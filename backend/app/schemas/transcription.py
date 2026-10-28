"""
Transcription domain schemas — Draft and Contract.

TranscriptionDraft      → transcriptions.draft_json  (immutable after INSERT)
TranscriptionContract   → transcriptions.contract_json (set once at approval)

contract_version lives INSIDE contract_json JSONB per Phase 0a RD-3.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from .ontology_types import AnnotationSeverity


# ---------------------------------------------------------------------------
# Annotation (transcription-domain — NOT the rubric-domain Annotation)
# ---------------------------------------------------------------------------

class TranscriptionAnnotation(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4())[:8])
    severity: AnnotationSeverity
    target_id: str  # "transcription" | "q{n}" | "q{n}.{sub}"
    annotation_type: Literal[
        "vlm_uncertainty",
        "vlm_unparseable",
        "student_name_missing",
        "vlm_low_logprob",       # S11: logprob span-min below threshold
        "reader_disagreement",   # trust layer: independent readers read this span differently
        "code_lint",             # trust layer: deterministic code check (brace balance)
        "segmentation_mismatch",  # student's leading marker contradicts the P2-assigned key
        "math_notation",         # a LaTeX span that may not render (MATH_RENDERING_PLAN §4) — INFO
    ]
    message: str  # Hebrew, user-facing
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Figures (MATH_RENDERING_PLAN §5) — Vivi's READING of a drawing, never a drawing
# ---------------------------------------------------------------------------
#
# The student's ink is the identical graph (owner ruling OD-M2: "nothing he drew is lost or
# changed"); these types hold what Vivi read FROM it, so the teacher can check each reading
# against the mark it came from before anything is graded. The answer string stays the only
# truth: it keeps the `[איור N: …]` line, and a Figure is attached to that line by
# (page, N) — see services/figures.py and FIG-1 below.
#
# Flat on purpose: union types in structured output differ across providers (plan §5).

FigureFeatureKind = Literal[
    "vertical_asymptote", "horizontal_asymptote", "minimum", "maximum",
    "x_intercept", "y_intercept", "point", "shaded_region",
    "vertex", "side_label", "angle_label", "segment_label", "right_angle_mark",
    "axis_label", "other_label",
]


class FigureFeature(BaseModel):
    model_config = {"frozen": True}
    kind: FigureFeatureKind
    #: The label EXACTLY as written on or beside the drawing, as a LaTeX body (no `\( \)`).
    #: Copied from the drawing, never from the computation beside it.
    as_written: str
    #: [y, x] on a 0–1000 grid of the whole page, at the mark it names. None when she added
    #: a feature by hand and did not place it.
    point: Optional[List[int]] = None
    #: "other" = a different colour from the student's main pen. Shown, never dropped:
    #: colour is not provenance (OD-M4).
    ink: Literal["primary", "other"] = "primary"
    uncertain: bool = False
    #: Who wrote this reading: Vivi's figure pass, or the teacher at the transcription gate.
    source: Literal["vivi", "teacher"] = "vivi"


class Figure(BaseModel):
    model_config = {"frozen": True}
    #: N in the `[איור N: …]` line — numbered per page in reading order (convention 8).
    figure_no: int
    page_number: int
    kind: Literal["function_sketch", "geometry", "other"] = "other"
    #: [ymin, xmin, ymax, xmax] on the page's 0–1000 grid — where the crop is cut.
    box_2d: Optional[List[int]] = None
    features: List[FigureFeature] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Draft side
# ---------------------------------------------------------------------------

class TranscriptionDraftAnswer(BaseModel):
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    confidence: float
    page_numbers: List[int] = Field(default_factory=list)
    #: Vivi's readings of the drawings this answer's `[איור N: …]` lines name (§5).
    #: Empty for every subject without the `figure` modality, and whenever the optional
    #: figure pass did not run or failed — the line then stands alone, as it always did.
    figures: List[Figure] = Field(default_factory=list)


class TranscriptionDraft(BaseModel):
    schema_version: str = "1.0"
    student_name_suggestion: Optional[str] = None  # VLM guess — hint only
    page_count: int
    answers: List[TranscriptionDraftAnswer]
    annotations: List[TranscriptionAnnotation] = Field(default_factory=list)
    model_version: Optional[str] = None
    # D-16 stamp (2026-09-08): the P1/P2 prompt version this draft was produced
    # under — `t1.4-tables` for CS, `t1.4-tables+<subject>` otherwise. Additive:
    # every stored draft parses unchanged (None = pre-seam).
    prompt_version: Optional[str] = None
    transcription_duration_ms: Optional[int] = None


# ---------------------------------------------------------------------------
# Selection expectation (review-surface auxiliary — NOT part of the draft)
# ---------------------------------------------------------------------------

class AnswerSpaceSelectionGroup(BaseModel):
    """A rubric SelectionGroup translated into transcription-answer space.

    `of_question_ids` ('q1', 'q2', …) become the `question_number` ints the
    transcription answers actually carry, so review surfaces and triage can
    reason about "choose k of N" without knowing the rubric's shape. Derived
    at read time by `selection_expectation.answer_space_groups` — never
    persisted (the rubric contract stays the single source)."""
    choose_k: int
    question_numbers: List[int]
    #: The teacher's OWN wording for this group («ענו על 4 מתוך 6 שאלות»),
    #: carried verbatim from `SelectionGroup.label`. Display-only, in no
    #: invariant — it exists because the transcription card's completeness
    #: sentence has to name WHICH choice it is talking about when a rubric has
    #: more than one group, and the only honest name is hers. `None` when the
    #: contract carried none: the surface then omits the prefix rather than
    #: inventing «קבוצה 1» (FC — never a value the teacher did not write).
    label: Optional[str] = None


# ---------------------------------------------------------------------------
# Review overlay (teacher working copy — transcriptions.review_json)
# ---------------------------------------------------------------------------

class TranscriptionReviewAnswer(BaseModel):
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    #: Her reviewed figure readings for this answer (§5). None = she did not touch them —
    #: the draft's readings stand. A list (even empty) is her decision, all of it.
    figures: Optional[List[Figure]] = None


class TranscriptionReview(BaseModel):
    """
    The teacher's persisted working copy of a transcription review.

    FULL SNAPSHOT, always: `answers` carries the complete answer set, and its
    (question_number, sub_question_id) key multiset must equal the draft's —
    a mismatched snapshot is rejected (422), never normalized. No merge
    semantics exist anywhere, now or in any future endpoint.

    `student_id` is the teacher's chosen student. It lives here (not in the
    transcriptions.student_id column) because transcriptions_approval_consistency
    forbids the column before approval.

    Lifecycle: writable only while status='transcribed'; set to NULL inside the
    same UPDATE that performs the 'transcribed'→'approved' transition (part of
    the transition write — LCY-1 untouched). Concurrent writes are
    last-write-wins. Accept endpoints remain body-authoritative: this overlay
    is durability for the UI, never the approval input (the future batch
    /submit endpoint is the documented exception — it has no body).
    """
    schema_version: str = "1.0"
    answers: List[TranscriptionReviewAnswer]
    student_id: Optional[str] = None
    updated_at: Optional[str] = None  # server-stamped ISO-8601 at write time


# ---------------------------------------------------------------------------
# Contract side (frozen — teacher-approved)
# ---------------------------------------------------------------------------

class TranscriptionContractAnswer(BaseModel):
    model_config = {"frozen": True}
    question_number: int
    sub_question_id: Optional[str] = None
    answer_text: str
    # A-4 closed (MATH_RENDERING_PLAN §7 Phase 2): the pages this answer was read from, so
    # a surface can show the ink behind it and a figure can reach its page. Written ONLY by
    # `services/transcription_contract.build_transcription_contract`, from the draft's P1
    # attribution matched by evidence. Default [] — every contract frozen before this field
    # parses unchanged, and an empty list is a recorded absence, never a guess.
    page_numbers: List[int] = Field(default_factory=list)
    #: The reviewed readings of this answer's drawings (§5), frozen with the text they
    #: belong to. Default [] — older contracts and every non-figure subject parse unchanged.
    figures: List[Figure] = Field(default_factory=list)

    @model_validator(mode="after")
    def _fig1_figure_line_integrity(self):
        """FIG-1: every figure is attached to exactly one `[איור N: …]` line of THIS text.

        A frozen reading of a drawing whose line is gone would be graded against nothing
        the teacher approved. `build_transcription_contract` keeps this true by
        construction; this is the type refusing anything else (§0.5 — a firing guard means
        the logic upstream is wrong)."""
        if self.figures:
            from app.services.figures import match_figures   # local: services import schemas
            orphans = match_figures(self.answer_text, self.figures).orphans
            if orphans:
                raise ValueError(
                    "FIG-1 FigureLineIntegrity: figure(s) "
                    + ", ".join(f"p{f.page_number}#{f.figure_no}" for f in orphans)
                    + " have no matching [איור N: …] line in the answer text")
        return self


class TranscriptionContract(BaseModel):
    model_config = {"frozen": True}
    schema_version: str = "1.0"
    contract_version: str = Field(default_factory=lambda: str(uuid4()))
    answers: List[TranscriptionContractAnswer]
