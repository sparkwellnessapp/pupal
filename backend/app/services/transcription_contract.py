"""The ONE builder of a `TranscriptionContract` (MATH_RENDERING_PLAN §7 Phase 2, ALPHA-GAP A-4).

Three approval paths freeze a transcription — `/grade`, the batch `accept_one`, and
`accept_clean` — and each used to construct the contract inline. They now call this, so the
contract's shape is decided in one place (§0.4) and a field added here reaches all three.

PAGE PROVENANCE travels into the contract. A frozen answer carries the pages it was read
from, so every downstream surface can show the ink behind it — and, in Phase 3, a figure can
reach its page. The pages come from the DRAFT (P1's deterministic attribution), matched by
EVIDENCE, never guessed:

  1. the accepted text equals a draft answer's text → that answer's pages. This follows the
     content through a SWAP (reassignment moves content between keys; its page chips travel
     with the content on screen, but the overlay never persisted them).
  2. otherwise (she edited the text) → the pages of the same key in the draft: an edit fixes
     words; it does not move the answer to another page.
  3. no draft answer for that key → no pages. An empty list is a recorded absence, never a
     guess (the VER-3 precedent).

FIGURES (plan §5) travel the same way. Her reviewed readings, when the request carries them,
are authoritative (`figures` not None); otherwise the draft's readings follow the content by
the same evidence as the pages. Then FIG-1 holds by construction: only a figure whose
`[איור N: …]` line is still in the text she approved is frozen. A figure whose line she
deleted goes with the line — her edit removed the drawing's reference, and the reading of it
follows her decision; it is never re-attached to some other line.
"""
from __future__ import annotations

from typing import Iterable, Optional, Protocol

from app.schemas.transcription import (
    TranscriptionContract,
    TranscriptionContractAnswer,
    TranscriptionDraft,
)
from app.services.figures import match_figures


class _AcceptedAnswer(Protocol):
    question_number: int
    sub_question_id: Optional[str]
    answer_text: str


def build_transcription_contract(
    answers: Iterable[_AcceptedAnswer],
    draft: Optional[TranscriptionDraft],
) -> TranscriptionContract:
    by_key: dict = {}
    by_text: dict = {}
    for d in (draft.answers if draft else []):
        evidence = (list(d.page_numbers), list(d.figures))
        by_key[(d.question_number, d.sub_question_id)] = (d.answer_text, evidence)
        if d.answer_text.strip():
            # First writer wins: two answers with the same text (blanks excluded) cannot be
            # told apart by content, so the key rule decides for the rest.
            by_text.setdefault(d.answer_text, evidence)

    frozen = []
    for a in answers:
        key = (a.question_number, a.sub_question_id)
        own_text, own = by_key.get(key, (None, ([], [])))
        if a.answer_text == own_text:
            pages, figures = own                                # untouched
        elif a.answer_text.strip() and a.answer_text in by_text:
            pages, figures = by_text[a.answer_text]             # moved here by a SWAP
        else:
            pages, figures = own                                # edited in place, or absent
        reviewed = getattr(a, "figures", None)
        if reviewed is not None:
            figures = list(reviewed)                            # her decision, all of it
        kept = [fig for _, fig in match_figures(a.answer_text, figures).pairs]
        frozen.append(TranscriptionContractAnswer(
            question_number=a.question_number,
            sub_question_id=a.sub_question_id,
            answer_text=a.answer_text,
            page_numbers=sorted(set(pages)),
            figures=kept,
        ))
    return TranscriptionContract(answers=frozen)
