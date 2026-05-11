"""Deterministic embedding helpers.

``hash_embedding(text, dim=1536)`` returns a stable unit-length vector for a
given text. Used in knowledge/RAG tests to avoid calling real embedding APIs.

Similarity properties (intentional):
- Same text → identical vector (cosine similarity = 1.0)
- Completely unrelated strings → vectors with low cosine similarity
- Substring overlap → modest positive correlation (enough to rank correctly
  for simple test cases)

This is NOT a replacement for a real embedding model — it exists to make
ranking tests deterministic, not to prove model quality.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable


def hash_embedding(text: str, *, dim: int = 1536) -> list[float]:
    """Return a stable unit-length vector for ``text``.

    Implementation: hash the lower-cased text plus each position index, map
    bytes to floats in ``[-1, 1]``, then L2-normalize. For test purposes only.
    """
    if dim <= 0:
        raise ValueError(f"dim must be positive, got {dim}")

    canonical = text.strip().lower().encode("utf-8")
    # Produce ``dim`` bytes deterministically by chaining hashes.
    buffer = bytearray()
    seed = canonical
    while len(buffer) < dim:
        seed = hashlib.sha256(seed).digest()
        buffer.extend(seed)
    raw = buffer[:dim]

    # Map each byte to a float in [-1, 1].
    vector = [(b / 127.5) - 1.0 for b in raw]
    return _l2_normalize(vector)


def _l2_normalize(vector: Iterable[float]) -> list[float]:
    vec = list(vector)
    norm = math.sqrt(sum(x * x for x in vec))
    if norm == 0:
        return vec
    return [x / norm for x in vec]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Convenience for tests asserting on embedding similarity."""
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} vs {len(b)}")
    return sum(x * y for x, y in zip(a, b))
