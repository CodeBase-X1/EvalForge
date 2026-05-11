"""Export eval cases and results to CSV."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from evalforge.models import EvalCase, EvalResult


def export_eval_cases(cases: list[EvalCase], path: str | Path) -> Path:
    """
    Export eval cases to a CSV file.

    Columns: case_id, cluster_label, input, expected_output, rubric
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["case_id", "cluster_label", "input", "expected_output", "rubric"],
        )
        writer.writeheader()
        for case in cases:
            writer.writerow(
                {
                    "case_id": case.case_id,
                    "cluster_label": case.cluster_label,
                    "input": case.input,
                    "expected_output": case.expected_output,
                    "rubric": json.dumps([r.model_dump() for r in case.rubric]),
                }
            )

    return path


def export_eval_results(results: list[EvalResult], path: str | Path) -> Path:
    """
    Export eval results to a CSV file.

    Columns: case_id, cluster_label, score, level, input, expected_output,
             actual_output, judge_reasoning
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "cluster_label",
                "score",
                "level",
                "input",
                "expected_output",
                "actual_output",
                "judge_reasoning",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "case_id": result.case_id,
                    "cluster_label": result.cluster_label,
                    "score": result.score,
                    "level": result.level.value,
                    "input": result.input,
                    "expected_output": result.expected_output,
                    "actual_output": result.actual_output,
                    "judge_reasoning": result.judge_reasoning,
                }
            )

    return path
