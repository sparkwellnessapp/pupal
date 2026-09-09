"""
S11 batch triage — flag-verdict aggregation and student auto-matching.

compute_flag_verdict()  → review_needed bool + reasons list
match_student()         → exact normalized match against a class roster (or None)

Thresholds are config constants (tunable; E2 will calibrate them from real
teacher corrections). The flag reasons are string literals so the frontend
can render localized labels without a lookup table.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..schemas.transcription import AnswerSpaceSelectionGroup, TranscriptionDraft
from .selection_expectation import expected_empty_keys


# ---------------------------------------------------------------------------
# Student name normalization
# ---------------------------------------------------------------------------

def _normalize_name(name: str) -> str:
    """
    Casefold + strip leading/trailing whitespace + strip Hebrew niqqud
    (cantillation marks U+0591–U+05C7 in Unicode block Hebrew).
    Normalizes to NFC first to handle pre-composed vs. combining forms.
    """
    name = unicodedata.normalize("NFC", name).casefold().strip()
    # Strip any character in the Hebrew cantillation/vowel range
    return "".join(c for c in name if not ("֑" <= c <= "ׇ"))


# ---------------------------------------------------------------------------
# Student matching
# ---------------------------------------------------------------------------

@dataclass
class StudentMatchResult:
    student_id: str | None        # UUID str of matched student, or None
    student_name: str | None      # full_name of matched student, or None
    match_confidence: str         # "exact" | "none"


def match_student(
    suggestion: str | None,
    roster: list[Any],            # objects with .id (UUID or str) and .full_name (str)
) -> StudentMatchResult:
    """
    Conservative exact-normalized match of the VLM's student_name_suggestion
    against the roster. Returns "none" on any doubt.

    - Only normalized-exact matches are accepted (casefold + niqqud strip).
    - Fuzzy matching is explicitly out of scope (S11 decision: normalize-exact only;
      revisit if the manual-assignment rate turns out to be high).
    - A missing/empty suggestion always returns "none".
    - A class-less batch passes an empty roster → all "none" (manual assignment).
    """
    if not suggestion or not suggestion.strip():
        return StudentMatchResult(student_id=None, student_name=None, match_confidence="none")

    norm_suggestion = _normalize_name(suggestion)
    for student in roster:
        if _normalize_name(str(student.full_name)) == norm_suggestion:
            return StudentMatchResult(
                student_id=str(student.id),
                student_name=student.full_name,
                match_confidence="exact",
            )

    return StudentMatchResult(student_id=None, student_name=None, match_confidence="none")


# ---------------------------------------------------------------------------
# Flag verdict
# ---------------------------------------------------------------------------

@dataclass
class FlagVerdict:
    review_needed: bool
    # Subset of: "unparseable", "grounding_retry", "low_confidence",
    #            "low_logprob_span", "missing_answers",
    #            "segmentation_mismatch", "student_unassigned", "student_unmatched"
    # Deduplicated and ordered for stable display.
    reasons: list[str] = field(default_factory=list)


# Default confidence threshold — shadows settings.transcription_confidence_threshold
# so that tests can override without importing settings.
_DEFAULT_CONFIDENCE_THRESHOLD: float = 0.8


def compute_flag_verdict(
    draft: TranscriptionDraft,
    student_match: StudentMatchResult,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
    selection_groups: Iterable[AnswerSpaceSelectionGroup] = (),
) -> FlagVerdict:
    """
    Aggregate all transcription-quality signals into a single review-needed verdict.
    A transcription is *clean* iff this returns review_needed=False.

    Signal sources (engine-agnostic — must be honest for BOTH engines):
      - draft.annotations: vlm_unparseable ([?] in an answer — both engines),
        vlm_uncertainty (grounding_retry or low_confidence — legacy only),
        vlm_low_logprob (legacy only)
      - draft.answers[]: empty answer_text → "missing_answers" (a fact, not a
        confidence guess); NON-EMPTY answer below confidence_threshold →
        "low_confidence". Under two_phase, confidence is page-attribution
        similarity, and a legitimately-skipped question is empty with 0.0 —
        counting those as "low confidence" flagged every two_phase doc
        (the 2026-08-07 false-red diagnosis), hence the empty-answer split.
      - student_match.match_confidence: "none" → two distinct facts, two reasons
        (2026-08-12, owner-ruled): a name WAS captured but matches no existing
        student → "student_unassigned" (the review surface offers one-click
        create; labeling this "name not identified" was false); no name
        captured at all → "student_unmatched". Either way the item needs
        individual attention (approval requires a student).
      - reader_disagreement is deliberately NOT a triage signal (retired in
        production — see two_phase_engine docstring).
      - code_lint (brace imbalance) is deliberately NOT a triage signal either
        (owner-ruled 2026-09-06: too noisy). A `{`/`}` imbalance is usually the
        STUDENT's own missing brace on a handwritten page — faithful capture,
        not a transcription defect — so routing the whole document to needs-eyes
        for it trains the click-through reflex INV-6's history warns about
        (the engine emitted 52 of them across 35 docs in one run). The engine
        still WRITES the INFO annotation and the review surface still renders it
        as an answer-level badge: she sees the imbalance on the card she is
        already reading, it just no longer decides where the document lives.

    Uses dict.fromkeys to deduplicate while preserving first-seen order.
    """
    reasons: list[str] = []

    for ann in draft.annotations:
        atype = ann.annotation_type
        meta = ann.metadata or {}

        if atype == "vlm_unparseable":
            reasons.append("unparseable")

        elif atype == "vlm_uncertainty":
            # The adapter sets metadata.needed_grounding_retry=True for grounding
            # retries and False (or absent) for low-confidence annotations.
            if meta.get("needed_grounding_retry"):
                reasons.append("grounding_retry")
            elif "low_confidence" not in reasons:
                reasons.append("low_confidence")

        elif atype == "vlm_low_logprob":
            reasons.append("low_logprob_span")

        elif atype == "segmentation_mismatch":
            # The student's own marker contradicts the assigned key — grading
            # would run against the wrong rubric question. Never bulk-accept.
            reasons.append("segmentation_mismatch")

    # Per-answer signals: empty answers are surfaced as their own fact;
    # the confidence check applies only to answers that HAVE content.
    # Selection-aware (2026-08-12): on a "choose k of N" exam, an unchosen
    # member's empty answers are EXPECTED — flagging them as missing was
    # false on every selection rubric (see selection_expectation.py).
    expected_empty = expected_empty_keys(
        ((a.question_number, a.sub_question_id, a.answer_text) for a in draft.answers),
        selection_groups,
    )
    for ans in draft.answers:
        if not ans.answer_text.strip():
            if (ans.question_number, ans.sub_question_id) not in expected_empty:
                reasons.append("missing_answers")
        elif ans.confidence < confidence_threshold:
            reasons.append("low_confidence")

    # Student match signal (see docstring: captured-but-unassigned vs no-name)
    if student_match.match_confidence != "exact":
        if (draft.student_name_suggestion or "").strip():
            reasons.append("student_unassigned")
        else:
            reasons.append("student_unmatched")

    return FlagVerdict(
        review_needed=bool(reasons),
        reasons=list(dict.fromkeys(reasons)),   # deduplicate, preserve order
    )
