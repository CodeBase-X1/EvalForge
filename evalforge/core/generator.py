"""
Step 3 — Eval Generator

For each failure cluster, uses Gemini to generate:
  - Representative test questions
  - Ideal expected answers
  - Scoring rubric (what makes a good answer)
  - Ready-to-use LLM-as-judge prompt
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from evalforge.config import settings
from evalforge.models import Cluster, EvalCase, ScoringCriteria

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

EVAL_GENERATION_PROMPT = """\
You are an expert at building evaluation datasets for AI assistants.

I have a cluster of user questions where an AI assistant is frequently failing.
Your job is to generate a high-quality eval dataset for this cluster.

## Cluster Topic
{cluster_label}

## Failure Rate
{failure_rate:.0%} of interactions in this cluster are failures.

## Example Interactions (input → output pairs from production)
{examples}

## Your Task
Generate {n_cases} diverse test cases for this cluster. Each test case must have:
1. A realistic user question (similar to but not identical to the examples)
2. The ideal expected answer
3. A scoring rubric (3-5 specific criteria for judging a good answer)

Return a JSON array with this exact structure:
[
  {{
    "input": "user question here",
    "expected_output": "ideal answer here",
    "rubric": [
      {{"criterion": "specific thing the answer must do or include", "weight": 1.0}},
      ...
    ]
  }},
  ...
]

Rules:
- Questions must be realistic and varied (different phrasings, edge cases)
- Expected answers must be specific and complete, not vague
- Rubric criteria must be concrete and checkable (not "be helpful")
- Cover edge cases and tricky variations, not just the happy path

Return ONLY the JSON array, no other text.
"""

JUDGE_PROMPT_TEMPLATE = """\
You are an expert evaluator for an AI assistant.

## Question
{input}

## Ideal Answer
{expected_output}

## Scoring Rubric
{rubric}

## Agent's Actual Answer
{actual_output}

## Your Task
Score the agent's answer on a scale of 0-10 based on the rubric above.

Return a JSON object with:
{{
  "score": <number 0-10>,
  "reasoning": "<brief explanation of the score>",
  "criteria_scores": {{
    "<criterion>": <0 or 1>,
    ...
  }}
}}

Return ONLY the JSON object, no other text.
"""


class EvalGenerator:
    """
    Generates eval cases for each failure cluster using Gemini.
    """

    def __init__(self, cases_per_cluster: int | None = None) -> None:
        self.cases_per_cluster = cases_per_cluster or settings.evalforge_cases_per_cluster

    # ── Public API ────────────────────────────────────────────────────────────

    async def generate(self, clusters: list[Cluster]) -> list[EvalCase]:
        """
        Generate eval cases for all clusters.

        Returns a flat list of EvalCase objects across all clusters.
        """
        all_cases: list[EvalCase] = []

        for cluster in clusters:
            logger.info(
                f"Generating {self.cases_per_cluster} eval cases "
                f"for cluster '{cluster.label}' ({cluster.failure_rate:.0%} failure rate)"
            )
            cases = await self._generate_for_cluster(cluster)
            all_cases.extend(cases)
            logger.info(f"  Generated {len(cases)} cases for '{cluster.label}'")

        logger.info(f"Total eval cases generated: {len(all_cases)}")
        return all_cases

    # ── Per-cluster generation ────────────────────────────────────────────────

    async def _generate_for_cluster(self, cluster: Cluster) -> list[EvalCase]:
        """Generate eval cases for a single cluster."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        # Build example interactions for the prompt
        examples = self._format_examples(cluster)

        prompt = EVAL_GENERATION_PROMPT.format(
            cluster_label=cluster.label,
            failure_rate=cluster.failure_rate,
            examples=examples,
            n_cases=self.cases_per_cluster,
        )

        try:
            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw_cases = json.loads(response.text)
        except json.JSONDecodeError as exc:
            logger.error(f"Gemini returned invalid JSON for cluster '{cluster.label}': {exc}")
            return []
        except Exception as exc:
            logger.error(f"Gemini API error for cluster '{cluster.label}': {exc}")
            return []

        return [
            self._raw_to_eval_case(raw, cluster)
            for raw in raw_cases
            if self._is_valid_raw_case(raw)
        ]

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _format_examples(self, cluster: Cluster) -> str:
        """Format up to 5 trace examples for the prompt."""
        lines: list[str] = []
        for i, trace in enumerate(cluster.traces[:5], 1):
            lines.append(f"Example {i}:")
            lines.append(f"  Input:  {trace.input[:300]}")
            lines.append(f"  Output: {trace.output[:300]}")
            if trace.score is not None:
                lines.append(f"  Score:  {trace.score:.2f}")
            lines.append("")
        return "\n".join(lines)

    def _is_valid_raw_case(self, raw: Any) -> bool:
        """Check that a raw dict has the required fields."""
        return (
            isinstance(raw, dict)
            and "input" in raw
            and "expected_output" in raw
            and "rubric" in raw
            and isinstance(raw["rubric"], list)
        )

    def _raw_to_eval_case(self, raw: dict[str, Any], cluster: Cluster) -> EvalCase:
        """Convert a raw Gemini-generated dict into an EvalCase."""
        rubric = [
            ScoringCriteria(
                criterion=r.get("criterion", ""),
                weight=float(r.get("weight", 1.0)),
            )
            for r in raw["rubric"]
            if r.get("criterion")
        ]

        rubric_text = "\n".join(
            f"- {r.criterion} (weight: {r.weight})" for r in rubric
        )

        judge_prompt = JUDGE_PROMPT_TEMPLATE.format(
            input=raw["input"],
            expected_output=raw["expected_output"],
            rubric=rubric_text,
            actual_output="{actual_output}",  # placeholder for runtime
        )

        return EvalCase(
            case_id=str(uuid.uuid4()),
            cluster_label=cluster.label,
            input=raw["input"],
            expected_output=raw["expected_output"],
            rubric=rubric,
            judge_prompt=judge_prompt,
            source_trace_ids=[t.trace_id for t in cluster.traces[:3]],
        )
