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

# Rebuild the frontend bundle when it is missing or older than the sources.
# Skip with KGENT_SKIP_BUILD=1.
WEB_INDEX="$ROOT/kgent/web/index.html"
if [[ -d "$ROOT/frontend" && "${KGENT_SKIP_BUILD:-0}" != "1" ]]; then
  if ! command -v npm >/dev/null 2>&1; then
    warn "npm not found, skipping frontend build (serving the existing bundle)."
  else
    needs_build=0
    if [[ ! -f "$WEB_INDEX" ]]; then
      needs_build=1
    elif [[ -n "$(find "$ROOT/frontend/src" "$ROOT/frontend/index.html" \
        "$ROOT/frontend/tailwind.config.js" -newer "$WEB_INDEX" 2>/dev/null)" ]]; then
      needs_build=1
    fi
    if [[ "$needs_build" == "1" ]]; then
      info "Building the frontend bundle..."
      build_ok=1
      if [[ ! -d "$ROOT/frontend/node_modules" ]]; then
        ( cd "$ROOT/frontend" && npm install ) || build_ok=0
      fi
      if [[ "$build_ok" == "1" ]] && ( cd "$ROOT/frontend" && npm run build ); then
        info "Frontend bundle rebuilt."
      else
        warn "Frontend build failed, serving the existing bundle."
      fi
    fi
  fi
fi

if command -v ollama >/dev/null 2>&1; then
  if ! curl -s -o /dev/null -m 1 "http://localhost:11434/api/tags"; then
    info "Starting local Ollama daemon..."
    nohup ollama serve >"$ROOT/.kgent_store/ollama.log" 2>&1 &
    sleep 2
  fi
fi

# Auto-build the knowledge graph when needed. Cooccurrence is built by the
# server itself at startup (it is fast). Entity mode requires an LLM call per
# chunk, so we do it here, before the server starts, only when the cache is
# missing or stale. Skip with KGENT_SKIP_GRAPH=1.
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1091
  set -a; . "$ROOT/.env"; set +a
fi
GRAPH_MODE="${KGENT_GRAPH_MODE:-cooccurrence}"
GRAPH_FILE="$ROOT/.kgent_store/graph.json"
if [[ "${KGENT_SKIP_GRAPH:-0}" != "1" && "$GRAPH_MODE" == "entity" ]]; then
  cached_mode=""
  if [[ -f "$GRAPH_FILE" ]]; then
    cached_mode="$(python -c "import json,sys; print(json.load(open('$GRAPH_FILE')).get('mode',''))" 2>/dev/null || true)"
  fi
  if [[ "$cached_mode" != "entity" ]]; then
    # Pick the cheapest available extractor: Groq > OpenAI > Anthropic > Ollama
    EXTRACT_PROVIDER=""
    EXTRACT_MODEL=""
    if [[ -n "${GROQ_API_KEY:-}" ]]; then
      EXTRACT_PROVIDER="groq"
      EXTRACT_MODEL="${KGENT_GRAPH_MODEL:-llama-3.3-70b-versatile}"
    elif [[ -n "${OPENAI_API_KEY:-}" ]]; then
      EXTRACT_PROVIDER="openai"
      EXTRACT_MODEL="${KGENT_GRAPH_MODEL:-gpt-4o-mini}"
    elif [[ -n "${ANTHROPIC_API_KEY:-}" ]]; then
      EXTRACT_PROVIDER="anthropic"
      EXTRACT_MODEL="${KGENT_GRAPH_MODEL:-claude-haiku-4-5-20251001}"
    elif command -v ollama >/dev/null 2>&1; then
      EXTRACT_PROVIDER="ollama"
      EXTRACT_MODEL="${KGENT_GRAPH_MODEL:-${OLLAMA_MODEL:-mistral}}"
    fi

    if [[ -z "$EXTRACT_PROVIDER" ]]; then
      warn "KGENT_GRAPH_MODE=entity but no LLM is available. Falling back to cooccurrence."
      warn "Set GROQ_API_KEY (or OPENAI_API_KEY / ANTHROPIC_API_KEY) in .env, or install Ollama."
      export KGENT_GRAPH_MODE=cooccurrence
    else
      info "Building entity graph with $EXTRACT_PROVIDER/$EXTRACT_MODEL (this can take a few minutes)..."
      if kgent graph build --provider "$EXTRACT_PROVIDER" --model "$EXTRACT_MODEL"; then
        info "Entity graph ready."
      else
        warn "Entity graph build failed. Falling back to cooccurrence for this session."
        export KGENT_GRAPH_MODE=cooccurrence
      fi
    fi
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
