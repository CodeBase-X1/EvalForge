"""
EvalForge Web UI — FastAPI + HTMX

Run with:
    evalforge ui
    # or
    uvicorn evalforge.ui.app:app --reload
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from evalforge.config import settings
from evalforge.core.clusterer import FailureClusterer
from evalforge.core.fetcher import PhoenixFetcher
from evalforge.core.generator import EvalGenerator
from evalforge.exporters import csv_exporter, json_exporter
from evalforge.models import Cluster, EvalCase

logger = logging.getLogger(__name__)

app = FastAPI(
    title="EvalForge",
    description="Auto-generate eval suites from production AI agent traces",
    version="0.1.0",
)

# Templates
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))

# In-memory pipeline state (per-process; use Redis for multi-worker)
_pipeline_state: dict[str, Any] = {
    "status": "idle",
    "traces": [],
    "clusters": [],
    "eval_cases": [],
    "error": None,
    "log": [],
}


# ── Pages ─────────────────────────────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/results", response_class=HTMLResponse)
async def results_page(request: Request):
    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "clusters": _pipeline_state["clusters"],
            "eval_cases": _pipeline_state["eval_cases"],
        },
    )


# ── API ───────────────────────────────────────────────────────────────────────


@app.get("/api/status")
async def get_status():
    """Return current pipeline status."""
    state = _pipeline_state
    return {
        "status": state["status"],
        "traces_loaded": len(state["traces"]),
        "clusters_found": len(state["clusters"]),
        "eval_cases_generated": len(state["eval_cases"]),
        "error": state["error"],
        "log": state["log"][-20:],  # last 20 log lines
    }


@app.post("/api/run")
async def run_pipeline(background_tasks: BackgroundTasks, request: Request):
    """Start the EvalForge pipeline in the background."""
    body = await request.json()
    trace_limit = int(body.get("trace_limit", settings.evalforge_trace_limit))
    project_name = body.get("project_name")

    if _pipeline_state["status"] == "running":
        return JSONResponse({"error": "Pipeline already running"}, status_code=409)

    _pipeline_state.update(
        {
            "status": "running",
            "traces": [],
            "clusters": [],
            "eval_cases": [],
            "error": None,
            "log": [],
        }
    )

    background_tasks.add_task(_run_pipeline_bg, trace_limit, project_name)
    return {"message": "Pipeline started"}


@app.get("/api/clusters")
async def get_clusters():
    """Return cluster data for the chart."""
    clusters: list[Cluster] = _pipeline_state["clusters"]
    return [
        {
            "label": c.label,
            "size": c.size,
            "failure_rate": round(c.failure_rate, 3),
            "representative_inputs": c.representative_inputs,
        }
        for c in clusters
    ]


@app.get("/api/eval-cases")
async def get_eval_cases():
    """Return generated eval cases."""
    cases: list[EvalCase] = _pipeline_state["eval_cases"]
    return [
        {
            "case_id": c.case_id,
            "cluster_label": c.cluster_label,
            "input": c.input,
            "expected_output": c.expected_output,
            "rubric": [r.model_dump() for r in c.rubric],
        }
        for c in cases
    ]


@app.get("/api/download/csv")
async def download_csv():
    """Download the eval dataset as CSV."""
    cases: list[EvalCase] = _pipeline_state["eval_cases"]
    if not cases:
        return JSONResponse({"error": "No eval cases generated yet"}, status_code=404)

    out_path = Path(settings.evalforge_output_dir) / "eval_dataset.csv"
    csv_exporter.export_eval_cases(cases, out_path)
    return FileResponse(str(out_path), filename="eval_dataset.csv", media_type="text/csv")


@app.get("/api/download/json")
async def download_json():
    """Download the eval dataset as JSON."""
    cases: list[EvalCase] = _pipeline_state["eval_cases"]
    if not cases:
        return JSONResponse({"error": "No eval cases generated yet"}, status_code=404)

    out_path = Path(settings.evalforge_output_dir) / "eval_dataset.json"
    json_exporter.export_eval_cases(cases, out_path)
    return FileResponse(str(out_path), filename="eval_dataset.json", media_type="application/json")


@app.get("/api/download/rubric")
async def download_rubric():
    """Download the judge rubric as JSON."""
    cases: list[EvalCase] = _pipeline_state["eval_cases"]
    if not cases:
        return JSONResponse({"error": "No eval cases generated yet"}, status_code=404)

    out_path = Path(settings.evalforge_output_dir) / "judge_rubric.json"
    json_exporter.export_judge_rubric(cases, out_path)
    return FileResponse(str(out_path), filename="judge_rubric.json", media_type="application/json")


# ── Background pipeline ───────────────────────────────────────────────────────


def _log(msg: str) -> None:
    logger.info(msg)
    _pipeline_state["log"].append(msg)


async def _run_pipeline_bg(trace_limit: int, project_name: str | None) -> None:
    """Run the full pipeline in the background."""
    try:
        # Step 1
        _log(f"Fetching up to {trace_limit} traces from Phoenix...")
        fetcher = PhoenixFetcher()
        traces = await fetcher.fetch_traces(limit=trace_limit, project_name=project_name)
        _pipeline_state["traces"] = traces
        failures = [t for t in traces if t.is_failure]
        _log(f"Fetched {len(traces)} traces. Found {len(failures)} failures.")

        if not failures:
            _pipeline_state["status"] = "complete"
            _log("No failures found — your agent is doing great!")
            return

        # Step 2
        _log("Clustering failures by semantic similarity...")
        clusterer = FailureClusterer()
        clusters = await clusterer.cluster(failures)
        _pipeline_state["clusters"] = clusters
        for c in clusters:
            _log(f"  Cluster '{c.label}': {c.size} traces, {c.failure_rate:.0%} failure rate")

        # Step 3
        _log("Generating eval cases with Gemini...")
        generator = EvalGenerator()
        eval_cases = await generator.generate(clusters)
        _pipeline_state["eval_cases"] = eval_cases
        _log(f"Generated {len(eval_cases)} eval cases.")

        _pipeline_state["status"] = "complete"
        _log("Pipeline complete! Download your eval dataset below.")

    except Exception as exc:
        logger.exception("Pipeline failed")
        _pipeline_state["status"] = "error"
        _pipeline_state["error"] = str(exc)
        _log(f"Error: {exc}")
