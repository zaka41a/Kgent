from pathlib import Path

from kgent.ingest import Document, chunk, discover, ingest_path, load


def test_discover_filters_by_extension(tmp_path: Path):
    (tmp_path / "a.md").write_text("# Hello", encoding="utf-8")
    (tmp_path / "b.png").write_bytes(b"\x89PNG")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "c.py").write_text("x = 1", encoding="utf-8")
    found = sorted(p.name for p in discover(tmp_path))
    assert found == ["a.md", "c.py"]


def test_discover_skips_ignored_dirs(tmp_path: Path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config.md").write_text("# git", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.md").write_text("nope", encoding="utf-8")
    (tmp_path / "keep.md").write_text("# keep", encoding="utf-8")
    found = sorted(p.name for p in discover(tmp_path))
    assert found == ["keep.md"]


def test_chunk_short_doc_returns_single_chunk():
    doc = Document(path="x.md", kind="markdown", text="# Title\nshort body")
    chunks = chunk(doc, max_chars=1500)
    assert len(chunks) == 1
    assert chunks[0].text.startswith("# Title")


def test_chunk_markdown_splits_by_headings():
    text = "# A\nbody A\n## B\nbody B\n## C\nbody C"
    doc = Document(path="x.md", kind="markdown", text=text)
    chunks = chunk(doc, max_chars=20, overlap=0)
    assert len(chunks) >= 3
    assert all(c.doc_path == "x.md" for c in chunks)


def test_chunk_sliding_window_for_code():
    body = "line\n" * 1000
    doc = Document(path="x.py", kind="python", text=body)
    chunks = chunk(doc, max_chars=500, overlap=50)
    assert len(chunks) > 1
    for i in range(1, len(chunks)):
        assert chunks[i].index == i


def test_ingest_path_end_to_end(tmp_path: Path):
    (tmp_path / "a.md").write_text("# Hello\nWorld", encoding="utf-8")
    (tmp_path / "b.py").write_text("def f(): return 1\n", encoding="utf-8")
    docs, chunks = ingest_path(tmp_path)
    assert len(docs) == 2
    assert len(chunks) >= 2
    paths = {d.path for d in docs}
    assert paths == {"a.md", "b.py"}


def test_load_relative_path(tmp_path: Path):
    file = tmp_path / "sub" / "c.md"
    file.parent.mkdir()
    file.write_text("# c", encoding="utf-8")
    doc = load(file, root=tmp_path)
    assert doc.path == "sub/c.md"
    assert doc.kind == "markdown"
