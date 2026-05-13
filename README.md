<div align="center">
  <img src="kgent/web_assets/logo.svg" width="84" alt="kgent logo" />
  <h1><span style="color:#10a37f">k</span>gent</h1>
  <p><strong>A knowledge graph aware chat agent over any project's documentation.</strong></p>
  <p>
    <a href="#install"><img src="https://img.shields.io/badge/python-3.10+-blue.svg" alt="python" /></a>
    <a href="#license"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="license" /></a>
    <img src="https://img.shields.io/badge/status-alpha-orange.svg" alt="status" />
  </p>
  <p>
    <img src="https://img.shields.io/badge/GraphRAG-enabled-10a37f.svg" alt="GraphRAG" />
    <img src="https://img.shields.io/badge/Vector%20DB-ChromaDB-1d4ed8.svg" alt="ChromaDB" />
    <img src="https://img.shields.io/badge/Index-HNSW-7c3aed.svg" alt="HNSW" />
    <img src="https://img.shields.io/badge/LLMs-Ollama%20%7C%20OpenAI%20%7C%20Anthropic%20%7C%20Groq-f59e0b.svg" alt="Multi-LLM" />
    <img src="https://img.shields.io/badge/Streaming-SSE-ef4444.svg" alt="SSE" />
    <img src="https://img.shields.io/badge/Stack-FastAPI%20%2B%20React-06b6d4.svg" alt="Stack" />
  </p>
</div>

## Overview

Point kgent at any folder. It indexes the documents, builds a vector store and a co occurrence knowledge graph, and exposes a chat agent that grounds its answers in retrieval. Reusable across projects, model agnostic, runnable fully local.

* Multi LLM. Ollama (local), OpenAI, Anthropic Claude, Groq.
* Multi store. Keyword (default, zero config) or vector embeddings via Chroma.
* GraphRAG. Vector top k combined with a graph hop on the co occurrence graph.
* Streaming. Server Sent Events stream responses token by token.
* Persistent chat. SQLite by default, Postgres in production.
* Web UI. React interface with provider switcher, settings modal, ingest flow.
* CLI. Pipe friendly commands for ingest, query, chat, and serve.

## Install

```bash
git clone <this repo>
cd kgent

python3.12 -m venv .venv
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -e ".[embed,graph]"   # full install: ChromaDB + graph

cd frontend && npm install && npm run build && cd ..
```

Extras:

* `[embed]` — adds `chromadb`, `sentence-transformers`, `torch` for vector search.
* `[graph]` — adds `networkx` for the co occurrence graph.
* Plain `pip install -e .` works too, but keeps the default keyword-based JSON store.

> Make sure your shell prompt shows `(.venv)` before installing. Installing outside the venv (e.g. from Anaconda's `(base)`) leaves `start.sh` unable to find the packages.

## Quick start

```bash
cp .env.example .env                # if not done yet
set -a; source .env; set +a         # export env vars into your shell
./start.sh
kgent ingest /path/to/your/repo
./stop.sh
```

Open http://127.0.0.1:8088 to use the UI, or run `kgent chat` for the REPL.

> `kgent/settings.py` reads `os.environ` directly and does not auto-load `.env`. The `set -a; source .env; set +a` line exports every variable from `.env` to the current shell, so `start.sh` picks them up.

## Vector storage (ChromaDB)

By default kgent stores chunks in a JSON file and searches by keyword. To switch to **semantic search** with ChromaDB:

```bash
# 1. ensure the embed extra is installed
python -m pip install -e ".[embed,graph]"

# 2. enable chroma in .env
echo "KGENT_STORE=chroma" >> .env

# 3. reload env and (re)start
set -a; source .env; set +a
./start.sh

# 4. verify
curl http://127.0.0.1:8088/api/store/info
# → "store_kind": "ChromaStore"

# 5. ingest your docs
kgent ingest /path/to/your/repo
```

This creates `.kgent_store/chroma_db/` containing:

| File | Role |
| --- | --- |
| `chroma.sqlite3` | Chunk text + metadata (collection registry) |
| `<uuid>/data_level0.bin` | The embedding vectors (~384 floats per chunk) |
| `<uuid>/link_lists.bin` | HNSW graph for fast nearest-neighbor search |
| `<uuid>/header.bin`, `length.bin` | HNSW index configuration |

JSON and Chroma stores cohabit without conflict in `.kgent_store/` — switch back any time with `KGENT_STORE=json`.

## Docker

```bash
cp .env.example .env
docker compose up --build
```

The compose file boots kgent with Postgres for chat history. Set your provider keys in `.env` first.

## Configuration

All configuration is via environment variables. None is required.

| Variable | Default | Purpose |
| --- | --- | --- |
| `KGENT_HOST` | `127.0.0.1` | Bind host |
| `KGENT_PORT` | `8088` | Bind port |
| `KGENT_VENV` | `$ROOT/.venv` | Python venv used by `start.sh` |
| `KGENT_STORE` | `auto` | `json` (keyword), `chroma` (semantic), or `auto` (chroma if installed, else json) |
| `KGENT_STORE_PATH` | `.kgent_store/index.json` | Index file location |
| `KGENT_DB_URL` | `sqlite:///.kgent_store/chat.db` | Connect string for chat history |
| `KGENT_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Allowed CORS origins |
| `KGENT_LOG_LEVEL` | `INFO` | Standard library log level |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Local Ollama daemon |
| `OLLAMA_MODEL` | `mistral` | Default Ollama model |
| `OPENAI_API_KEY` | unset | OpenAI provider |
| `ANTHROPIC_API_KEY` | unset | Anthropic Claude provider |
| `GROQ_API_KEY` | unset | Groq provider |

API keys can also be saved via the in app settings modal. They are persisted to the browser's `localStorage` and forwarded as a header on each request. The server never persists them.

## CLI

```bash
kgent ingest <path>            # index a directory
kgent query "your question"    # retrieval only, no LLM
kgent chat                     # interactive REPL
kgent serve --port 8088        # run the HTTP API + UI
```

## HTTP API

```
GET    /api/health
GET    /api/store/info
GET    /api/providers
POST   /api/ingest               { "path", "replace" }
POST   /api/ask                  { "question", "k", "provider", "model", "history", "conversation_id" }
POST   /api/ask/stream           same body, returns SSE
GET    /api/conversations
POST   /api/conversations        { "title", "provider", "model" }
GET    /api/conversations/{id}
DELETE /api/conversations/{id}
```

Bring your own keys by sending the `X-Kgent-Keys` header with a JSON object of key value pairs (the UI does this automatically).

## Architecture

```
Client (React)                          Server (FastAPI)                   Backends
                                                                          
provider picker            ───►  POST /api/ask/stream
ingest modal                       │
chat (multi turn,                  ▼
 streaming, copy/regen)     retriever ──► JsonStore | ChromaStore
                                   │
                                   ▼
                            graph hop on KGraph (co occurrence)
                                   │
                                   ▼
                            agent.complete / stream                ──►  ollama / openai
                                                                          anthropic / groq
                                   │
                                   ▼
                            chat_store (SQLite or Postgres)
```

## Development

```bash
pip install -e ".[test]"
pytest
ruff check kgent tests

cd frontend && npm run dev
```

## Project layout

```
kgent/
├── kgent/
│   ├── ingest.py         document discovery and chunking
│   ├── store.py          JsonStore + provider selector
│   ├── stores_chroma.py  Chroma vector store (opt in)
│   ├── graph.py          co occurrence graph
│   ├── retriever.py      retrieve_with_graph
│   ├── agent.py          Ollama / OpenAI / Anthropic / Groq clients
│   ├── chat_store.py     SQLAlchemy persistence for conversations
│   ├── server.py         FastAPI app
│   ├── settings.py       Pydantic environment configuration
│   ├── logging_config.py logging setup
│   ├── cli.py            click based CLI
│   ├── web/              built React assets (served at /)
│   └── web_assets/       static assets (logo)
├── frontend/             React + Vite + Tailwind source
├── tests/                pytest suite
├── Dockerfile            production image (multi stage build)
├── docker-compose.yml    kgent + Postgres
├── start.sh              start the server (with PID file)
├── stop.sh               stop the server cleanly
└── pyproject.toml
```

## License

MIT.
