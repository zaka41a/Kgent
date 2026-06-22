from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .ingest import Chunk


class VectorStore(Protocol):
    def add(
        self,
        chunks: list[Chunk],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None: ...
    def query(self, text: str, k: int = 5) -> list[Chunk]: ...
    def count(self) -> int: ...
    def all_chunks(self) -> list[Chunk]: ...


class _MetaMixin:
    """Shared on-disk corpus metadata, read from/written to ``self._meta_path``."""

    _meta_path: Path

    def get_meta(self) -> dict:
        if not self._meta_path.exists():
            return {}
        try:
            return json.loads(self._meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def set_meta(self, meta: dict) -> None:
        self._meta_path.parent.mkdir(parents=True, exist_ok=True)
        self._meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


class JsonStore(_MetaMixin):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._chunks: list[Chunk] = []
        if self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            self._chunks = [Chunk(**row) for row in data]
        self._meta_path = self.path.parent / "meta.json"

    def add(
        self,
        chunks: list[Chunk],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        self._chunks.extend(chunks)
        self._persist()
        if on_progress is not None and chunks:
            on_progress(len(chunks), len(chunks))

    def reset(self) -> None:
        self._chunks = []
        self._persist()

    def _persist(self) -> None:
        self.path.write_text(
            json.dumps([asdict(c) for c in self._chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def query(self, text: str, k: int = 5) -> list[Chunk]:
        terms = [t.lower() for t in text.split() if t]
        if not terms:
            return self._chunks[:k]
        scored: list[tuple[float, Chunk]] = []
        for c in self._chunks:
            body = c.text.lower()
            score = float(sum(body.count(t) for t in terms))
            if score > 0:
                score *= _path_boost(c.doc_path)
                scored.append((score, c))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [c for _, c in scored[:k]]

    def count(self) -> int:
        return len(self._chunks)

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks)


def get_store(kind: str, path: Path) -> VectorStore:
    if kind == "auto":
        env_kind = os.getenv("KGENT_STORE", "json").lower()
        if env_kind == "chroma":
            try:
                return _try_chroma(path)
            except Exception:
                return JsonStore(path)
        return JsonStore(path)
    if kind == "json":
        return JsonStore(path)
    if kind == "chroma":
        return _try_chroma(path)
    raise ValueError(f"unknown store kind: {kind!r}")


def _path_boost(doc_path: str) -> float:
    lower = doc_path.lower()
    parts = doc_path.split("/")
    name = parts[-1].lower()

    if name.startswith("readme"):
        return 4.0
    if name in {"world.py", "main.py", "__init__.py", "app.py", "server.py"}:
        return 2.5
    if any(p in {"docs", "doc"} for p in parts):
        return 1.6
    if any(p in {"tests", "test", "fixtures"} for p in parts):
        return 0.5
    if "release_notes" in lower or "changelog" in lower:
        return 0.7
    if len(parts) == 1 and name.endswith(".md"):
        return 2.0
    return 1.0


def _try_chroma(path: Path) -> VectorStore:
    try:
        import chromadb  # noqa: F401
    except ImportError as e:
        raise RuntimeError("chromadb is not installed") from e
    from .stores_chroma import ChromaStore
    return ChromaStore(path)
