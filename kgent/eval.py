"""Retrieval quality evaluation against a labelled dataset.

A dataset is a JSONL file where each line is a case:

    {"question": "How is the graph built?", "relevant": ["graph.py"]}

`relevant` lists substrings expected to appear in the `doc_path` of a
retrieved chunk. Lines that are empty or start with `#` are ignored.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .retriever import retrieve
from .store import VectorStore


@dataclass
class EvalCase:
    question: str
    relevant: list[str]


@dataclass
class CaseResult:
    question: str
    hit: bool
    reciprocal_rank: float
    recall: float
    precision: float
    retrieved: list[str]


@dataclass
class EvalReport:
    k: int
    cases: list[CaseResult]

    @property
    def n(self) -> int:
        return len(self.cases)

    @property
    def hit_rate(self) -> float:
        return _mean([1.0 if c.hit else 0.0 for c in self.cases])

    @property
    def mrr(self) -> float:
        return _mean([c.reciprocal_rank for c in self.cases])

    @property
    def recall(self) -> float:
        return _mean([c.recall for c in self.cases])

    @property
    def precision(self) -> float:
        return _mean([c.precision for c in self.cases])


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: invalid JSON ({exc})") from exc
        question = str(data.get("question", "")).strip()
        relevant = data.get("relevant") or data.get("relevant_docs") or []
        if not question or not relevant:
            raise ValueError(
                f"{path}:{line_no}: each case needs a 'question' and a non-empty 'relevant'"
            )
        cases.append(EvalCase(question=question, relevant=[str(r) for r in relevant]))
    return cases


def evaluate_case(store: VectorStore, case: EvalCase, k: int) -> CaseResult:
    retrieved = [c.doc_path for c in retrieve(store, case.question, k=k)]

    first_rank = 0
    for rank, path in enumerate(retrieved, start=1):
        if _matches(path, case.relevant):
            first_rank = rank
            break

    relevant_hits = sum(1 for p in retrieved if _matches(p, case.relevant))
    found = {r for r in case.relevant if any(r in p for p in retrieved)}

    return CaseResult(
        question=case.question,
        hit=first_rank > 0,
        reciprocal_rank=1.0 / first_rank if first_rank else 0.0,
        recall=len(found) / len(case.relevant),
        precision=relevant_hits / len(retrieved) if retrieved else 0.0,
        retrieved=retrieved,
    )


def evaluate(store: VectorStore, cases: list[EvalCase], k: int = 5) -> EvalReport:
    return EvalReport(k=k, cases=[evaluate_case(store, case, k) for case in cases])


def _matches(doc_path: str, relevant: list[str]) -> bool:
    return any(r in doc_path for r in relevant)


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0
