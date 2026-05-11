"""Tests for EvalForge data models."""

import pytest
from evalforge.models import (
    Cluster,
    EvalCase,
    EvalResult,
    ScoreLevel,
    ScoringCriteria,
    Trace,
)


class TestTrace:
    def test_is_failure_below_threshold(self):
        trace = Trace(trace_id="t1", input="hello", output="world", score=0.3)
        assert trace.is_failure is True

    def test_is_not_failure_above_threshold(self):
        trace = Trace(trace_id="t1", input="hello", output="world", score=0.8)
        assert trace.is_failure is False

    def test_is_not_failure_when_no_score(self):
        trace = Trace(trace_id="t1", input="hello", output="world")
        assert trace.is_failure is False


class TestCluster:
    def _make_cluster(self, scores: list[float]) -> Cluster:
        traces = [
            Trace(trace_id=f"t{i}", input=f"q{i}", output=f"a{i}", score=s)
            for i, s in enumerate(scores)
        ]
        failures = [t for t in traces if t.is_failure]
        failure_rate = len(failures) / len(traces) if traces else 0.0
        return Cluster(
            cluster_id=0,
            label="test_cluster",
            traces=traces,
            failure_rate=failure_rate,
        )

    def test_size(self):
        cluster = self._make_cluster([0.1, 0.2, 0.9])
        assert cluster.size == 3

    def test_failure_rate(self):
        cluster = self._make_cluster([0.1, 0.2, 0.9])
        # 2 out of 3 are failures (score < 0.5)
        assert cluster.failure_rate == pytest.approx(2 / 3)

    def test_representative_inputs(self):
        cluster = self._make_cluster([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
        reps = cluster.representative_inputs
        assert len(reps) <= 5


class TestEvalCase:
    def test_eval_case_creation(self):
        case = EvalCase(
            case_id="c1",
            cluster_label="billing",
            input="What is the refund policy?",
            expected_output="7-10 business days",
            rubric=[ScoringCriteria(criterion="Must mention days", weight=1.0)],
            judge_prompt="Score this: {actual_output}",
        )
        assert case.case_id == "c1"
        assert len(case.rubric) == 1


class TestEvalResult:
    def test_pass_level(self):
        result = EvalResult(
            case_id="c1",
            input="q",
            expected_output="a",
            actual_output="a",
            score=8.5,
            level=ScoreLevel.PASS,
            judge_reasoning="Good answer",
            cluster_label="billing",
        )
        assert result.level == ScoreLevel.PASS

    def test_fail_level(self):
        result = EvalResult(
            case_id="c1",
            input="q",
            expected_output="a",
            actual_output="wrong",
            score=2.0,
            level=ScoreLevel.FAIL,
            judge_reasoning="Wrong answer",
            cluster_label="billing",
        )
        assert result.level == ScoreLevel.FAIL
