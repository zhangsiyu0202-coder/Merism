"""Merism — AI-moderated qualitative research platform."""

from __future__ import annotations

# Import the Celery app so it's loaded whenever Django starts.
# ``celery -A merism`` finds the app instance via this re-export.
from merism.celery import app as celery_app

__version__ = "0.1.0"

__all__ = ["celery_app"]

default_app_config = "merism.apps.MerismConfig"
