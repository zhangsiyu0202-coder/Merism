#!/usr/bin/env bash
# Merism daily dev launcher with subcommands and PID tracking.
#
# Subcommands:
#   bin/dev.sh start        # default — start all services
#   bin/dev.sh stop         # stop services started by this script
#   bin/dev.sh status       # show what's running
#   bin/dev.sh restart      # stop + start
#
# Flags (start only):
#   --skip-docker           # skip docker compose up
#   --skip-seed             # skip seed_dev (admin password reset)
#   --skip-doctor           # skip post-startup doctor --quick
#
# What this owns:
#   1. Clears stale listeners on :8000 / :5173
#   2. docker compose up -d --wait  (postgres / redis / minio / celery)
#   3. python manage.py seed_dev    (idempotent — admin pw + org membership)
#   4. python manage.py runserver   (backend on :8000)
#   5. pnpm dev                     (frontend on :5173)
#   6. bin/doctor.sh --quick        (post-startup smoke test)
#
# PID tracking:
#   - Each child PID is written to .pids/dev/<service>.pid.
#   - The launcher itself writes its own PID to .pids/dev/launcher.pid.
#   - `stop` / `status` read these files. `start` refuses if launcher.pid
#     exists and the process is alive.
#
# Ctrl-C cleanly stops every child via pkill -P <launcher-pid>.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

PIDS_DIR="$REPO_ROOT/.pids/dev"
LAUNCHER_PID_FILE="$PIDS_DIR/launcher.pid"
BACKEND_PID_FILE="$PIDS_DIR/backend.pid"
FRONTEND_PID_FILE="$PIDS_DIR/frontend.pid"
mkdir -p "$PIDS_DIR"

# ── output helpers ────────────────────────────────────────────
green()  { printf "\033[32m✓\033[0m %s\n" "$*"; }
yellow() { printf "\033[33m⏳\033[0m %s\n" "$*"; }
red()    { printf "\033[31m✗\033[0m %s\n" "$*" >&2; }
dim()    { printf "\033[2m%s\033[0m\n" "$*"; }

# ── subcommand parsing ────────────────────────────────────────
SUBCOMMAND="start"
case "${1:-}" in
    start|stop|status|restart) SUBCOMMAND="$1"; shift ;;
    -h|--help)
        sed -n '2,30p' "$0"
        exit 0
        ;;
esac

SKIP_DOCKER=false
SKIP_SEED=false
SKIP_DOCTOR=false
for arg in "$@"; do
    case "$arg" in
        --skip-docker) SKIP_DOCKER=true ;;
        --skip-seed)   SKIP_SEED=true ;;
        --skip-doctor) SKIP_DOCTOR=true ;;
        *) red "unknown flag: $arg"; exit 1 ;;
    esac
done

# ── PID helpers ───────────────────────────────────────────────
is_alive() {
    local pid="$1"
    [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null
}

read_pid() {
    local file="$1"
    [[ -f "$file" ]] && cat "$file" 2>/dev/null
}

# ── status subcommand ─────────────────────────────────────────
cmd_status() {
    local launcher_pid backend_pid frontend_pid
    launcher_pid="$(read_pid "$LAUNCHER_PID_FILE")"
    backend_pid="$(read_pid "$BACKEND_PID_FILE")"
    frontend_pid="$(read_pid "$FRONTEND_PID_FILE")"

    printf "  %-12s " "launcher"
    if is_alive "$launcher_pid"; then green "running (PID $launcher_pid)"; else red "stopped"; fi

    printf "  %-12s " "backend"
    if is_alive "$backend_pid"; then
        green "running (PID $backend_pid)"
    elif lsof -ti tcp:8000 >/dev/null 2>&1; then
        local owner; owner="$(lsof -ti tcp:8000 | head -1)"
        printf "\033[33m?\033[0m :8000 owned by PID %s but no PID file (orphan)\n" "$owner"
    else
        red "stopped"
    fi

    printf "  %-12s " "frontend"
    if is_alive "$frontend_pid"; then
        green "running (PID $frontend_pid)"
    elif lsof -ti tcp:5173 >/dev/null 2>&1; then
        local owner; owner="$(lsof -ti tcp:5173 | head -1)"
        printf "\033[33m?\033[0m :5173 owned by PID %s but no PID file (orphan)\n" "$owner"
    else
        red "stopped"
    fi

    printf "  %-12s " "docker"
    if docker compose ps --status running --quiet 2>/dev/null | grep -q .; then
        local n; n="$(docker compose ps --status running --quiet 2>/dev/null | wc -l)"
        green "$n containers running"
    else
        red "stopped"
    fi
}

# ── stop subcommand ───────────────────────────────────────────
cmd_stop() {
    local launcher_pid backend_pid frontend_pid
    launcher_pid="$(read_pid "$LAUNCHER_PID_FILE")"
    backend_pid="$(read_pid "$BACKEND_PID_FILE")"
    frontend_pid="$(read_pid "$FRONTEND_PID_FILE")"

    yellow "Stopping merism dev services..."

    # Kill the entire process group rooted at the launcher. This catches
    # any descendants (StatReloader children, vite worker threads, etc.)
    # without us having to enumerate them.
    if is_alive "$launcher_pid"; then
        pkill -TERM -P "$launcher_pid" 2>/dev/null || true
        kill -TERM "$launcher_pid" 2>/dev/null || true
    fi

    # Also kill the explicit child PIDs in case the launcher was already
    # gone but its children survived (orphaned).
    for pid in "$backend_pid" "$frontend_pid"; do
        if is_alive "$pid"; then
            pkill -TERM -P "$pid" 2>/dev/null || true
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    sleep 1

    # Force-kill anything still on our ports.
    "$SCRIPT_DIR/clear-dev-ports.sh" 8000 5173

    rm -f "$LAUNCHER_PID_FILE" "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
    green "stopped"
}

# ── restart subcommand ────────────────────────────────────────
cmd_restart() {
    cmd_stop
    sleep 1
    cmd_start
}

# ── start subcommand ──────────────────────────────────────────
cmd_start() {
    # Refuse if already running (PID file exists + alive).
    local existing_pid
    existing_pid="$(read_pid "$LAUNCHER_PID_FILE")"
    if is_alive "$existing_pid"; then
        red "merism dev is already running (launcher PID $existing_pid)"
        red "Use 'bin/dev.sh stop' or 'bin/dev.sh restart'."
        exit 1
    fi
    # Stale PID file → clean and continue.
    rm -f "$LAUNCHER_PID_FILE"

    # Record the launcher's own PID so 'stop' / 'status' can find it.
    echo $$ > "$LAUNCHER_PID_FILE"

    # ── 1. Clear stale ports ────────────────────────────────
    yellow "Clearing stale listeners on :8000 / :5173..."
    "$SCRIPT_DIR/clear-dev-ports.sh" 8000 5173 || true
    green "ports clear"

    # ── 2. Docker services ──────────────────────────────────
    if [[ "$SKIP_DOCKER" == false ]]; then
        yellow "Starting docker services..."
        docker compose up -d --wait postgres redis minio celery-worker celery-beat
        green "docker services healthy"
    else
        dim "skipping docker (--skip-docker)"
    fi

    # ── 3. Apply migrations + seed (idempotent) ─────────────
    source .venv/bin/activate
    export DJANGO_SETTINGS_MODULE="merism.settings.dev"
    yellow "Applying migrations..."
    python manage.py migrate --no-input >/dev/null
    green "migrations up to date"

    if [[ "$SKIP_SEED" == false ]]; then
        yellow "Running seed_dev..."
        python manage.py seed_dev 2>&1 | sed 's/^/  /'
    else
        dim "skipping seed_dev (--skip-seed)"
    fi

    # ── 4. Cleanup trap ─────────────────────────────────────
    cleanup() {
        local exit_code=$?
        echo ""
        yellow "Shutting down..."
        # Kill all descendants of the launcher.
        pkill -TERM -P $$ 2>/dev/null || true
        sleep 1
        pkill -KILL -P $$ 2>/dev/null || true
        rm -f "$LAUNCHER_PID_FILE" "$BACKEND_PID_FILE" "$FRONTEND_PID_FILE"
        green "all processes stopped"
        exit "$exit_code"
    }
    trap cleanup EXIT INT TERM

    # ── 5. Backend (Django runserver) ──────────────────────
    yellow "Starting Django on :8000..."
    python manage.py runserver 0.0.0.0:8000 2>&1 | sed 's/^/[django] /' &
    local backend_pid=$!
    echo "$backend_pid" > "$BACKEND_PID_FILE"

    # Wait for /api/ to respond. Any HTTP response counts as "alive" — a
    # 403 is fine (auth required), only network failure should fail.
    local ok=false
    for _ in $(seq 1 30); do
        if curl -s -o /dev/null -w "%{http_code}" --max-time 2 \
                http://localhost:8000/api/ 2>/dev/null | grep -qE '^[1-5][0-9]{2}$'; then
            ok=true; break
        fi
        sleep 1
    done
    if [[ "$ok" == true ]]; then
        green "backend ready on :8000 (PID $backend_pid)"
    else
        red "backend failed to start within 30s — see [django] logs above"
        exit 1
    fi

    # ── 6. Frontend (Vite) ─────────────────────────────────
    yellow "Starting Vite on :5173..."
    (cd frontend && pnpm dev) 2>&1 | sed 's/^/[vite]   /' &
    local frontend_pid=$!
    echo "$frontend_pid" > "$FRONTEND_PID_FILE"

    ok=false
    for _ in $(seq 1 15); do
        if curl -s -o /dev/null -w "%{http_code}" --max-time 2 \
                http://localhost:5173/ 2>/dev/null | grep -qE '^[1-5][0-9]{2}$'; then
            ok=true; break
        fi
        sleep 1
    done
    if [[ "$ok" == true ]]; then
        green "frontend ready on :5173 (PID $frontend_pid)"
    else
        red "frontend failed to start within 15s — see [vite] logs above"
        exit 1
    fi

    # ── 7. Smoke test ──────────────────────────────────────
    if [[ "$SKIP_DOCTOR" == false ]] && [[ -x "$SCRIPT_DIR/doctor.sh" ]]; then
        echo ""
        yellow "Running doctor --quick..."
        if "$SCRIPT_DIR/doctor.sh" --quick > /tmp/merism-doctor.log 2>&1; then
            green "doctor: all checks passed"
        else
            red "doctor: some checks failed — see /tmp/merism-doctor.log"
            tail -20 /tmp/merism-doctor.log
        fi
    fi

    # ── Ready ──────────────────────────────────────────────
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    green "Merism dev ready → http://localhost:5173"
    dim "Login: admin@merism.test / merism-dev"
    dim "Stop:  bin/dev.sh stop  (or Ctrl-C)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Keep running until Ctrl-C; cleanup trap takes care of children.
    wait
}

# ── dispatch ──────────────────────────────────────────────────
case "$SUBCOMMAND" in
    start)   cmd_start ;;
    stop)    cmd_stop ;;
    status)  cmd_status ;;
    restart) cmd_restart ;;
esac
