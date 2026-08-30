"""
Shared api-layer write guards (batch-redesign spec v2, item B2).

One concept, one place: the full-snapshot answer-key-multiset rule guards BOTH
the review-overlay save (PATCH /transcriptions/{id}/review) and the batch
accept_one approval. The approval write — the higher-stakes path, it freezes a
TranscriptionContract — must never validate less than the overlay save
(census Q14). Both call sites import this function and this detail constant;
copying either is a regression.
"""
from __future__ import annotations

from typing import Iterable

from fastapi import HTTPException

from ..schemas.transcription import TranscriptionDraft

ANSWER_KEY_MISMATCH_DETAIL = (
    "התשובות שנשלחו אינן תואמות את מבנה התמלול — נדרשת שמירה של כל התשובות"
)


def ensure_answer_keys_match_draft(draft: TranscriptionDraft, answers: Iterable) -> None:
    """422 unless the answers' (question_number, sub_question_id) key multiset
    exactly equals the draft's. Never normalizes/fills/prunes silently.

    sub_question_id normalization: None ≡ "" — the PATCH's historical mapping
    (`or ""`); B2 requires the two call sites to be byte-identical.
    """
    draft_keys = sorted((a.question_number, a.sub_question_id or "") for a in draft.answers)
    body_keys = sorted((a.question_number, a.sub_question_id or "") for a in answers)
    if draft_keys != body_keys:
        raise HTTPException(status_code=422, detail=ANSWER_KEY_MISMATCH_DETAIL)
