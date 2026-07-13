from __future__ import annotations

import re

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


def format_graph_context(
    graph: KGraph | None,
    chunks: list[Chunk],
    max_entities: int = 15,
    max_relations: int = 20,
) -> str:
    """Summarize the typed relations among entities that the sources mention.

    This is the "graph" in GraphRAG: instead of only handing the model raw
    chunks, we give it the explicit relationships (from the entity graph)
    between the entities that actually appear in those chunks, so it can connect
    facts that are spread across several snippets. Co-occurrence graphs carry no
    real relations, so they produce no context and this returns "".
    """
    if graph is None or not graph.nodes or not chunks:
        return ""

    text = " ".join(c.text for c in chunks).lower()
    tokens = set(re.findall(r"[a-z0-9_]+", text))
    mentioned = [
        node
        for node in graph.nodes.values()
        if len(node.label) >= 3
        and (node.label.lower() in text if " " in node.label else node.label.lower() in tokens)
    ]
    if not mentioned:
        return ""

    degree: dict[str, int] = {}
    for e in graph.edges:
        degree[e.src] = degree.get(e.src, 0) + 1
        degree[e.dst] = degree.get(e.dst, 0) + 1
    mentioned.sort(key=lambda n: degree.get(n.id, 0), reverse=True)
    keep = {n.id for n in mentioned[:max_entities]}
    label_by_id = {n.id: n.label for n in graph.nodes.values()}

    seen: set[tuple[str, str, str]] = set()
    lines: list[str] = []
    for e in graph.edges:
        if e.kind == "co_occurs" or e.src not in keep or e.dst not in keep:
            continue
        key = (e.src, e.kind, e.dst)
        if key in seen:
            continue
        seen.add(key)
        rel = e.kind.replace("_", " ")
        lines.append(f"- {label_by_id.get(e.src, e.src)} {rel} {label_by_id.get(e.dst, e.dst)}")
        if len(lines) >= max_relations:
            break

    if not lines:
        return ""
    return "Known relationships among entities in the sources:\n" + "\n".join(lines)
