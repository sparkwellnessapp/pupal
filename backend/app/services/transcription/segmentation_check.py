"""
segmentation_check — deterministic marker↔key mismatch detection (2026-08-07).

P1's verbatim contract preserves the student's own section markers inside each
answer's text ("שאלה 5", "א) 3", "3 (א", "ב)"). P2 assigns each block a spec
key — and nano sometimes renumbers answered questions sequentially when the
student skipped one, overriding both the content signatures and the student's
markers (observed live: a student skipped Q2 and every later block landed one
question early; DiceStatistics sat at q2.א while its own first line said
"א) 3"). The assigned key is the GRADING route, so a mislabel grades the
answer against the wrong rubric question.

This module is the pure, precision-biased detector: parse the LEADING lines of
an answer for a self-declared marker and report a mismatch only when a declared
question DIGIT contradicts the assigned key. It never remaps anything — the
result becomes a WARNING annotation + a proposed swap the teacher confirms
(FC: capture the error, propose the fix, teacher decides).

Grammar rules (deliberately conservative — when unsure, no claim):
  * only the first two non-empty lines are examined, stopping at the first
    line that is not a marker line — a trace-table or code first line means
    the answer makes no claim;
  * a marker line must FULL-match one of the known shapes and be short
    (≤ _MAX_MARKER_LEN chars), so digits inside code can never match;
  * sub-letter-only markers ("ב)") never fire a mismatch on their own.

The frontend mirrors this grammar in src/utils/segmentation-check.ts for LIVE
recomputation while the teacher moves text between containers. The two
implementations are cross-pinned by tests sharing the same fixture strings —
if you change a rule here, change it there and in both test files.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

# Hebrew ordinals א..י — the same vocabulary keys.normalize_key speaks.
_HEB = "אבגדהוזחטי"
_MAX_MARKER_LEN = 12

# "שאלה 5" / "שאלה 5:" / "שאלה 5."
_Q_WORD = re.compile(r"^שאלה\s*(\d{1,2})\s*[:.]?$")
# "א) 3" — letter, paren, digit (the shape P1 emitted for this student)
_LETTER_PAREN_DIGIT = re.compile(rf"^([{_HEB}])\)\s*(\d{{1,2}})$")
# "3 (א" — digit, paren, letter
_DIGIT_PAREN_LETTER = re.compile(rf"^(\d{{1,2}})\s*\(\s*([{_HEB}])$")
# "א)" / "א." / "ב:" — sub-section marker alone
_SUB_ONLY = re.compile(rf"^([{_HEB}])\s*[).:]$")


@dataclass(frozen=True)
class DeclaredMarker:
    """What the student's leading ink claims this block is."""
    question: Optional[int] = None
    sub: Optional[str] = None


@dataclass(frozen=True)
class Mismatch:
    """An answer whose declared question digit contradicts its assigned key."""
    question_number: int                 # assigned (the grading route)
    sub_question_id: Optional[str]
    declared_question: int               # what the ink says
    # Existing draft key to swap with, or None when no reasonable target
    # exists: (declared_q, same sub) → (declared_q, declared sub) → bare
    # (declared_q, None) — first that exists in the draft's key set.
    proposed_target: Optional[tuple[int, Optional[str]]]


def _parse_marker_line(line: str) -> Optional[DeclaredMarker]:
    """One line → its marker claim, or None if the line is not a marker."""
    s = line.strip()
    if not s or len(s) > _MAX_MARKER_LEN:
        return None
    m = _Q_WORD.match(s)
    if m:
        return DeclaredMarker(question=int(m.group(1)))
    m = _LETTER_PAREN_DIGIT.match(s)
    if m:
        return DeclaredMarker(question=int(m.group(2)), sub=m.group(1))
    m = _DIGIT_PAREN_LETTER.match(s)
    if m:
        return DeclaredMarker(question=int(m.group(1)), sub=m.group(2))
    m = _SUB_ONLY.match(s)
    if m:
        return DeclaredMarker(sub=m.group(1))
    return None


def parse_leading_marker(text: str) -> DeclaredMarker:
    """
    The block's self-declared identity from its leading lines.

    Scans up to the first two non-empty lines, stopping at the first
    non-marker line ("שאלה 5" then "א." composes; "if:" claims nothing).
    First finding wins per field.
    """
    question: Optional[int] = None
    sub: Optional[str] = None
    seen = 0
    for line in text.split("\n"):
        if not line.strip():
            continue
        marker = _parse_marker_line(line)
        if marker is None:
            break
        question = question if question is not None else marker.question
        sub = sub if sub is not None else marker.sub
        seen += 1
        if seen >= 2:
            break
    return DeclaredMarker(question=question, sub=sub)


def detect_mismatches(
    answers: list[tuple[int, Optional[str], str]],
) -> list[Mismatch]:
    """
    All marker↔key mismatches in a draft's answer set.

    `answers` is (question_number, sub_question_id, answer_text) per answer —
    the full set, because proposal resolution needs the existing keys.
    """
    keys = {(q, sub) for q, sub, _ in answers}
    out: list[Mismatch] = []
    for q, sub, text in answers:
        marker = parse_leading_marker(text)
        if marker.question is None or marker.question == q:
            continue
        proposed: Optional[tuple[int, Optional[str]]] = None
        for candidate in (
            (marker.question, sub),
            (marker.question, marker.sub),
            (marker.question, None),
        ):
            if candidate in keys and candidate != (q, sub):
                proposed = candidate
                break
        out.append(Mismatch(
            question_number=q,
            sub_question_id=sub,
            declared_question=marker.question,
            proposed_target=proposed,
        ))
    return out
