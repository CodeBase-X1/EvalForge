"""
Step 1 — Trace Fetcher

Pulls production traces from Arize Phoenix via the Phoenix MCP / REST API,
extracts the fields we care about, and filters for failures.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from evalforge.config import settings
from evalforge.models import Trace

logger = logging.getLogger(__name__)


class PhoenixFetcher:
    """
    Fetches traces from a running Phoenix instance.

    Phoenix exposes a GraphQL API at /v1/graphql and a REST API at /v1/spans.
    We use the REST spans endpoint because it's simpler and doesn't require
    a full GraphQL client.
    """

    def __init__(
        self,
        endpoint: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self.endpoint = (endpoint or settings.phoenix_endpoint).rstrip("/")
        self.api_key = api_key or settings.phoenix_api_key
        self._headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            self._headers["Authorization"] = f"Bearer {self.api_key}"

    # ── Public API ────────────────────────────────────────────────────────────

    async def fetch_traces(
        self,
        limit: int | None = None,
        project_name: str | None = None,
        min_score: float | None = None,
        max_score: float | None = None,
    ) -> list[Trace]:
        """
        Fetch up to `limit` traces from Phoenix.

        Args:
            limit: Maximum number of traces to return.
            project_name: Filter to a specific Phoenix project.
            min_score: Only return traces with score >= this value.
            max_score: Only return traces with score <= this value.

        Returns:
            List of Trace objects, newest first.
        """
        limit = limit or settings.evalforge_trace_limit
        logger.info(f"Fetching up to {limit} traces from {self.endpoint}")

        raw_spans = await self._fetch_spans(limit=limit, project_name=project_name)
        traces = [self._span_to_trace(s) for s in raw_spans]

        # Apply score filters
        if min_score is not None:
            traces = [t for t in traces if t.score is not None and t.score >= min_score]
        if max_score is not None:
            traces = [t for t in traces if t.score is not None and t.score <= max_score]

        logger.info(f"Fetched {len(traces)} traces")
        return traces

    async def fetch_failures(self, limit: int | None = None) -> list[Trace]:
        """
        Convenience method — fetch only traces that are considered failures
        (score below the configured failure threshold).
        """
        limit = limit or settings.evalforge_trace_limit
        all_traces = await self.fetch_traces(limit=limit)
        failures = [t for t in all_traces if t.is_failure]
        logger.info(
            f"Found {len(failures)} failures out of {len(all_traces)} traces "
            f"(threshold={settings.evalforge_failure_threshold})"
        )
        return failures

    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _fetch_spans(
        self,
        limit: int,
        project_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Call the Phoenix /v1/spans REST endpoint."""
        params: dict[str, Any] = {"limit": limit, "sort": "startTime desc"}
        if project_name:
            params["project_name"] = project_name

        async with httpx.AsyncClient(headers=self._headers, timeout=30.0) as client:
            try:
                response = await client.get(
                    f"{self.endpoint}/v1/spans",
                    params=params,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
            except httpx.HTTPStatusError as exc:
                logger.error(f"Phoenix API error: {exc.response.status_code} — {exc.response.text}")
                raise
            except httpx.ConnectError:
                logger.error(
                    f"Cannot connect to Phoenix at {self.endpoint}. "
                    "Is Phoenix running? Try: python -m phoenix.server.main serve"
                )
                raise

    def _span_to_trace(self, span: dict[str, Any]) -> Trace:
        """Convert a raw Phoenix span dict into a Trace model."""
        attrs = span.get("attributes", {})

        # Phoenix stores LLM input/output in standard OpenTelemetry attributes
        input_text = (
            attrs.get("input.value")
            or attrs.get("llm.input_messages", [{}])[0].get("message.content", "")
            or ""
        )
        output_text = (
            attrs.get("output.value")
            or attrs.get("llm.output_messages", [{}])[0].get("message.content", "")
            or ""
        )

        # Score can come from annotations or attributes
        score: float | None = None
        annotations = span.get("spanAnnotations", [])
        if annotations:
            # Use the first numeric annotation score
            for ann in annotations:
                if ann.get("score") is not None:
                    score = float(ann["score"])
                    break

        # Parse timestamp
        timestamp: datetime | None = None
        ts_str = span.get("startTime")
        if ts_str:
            try:
                timestamp = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                timestamp = datetime.now(tz=timezone.utc)

        return Trace(
            trace_id=span.get("traceId", span.get("id", "")),
            span_id=span.get("id"),
            input=str(input_text),
            output=str(output_text),
            latency_ms=span.get("latencyMs"),
            score=score,
            metadata={
                "project": span.get("project", {}).get("name"),
                "span_kind": attrs.get("openinference.span.kind"),
                "status": span.get("statusCode"),
            },
            timestamp=timestamp,
        )
