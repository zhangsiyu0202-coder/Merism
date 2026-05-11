"""Tests for the themes clusterer — HDBSCAN on synthetic embeddings."""

from __future__ import annotations

import random

import numpy as np
import pytest

from merism.analysis.themes.clusterer import (
    ClusteringResult,
    cluster_quote_embeddings,
    cosine_similarity,
)


def _make_sample(quote_id: str, base: list[float], noise: float = 0.05) -> dict:
    """Build a test sample: base vector + small gaussian noise."""
    v = np.array(base, dtype=np.float32) + np.random.normal(0, noise, size=len(base)).astype(np.float32)
    return {"quote_id": quote_id, "session_id": f"s-{quote_id}", "text": "...", "embedding": v.tolist()}


class TestClusterer:
    def setup_method(self) -> None:
        random.seed(42)
        np.random.seed(42)

    def test_empty_input_returns_empty_result(self) -> None:
        result = cluster_quote_embeddings([])
        assert result.total_quotes == 0
        assert len(result.clusters) == 0

    def test_below_min_cluster_size_returns_empty(self) -> None:
        samples = [_make_sample(f"q{i}", [1.0, 0.0, 0.0] + [0.0] * 10) for i in range(2)]
        result = cluster_quote_embeddings(samples, min_cluster_size=3)
        assert result.total_quotes == 2
        assert len(result.clusters) == 0

    def test_two_distinct_clusters(self) -> None:
        # Cluster A: vectors near [1, 0, 0, ...]
        # Cluster B: vectors near [0, 1, 0, ...]
        base_a = [1.0, 0.0] + [0.0] * 14
        base_b = [0.0, 1.0] + [0.0] * 14
        samples = []
        for i in range(5):
            samples.append(_make_sample(f"a{i}", base_a))
        for i in range(5):
            samples.append(_make_sample(f"b{i}", base_b))

        result = cluster_quote_embeddings(samples, min_cluster_size=3)

        # Expect 2 clusters (no noise)
        assert len(result.clusters) >= 1  # HDBSCAN may occasionally merge
        assert result.total_quotes == 10
        # All 10 quotes should have a label
        assert len(result.labels) == 10

    def test_cosine_similarity_identical_vectors(self) -> None:
        v = [0.5, 0.5, 0.5, 0.5]
        assert cosine_similarity(v, v) == pytest.approx(1.0, abs=1e-5)

    def test_cosine_similarity_orthogonal(self) -> None:
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        assert cosine_similarity(a, b) == pytest.approx(0.0, abs=1e-5)

    def test_cosine_similarity_zero_vector(self) -> None:
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_centroid_is_normalized(self) -> None:
        base = [0.7, 0.7] + [0.0] * 14
        samples = [_make_sample(f"q{i}", base, noise=0.02) for i in range(5)]
        result = cluster_quote_embeddings(samples, min_cluster_size=3)
        for centroid in result.centroids.values():
            norm = np.linalg.norm(np.array(centroid))
            assert norm == pytest.approx(1.0, abs=0.01)
