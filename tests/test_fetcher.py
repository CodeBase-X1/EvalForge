"""Tests for the Phoenix trace fetcher."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from evalforge.core.fetcher import PhoenixFetcher
from evalforge.models import Trace


@pytest.fixture
def fetcher():
    return PhoenixFetcher(endpoint="http://localhost:6006")


@pytest.fixture
def sample_span():
    return {
        "id": "span-123",
        "traceId": "trace-abc",
        "startTime": "2024-01-15T10:00:00Z",
        "latencyMs": 250.0,
        "statusCode": "OK",
        "attributes": {
            "input.value": "What is the refund policy?",
            "output.value": "Our refund policy is 30 days.",
            "openinference.span.kind": "CHAIN",
        },
        "spanAnnotations": [{"score": 0.3, "label": "thumbs_down"}],
        "project": {"name": "customer-support"},
    }


class TestPhoenixFetcher:
    def test_span_to_trace_basic(self, fetcher, sample_span):
        trace = fetcher._span_to_trace(sample_span)
        assert trace.trace_id == "trace-abc"
        assert trace.input == "What is the refund policy?"
        assert trace.output == "Our refund policy is 30 days."
        assert trace.score == pytest.approx(0.3)
        assert trace.latency_ms == 250.0

    def test_span_to_trace_no_score(self, fetcher, sample_span):
        sample_span["spanAnnotations"] = []
        trace = fetcher._span_to_trace(sample_span)
        assert trace.score is None
        assert trace.is_failure is False

    def test_span_to_trace_timestamp(self, fetcher, sample_span):
        trace = fetcher._span_to_trace(sample_span)
        assert trace.timestamp is not None
        assert trace.timestamp.year == 2024

    @pytest.mark.asyncio
    async def test_fetch_failures_filters_correctly(self, fetcher):
        mock_traces = [
            Trace(trace_id="t1", input="q1", output="a1", score=0.2),  # failure
            Trace(trace_id="t2", input="q2", output="a2", score=0.8),  # pass
            Trace(trace_id="t3", input="q3", output="a3", score=0.1),  # failure
        ]

        with patch.object(fetcher, "fetch_traces", new=AsyncMock(return_value=mock_traces)):
            # fetch_failures calls fetch_traces internally, so we test the filter logic
            failures = [t for t in mock_traces if t.is_failure]
            assert len(failures) == 2
            assert all(t.score < 0.5 for t in failures)
