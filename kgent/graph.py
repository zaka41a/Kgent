from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .ingest import Chunk


@dataclass
class Node:
    id: str
    label: str
    kind: str = "term"


@dataclass
class Edge:
    src: str
    dst: str
    kind: str = "co_occurs"
    weight: float = 1.0


@dataclass
class KGraph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)

    def add_node(self, node: Node) -> None:
        self.nodes.setdefault(node.id, node)

    def add_edge(self, edge: Edge) -> None:
        self.edges.append(edge)


def build_cooccurrence_graph(chunks: list[Chunk], min_count: int = 2) -> KGraph:
    counts: dict[str, int] = defaultdict(int)
    pairs: dict[tuple[str, str], int] = defaultdict(int)
    for chunk in chunks:
        terms = _extract_capitalized(chunk.text)
        for term in terms:
            counts[term] += 1
        for i, a in enumerate(terms):
            for b in terms[i + 1 :]:
                if a == b:
                    continue
                key = tuple(sorted((a, b)))
                pairs[key] += 1

    graph = KGraph()
    for term, count in counts.items():
        if count >= min_count:
            graph.add_node(Node(id=term, label=term))
    for (a, b), weight in pairs.items():
        if a in graph.nodes and b in graph.nodes:
            graph.add_edge(Edge(src=a, dst=b, weight=float(weight)))
    return graph


def _extract_capitalized(text: str) -> list[str]:
    out: list[str] = []
    for token in text.split():
        cleaned = token.strip(".,;:!?()[]{}\"'`")
        if len(cleaned) >= 3 and cleaned[0].isupper() and any(c.islower() for c in cleaned):
            out.append(cleaned)
    return out
