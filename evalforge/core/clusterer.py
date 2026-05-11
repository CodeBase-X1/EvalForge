"""
Step 2 — Failure Clusterer

Embeds each failing trace and groups them into semantically similar clusters.
Each cluster gets a human-readable label via Gemini.
"""

from __future__ import annotations

import logging
import math
from typing import Any

import numpy as np

from evalforge.config import settings
from evalforge.models import Cluster, Trace

logger = logging.getLogger(__name__)


class FailureClusterer:
    """
    Clusters failing traces by semantic similarity.

    Pipeline:
        1. Embed each trace input using Gemini embeddings
        2. Run KMeans (or DBSCAN for auto-k) to find clusters
        3. Ask Gemini to label each cluster with a short topic name
        4. Compute failure rate per cluster
    """

    def __init__(self, num_clusters: int = 0) -> None:
        """
        Args:
            num_clusters: Number of clusters. 0 = auto-detect using silhouette score.
        """
        self.num_clusters = num_clusters or settings.evalforge_num_clusters
        self._embedder: Any = None  # lazy-loaded

    # ── Public API ────────────────────────────────────────────────────────────

    async def cluster(self, traces: list[Trace]) -> list[Cluster]:
        """
        Cluster a list of traces.

        Returns clusters sorted by failure_rate descending (worst first).
        """
        if len(traces) < 2:
            logger.warning("Not enough traces to cluster (need at least 2)")
            return []

        logger.info(f"Embedding {len(traces)} traces...")
        embeddings = await self._embed_traces(traces)

        logger.info("Clustering embeddings...")
        labels = self._run_clustering(embeddings, n_traces=len(traces))

        logger.info("Building cluster objects...")
        clusters = self._build_clusters(traces, labels, embeddings)

        logger.info("Labeling clusters with Gemini...")
        clusters = await self._label_clusters(clusters)

        # Sort worst-first
        clusters.sort(key=lambda c: c.failure_rate, reverse=True)

        for c in clusters:
            logger.info(
                f"  Cluster '{c.label}': {c.size} traces, "
                f"{c.failure_rate:.0%} failure rate"
            )

        return clusters

    # ── Embedding ─────────────────────────────────────────────────────────────

    async def _embed_traces(self, traces: list[Trace]) -> np.ndarray:
        """
        Embed trace inputs.

        Priority:
          1. Gemini text-embedding-004 (best quality, requires API key)
          2. sentence-transformers all-MiniLM-L6-v2 (good quality, local)
          3. scikit-learn TF-IDF (always available, no extra deps)
        """
        texts = [t.input for t in traces]

        if settings.gemini_api_key:
            return await self._embed_with_gemini(texts)

        # Try sentence-transformers; fall back to TF-IDF if unavailable
        try:
            return self._embed_with_sentence_transformers(texts)
        except Exception as exc:
            logger.warning(
                f"sentence-transformers unavailable ({exc}). "
                "Falling back to TF-IDF embeddings. "
                "Set GEMINI_API_KEY for better clustering quality."
            )
            return self._embed_with_tfidf(texts)

    async def _embed_with_gemini(self, texts: list[str]) -> np.ndarray:
        """Use Gemini text-embedding-004 to embed texts in batches."""
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.gemini_api_key)

        batch_size = 100  # Gemini embedding API limit
        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            result = client.models.embed_content(
                model=settings.gemini_embedding_model,
                contents=batch,
                config=types.EmbedContentConfig(task_type="CLUSTERING"),
            )
            all_embeddings.extend([e.values for e in result.embeddings])

        return np.array(all_embeddings, dtype=np.float32)

    def _embed_with_sentence_transformers(self, texts: list[str]) -> np.ndarray:
        """Use sentence-transformers (runs locally, no API key needed)."""
        from sentence_transformers import SentenceTransformer

        logger.info("Using sentence-transformers for embeddings (no Gemini key set)")
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)

    def _embed_with_tfidf(self, texts: list[str]) -> np.ndarray:
        """
        Fallback: TF-IDF sparse → dense via SVD (no GPU, no downloads).

        Lower quality than neural embeddings but always works.
        """
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline

        logger.info("Using TF-IDF + SVD embeddings (scikit-learn fallback)")
        n_components = min(64, len(texts) - 1)
        pipe = Pipeline([
            ("tfidf", TfidfVectorizer(ngram_range=(1, 2), max_features=10_000)),
            ("svd", TruncatedSVD(n_components=n_components, random_state=42)),
        ])
        return pipe.fit_transform(texts).astype(np.float32)

    # ── Clustering ────────────────────────────────────────────────────────────

    def _run_clustering(self, embeddings: np.ndarray, n_traces: int) -> np.ndarray:
        """
        Run KMeans clustering. If num_clusters == 0, auto-detect k using
        the silhouette score over a range of k values.
        """
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score
        from sklearn.preprocessing import normalize

        # L2-normalize embeddings for cosine-like distance
        X = normalize(embeddings)

        k = self.num_clusters
        if k == 0:
            k = self._find_best_k(X, n_traces)

        logger.info(f"Running KMeans with k={k}")
        kmeans = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = kmeans.fit_predict(X)

        if len(set(labels)) > 1:
            score = silhouette_score(X, labels)
            logger.info(f"Silhouette score: {score:.3f}")

        return labels

    def _find_best_k(self, X: np.ndarray, n_traces: int) -> int:
        """
        Try k from 2 to sqrt(n) and pick the k with the best silhouette score.
        """
        from sklearn.cluster import KMeans
        from sklearn.metrics import silhouette_score

        max_k = min(10, max(2, int(math.sqrt(n_traces))))
        best_k, best_score = 2, -1.0

        for k in range(2, max_k + 1):
            km = KMeans(n_clusters=k, random_state=42, n_init="auto")
            labels = km.fit_predict(X)
            if len(set(labels)) < 2:
                continue
            s = silhouette_score(X, labels)
            logger.debug(f"  k={k} → silhouette={s:.3f}")
            if s > best_score:
                best_score = s
                best_k = k

        logger.info(f"Auto-selected k={best_k} (silhouette={best_score:.3f})")
        return best_k

    # ── Build cluster objects ─────────────────────────────────────────────────

    def _build_clusters(
        self,
        traces: list[Trace],
        labels: np.ndarray,
        embeddings: np.ndarray,
    ) -> list[Cluster]:
        """Group traces by cluster label and compute failure rates."""
        from sklearn.preprocessing import normalize

        X = normalize(embeddings)
        clusters: list[Cluster] = []

        for cluster_id in sorted(set(labels)):
            mask = labels == cluster_id
            cluster_traces = [t for t, m in zip(traces, mask) if m]
            cluster_embeddings = X[mask]

            # Centroid = mean of normalized embeddings
            centroid = cluster_embeddings.mean(axis=0).tolist()

            # Failure rate = fraction of traces with score below threshold
            scored = [t for t in cluster_traces if t.score is not None]
            if scored:
                failure_rate = sum(1 for t in scored if t.is_failure) / len(scored)
            else:
                failure_rate = 0.0

            clusters.append(
                Cluster(
                    cluster_id=int(cluster_id),
                    label=f"cluster_{cluster_id}",  # placeholder, replaced by Gemini
                    traces=cluster_traces,
                    failure_rate=failure_rate,
                    centroid=centroid,
                )
            )

        return clusters

    # ── Labeling ──────────────────────────────────────────────────────────────

    async def _label_clusters(self, clusters: list[Cluster]) -> list[Cluster]:
        """Ask Gemini to give each cluster a short, descriptive topic label."""
        from google import genai

        if not settings.gemini_api_key:
            logger.warning("No Gemini API key — skipping cluster labeling")
            return clusters

        client = genai.Client(api_key=settings.gemini_api_key)

        labeled: list[Cluster] = []
        for cluster in clusters:
            examples = "\n".join(
                f"- {inp}" for inp in cluster.representative_inputs
            )
            prompt = (
                "You are analyzing a cluster of user questions to an AI assistant.\n\n"
                f"Here are {min(5, cluster.size)} representative questions from this cluster:\n"
                f"{examples}\n\n"
                "Give this cluster a short, descriptive topic label (2-4 words, lowercase, "
                "use underscores for spaces). Examples: billing_questions, cancellation_flow, "
                "feature_requests, pricing_info.\n\n"
                "Respond with ONLY the label, nothing else."
            )

            try:
                response = client.models.generate_content(
                    model=settings.gemini_model,
                    contents=prompt,
                )
                raw_label = response.text.strip().lower().replace(" ", "_")
                # Sanitize: keep only alphanumeric and underscores
                label = "".join(c for c in raw_label if c.isalnum() or c == "_")
                cluster.label = label or f"cluster_{cluster.cluster_id}"
            except Exception as exc:
                logger.warning(f"Failed to label cluster {cluster.cluster_id}: {exc}")

            labeled.append(cluster)

        return labeled
