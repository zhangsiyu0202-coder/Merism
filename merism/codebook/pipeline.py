"""Codebook governance pipeline — orchestrates the post-session codebook steps.

Called after quote tagging completes. Runs:
  1. InductiveCodeSuggester (batch, session-level)
  2. CodebookReviewer (study-level, proposes changes)
  3. VersionManager.apply (auto-approve or queue for researcher)
  4. RetaggingJob (affected quotes only)
  5. ThemeSynthesizer trigger (conditional)
"""

from __future__ import annotations

import logging
from uuid import UUID

from asgiref.sync import sync_to_async

from merism.codebook.models import CodeChange
from merism.codebook.retagging import retag_affected_quotes
from merism.codebook.saturation import is_codebook_saturated
from merism.codebook.version_manager import apply_proposal, create_initial_version, get_latest_version

logger = logging.getLogger(__name__)


async def run_codebook_governance(study_id: str | UUID, session_id: str | UUID) -> dict:
    """Full codebook governance pipeline. Returns counters."""
    counters = {"suggestions": 0, "proposals": 0, "applied": 0, "retagged": 0, "theme_triggered": False}

    study, session = await _load(study_id, session_id)
    if study is None or session is None:
        return counters

    # Ensure at least version 1 exists
    current_version = await get_latest_version(study)
    if current_version is None:
        current_version = await create_initial_version(study)

    # ── 1. Inductive code suggestion ──
    from merism.memai.agents.inductive_code_suggester import suggest_codes

    quotes = await _get_session_quotes(session)
    suggestions = await suggest_codes(quotes, study)
    counters["suggestions"] = len(suggestions)

    # ── 2. Codebook review ──
    from merism.memai.agents.codebook_reviewer import review_codebook

    proposals = await review_codebook(study, suggestions)
    counters["proposals"] = len(proposals)

    # ── 3. Apply proposals (auto-approve for now) ──
    for proposal in proposals:
        change = await _create_change(study, current_version, proposal, session)
        new_version = await apply_proposal(study, change)
        current_version = new_version
        counters["applied"] += 1

        # ── 4. Retag affected quotes ──
        retagged = await retag_affected_quotes(study, change)
        counters["retagged"] += retagged

    # ── 5. Theme synthesizer trigger ──
    saturated = await is_codebook_saturated(study)
    target_reached = study.is_target_reached
    if saturated or target_reached:
        counters["theme_triggered"] = True
        logger.info(
            "codebook.pipeline.theme_trigger",
            extra={"study_id": str(study.id), "saturated": saturated, "target_reached": target_reached},
        )

    return counters


@sync_to_async
def _load(study_id, session_id):
    from merism.models import InterviewSession, Study

    try:
        study = Study.objects.select_related("team").get(id=study_id)
        session = InterviewSession.objects.get(id=session_id)
        return study, session
    except (Study.DoesNotExist, InterviewSession.DoesNotExist):
        return None, None


@sync_to_async
def _get_session_quotes(session):
    from merism.models import SessionQuote

    return list(SessionQuote.objects.filter(session=session))


@sync_to_async
def _create_change(study, current_version, proposal: dict, session) -> CodeChange:
    return CodeChange.objects.create(
        team=study.team,
        study=study,
        from_version=current_version,
        change_type=proposal["change_type"],
        payload=proposal["payload"],
        rationale=proposal.get("rationale", ""),
        status=CodeChange.Status.APPROVED,
        session=session,
    )
