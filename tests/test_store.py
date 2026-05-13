from pathlib import Path

from kgent.ingest import Chunk
from kgent.store import JsonStore, get_store


def test_jsonstore_roundtrip(tmp_path: Path):
    store = JsonStore(tmp_path / "index.json")
    store.add([
        Chunk(doc_path="a.md", kind="markdown", index=0, text="alpha beta"),
        Chunk(doc_path="b.md", kind="markdown", index=0, text="gamma delta"),
    ])
    reopened = JsonStore(tmp_path / "index.json")
    assert reopened.count() == 2


def test_jsonstore_query_ranks_by_term_frequency(tmp_path: Path):
    store = JsonStore(tmp_path / "index.json")
    store.add([
        Chunk(doc_path="a.md", kind="markdown", index=0, text="alpha alpha alpha beta"),
        Chunk(doc_path="b.md", kind="markdown", index=0, text="alpha gamma"),
        Chunk(doc_path="c.md", kind="markdown", index=0, text="zeta eta"),
    ])
    hits = store.query("alpha", k=3)
    assert hits[0].doc_path == "a.md"
    assert {h.doc_path for h in hits} == {"a.md", "b.md"}


def test_jsonstore_query_returns_empty_on_no_match(tmp_path: Path):
    store = JsonStore(tmp_path / "index.json")
    store.add([Chunk(doc_path="a.md", kind="markdown", index=0, text="hello")])
    assert store.query("nothing", k=5) == []


def test_get_store_unknown_kind_raises(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        get_store("unknown", tmp_path / "index.json")
