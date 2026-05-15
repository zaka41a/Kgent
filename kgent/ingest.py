from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "rst",
    ".txt": "text",
    ".py": "python",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".yaml": "yaml",
    ".yml": "yaml",
}


@dataclass(frozen=True)
class Document:
    path: str
    kind: str
    text: str


@dataclass(frozen=True)
class Chunk:
    doc_path: str
    kind: str
    index: int
    text: str


_NOISE_FILENAMES = {
    "license",
    "license.txt",
    "license.md",
    "copying",
    "notice",
    "notice.txt",
    "code_of_conduct.md",
    "contributing.md",
    "changelog.md",
}

_NOISE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "dist", "build",
               ".kgent_store", ".github", "LICENSES", "licenses", ".idea",
               ".vscode", "site-packages", "egg-info", "chroma_db", ".tox",
               ".mypy_cache", ".pytest_cache", ".ruff_cache",
               ".next", ".vercel", ".turbo", ".nuxt", ".svelte-kit",
               "out", "coverage", ".cache", ".parcel-cache"}


def discover(root: Path, ignore: Iterable[str] = ()) -> Iterator[Path]:
    ignore_set = set(_NOISE_DIRS)
    ignore_set.update(ignore)
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in ignore_set or part.endswith(".egg-info") for part in path.parts):
            continue
        if path.name.lower() in _NOISE_FILENAMES:
            continue
        if path.suffix.lower() in SUPPORTED_EXTENSIONS:
            yield path


def load(path: Path, root: Path | None = None) -> Document:
    rel = str(path.relative_to(root)) if root else str(path)
    return Document(
        path=rel,
        kind=SUPPORTED_EXTENSIONS[path.suffix.lower()],
        text=path.read_text(encoding="utf-8", errors="replace"),
    )


def chunk(doc: Document, max_chars: int = 1500, overlap: int = 200) -> list[Chunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap < 0 or overlap >= max_chars:
        raise ValueError("overlap must be in [0, max_chars)")

    if doc.kind == "markdown":
        return _chunk_markdown(doc, max_chars, overlap)
    return _chunk_sliding(doc, max_chars, overlap)


def _chunk_sliding(doc: Document, max_chars: int, overlap: int) -> list[Chunk]:
    text = doc.text
    if len(text) <= max_chars:
        return [Chunk(doc.path, doc.kind, 0, text)]
    chunks: list[Chunk] = []
    start = 0
    idx = 0
    step = max_chars - overlap
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(Chunk(doc.path, doc.kind, idx, text[start:end]))
        idx += 1
        if end == len(text):
            break
        start += step
    return chunks


def _chunk_markdown(doc: Document, max_chars: int, overlap: int) -> list[Chunk]:
    sections = _split_markdown_by_headings(doc.text)
    chunks: list[Chunk] = []
    idx = 0
    for section in sections:
        if len(section) <= max_chars:
            chunks.append(Chunk(doc.path, doc.kind, idx, section))
            idx += 1
            continue
        sub = _chunk_sliding(Document(doc.path, doc.kind, section), max_chars, overlap)
        for c in sub:
            chunks.append(Chunk(doc.path, doc.kind, idx, c.text))
            idx += 1
    return chunks


def _split_markdown_by_headings(text: str) -> list[str]:
    lines = text.splitlines(keepends=True)
    sections: list[str] = []
    buf: list[str] = []
    for line in lines:
        if line.startswith("#") and buf:
            sections.append("".join(buf))
            buf = [line]
        else:
            buf.append(line)
    if buf:
        sections.append("".join(buf))
    return sections or [text]


def ingest_path(root: Path) -> tuple[list[Document], list[Chunk]]:
    docs: list[Document] = []
    chunks: list[Chunk] = []
    for path in discover(root):
        doc = load(path, root=root)
        docs.append(doc)
        chunks.extend(chunk(doc))
    return docs, chunks
