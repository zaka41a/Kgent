from __future__ import annotations

from .graph import KGraph
from .ingest import Chunk
from .store import VectorStore


def retrieve(store: VectorStore, query: str, k: int = 5) -> list[Chunk]:
    return store.query(query, k=k)


def retrieve_with_graph(
    store: VectorStore,
    query: str,
    graph: KGraph | None,
    k: int = 5,
    hop_limit: int = 3,
) -> list[Chunk]:
    primary = store.query(query, k=k)
    if not graph or not primary or hop_limit <= 0:
        return primary

    seen: set[tuple[str, int]] = {(c.doc_path, c.index) for c in primary}
    expanded_terms: list[str] = []
    for chunk in primary:
        terms = _terms_in_text(chunk.text, set(graph.nodes.keys()))
        for term in terms:
            neighbors = _top_neighbors(graph, term, limit=2)
            for neighbor in neighbors:
                if neighbor not in expanded_terms:
                    expanded_terms.append(neighbor)
        if len(expanded_terms) >= hop_limit:
            break

    extra: list[Chunk] = []
    for term in expanded_terms[:hop_limit]:
        for chunk in store.query(term, k=2):
            key = (chunk.doc_path, chunk.index)
            if key in seen:
                continue
            seen.add(key)
            extra.append(chunk)

    return primary + extra


def _terms_in_text(text: str, vocabulary: set[str]) -> list[str]:
    found: list[str] = []
    for token in text.split():
        cleaned = token.strip(".,;:!?()[]{}\"'`")
        if cleaned in vocabulary and cleaned not in found:
            found.append(cleaned)
    return found


def _top_neighbors(graph: KGraph, term: str, limit: int = 2) -> list[str]:
    weighted: list[tuple[float, str]] = []
    for edge in graph.edges:
        if edge.src == term:
            weighted.append((edge.weight, edge.dst))
        elif edge.dst == term:
            weighted.append((edge.weight, edge.src))
    weighted.sort(key=lambda row: row[0], reverse=True)
    return [t for _, t in weighted[:limit]]


def format_context(chunks: list[Chunk]) -> str:
    parts: list[str] = []
    for c in chunks:
        header = f"[{c.doc_path}#{c.index}]"
        parts.append(f"{header}\n{c.text.strip()}")
    return "\n\n".join(parts)
