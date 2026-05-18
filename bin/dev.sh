#!/usr/bin/env bash
# Merism daily dev launcher.
#
# Starts all services in the correct order with health gates:
#   1. Kill stale listeners on :8000 / :5173
#   2. docker compose up --wait (postgres + redis + minio healthy)
#   3. Django runserver (waits until /api/ responds)
#   4. Vite dev server
#
# Usage:
#   bin/dev.sh          # start everything
#   bin/dev.sh --skip-docker  # skip docker (already running)
#
# Ctrl-C stops all child processes cleanly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

SKIP_DOCKER=false
for arg in "$@"; do
    case "$arg" in
        --skip-docker) SKIP_DOCKER=true ;;
    esac
done

green()  { printf "\033[32m✓\033[0m %s\n" "$*"; }
yellow() { printf "\033[33m⏳\033[0m %s\n" "$*"; }
red()    { printf "\033[31m✗\033[0m %s\n" "$*" >&2; }

# ── Cleanup on exit ─────────────────────────────────────────
PIDS=()
cleanup() {
    echo ""
    yellow "Shutting down..."
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    green "All processes stopped."
}
trap cleanup EXIT INT TERM

# ── 1. Clear stale ports ────────────────────────────────────
yellow "Clearing stale listeners on :8000 / :5173..."
"$SCRIPT_DIR/clear-dev-ports.sh" 8000 5173
green "Ports clear"

# ── 2. Docker services ──────────────────────────────────────
if [[ "$SKIP_DOCKER" == false ]]; then
    yellow "Starting docker services (postgres, redis, minio)..."
    docker compose up -d --wait
    green "Docker services healthy"
else
    yellow "Skipping docker (--skip-docker)"
fi

# ── 3. Django backend ───────────────────────────────────────
yellow "Starting Django on :8000..."
source .venv/bin/activate
export DJANGO_SETTINGS_MODULE="merism.settings.dev"
python manage.py runserver 0.0.0.0:8000 2>&1 | sed 's/^/[django] /' &
PIDS+=($!)

# Wait for Django to be ready
for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/api/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if curl -sf http://localhost:8000/api/ > /dev/null 2>&1; then
    green "Django ready on :8000"
else
    red "Django failed to start within 30s — check logs above"
    exit 1
fi

# ── 4. Vite frontend ───────────────────────────────────────
yellow "Starting Vite on :5173..."
cd frontend
pnpm dev 2>&1 | sed 's/^/[vite]   /' &
PIDS+=($!)
cd "$REPO_ROOT"

# Wait for Vite
for i in $(seq 1 15); do
    if curl -sf http://localhost:5173/ > /dev/null 2>&1; then
        break
    fi
    sleep 1
done

if curl -sf http://localhost:5173/ > /dev/null 2>&1; then
    green "Vite ready on :5173"
else
    red "Vite failed to start within 15s — check logs above"
    exit 1
fi

# ── Ready ───────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
green "Merism dev ready → http://localhost:5173"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Keep running until Ctrl-C
wait
