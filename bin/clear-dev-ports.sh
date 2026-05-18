#!/usr/bin/env bash
# Clear stale local listeners before starting Merism dev servers.
#
# We use this from `make api`, `make web`, and the Playwright E2E launcher
# so a leftover Django or Vite process cannot silently keep serving an old
# bundle or an old backend implementation.

set -euo pipefail

if [[ $# -eq 0 ]]; then
    echo "usage: $0 PORT [PORT...]" >&2
    exit 1
fi

kill_listeners() {
    local port="$1"
    local pids
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        return
    fi

    echo "[dev] clearing listeners on :$port"
    while IFS= read -r pid; do
        [[ -z "$pid" ]] && continue
        kill -TERM "$pid" 2>/dev/null || true
    done <<< "$pids"
}

for port in "$@"; do
    kill_listeners "$port"
done

sleep 1

for port in "$@"; do
    pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
    if [[ -z "$pids" ]]; then
        continue
    fi
    echo "[dev] force-killing stubborn listeners on :$port" >&2
    while IFS= read -r pid; do
        [[ -z "$pid" ]] && continue
        kill -KILL "$pid" 2>/dev/null || true
    done <<< "$pids"
done
