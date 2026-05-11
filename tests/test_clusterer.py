"""Tests for the failure clusterer."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import numpy as np
import pytest

from evalforge.core.clusterer import FailureClusterer
from evalforge.models import Cluster, Trace


def make_traces(n: int, score: float = 0.2) -> list[Trace]:
    return [
        Trace(trace_id=f"t{i}", input=f"question number {i}", output=f"answer {i}", score=score)
        for i in range(n)
    ]


class TestFailureClusterer:
    def test_init_default(self):
        c = FailureClusterer()
        assert c.num_clusters == 0  # auto-detect

    def test_init_explicit_k(self):
        c = FailureClusterer(num_clusters=4)
        assert c.num_clusters == 4

    @pytest.mark.asyncio
    async def test_cluster_too_few_traces(self):
        clusterer = FailureClusterer(num_clusters=2)
        result = await clusterer.cluster([make_traces(1)[0]])
        assert result == []

    def test_embed_with_tfidf(self):
        clusterer = FailureClusterer()
        texts = [f"this is sentence number {i} about billing" for i in range(10)]
        embeddings = clusterer._embed_with_tfidf(texts)
        assert embeddings.shape[0] == 10
        assert embeddings.dtype == np.float32

    def test_tfidf_min_components(self):
        """With very few texts, n_components is capped to len(texts)-1."""
        clusterer = FailureClusterer()
        texts = ["hello world", "foo bar", "baz qux"]
        embeddings = clusterer._embed_with_tfidf(texts)
        assert embeddings.shape[0] == 3

    def test_run_clustering_returns_labels(self):
        clusterer = FailureClusterer(num_clusters=2)
        rng = np.random.default_rng(42)
        embeddings = rng.random((20, 8)).astype(np.float32)
        labels = clusterer._run_clustering(embeddings, n_traces=20)
        assert len(labels) == 20
        assert set(labels) == {0, 1}

    def test_find_best_k_returns_valid_k(self):
        clusterer = FailureClusterer(num_clusters=0)
        rng = np.random.default_rng(42)
        x_norm = rng.random((30, 8)).astype(np.float32)
        k = clusterer._find_best_k(x_norm, n_traces=30)
        assert 2 <= k <= 10

    def test_build_clusters_groups_correctly(self):
        clusterer = FailureClusterer(num_clusters=2)
        traces = make_traces(6, score=0.2)  # all failures
        labels = np.array([0, 0, 0, 1, 1, 1])
        rng = np.random.default_rng(0)
        embeddings = rng.random((6, 4)).astype(np.float32)

        clusters = clusterer._build_clusters(traces, labels, embeddings)
        assert len(clusters) == 2
        assert clusters[0].size == 3
        assert clusters[1].size == 3
        assert clusters[0].failure_rate == pytest.approx(1.0)

    def test_build_clusters_failure_rate_mixed(self):
        clusterer = FailureClusterer()
        traces = [
            Trace(trace_id="t0", input="q0", output="a0", score=0.1),  # fail
            Trace(trace_id="t1", input="q1", output="a1", score=0.9),  # pass
            Trace(trace_id="t2", input="q2", output="a2", score=0.2),  # fail
            Trace(trace_id="t3", input="q3", output="a3", score=0.8),  # pass
        ]
        labels = np.array([0, 0, 0, 0])
        rng = np.random.default_rng(0)
        embeddings = rng.random((4, 4)).astype(np.float32)

        clusters = clusterer._build_clusters(traces, labels, embeddings)
        assert clusters[0].failure_rate == pytest.approx(0.5)

    def test_build_clusters_no_scores(self):
        """Traces with no score should result in 0.0 failure rate."""
        clusterer = FailureClusterer()
        traces = [
            Trace(trace_id="t0", input="q0", output="a0"),
            Trace(trace_id="t1", input="q1", output="a1"),
        ]
        labels = np.array([0, 0])
        rng = np.random.default_rng(0)
        embeddings = rng.random((2, 4)).astype(np.float32)

        clusters = clusterer._build_clusters(traces, labels, embeddings)
        assert clusters[0].failure_rate == 0.0

    @pytest.mark.asyncio
    async def test_label_clusters_no_api_key(self):
        """Without a Gemini key, labels stay as cluster_N placeholders."""
        clusterer = FailureClusterer()
        clusters = [
            Cluster(
                cluster_id=0,
                label="cluster_0",
                traces=make_traces(3),
                failure_rate=1.0,
            )
        ]
        # No API key set — should return unchanged
        result = await clusterer._label_clusters(clusters)
        assert result[0].label == "cluster_0"

    @pytest.mark.asyncio
    async def test_full_cluster_pipeline_tfidf(self):
        """End-to-end cluster() using TF-IDF (no API key needed)."""
        clusterer = FailureClusterer(num_clusters=2)
        traces = make_traces(20, score=0.2)

        with patch.object(clusterer, "_label_clusters", new=AsyncMock(side_effect=lambda c: c)):
            clusters = await clusterer.cluster(traces)

        assert len(clusters) == 2
        total = sum(c.size for c in clusters)
        assert total == 20
        # Sorted worst-first (all 100% here, so order doesn't matter but list is non-empty)
        assert all(c.failure_rate == pytest.approx(1.0) for c in clusters)
