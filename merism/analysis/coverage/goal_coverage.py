"""Per-goal coverage computation."""

from __future__ import annotations

import logging
from uuid import UUID, uuid4

from asgiref.sync import sync_to_async

from merism.analysis.themes.clusterer import cosine_similarity
from merism.models import CoverageSnapshot, Study, StudyGoal

logger = logging.getLogger(__name__)

GOAL_MATCH_THRESHOLD = 0.55
PRIORITY_WEIGHTS = {"P0": 3, "P1": 2, "P2": 1}


async def compute_coverage_snapshot(study: Study) -> CoverageSnapshot | None:
    """Compute coverage of all goals for a study and persist a snapshot."""
    goals = await _goals_for_study(study.id)
    if not goals:
        return None

    goal_embeddings = await _embed_goals(study, goals)

    from merism.analysis.themes.embedder import fetch_study_quote_embeddings

    quote_samples = await fetch_study_quote_embeddings(study.id)

    session_ids_by_goal: dict[str, set[str]] = {str(g.id): set() for g in goals}
    for sample in quote_samples:
        for goal in goals:
            goal_emb = goal_embeddings.get(str(goal.id))
            if goal_emb is None:
                continue
            if cosine_similarity(sample["embedding"], goal_emb) >= GOAL_MATCH_THRESHOLD:
                session_ids_by_goal[str(goal.id)].add(sample["session_id"])

    total_sessions = len({s["session_id"] for s in quote_samples}) or 1

    goal_coverage: dict[str, float] = {}
    gaps: list[dict] = []
    for g in goals:
        gid = str(g.id)
        matched = len(session_ids_by_goal[gid])
        ratio = round(min(1.0, matched / total_sessions), 3)
        goal_coverage[gid] = ratio
        if ratio < 0.3:
            gaps.append({
                "goal_id": gid,
                "goal_text": g.text,
                "priority": g.priority,
                "coverage": ratio,
                "sessions_matched": matched,
                "sessions_total": total_sessions,
            })

    overall = _weighted_overall(goals, goal_coverage)
    await _update_goal_coverages(goals, goal_coverage)
    recommendations = _build_recommendations(gaps, total_sessions)

    snapshot = await _create_snapshot(
        study=study, goal_coverage=goal_coverage, overall_coverage=overall,
        gaps=gaps, recommendations=recommendations, session_count=total_sessions,
    )
    logger.info(
        "coverage.snapshot_created: study=%s overall=%.2f gaps=%d",
        str(study.id), overall, len(gaps),
    )
    return snapshot


@sync_to_async
def _goals_for_study(study_id: str | UUID) -> list[StudyGoal]:
    return list(StudyGoal.objects.filter(study_id=study_id).order_by("display_order"))


async def _embed_goals(study: Study, goals: list[StudyGoal]) -> dict[str, list[float]]:
    texts = [g.text for g in goals]
    ids = [str(g.id) for g in goals]
    embeddings: list[list[float] | None] = []
    try:
        from merism.llm_gateway.client import get_client
        client = await get_client("embedding", team=study.team, trace_id=uuid4())
        resp = await client.embed(texts)
        embeddings = [list(item["embedding"]) for item in resp.data]
    except Exception:
        from merism.knowledge.embeddings import embed_batch
        embeddings = await sync_to_async(embed_batch)(texts, team=study.team)
    result: dict[str, list[float]] = {}
    for gid, emb in zip(ids, embeddings, strict=False):
        if emb is not None:
            result[gid] = emb
    return result


def _weighted_overall(goals: list[StudyGoal], coverage_by_id: dict[str, float]) -> float:
    total_w = 0
    weighted = 0.0
    for g in goals:
        w = PRIORITY_WEIGHTS.get(g.priority, 1)
        total_w += w
        weighted += w * coverage_by_id.get(str(g.id), 0.0)
    return round(weighted / total_w, 3) if total_w else 0.0


@sync_to_async
def _update_goal_coverages(goals: list[StudyGoal], coverage_by_id: dict[str, float]) -> None:
    for g in goals:
        new_cov = coverage_by_id.get(str(g.id), 0.0)
        if g.coverage != new_cov:
            g.coverage = new_cov
            g.is_answered = new_cov >= 0.7
            g.save(update_fields=["coverage", "is_answered", "updated_at"])


def _build_recommendations(gaps: list[dict], session_count: int) -> list[str]:
    recs: list[str] = []
    p0 = [g for g in gaps if g["priority"] == "P0"]
    if p0:
        texts = ", ".join(f'"{g["goal_text"][:50]}"' for g in p0[:3])
        recs.append(f"{len(p0)} P0 goal(s) under-covered: {texts}.")
    if session_count < 5:
        recs.append(f"Only {session_count} session(s) analyzed — coverage becomes reliable at 5+.")
    return recs


@sync_to_async
def _create_snapshot(**kwargs) -> CoverageSnapshot:
    study = kwargs.pop("study")
    return CoverageSnapshot.objects.create(team=study.team, study=study, **kwargs)
