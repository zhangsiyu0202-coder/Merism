"""Celery tasks for codebook governance pipeline steps."""

from __future__ import annotations

from asgiref.sync import async_to_sync
from celery import shared_task


@shared_task(name="merism.codebook.tasks.run_codebook_governance")
def run_codebook_governance_task(study_id: str, session_id: str) -> dict:
    """Run the full codebook governance pipeline for a session."""
    from merism.codebook.pipeline import run_codebook_governance

    return async_to_sync(run_codebook_governance)(study_id, session_id)
