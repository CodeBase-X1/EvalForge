"""
EvalForge Agent — built with Google ADK.

This agent orchestrates the full pipeline:
  1. Fetch traces from Phoenix
  2. Cluster failures
  3. Generate eval cases
  4. Export the dataset

Run with:
    python -m evalforge.agent.agent
"""

from __future__ import annotations

import asyncio
import logging

from evalforge.config import settings

logger = logging.getLogger(__name__)

AGENT_INSTRUCTION = """\
You are EvalForge, an AI agent that automatically generates eval datasets
from production AI agent traces.

Your job is to run a 4-step pipeline:

1. **fetch_traces** — Pull production traces from Phoenix
2. **cluster_failures** — Group similar failures together
3. **generate_eval_cases** — Generate test cases + rubrics for each cluster
4. **export_eval_dataset** — Save everything to disk

Always start by calling get_pipeline_status() to see what has already been done.
Then run the remaining steps in order.

After each step, summarize what you found in plain English.
Be specific: mention cluster names, failure rates, and case counts.

When the pipeline is complete, give the user a clear summary:
- How many traces were analyzed
- What failure clusters were found (with failure rates)
- How many eval cases were generated
- Where the files were saved
"""


def create_agent():
    """
    Create and return the EvalForge ADK agent.

    Returns a google.adk.agents.Agent instance.
    """
    try:
        from google.adk.agents import Agent
        from google.adk.models.lite_llm import LiteLlm
    except ImportError:
        raise ImportError(
            "google-adk is required. Install it with: pip install google-adk"
        )

    from evalforge.agent.tools import (
        cluster_failures,
        export_eval_dataset,
        fetch_traces,
        generate_eval_cases,
        get_pipeline_status,
    )

    agent = Agent(
        name="evalforge",
        model=LiteLlm(model=f"gemini/{settings.gemini_model}"),
        description="Auto-generates eval suites from production AI agent traces",
        instruction=AGENT_INSTRUCTION,
        tools=[
            get_pipeline_status,
            fetch_traces,
            cluster_failures,
            generate_eval_cases,
            export_eval_dataset,
        ],
    )

    return agent


async def run_pipeline(
    trace_limit: int = 500,
    output_dir: str | None = None,
    project_name: str | None = None,
) -> None:
    """
    Run the full EvalForge pipeline programmatically (no agent loop).

    This is the direct API — useful for CI/CD integration.
    """
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, TextColumn

    from evalforge.core.clusterer import FailureClusterer
    from evalforge.core.fetcher import PhoenixFetcher
    from evalforge.core.generator import EvalGenerator
    from evalforge.exporters import csv_exporter, json_exporter

    console = Console()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        # Step 1: Fetch
        task = progress.add_task("Fetching traces from Phoenix...", total=None)
        fetcher = PhoenixFetcher()
        traces = await fetcher.fetch_traces(limit=trace_limit, project_name=project_name)
        failures = [t for t in traces if t.is_failure]
        progress.update(task, description=f"✓ Fetched {len(traces)} traces, {len(failures)} failures")
        progress.stop_task(task)

        if not failures:
            console.print("[green]No failures found — your agent is doing great![/green]")
            return

        # Step 2: Cluster
        task = progress.add_task("Clustering failures...", total=None)
        clusterer = FailureClusterer()
        clusters = await clusterer.cluster(failures)
        progress.update(task, description=f"✓ Found {len(clusters)} failure clusters")
        progress.stop_task(task)

        # Step 3: Generate
        task = progress.add_task("Generating eval cases with Gemini...", total=None)
        generator = EvalGenerator()
        eval_cases = await generator.generate(clusters)
        progress.update(task, description=f"✓ Generated {len(eval_cases)} eval cases")
        progress.stop_task(task)

        # Step 4: Export
        task = progress.add_task("Exporting eval dataset...", total=None)
        from pathlib import Path
        out = Path(output_dir or settings.evalforge_output_dir)
        csv_exporter.export_eval_cases(eval_cases, out / "eval_dataset.csv")
        json_exporter.export_eval_cases(eval_cases, out / "eval_dataset.json")
        json_exporter.export_judge_rubric(eval_cases, out / "judge_rubric.json")
        json_exporter.export_clusters(clusters, out / "clusters.json")
        progress.update(task, description=f"✓ Saved to {out}/")
        progress.stop_task(task)

    # Summary
    console.print()
    console.print("[bold]EvalForge complete![/bold]")
    console.print(f"  Traces analyzed:    {len(traces)}")
    console.print(f"  Failure clusters:   {len(clusters)}")
    console.print(f"  Eval cases:         {len(eval_cases)}")
    console.print()
    console.print("[bold]Clusters (worst first):[/bold]")
    for c in clusters:
        bar = "█" * int(c.failure_rate * 20)
        console.print(f"  {c.label:<30} {c.failure_rate:.0%}  {bar}")
    console.print()
    console.print(f"[bold]Output:[/bold] {out}/")


if __name__ == "__main__":
    asyncio.run(run_pipeline())
