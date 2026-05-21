import json

from kgent.graph import (
    KGraph,
    _extract_capitalized,
    _parse_extraction,
    build_cooccurrence_graph,
    build_entity_graph,
)
from kgent.ingest import Chunk


def _chunk(text: str, idx: int = 0) -> Chunk:
    return Chunk(doc_path="x.md", kind="markdown", index=idx, text=text)


def test_extract_capitalized_keeps_proper_nouns():
    found = _extract_capitalized("Alice met Bob at NASA in Paris.")
    assert "Alice" in found
    assert "Bob" in found
    assert "Paris" in found


def test_extract_capitalized_filters_short_or_uppercase():
    found = _extract_capitalized("AI ML and Cat are here")
    assert "AI" not in found
    assert "ML" not in found
    assert "Cat" in found


def test_extract_capitalized_strips_punctuation():
    found = _extract_capitalized("Hello, World!")
    assert "World" in found


def test_build_cooccurrence_respects_min_count():
    chunks = [
        _chunk("Alice met Bob.", 0),
        _chunk("Bob met Carol.", 1),
        _chunk("Alice met Bob again.", 2),
    ]
    graph = build_cooccurrence_graph(chunks, min_count=2)
    assert "Alice" in graph.nodes
    assert "Bob" in graph.nodes
    assert "Carol" not in graph.nodes


def test_build_cooccurrence_creates_edges():
    chunks = [_chunk("Alice met Bob.", 0), _chunk("Alice met Bob.", 1)]
    graph = build_cooccurrence_graph(chunks, min_count=2)
    pairs = {tuple(sorted((e.src, e.dst))) for e in graph.edges}
    assert ("Alice", "Bob") in pairs


def test_kgraph_add_node_is_idempotent():
    from kgent.graph import Node

    g = KGraph()
    g.add_node(Node(id="x", label="X"))
    g.add_node(Node(id="x", label="X-bis"))
    assert len(g.nodes) == 1
    assert g.nodes["x"].label == "X"


def test_kgraph_typed_node_replaces_a_plain_term():
    from kgent.graph import Node

    g = KGraph()
    g.add_node(Node(id="paris", label="Paris"))
    g.add_node(Node(id="paris", label="Paris", kind="location"))
    assert g.nodes["paris"].kind == "location"


def test_parse_extraction_handles_code_fences():
    raw = '```json\n{"entities": [{"name": "Paris", "type": "location"}], "relations": []}\n```'
    parsed = _parse_extraction(raw)
    assert parsed is not None
    assert parsed["entities"][0]["name"] == "Paris"


def test_parse_extraction_returns_none_on_garbage():
    assert _parse_extraction("not json at all") is None
    assert _parse_extraction("") is None


class _StubExtractor:
    def __init__(self, payloads: list[dict]):
        self._payloads = list(payloads)

    def complete(self, system: str, user: str) -> str:
        if not self._payloads:
            return "{}"
        return json.dumps(self._payloads.pop(0))


def test_build_entity_graph_collects_typed_entities_and_relations():
    chunks = [
        _chunk(
            "Marie Curie worked at the University of Paris. " * 4,
            0,
        ),
        _chunk(
            "She moved to Paris in 1891. " * 4,
            1,
        ),
    ]
    extractor = _StubExtractor(
        [
            {
                "entities": [
                    {"name": "Marie Curie", "type": "person"},
                    {"name": "University of Paris", "type": "organization"},
                ],
                "relations": [
                    {
                        "source": "Marie Curie",
                        "type": "works at",
                        "target": "University of Paris",
                    }
                ],
            },
            {
                "entities": [
                    {"name": "Marie Curie", "type": "person"},
                    {"name": "Paris", "type": "location"},
                ],
                "relations": [
                    {"source": "Marie Curie", "type": "moved_to", "target": "Paris"}
                ],
            },
        ]
    )

    graph = build_entity_graph(chunks, extractor)

    assert "Marie Curie" in graph.nodes
    assert graph.nodes["Marie Curie"].kind == "person"
    assert graph.nodes["Paris"].kind == "location"
    edge_kinds = {(e.src, e.kind, e.dst) for e in graph.edges}
    assert ("Marie Curie", "works_at", "University of Paris") in edge_kinds
    assert ("Marie Curie", "moved_to", "Paris") in edge_kinds


def test_build_entity_graph_skips_short_chunks_and_bad_json():
    chunks = [_chunk("too short", 0), _chunk("Long enough text. " * 10, 1)]
    extractor = _StubExtractor([])  # always returns "{}"
    graph = build_entity_graph(chunks, extractor)
    assert graph.nodes == {}
    assert graph.edges == []


def test_build_entity_graph_drops_relations_pointing_to_unknown_entities():
    chunks = [_chunk("Some long enough passage. " * 8, 0)]
    extractor = _StubExtractor(
        [
            {
                "entities": [{"name": "Alice", "type": "person"}],
                "relations": [
                    {"source": "Alice", "type": "knows", "target": "Bob"}  # Bob missing
                ],
            }
        ]
    )
    graph = build_entity_graph(chunks, extractor)
    assert "Alice" in graph.nodes
    assert "Bob" not in graph.nodes
    assert graph.edges == []
