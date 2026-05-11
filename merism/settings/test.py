"""Pytest settings for Merism.

- sqlite ``:memory:`` database (fast, no external deps)
- local-memory cache (no Redis required)
- dummy Celery (``task_always_eager``) so task invocations run inline
- zero external service calls
"""

from __future__ import annotations

from merism.settings.base import *  # noqa: F401, F403

DEBUG = False
TEST = True
SECRET_KEY = "merism-pytest-not-for-production"  # noqa: S105

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "merism-test",
    }
}

# In-memory Channels backend — no Redis required for tests.
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"},
}

# Run Celery tasks synchronously in tests.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Email goes to in-memory backend so password-reset tests don't touch SMTP.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Storage test double — swap with moto/minio in integration tests.
OBJECT_STORAGE_ENDPOINT = ""
OBJECT_STORAGE_ACCESS_KEY = ""
OBJECT_STORAGE_SECRET_KEY = ""

# No live LLM calls during tests unless MERISM_LLM_API_KEY is explicitly set.
# The test harness's @pytest.mark.merism_llm_live marker handles auto-skip.

# Disable DRF throttle during tests — LocMemCache keeps state across the
# whole pytest session and a handful of fast API tests can easily exhaust
# the anon/user baselines, producing flaky 429s that don't reflect real
# behaviour. Scope-specific throttle coverage lives in test_throttle.py.
REST_FRAMEWORK = {  # noqa: F405 — intentionally overriding base
    **REST_FRAMEWORK,  # type: ignore[name-defined]  # noqa: F405
    "DEFAULT_THROTTLE_CLASSES": [],
    "DEFAULT_THROTTLE_RATES": {},
}
