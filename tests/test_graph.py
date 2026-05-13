from kgent.graph import KGraph, _extract_capitalized, build_cooccurrence_graph
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
