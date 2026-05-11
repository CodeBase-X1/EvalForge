"""Shared data models used across the EvalForge pipeline."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# ── Raw trace from Phoenix ────────────────────────────────────────────────────


class Trace(BaseModel):
    """A single production trace fetched from Phoenix."""

    trace_id: str
    span_id: str | None = None
    input: str
    output: str
    latency_ms: float | None = None
    score: float | None = None  # 0.0 (bad) → 1.0 (good)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | None = None

    @property
    def is_failure(self) -> bool:
        """True when the trace has a score below the failure threshold."""
        if self.score is None:
            return False
        from evalforge.config import settings

        return self.score < settings.evalforge_failure_threshold


# ── Cluster ───────────────────────────────────────────────────────────────────


class Cluster(BaseModel):
    """A group of similar failing traces."""

    cluster_id: int
    label: str  # e.g. "billing", "cancellation"
    traces: list[Trace]
    failure_rate: float  # 0.0 → 1.0
    centroid: list[float] | None = None  # embedding centroid

    @property
    def size(self) -> int:
        return len(self.traces)

    @property
    def representative_inputs(self) -> list[str]:
        """Return up to 5 representative inputs from this cluster."""
        return [t.input for t in self.traces[:5]]


# ── Eval case ─────────────────────────────────────────────────────────────────


class ScoringCriteria(BaseModel):
    """A single criterion in a rubric."""

    criterion: str  # e.g. "Must mention specific days"
    weight: float = 1.0  # relative importance


class EvalCase(BaseModel):
    """One row in the eval dataset."""

    case_id: str
    cluster_label: str
    input: str  # test question
    expected_output: str  # ideal answer
    rubric: list[ScoringCriteria]
    judge_prompt: str  # ready-to-use LLM-as-judge prompt
    source_trace_ids: list[str] = Field(default_factory=list)


# ── Eval result ───────────────────────────────────────────────────────────────


class ScoreLevel(str, Enum):
    PASS = "pass"
    PARTIAL = "partial"
    FAIL = "fail"


class EvalResult(BaseModel):
    """Result of running one eval case against the agent."""

    case_id: str
    input: str
    expected_output: str
    actual_output: str
    score: float  # 0.0 → 10.0
    level: ScoreLevel
    judge_reasoning: str
    cluster_label: str


# ── Pipeline report ───────────────────────────────────────────────────────────


class ClusterSummary(BaseModel):
    label: str
    size: int
    failure_rate: float
    cases_generated: int
    pass_rate: float | None = None  # filled in after eval run


class PipelineReport(BaseModel):
    """Top-level report produced at the end of a full EvalForge run."""

    run_id: str
    timestamp: datetime
    traces_analyzed: int
    clusters_found: int
    eval_cases_generated: int
    overall_pass_rate: float | None = None
    cluster_summaries: list[ClusterSummary]
    output_dir: str
