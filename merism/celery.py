"""Celery app instance — the ``-A merism`` entry point.

Reads broker / result backend / timezone from Django settings (prefix
``CELERY_``). Auto-discovers tasks under ``merism.*``.

Usage::

    celery -A merism worker -l info
    celery -A merism beat -l info --scheduler redbeat.RedBeatScheduler
"""

from __future__ import annotations

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "merism.settings.dev")

app = Celery("merism")

# All ``CELERY_*`` settings in Django config flow in.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Pull tasks from every Django app's ``tasks.py``.
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self) -> None:  # pragma: no cover
    """Tiny sanity task — ``debug_task.delay()`` should print request info."""
    print(f"Request: {self.request!r}")
