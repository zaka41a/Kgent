from __future__ import annotations

import json
import re
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol

from .ingest import Chunk
from .logging_config import get_logger

log = get_logger(__name__)


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
        existing = self.nodes.get(node.id)
        if existing is None:
            self.nodes[node.id] = node
        elif existing.kind == "term" and node.kind != "term":
            self.nodes[node.id] = node

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


# --- LLM-based entity/relation extraction --------------------------------

class _Extractor(Protocol):
    def complete(self, system: str, user: str) -> str: ...


ENTITY_KINDS = {
    "person", "organization", "location", "product", "technology",
    "concept", "event", "document", "other",
}

EXTRACTION_SYSTEM = (
    "You are an information extraction engine. Given a passage of text, "
    "extract the named entities and the relations between them. "
    "Respond with strict JSON only, no prose."
)

EXTRACTION_INSTRUCTION = """Extract entities and relations from the passage below.

Output strict JSON in this exact shape, nothing else:
{
  "entities": [
    {"name": "<canonical name>", "type": "<one of: person, organization, location, product, technology, concept, event, document, other>"}
  ],
  "relations": [
    {"source": "<entity name>", "type": "<short verb phrase, snake_case>", "target": "<entity name>"}
  ]
}

Rules:
- Only include entities that are explicitly named in the passage.
- Use the canonical surface form (e.g. "Marie Curie", not "she").
- Relation type is a short snake_case verb phrase like "works_at", "located_in", "depends_on", "wrote", "mentions".
- Only include relations whose source and target are both in the entities list.
- If nothing is extractable, return {"entities": [], "relations": []}.

Passage:
"""


def build_entity_graph(
    chunks: list[Chunk],
    extractor: _Extractor,
    *,
    min_chunk_chars: int = 80,
    max_chunk_chars: int = 4000,
    min_mentions: int = 1,
    on_progress: Callable[[int, int], None] | None = None,
) -> KGraph:
    """Build a graph of typed entities and relations by querying an LLM per chunk.

    `extractor` is any object exposing a `complete(system, user) -> str` method,
    e.g. an OllamaClient or OpenAIClient from agent.py.
    """
    counts: dict[str, int] = defaultdict(int)
    kinds: dict[str, str] = {}
    relations: dict[tuple[str, str, str], float] = defaultdict(float)

    total = len(chunks)
    for i, chunk in enumerate(chunks):
        text = chunk.text.strip()
        if len(text) < min_chunk_chars:
            if on_progress:
                on_progress(i + 1, total)
            continue
        if len(text) > max_chunk_chars:
            text = text[:max_chunk_chars]

        try:
            raw = extractor.complete(EXTRACTION_SYSTEM, EXTRACTION_INSTRUCTION + text)
        except Exception as exc:
            log.warning("entity extraction failed on chunk %d: %s", i, exc)
            if on_progress:
                on_progress(i + 1, total)
            continue

        payload = _parse_extraction(raw)
        if not payload:
            if on_progress:
                on_progress(i + 1, total)
            continue

        local_names: set[str] = set()
        for ent in payload.get("entities", []):
            name = _normalize_name(ent.get("name", ""))
            kind = _normalize_kind(ent.get("type", ""))
            if not name:
                continue
            counts[name] += 1
            kinds.setdefault(name, kind)
            local_names.add(name)

        for rel in payload.get("relations", []):
            src = _normalize_name(rel.get("source", ""))
            dst = _normalize_name(rel.get("target", ""))
            kind = _normalize_relation_kind(rel.get("type", ""))
            if not src or not dst or src == dst:
                continue
            if src not in local_names or dst not in local_names:
                continue
            relations[(src, dst, kind)] += 1.0

        if on_progress:
            on_progress(i + 1, total)

    graph = KGraph()
    for name, count in counts.items():
        if count >= min_mentions:
            graph.add_node(Node(id=name, label=name, kind=kinds.get(name, "concept")))
    for (src, dst, kind), weight in relations.items():
        if src in graph.nodes and dst in graph.nodes:
            graph.add_edge(Edge(src=src, dst=dst, kind=kind, weight=weight))
    return graph


def _parse_extraction(raw: str) -> dict | None:
    if not raw:
        return None
    text = raw.strip()
    # Some models wrap JSON in code fences.
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    # Find the first JSON object in the response.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


def _normalize_name(value: object) -> str:
    if not isinstance(value, str):
        return ""
    name = value.strip().strip("\"'`")
    if len(name) < 2 or len(name) > 120:
        return ""
    return name


def _normalize_kind(value: object) -> str:
    if not isinstance(value, str):
        return "concept"
    kind = value.strip().lower().replace(" ", "_")
    return kind if kind in ENTITY_KINDS else "concept"


def _normalize_relation_kind(value: object) -> str:
    if not isinstance(value, str):
        return "related_to"
    kind = re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
    return kind or "related_to"
