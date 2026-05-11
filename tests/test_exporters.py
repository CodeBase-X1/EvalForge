"""Tests for CSV and JSON exporters."""

import csv
import json
import tempfile
from pathlib import Path

import pytest

from evalforge.exporters import csv_exporter, json_exporter
from evalforge.models import EvalCase, EvalResult, ScoreLevel, ScoringCriteria


@pytest.fixture
def sample_cases():
    return [
        EvalCase(
            case_id="c1",
            cluster_label="billing",
            input="What is the refund policy?",
            expected_output="7-10 business days",
            rubric=[ScoringCriteria(criterion="Must mention days", weight=1.0)],
            judge_prompt="Score: {actual_output}",
        ),
        EvalCase(
            case_id="c2",
            cluster_label="cancellation",
            input="How do I cancel?",
            expected_output="Go to Settings > Cancel",
            rubric=[ScoringCriteria(criterion="Must give exact steps", weight=1.0)],
            judge_prompt="Score: {actual_output}",
        ),
    ]


@pytest.fixture
def sample_results():
    return [
        EvalResult(
            case_id="c1",
            input="What is the refund policy?",
            expected_output="7-10 business days",
            actual_output="We offer refunds within 7-10 business days.",
            score=8.5,
            level=ScoreLevel.PASS,
            judge_reasoning="Mentions specific days",
            cluster_label="billing",
        ),
    ]


class TestCsvExporter:
    def test_export_eval_cases(self, sample_cases):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "eval_dataset.csv"
            result_path = csv_exporter.export_eval_cases(sample_cases, path)

            assert result_path.exists()
            with open(result_path, newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)

            assert len(rows) == 2
            assert rows[0]["case_id"] == "c1"
            assert rows[0]["cluster_label"] == "billing"
            assert rows[1]["input"] == "How do I cancel?"

    def test_export_creates_parent_dirs(self, sample_cases):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "nested" / "dir" / "eval.csv"
            csv_exporter.export_eval_cases(sample_cases, path)
            assert path.exists()


class TestJsonExporter:
    def test_export_eval_cases(self, sample_cases):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "eval_dataset.json"
            json_exporter.export_eval_cases(sample_cases, path)

            data = json.loads(path.read_text())
            assert len(data) == 2
            assert data[0]["case_id"] == "c1"

    def test_export_judge_rubric(self, sample_cases):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "judge_rubric.json"
            json_exporter.export_judge_rubric(sample_cases, path)

            rubric = json.loads(path.read_text())
            assert "billing" in rubric
            assert "cancellation" in rubric
            assert "judge_prompt_template" in rubric["billing"]
            assert "rubric_criteria" in rubric["billing"]
