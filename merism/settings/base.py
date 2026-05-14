"""Base Django settings for Merism.

Environment-specific variants (dev/test/prod) import from here and override
the few fields that differ per environment.
"""

from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Core ───────────────────────────────────────────────────
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-merism-dev-only")
DEBUG = os.environ.get("DEBUG", "0") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Installed apps ─────────────────────────────────────────
INSTALLED_APPS = [
    # django-unfold replaces the stock admin UI — must come *before*
    # django.contrib.admin (ADR 0001).
    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",

    # daphne must come BEFORE django.contrib.staticfiles so its
    # runserver command takes precedence in dev.
    "daphne",
    "channels",

    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",

    # third-party — auth (ADR 0001)
    "allauth",
    "allauth.account",
    "allauth.socialaccount",

    # third-party — API
    "rest_framework",
    "drf_spectacular",
    "corsheaders",

    # third-party — ops
    "anymail",

    # observability — Prometheus /metrics endpoint.
    # Needs matching middleware entries (PrometheusBeforeMiddleware must be
    # first, PrometheusAfterMiddleware must be last).
    "django_prometheus",

    # merism
    "merism.apps.MerismConfig",
]

SITE_ID = 1

MIDDLEWARE = [
    # Prometheus metrics — must wrap the whole stack: Before first, After last.
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Merism security headers (CSP + Permissions-Policy) — slots in right
    # after Django's SecurityMiddleware so the two cooperate cleanly.
    "merism.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # allauth adds a middleware for account stack handling.
    "allauth.account.middleware.AccountMiddleware",
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

# CORS defaults — tighten in prod.
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# ── Auth (django-allauth — ADR 0001) ───────────────────────
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# ── Unfold admin skin (ADR 0001) ───────────────────────────
UNFOLD = {
    "SITE_TITLE": "Merism 管理后台",
    "SITE_HEADER": "Merism 管理后台",
    "SITE_URL": "/",
    "DASHBOARD_CALLBACK": "merism.admin.dashboard_callback",
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,
    "COLORS": {
        "primary": {
            # Match merism-accent from the frontend design system.
            "500": "84 104 255",
            "600": "64 82 229",
            "700": "49 66 194",
        },
    },
}

ROOT_URLCONF = "merism.urls"
WSGI_APPLICATION = "merism.wsgi.application"
ASGI_APPLICATION = "merism.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "merism" / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ── i18n / tz ──────────────────────────────────────────────
LANGUAGE_CODE = "zh-hans"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ── Static & media ─────────────────────────────────────────
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── DRF ────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 50,
    # Global rate limits (per-IP for anon, per-user for authenticated).
    # Individual views can declare throttle_scope for finer-grained limits
    # (e.g. interview_turn / ask_stream / auth).
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        # Baseline per-IP / per-user caps. Aggressive enough to stop
        # credential-stuffing and scraping, loose enough that a fast
        # researcher doesn't trip them.
        "anon": "60/minute",
        "user": "1000/hour",
        # Scoped rates — set ``throttle_scope = "<scope>"`` on a view to
        # apply one of these instead of the per-user default.
        "interview_turn": "120/minute",  # participant → moderator text turns
        "ask_stream": "30/minute",        # Ask Merism SSE LLM calls
        "auth": "10/minute",              # login / signup / password reset
        "recruitment_dispatch": "100/hour",  # outbound IM/email broadcast
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Merism API",
    "DESCRIPTION": "AI-moderated qualitative research platform.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Two serializer fields pull from the same ``Study.InterviewMode`` choices
    # ("interview_mode" on Study + future use on Participation). Give them a
    # single canonical component name instead of rejection-prefixing.
    "ENUM_NAME_OVERRIDES": {
        "InterviewModeEnum": "merism.models.study.Study.InterviewMode.choices",
        "StudyStatusEnum": "merism.models.study.Study.Status.choices",
    },
}

# ── Redis / cache / channels ───────────────────────────────
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
    },
}

# Channels: Redis-backed channel layer so multi-worker deployments can
# broadcast messages across voice consumer instances. In tests, settings/test.py
# swaps this to the in-memory layer.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [os.environ.get("CHANNELS_REDIS_URL", "redis://localhost:6379/3")],
            "capacity": 1500,
            "expiry": 20,  # seconds; audio frames must not outlive this
        },
    },
}

# ── Celery ─────────────────────────────────────────────────
CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE


CELERY_BEAT_SCHEDULE = {
    "abandon-stuck-sessions": {
        "task": "merism.conductor.tasks.abandon_stuck_sessions",
        "schedule": 600.0,
    },
    "dispatch-pending-broadcasts": {
        "task": "merism.recruitment.tasks.dispatch_pending_broadcasts",
        "schedule": 60.0,
    },
}

# ── LLM / AI stack ─────────────────────────────────────────
MERISM_LLM_API_KEY = os.environ.get("MERISM_LLM_API_KEY", "")
MERISM_LLM_BASE_URL = os.environ.get("MERISM_LLM_BASE_URL", "https://api.deepseek.com")
MERISM_LLM_MODEL = os.environ.get("MERISM_LLM_MODEL", "deepseek-chat")
MERISM_LLM_REASONER_MODEL = os.environ.get("MERISM_LLM_REASONER_MODEL", "deepseek-reasoner")

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
# Separate ASR and TTS keys — DashScope charges them as distinct model
# families, so teams may scope credentials by function. Both fall back to
# the shared ``DASHSCOPE_API_KEY`` if the per-function var is unset.
DASHSCOPE_ASR_API_KEY = os.environ.get("DASHSCOPE_ASR_API_KEY", DASHSCOPE_API_KEY)
DASHSCOPE_TTS_API_KEY = os.environ.get("DASHSCOPE_TTS_API_KEY", DASHSCOPE_API_KEY)
DASHSCOPE_REALTIME_URL = os.environ.get(
    "DASHSCOPE_REALTIME_URL",
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
)
DASHSCOPE_TTS_MODEL = os.environ.get("DASHSCOPE_TTS_MODEL", "qwen3-tts-instruct-flash-realtime")
DASHSCOPE_STT_MODEL = os.environ.get("DASHSCOPE_STT_MODEL", "qwen3-asr-flash-realtime")
DASHSCOPE_VISION_MODEL = os.environ.get("DASHSCOPE_VISION_MODEL", "qwen-vl-max")

# ── Channel credential encryption (Fernet) ─────────────────
MERISM_CHANNEL_ENCRYPTION_KEY = os.environ.get("MERISM_CHANNEL_ENCRYPTION_KEY", "")

# ── Feature flags ──────────────────────────────────────────
MERISM_KNOWLEDGE_VECTOR_SEARCH = os.environ.get("MERISM_KNOWLEDGE_VECTOR_SEARCH", "1") == "1"
MERISM_IM_RECRUITMENT = os.environ.get("MERISM_IM_RECRUITMENT", "1") == "1"

# ── Object storage ─────────────────────────────────────────
OBJECT_STORAGE_ENDPOINT = os.environ.get("OBJECT_STORAGE_ENDPOINT", "")
OBJECT_STORAGE_ACCESS_KEY = os.environ.get("OBJECT_STORAGE_ACCESS_KEY", "")
OBJECT_STORAGE_SECRET_KEY = os.environ.get("OBJECT_STORAGE_SECRET_KEY", "")
OBJECT_STORAGE_BUCKET = os.environ.get("OBJECT_STORAGE_BUCKET", "merism-dev")
OBJECT_STORAGE_REGION = os.environ.get("OBJECT_STORAGE_REGION", "us-east-1")

# ── Email (django-anymail — ADR 0001) ──────────────────────
# Flip ANYMAIL_PROVIDER to switch provider without code changes.
# Supported: "ses" | "resend" | "mailgun" | "postmark" | "console" (dev default).
ANYMAIL_PROVIDER = os.environ.get("ANYMAIL_PROVIDER", "console")

ANYMAIL: dict[str, str] = {}
if ANYMAIL_PROVIDER == "resend":
    EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
    ANYMAIL = {"RESEND_API_KEY": os.environ.get("RESEND_API_KEY", "")}
elif ANYMAIL_PROVIDER == "ses":
    EMAIL_BACKEND = "anymail.backends.amazon_ses.EmailBackend"
elif ANYMAIL_PROVIDER == "mailgun":
    EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
    ANYMAIL = {"MAILGUN_API_KEY": os.environ.get("MAILGUN_API_KEY", "")}
elif ANYMAIL_PROVIDER == "postmark":
    EMAIL_BACKEND = "anymail.backends.postmark.EmailBackend"
    ANYMAIL = {"POSTMARK_SERVER_TOKEN": os.environ.get("POSTMARK_SERVER_TOKEN", "")}
else:
    # Dev default — emails print to stdout. Tests use locmem via settings/test.py.
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "merism-dev@merism.test")

# ── LLM observability (Langfuse — ADR 0001) ────────────────
# Optional. When unset, Langfuse is a no-op import.
LANGFUSE_PUBLIC_KEY = os.environ.get("LANGFUSE_PUBLIC_KEY", "")
LANGFUSE_SECRET_KEY = os.environ.get("LANGFUSE_SECRET_KEY", "")
LANGFUSE_HOST = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

# ── Sentry (application-level error tracking) ──────────────
# Opt-in via SENTRY_DSN env var. See merism/sentry.py for details.
# Initialised here at settings-import time so worker / ASGI / WSGI /
# management commands all pick it up.
from merism.sentry import init_sentry  # noqa: E402

init_sentry()

# ── Logging (django-structlog — JSON in prod, plain in dev) ──
import structlog  # noqa: E402

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "merism": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "django_structlog": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
