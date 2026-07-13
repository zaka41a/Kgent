from __future__ import annotations

import json
import math
import os
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Protocol

from .ingest import Chunk

# BM25 ranking. k1 controls term-frequency saturation, b the length
# normalization; 1.5 / 0.75 are the standard Okapi defaults.
_TOKEN_RE = re.compile(r"[a-z0-9_]+")
_BM25_K1 = 1.5
_BM25_B = 0.75


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


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
        # Cached BM25 statistics, rebuilt lazily and invalidated on write.
        self._index: tuple[list[Counter[str]], list[int], dict[str, int], float] | None = None

    def add(
        self,
        chunks: list[Chunk],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        self._chunks.extend(chunks)
        self._index = None
        self._persist()
        if on_progress is not None and chunks:
            on_progress(len(chunks), len(chunks))

    def reset(self) -> None:
        self._chunks = []
        self._index = None
        self._persist()

    def _persist(self) -> None:
        self.path.write_text(
            json.dumps([asdict(c) for c in self._chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _ensure_index(
        self,
    ) -> tuple[list[Counter[str]], list[int], dict[str, int], float]:
        if self._index is None:
            tfs: list[Counter[str]] = []
            lengths: list[int] = []
            df: dict[str, int] = {}
            for c in self._chunks:
                tf = Counter(_tokenize(c.text))
                tfs.append(tf)
                lengths.append(sum(tf.values()))
                for term in tf:
                    df[term] = df.get(term, 0) + 1
            avgdl = (sum(lengths) / len(lengths)) if lengths else 0.0
            self._index = (tfs, lengths, df, avgdl)
        return self._index

    def query(self, text: str, k: int = 5) -> list[Chunk]:
        qterms = set(_tokenize(text))
        if not qterms:
            return self._chunks[:k]
        n = len(self._chunks)
        if n == 0:
            return []
        tfs, lengths, df, avgdl = self._ensure_index()
        idf = {
            t: math.log(1 + (n - df.get(t, 0) + 0.5) / (df.get(t, 0) + 0.5))
            for t in qterms
        }
        scored: list[tuple[float, Chunk]] = []
        for i, c in enumerate(self._chunks):
            tf = tfs[i]
            dl = lengths[i]
            score = 0.0
            for t in qterms:
                f = tf.get(t, 0)
                if not f:
                    continue
                norm = 1 - _BM25_B + _BM25_B * (dl / avgdl if avgdl else 0.0)
                score += idf[t] * (f * (_BM25_K1 + 1)) / (f + _BM25_K1 * norm)
            if score > 0:
                scored.append((score * _path_boost(c.doc_path), c))
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
