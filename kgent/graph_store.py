"""On-disk persistence for the knowledge graph.

Entity-based extraction is expensive (one LLM call per chunk), so the result
is cached next to the vector index. The cache embeds the store path and the
chunk count so a stale graph from a previous corpus can be detected and
rebuilt instead of being silently reused.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .graph import Edge, KGraph, Node

GRAPH_FILENAME = "graph.json"
GRAPH_VERSION = 1


def graph_path_for(store_path: Path) -> Path:
    return Path(store_path).parent / GRAPH_FILENAME


def save_graph(graph: KGraph, store_path: Path, chunk_count: int, mode: str) -> Path:
    target = graph_path_for(store_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": GRAPH_VERSION,
        "mode": mode,
        "store_path": str(store_path),
        "chunk_count": chunk_count,
        "nodes": [asdict(n) for n in graph.nodes.values()],
        "edges": [asdict(e) for e in graph.edges],
    }
    target.write_text(json.dumps(payload), encoding="utf-8")
    return target


def load_graph(store_path: Path, chunk_count: int, mode: str) -> KGraph | None:
    target = graph_path_for(store_path)
    if not target.exists():
        return None
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if payload.get("version") != GRAPH_VERSION:
        return None
    if payload.get("mode") != mode:
        return None
    if payload.get("chunk_count") != chunk_count:
        return None
    graph = KGraph()
    for raw in payload.get("nodes", []):
        graph.add_node(Node(**raw))
    for raw in payload.get("edges", []):
        graph.add_edge(Edge(**raw))
    return graph


def delete_graph(store_path: Path) -> None:
    target = graph_path_for(store_path)
    target.unlink(missing_ok=True)
