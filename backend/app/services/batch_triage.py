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
from typing import Any

from ..schemas.transcription import TranscriptionDraft


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
    #            "low_logprob_span", "student_unmatched"
    # Deduplicated and ordered for stable display.
    reasons: list[str] = field(default_factory=list)


# Default confidence threshold — shadows settings.transcription_confidence_threshold
# so that tests can override without importing settings.
_DEFAULT_CONFIDENCE_THRESHOLD: float = 0.8


def compute_flag_verdict(
    draft: TranscriptionDraft,
    student_match: StudentMatchResult,
    confidence_threshold: float = _DEFAULT_CONFIDENCE_THRESHOLD,
) -> FlagVerdict:
    """
    Aggregate all transcription-quality signals into a single review-needed verdict.
    A transcription is *clean* iff this returns review_needed=False.

    Signal sources:
      - draft.annotations: vlm_unparseable, vlm_uncertainty (grounding_retry or
        low_confidence), vlm_low_logprob → from the adapter
      - draft.answers[].confidence: belt-and-suspenders per-answer check
      - student_match.match_confidence: "none" → student must be assigned manually

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

    # Belt-and-suspenders: check per-answer confidence in case the adapter missed it
    for ans in draft.answers:
        if ans.confidence < confidence_threshold and "low_confidence" not in reasons:
            reasons.append("low_confidence")

    # Student match signal
    if student_match.match_confidence != "exact":
        reasons.append("student_unmatched")

    return FlagVerdict(
        review_needed=bool(reasons),
        reasons=list(dict.fromkeys(reasons)),   # deduplicate, preserve order
    )
