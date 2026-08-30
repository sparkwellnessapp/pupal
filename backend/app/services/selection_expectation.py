"""
selection_expectation — "choose k of N" awareness for transcription review.

The P2 segmentation deliberately emits an answer entry for EVERY rubric
target (empty when unanswered) because the review/accept machinery is built
on a frozen answer-key multiset. On a selection exam ("answer 4 of 6") that
is correct data but a false diagnostic: an unchosen question is not a
"missing answer", and its empty container is noise the teacher must ignore.

This module is the ONE rule both sides consume (owner-ruled 2026-08-12):

  * `answer_space_groups(contract)` translates the contract's
    `selection_groups` (member ids 'q5', 'q6') into the `question_number`
    ints transcription answers carry — using the SAME id→number rule the
    gradable compiler uses (`_q_num`: 'qN' → N, else array position + 1),
    so review expectation and grading alignment can never disagree.

  * `expected_empty_keys(answers, groups)`: a group member is ATTEMPTED iff
    at least one of its answers has non-empty text. When a group has
    ≥ choose_k attempted members, every answer key of its UNATTEMPTED
    members is "expected empty" — not missing, not rendered as a gap.
    An under-answered group (attempted < choose_k) suppresses NOTHING:
    those empties are genuinely reviewable. Empty answers WITHIN an
    attempted member are also never suppressed (the student chose the
    question and skipped a part — a real gap).

Consumers: batch triage (`missing_answers`), the batch detail payload, the
/transcribe response, and (via the cross-pinned TS mirror
`frontend/src/utils/selection-expectation.ts` + the shared fixture
`tests/fixtures/selection_expectation_cases.json`) both review surfaces,
which recompute live against edited text. Pure, no I/O.

Caveat: groups are derived from the rubric's CURRENT contract. If a rubric
was recompiled after transcription the numbering can drift, but suppression
only ever hides EMPTY answers inside a satisfied group — a drifted group at
worst suppresses nothing.
"""
from __future__ import annotations

from typing import Iterable, Optional

from ..schemas.ontology_types import GradingRubricContract
from ..schemas.transcription import AnswerSpaceSelectionGroup
from .gradable_compiler import _q_num

AnswerKey = tuple[int, Optional[str]]


def answer_space_groups(
    contract_json: dict | None,
) -> list[AnswerSpaceSelectionGroup]:
    """Selection groups of a rubric contract, in transcription-answer space.

    Accepts the raw `rubrics.contract_json` (validated here — it was written
    by the compiler, so validation failing is a loud bug, not a case to
    paper over). Returns [] for a missing contract or a selection-free
    rubric, which makes every consumer reduce exactly to today's behavior.
    Dangling member ids are dropped (structural validation owns surfacing
    them; a dropped member can only make suppression rarer, never wronger).
    """
    if not contract_json:
        return []
    contract = GradingRubricContract.model_validate(contract_json)
    if not contract.selection_groups:
        return []

    num_by_id = {
        q.question_id: _q_num(q.question_id, i)
        for i, q in enumerate(contract.questions)
    }
    groups: list[AnswerSpaceSelectionGroup] = []
    for g in contract.selection_groups:
        numbers = sorted(
            num_by_id[qid] for qid in g.of_question_ids if qid in num_by_id
        )
        if numbers:
            groups.append(AnswerSpaceSelectionGroup(
                choose_k=g.choose_k, question_numbers=numbers,
            ))
    return groups


def expected_empty_keys(
    answers: Iterable[tuple[int, Optional[str], str]],
    groups: Iterable[AnswerSpaceSelectionGroup],
) -> set[AnswerKey]:
    """Answer keys whose emptiness the selection rules fully explain.

    `answers` is (question_number, sub_question_id, current_text) — callers
    pass draft text (triage) or live edited text (review surfaces).
    """
    keys_by_question: dict[int, list[AnswerKey]] = {}
    attempted_questions: set[int] = set()
    for q_num, sub_id, text in answers:
        keys_by_question.setdefault(q_num, []).append((q_num, sub_id))
        if text.strip():
            attempted_questions.add(q_num)

    expected_empty: set[AnswerKey] = set()
    for g in groups:
        attempted = [n for n in g.question_numbers if n in attempted_questions]
        if len(attempted) < g.choose_k:
            continue  # under-answered group: every empty stays reviewable
        for n in g.question_numbers:
            if n not in attempted_questions:
                expected_empty.update(keys_by_question.get(n, []))
    return expected_empty
