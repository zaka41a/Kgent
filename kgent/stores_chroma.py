from __future__ import annotations

import uuid
from collections.abc import Callable
from pathlib import Path

from .ingest import Chunk
from .store import _MetaMixin

# Chunks are sent to Chroma in slices of this size so a large repository does
# not embed everything in one call and spike memory and CPU.
ADD_BATCH_SIZE = 256


class ChromaStore(_MetaMixin):
    COLLECTION = "kgent_chunks"

    def __init__(self, path: Path):
        try:
            import chromadb
        except ImportError as e:
            raise RuntimeError(
                "chromadb is not installed. Run `pip install chromadb`."
            ) from e

        self._chromadb = chromadb
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self.client = chromadb.PersistentClient(path=str(self.path.parent / "chroma_db"))
        self.collection = self.client.get_or_create_collection(name=self.COLLECTION)
        self._meta_path = self.path.parent / "meta.json"

    def add(
        self,
        chunks: list[Chunk],
        on_progress: Callable[[int, int], None] | None = None,
    ) -> None:
        if not chunks:
            return
        total = len(chunks)
        for start in range(0, total, ADD_BATCH_SIZE):
            batch = chunks[start:start + ADD_BATCH_SIZE]
            ids: list[str] = []
            documents: list[str] = []
            metadatas: list[dict] = []
            for c in batch:
                ids.append(f"{c.doc_path}#{c.index}#{uuid.uuid4().hex[:6]}")
                documents.append(c.text)
                metadatas.append({"doc_path": c.doc_path, "kind": c.kind, "index": c.index})
            self.collection.add(ids=ids, documents=documents, metadatas=metadatas)
            if on_progress is not None:
                on_progress(min(start + ADD_BATCH_SIZE, total), total)

    def reset(self) -> None:
        existing = {c.name for c in self.client.list_collections()}
        if self.COLLECTION in existing:
            self.client.delete_collection(self.COLLECTION)
        self.collection = self.client.get_or_create_collection(name=self.COLLECTION)

    def query(self, text: str, k: int = 5) -> list[Chunk]:
        if self.collection.count() == 0:
            return []
        result = self.collection.query(query_texts=[text], n_results=k)
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        chunks: list[Chunk] = []
        for text_i, meta in zip(documents, metadatas, strict=False):
            chunks.append(
                Chunk(
                    doc_path=meta.get("doc_path", "?"),
                    kind=meta.get("kind", "text"),
                    index=int(meta.get("index", 0)),
                    text=text_i,
                )
            )
        return chunks

    def count(self) -> int:
        return self.collection.count()

    def all_chunks(self) -> list[Chunk]:
        if self.collection.count() == 0:
            return []
        result = self.collection.get()
        documents = result.get("documents", [])
        metadatas = result.get("metadatas", [])
        chunks: list[Chunk] = []
        for text_i, meta in zip(documents, metadatas, strict=False):
            chunks.append(
                Chunk(
                    doc_path=meta.get("doc_path", "?"),
                    kind=meta.get("kind", "text"),
                    index=int(meta.get("index", 0)),
                    text=text_i,
                )
            )
        return chunks
