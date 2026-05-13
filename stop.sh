#!/usr/bin/env bash
# Stop the kgent server started via ./start.sh.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PID_FILE="$ROOT/.kgent_store/server.pid"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
info()  { color "36" "[kgent] $*"; }
warn()  { color "33" "[kgent] $*"; }

if [[ ! -f "$PID_FILE" ]]; then
  warn "No PID file at $PID_FILE."
  if pgrep -f "kgent serve" >/dev/null; then
    warn "Found a kgent process not started by start.sh:"
    pgrep -fl "kgent serve" || true
    info "Killing it..."
    pkill -f "kgent serve" || true
  fi
  exit 0
fi

PID="$(cat "$PID_FILE")"
if kill -0 "$PID" 2>/dev/null; then
  info "Stopping kgent (PID $PID)..."
  kill "$PID"
  for _ in $(seq 1 10); do
    sleep 0.3
    kill -0 "$PID" 2>/dev/null || break
  done
  if kill -0 "$PID" 2>/dev/null; then
    warn "Process did not exit, sending SIGKILL"
    kill -9 "$PID" || true
  fi
  info "Stopped."
else
  warn "PID $PID is not running (stale PID file)."
fi
rm -f "$PID_FILE"
