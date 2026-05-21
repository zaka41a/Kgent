from pathlib import Path

from kgent.graph import Edge, KGraph, Node
from kgent.graph_store import delete_graph, graph_path_for, load_graph, save_graph


def _graph() -> KGraph:
    g = KGraph()
    g.add_node(Node(id="Alice", label="Alice", kind="person"))
    g.add_node(Node(id="Paris", label="Paris", kind="location"))
    g.add_edge(Edge(src="Alice", dst="Paris", kind="lives_in", weight=2.0))
    return g


def test_round_trip_saves_and_loads_the_graph(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_graph(_graph(), store_path, chunk_count=42, mode="entity")
    loaded = load_graph(store_path, chunk_count=42, mode="entity")
    assert loaded is not None
    assert loaded.nodes["Alice"].kind == "person"
    assert any(e.src == "Alice" and e.dst == "Paris" for e in loaded.edges)


def test_load_returns_none_when_chunk_count_changed(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_graph(_graph(), store_path, chunk_count=42, mode="entity")
    assert load_graph(store_path, chunk_count=43, mode="entity") is None


def test_load_returns_none_when_mode_differs(tmp_path: Path):
    store_path = tmp_path / "index.json"
    save_graph(_graph(), store_path, chunk_count=42, mode="entity")
    assert load_graph(store_path, chunk_count=42, mode="cooccurrence") is None


def test_load_returns_none_when_no_file(tmp_path: Path):
    assert load_graph(tmp_path / "index.json", chunk_count=1, mode="entity") is None


def test_delete_graph_is_idempotent(tmp_path: Path):
    store_path = tmp_path / "index.json"
    delete_graph(store_path)  # no file yet, should not raise
    save_graph(_graph(), store_path, chunk_count=1, mode="entity")
    delete_graph(store_path)
    assert not graph_path_for(store_path).exists()
