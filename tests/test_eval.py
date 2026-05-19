from pathlib import Path

import pytest

from kgent.eval import evaluate, load_cases
from kgent.ingest import Chunk
from kgent.store import JsonStore


def _make_store(tmp_path: Path) -> JsonStore:
    store = JsonStore(tmp_path / "index.json")
    store.add(
        [
            Chunk("graph.md", "markdown", 0, "the cooccurrence graph links capitalized terms"),
            Chunk("ingest.md", "markdown", 0, "ingestion reads pdf word and email files"),
            Chunk("other.md", "markdown", 0, "completely unrelated placeholder content"),
        ]
    )
    return store


def test_load_cases_skips_comments_and_blank_lines(tmp_path: Path):
    dataset = tmp_path / "eval.jsonl"
    dataset.write_text(
        "# a comment\n"
        "\n"
        '{"question": "what graph?", "relevant": ["graph.md"]}\n'
        '{"question": "what ingest?", "relevant": ["ingest.md"]}\n',
        encoding="utf-8",
    )
    cases = load_cases(dataset)
    assert len(cases) == 2
    assert cases[0].question == "what graph?"
    assert cases[0].relevant == ["graph.md"]


def test_load_cases_rejects_a_case_without_relevant(tmp_path: Path):
    dataset = tmp_path / "bad.jsonl"
    dataset.write_text('{"question": "no labels here"}\n', encoding="utf-8")
    with pytest.raises(ValueError):
        load_cases(dataset)


def test_evaluate_scores_a_hit_and_a_miss(tmp_path: Path):
    store = _make_store(tmp_path)
    cases = load_cases_inline(
        tmp_path,
        [
            ("cooccurrence graph capitalized terms", ["graph.md"]),
            ("unrelated placeholder content", ["graph.md"]),
        ],
    )
    report = evaluate(store, cases, k=1)

    assert report.n == 2
    assert report.cases[0].hit is True
    assert report.cases[0].reciprocal_rank == 1.0
    assert report.cases[1].hit is False
    assert report.hit_rate == 0.5
    assert report.mrr == 0.5


def load_cases_inline(tmp_path: Path, rows: list[tuple[str, list[str]]]):
    import json

    dataset = tmp_path / "inline.jsonl"
    dataset.write_text(
        "\n".join(json.dumps({"question": q, "relevant": r}) for q, r in rows),
        encoding="utf-8",
    )
    return load_cases(dataset)
