"""build_transcription_contract — the one builder of a frozen transcription (A-4). Pure."""
from __future__ import annotations

from types import SimpleNamespace as A

from app.schemas.transcription import TranscriptionContract, TranscriptionDraft, TranscriptionDraftAnswer
from app.services.transcription_contract import build_transcription_contract


def _draft(*answers):
    return TranscriptionDraft(page_count=4, answers=[
        TranscriptionDraftAnswer(question_number=q, sub_question_id=s, answer_text=t,
                                 confidence=0.9, page_numbers=p)
        for q, s, t, p in answers])


DRAFT = _draft((1, "א", "\\(x=2\\)", [1]), (1, "ב", "\\(y=3\\)", [2, 3]), (2, None, "", []))


def _pages(contract):
    return {(a.question_number, a.sub_question_id): a.page_numbers for a in contract.answers}


def test_untouched_answers_carry_their_pages():
    c = build_transcription_contract(DRAFT.answers, DRAFT)
    assert _pages(c) == {(1, "א"): [1], (1, "ב"): [2, 3], (2, None): []}


def test_an_edited_answer_keeps_its_own_pages():
    c = build_transcription_contract(
        [A(question_number=1, sub_question_id="א", answer_text="\\(x=4\\)")], DRAFT)
    assert _pages(c) == {(1, "א"): [1]}


def test_pages_follow_the_content_through_a_swap():
    swapped = [A(question_number=1, sub_question_id="א", answer_text="\\(y=3\\)"),
               A(question_number=1, sub_question_id="ב", answer_text="\\(x=2\\)")]
    c = build_transcription_contract(swapped, DRAFT)
    assert _pages(c) == {(1, "א"): [2, 3], (1, "ב"): [1]}


def test_a_key_the_draft_never_had_records_no_pages():
    c = build_transcription_contract([A(question_number=9, sub_question_id=None, answer_text="x")], DRAFT)
    assert _pages(c) == {(9, None): []}


def test_text_is_frozen_verbatim():
    c = build_transcription_contract(DRAFT.answers, DRAFT)
    assert [a.answer_text for a in c.answers] == [a.answer_text for a in DRAFT.answers]


def test_a_contract_frozen_before_the_field_still_parses():
    old = {"schema_version": "1.0", "contract_version": "c1",
           "answers": [{"question_number": 1, "sub_question_id": None, "answer_text": "x"}]}
    assert TranscriptionContract.model_validate(old).answers[0].page_numbers == []
