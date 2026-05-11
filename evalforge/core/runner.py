"""
Step 4 — Eval Runner

Runs the generated eval dataset against an agent and scores each response
using LLM-as-a-judge (Gemini).
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine

from evalforge.config import settings
from evalforge.models import EvalCase, EvalResult, ScoreLevel

logger = logging.getLogger(__name__)

# Type alias for an agent callable
AgentFn = Callable[[str], Coroutine[Any, Any, str]]


class EvalRunner:
    """
    Runs eval cases against an agent and scores them with LLM-as-a-judge.

    Usage:
        runner = EvalRunner(agent_fn=my_agent)
        results = await runner.run(eval_cases)
    """

    PASS_THRESHOLD = 7.0    # score >= 7 → pass
    PARTIAL_THRESHOLD = 4.0  # score >= 4 → partial

    def __init__(
        self,
        agent_fn: AgentFn | None = None,
        concurrency: int = 5,
    ) -> None:
        """
        Args:
            agent_fn: Async callable that takes a question string and returns
                      the agent's answer string. If None, you must call
                      run_with_outputs() directly.
            concurrency: Max parallel eval cases to run at once.
        """
        self.agent_fn = agent_fn
        self.concurrency = concurrency

    # ── Public API ────────────────────────────────────────────────────────────

    async def run(self, eval_cases: list[EvalCase]) -> list[EvalResult]:
        """
        Run all eval cases through the agent and score them.

        Requires agent_fn to be set.
        """
        if self.agent_fn is None:
            raise ValueError(
                "agent_fn is required. Pass your agent callable to EvalRunner()."
            )

        logger.info(f"Running {len(eval_cases)} eval cases (concurrency={self.concurrency})")

        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._run_single(case, semaphore)
            for case in eval_cases
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        clean_results: list[EvalResult] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Case {eval_cases[i].case_id} failed: {result}")
            else:
                clean_results.append(result)

        self._log_summary(clean_results)
        return clean_results

    async def run_with_outputs(
        self,
        eval_cases: list[EvalCase],
        actual_outputs: list[str],
    ) -> list[EvalResult]:
        """
        Score pre-computed outputs (useful when you already have agent responses).

        Args:
            eval_cases: The eval cases.
            actual_outputs: The agent's responses, one per eval case.
        """
        if len(eval_cases) != len(actual_outputs):
            raise ValueError("eval_cases and actual_outputs must have the same length")

        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = [
            self._score_single(case, output, semaphore)
            for case, output in zip(eval_cases, actual_outputs)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        clean_results = [r for r in results if not isinstance(r, Exception)]
        self._log_summary(clean_results)
        return clean_results

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _run_single(
        self,
        case: EvalCase,
        semaphore: asyncio.Semaphore,
    ) -> EvalResult:
        """Run one eval case: call agent, then score."""
        async with semaphore:
            actual_output = await self.agent_fn(case.input)  # type: ignore[misc]
            return await self._score_single(case, actual_output, semaphore)

    async def _score_single(
        self,
        case: EvalCase,
        actual_output: str,
        semaphore: asyncio.Semaphore,
    ) -> EvalResult:
        """Score one eval case using LLM-as-a-judge."""
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            settings.gemini_model,
            generation_config={"response_mime_type": "application/json"},
        )

        # Fill in the actual output in the judge prompt
        judge_prompt = case.judge_prompt.replace("{actual_output}", actual_output)

        try:
            response = await model.generate_content_async(judge_prompt)
            judgment = json.loads(response.text)
        except json.JSONDecodeError:
            # Fallback: try to extract score from raw text
            judgment = {"score": 0, "reasoning": "Failed to parse judge response"}
        except Exception as exc:
            logger.warning(f"Judge API error for case {case.case_id}: {exc}")
            judgment = {"score": 0, "reasoning": str(exc)}

        score = float(judgment.get("score", 0))
        level = self._score_to_level(score)

        return EvalResult(
            case_id=case.case_id,
            input=case.input,
            expected_output=case.expected_output,
            actual_output=actual_output,
            score=score,
            level=level,
            judge_reasoning=judgment.get("reasoning", ""),
            cluster_label=case.cluster_label,
        )

    def _score_to_level(self, score: float) -> ScoreLevel:
        if score >= self.PASS_THRESHOLD:
            return ScoreLevel.PASS
        elif score >= self.PARTIAL_THRESHOLD:
            return ScoreLevel.PARTIAL
        return ScoreLevel.FAIL

    def _log_summary(self, results: list[EvalResult]) -> None:
        if not results:
            return
        total = len(results)
        passed = sum(1 for r in results if r.level == ScoreLevel.PASS)
        partial = sum(1 for r in results if r.level == ScoreLevel.PARTIAL)
        failed = sum(1 for r in results if r.level == ScoreLevel.FAIL)
        avg_score = sum(r.score for r in results) / total

        logger.info(
            f"Eval complete: {passed}/{total} pass ({passed/total:.0%}), "
            f"{partial} partial, {failed} fail | avg score: {avg_score:.1f}/10"
        )
