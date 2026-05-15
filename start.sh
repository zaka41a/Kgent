#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${KGENT_PORT:-8088}"
HOST="${KGENT_HOST:-127.0.0.1}"
VENV_PATH="${KGENT_VENV:-$ROOT/.venv}"
LOG_FILE="$ROOT/.kgent_store/server.log"
PID_FILE="$ROOT/.kgent_store/server.pid"

mkdir -p "$ROOT/.kgent_store"

color() { printf "\033[%sm%s\033[0m\n" "$1" "$2"; }
info()  { color "36" "[kgent] $*"; }
warn()  { color "33" "[kgent] $*"; }
err()   { color "31" "[kgent] $*"; }

if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
  warn "Already running (PID $(cat "$PID_FILE")). Run ./stop.sh first."
  exit 1
fi

if [[ ! -d "$VENV_PATH" ]]; then
  err "Virtual env not found at: $VENV_PATH"
  err "Create one with: python3.12 -m venv .venv && source .venv/bin/activate && pip install -e ."
  err "Or set KGENT_VENV to an existing venv path."
  exit 1
fi

# shellcheck disable=SC1091
source "$VENV_PATH/bin/activate"

if ! command -v kgent >/dev/null 2>&1; then
  info "Installing kgent in editable mode..."
  pip install -e "$ROOT" >/dev/null
fi

if command -v ollama >/dev/null 2>&1; then
  if ! curl -s -o /dev/null -m 1 "http://localhost:11434/api/tags"; then
    info "Starting local Ollama daemon..."
    nohup ollama serve >"$ROOT/.kgent_store/ollama.log" 2>&1 &
    sleep 2
  fi
fi

info "Starting kgent on http://$HOST:$PORT"
nohup kgent serve --host "$HOST" --port "$PORT" >"$LOG_FILE" 2>&1 &
echo $! >"$PID_FILE"

READY_TIMEOUT_S="${KGENT_READY_TIMEOUT:-30}"
ready=0
iterations=$((READY_TIMEOUT_S * 2))
for _ in $(seq 1 "$iterations"); do
  if curl -s -o /dev/null "http://$HOST:$PORT/api/store/info"; then
    ready=1
    break
  fi
  sleep 0.5
done

PID="$(cat "$PID_FILE" 2>/dev/null || echo "")"

if [[ "$ready" == "1" ]]; then
  info "Server is up. PID: $PID"
  info "Open: http://$HOST:$PORT"
  info "Logs: $LOG_FILE"
else
  if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
    warn "Server did not respond after ${READY_TIMEOUT_S}s, but the process is still running (PID $PID)."
    warn "First start can take longer (torch + embeddings). Watch the log:"
    warn "  tail -f $LOG_FILE"
    warn "Then try: curl http://$HOST:$PORT/api/store/info"
    warn "Override the wait with: KGENT_READY_TIMEOUT=60 ./start.sh"
  else
    err "Server failed to start within ${READY_TIMEOUT_S}s. Tail of log:"
    tail -20 "$LOG_FILE" || true
    rm -f "$PID_FILE"
    exit 1
  fi
fi
