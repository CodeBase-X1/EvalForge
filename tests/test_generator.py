"""Tests for the eval generator."""

from __future__ import annotations

from evalforge.core.generator import EvalGenerator
from evalforge.models import Cluster, EvalCase, Trace


def make_cluster(label: str = "billing", n: int = 5) -> Cluster:
    traces = [
        Trace(
            trace_id=f"t{i}",
            input=f"billing question {i}",
            output=f"unhelpful answer {i}",
            score=0.2,
        )
        for i in range(n)
    ]
    return Cluster(
        cluster_id=0,
        label=label,
        traces=traces,
        failure_rate=0.8,
    )


class TestEvalGenerator:
    def test_init_default(self):
        gen = EvalGenerator()
        assert gen.cases_per_cluster == 10

    def test_init_custom(self):
        gen = EvalGenerator(cases_per_cluster=5)
        assert gen.cases_per_cluster == 5

    def test_format_examples(self):
        gen = EvalGenerator()
        cluster = make_cluster(n=3)
        examples = gen._format_examples(cluster)
        assert "Example 1:" in examples
        assert "billing question 0" in examples
        assert "unhelpful answer 0" in examples

    def test_format_examples_caps_at_5(self):
        gen = EvalGenerator()
        cluster = make_cluster(n=10)
        examples = gen._format_examples(cluster)
        # Should only show up to 5 examples
        assert "Example 5:" in examples
        assert "Example 6:" not in examples

    def test_is_valid_raw_case_valid(self):
        gen = EvalGenerator()
        raw = {
            "input": "What is the refund policy?",
            "expected_output": "7-10 business days",
            "rubric": [{"criterion": "Must mention days", "weight": 1.0}],
        }
        assert gen._is_valid_raw_case(raw) is True

    def test_is_valid_raw_case_missing_field(self):
        gen = EvalGenerator()
        assert gen._is_valid_raw_case({"input": "q", "expected_output": "a"}) is False
        assert gen._is_valid_raw_case({"input": "q", "rubric": []}) is False
        assert gen._is_valid_raw_case({"expected_output": "a", "rubric": []}) is False

    def test_is_valid_raw_case_wrong_type(self):
        gen = EvalGenerator()
        assert gen._is_valid_raw_case("not a dict") is False  # type: ignore
        assert gen._is_valid_raw_case({"input": "q", "expected_output": "a", "rubric": "bad"}) is False

    def test_raw_to_eval_case(self):
        gen = EvalGenerator()
        cluster = make_cluster("billing")
        raw = {
            "input": "When do I get my refund?",
            "expected_output": "Within 7-10 business days",
            "rubric": [
                {"criterion": "Must mention days", "weight": 1.0},
                {"criterion": "Must be specific", "weight": 0.5},
            ],
        }
        case = gen._raw_to_eval_case(raw, cluster)

        assert isinstance(case, EvalCase)
        assert case.cluster_label == "billing"
        assert case.input == "When do I get my refund?"
        assert case.expected_output == "Within 7-10 business days"
        assert len(case.rubric) == 2
        assert case.rubric[0].criterion == "Must mention days"
        assert case.rubric[1].weight == 0.5
        # Judge prompt should have placeholder for actual_output
        assert "{actual_output}" in case.judge_prompt

    def test_raw_to_eval_case_skips_empty_criteria(self):
        gen = EvalGenerator()
        cluster = make_cluster()
        raw = {
            "input": "q",
            "expected_output": "a",
            "rubric": [
                {"criterion": "Valid criterion", "weight": 1.0},
                {"criterion": "", "weight": 1.0},  # empty — should be skipped
            ],
        }
        case = gen._raw_to_eval_case(raw, cluster)
        assert len(case.rubric) == 1

    def test_raw_to_eval_case_source_trace_ids(self):
        gen = EvalGenerator()
        cluster = make_cluster(n=5)
        raw = {"input": "q", "expected_output": "a", "rubric": [{"criterion": "c", "weight": 1.0}]}
        case = gen._raw_to_eval_case(raw, cluster)
        # Should include up to 3 source trace IDs
        assert len(case.source_trace_ids) <= 3
        assert all(tid.startswith("t") for tid in case.source_trace_ids)
