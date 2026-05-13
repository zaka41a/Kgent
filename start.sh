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

ready=0
for _ in $(seq 1 20); do
  if curl -s -o /dev/null "http://$HOST:$PORT/api/store/info"; then
    ready=1
    break
  fi
  sleep 0.5
done

if [[ "$ready" == "1" ]]; then
  info "Server is up. PID: $(cat "$PID_FILE")"
  info "Open: http://$HOST:$PORT"
  info "Logs: $LOG_FILE"
else
  err "Server did not respond after 10s. Tail of log:"
  tail -20 "$LOG_FILE" || true
  rm -f "$PID_FILE"
  exit 1
fi
