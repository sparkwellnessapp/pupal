"""
Ground-truth format + parser for the transcription eval suite.

Canonical segmented format — one unambiguous delimiter per answer, mapping
directly to the pipeline's (question_number, sub_question_id) answer shape:

    === Q1.א ===
    public class Hobby
    { ... }

    === Q1.ב ===
    public class SchoolHobbies
    { ... }

    === Q3 ===          # no sub-question
    ...

Rules enforced by this format (and the converter that produces it):
    - One "=== Q{n}[.{sub}] ===" delimiter per answer.
    - Everything between delimiters is the answer body, VERBATIM (student bugs,
      typos, abbreviations like CW/CR, capitalization like While/For preserved).
    - Hebrew section headers ("שאלה 1", "סעיף א", "א.") never appear inside bodies.
    - Illegible source is marked "[?]" (one shared vocabulary with model output).
    - Crossed-out source is dropped (we transcribe visible ink only).

This module is pure (parse + load). The only I/O is `load_ground_truth` reading
a file from disk; the parser itself is a pure function over a string.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# (question_number, sub_question_id|None) — the join key shared with predictions.
Key = tuple[int, str | None]

# Matches a delimiter line:  === Q12 ===  or  === Q1.א ===  or  === Q2.ii ===
# sub-id is any run of non-space, non-'=' characters (Hebrew letters included).
_DELIM_RE = re.compile(r"^===\s*Q(\d+)(?:\.([^\s=]+))?\s*===\s*$", re.MULTILINE)


@dataclass(frozen=True)
class GoldAnswer:
    question_number: int
    sub_question_id: str | None
    answer_text: str  # verbatim body (whitespace/bugs preserved; normalize at score time)

    @property
    def key(self) -> Key:
        return (self.question_number, self.sub_question_id)


@dataclass(frozen=True)
class GoldDocument:
    doc_id: str
    answers: tuple[GoldAnswer, ...]

    def as_dict(self) -> dict[Key, str]:
        return {a.key: a.answer_text for a in self.answers}

    def keys_in_order(self) -> list[Key]:
        return [a.key for a in self.answers]


def _strip_blank_edges(body: str) -> str:
    """Drop leading/trailing blank lines but keep internal formatting intact."""
    return body.strip("\n")


def parse_ground_truth(text: str, *, doc_id: str) -> GoldDocument:
    """Parse a canonical ground-truth string into a GoldDocument. Pure.

    Raises:
        ValueError: if no answers are found, or if a (question, sub) key repeats.
    """
    matches = list(_DELIM_RE.finditer(text))
    if not matches:
        raise ValueError(
            f"{doc_id}: no '=== Q.. ===' delimiters found — not canonical format."
        )

    answers: list[GoldAnswer] = []
    seen: set[Key] = set()
    for i, m in enumerate(matches):
        q_num = int(m.group(1))
        sub_id = m.group(2)  # None when absent
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = _strip_blank_edges(text[body_start:body_end])

        key: Key = (q_num, sub_id)
        if key in seen:
            raise ValueError(
                f"{doc_id}: duplicate answer key Q{q_num}"
                + (f".{sub_id}" if sub_id else "")
                + " — each (question, sub-question) may appear once."
            )
        seen.add(key)
        answers.append(GoldAnswer(q_num, sub_id, body))

    return GoldDocument(doc_id=doc_id, answers=tuple(answers))


def load_ground_truth(path: str | Path) -> GoldDocument:
    """Read a canonical ground-truth markdown file and parse it.

    doc_id is the filename stem (e.g. 'moran_aharon').
    """
    p = Path(path)
    return parse_ground_truth(p.read_text(encoding="utf-8"), doc_id=p.stem)


# ---------------------------------------------------------------------------
# Phase-1 (raw / per-page) ground truth
# ---------------------------------------------------------------------------
#
# Phase 1 transcribes VERBATIM, page by page. Its ground truth therefore:
#   - is delimited by "=== PAGE 1 ===" markers, one per physical page;
#   - INCLUDES the student's section headers ("שאלה 1", "א.") — they are ink
#     on the page, and verbatim means verbatim (unlike the per-question
#     format, which excludes headers from answer bodies);
#   - uses "[?]" for illegible ink, drops crossed-out ink (same canonical
#     vocabulary as the per-question format);
#   - writes circled question digits as "שאלה {n}" (authoring convention).

_PAGE_DELIM_RE = re.compile(r"^===\s*PAGE\s+(\d+)\s*===\s*$", re.MULTILINE | re.IGNORECASE)


@dataclass(frozen=True)
class GoldPage:
    page_number: int
    text: str  # verbatim page ink (headers included; normalize at score time)


@dataclass(frozen=True)
class GoldPageDocument:
    doc_id: str
    pages: tuple[GoldPage, ...]

    def as_dict(self) -> dict[int, str]:
        return {p.page_number: p.text for p in self.pages}


def parse_page_ground_truth(text: str, *, doc_id: str) -> GoldPageDocument:
    """Parse a canonical per-page ground-truth string. Pure.

    Raises:
        ValueError: if no pages found, a page number repeats, or numbering
        is not contiguous from 1 (a gap usually means an authoring typo).
    """
    matches = list(_PAGE_DELIM_RE.finditer(text))
    if not matches:
        raise ValueError(
            f"{doc_id}: no '=== PAGE n ===' delimiters found — not canonical raw format."
        )

    pages: list[GoldPage] = []
    seen: set[int] = set()
    for i, m in enumerate(matches):
        n = int(m.group(1))
        if n in seen:
            raise ValueError(f"{doc_id}: duplicate page {n}.")
        seen.add(n)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append(GoldPage(n, _strip_blank_edges(text[body_start:body_end])))

    expected = set(range(1, len(pages) + 1))
    if seen != expected:
        raise ValueError(
            f"{doc_id}: page numbers {sorted(seen)} are not contiguous 1..{len(pages)}."
        )

    pages.sort(key=lambda p: p.page_number)
    return GoldPageDocument(doc_id=doc_id, pages=tuple(pages))


def load_page_ground_truth(path: str | Path) -> GoldPageDocument:
    p = Path(path)
    return parse_page_ground_truth(p.read_text(encoding="utf-8"), doc_id=p.stem)
