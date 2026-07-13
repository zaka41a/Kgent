from pathlib import Path

from kgent.graph import Edge, KGraph, Node, build_cooccurrence_graph
from kgent.ingest import Chunk
from kgent.retriever import (
    format_context,
    format_graph_context,
    retrieve,
    retrieve_with_graph,
)
from kgent.store import JsonStore


def _make_store(tmp_path: Path, chunks: list[Chunk]) -> JsonStore:
    store = JsonStore(tmp_path / "index.json")
    store.add(chunks)
    return store


def test_retrieve_returns_top_k_by_keyword(tmp_path: Path):
    store = _make_store(
        tmp_path,
        [
            Chunk("a.md", "markdown", 0, "alpha beta"),
            Chunk("b.md", "markdown", 0, "gamma delta"),
            Chunk("c.md", "markdown", 0, "alpha gamma"),
        ],
    )
    hits = retrieve(store, "alpha", k=2)
    paths = {c.doc_path for c in hits}
    assert "a.md" in paths
    assert "c.md" in paths


def test_retrieve_with_graph_falls_back_without_graph(tmp_path: Path):
    store = _make_store(tmp_path, [Chunk("a.md", "markdown", 0, "alpha")])
    hits = retrieve_with_graph(store, "alpha", graph=None, k=3)
    assert len(hits) == 1


def test_retrieve_with_graph_expands_via_neighbors(tmp_path: Path):
    chunks = [
        Chunk("docs/intro.md", "markdown", 0, "Alice introduced Bob to the project"),
        Chunk("docs/team.md", "markdown", 0, "Alice and Bob lead the team"),
        Chunk("notes/carol.md", "markdown", 0, "Bob mentored Carol last quarter"),
        Chunk("notes/follow.md", "markdown", 0, "Bob and Carol shipped the release"),
    ]
    store = _make_store(tmp_path, chunks)
    graph = build_cooccurrence_graph(chunks, min_count=2)
    hits = retrieve_with_graph(store, "Alice", graph=graph, k=2, hop_limit=3)
    paths = [c.doc_path for c in hits]
    assert paths[:2] == ["docs/intro.md", "docs/team.md"]
    assert any(p.startswith("notes/") for p in paths)


def test_retrieve_with_graph_zero_hop_skips_expansion(tmp_path: Path):
    chunks = [
        Chunk("a.md", "markdown", 0, "Alice met Bob"),
        Chunk("b.md", "markdown", 0, "Alice met Bob"),
        Chunk("c.md", "markdown", 0, "Bob met Carol"),
    ]
    store = _make_store(tmp_path, chunks)
    graph = build_cooccurrence_graph(chunks, min_count=2)
    hits = retrieve_with_graph(store, "Alice", graph=graph, k=2, hop_limit=0)
    assert len(hits) == 2


def test_format_context_includes_path_header():
    chunks = [Chunk("readme.md", "markdown", 0, "hello")]
    out = format_context(chunks)
    assert "[readme.md#0]" in out
    assert "hello" in out


def test_format_graph_context_lists_entity_relations():
    g = KGraph()
    g.add_node(Node(id="Marie Curie", label="Marie Curie", kind="person"))
    g.add_node(Node(id="Radium", label="Radium", kind="concept"))
    g.add_edge(Edge(src="Marie Curie", dst="Radium", kind="discovered"))
    chunks = [
        Chunk(doc_path="bio.md", kind="markdown", index=0,
              text="Marie Curie discovered Radium in 1898."),
    ]
    out = format_graph_context(g, chunks)
    assert "Marie Curie discovered Radium" in out


def test_format_graph_context_empty_for_cooccurrence():
    g = KGraph()
    g.add_node(Node(id="Alpha", label="Alpha"))
    g.add_node(Node(id="Beta", label="Beta"))
    g.add_edge(Edge(src="Alpha", dst="Beta", kind="co_occurs"))
    chunks = [
        Chunk(doc_path="x.md", kind="markdown", index=0,
              text="Alpha and Beta appear together."),
    ]
    assert format_graph_context(g, chunks) == ""


def test_format_graph_context_empty_when_no_entities_mentioned():
    g = KGraph()
    g.add_node(Node(id="Zeta", label="Zeta", kind="concept"))
    g.add_node(Node(id="Theta", label="Theta", kind="concept"))
    g.add_edge(Edge(src="Zeta", dst="Theta", kind="relates_to"))
    chunks = [Chunk(doc_path="x.md", kind="markdown", index=0, text="nothing relevant here")]
    assert format_graph_context(g, chunks) == ""
