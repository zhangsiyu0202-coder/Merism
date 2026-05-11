#!/usr/bin/env bash
# Merism dev environment bootstrap.
#
# Idempotent: safe to rerun. Each step checks whether work is needed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

green()  { printf "\033[32m[OK]\033[0m %s\n" "$*"; }
yellow() { printf "\033[33m[--]\033[0m %s\n" "$*"; }
red()    { printf "\033[31m[!!]\033[0m %s\n" "$*" >&2; }

# ── 1. Check system prerequisites ──────────────────────────

require() {
    if ! command -v "$1" >/dev/null 2>&1; then
        red "Missing required tool: $1"
        red "Install hint: $2"
        exit 1
    fi
}

yellow "Checking prerequisites..."
require python3.12 "Install Python 3.12 (exact minor via pyenv or system pkg)"
require uv         "curl -LsSf https://astral.sh/uv/install.sh | sh"
require docker     "Install Docker Desktop or Docker Engine"

PYVER="$(python3.12 --version | awk '{print $2}')"
if [[ "$PYVER" != "3.12."* ]]; then
    red "Need Python 3.12.x, got $PYVER"
    exit 1
fi
green "Python $PYVER, uv, docker all present"

# ── 2. Start local services ─────────────────────────────────

yellow "Starting postgres + redis + minio (docker compose)..."
docker compose up -d --wait
green "Services healthy"

# ── 3. Python venv via uv ───────────────────────────────────

if [[ ! -d .venv ]]; then
    yellow "Creating .venv/ via uv sync..."
    uv sync --extra dev
    green ".venv/ created"
else
    yellow "Refreshing .venv/ via uv sync..."
    uv sync --extra dev
    green ".venv/ refreshed"
fi

# ── 4. Django migrations ────────────────────────────────────

yellow "Running migrations..."
export DJANGO_SETTINGS_MODULE="merism.settings.dev"
.venv/bin/python manage.py migrate --no-input
green "Migrations applied"

# ── 5. Ensure demo superuser + seed data ────────────────────

yellow "Ensuring dev superuser + demo data..."
.venv/bin/python manage.py ensure_superuser
.venv/bin/python manage.py seed_demo
green "Superuser + demo data ready"

# ── 6. Smoke test ───────────────────────────────────────────

yellow "Running smoke tests..."
.venv/bin/pytest merism/tests --no-header -q
green "Smoke tests pass"

# ── 7. Next steps ───────────────────────────────────────────

cat <<EOF

────────────────────────────────────────────────────────────────────
  Setup complete. Two-terminal workflow:

    # Terminal 1 — Django (ASGI via daphne for WebSocket support)
    source .venv/bin/activate
    python manage.py runserver             # plain Django on :8000

    # Terminal 2 — Vite frontend
    cd frontend && pnpm dev                # Vite dev server on :5173

  Then open http://localhost:5173 and log in as:
      admin@merism.test  /  merism-dev

  Useful commands:
    make test           # backend pytest + frontend vitest
    make lint           # ruff + oxlint + tsc
    docker compose down # stop postgres / redis / minio
────────────────────────────────────────────────────────────────────
EOF
