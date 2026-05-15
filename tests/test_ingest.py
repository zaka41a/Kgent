from pathlib import Path

from kgent.ingest import (
    MAX_FILE_BYTES,
    Document,
    chunk,
    discover,
    ingest_path,
    load,
    looks_minified,
)


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


def test_discover_skips_files_over_size_limit(tmp_path: Path):
    big = tmp_path / "big.py"
    big.write_text("x = 1\n" * 200_000, encoding="utf-8")
    (tmp_path / "small.py").write_text("x = 1\n", encoding="utf-8")
    assert big.stat().st_size > MAX_FILE_BYTES
    found = sorted(p.name for p in discover(tmp_path))
    assert found == ["small.py"]


def test_discover_respects_gitignore(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("secret_dir\nscratch.md\n", encoding="utf-8")
    (tmp_path / "secret_dir").mkdir()
    (tmp_path / "secret_dir" / "x.md").write_text("# hidden", encoding="utf-8")
    (tmp_path / "scratch.md").write_text("# scratch", encoding="utf-8")
    (tmp_path / "keep.md").write_text("# keep", encoding="utf-8")
    found = sorted(p.name for p in discover(tmp_path))
    assert found == ["keep.md"]


def test_looks_minified_detects_long_lines():
    assert looks_minified("var a=1;" + "x" * 6000)
    assert not looks_minified("short\nlines\nonly\n")


def test_ingest_path_skips_minified_files(tmp_path: Path):
    (tmp_path / "bundle.js").write_text("var a=1;" + "y" * 6000, encoding="utf-8")
    (tmp_path / "clean.js").write_text("const a = 1;\n", encoding="utf-8")
    docs, _ = ingest_path(tmp_path)
    assert {d.path for d in docs} == {"clean.js"}


def test_ingest_path_reports_progress(tmp_path: Path):
    (tmp_path / "a.md").write_text("# a", encoding="utf-8")
    (tmp_path / "b.md").write_text("# b", encoding="utf-8")
    events: list[tuple[int, int, int, int]] = []
    ingest_path(tmp_path, on_progress=lambda *args: events.append(args))
    assert len(events) == 2
    assert events[-1][0] == 2
    assert events[-1][1] == 2
