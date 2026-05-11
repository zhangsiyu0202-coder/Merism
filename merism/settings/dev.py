"""Local development settings for Merism.

Reads ``.env`` via ``python-dotenv`` so devs can override any base setting
without editing code.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()  # noqa: T201 — intentional side effect at import time

from merism.settings.base import *  # noqa: F401, F403, E402

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# Default to the docker-compose postgres (port 5542 to avoid clash with any
# parallel Postgres on 5432). Override via POSTGRES_PORT env var.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "merism"),
        "USER": os.environ.get("POSTGRES_USER", "merism"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "merism"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5542"),
    }
}

# Loosen CORS for the Vite dev server on :5173. Still credentials-aware so
# the session cookie flows. Production uses the tight list in base.py.
CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Enable CSRF trust for the Vite origin so /accounts/login/ accepts POSTs
# forwarded through the Vite proxy or made cross-origin.
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
