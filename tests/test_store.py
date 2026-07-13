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


def test_jsonstore_query_bm25_prefers_rarer_terms(tmp_path: Path):
    store = JsonStore(tmp_path / "index.json")
    store.add([
        Chunk(doc_path="common.md", kind="markdown", index=0,
              text="report report report report status"),
        Chunk(doc_path="rare.md", kind="markdown", index=0, text="report unicorn"),
        Chunk(doc_path="f1.md", kind="markdown", index=0, text="report note"),
        Chunk(doc_path="f2.md", kind="markdown", index=0, text="report memo"),
    ])
    # "report" is common (df=4) so it carries little weight; "unicorn" is rare
    # (df=1). BM25 ranks the doc with the rare term first, unlike raw counting.
    hits = store.query("report unicorn", k=1)
    assert hits[0].doc_path == "rare.md"


def test_jsonstore_query_returns_empty_on_no_match(tmp_path: Path):
    store = JsonStore(tmp_path / "index.json")
    store.add([Chunk(doc_path="a.md", kind="markdown", index=0, text="hello")])
    assert store.query("nothing", k=5) == []


def test_get_store_unknown_kind_raises(tmp_path: Path):
    import pytest

    with pytest.raises(ValueError):
        get_store("unknown", tmp_path / "index.json")
