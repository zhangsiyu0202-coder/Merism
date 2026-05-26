#!/usr/bin/env bash
# Merism dev environment self-check.
#
# Runs a battery of health checks against the local dev stack and prints
# ✓ / ✗ for each. When something fails it prints a one-line fix hint.
#
# Usage:
#   bin/doctor.sh                # run all checks
#   bin/doctor.sh --quick        # skip slow LLM/embedding checks
#
# Exit code: 0 = all green, 1 = at least one ✗.
#
# Add new checks at the bottom — each is a single function so they can
# be re-ordered or disabled per category.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

QUICK=false
for arg in "$@"; do
    case "$arg" in
        --quick) QUICK=true ;;
    esac
done

# ── output helpers ────────────────────────────────────────────
GREEN=$'\033[32m'
RED=$'\033[31m'
YELLOW=$'\033[33m'
DIM=$'\033[2m'
RESET=$'\033[0m'

FAIL_COUNT=0

section() {
    echo ""
    echo "${DIM}── $1 ──${RESET}"
}

check() {
    # check "Description" "fix-hint" command...
    local desc="$1" hint="$2"
    shift 2
    local out
    if out=$("$@" 2>&1); then
        printf "  ${GREEN}✓${RESET} %s\n" "$desc"
    else
        printf "  ${RED}✗${RESET} %s\n" "$desc"
        if [[ -n "$out" ]]; then
            printf "    ${DIM}%s${RESET}\n" "$(printf "%s" "$out" | head -1)"
        fi
        printf "    ${YELLOW}fix:${RESET} %s\n" "$hint"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

check_count() {
    # Like check, but command's stdout is a count and we compare to a max.
    local desc="$1" hint="$2" max="$3"
    shift 3
    local n
    n=$("$@" 2>/dev/null || echo "?")
    if [[ "$n" =~ ^[0-9]+$ ]] && [[ "$n" -le "$max" ]]; then
        printf "  ${GREEN}✓${RESET} %s ${DIM}($n)${RESET}\n" "$desc"
    else
        printf "  ${RED}✗${RESET} %s ${DIM}($n, max $max)${RESET}\n" "$desc"
        printf "    ${YELLOW}fix:${RESET} %s\n" "$hint"
        FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
}

# ── checks ─────────────────────────────────────────────────────

section "ports"
check "8000 (backend)  listening" \
    "bin/dev.sh — backend not running" \
    nc -z 127.0.0.1 8000
check "5173 (frontend) listening" \
    "cd frontend && pnpm dev — frontend not running" \
    nc -z 127.0.0.1 5173
check "5542 (postgres) reachable" \
    "docker compose up -d postgres" \
    nc -z 127.0.0.1 5542
check "6479 (redis)    reachable" \
    "docker compose up -d redis" \
    nc -z 127.0.0.1 6479

section "docker"
check "no stale merism-app-web container" \
    "docker rm -f merism-app-web-1" \
    sh -c "! docker ps -a --format '{{.Names}}' | grep -qx merism-app-web-1"
check "no stale merism-app-frontend container" \
    "docker rm -f merism-app-frontend-1" \
    sh -c "! docker ps -a --format '{{.Names}}' | grep -qx merism-app-frontend-1"
check "celery-worker container running" \
    "docker compose up -d celery-worker" \
    sh -c "docker inspect -f '{{.State.Running}}' merism-app-celery-worker-1 2>/dev/null | grep -qx true"
check "celery-beat container running" \
    "docker compose up -d celery-beat" \
    sh -c "docker inspect -f '{{.State.Running}}' merism-app-celery-beat-1 2>/dev/null | grep -qx true"
check "no duplicate runserver processes" \
    "bin/clear-dev-ports.sh 8000 5173 — kill stale, restart bin/dev.sh" \
    sh -c "[ \$(ps -eo pid,comm,args | awk '\$2 ~ /^python/ && /manage.py runserver 0.0.0.0:8000/' | wc -l) -le 2 ]"

section "redis queues"
check_count "celery main queue not backed up" \
    "docker exec merism-app-redis-1 redis-cli -n 0 del celery — drop the queue" \
    100 \
    docker exec merism-app-redis-1 redis-cli -n 0 llen celery
check_count "no stale legacy task class names" \
    "docker exec merism-app-redis-1 redis-cli -n 0 flushdb — clear stale tasks" \
    20 \
    sh -c "docker exec merism-app-redis-1 redis-cli -n 0 dbsize"

section "django"
check "DB connection from manage.py" \
    "check POSTGRES_HOST/PORT in .env; docker compose ps postgres" \
    .venv/bin/python manage.py shell -c "from django.db import connections; connections['default'].ensure_connection()"
check "settings module is dev" \
    "export DJANGO_SETTINGS_MODULE=merism.settings.dev" \
    .venv/bin/python -c "from django.conf import settings; import os; assert os.environ.get('DJANGO_SETTINGS_MODULE') == 'merism.settings.dev', os.environ.get('DJANGO_SETTINGS_MODULE')"
check "no pending migrations" \
    "python manage.py migrate" \
    sh -c ".venv/bin/python manage.py migrate --check >/dev/null 2>&1"

section "test data"
check "admin user exists" \
    "python manage.py seed_dev" \
    .venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; assert get_user_model().objects.filter(email='admin@merism.test', is_superuser=True).exists()"
check "admin password is merism-dev" \
    "python manage.py seed_dev — re-runs set_password" \
    .venv/bin/python manage.py shell -c "from django.contrib.auth import authenticate; assert authenticate(username='admin@merism.test', password='merism-dev') is not None"
check "admin in at least one Organization" \
    "python manage.py seed_dev — joins admin to all orgs" \
    .venv/bin/python manage.py shell -c "from django.contrib.auth import get_user_model; u = get_user_model().objects.get(email='admin@merism.test'); assert u.merism_org_memberships.exists()"

section "celery"
check "worker can ping itself" \
    "docker logs merism-app-celery-worker-1 — check for crash" \
    docker exec merism-app-celery-worker-1 sh -c "celery -A merism inspect ping -d celery@\$(hostname) >/dev/null"
check "worker not failing on stale tasks" \
    "docker exec merism-app-redis-1 redis-cli -n 0 flushdb — clear queue" \
    sh -c "[ $(docker logs merism-app-celery-worker-1 --since 60s 2>&1 | grep -c 'unregistered task') -lt 5 ]"

if [[ "$QUICK" == false ]]; then
    section "external services (slow)"
    check "DeepSeek API key set" \
        "set MERISM_LLM_API_KEY in .env" \
        sh -c "[ -n \"\${MERISM_LLM_API_KEY:-\$(grep '^MERISM_LLM_API_KEY=' .env 2>/dev/null | cut -d= -f2-)}\" ]"
    check "MinIO reachable" \
        "docker compose up -d minio" \
        curl -sf -o /dev/null http://127.0.0.1:9100/minio/health/live
fi

# ── summary ────────────────────────────────────────────────────

echo ""
if [[ "$FAIL_COUNT" -eq 0 ]]; then
    echo "${GREEN}━━━ all checks passed ━━━${RESET}"
    exit 0
else
    echo "${RED}━━━ $FAIL_COUNT check(s) failed — see fix hints above ━━━${RESET}"
    echo ""
    echo "Common one-shot recovery: ${YELLOW}bin/reset.sh${RESET}"
    exit 1
fi
