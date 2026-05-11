"""Production settings for Merism.

Imports the base and flips every dev-unsafe toggle. **All** secrets come from
environment variables — importing this module with any of them missing raises
``ImproperlyConfigured`` so bad deploys fail fast.
"""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

from merism.settings.base import *  # noqa: F401, F403


def _require_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ImproperlyConfigured(f"{name} must be set in production")
    return value


SECRET_KEY = _require_env("SECRET_KEY")
DEBUG = False
ALLOWED_HOSTS = [h for h in os.environ.get("ALLOWED_HOSTS", "").split(",") if h]
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be a comma-separated list")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _require_env("POSTGRES_DB"),
        "USER": _require_env("POSTGRES_USER"),
        "PASSWORD": _require_env("POSTGRES_PASSWORD"),
        "HOST": _require_env("POSTGRES_HOST"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# ── Security ───────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
# Balanced referrer exposure: full URL on same-origin, origin-only on
# cross-origin HTTPS, nothing when downgrading to HTTP.
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ── Required runtime secrets ───────────────────────────────
_require_env("MERISM_CHANNEL_ENCRYPTION_KEY")
_require_env("MERISM_LLM_API_KEY")
