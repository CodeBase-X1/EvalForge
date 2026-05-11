"""
Quick smoke test for the full EvalForge pipeline.
Requires mock_phoenix.py to be running on localhost:6006.

Run:
    python examples/customer_support/mock_phoenix.py   (in one terminal)
    python scripts/check_pipeline.py                   (in another)
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from evalforge.core.fetcher import PhoenixFetcher
from evalforge.core.clusterer import FailureClusterer
from evalforge.exporters import csv_exporter, json_exporter
from pathlib import Path


async def main():
    print("\n=== EvalForge Pipeline Smoke Test ===\n")

    # Step 1: Fetch
    print("Step 1: Fetching traces from mock Phoenix...")
    fetcher = PhoenixFetcher(endpoint="http://localhost:6006")
    traces = await fetcher.fetch_traces(limit=100)
    failures = [t for t in traces if t.is_failure]
    print(f"  ✓ Fetched {len(traces)} traces, {len(failures)} failures\n")
    assert len(traces) > 0, "No traces returned"
    assert len(failures) > 0, "No failures found"

    # Step 2: Cluster
    print("Step 2: Clustering failures (using sentence-transformers)...")
    print("  (downloading model on first run — may take a minute)")
    clusterer = FailureClusterer(num_clusters=3)
    clusters = await clusterer.cluster(failures)
    print(f"  ✓ Found {len(clusters)} clusters:")
    for c in clusters:
        print(f"      {c.label:<30} {c.size} traces  {c.failure_rate:.0%} failure rate")
    print()
    assert len(clusters) > 0, "No clusters found"

    # Step 3: Export (skip Gemini generation — no API key in smoke test)
    print("Step 3: Testing exporters...")
    from evalforge.models import EvalCase, ScoringCriteria
    import uuid

    dummy_cases = [
        EvalCase(
            case_id=str(uuid.uuid4()),
            cluster_label=clusters[0].label,
            input="What is the refund policy?",
            expected_output="7-10 business days",
            rubric=[ScoringCriteria(criterion="Must mention days", weight=1.0)],
            judge_prompt="Score: {actual_output}",
        )
    ]

    out = Path("./output/smoke_test")
    csv_path = csv_exporter.export_eval_cases(dummy_cases, out / "eval_dataset.csv")
    json_path = json_exporter.export_eval_cases(dummy_cases, out / "eval_dataset.json")
    rubric_path = json_exporter.export_judge_rubric(dummy_cases, out / "judge_rubric.json")
    cluster_path = json_exporter.export_clusters(clusters, out / "clusters.json")

    for p in [csv_path, json_path, rubric_path, cluster_path]:
        assert p.exists(), f"Missing output file: {p}"
        print(f"  ✓ {p}")

    print()
    print("=== All checks passed ✓ ===")
    print(f"\nOutput written to: {out}/")
    print("\nNote: Eval generation (Step 3) requires GEMINI_API_KEY.")
    print("      Set it in .env and run: evalforge run --traces 100")


if __name__ == "__main__":
    asyncio.run(main())
