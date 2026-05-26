#!/usr/bin/env bash
# Merism dev environment one-shot reset.
#
# Returns the local stack to a known-good state in three modes:
#
#   bin/reset.sh                # soft reset (default) — clear queues, kill
#                               # stale processes, re-seed dev data, leave DB
#   bin/reset.sh --queues       # only clear Celery / Redis queues
#   bin/reset.sh --processes    # only kill stale runserver / vite processes
#   bin/reset.sh --containers   # only remove stale + recreate compose containers
#   bin/reset.sh --hard         # everything above + drop & re-create the DB
#                               # (DESTRUCTIVE — flushes every model row)
#
# After running, ``bin/doctor.sh`` should pass all checks.
#
# Safe to re-run.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

GREEN=$'\033[32m'
RED=$'\033[31m'
YELLOW=$'\033[33m'
DIM=$'\033[2m'
RESET=$'\033[0m'

step() { printf "${YELLOW}━━ %s${RESET}\n" "$*"; }
ok()   { printf "  ${GREEN}✓${RESET} %s\n" "$*"; }
warn() { printf "  ${RED}!${RESET} %s\n" "$*"; }

# ── parse mode ────────────────────────────────────────────────
MODE="soft"
for arg in "$@"; do
    case "$arg" in
        --queues)     MODE="queues" ;;
        --processes)  MODE="processes" ;;
        --containers) MODE="containers" ;;
        --hard)       MODE="hard" ;;
        --help|-h)
            sed -n '2,18p' "$0"
            exit 0
            ;;
        *)
            echo "unknown arg: $arg" >&2
            exit 1
            ;;
    esac
done

# ── confirmation for hard mode ────────────────────────────────
if [[ "$MODE" == "hard" ]]; then
    printf "${RED}WARNING${RESET}: --hard will drop and recreate the merism database.\n"
    printf "All study / session / participant data will be lost.\n"
    read -rp "Type 'yes' to continue: " confirm
    if [[ "$confirm" != "yes" ]]; then
        echo "aborted."
        exit 1
    fi
fi

# ── helpers ───────────────────────────────────────────────────

reset_processes() {
    step "kill stale dev processes"
    if [[ -x "$SCRIPT_DIR/clear-dev-ports.sh" ]]; then
        "$SCRIPT_DIR/clear-dev-ports.sh" 8000 5173 || true
    fi
    # Also kill any spare runserver children that lingered after their
    # parent died (the `for i in pid` reaper).
    pgrep -f "manage.py runserver" | while read -r pid; do
        kill -TERM "$pid" 2>/dev/null || true
    done
    sleep 1
    pgrep -f "manage.py runserver" | while read -r pid; do
        kill -KILL "$pid" 2>/dev/null || true
    done
    ok "ports 8000/5173 clear; runserver processes killed"
}

reset_queues() {
    step "flush Redis queues"
    if docker ps --format '{{.Names}}' | grep -qx merism-app-redis-1; then
        # db 0 = celery broker, db 1 = result backend, db 2 = app cache,
        # db 3 = channels redis. flushdb each — they're all dev-only.
        for db in 0 1 2 3; do
            docker exec merism-app-redis-1 redis-cli -n "$db" flushdb >/dev/null
        done
        ok "redis dbs 0..3 flushed (broker, results, cache, channels)"
    else
        warn "redis container not running — skipping flush"
    fi
}

reset_containers() {
    step "remove stale containers + recreate compose set"
    # Stale = present on the docker daemon but NOT in current docker-compose.yml.
    # We list services from the current compose, then any merism-app-* container
    # that doesn't match gets removed.
    local current_services
    current_services=$(docker compose config --services 2>/dev/null | sort)
    docker ps -a --format '{{.Names}}' | grep '^merism-app-' | while read -r name; do
        local svc=${name#merism-app-}
        svc=${svc%-*}  # strip trailing -<index>
        if ! echo "$current_services" | grep -qx "$svc"; then
            docker rm -f "$name" >/dev/null 2>&1 && \
                ok "removed stale $name"
        fi
    done
    docker compose up -d --wait postgres redis minio celery-worker celery-beat
    ok "compose set up + healthy"
}

reset_hard_db() {
    step "drop + recreate merism database"
    docker exec merism-app-postgres-1 \
        psql -U merism -d postgres -c "DROP DATABASE IF EXISTS merism;" >/dev/null
    docker exec merism-app-postgres-1 \
        psql -U merism -d postgres -c "CREATE DATABASE merism OWNER merism;" >/dev/null
    ok "database dropped and recreated"
}

reset_django() {
    step "django migrations + seed_dev"
    if [[ ! -d .venv ]]; then
        warn ".venv missing — run 'uv sync --extra dev' first"
        return 1
    fi
    .venv/bin/python manage.py migrate --no-input
    .venv/bin/python manage.py seed_dev
    ok "migrations + seed complete"
}

# ── dispatch ──────────────────────────────────────────────────

case "$MODE" in
    queues)
        reset_queues
        ;;
    processes)
        reset_processes
        ;;
    containers)
        reset_containers
        ;;
    soft)
        reset_processes
        reset_queues
        reset_containers
        reset_django
        ;;
    hard)
        reset_processes
        reset_queues
        reset_containers
        reset_hard_db
        reset_django
        ;;
esac

echo ""
echo "${GREEN}━━━ reset complete ━━━${RESET}"
echo ""
echo "Next: ${YELLOW}bin/doctor.sh${RESET} to verify, then ${YELLOW}bin/dev.sh${RESET} to start."
