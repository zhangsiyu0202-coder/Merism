"""Session outline resolution for v3 interview entrypoints.

The session row stores a frozen ``guide_snapshot`` captured at session
start so the interview can keep using the same outline even if the live
guide changes later. Callers fall back to ``session.guide.sections`` for
older rows that predate the snapshot field.
"""

from __future__ import annotations

from typing import Any

from merism.conductor.schema import Outline


def get_session_outline(session: Any) -> Outline:
    """Return the v3 outline that should drive this session.

    Preference order:
    1. ``session.guide_snapshot`` when present
    2. ``session.guide.sections`` as a compatibility fallback
    """
    snapshot = getattr(session, "guide_snapshot", None)
    if snapshot:
        return Outline.model_validate(snapshot)

    guide = getattr(session, "guide", None)
    if guide is None:
        raise RuntimeError("session is missing guide")

    return Outline.model_validate(guide.sections)


__all__ = ["get_session_outline"]
