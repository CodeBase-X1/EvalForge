"""Export eval cases, rubrics, and results to JSON."""

from __future__ import annotations

import json
from pathlib import Path

from evalforge.models import Cluster, EvalCase, EvalResult, PipelineReport


def export_eval_cases(cases: list[EvalCase], path: str | Path) -> Path:
    """Export eval cases to a JSON file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [c.model_dump() for c in cases]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def export_judge_rubric(cases: list[EvalCase], path: str | Path) -> Path:
    """
    Export a judge_rubric.json file — a map of cluster_label → judge prompt template.

    This is the config you hand to your CI pipeline to run LLM-as-a-judge scoring.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    rubric: dict[str, dict] = {}
    for case in cases:
        if case.cluster_label not in rubric:
            rubric[case.cluster_label] = {
                "judge_prompt_template": case.judge_prompt,
                "rubric_criteria": [r.model_dump() for r in case.rubric],
            }

    path.write_text(json.dumps(rubric, indent=2), encoding="utf-8")
    return path


def export_clusters(clusters: list[Cluster], path: str | Path) -> Path:
    """Export cluster metadata (without full trace data) to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    data = [
        {
            "cluster_id": c.cluster_id,
            "label": c.label,
            "size": c.size,
            "failure_rate": c.failure_rate,
            "representative_inputs": c.representative_inputs,
        }
        for c in clusters
    ]
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def export_report(report: PipelineReport, path: str | Path) -> Path:
    """Export the pipeline report to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


def export_results(results: list[EvalResult], path: str | Path) -> Path:
    """Export eval results to JSON."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [r.model_dump() for r in results]
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path
