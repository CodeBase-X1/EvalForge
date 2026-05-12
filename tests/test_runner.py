"""Tests for the eval runner and LLM-as-a-judge scoring."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from evalforge.core.runner import EvalRunner
from evalforge.models import EvalCase, EvalResult, ScoreLevel, ScoringCriteria


def make_case(case_id: str = "c1", cluster: str = "billing") -> EvalCase:
    return EvalCase(
        case_id=case_id,
        cluster_label=cluster,
        input="What is the refund policy?",
        expected_output="7-10 business days",
        rubric=[ScoringCriteria(criterion="Must mention days", weight=1.0)],
        judge_prompt="Score this answer: {actual_output}",
    )


class TestEvalRunner:
    def test_score_to_level_pass(self):
        runner = EvalRunner()
        assert runner._score_to_level(8.0) == ScoreLevel.PASS
        assert runner._score_to_level(7.0) == ScoreLevel.PASS
        assert runner._score_to_level(10.0) == ScoreLevel.PASS

    def test_score_to_level_partial(self):
        runner = EvalRunner()
        assert runner._score_to_level(5.0) == ScoreLevel.PARTIAL
        assert runner._score_to_level(4.0) == ScoreLevel.PARTIAL

    def test_score_to_level_fail(self):
        runner = EvalRunner()
        assert runner._score_to_level(3.9) == ScoreLevel.FAIL
        assert runner._score_to_level(0.0) == ScoreLevel.FAIL

    def test_run_requires_agent_fn(self):
        runner = EvalRunner(agent_fn=None)
        with pytest.raises(ValueError, match="agent_fn is required"):
            import asyncio

            asyncio.run(runner.run([make_case()]))

    @pytest.mark.asyncio
    async def test_run_with_outputs_length_mismatch(self):
        runner = EvalRunner()
        cases = [make_case("c1"), make_case("c2")]
        with pytest.raises(ValueError, match="same length"):
            await runner.run_with_outputs(cases, ["only one output"])

    @pytest.mark.asyncio
    async def test_run_with_outputs_scores_correctly(self):
        runner = EvalRunner()
        cases = [make_case("c1"), make_case("c2")]
        outputs = ["We refund within 7-10 business days.", "Sorry, I don't know."]

        mock_judgment_pass = {"score": 9, "reasoning": "Mentions days correctly"}
        mock_judgment_fail = {"score": 2, "reasoning": "No useful information"}

        judgment_by_case_id = {
            "c1": mock_judgment_pass,
            "c2": mock_judgment_fail,
        }

        async def mock_score(case, output, semaphore):
            j = judgment_by_case_id[case.case_id]
            score = float(j["score"])
            return EvalResult(
                case_id=case.case_id,
                input=case.input,
                expected_output=case.expected_output,
                actual_output=output,
                score=score,
                level=runner._score_to_level(score),
                judge_reasoning=j["reasoning"],
                cluster_label=case.cluster_label,
            )

        with patch.object(runner, "_score_single", side_effect=mock_score):
            results = await runner.run_with_outputs(cases, outputs)

        assert len(results) == 2
        assert results[0].level == ScoreLevel.PASS
        assert results[1].level == ScoreLevel.FAIL

    @pytest.mark.asyncio
    async def test_run_with_agent_fn(self):
        async def mock_agent(question: str) -> str:
            return "We offer refunds within 7-10 business days."

        runner = EvalRunner(agent_fn=mock_agent)
        cases = [make_case("c1")]

        mock_result = EvalResult(
            case_id="c1",
            input="What is the refund policy?",
            expected_output="7-10 business days",
            actual_output="We offer refunds within 7-10 business days.",
            score=9.0,
            level=ScoreLevel.PASS,
            judge_reasoning="Good answer",
            cluster_label="billing",
        )

        async def mock_score(case, output, semaphore):
            return mock_result

        with patch.object(runner, "_score_single", side_effect=mock_score):
            results = await runner.run(cases)

        assert len(results) == 1
        assert results[0].score == 9.0

    def test_log_summary_empty(self):
        """_log_summary should not crash on empty results."""
        runner = EvalRunner()
        runner._log_summary([])  # should not raise
