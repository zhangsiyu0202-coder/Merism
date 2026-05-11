# syntax=docker/dockerfile:1.7
# ─────────────────────────────────────────────────────────────────────────
# Merism app image — single image, multi-process (Django ASGI + Celery).
#
# Build:
#   docker build -t merism-app:local .
#
# Run Django ASGI (daphne):
#   docker run --rm -p 8000:8000 --env-file .env merism-app:local
#
# Run a Celery worker against the same image:
#   docker run --rm --env-file .env merism-app:local \
#     celery -A merism worker -l info --concurrency=2
#
# Run Celery beat:
#   docker run --rm --env-file .env merism-app:local \
#     celery -A merism beat -l info --scheduler redbeat.RedBeatScheduler
#
# Stages:
#   1. builder   — installs uv, resolves + builds all wheels into .venv
#   2. runtime   — slim image with .venv copied in, non-root user, tini as PID 1
# ─────────────────────────────────────────────────────────────────────────

ARG PYTHON_VERSION=3.12.12

# ╔═══════════════════════════════════════════════════════════════════════╗
# ║ Stage 1 — builder                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════╝
FROM python:${PYTHON_VERSION}-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON=/usr/local/bin/python

# Build toolchain needed for native wheels (psycopg, cryptography, numpy,
# onnxruntime transitive deps). Kept out of the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        git \
        libpq-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Pinned uv for reproducibility. Bump deliberately.
COPY --from=ghcr.io/astral-sh/uv:0.5.14 /uv /uvx /usr/local/bin/

WORKDIR /app

# Dep resolution layer — only invalidated when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

# Now copy source and install the project itself into .venv.
COPY merism ./merism
COPY manage.py ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# Collect static files at build time so the runtime image is read-only.
# SECRET_KEY is required by Django even for collectstatic; a throwaway one is fine.
ENV DJANGO_SETTINGS_MODULE=merism.settings.prod \
    SECRET_KEY=build-time-placeholder-not-used-at-runtime \
    ALLOWED_HOSTS=localhost \
    POSTGRES_DB=placeholder POSTGRES_USER=placeholder POSTGRES_PASSWORD=placeholder POSTGRES_HOST=placeholder \
    MERISM_CHANNEL_ENCRYPTION_KEY=build-placeholder-rotate-in-runtime \
    MERISM_LLM_API_KEY=build-placeholder
RUN .venv/bin/python manage.py collectstatic --noinput --clear

# ╔═══════════════════════════════════════════════════════════════════════╗
# ║ Stage 2 — runtime                                                      ║
# ╚═══════════════════════════════════════════════════════════════════════╝
FROM python:${PYTHON_VERSION}-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:${PATH}" \
    DJANGO_SETTINGS_MODULE=merism.settings.prod

# Runtime-only dependencies: libpq for psycopg, tini for signal handling,
# curl for container healthchecks, ca-certificates for outbound TLS.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        libpq5 \
        tini \
    && rm -rf /var/lib/apt/lists/*

# Non-root user — never run the app as root.
RUN groupadd --gid 1000 merism \
    && useradd --uid 1000 --gid merism --home /app --shell /usr/sbin/nologin merism

WORKDIR /app

# Copy the resolved venv + source + collected static files from the builder.
COPY --from=builder --chown=merism:merism /app/.venv /app/.venv
COPY --from=builder --chown=merism:merism /app/merism /app/merism
COPY --from=builder --chown=merism:merism /app/manage.py /app/manage.py
COPY --from=builder --chown=merism:merism /app/staticfiles /app/staticfiles

USER merism

EXPOSE 8000

# tini as PID 1 so SIGTERM propagates to Daphne / Celery cleanly
# (prevents zombie children and 30s shutdown stalls).
ENTRYPOINT ["/usr/bin/tini", "--"]

# Default command runs the Django ASGI server. Override at runtime for
# Celery worker / beat by passing `celery -A merism worker ...`.
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "merism.asgi:application"]

# Container-level liveness probe. Assumes /healthz is wired up (see C1/C2).
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail --silent http://127.0.0.1:8000/healthz || exit 1
