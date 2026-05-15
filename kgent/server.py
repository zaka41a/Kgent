from __future__ import annotations

import json
import time
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agent import (
    answer,
    answer_stream,
    build_client,
    build_default_client,
    list_providers,
)
from .chat_store import ChatStore
from .graph import KGraph, build_cooccurrence_graph
from .ingest import Chunk, ingest_path
from .logging_config import configure_logging, get_logger
from .retriever import retrieve_with_graph
from .settings import Settings, get_settings
from .store import get_store

WEB_DIR = Path(__file__).parent / "web"

log = get_logger(__name__)


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    k: int = 5
    provider: str | None = None
    model: str | None = None
    history: list[dict] = Field(default_factory=list)
    conversation_id: str | None = None


class StoreInfo(BaseModel):
    count: int
    store_path: str
    store_kind: str
    default_provider: str
    default_model: str
    active_repo: str | None = None
    document_count: int = 0
    has_graph: bool = False


class IngestRequest(BaseModel):
    path: str = Field(min_length=1)
    replace: bool = True


class ConversationCreate(BaseModel):
    title: str = "New chat"
    provider: str | None = None
    model: str | None = None


def _parse_api_keys(header_value: str | None) -> dict[str, str]:
    if not header_value:
        return {}
    try:
        return json.loads(header_value)
    except json.JSONDecodeError:
        log.warning("invalid X-Kgent-Keys header, ignoring")
        return {}


def _resolve_client(req: AskRequest, api_keys: dict[str, str]):
    if req.provider:
        return build_client(req.provider, req.model, api_keys=api_keys)
    return build_default_client()


def _llm_error_payload(exc: Exception, provider: str, model: str) -> dict:
    """Map a raw LLM exception to a structured, actionable error payload."""
    import httpx

    msg = str(exc)
    lower = msg.lower()
    error_type = "unknown"
    hint = "Check the server logs for the full traceback."

    if isinstance(exc, httpx.ConnectError) or "connection refused" in lower or "connection error" in lower:
        error_type = "connection"
        if provider == "ollama":
            hint = (
                "The Ollama daemon is not reachable. Start it with `ollama serve` and "
                "verify `OLLAMA_BASE_URL` (default: http://localhost:11434)."
            )
        else:
            hint = f"Could not reach the {provider} API. Check your internet connection and any proxy."
    elif isinstance(exc, httpx.TimeoutException) or "timeout" in lower:
        error_type = "timeout"
        hint = f"The {provider} API timed out. Try again, or pick a smaller/faster model than {model!r}."
    elif isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code if exc.response is not None else 0
        if status == 401 or status == 403:
            error_type = "auth"
            hint = f"Authentication failed for {provider}. Open Settings and re-enter your API key."
        elif status == 404:
            error_type = "model_not_found"
            if provider == "ollama":
                hint = f"Model {model!r} is not pulled locally. Run `ollama pull {model}` and retry."
            else:
                hint = f"Model {model!r} does not exist on {provider}. Pick another in the model selector."
        elif status == 429:
            error_type = "rate_limit"
            hint = f"{provider} rate limit hit. Wait a few seconds and try again."
        elif 500 <= status < 600:
            error_type = "upstream"
            hint = f"{provider} is having a problem (HTTP {status}). Retry in a moment."
        else:
            error_type = "http"
            hint = f"{provider} returned HTTP {status}."
    elif "api key" in lower or "unauthorized" in lower:
        error_type = "auth"
        hint = f"Missing or invalid API key for {provider}. Open Settings and set the key."

    return {
        "error": msg,
        "error_type": error_type,
        "provider": provider,
        "model": model,
        "hint": hint,
    }


def _augment_question_with_history(question: str, history: list[dict], window: int = 6) -> str:
    if not history:
        return question
    turns: list[str] = []
    for msg in history[-window:]:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if not content:
            continue
        prefix = "User" if role == "user" else "Assistant"
        turns.append(f"{prefix}: {content}")
    turns.append(f"User: {question}")
    return "\n".join(turns)


class _State:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store_path = settings.store_path
        self.store = get_store(settings.store_kind, settings.store_path)
        self.store_kind = type(self.store).__name__
        self.graph: KGraph | None = None
        self.chats = ChatStore(db_url=settings.db_url)
        self._maybe_rebuild_graph()

    def _maybe_rebuild_graph(self) -> None:
        chunks = getattr(self.store, "_chunks", None)
        if chunks:
            self.graph = build_cooccurrence_graph(chunks, min_count=3)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="kgent", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    state = _State(settings)

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/api/store/info", response_model=StoreInfo)
    def store_info(x_kgent_keys: str | None = Header(default=None)) -> StoreInfo:
        api_keys = _parse_api_keys(x_kgent_keys)
        try:
            client = build_default_client() if not api_keys else build_client(
                _first_available_provider(api_keys), api_keys=api_keys
            )
            provider = client.name
            model = client.model
        except Exception as exc:
            log.warning("default client unavailable: %s", exc)
            provider = "ollama"
            model = ""
        meta = state.store.get_meta() if hasattr(state.store, "get_meta") else {}
        return StoreInfo(
            count=state.store.count(),
            store_path=str(state.store_path),
            store_kind=state.store_kind,
            default_provider=provider,
            default_model=model,
            active_repo=meta.get("repo_path"),
            document_count=meta.get("document_count", 0),
            has_graph=state.graph is not None,
        )

    @app.get("/api/providers")
    def providers_endpoint(x_kgent_keys: str | None = Header(default=None)) -> dict:
        api_keys = _parse_api_keys(x_kgent_keys)
        infos = list_providers(api_keys=api_keys)
        return {"providers": [asdict(p) for p in infos]}

    @app.post("/api/ingest")
    def ingest_endpoint(req: IngestRequest) -> dict:
        target = Path(req.path).expanduser().resolve()
        if not target.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {target}")
        if not target.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {target}")

        if req.replace and hasattr(state.store, "reset"):
            state.store.reset()

        try:
            docs, chunks = ingest_path(target)
        except Exception as exc:
            log.exception("ingest failed for %s", target)
            raise HTTPException(status_code=500, detail=f"Ingestion failed: {exc}") from exc

        state.store.add(chunks)
        if hasattr(state.store, "set_meta"):
            state.store.set_meta({
                "repo_path": str(target),
                "document_count": len(docs),
                "chunk_count": state.store.count(),
            })

        if chunks:
            state.graph = build_cooccurrence_graph(chunks, min_count=3)

        log.info("ingested %d documents (%d chunks) from %s", len(docs), len(chunks), target)
        return {
            "documents": len(docs),
            "chunks_added": len(chunks),
            "total_chunks": state.store.count(),
            "repo_path": str(target),
        }

    @app.post("/api/ask")
    def ask_endpoint(
        req: AskRequest,
        x_kgent_keys: str | None = Header(default=None),
    ) -> dict:
        if state.store.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="Store is empty. Add a repository first.",
            )
        api_keys = _parse_api_keys(x_kgent_keys)
        try:
            client = _resolve_client(req, api_keys)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        question = _augment_question_with_history(req.question, req.history)
        chunks: list[Chunk] = retrieve_with_graph(state.store, question, state.graph, k=req.k)
        started = time.perf_counter()
        try:
            text = answer(client, question, chunks)
        except Exception as exc:
            log.exception("LLM backend error (provider=%s model=%s)", client.name, client.model)
            payload = _llm_error_payload(exc, client.name, client.model)
            raise HTTPException(status_code=502, detail=payload) from exc
        elapsed_ms = int((time.perf_counter() - started) * 1000)

        if req.conversation_id:
            try:
                state.chats.append_message(req.conversation_id, "user", req.question)
                state.chats.append_message(
                    req.conversation_id,
                    "assistant",
                    text,
                    context_json=json.dumps([asdict(c) for c in chunks]),
                    provider=client.name,
                    model=client.model,
                    elapsed_ms=elapsed_ms,
                )
            except ValueError as exc:
                log.warning("could not persist message: %s", exc)

        return {
            "answer": text,
            "context": [asdict(c) for c in chunks],
            "provider": client.name,
            "model": client.model,
            "elapsed_ms": elapsed_ms,
        }

    @app.post("/api/ask/stream")
    def ask_stream_endpoint(
        req: AskRequest,
        x_kgent_keys: str | None = Header(default=None),
    ) -> StreamingResponse:
        if state.store.count() == 0:
            raise HTTPException(
                status_code=400,
                detail="Store is empty. Add a repository first.",
            )
        api_keys = _parse_api_keys(x_kgent_keys)
        try:
            client = _resolve_client(req, api_keys)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        question = _augment_question_with_history(req.question, req.history)
        chunks: list[Chunk] = retrieve_with_graph(state.store, question, state.graph, k=req.k)

        def event_gen():
            yield _sse({
                "type": "context",
                "context": [asdict(c) for c in chunks],
                "provider": client.name,
                "model": client.model,
            })
            collected: list[str] = []
            started = time.perf_counter()
            try:
                for token in answer_stream(client, question, chunks):
                    collected.append(token)
                    yield _sse({"type": "delta", "content": token})
            except Exception as exc:
                log.exception("stream error (provider=%s)", client.name)
                payload = _llm_error_payload(exc, client.name, client.model)
                yield _sse({"type": "error", **payload})
                yield _sse({"type": "done"})
                return
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            answer_text = "".join(collected)

            if req.conversation_id:
                try:
                    state.chats.append_message(req.conversation_id, "user", req.question)
                    state.chats.append_message(
                        req.conversation_id,
                        "assistant",
                        answer_text,
                        context_json=json.dumps([asdict(c) for c in chunks]),
                        provider=client.name,
                        model=client.model,
                        elapsed_ms=elapsed_ms,
                    )
                except ValueError as exc:
                    log.warning("could not persist streamed message: %s", exc)

            yield _sse({"type": "done"})

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @app.get("/api/conversations")
    def list_conversations() -> dict:
        return {"conversations": state.chats.list_conversations()}

    @app.post("/api/conversations")
    def create_conversation(req: ConversationCreate) -> dict:
        meta = state.store.get_meta() if hasattr(state.store, "get_meta") else {}
        return state.chats.create_conversation(
            title=req.title,
            repo_path=meta.get("repo_path"),
            provider=req.provider,
            model=req.model,
        )

    @app.get("/api/conversations/{conv_id}")
    def get_conversation(conv_id: str) -> dict:
        conv = state.chats.get_conversation(conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="conversation not found")
        return conv

    @app.delete("/api/conversations/{conv_id}")
    def delete_conversation(conv_id: str) -> dict:
        if not state.chats.delete_conversation(conv_id):
            raise HTTPException(status_code=404, detail="conversation not found")
        return {"status": "deleted"}

    if WEB_DIR.exists():
        app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="frontend")

    return app


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _first_available_provider(api_keys: dict[str, str]) -> str:
    for info in list_providers(api_keys=api_keys):
        if info.available:
            return info.name
    return "ollama"


def serve(host: str | None = None, port: int | None = None, store_path: Path | None = None) -> None:
    import uvicorn

    settings = get_settings()
    if host is not None:
        settings.host = host
    if port is not None:
        settings.port = port
    if store_path is not None:
        settings.store_path = store_path

    uvicorn.run(create_app(settings), host=settings.host, port=settings.port)
