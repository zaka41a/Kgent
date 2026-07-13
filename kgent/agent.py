from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Protocol

import httpx

from .ingest import Chunk
from .retriever import format_context

SYSTEM_PROMPT = (
    "You are a documentation assistant. You answer questions strictly based on the "
    "context snippets below. If the context does not contain the answer, say so. "
    "Always cite the document path of the snippet you used. When a list of known "
    "relationships between entities is provided, use it to connect facts that span "
    "multiple snippets."
)


class LLMClient(Protocol):
    name: str
    model: str

    def complete(self, system: str, user: str) -> str: ...
    def stream(self, system: str, user: str) -> Iterator[str]: ...


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434"
    model: str = "mistral"
    name: str = "ollama"

    def complete(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n{user}"
        resp = httpx.post(
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": False},
            timeout=300.0,
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()

    def stream(self, system: str, user: str) -> Iterator[str]:
        prompt = f"{system}\n\n{user}"
        with httpx.stream(
            "POST",
            f"{self.base_url}/api/generate",
            json={"model": self.model, "prompt": prompt, "stream": True},
            timeout=300.0,
        ) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if payload.get("response"):
                    yield payload["response"]
                if payload.get("done"):
                    break


@dataclass
class OpenAIClient:
    api_key: str
    model: str = "gpt-4o-mini"
    base_url: str = "https://api.openai.com/v1"
    name: str = "openai"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

    def complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()

    def stream(self, system: str, user: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/chat/completions",
            headers=self._headers(),
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": True,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw or not raw.startswith("data:"):
                    continue
                data = raw[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                delta = payload.get("choices", [{}])[0].get("delta", {}).get("content")
                if delta:
                    yield delta


@dataclass
class GroqClient(OpenAIClient):
    base_url: str = "https://api.groq.com/openai/v1"
    name: str = "groq"
    model: str = "llama-3.3-70b-versatile"


@dataclass
class AnthropicClient:
    api_key: str
    model: str = "claude-haiku-4-5"
    base_url: str = "https://api.anthropic.com/v1"
    name: str = "anthropic"

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def complete(self, system: str, user: str) -> str:
        resp = httpx.post(
            f"{self.base_url}/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120.0,
        )
        resp.raise_for_status()
        blocks = resp.json().get("content", [])
        return "".join(b.get("text", "") for b in blocks if b.get("type") == "text").strip()

    def stream(self, system: str, user: str) -> Iterator[str]:
        with httpx.stream(
            "POST",
            f"{self.base_url}/messages",
            headers=self._headers(),
            json={
                "model": self.model,
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": user}],
                "stream": True,
            },
            timeout=120.0,
        ) as resp:
            resp.raise_for_status()
            for raw in resp.iter_lines():
                if not raw or not raw.startswith("data:"):
                    continue
                data = raw[5:].strip()
                try:
                    payload = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if payload.get("type") == "content_block_delta":
                    delta = payload.get("delta", {}).get("text")
                    if delta:
                        yield delta
                elif payload.get("type") == "message_stop":
                    break


@dataclass(frozen=True)
class ProviderInfo:
    name: str
    available: bool
    models: list[str] = field(default_factory=list)


PROVIDER_MODELS = {
    "ollama": [],
    "openai": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
    "anthropic": ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-7"],
    "groq": ["llama-3.3-70b-versatile", "mixtral-8x7b-32768", "gemma2-9b-it"],
}


def list_providers(api_keys: dict[str, str] | None = None) -> list[ProviderInfo]:
    keys = {**os.environ, **(api_keys or {})}
    ollama_models = _list_ollama_models()
    return [
        ProviderInfo(name="ollama", available=bool(ollama_models), models=ollama_models),
        ProviderInfo(
            name="openai",
            available=bool(keys.get("OPENAI_API_KEY")),
            models=PROVIDER_MODELS["openai"],
        ),
        ProviderInfo(
            name="anthropic",
            available=bool(keys.get("ANTHROPIC_API_KEY")),
            models=PROVIDER_MODELS["anthropic"],
        ),
        ProviderInfo(
            name="groq",
            available=bool(keys.get("GROQ_API_KEY")),
            models=PROVIDER_MODELS["groq"],
        ),
    ]


def _list_ollama_models() -> list[str]:
    base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        resp = httpx.get(f"{base}/api/tags", timeout=2.0)
        resp.raise_for_status()
        return [m["name"] for m in resp.json().get("models", [])]
    except (httpx.HTTPError, ValueError):
        return []


def build_client(
    provider: str,
    model: str | None = None,
    api_keys: dict[str, str] | None = None,
) -> LLMClient:
    keys = {**os.environ, **(api_keys or {})}

    if provider == "ollama":
        return OllamaClient(
            base_url=keys.get("OLLAMA_BASE_URL", "http://localhost:11434"),
            model=model or keys.get("OLLAMA_MODEL", "mistral"),
        )
    if provider == "openai":
        api_key = keys.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        return OpenAIClient(api_key=api_key, model=model or "gpt-4o-mini")
    if provider == "anthropic":
        api_key = keys.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not set")
        return AnthropicClient(api_key=api_key, model=model or "claude-haiku-4-5")
    if provider == "groq":
        api_key = keys.get("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        return GroqClient(api_key=api_key, model=model or "llama-3.3-70b-versatile")

    raise ValueError(f"unknown provider: {provider!r}")


def build_default_client() -> LLMClient:
    if os.getenv("ANTHROPIC_API_KEY"):
        return build_client("anthropic")
    if os.getenv("OPENAI_API_KEY"):
        return build_client("openai")
    if os.getenv("GROQ_API_KEY"):
        return build_client("groq")
    return build_client("ollama")


def _build_user(question: str, chunks: list[Chunk], graph_context: str) -> str:
    parts: list[str] = []
    if graph_context:
        parts.append(graph_context)
    parts.append(f"Context:\n{format_context(chunks)}")
    parts.append(f"Question: {question}\nAnswer:")
    return "\n\n".join(parts)


def answer(
    client: LLMClient,
    question: str,
    chunks: list[Chunk],
    graph_context: str = "",
) -> str:
    if not chunks:
        return "No documentation has been ingested yet. Run `kgent ingest <path>` first."
    return client.complete(SYSTEM_PROMPT, _build_user(question, chunks, graph_context))


def answer_stream(
    client: LLMClient,
    question: str,
    chunks: list[Chunk],
    graph_context: str = "",
) -> Iterator[str]:
    if not chunks:
        yield "No documentation has been ingested yet. Run `kgent ingest <path>` first."
        return
    yield from client.stream(SYSTEM_PROMPT, _build_user(question, chunks, graph_context))
