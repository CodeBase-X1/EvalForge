"""
Google ADK tool definitions for the EvalForge agent.

Each function here becomes a tool the agent can call.
"""

from __future__ import annotations

import logging
from typing import Any

from evalforge.config import settings
from evalforge.core.clusterer import FailureClusterer
from evalforge.core.fetcher import PhoenixFetcher
from evalforge.core.generator import EvalGenerator
from evalforge.models import Cluster, EvalCase, Trace

logger = logging.getLogger(__name__)

# ── In-memory state shared between tool calls ─────────────────────────────────
# (In production you'd use a proper session store)
_state: dict[str, Any] = {
    "traces": [],
    "clusters": [],
    "eval_cases": [],
}


async def fetch_traces(
    limit: int = 500,
    project_name: str | None = None,
) -> dict[str, Any]:
    """
    Fetch production traces from Phoenix.

    Args:
        limit: Maximum number of traces to fetch.
        project_name: Optional Phoenix project name to filter by.

    Returns:
        Summary dict with trace count and failure count.
    """
    fetcher = PhoenixFetcher()
    traces = await fetcher.fetch_traces(limit=limit, project_name=project_name)
    _state["traces"] = traces

    failures = [t for t in traces if t.is_failure]
    return {
        "total_traces": len(traces),
        "failure_count": len(failures),
        "failure_rate": len(failures) / len(traces) if traces else 0,
        "message": (
            f"Fetched {len(traces)} traces. "
            f"Found {len(failures)} failures ({len(failures) / len(traces):.0%})."
            if traces
            else "No traces found."
        ),
    }


async def cluster_failures(num_clusters: int = 0) -> dict[str, Any]:
    """
    Cluster the failing traces by semantic similarity.

    Args:
        num_clusters: Number of clusters (0 = auto-detect).

    Returns:
        Summary of clusters found.
    """
    traces: list[Trace] = _state.get("traces", [])
    if not traces:
        return {"error": "No traces loaded. Call fetch_traces first."}

    failures = [t for t in traces if t.is_failure]
    if not failures:
        return {"message": "No failures found — your agent is doing great!"}

    clusterer = FailureClusterer(num_clusters=num_clusters)
    clusters = await clusterer.cluster(failures)
    _state["clusters"] = clusters

    return {
        "clusters_found": len(clusters),
        "clusters": [
            {
                "label": c.label,
                "size": c.size,
                "failure_rate": f"{c.failure_rate:.0%}",
            }
            for c in clusters
        ],
        "message": (
            f"Found {len(clusters)} failure clusters. "
            "Worst cluster: "
            + (
                f"'{clusters[0].label}' at {clusters[0].failure_rate:.0%} failure rate"
                if clusters
                else "none"
            )
        ),
    }


async def generate_eval_cases(cases_per_cluster: int = 10) -> dict[str, Any]:
    """
    Generate eval cases for each failure cluster using Gemini.

    Args:
        cases_per_cluster: Number of test cases to generate per cluster.

    Returns:
        Summary of eval cases generated.
    """
    clusters: list[Cluster] = _state.get("clusters", [])
    if not clusters:
        return {"error": "No clusters found. Call cluster_failures first."}

    generator = EvalGenerator(cases_per_cluster=cases_per_cluster)
    eval_cases = await generator.generate(clusters)
    _state["eval_cases"] = eval_cases

    by_cluster: dict[str, int] = {}
    for case in eval_cases:
        by_cluster[case.cluster_label] = by_cluster.get(case.cluster_label, 0) + 1

    return {
        "total_cases": len(eval_cases),
        "by_cluster": by_cluster,
        "message": (f"Generated {len(eval_cases)} eval cases across {len(by_cluster)} clusters."),
    }


async def export_eval_dataset(output_dir: str | None = None) -> dict[str, Any]:
    """
    Export the generated eval dataset to CSV, JSON, and a judge rubric.

    Args:
        output_dir: Directory to write output files. Defaults to ./output.

    Returns:
        Paths to the exported files.
    """
    from pathlib import Path

    from evalforge.exporters import csv_exporter, json_exporter

    eval_cases: list[EvalCase] = _state.get("eval_cases", [])
    if not eval_cases:
        return {"error": "No eval cases generated. Call generate_eval_cases first."}

    out = Path(output_dir or settings.evalforge_output_dir)
    out.mkdir(parents=True, exist_ok=True)

    csv_path = csv_exporter.export_eval_cases(eval_cases, out / "eval_dataset.csv")
    json_path = json_exporter.export_eval_cases(eval_cases, out / "eval_dataset.json")
    rubric_path = json_exporter.export_judge_rubric(eval_cases, out / "judge_rubric.json")

    return {
        "files_written": [str(csv_path), str(json_path), str(rubric_path)],
        "message": (
            f"Exported {len(eval_cases)} eval cases to {out}. "
            "Files: eval_dataset.csv, eval_dataset.json, judge_rubric.json"
        ),
    }


def get_pipeline_status() -> dict[str, Any]:
    """
    Return the current state of the EvalForge pipeline.

    Useful for the agent to check what has been done so far.
    """
    traces: list = _state.get("traces", [])
    clusters: list = _state.get("clusters", [])
    eval_cases: list = _state.get("eval_cases", [])

    return {
        "traces_loaded": len(traces),
        "clusters_found": len(clusters),
        "eval_cases_generated": len(eval_cases),
        "next_step": (
            "fetch_traces"
            if not traces
            else "cluster_failures"
            if not clusters
            else "generate_eval_cases"
            if not eval_cases
            else "export_eval_dataset"
        ),
    }
