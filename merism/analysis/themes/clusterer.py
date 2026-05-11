"""HDBSCAN clustering for quote embeddings.

Why HDBSCAN over k-means:
- No need to pre-specify k (number of themes)
- Handles noise (quotes that don't belong to any theme → label=-1)
- Variable cluster sizes (some themes are niche, others dominant)

Input: list of (quote_id, embedding) pairs
Output: ClusteringResult with labels + centroids

Tuning:
- ``min_cluster_size`` = smallest theme we want to surface. Default 3
  (need at least 3 quotes across sessions to call it a pattern).
- ``min_samples`` = how conservative to be about noise. Lower = more
  clusters, looser. Higher = fewer clusters, tighter.
- ``metric`` = cosine for semantic similarity (embeddings aren't
  euclidean-normalized).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class ClusterAssignment:
    quote_id: str
    cluster_id: int  # -1 = noise
    distance_to_centroid: float  # 0.0 if noise


@dataclass
class ClusteringResult:
    """Output of HDBSCAN clustering."""

    # quote_id → cluster_id (-1 = noise / unclustered)
    labels: dict[str, int] = field(default_factory=dict)
    # cluster_id → list of quote_ids in that cluster, ordered by distance
    # to centroid (closest first). Noise (-1) excluded.
    clusters: dict[int, list[str]] = field(default_factory=dict)
    # cluster_id → centroid vector (mean of member embeddings, L2-normalized)
    centroids: dict[int, list[float]] = field(default_factory=dict)
    # Total quotes processed
    total_quotes: int = 0
    # Quotes assigned to noise
    noise_count: int = 0


def cluster_quote_embeddings(
    samples: list[dict],
    *,
    min_cluster_size: int = 3,
    min_samples: int | None = None,
    metric: str = "cosine",
) -> ClusteringResult:
    """Run HDBSCAN on the quote samples. ``samples`` is the output of
    :func:`merism.analysis.themes.embedder.fetch_study_quote_embeddings`.

    Returns a :class:`ClusteringResult` mapping each quote to a cluster
    id (-1 = noise) plus cluster centroids for downstream matching.

    If ``len(samples) < min_cluster_size``, returns an empty result —
    we can't form even one theme yet.
    """
    if len(samples) < min_cluster_size:
        return ClusteringResult(total_quotes=len(samples))

    # Lazy import so test collection works without hdbscan installed
    try:
        import hdbscan
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("hdbscan not installed — `uv add hdbscan`") from exc

    quote_ids = [s["quote_id"] for s in samples]
    X = np.array([s["embedding"] for s in samples], dtype=np.float32)

    # Normalize to unit length for cosine distance
    norms = np.linalg.norm(X, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    X_normalized = X / norms

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",  # on L2-normalized vectors, euclidean ≈ 2(1-cosine)
        cluster_selection_method="eom",  # excess of mass — more balanced clusters
    )
    labels = clusterer.fit_predict(X_normalized)

    result = ClusteringResult(total_quotes=len(samples))
    result.labels = dict(zip(quote_ids, labels.tolist()))
    result.noise_count = int((labels == -1).sum())

    # Build per-cluster member lists + centroids
    unique_ids = sorted(set(int(x) for x in labels) - {-1})
    for cid in unique_ids:
        mask = labels == cid
        cluster_samples = [(quote_ids[i], X_normalized[i]) for i, m in enumerate(mask) if m]
        # Centroid = mean of member vectors (already unit-length)
        centroid = np.mean([v for _, v in cluster_samples], axis=0)
        # Re-normalize the centroid itself (mean of unit vectors isn't unit)
        c_norm = np.linalg.norm(centroid)
        if c_norm > 0:
            centroid = centroid / c_norm

        # Sort member quotes by distance to centroid (closest first)
        distances = [(qid, float(1.0 - np.dot(v, centroid))) for qid, v in cluster_samples]
        distances.sort(key=lambda t: t[1])

        result.clusters[cid] = [qid for qid, _ in distances]
        result.centroids[cid] = centroid.tolist()

    logger.info(
        "themes.clusterer.done",
        extra={
            "total": result.total_quotes,
            "clusters": len(result.clusters),
            "noise": result.noise_count,
        },
    )
    return result


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two vectors. Range [-1, 1]."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(va, vb) / (na * nb))
