"""Concept rotation strategies.

Each strategy takes the block's ordered concept list + a session seed
and returns a list of concept ids in presentation order. Pure
functions — no Django imports — so they're fast to test.
"""

from __future__ import annotations

import random
from typing import Sequence


def order_fixed(concept_ids: Sequence[str], _session_seed: str) -> list[str]:
    """Always A → B → C."""
    return list(concept_ids)


def order_random(concept_ids: Sequence[str], session_seed: str) -> list[str]:
    """Fisher-Yates shuffle seeded by the session id so the order is
    reproducible (useful for debugging / session replay)."""
    rng = random.Random(session_seed)
    ids = list(concept_ids)
    rng.shuffle(ids)
    return ids


def order_latin_square(concept_ids: Sequence[str], session_seed: str) -> list[str]:
    """Cyclic shift by a seed-derived offset. Over a large N of
    participants this gives every concept roughly equal representation
    in every position. Not a full Latin Square but a cheap approximation
    — a real LS needs coordination across sessions (DB row) which we
    defer to v2.
    """
    if not concept_ids:
        return []
    offset = int.from_bytes(session_seed.encode()[:4].ljust(4, b"\x00"), "big")
    offset %= len(concept_ids)
    ids = list(concept_ids)
    return ids[offset:] + ids[:offset]


STRATEGIES = {
    "fixed": order_fixed,
    "random_per_session": order_random,
    "latin_square": order_latin_square,
}


def compute_order(rotation: str, concept_ids: Sequence[str], session_seed: str) -> list[str]:
    fn = STRATEGIES.get(rotation, order_random)
    return fn(concept_ids, session_seed)
