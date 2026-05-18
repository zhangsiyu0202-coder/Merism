"""Celery tasks for knowledge indexing."""

from __future__ import annotations

import logging

from asgiref.sync import async_to_sync
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=30)
def index_transcript_task(self, session_id: str) -> None:
    """Index a session's transcript into the knowledge base."""
    from merism.knowledge.transcript_indexer import index_session_transcript
    from merism.models import InterviewSession

    try:
        session = InterviewSession.objects.select_related("team", "study").get(id=session_id)
    except InterviewSession.DoesNotExist:
        logger.warning("index_transcript_task: session not found", extra={"session_id": session_id})
        return

    count = async_to_sync(index_session_transcript)(session)
    logger.info("index_transcript_task.done", extra={"session_id": session_id, "chunks": count})
