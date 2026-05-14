"""RetaggingJob — re-tags quotes affected by codebook changes."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

if TYPE_CHECKING:
    from merism.models import Study

from merism.codebook.models import CodeChange, CodeMapping

logger = logging.getLogger(__name__)


async def retag_affected_quotes(study: Study, change: CodeChange) -> int:
    """Find quotes with old code_ids and re-tag them. Returns count retagged."""
    mappings = await _get_mappings(change)
    if not mappings:
        return 0

    old_code_ids = [m.old_code_id for m in mappings]
    affected = await _find_affected_quotes(study, old_code_ids)
    if not affected:
        return 0

    # Clear deductive tags so QuoteTagger will re-process them
    await _clear_deductive_tags(affected)

    # Re-tag with updated codebook
    from merism.memai.agents.quote_tagger import tag_quotes_for_session

    await tag_quotes_for_session(affected, study)

    logger.info(
        "codebook.retagging.done",
        extra={"study_id": str(study.id), "retagged": len(affected)},
    )
    return len(affected)


@sync_to_async
def _get_mappings(change: CodeChange) -> list[CodeMapping]:
    return list(CodeMapping.objects.filter(change=change))


@sync_to_async
def _find_affected_quotes(study: Study, old_code_ids: list[str]) -> list:
    from merism.models import SessionQuote

    # Find quotes where any deductive match uses an old code_id
    all_quotes = SessionQuote.objects.filter(study=study)
    affected = []
    for q in all_quotes:
        deductive = (q.tags or {}).get("deductive", [])
        if any(d.get("code_id") in old_code_ids for d in deductive):
            affected.append(q)
    return affected


@sync_to_async
def _clear_deductive_tags(quotes: list) -> None:
    for q in quotes:
        if isinstance(q.tags, dict):
            q.tags.pop("deductive", None)
            q.save(update_fields=["tags", "updated_at"])
