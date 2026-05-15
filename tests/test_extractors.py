import io
import mailbox
from email.message import EmailMessage
from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")
pytest.importorskip("docx")

from docx import Document as DocxDocument  # noqa: E402

from kgent.extractors import (  # noqa: E402
    extract_attachment,
    extract_docx,
    extract_pdf,
    iter_mbox,
    parse_email,
)
from kgent.ingest import extract_documents, ingest_path  # noqa: E402


def _make_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_docx(text: str) -> bytes:
    doc = DocxDocument()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_pdf_returns_text():
    text = extract_pdf(_make_pdf("Hello from a PDF document"))
    assert "Hello from a PDF document" in text


def test_extract_docx_returns_text():
    text = extract_docx(_make_docx("Hello from a Word document"))
    assert "Hello from a Word document" in text


def test_extract_attachment_dispatches_by_suffix():
    assert "PDF body" in (extract_attachment("a.pdf", _make_pdf("PDF body")) or "")
    assert extract_attachment("notes.txt", b"plain notes") == "plain notes"
    assert extract_attachment("archive.zip", b"\x00") is None


def test_parse_email_extracts_headers_body_and_attachment():
    msg = EmailMessage()
    msg["Subject"] = "Quarterly report"
    msg["From"] = "alice@example.com"
    msg["To"] = "bob@example.com"
    msg.set_content("Please find the report attached.")
    msg.add_attachment(
        _make_pdf("Revenue grew this quarter"),
        maintype="application",
        subtype="pdf",
        filename="report.pdf",
    )
    content = parse_email(msg.as_bytes())
    assert "Quarterly report" in content.text
    assert "Please find the report attached." in content.text
    assert len(content.attachments) == 1
    name, data = content.attachments[0]
    assert name == "report.pdf"
    assert "Revenue grew this quarter" in extract_pdf(data)


def test_iter_mbox_yields_one_content_per_message(tmp_path: Path):
    mbox_path = tmp_path / "inbox.mbox"
    box = mailbox.mbox(str(mbox_path))
    box.lock()
    for i in range(3):
        msg = EmailMessage()
        msg["Subject"] = f"Message {i}"
        msg["From"] = "sender@example.com"
        msg.set_content(f"Body of message number {i}")
        box.add(msg)
    box.flush()
    box.unlock()
    box.close()

    contents = list(iter_mbox(mbox_path))
    assert len(contents) == 3
    assert "Body of message number 1" in contents[1].text


def test_extract_documents_handles_pdf(tmp_path: Path):
    pdf = tmp_path / "guide.pdf"
    pdf.write_bytes(_make_pdf("Indexed PDF content"))
    docs = extract_documents(pdf, root=tmp_path)
    assert len(docs) == 1
    assert docs[0].kind == "pdf"
    assert "Indexed PDF content" in docs[0].text


def test_extract_documents_splits_email_and_attachment(tmp_path: Path):
    msg = EmailMessage()
    msg["Subject"] = "With attachment"
    msg.set_content("See attached document.")
    msg.add_attachment(
        _make_docx("Attached Word content"),
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="memo.docx",
    )
    eml = tmp_path / "mail.eml"
    eml.write_bytes(msg.as_bytes())
    docs = extract_documents(eml, root=tmp_path)
    assert sorted(d.kind for d in docs) == ["attachment", "email"]
    attachment = next(d for d in docs if d.kind == "attachment")
    assert "Attached Word content" in attachment.text


def test_ingest_path_indexes_pdf_and_email(tmp_path: Path):
    (tmp_path / "doc.pdf").write_bytes(_make_pdf("Searchable PDF text"))
    msg = EmailMessage()
    msg["Subject"] = "Plain mail"
    msg.set_content("A short email body.")
    (tmp_path / "note.eml").write_bytes(msg.as_bytes())
    (tmp_path / "readme.md").write_text("# Readme\nProject notes.", encoding="utf-8")

    docs, chunks = ingest_path(tmp_path)
    kinds = {d.kind for d in docs}
    assert {"pdf", "email", "markdown"}.issubset(kinds)
    assert len(chunks) >= 3
