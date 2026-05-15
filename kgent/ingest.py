from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

from . import extractors
from .logging_config import get_logger

log = get_logger(__name__)

# Plain text formats: read directly, subject to the size and minified guards.
TEXT_EXTENSIONS = {
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

# Binary document formats: extracted through kgent.extractors.
DOC_EXTENSIONS = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".eml": "email",
    ".mbox": "email",
}

SUPPORTED_EXTENSIONS = {**TEXT_EXTENSIONS, **DOC_EXTENSIONS}
_TEXT_KINDS = set(TEXT_EXTENSIONS.values())


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


# Text files larger than this are skipped: likely data dumps, bundles, or
# minified assets that would explode into thousands of low value chunks.
MAX_FILE_BYTES = 1_000_000

# Binary documents (PDF, Word, mbox) may be much larger; a mailbox export in
# particular is routinely tens of megabytes.
MAX_DOC_BYTES = 200_000_000

# A single line longer than this strongly suggests a minified or generated file.
_MINIFIED_LINE_LEN = 5000


def looks_minified(text: str) -> bool:
    """Return True when the text looks like a minified or generated file.

    The heuristic is the longest line: hand written source keeps lines short,
    bundlers and minifiers pack everything onto one very long line.
    """
    longest = 0
    for line in text.splitlines():
        if len(line) > longest:
            longest = len(line)
            if longest > _MINIFIED_LINE_LEN:
                return True
    return False


def _read_gitignore(root: Path) -> set[str]:
    """Collect plain name patterns from a .gitignore at the repository root.

    Only simple unanchored names are honoured (for example ``build`` or
    ``*.log``). Nested path patterns and negations are left out of scope.
    """
    gitignore = root / ".gitignore"
    if not gitignore.is_file():
        return set()
    patterns: set[str] = set()
    try:
        lines = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("!"):
            continue
        line = line.strip("/")
        if not line or "/" in line:
            continue
        patterns.add(line)
    return patterns


def discover(root: Path, ignore: Iterable[str] = ()) -> Iterator[Path]:
    import fnmatch
    import os

    ignore_set = set(_NOISE_DIRS)
    ignore_set.update(ignore)
    gitignore = _read_gitignore(root)

    def _ignored(name: str) -> bool:
        if name in ignore_set or name.endswith(".egg-info"):
            return True
        return any(fnmatch.fnmatch(name, pat) for pat in gitignore)

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in place so os.walk never descends into
        # them (avoids stat'ing thousands of .venv or node_modules files).
        dirnames[:] = [d for d in dirnames if not _ignored(d)]
        for name in filenames:
            if name.lower() in _NOISE_FILENAMES or _ignored(name):
                continue
            suffix = Path(name).suffix.lower()
            if suffix not in SUPPORTED_EXTENSIONS:
                continue
            path = Path(dirpath) / name
            limit = MAX_FILE_BYTES if suffix in TEXT_EXTENSIONS else MAX_DOC_BYTES
            try:
                if path.stat().st_size > limit:
                    continue
            except OSError:
                continue
            yield path


def load(path: Path, root: Path | None = None) -> Document:
    """Load a plain text file into a Document."""
    rel = str(path.relative_to(root)) if root else str(path)
    return Document(
        path=rel,
        kind=TEXT_EXTENSIONS[path.suffix.lower()],
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


def extract_documents(path: Path, root: Path | None = None) -> list[Document]:
    """Load one file into one or more Documents, dispatching on file type.

    A text, PDF, or Word file yields a single Document. An email yields its
    body plus one Document per readable attachment, and an mbox export yields
    that for every message it contains.
    """
    suffix = path.suffix.lower()
    rel = str(path.relative_to(root)) if root else str(path)

    if suffix in TEXT_EXTENSIONS:
        return [load(path, root=root)]

    if suffix == ".pdf":
        text = extractors.extract_pdf(path.read_bytes())
        return [Document(path=rel, kind="pdf", text=text)] if text else []

    if suffix == ".docx":
        text = extractors.extract_docx(path.read_bytes())
        return [Document(path=rel, kind="docx", text=text)] if text else []

    if suffix == ".eml":
        return _email_documents(extractors.parse_email(path.read_bytes()), rel)

    if suffix == ".mbox":
        docs: list[Document] = []
        for i, content in enumerate(extractors.iter_mbox(path)):
            docs.extend(_email_documents(content, f"{rel}#mail{i}"))
        return docs

    return []


def _email_documents(content: extractors.EmailContent, base_path: str) -> list[Document]:
    docs: list[Document] = []
    if content.text:
        docs.append(Document(path=base_path, kind="email", text=content.text))
    for name, data in content.attachments:
        try:
            extracted = extractors.extract_attachment(name, data)
        except Exception:
            log.warning("could not read attachment %s in %s", name, base_path)
            continue
        if extracted:
            docs.append(
                Document(path=f"{base_path}::{name}", kind="attachment", text=extracted)
            )
    return docs


# Called once per file scanned, with (processed, total, documents, chunks).
ProgressFn = Callable[[int, int, int, int], None]


def ingest_path(
    root: Path, on_progress: ProgressFn | None = None
) -> tuple[list[Document], list[Chunk]]:
    docs: list[Document] = []
    chunks: list[Chunk] = []
    paths = list(discover(root))
    total = len(paths)
    for i, path in enumerate(paths, start=1):
        try:
            extracted = extract_documents(path, root=root)
        except Exception:
            log.warning("could not read %s, skipping", path, exc_info=True)
            extracted = []
        for doc in extracted:
            if doc.kind in _TEXT_KINDS and looks_minified(doc.text):
                continue
            docs.append(doc)
            chunks.extend(chunk(doc))
        if on_progress is not None:
            on_progress(i, total, len(docs), len(chunks))
    return docs, chunks
