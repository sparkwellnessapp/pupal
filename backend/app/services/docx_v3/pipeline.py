"""
Rubric Extraction Pipeline v3.
Location: app/services/docx_v3/pipeline.py

Pipeline steps:
  Step 0: Parse + Render (deterministic)
  Step 1: Extract with LLM (structured output) + evaluator/optimizer retry loop
    1a: LLM call → RubricExtraction
    1b: Clean — remove 0-point criteria (crossed out by teacher)
    1c: Validate — structural (retryable) + point sums (flag-only)
    1d: If retryable issues → retry LLM with error feedback (max 2 retries)
  Step 2: Build ontology objects
    2a: Build ExtractRubricResponse with Question/SubQuestion/Criterion/SubCriterion
    2b: Compilation preflight — verify INV-1/INV-3 will pass
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import os
import time
from dataclasses import dataclass, field, replace as dc_replace
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple, Union
from uuid import uuid4

from pydantic import BaseModel, Field

# Canonical ontology types
from ...schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    ExtractRubricResponse,
    Question,
    SubQuestion,
    Criterion,
    SubCriterion,
    QuestionType,
    SelectionGroup,
)
from .pedagogical_mistakes import detect_pedagogical_mistakes, QuestionAdjudication

logger = logging.getLogger(__name__)

# 3.1.0 (PR B): point-mismatch issues are non-retryable — they downgrade to
# rubric_mismatch annotations immediately instead of triggering an LLM retry.
# 3.2.0 (PR-1): additive on_progress observability seam — no behavior change
#               with on_progress=None (the default); see ProgressEvent below.
# 3.3.0 (PR-2): transport policy — every LLM attempt is BOUNDED (timeout, default
#               360s), the SDK's hidden 2-retry layer is DISABLED (max_retries=0),
#               and ONE owned retry layer replaces it (_transport_retry_*) with a
#               predicate that fails fast on permanent conditions
#               (insufficient_quota / 401 / 403 / 400). A wall deadline is enforced
#               at three points so a budget overrun becomes a clean, retryable
#               failure instead of a Cloud Run SIGKILL. Behavior-affecting =>
#               invalidates transport/latency comparisons vs pre-3.3.0 runs.
#               deadline_seconds=None (eval default) => unbounded, gate untouched.
from .trace import resolve as _resolve_tracer, NULL_TRACER  # injected tracelog (no-op by default)

# PR-6 (3.5.0): Step 2c emission became consumable by the findings UI —
#   * pedagogical point-sum mistakes now carry a real SuggestedFix
#     (operation='adjust_points', params from the same evidence), so the one-click
#     proposal has ONE owner of fix semantics: the detector. `requires_teacher_input`
#     stays True — it means "never apply without her", which a proposal she must
#     click IS, rather than overrides.
#   * sub-question mistakes anchor on the FULL PATH (`q1.א.2`), the same scope
#     vocabulary the validator/compiler/mirror speak. The bare id was unpairable
#     with its own live blocker and ambiguous across questions.
#   * advisory-scan status is stamped into extraction_metadata, so partial-scan
#     honesty survives into the saved draft instead of dying with the job row.
# Selection-normalization deliberately keeps suggested_fix=None: its intent is
# unknowable, and inventing a number there is precisely what FC forbids.
# 3.6.1: additive xai provider branch (grok via the OpenAI-compatible endpoint) —
#   zero behavior change for openai/anthropic/gemini; version bumped only so the
#   provenance stamp announces the pipeline-code change (suite_hash is blind to it).
# 3.6.2: xai branch constructs with streaming=True + stream_usage=True — x.ai's
#   non-streaming path hangs on real extraction workloads (see _get_llm comment).
PIPELINE_VERSION = "3.6.2"
_MAX_RETRIES = 2
_SUM_TOLERANCE = 0.5   # validation tolerance (pre-save, human-readable)
_COMPILE_TOLERANCE = 0.01  # compilation tolerance (INV-1/INV-2 exact)
_MISMATCH_CODES = frozenset({"POINT_MISMATCH_Q", "POINT_MISMATCH_SQ", "POINT_MISMATCH_RUBRIC"})


# =============================================================================
# CONFIG + RESULT (backward-compatible)
# =============================================================================

@dataclass
class ExtractionConfig:
    subject: str = "computer_science"
    locale: str = "he-IL"
    # Pedagogical-mistake detection: Tier A (deterministic) always runs; this gates the
    # Tier B LLM adjudicator (one call per structural trigger; triggers are rare).
    detect_pedagogical_mistakes: bool = True
    # Legacy fields — accepted, ignored by v3
    use_domain_hints: bool = True
    use_llm_classification: bool = True
    llm_fallback_to_heuristics: bool = True
    self_consistency_samples: int = 1
    validate_response: bool = True
    strict_validation: bool = False
    enable_reduction_rules: bool = True


@dataclass
class ExtractionMetrics:
    total_time_seconds: float = 0.0
    render_time_seconds: float = 0.0
    llm_time_seconds: float = 0.0
    retry_count: int = 0
    num_questions: int = 0
    num_criteria: int = 0
    rendered_chars: int = 0
    # LLM provenance (a result is a function of model + prompt + input; record it).
    # Tokens accumulate across retries — cost is total spend. Dollar conversion is
    # deliberately NOT done here: prices drift, so the pipeline measures tokens and
    # the consumer (eval config) owns the price table.
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0   # subset of output (decode) that was hidden reasoning
    cached_tokens: int = 0      # subset of input served from the prompt cache
    finish_reason: Optional[str] = None
    llm_model: Optional[str] = None


@dataclass
class ExtractionResult:
    response: Optional[ExtractRubricResponse]
    document: Optional[Any] = None
    structure: Optional[Any] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    metrics: ExtractionMetrics = field(default_factory=ExtractionMetrics)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    requires_review: bool = False
    validation: Optional[Any] = None

    @property
    def is_successful(self) -> bool:
        return self.response is not None and len(self.errors) == 0


class ExtractionError(Exception):
    pass


# =============================================================================
# TRANSPORT BUDGET (PR-2) — one retry layer, every attempt bounded
# =============================================================================
# The evidence (PR-2 context report) killed the original "add retries" framing:
#   * A retry layer ALREADY existed and was invisible (openai SDK max_retries=2).
#   * The timeout was INFINITE (LangChain passes timeout=None explicitly) — the
#     root defect. One observed attempt ran 1736s, 1.9x the 900s task budget.
#   * Every organic failure arrived AFTER the SDK's 3 attempts were exhausted, so
#     attempts 4-9 have no supporting evidence.
#   * All observed 429s were `insufficient_quota` — PERMANENT billing exhaustion,
#     which the SDK retried anyway because it cannot discriminate it.
# Hence: disable the hidden layer (max_retries=0), bound every attempt (timeout),
# own exactly ONE retry layer here, and fail fast on permanent conditions.
#
# DEADLINE — a controlled in-budget failure beats an infra kill. Failing cleanly
# at the budget with a readable message + a working retry button is strictly
# better than being SIGKILLed by Cloud Run at 900s into a stranded 'extracting'
# row that only surfaces 15 minutes later via heartbeat-staleness.
# The budget is enforced at THREE points (a guard at only one of them is a
# no-op — a logical call is up to attempts x timeout, not one timeout):
#   1. validation-loop entry   — need T + 20s to start a logical call (room for
#                                ONE transport attempt + the few seconds of
#                                per-iteration work; NOT a full extra minute —
#                                (2) is what keeps a started call in budget)
#   2. each transport attempt  — need T + 10s to start an attempt (this is what
#                                makes (1) sound; without it a call admitted at
#                                the entry guard could still run 2xT and blow the budget)
#   3. Tier-B entry            — need T + 10s, else SKIP (it is best-effort)
# deadline_seconds=None => unbounded => byte-identical to pre-PR-2 behavior.
# The eval runner passes None, so eval runs and the gate are untouched BY
# CONSTRUCTION; the deadline path is production-only.

_DEFAULT_LLM_TIMEOUT_S = 360.0        # T — per-attempt wall bound (F6 ruling)
_DEFAULT_TRANSPORT_RETRIES = 1        # -> 2 attempts per logical call
_DEADLINE_ATTEMPT_RESERVE_S = 10.0    # (2)/(3) per attempt: need T + 10
# (1) validation-loop entry: a logical call needs room for its FIRST transport
# attempt (T + attempt-reserve) plus the fast per-iteration work it does on top
# (clean/validate/downgrade/emit ~ a few seconds). It does NOT need room for the
# transport RETRY — check (2) guards that. The old 60s over-reserved the ~seconds
# of post-call work by ~6x, so with a slow model (~213s/call) only 2 attempts ever
# fit and a completable extraction HARD-FAILED with a full attempt's budget still
# free (prod incident: a 3rd attempt refused — needed 420s, 414s left).
_DEADLINE_ENTRY_RESERVE_S = _DEADLINE_ATTEMPT_RESERVE_S + 10.0   # T + 20
_BACKOFF_BASE_S = 1.0
_BACKOFF_MAX_S = 4.0


class _Deadline:
    """Monotonic time budget. `seconds=None` => unbounded (eval CLI / dev).

    The clock is injectable so the budget arithmetic is testable without sleeping
    (see test_transport_budget.py's fake clock).
    """

    def __init__(self, seconds: Optional[float] = None,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._end: Optional[float] = None if seconds is None else clock() + seconds

    @property
    def bounded(self) -> bool:
        return self._end is not None

    def remaining(self) -> float:
        if self._end is None:
            return float("inf")
        return self._end - self._clock()

    def can_fit(self, need: float) -> bool:
        return self.remaining() >= need


def _describe_exc(exc: BaseException) -> str:
    """Type name + message. B5 lesson: the STRING is what reaches artifacts and
    humans (the pipeline wraps everything in ExtractionError), so the underlying
    type must be carried in the text — not only on __cause__."""
    return f"{type(exc).__name__}: {exc}"


def _is_quota_exhausted(exc: BaseException) -> bool:
    """A 429 that is NOT rate pressure but billing exhaustion — NEVER retryable.
    All three 429s observed in the eval era were this. Checked three ways because
    the code surfaces on .code, in .body, or only in the message depending on the
    SDK path."""
    if getattr(exc, "code", None) == "insufficient_quota":
        return True
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict) and err.get("code") == "insufficient_quota":
            return True
    return "insufficient_quota" in str(exc)


def _transient_classes() -> Tuple[type, ...]:
    """Retryable transport classes. Note openai.APITimeoutError subclasses
    APIConnectionError — and it is REACHABLE FOR THE FIRST TIME now that a
    timeout exists (before PR-2 it was a dead branch)."""
    classes: List[type] = []
    for mod in ("openai", "anthropic"):
        try:
            m = __import__(mod)
            classes += [m.APIConnectionError, m.APITimeoutError,
                        m.InternalServerError, m.RateLimitError]
        except Exception:  # provider package absent — skip its classes
            continue
    return tuple(classes)


def _terminal_classes() -> Tuple[type, ...]:
    """Permanent provider rejections: retrying cannot help. Fail fast, named."""
    classes: List[type] = []
    for mod in ("openai", "anthropic"):
        try:
            m = __import__(mod)
            classes += [m.AuthenticationError, m.PermissionDeniedError, m.BadRequestError]
        except Exception:
            continue
    return tuple(classes)


def _classify_transport(exc: BaseException) -> str:
    """-> 'quota' | 'terminal' | 'transient' | 'other'. The single predicate table."""
    if _is_quota_exhausted(exc):
        return "quota"          # permanent 429 — billing, not pressure
    if isinstance(exc, _terminal_classes()):
        return "terminal"       # 401/403/400 — permanent
    if isinstance(exc, _transient_classes()):
        return "transient"      # connection / timeout / 5xx / real rate-limit
    return "other"              # content, parse, bugs — NOT our business; re-raise


def _backoff_delay(attempt_index: int) -> float:
    """Jittered exponential, tightly capped — the budget is precious."""
    import random
    base = min(_BACKOFF_BASE_S * (2 ** attempt_index), _BACKOFF_MAX_S)
    return base * (0.5 + random.random() / 2.0)   # 50-100% jitter


def _transport_terminal_error(exc: BaseException) -> ExtractionError:
    """Permanent conditions get a human-readable cause, never a retry."""
    if _is_quota_exhausted(exc):
        return ExtractionError(
            f"OpenAI quota exhausted — billing issue, not retryable ({_describe_exc(exc)})"
        )
    return ExtractionError(
        f"provider rejected the request, not retryable ({_describe_exc(exc)})"
    )


def _budget_refusal_error(
    label: str, attempt_no: int, need: float, remaining: float,
    last_exc: Optional[BaseException],
) -> ExtractionError:
    """Budget refusal. When it follows a transient failure, the message carries
    BOTH facts — the transient cause AND the refusal (F1 ruling: two facts, one
    message). A message with only one of them sends the reader down a blind alley.
    """
    if last_exc is None:
        return ExtractionError(
            f"time budget exhausted before {label} attempt {attempt_no} "
            f"(need {need:.0f}s, {remaining:.0f}s left)"
        )
    return ExtractionError(
        f"{label} attempt {attempt_no} refused: time budget exhausted "
        f"(need {need:.0f}s, {remaining:.0f}s left) after transient failure — "
        f"{_describe_exc(last_exc)}"
    )


async def _transport_retry_async(
    invoke: Callable[[], Any], *, attempts: int, timeout_s: float,
    deadline: "_Deadline", label: str = "LLM call",
    sleep: Optional[Callable[[float], Any]] = None,
) -> Any:
    """THE retry layer (async). Wraps the ainvoke INSIDE the pipeline — the
    predicate cannot live at the runner boundary because the pipeline wraps every
    exception in ExtractionError (B5: the type survives only on __cause__).
    Never stacked: the SDK layer is off (max_retries=0)."""
    _sleep = sleep or asyncio.sleep
    need = timeout_s + _DEADLINE_ATTEMPT_RESERVE_S
    last: Optional[BaseException] = None

    for i in range(attempts):
        if not deadline.can_fit(need):
            raise _budget_refusal_error(
                label, i + 1, need, deadline.remaining(), last) from last
        try:
            return await invoke()
        except Exception as e:
            kind = _classify_transport(e)
            if kind in ("quota", "terminal"):
                raise _transport_terminal_error(e) from e
            if kind == "other":
                raise                                   # unchanged behavior
            last = e
            if i + 1 >= attempts:
                raise ExtractionError(
                    f"{label} failed after {attempts} transport attempt(s) — "
                    f"{_describe_exc(e)}"
                ) from e
            logger.warning(
                f"[TRANSPORT] {label} attempt {i + 1}/{attempts} transient "
                f"({_describe_exc(e)}) — retrying"
            )
            await _sleep(_backoff_delay(i))

    raise ExtractionError(f"{label}: unreachable retry state")  # pragma: no cover


def _transport_retry_sync(
    invoke: Callable[[], Any], *, attempts: int, timeout_s: float,
    deadline: "_Deadline", label: str = "Tier-B call",
    sleep: Optional[Callable[[float], Any]] = None,
) -> Any:
    """Sync twin for the Tier-B adjudicator's blocking .invoke (it runs inside
    asyncio.to_thread). Identical policy — one layer, same predicate."""
    _sleep = sleep or time.sleep
    need = timeout_s + _DEADLINE_ATTEMPT_RESERVE_S
    last: Optional[BaseException] = None

    for i in range(attempts):
        if not deadline.can_fit(need):
            raise _budget_refusal_error(
                label, i + 1, need, deadline.remaining(), last) from last
        try:
            return invoke()
        except Exception as e:
            kind = _classify_transport(e)
            if kind in ("quota", "terminal"):
                raise _transport_terminal_error(e) from e
            if kind == "other":
                raise
            last = e
            if i + 1 >= attempts:
                raise ExtractionError(
                    f"{label} failed after {attempts} transport attempt(s) — "
                    f"{_describe_exc(e)}"
                ) from e
            logger.warning(
                f"[TRANSPORT] {label} attempt {i + 1}/{attempts} transient "
                f"({_describe_exc(e)}) — retrying"
            )
            _sleep(_backoff_delay(i))

    raise ExtractionError(f"{label}: unreachable retry state")  # pragma: no cover


# =============================================================================
# PROGRESS OBSERVABILITY SEAM (PR-1)
# =============================================================================
# Injected, never imported: the pipeline emits pure-data ProgressEvents to an
# optional caller-supplied callback; the CALLER owns persistence (the job
# runner maps events onto its status row). Same injection pattern as
# _make_adjudicator / warnings_sink. Three hard rules:
#   1. on_progress default None ⇒ byte-identical behavior (zero emissions).
#   2. Every invocation is try/except-swallowed — a progress failure must
#      never fail or alter the extraction.
#   3. Payload is pure data only (no ORM objects, no sessions).

@dataclass(frozen=True)
class ProgressEvent:
    stage: str                        # render|llm_call|validate|retry|build|pedagogical|complete
    attempt: Optional[int] = None     # 1-based, for llm_call/validate/retry
    elapsed_s: Optional[float] = None
    input_tokens: Optional[int] = None   # cumulative across attempts, when known
    output_tokens: Optional[int] = None
    detail: Optional[str] = None


# Sync or async callback; the pipeline treats it opaquely.
OnProgress = Union[Callable[[ProgressEvent], None], Callable[[ProgressEvent], Awaitable[None]]]


async def _emit_progress(on_progress: Optional[OnProgress], event: ProgressEvent) -> None:
    """Best-effort dispatch — never raises (rule 2 above)."""
    if on_progress is None:
        return
    try:
        result = on_progress(event)
        if inspect.isawaitable(result):
            await result
    except Exception:  # deliberate blanket: observability must not affect extraction
        logger.debug("on_progress callback failed (ignored)", exc_info=True)


# =============================================================================
# STEP 1a: LLM EXTRACTION SCHEMA
# =============================================================================

class SubCriterionExtraction(BaseModel):
    description: str = Field(..., description="Sub-criterion text exactly as the teacher wrote it.")
    points: float = Field(..., ge=0, description="Points for this sub-criterion.")


class CriterionExtraction(BaseModel):
    description: str = Field(..., description="Criterion text exactly as the teacher wrote it. If no criterion text was found, this should be an empty string, not null.")
    points: float = Field(..., ge=0, description="Points allocated by the teacher. Use 0 for crossed-out criteria.")
    sub_criteria: List["SubCriterionExtraction"] = Field(
        default_factory=list,
        description="When this rubric row has a [NESTED TABLE] block below it: "
                    "list each nested-table row here as a SubCriterionExtraction. "
                    "Leave EMPTY when there is no nested table. "
                    "When non-empty, sum(sub_criteria.points) MUST equal this criterion's points — "
                    "do NOT also add the nested rows as separate CriterionExtraction objects.",
    )


class InnerSubQuestionExtraction(BaseModel):
    """A nested sub-question (e.g. 'א' containing numbered parts '1', '2').

    DELIBERATELY NOT RECURSIVE: bounded depth-2 as a separate concrete type.
    All observed rubrics nest at most two levels; a concrete leaf type avoids
    self-referencing $ref schemas (the weak point of cross-provider structured-
    output translation, Gemini especially) and denies constrained decoding the
    option of hallucinating deeper nesting. Depth-3 content fails LOUDLY as a
    structure mismatch in the eval — that is the extension trigger, not a bug.
    """
    sub_question_id: str = Field(..., description="Identifier of the nested part: number (1, 2) or letter.")
    text: Optional[str] = Field(None, description="The specific task instruction for this nested part.")
    # ge=0 (multisubject Phase 2, 2026-09-08): a part the document does not score at all
    # is a FACT to surface (0, flagged for the teacher), not a parse failure — the 4-unit
    # Math fixture has no marking scheme for q2. CS documents never carry a 0 here.
    points: float = Field(..., ge=0, description="Points declared for this nested part (e.g. from a 'ניקוד: N נקודות' line). Copy the DECLARED value even if criteria sum differently — never reconcile.")
    example_solution: Optional[str] = Field(
        None,
        description="Model solution / answer TEXT for this nested part — lines starting "
        "with תשובה: or פתרון: or ערך מוחזר: are solutions, NOT criteria. "
        "Null if image-only or absent.",
    )
    criteria: List[CriterionExtraction] = Field(
        default_factory=list,
        description="Criteria from the rubric table serving this part, OR from inline "
        "scoring lines (see SECTION 7) when no table serves it.",
    )


class SubQuestionExtraction(BaseModel):
    sub_question_id: str = Field(..., description="Identifier: Hebrew letter (א,ב,ג…), Latin letter, or number.")
    text: Optional[str] = Field(
        None,
        description="The SPECIFIC TASK INSTRUCTION for this sub-question. "
        "Starts at the sub-question marker (א., ב., etc.) and includes only "
        "what THIS sub-question asks the student to do. "
        "Must not be null if the sub-question has a task description in the document.",
    )
    points: float = Field(..., ge=0, description="Total points (= sum of criteria).")  # ge=0: see InnerSubQuestionExtraction.points
    example_solution: Optional[str] = Field(
        None,
        description="Model solution as TEXT for this sub-question. "
        "Null if solution is an image/screenshot or not present.",
    )
    criteria: List[CriterionExtraction] = Field(
        default_factory=list,
        description="Criteria from the rubric table serving this sub-question, OR from "
        "inline scoring lines when no table serves it (SECTION 7). MUTUALLY EXCLUSIVE "
        "with sub_questions: a sub-question has criteria XOR nested sub_questions, never both.",
    )
    sub_questions: List[InnerSubQuestionExtraction] = Field(
        default_factory=list,
        description="Nested parts when this sub-question itself splits into numbered/"
        "lettered parts (e.g. sub-question א containing parts 1 and 2, each separately "
        "scored). Empty for ordinary sub-questions. When non-empty, this sub-question's "
        "own criteria list MUST be empty (exclusivity) and points = sum of nested parts.",
    )


class QuestionExtraction(BaseModel):
    question_number: int = Field(..., description="1-based question number.")
    question_text: str = Field(
        ...,
        description="When question has sub-questions: SHARED CONTEXT only — class definitions, "
        "interface tables, setup text, code blocks. Everything BEFORE the first sub-question "
        "marker plus any context between markers. Do NOT include sub-question task instructions. "
        "When question has NO sub-questions: the full question text."
        "When a question has an explicit total points value in its header (e.g., 'שאלה 1 - 40 נקודות'), extract that number as total_points, even if no rubric table exists."
    )
    total_points: float = Field(..., gt=0, description="Total points as stated in the document.")
    example_solution: Optional[str] = Field(
        None,
        description="Question-level model solution as TEXT. "
        "Null if solution is an image/screenshot or not present.",
    )
    criteria: List[CriterionExtraction] = Field(
        default_factory=list,
        description="Criteria extracted from rubric tables (primary source) OR, when no "
        "rubric table serves this question, from INLINE SCORING LINES the teacher wrote "
        "(prose lines carrying point notation — see SECTION 7). "
        "NEVER invent criteria — only extract what the teacher wrote.",
    )
    sub_questions: List[SubQuestionExtraction] = Field(
        default_factory=list,
        description="Sub-questions detected by markers (א., ב., סעיף א, 1., etc.). "
        "Empty if no markers found.",
    )


class SelectionGroupExtraction(BaseModel):
    """A 'choose k of N' instruction over questions (e.g. 'ענו על 4 מתוך 6 שאלות')."""
    question_numbers: List[int] = Field(
        ..., min_length=1,
        description="The question numbers the student chooses among, e.g. [1,2,3,4,5,6].")
    choose_k: int = Field(..., ge=1, description="How many of them the student must answer.")
    label: Optional[str] = Field(
        None, description="The selection instruction text verbatim, e.g. 'ענו על 4 מתוך 6 שאלות'.")


class RubricExtraction(BaseModel):
    document_title: Optional[str] = None
    # `subject` is NEVER model output (D-10, ruled 2026-09-08): it was a field of
    # this structured-output schema with a CS default, i.e. the model was told
    # the default was CS. It is stamped from the job's subject after parsing.
    total_points: float = Field(..., description="Total rubric points as declared (usually 100). The pipeline recomputes the achievable total from questions + selection groups; do not reconcile it yourself.")
    questions: List[QuestionExtraction] = Field(..., min_length=1)
    selection_groups: List[SelectionGroupExtraction] = Field(
        default_factory=list,
        description="Choose-k-of-N constraints stated in the exam (SECTION 6). Empty when "
        "every question is mandatory. Question totals stay as declared in their headers — "
        "selection NEVER changes per-question points.",
    )


# =============================================================================
# STEP 1a: PROMPT
# =============================================================================

# Prompt identity. BUMP ON ANY PROMPT-TEXT CHANGE to EXTRACTION_SYSTEM_PROMPT.
# Versions the prompt INDEPENDENTLY of PIPELINE_VERSION (the code/tail version): a
# prompt edit that leaves the deterministic pipeline untouched still changes extraction
# behavior, and an extraction is a function of (prompt, pipeline, model) — each recorded
# on its own axis so the eval suite can attribute a metric move to the right one.
# --- PR-2 (3.2.0-textconv): aligned the prompt to the ratified GT text
# --- conventions (instrument-alignment; prompt must state the same rules the GT
# --- was authored under, or the eval manufactures false failures). Changes vs
# --- 3.1.0-fp123: S0 master ROLE-classification principle; S1 furniture
# --- exclusion + table cell-encoding + given-code-is-context; S2 faithful
# --- body-vs-מחוון structure; S3 role-based color (incl. question-errata + drop
# --- self-notes) + struck-prose omission; S4 filled-table->solution; renumbered
# --- to remove the duplicate SECTION 5. Context-placement rule UNCHANGED
# --- (Option B: between-marker context -> question_text).
# --- 3.4.0-tablemarkers: REVERSED the SECTION 1 table-encoding decision — a
# --- CONTEXT table (data array, interface, trace scaffold) in question_text/
# --- sub_question.text is now PRESERVED as [TABLE N: RxC] markdown (marker +
# --- separator + pipe rows, verbatim) instead of flattened to cell text, so the
# --- review surface re-renders it as a real table. SECTION 4 (FILLED solution
# --- tables -> example_solution) is UNCHANGED: still flattened to cell text —
# --- the deliberate context/solution asymmetry. GT regenerated to match
# --- (populate_texts.assemble preserves table markdown); text fidelity is
# --- ungated so this moves a diagnostic, not the gate.
# --- 3.5.0-solutiontables: extended the table-markdown preservation to SECTION 4
# --- (FILLED trace/solution tables) — example_solution now PRESERVES the full
# --- [TABLE N: RxC] block VERBATIM (marker + header + separator + value rows, empty
# --- cells kept, [[color]]/[[hl]] ink stripped) instead of flattening to cell text,
# --- so the review surface re-renders the solution as a real table. REVERSED the
# --- HEADER ROW EXCLUSION sub-rule to HEADER ROW INCLUSION (the solution table keeps
# --- its header, self-labeled). GT example_solution tables regenerated to match.
# --- example_solution_fidelity is gated but scored by a >=0.85 ratio, so GT+prompt
# --- moving together keeps it at ~1.0. Also added the 1x1-table EXCEPTION (SECTION 1
# --- + 4): a single-cell table is a code/prose container, unwrapped (marker + pipes
# --- dropped, cell content kept) — so model-solution code the teacher wrapped in a
# --- 1x1 table is NOT marked/rendered as a table.
# --- 3.6.0-scaffoldsplit: SECTION 4 — a teacher-filled table now gets a ROLE decision
# --- by JUDGEMENT (contrast ink is a HINT, not a rule). When the colored cells ARE an
# --- example-solution fill of a table the student was to complete, emit it TWICE — the
# --- filled table -> example_solution AND the blank SCAFFOLD (answer cells emptied) ->
# --- question_text. Fixes the trace scaffold being absent from question_text (the teacher
# --- never saw the empty trace table). GT already encodes the target (scaffold in q1.א.1
# --- text, filled in its solution); prompt-only.
# --- 3.7.0-tabledir: the [TABLE] marker now carries the table's OWN direction
# --- ("[TABLE N: RxC rtl|ltr]", from OOXML <w:tblPr><w:bidiVisual/>). Cells are
# --- listed in the table's LOGICAL order, so direction is what decides which end
# --- is column 1; the UI used to GUESS it from cell content and mirrored 16 tables
# --- across the fixtures in both directions. The token must be copied verbatim.
EXTRACTION_PROMPT_VERSION = "3.10.0-fixsource"

EXTRACTION_SYSTEM_PROMPT = """You are an expert Israeli education rubric extractor. You read Hebrew exam rubric documents (מחוון) carefully and extract their structure into JSON.

═══════════════════════════════════════════
SECTION 0: CARDINAL RULES
═══════════════════════════════════════════

You are an EXTRACTOR, not a GENERATOR. Copy and structure what the teacher wrote — never invent, improve, or reconcile.

MASTER PRINCIPLE — classify every region of the document by its ROLE, not by its color, position, or formatting. Each span is exactly ONE of:
  • QUESTION SPECIFICATION  → a text field (question_text or sub_question.text)
  • MODEL SOLUTION          → example_solution
  • SCORING CRITERION       → criteria (or sub_criteria)
  • FURNITURE (non-content) → dropped
Color (red [[color:...]]), position (before/after a marker), and shape (table vs prose) are HINTS to the role — never the decision. Always ask what the span DOES, then place it.

  • If a rubric table exists → extract its criteria verbatim.
  • If NO rubric table serves a scope but the teacher wrote INLINE SCORING LINES (prose carrying נק' / נקודות / ניקוד, often in teacher-red) → those lines ARE the criteria (SECTION 7).
  • If neither a rubric table nor inline scoring lines exist for a scope → criteria = [] (empty list). NEVER invent criteria, descriptions, or point values.
  • NEVER reconcile numbers. If the teacher's own point values are inconsistent (components summing to less than a declared total), copy them EXACTLY as written — the pipeline flags the inconsistency for the teacher; silently "fixing" it erases a real teacher error.
  • A field with no corresponding content in the document → null (never an empty string — except CriterionExtraction.description, which is "" when no criterion text was found).
  • Points not explicitly stated at a Question/Sub-Question level → do NOT guess or estimate.

═══════════════════════════════════════════
SECTION 1: TEXT FIELDS — question_text vs sub_question.text
═══════════════════════════════════════════

This is the most critical rule. A downstream grading agent reads each sub-question as question_text + sub_question.text. So text must be split by scope, faithfully, and carry ONLY the teacher's question — no solution, no scoring, no furniture.

• question_text = SHARED CONTEXT only — everything the student needs BEFORE any specific sub-question: class definitions, interface tables, setup descriptions, given code blocks, data tables. It applies to ALL sub-questions equally.

• sub_question.text = the SPECIFIC TASK INSTRUCTION for that sub-question. INCLUDE its marker (א., ב., ג., "סעיף א", 1., 2.). It runs from the marker to the next boundary: the next sub-question marker, the rubric table, the מחוון, a solution block (פתרון:/תשובה:), the next question header (שאלה N), or end of document.

SPLITTING RULE: scan the document top-to-bottom. Everything BEFORE the first sub-question marker → question_text. Each marker opens a new sub_question.text. Context that appears BETWEEN two markers (e.g. a new class definition introduced between ב and ג) is SHARED CONTEXT → append it to question_text, NOT to any single sub_question.text. A sub_question.text contains ONLY that sub-question's own task instruction.

If a question has NO sub-question markers → it has no sub_questions; all text goes into question_text; criteria are direct.

GIVEN CODE is context, not solution. Code the question PROVIDES for the student to use, extend, or trace (a class skeleton, a function to analyze) — whether inline or inside a [TEXTBOX]...[/TEXTBOX] block — goes into a text field (shared → question_text). Strip the [TEXTBOX] wrapper; keep the code. It is example_solution ONLY when it appears under a solution label (פתרון: / פתרון לדוגמה) — see SECTION 4.

EXCLUDE FROM ALL TEXT — furniture belongs to no scope, even though it sits inside a span in reading order:
  • Continuation / navigation: "(המשך השאלה - בעמוד הבא)", "(המשך שאלה N)", "בעמוד הבא", printed page numbers.
  • Exam chrome: the document title, "שם התלמיד" / "שם המורה" fields, the instructions block (הנחיות, exam duration, "חומר עזר..."), "בהצלחה!".
  • [IMAGE: ...] markers — unreadable embedded images (SECTION 4).
Leaving furniture inside a text field corrupts that scope's text.

TABLE ENCODING — when a context table (data array, class interface, trace scaffold) belongs in a text field, PRESERVE IT AS MARKDOWN, VERBATIM. The marker carries the table's own reading DIRECTION — `[TABLE N: RxC ltr]` or `[TABLE N: RxC rtl]` — which comes from the source document and tells the review surface which end is column 1; copy that token exactly as given and NEVER change, drop, or "correct" it (the cells are listed in the table's own logical order, so dropping the token mirrors her table). Copy the `[TABLE N: RxC ...]` marker line and every table line beneath it — the header row, the `|---|` separator, and each `| cell | cell |` data row — EXACTLY as they appear in the rendered document, on their own lines; keep any indented `[NESTED TABLE: RxC]` block inside it. Do NOT flatten the table to space-joined cell text; do NOT drop the marker, the pipes, or the separator; do NOT renumber or reformat. The review surface parses this markdown back into a real table, so the structure MUST survive intact. EXCEPTION — a 1×1 table (RxC = 1x1, a single cell) is NOT a grid; it is a container the renderer wrapped around code or a prose block. DROP its `[TABLE …: 1x1]` marker, the `|---|` separator, and the surrounding pipes, and keep ONLY the cell's content (the code/text itself). Preserve `[TABLE]` markers ONLY for tables with real structure — 2 or more columns, or 2 or more rows. (A data array is rendered as the marker line `[TABLE 4: 1x8 rtl]` followed by the row `| 2 | 9 | 40 | 3 | 15 | 4 | 5 | 8 |` — that whole block goes into the text field unchanged. This applies to CONTEXT tables only; a FILLED solution table is handled differently — see SECTION 4.)

EXAMPLE — correct splitting:

Document fragment:
  "שאלה 1 - 40 נקודות
  הוגדרה מחלקה בשם Hobby בעלת התכונות הבאות:
  hobbyName - שם התחביב...
  [TABLE 1: 2x2 rtl]
  | תיאור הפעולה | כותרת הפעולה |
  |---|---|
  | פעולה בונה תחביב... | public Hobby(...) |
  א. כתבו כותרת ותכונות המחלקה Hobby ואת הפעולה הבונה.
  (המשך השאלה - בעמוד הבא)
  public class SchoolHobbies { ... }
  ב. כתבו פעולה פנימית בשם PopulateHobbies..."

CORRECT output:
  question_text:
    "הוגדרה מחלקה בשם Hobby בעלת התכונות הבאות:
     hobbyName - שם התחביב...
     [TABLE 1: 2x2 rtl]
     | תיאור הפעולה | כותרת הפעולה |
     |---|---|
     | פעולה בונה תחביב... | public Hobby(...) |
     public class SchoolHobbies { ... }"
  total_points: 40
  sub_questions:
    א.text: "א. כתבו כותרת ותכונות המחלקה Hobby ואת הפעולה הבונה."
    ב.text: "ב. כתבו פעולה פנימית בשם PopulateHobbies..."

Three things to notice: the [TABLE] block was PRESERVED as markdown (marker, separator, and pipes ALL kept, on their own lines — the review surface re-renders it as a table); the continuation marker was DROPPED; and the SchoolHobbies class sits between א and ב but is SHARED CONTEXT (used by ב and later), so it went into question_text — NOT into א.text.

WRONG (do NOT do any of these):
  • א.text or ב.text containing the SchoolHobbies class → context bled into a sub-question.
  • א.text: null with its task text absorbed into question_text → task dumped into shared context.
  • The continuation marker "(המשך...)" kept in any text field → furniture retained.
  • question_text with the [TABLE] FLATTENED to space-joined cell text ("תיאור הפעולה כותרת הפעולה\nפעולה בונה תחביב... public Hobby(...)") — the marker and pipes dropped → table structure destroyed; the review surface can no longer render it as a table.

═══════════════════════════════════════════
SECTION 2: SUB-QUESTION DETECTION & STRUCTURE
═══════════════════════════════════════════

Sub-question markers (any of these):
• Hebrew letter + period or parenthesis: א., ב., ג., א), ב)
• "סעיף" prefix: "סעיף א", "סעיף ב'"
• Numeric: 1., 2., 3.

A question with NO markers → zero sub_questions; all criteria direct.

When the rubric table labels criteria with prefixes ("סעיף א:", "סעיף ב בתוך..."), those labels say which sub-question each criterion belongs to. Group criteria accordingly — the sub-question STRUCTURE follows the מחוון's grouping.

FAITHFUL STRUCTURE: if the question BODY marks a sub-question that the מחוון does NOT score as its own section — the מחוון folds that operation's criteria under an adjacent section (e.g. the body has 'ג.' but every criterion for that operation is filed under 'סעיף ב') — do NOT invent an empty sub-question. Keep the structure the מחוון implies, and fold that body-task's INSTRUCTION TEXT into the text of the section that scores it (its marker kept verbatim). The pipeline's detector flags the body-vs-מחוון discrepancy for the teacher separately — reproduce it, don't fix it.

═══════════════════════════════════════════
SECTION 3: RUBRIC TABLE EXTRACTION
═══════════════════════════════════════════

• PRESERVE teacher text exactly — copy criterion descriptions verbatim.
• PRESERVE teacher points exactly — use exact point values from the rubric.
• SKIP total/summary rows (סה"כ) — these are sums, NOT criteria.
• SKIP section-header rows with empty points cells — rows like "סעיף ב': פעולה חיצונית LowestRateChannel סה"כ לכל הפעולה 30" with no points value are headers, NOT criteria.
• When rubric tables have TWO text columns (e.g., "תיאור" + "רכיב הערכה"), concatenate into one description: "column1: column2".
• Tables that are NOT rubric tables (data arrays, class interfaces, trace tables) are CONTEXT — PRESERVE them in question_text as [TABLE N: RxC] markdown, VERBATIM (SECTION 1); do NOT extract criteria from them.
• NESTED TABLES: When a rubric row is immediately followed by an indented [NESTED TABLE: NxM] block, that row is a PARENT CRITERION with a point breakdown. Handle it as follows:
  1. Extract the parent row as a CriterionExtraction (description = parent row text, points = parent row point value).
  2. Extract EACH row of the nested table as a SubCriterionExtraction and put them in the parent's sub_criteria list.
  3. Do NOT also add the nested-table rows as separate top-level CriterionExtraction objects — that would double-count their points.
  4. sum(sub_criteria.points) must equal the parent criterion's points.

  EXAMPLE — a rubric row followed by a nested table:

    | לולאה על TvShows - סה"כ לצבירה 12. פירוט ל-12: | 12 |
      [NESTED TABLE: 4x2]
      | הגדרת לולאה על מערך TvShows | 3 |
      | בתוך הלולאה: בדיקה אם התא אינו null | 2 |
      | בתוך הלולאה: גישה לערוץ GetChl | 2 |
      | בתוך הלולאה: צבירת הדירוג | 5 |

  CORRECT extraction:
    CriterionExtraction(
      description="לולאה על TvShows - סה"כ לצבירה 12. פירוט ל-12",
      points=12,
      sub_criteria=[
        SubCriterionExtraction("הגדרת לולאה על מערך TvShows", 3),
        SubCriterionExtraction("בתוך הלולאה: בדיקה אם התא אינו null", 2),
        SubCriterionExtraction("בתוך הלולאה: גישה לערוץ GetChl", 2),
        SubCriterionExtraction("בתוך הלולאה: צבירת הדירוג", 5),
      ]
    )

  WRONG — double-counting (do NOT do this):
    CriterionExtraction("לולאה על TvShows...", 12, sub_criteria=[])  ← parent extracted as criterion
    CriterionExtraction("הגדרת לולאה...", 3)   ← nested row ALSO extracted as criterion = +3 double-counted
    ... (total double-count: 12 extra points)

• STRIKETHROUGH — text the teacher REMOVED, wrapped in ~~tildes~~:
  – ~~old_value~~ immediately followed by a new value → use the NEW value.
  – An entire criterion row struck through (all columns ~~...~~) → assign it 0 points (the pipeline drops 0-point rows).
  – Struck-out PROSE (a crossed-out sentence or phrase, not a point value) → OMIT it entirely from every text field. It is content the teacher deleted; it is neither question text nor anything else.

• COLOR / HIGHLIGHT — classify by ROLE, never by color. [[color:RRGGBB]]...[[/color]] marks teacher ink written in a contrasting color (usually red); [[hl:name]]...[[/hl]] marks teacher HIGHLIGHTING (marker pen, e.g. [[hl:yellow]]). Both are HINTS that the ink is teacher-touched; they are NOT instructions to exclude, and the marker tokens themselves never appear in any output field. Decide by what the text DOES:
  – MARKED OPTION = THE ANSWER: when the question presents a list of options/alternatives (e.g. candidate code lines to choose from) and one or more items are highlight- or color-marked, the marking is the teacher indicating the CORRECT option(s) → set that scope's example_solution to the marked item text verbatim (markers stripped). The full options list stays question text; the marked item appears in BOTH (it is part of the question AND it is the answer).
  – Solution ("תשובה:", "פתרון:", "ערך מוחזר:") → example_solution for that scope.
  – Scoring ("ניקוד:", or a component carrying נק' / נקודות) → a criterion, or a scope's points (SECTION 7).
  – Deduction / penalty guidance ("להוריד X נק' אם...", "אם לא השתמשו... להוריד 2") → grading guidance: NOT a scored criterion, and NOT question text. (If it is written as part of a criterion line, keep it verbatim inside that criterion's description; a standalone deduction line is neither a criterion nor text.)
  – Question SPECIFICATION, or a CORRECTION to the question (the red text states or fixes what the student must actually do — e.g. a corrected return-value spec) → this IS question content; put it in the relevant text field. Red does not make it "not the question."
  – Teacher NOTE-TO-SELF (a remark to another teacher / a to-do, e.g. "לתקן בשאלון המקורי", "לבדוק עם...") → DROP entirely; it belongs to no field.
  Where one location has a struck-out old version AND a red corrected version, drop the struck text (per STRIKETHROUGH above) and keep the corrected text in its role.

═══════════════════════════════════════════
SECTION 4: EXAMPLE SOLUTIONS
═══════════════════════════════════════════

• Extract text under "פתרון לדוגמה" / "פתרון:" / "תשובה:" / "ערך מוחזר:" verbatim; assign to the correct scope when possible.
• VERBATIM MEANS THE WHOLE ANSWER-KEY INK, UNCLEANED: include ALL alternative solutions the teacher wrote (e.g. "OPTION 1" AND "OPTION 2 (WHILE)" blocks — never pick one), commented-out / dead code blocks (/* ... */ or // lines the teacher left in), boundary/separator lines (e.g. "//Q2 - ב - START", "//------"), and the teacher's own typos or naming inconsistencies exactly as written (a solution named ArrangeMirrorBR stays ArrangeMirrorBR even if the question says ArrangeMirror). The answer key is teacher ink — you copy it, you never edit, select, deduplicate, or normalize it.
• BLOCK-BOUNDARY TEST — decide where the solution ENDS before you copy it. The end of the CODE is not the end of the BLOCK. Walk forward from the solution's first line and keep copying until you reach the next scope's content (its question/sub-question label, its rubric table, or its scoring lines). Everything before that boundary is part of this solution — INCLUDING a closing ruler/separator comment line such as "//----------------------------------------" that the teacher used to close the block off. A closing brace "}" is NOT a stop signal; a ruler line AFTER it still belongs to this solution. Copy only what is actually present in the source — never add a ruler the teacher did not write.
• If the solution appears as [IMAGE: ...] markers (screenshots, not extractable text), set example_solution to null.
• [IMAGE: ...] markers indicate embedded images that cannot be read as text — never place them in any text field; drop them.
• A TABLE THE TEACHER FILLED WITH VALUES — first, wherever it lands, PRESERVE IT AS MARKDOWN, VERBATIM: copy the `[TABLE N: RxC]` marker, the header row, the `|---|` separator, and every value row exactly as rendered — keep empty cells so the columns stay aligned; strip ONLY the teacher-ink annotation tokens ([[color:...]] and [[hl:...]]) from the cell contents, never the values themselves; never flatten to space-joined text; the HEADER ROW is INCLUDED so the table renders self-labeled. This is SYMMETRIC with SECTION 1, and both obey the SECTION 1 1×1 EXCEPTION (a block wrapped in a 1×1 table is code/prose, NOT a grid — unwrap it, dropping the marker/pipes).
  Now decide WHERE it goes — classify by ROLE, not color (SECTION 3). Contrast ink ([[color:...]] / [[hl:...]]) on the filled cells HINTS the values are the teacher's answer, but it is ONLY a hint; use your JUDGEMENT to decide whether the contrast-ink cells are an EXAMPLE SOLUTION the teacher wrote into the table:
   – YES — the colored cells ARE the answer, and blanking them leaves the empty table the student was given to fill → the table has a DUAL role; emit it TWICE:
       → example_solution: the WHOLE filled table (ink stripped) — the answer key.
       → question_text: the SAME table as the EMPTY SCAFFOLD the student sees — keep the marker, header and column structure, but REPLACE every answer (contrast-ink) cell with an EMPTY cell.
   – NO — the contrast ink is mere emphasis on a value in a GIVEN data/example table, not an answer the student was to supply → route the WHOLE table (ink stripped) into question_text as context ([TABLE] markdown, SECTION 1); do NOT blank, do NOT duplicate.
   – The table sits UNDER a solution label (פתרון: / תשובה: / ערך מוחזר:) as the teacher's OWN worked answer (not a blank the student fills) → example_solution ONLY, whole table, ink stripped; no scaffold.
   Example (DUAL role) — [TABLE 3: 6x5 rtl], default-ink header `| ערך מוחזר | <cond> | arr[i] | i | x |`, red-filled rows `|  | F | 8 | 0 | 6 |` … `| T | T | 3 | 4 |  |`, the question having told the student to complete a trace table:
       question_text  ← `[TABLE 3: 6x5 rtl]` + header + `|---|` + five EMPTY rows `|  |  |  |  |  |`
       example_solution ← `[TABLE 3: 6x5 rtl]` + header + `|---|` + the filled rows (ink stripped)

═══════════════════════════════════════════
SECTION 5: POINT INVARIANTS (only when criteria exist)
═══════════════════════════════════════════

These rules apply when criteria are present (from rubric tables OR inline scoring lines):
• For each sub-question: points = sum(criteria.points) — but if the document DECLARES a different value (e.g. a 'ניקוד: N נקודות' line), the declared value wins for `points`; keep the criteria values as written even if they disagree (never reconcile).
• For each question: total_points comes from the question header (e.g., "שאלה 1 - 40 נקודות") — it is authoritative, never recomputed from children.
• For the rubric: total_points = the declared exam total when stated; otherwise sum of question totals. When a selection instruction exists (SECTION 6), do NOT try to reconcile — the pipeline computes the achievable total.

When NO criteria exist anywhere for a question (no table, no inline scoring lines): still extract total_points from the question header, and leave criteria as an empty list.

═══════════════════════════════════════════
SECTION 6: SELECTION GROUPS — "choose k of N" exams
═══════════════════════════════════════════

Israeli exams frequently offer more questions than the student answers. Detect instructions like:
• "ענו על 4 מתוך 6 שאלות" / "ענו על ארבע שאלות מבין השאלות 1–6"
• "ענו על שאלה אחת בלבד" (over a listed set of questions)

For each such instruction, emit a selection_groups entry:
• question_numbers = the question numbers the student chooses among
• choose_k = how many they must answer
• label = the instruction text verbatim

Rules:
• Per-question total_points stay EXACTLY as declared in their headers. Selection never changes per-question points.
• Do NOT adjust rubric total_points to account for selection — the pipeline computes the achievable total from your groups.
• A question not mentioned in any selection instruction is mandatory — do not put it in a group.
• No selection instruction in the document → selection_groups = [].

═══════════════════════════════════════════
SECTION 7: INLINE / PROSE SCORING LINES AS CRITERIA
═══════════════════════════════════════════

Some questions have no rubric table. Their scoring lives in prose lines the teacher wrote, usually marked in teacher-red ([[color:...]]) and carrying point notation. These lines ARE the criteria for that scope.

How to recognize a scoring line: it names an evaluation component and carries points — e.g. "כותרת – 3 נק'", "סעיף א : 15 נק  (כל עדכון 2/3 נק)", "הבנת הבדיקה של מחלק ללא שארית  1.5 נק'".

Extraction rules:
• description = the line VERBATIM, INCLUDING its point notation and any parenthetical guidance. "כותרת – 3 נק'" stays exactly that.
• points = the line's scope-level point value ("סעיף א : 15 נק (כל עדכון 2/3 נק)" → points=15; the 2/3 is internal per-item guidance inside the verbatim text).
• TOTAL-LABEL TEST — run this BEFORE emitting anything for a "ניקוד: N נקודות" line. Look through that scope's WHOLE scoring block, not just the next line:
  – If the block contains itemized component lines carrying their own points (e.g. "- זיהוי ש... – 2 נק'", "הבנת הבדיקה...  1.5 נק'") → the "ניקוד: N נקודות" line is the scope's TOTAL. Set the sub-question's points=N and emit ONE CRITERION PER COMPONENT LINE. **Do NOT emit the "ניקוד: N נקודות" line itself as a criterion.** Copy both faithfully EVEN IF the components do not sum to N (never reconcile — the pipeline flags it).
  – ONLY if the block has NO such component lines anywhere → the "ניקוד: N נקודות" line IS the scope's single criterion: emit ONE criterion, description = that verbatim line, points=N.
• INTERVENING LINES DO NOT BREAK THE ASSOCIATION. The component lines often do not sit directly under the label — an example-solution line (תשובה:/פתרון:/ערך מוחזר:, SECTION 7 above) or a deduction/penalty note ("אם כתבו הפוך... להוריד 0.5") frequently sits between them. Those lines are not criteria and are not separators: keep scanning past them to the end of the scope's scoring block before deciding which branch of the TOTAL-LABEL TEST applies.
• WHY THIS MATTERS: emitting the total label as a criterion double-counts the scope's points (its components already carry them). The scope then sums to ~2x its declared value, and the pipeline raises a point-sum mismatch on a node the teacher wrote CORRECTLY — a false alarm the teacher has to chase. That is worse than a missing criterion, because it destroys trust in every real flag.
• Lines starting with תשובה: / פתרון: / ערך מוחזר: are EXAMPLE SOLUTIONS → example_solution field, never criteria.
• Deduction/penalty guidance ("להוריד X נק' אם...", "אם לא השתמשו... להוריד 2") is NOT a criterion — do not emit it as one.
• Question body text, task instructions, and data values are NEVER criteria, even when they contain numbers. Only lines whose purpose is scoring qualify.
• When a rubric TABLE serves a scope, the table is the criteria source — do not additionally extract prose lines for that scope.

═══════════════════════════════════════════
SECTION 8: NESTED SUB-QUESTIONS
═══════════════════════════════════════════

A sub-question can itself split into separately-scored parts: e.g. sub-question א containing part 1 (a trace table task) and part 2 (an explanation task), each with its own scoring.

• Detect by markers inside a sub-question's scope: numbered parts (1., 2.) under a lettered sub-question, or vice versa.
• DETECT BY SCORING STRUCTURE WHEN MARKERS ARE WEAK OR MISSING: real sources often mark only the first part — "א. (1) ..." with the second task appearing later with NO "(2)". The reliable signal is the SCORING: if a sub-question's ink contains MULTIPLE distinct task statements, EACH followed by its own scoring block (its own "ניקוד: N נקודות" line, its own scored table, or its own itemized component lines), those are separately-scored nested parts → emit them as sub_questions labeled 1, 2, ... in document order. A "רשמו בקצרה..." task after a trace-table task, each with its own ניקוד block, is TWO parts even though the source never writes "(2)". Never fold a separately-scored second task's scoring lines into the first task's criteria.
• Emit them as the sub-question's `sub_questions` list (one nesting level only).
• EXCLUSIVITY: a sub-question has criteria XOR sub_questions — never both. When it has nested parts, its own criteria list is empty and the criteria live on the parts.
• The parent sub-question's points = sum of its parts' declared points.
• MARKER INCLUSION for nested parts: a part's `text` keeps its OWN inner marker ('(1)', '(2)') and does NOT repeat the parent letter — the parent's 'א.'/'ב.' belongs to the parent scope. The parent sub-question's own `text` is the shared lead-in for its parts, or null when there is none (a pure splitter)."""


# =============================================================================
# STEP 1a: LLM CALL
# =============================================================================

def _is_openai_reasoning(model: str) -> bool:
    """OpenAI reasoning family (gpt-5.x, o-series): rejects non-default temperature;
    reasoning tokens bill against the completion budget."""
    return model.startswith(("gpt-5", "o1", "o3", "o4"))


def _llm_params(
    provider: str,
    model: str,
    max_output_tokens: Optional[int] = None,
    reasoning_effort: Optional[str] = None,
    timeout_s: Optional[float] = None,
) -> Dict[str, Any]:
    """PURE per-family constructor-kwargs policy (no imports, no I/O — testable
    without provider packages installed). Encodes:

    - openai reasoning family (gpt-5.x / o-series): temperature OMITTED (the API
      rejects non-default values), `reasoning_effort` passed through when set,
      completion budget defaults to 32k because reasoning tokens bill against it
      (langchain-openai maps max_tokens -> max_completion_tokens for this family;
      requires a current langchain-openai — verified by the smoke run).
    - openai non-reasoning (gpt-4o family): temperature=0, max_tokens 12k (the
      original behavior, unchanged).
    - anthropic: temperature=0, max_tokens required by the API, default 16k.
      (Extended thinking is a deliberate non-feature here: it forces temperature=1
      and constrains forced tool choice, which structured output uses. If it ever
      becomes a config knob, it is a new policy branch, not a flag on this one.)
    - gemini: temperature=0, Gemini's kwarg is `max_output_tokens`, default 16k.

    PR-2 — EVERY CALL IS BOUNDED AND OWNS ITS RETRY BUDGET (openai + anthropic):
      * `timeout` (alias; the real fields are `request_timeout` on ChatOpenAI and
        `default_request_timeout` on ChatAnthropic — both accept the alias and
        both reach the SDK client, verified against langchain-openai 1.1.7 /
        langchain-anthropic 1.4.0). WITHOUT this, LangChain passes timeout=None
        EXPLICITLY, which overrides the SDK's own default and yields
        httpx Timeout(None) = NO TIMEOUT: one observed attempt ran 1736s (29 min),
        1.9x the entire task budget.
      * `max_retries=0` DISABLES the SDK's hidden 2-retry layer (its default). That
        layer is invisible, unbounded, and cannot discriminate `insufficient_quota`
        (a permanent billing 429) from real rate pressure. ALL retrying moves to the
        one layer we own: _transport_retry_async / _transport_retry_sync.
      GEMINI IS DELIBERATELY UNTOUCHED — that branch is undeployable today
      (langchain_google_genai is not installed); bounding it is a separate decision.
    """
    timeout = _DEFAULT_LLM_TIMEOUT_S if timeout_s is None else timeout_s
    # The bound + the disabled hidden layer travel together — never one without the other.
    bounded: Dict[str, Any] = {"timeout": timeout, "max_retries": 0}

    if provider == "anthropic":
        # Claude 5 family REJECTS the temperature parameter outright (live 400,
        # 2026-08-28 grading-eval screen: "`temperature` is deprecated for this
        # model", req_011CeVWAnCj55zLZezwwRNGm) — the same knob-drop the OpenAI
        # reasoning family made above; omission is the only valid setting.
        # 4.x models (haiku-4.5, sonnet-4.x, opus-4.x) keep temperature=0.
        # `effort` (output_config.effort on the wire) is the 5-family's thinking-
        # depth knob and ChatAnthropic 1.4.0 exposes it as a native field. Passed
        # through ONLY when explicitly configured, exactly like the openai
        # reasoning branch below — models without effort support are untouched.
        if model.startswith(("claude-sonnet-5", "claude-opus-5",
                             "claude-haiku-5", "claude-fable", "claude-mythos")):
            params: Dict[str, Any] = {"max_tokens": max_output_tokens or 16000, **bounded}
            if reasoning_effort:
                params["effort"] = reasoning_effort
            return params
        return {"temperature": 0, "max_tokens": max_output_tokens or 16000, **bounded}
    if provider == "gemini":
        return {"temperature": 0, "max_output_tokens": max_output_tokens or 16000}
    if provider == "xai":
        # grok (OpenAI-compatible, reasoning family): temperature OMITTED (grok-4+
        # reasoning models reject/ignore sampling knobs — omission is always safe),
        # reasoning_effort passed through only when explicitly set, completion
        # budget defaults to 32k (reasoning tokens bill against it). Bounded like
        # openai — same SDK underneath, same hidden retry layer to disable.
        params: Dict[str, Any] = {"max_tokens": max_output_tokens or 32000, **bounded}
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
        return params
    # openai
    if _is_openai_reasoning(model):
        params: Dict[str, Any] = {"max_tokens": max_output_tokens or 32000, **bounded}
        if reasoning_effort:
            params["reasoning_effort"] = reasoning_effort
        return params
    return {"temperature": 0, "max_tokens": max_output_tokens or 12000, **bounded}



def _tier_b_prompt_version() -> Optional[str]:
    """Tier-B prompt identity, read lazily and defensively: provenance must never
    be able to break an extraction."""
    try:
        from .pedagogical_mistakes import TIER_B_PROMPT_VERSION
        return TIER_B_PROMPT_VERSION
    except Exception:
        return None

def _llm_timeout_s() -> float:
    """Per-attempt wall bound. Ruled default 360s (see PR-2 F6): the observed
    per-attempt distribution is bimodal — all mass <=235s, one point at 1736s,
    nothing between — so the choice is insurance pricing, and the costs are
    asymmetric (a false timeout burns two attempts ~12 min and fails a
    teacher-visible job; the extra 60s only costs latency on a genuine hang)."""
    raw = os.environ.get("EXTRACTION_LLM_TIMEOUT_S")
    return float(raw) if raw else _DEFAULT_LLM_TIMEOUT_S


def _transport_attempts() -> int:
    """Total transport attempts per logical call = 1 + retries. Default 2 (one
    retry) — the GraderAgent's 'one surgical retry' convention, made true here."""
    raw = os.environ.get("EXTRACTION_TRANSPORT_RETRIES")
    retries = int(raw) if raw else _DEFAULT_TRANSPORT_RETRIES
    return max(1, retries + 1)


def _get_llm(provider: str, model: str, timeout_s: Optional[float] = None):
    """Construction only — all parameter policy lives in _llm_params (pure).
    Generation knobs arrive via env (set per-run by the eval runner from its
    config file, same channel as model/provider)."""
    max_out = os.environ.get("EXTRACTION_LLM_MAX_TOKENS")
    effort = os.environ.get("EXTRACTION_LLM_REASONING_EFFORT") or None
    params = _llm_params(
        provider, model, int(max_out) if max_out else None, effort,
        timeout_s=_llm_timeout_s() if timeout_s is None else timeout_s,
    )
    if provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=model, **params)
    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model=model, **params)
    if provider == "xai":
        # grok rides the OpenAI-compatible endpoint: same ChatOpenAI client,
        # different base_url + key. XAI_API_KEY is REQUIRED explicitly — a silent
        # fallback to OPENAI_API_KEY would 401 with a misattributed key.
        from langchain_openai import ChatOpenAI
        xai_key = os.environ.get("XAI_API_KEY")
        if not xai_key:
            raise RuntimeError("provider 'xai' requires XAI_API_KEY in the environment")
        # streaming REQUIRED for xai (empirical, 2026-08-15): x.ai's NON-streaming
        # response path hangs indefinitely on large-prompt/long-generation requests
        # (probe: identical request streamed → TTFT 1.5s, done 156s; non-streamed →
        # ReadTimeout at 620s). stream_usage keeps token accounting for cost.
        return ChatOpenAI(model=model, api_key=xai_key,
                          base_url="https://api.x.ai/v1",
                          streaming=True, stream_usage=True, **params)
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(model=model, **params)


def _get_llm_config() -> Tuple[str, str]:
    """Get provider and model from environment."""
    provider = os.environ.get("EXTRACTION_LLM_PROVIDER", "openai")
    model = os.environ.get("EXTRACTION_LLM_MODEL", None)
    defaults = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-20250514",
                "gemini": "gemini-3.1-pro-preview", "xai": "grok-4.6"}
    return provider, model or defaults.get(provider, "gpt-4o")


def _make_adjudicator(deadline: Optional["_Deadline"] = None):
    """Build the Tier-B StructuredLLM adapter for pedagogical-mistake adjudication,
    reusing the extraction LLM config.

    Returns a callable (*, system, user, schema) -> QuestionAdjudication wrapping
    LangChain's with_structured_output. Two deliberate properties:
      * LAZY construction — the LLM client is built on first invocation, not here.
        Triggers are rare, so the common (no-trigger) path pays nothing; and a
        construction failure (missing key, import error) surfaces inside the
        detector's per-trigger isolation instead of aborting Tier A detection.
        This also matches _call_llm's per-call-construction convention.
      * Synchronous .invoke — detection runs inside asyncio.to_thread in
        extract_rubric_from_docx, so the blocking call does not stall the event
        loop, and the detection module stays sync (and unit-testable).

    PR-2: the call is bounded (timeout) and goes through the ONE retry layer
    (sync variant). Tier B previously had no application retry AND relied on the
    SDK's hidden 3 attempts — which it exhausted on its one real organic failure
    (B7). Per-trigger isolation in the detector is unchanged: whatever this raises
    becomes a warning for that trigger, never a failed extraction.
    """
    state: Dict[str, Any] = {}
    dl = deadline or _Deadline(None)
    timeout_s = _llm_timeout_s()
    attempts = _transport_attempts()

    def _adjudicate(*, system: str, user: str, schema):
        if "structured" not in state:
            from langchain_core.messages import SystemMessage, HumanMessage
            provider, model = _get_llm_config()
            state["structured"] = _get_llm(
                provider, model, timeout_s=timeout_s
            ).with_structured_output(QuestionAdjudication)
            state["messages"] = (SystemMessage, HumanMessage)
        SystemMessage, HumanMessage = state["messages"]
        return _transport_retry_sync(
            lambda: state["structured"].invoke(
                [SystemMessage(content=system), HumanMessage(content=user)]
            ),
            attempts=attempts, timeout_s=timeout_s, deadline=dl, label="Tier-B call",
        )

    return _adjudicate


def _call_meta_from_raw(raw: Any, model: str) -> Dict[str, Any]:
    """PURE provenance extraction from an include_raw AIMessage, portable across
    providers. Token counts prefer LangChain-normalized `usage_metadata`
    (openai/anthropic/gemini all populate it), falling back to the OpenAI-shaped
    `response_metadata.token_usage`. finish_reason reads `finish_reason` (openai:
    'stop'/'length'; gemini: 'STOP'/'MAX_TOKENS') or `stop_reason` (anthropic:
    'end_turn'/'max_tokens'); the scorer's truncation guard compares
    case-insensitively, so provider casing is irrelevant. May raise on exotic
    shapes — the caller wraps it in best-effort."""
    usage = getattr(raw, "usage_metadata", None) or {}
    if not usage:
        usage_raw = (getattr(raw, "response_metadata", None) or {}).get("token_usage", {})
        usage = {"input_tokens": usage_raw.get("prompt_tokens", 0),
                 "output_tokens": usage_raw.get("completion_tokens", 0)}
    rm = getattr(raw, "response_metadata", None) or {}
    # reasoning + prompt-cache detail (LangChain normalizes these into *_token_details
    # for the OpenAI reasoning family; absent → 0). reasoning tokens are decode time;
    # cached input is prefill we didn't pay to recompute — both are latency signal.
    in_details = usage.get("input_token_details") or {}
    out_details = usage.get("output_token_details") or {}
    return {
        "input_tokens": int(usage.get("input_tokens", 0) or 0),
        "output_tokens": int(usage.get("output_tokens", 0) or 0),
        "reasoning_tokens": int(out_details.get("reasoning", 0) or 0),
        "cached_tokens": int(in_details.get("cache_read", 0) or 0),
        "finish_reason": rm.get("finish_reason") or rm.get("stop_reason"),
        "model": model,
    }


def _extraction_digest(ext: Any) -> Dict[str, Any]:
    """Compact, always-retained structural digest of an extraction — the debug gold
    for point/selection errors (e.g. a question that should be 25 coming back 40 and
    inflating achievable points). Defensive getattr; never raises."""
    qs = []
    for q in (getattr(ext, "questions", None) or []):
        qs.append({"q": getattr(q, "question_number", None),
                   "pts": str(getattr(q, "total_points", None))})
    groups = []
    for g in (getattr(ext, "selection_groups", None) or []):
        groups.append({"choose_k": getattr(g, "choose_k", None),
                       "of": list(getattr(g, "of_question_ids", None) or [])})
    return {"total_points": str(getattr(ext, "total_points", None)),
            "questions": qs, "selection_groups": groups}


def extraction_system_prompt(profile=None) -> str:
    """The extraction system prompt for a subject profile (None ⇒ the CS baseline).

    Multisubject seam (2026-09-08): `computer_science` IS `EXTRACTION_SYSTEM_PROMPT`
    byte-for-byte (sha-pinned in tests/subjects/test_prompt_identity.py). Another
    profile APPENDS its <= 12-line F-1 section; nothing above it is rewritten.
    """
    if profile is None or profile.extraction_fragment is None:
        return EXTRACTION_SYSTEM_PROMPT
    return EXTRACTION_SYSTEM_PROMPT + "\n\n" + profile.extraction_fragment


async def _call_llm(
    rendered_text: str,
    error_feedback: Optional[str] = None,
    deadline: Optional["_Deadline"] = None,
    tracer: Any = NULL_TRACER,
    profile: Any = None,
) -> Tuple[RubricExtraction, Dict[str, Any]]:
    """Single LLM call. If error_feedback is provided, it's appended as correction context.

    Returns (extraction, call_meta) where call_meta carries per-call provenance:
    {"input_tokens", "output_tokens", "finish_reason", "model"}. include_raw=True is
    the instrumentation seam (same convention as the GraderAgent): without it, token
    usage and finish_reason are discarded and a truncated extraction (finish_reason
    'length') is indistinguishable from a merely bad one. Provenance extraction is
    best-effort — it never raises. A structured-output parse failure raises (same
    externally observable behavior as the un-instrumented ainvoke), so the retry /
    error paths are unchanged.

    PR-2: the ainvoke is wrapped in the ONE transport-retry layer — bounded per
    attempt (timeout) and budget-aware (an attempt that cannot fit is refused
    rather than started). A parse failure is classified 'other' and re-raises
    untouched: transport policy never retries content failures.
    """
    from langchain_core.messages import SystemMessage, HumanMessage

    dl = deadline or _Deadline(None)
    timeout_s = _llm_timeout_s()

    provider, model = _get_llm_config()
    llm = _get_llm(provider, model, timeout_s=timeout_s)
    structured = llm.with_structured_output(RubricExtraction, include_raw=True)

    user_content = f"Extract the complete rubric structure from this document.\n\nDOCUMENT:\n{rendered_text}"

    if error_feedback:
        user_content += f"\n\n⚠️ CORRECTION REQUIRED — Your previous extraction had these errors. Fix them:\n{error_feedback}"

    system_prompt = extraction_system_prompt(profile)
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_content),
    ]

    logger.info(f"Step 1: LLM call ({provider}/{model}){' [RETRY]' if error_feedback else ''}")
    # TRACE: one generation span per LLM interaction. Prompt/raw are content-addressed
    # blobs (full tier, retained on failure); the output digest is skeleton tier
    # (always kept). tracer is NULL_TRACER by default ⇒ byte-identical when off.
    with tracer.generation("llm_call", is_retry=bool(error_feedback),
                           provider=provider, model=model) as gen:
        gen.set(prompt_version=_extraction_prompt_version(profile), timeout_s=timeout_s,
                user_chars=len(user_content))
        gen.blob("system_prompt", system_prompt)
        gen.blob("user_message", user_content)
        if error_feedback:
            gen.blob("retry_feedback_in", error_feedback)

        result = await _transport_retry_async(
            lambda: structured.ainvoke(messages),
            attempts=_transport_attempts(), timeout_s=timeout_s, deadline=dl,
            label="extraction LLM call",
        )

        raw = result.get("raw")
        call_meta: Dict[str, Any] = {
            "input_tokens": 0, "output_tokens": 0, "finish_reason": None, "model": model,
        }
        try:  # provenance is best-effort; its failure must never fail the extraction
            call_meta = _call_meta_from_raw(raw, model)
        except Exception as e:  # pragma: no cover — defensive
            logger.warning(f"Step 1: provenance extraction failed (non-fatal): {e}")

        gen.set(input_tokens=call_meta.get("input_tokens"),
                output_tokens=call_meta.get("output_tokens"),
                reasoning_tokens=call_meta.get("reasoning_tokens"),
                cached_tokens=call_meta.get("cached_tokens"),
                finish_reason=call_meta.get("finish_reason"))
        try:  # raw output + any reasoning summary the provider surfaced (best-effort)
            gen.blob("raw_response", getattr(raw, "content", None) or "")
            ak = getattr(raw, "additional_kwargs", None)
            if ak:
                gen.blob("additional_kwargs", ak)
        except Exception:
            pass

        if result.get("parsing_error") is not None or result.get("parsed") is None:
            # Same observable behavior as ainvoke without include_raw (which raises on
            # parse failure). finish_reason is in the message so truncation is diagnosable.
            raise ExtractionError(
                f"structured output parse failed "
                f"(finish_reason={call_meta['finish_reason']}): {result.get('parsing_error')}"
            )

        parsed = result["parsed"]
        try:  # skeleton-tier digest — survives a passing run; catches point/selection errors
            gen.set(output_digest=_extraction_digest(parsed))
        except Exception:
            pass
        return parsed, call_meta


# =============================================================================
# STEP 1b: CLEANER — remove 0-point criteria (crossed out)
# =============================================================================

def _achievable_from_extraction(extraction: "RubricExtraction") -> float:
    """PURE float mirror of ontology compute_achievable_points, over extraction types.

    achievable = Σ(mandatory question totals) + Σ over groups of [top choose_k totals].
    A question in no group is mandatory; with no groups this reduces to Σ all totals
    (the legacy rule — so no-selection documents are provably unaffected). A group
    member number with no matching question contributes 0 (the dangling reference is
    surfaced by _build_response as a warning, never silently corrected here).

    Duplication of the ontology rule is DELIBERATE, following the preflight precedent
    (preflight mirrors ContractCompiler): Step 1c operates on extraction floats before
    ontology objects exist. test_fp123 pins this mirror against the ontology function
    so the two cannot silently drift.
    """
    by_num = {q.question_number: q.total_points for q in extraction.questions}
    grouped: set = set()
    achievable = 0.0
    for g in extraction.selection_groups:
        member_pts = sorted((by_num.get(n, 0.0) for n in g.question_numbers), reverse=True)
        achievable += sum(member_pts[: g.choose_k])
        grouped.update(g.question_numbers)
    achievable += sum(pts for num, pts in by_num.items() if num not in grouped)
    return achievable


def _clean_extraction(extraction: RubricExtraction) -> RubricExtraction:
    """Remove criteria with 0 points (teacher crossed them out).

    Sub-question points are recalculated from remaining criteria.
    Question total_points is NOT recalculated — the document header is authoritative.
    Mutates and returns the same object.
    """
    removed_count = 0

    for q in extraction.questions:
        # Sub_criteria cleaning must run BEFORE the 0-point filter so that a criterion
        # whose entire nested table was crossed out gets zeroed and then removed.
        for c in q.criteria:
            if c.sub_criteria:
                before_sc = len(c.sub_criteria)
                c.sub_criteria = [sc for sc in c.sub_criteria if sc.points > 0]
                removed_here = before_sc - len(c.sub_criteria)
                removed_count += removed_here
                if removed_here > 0:
                    # Recalc ONLY as a consequence of removing crossed-out rows. An
                    # unconditional recalc would silently reconcile a faithful teacher
                    # mismatch (Σ sub_criteria != declared) before validation can see
                    # it — erasing the rubric_mismatch annotation the teacher must review.
                    c.points = sum(sc.points for sc in c.sub_criteria)  # 0 if all removed

        before = len(q.criteria)
        q.criteria = [c for c in q.criteria if c.points > 0]
        removed_count += before - len(q.criteria)

        # Clean sub-question criteria (same order: sub_criteria first, then filter)
        for sq in q.sub_questions:
            for node in [sq] + list(sq.sub_questions):
                for c in node.criteria:
                    if c.sub_criteria:
                        before_sc = len(c.sub_criteria)
                        c.sub_criteria = [sc for sc in c.sub_criteria if sc.points > 0]
                        removed_here = before_sc - len(c.sub_criteria)
                        removed_count += removed_here
                        if removed_here > 0:  # consequence-of-removal only (see above)
                            c.points = sum(sc.points for sc in c.sub_criteria)

                before = len(node.criteria)
                node.criteria = [c for c in node.criteria if c.points > 0]
                removed_here = before - len(node.criteria)
                removed_count += removed_here
                # Recalc node points ONLY as a consequence of removal. Unconditional
                # recalc erases faithful teacher mismatches (e.g. components 1.5+0.5
                # under a declared 'ניקוד: 3 נקודות') that MUST reach validation and
                # become a rubric_mismatch annotation — never-reconcile applies to
                # deterministic code exactly as it applies to the LLM.
                if removed_here > 0 and node.criteria:
                    node.points = sum(c.points for c in node.criteria)

        # Do NOT override q.total_points from the sum of children.
        # The question header ("שאלה 2 - 60 נקודות") is the authoritative source.
        # Sub-question mismatches are caught and reported by validation below.

    # Keep rubric total aligned with the (authoritative) question totals — SELECTION-
    # AWARE: with choose-k groups the achievable total is what the rubric is out of
    # (employee: choose 1 of 15/50/35 → 50; 899371: choose 4 of 6×25 → 100). With no
    # groups this reduces exactly to the legacy Σ(question totals).
    extraction.total_points = _achievable_from_extraction(extraction)

    if removed_count > 0:
        logger.info(f"[CLEAN] Removed {removed_count} crossed-out criteria (0 points)")

    return extraction


# =============================================================================
# STEP 1c: VALIDATION
# =============================================================================

@dataclass
class ValidationIssue:
    code: str
    message: str
    retryable: bool  # True = retry LLM, False = flag for teacher

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


@dataclass
class PointMismatchIssue(ValidationIssue):
    """ValidationIssue carrying structured mismatch data for fingerprint comparison.

    The subtype itself acts as the fingerprint — two instances with identical
    (scope, round(computed,2), round(declared,2)) represent the same persisted
    teacher-rubric error rather than a fixable extraction mistake.

    Design note: the retry NOTE in _build_retry_feedback prevents the LLM from
    hallucinating point adjustments to satisfy the constraint. This fingerprint
    check provides early exit once the LLM confirms it cannot fix the mismatch.
    Both mechanisms are required; neither alone is sufficient.
    """
    scope: str = ""        # "Q2" | "Q2.א" | "RUBRIC"
    computed: float = 0.0  # actual sum of children
    declared: float = 0.0  # declared total_points (authoritative)

    def fingerprint(self) -> tuple:
        return (self.scope, round(self.computed, 2), round(self.declared, 2))


def _selection_satisfiability_issues(
    selection_groups: List["SelectionGroupExtraction"], extracted_numbers: set,
) -> List[ValidationIssue]:
    """A 'choose k of N' selection group is UNSATISFIABLE when fewer than `choose_k`
    of its member questions were extracted — the "choose 4 of 1" bug, where the
    selection LLM correctly read "answer 4" but question segmentation missed or
    MERGED the questions.

    Emitted as a RETRYABLE issue (not a POINT_MISMATCH, so it triggers a retry): the
    _extract_with_retry loop feeds the message back to the model as a CORRECTION,
    prompting it to re-extract every question the selection instruction refers to.
    Non-deterministic re-segmentation usually recovers the missing questions.
    """
    out: List[ValidationIssue] = []
    for g in selection_groups:
        present = sum(1 for n in g.question_numbers if n in extracted_numbers)
        if g.choose_k > present:
            out.append(ValidationIssue(
                code="SELECTION_UNSATISFIABLE",
                message=(
                    f"SELECTION RUBRIC ERROR: the instruction "
                    f"\"{g.label or f'answer {g.choose_k} of {len(g.question_numbers)}'}\" "
                    f"requires answering {g.choose_k} of {len(g.question_numbers)} questions "
                    f"(question numbers {g.question_numbers}), but you extracted only "
                    f"{present} of them (extracted question numbers: {sorted(extracted_numbers)}). "
                    f"You MISSED or MERGED questions. Re-extract EVERY question the selection "
                    f"instruction refers to as its OWN separate top-level question."
                ),
                retryable=True,
            ))
    return out


def _validate_extraction(extraction: RubricExtraction) -> List[ValidationIssue]:
    """Validate extraction for structural and point-sum issues.

    Returns list of issues. Each issue is either:
      - retryable: will trigger an LLM retry with error feedback
      - flag-only: will become a warning for the teacher
    """
    issues: List[ValidationIssue] = []

    for q in extraction.questions:
        qid = f"Q{q.question_number}"

        # --- STRUCTURAL CHECKS (retryable) ---

        # No criteria at all — may be a test doc without rubric tables (legitimate)
        has_direct = len(q.criteria) > 0
        has_sq = len(q.sub_questions) > 0
        if not has_direct and not has_sq:
            issues.append(ValidationIssue(
                code="ZERO_CRITERIA",
                message=f"{qid}: No criteria and no sub-questions found. ",
                retryable=False,
            ))
            continue

        # Sub-questions with missing text — LEAF sub-questions only (P-L1).
        # A BRANCH (splitter) sub-question — one that carries its own sub_questions —
        # legitimately has null task text under the SECTION-8 convention: its prose
        # lives in its nested parts (e.g. bagrut q1.א splits into (1)/(2)). Firing
        # the retryable EMPTY_SQ_TEXT on such a node is a FALSE trigger: it demands
        # text the convention says must not exist, so the retry cannot succeed and
        # burns a full extra LLM call (~200s/draw on bagrut, ~71% of draws), while
        # tempting the model to invent splitter prose. Only LEAF sub-questions carry
        # task text, so only they are checked here.
        for sq in q.sub_questions:
            if not sq.sub_questions and (not sq.text or sq.text.strip() == ""):
                issues.append(ValidationIssue(
                    code="EMPTY_SQ_TEXT",
                    message=f"{qid}.{sq.sub_question_id}: Sub-question exists but has no task text. "
                    "The task instruction starting at the sub-question marker was not extracted.",
                    retryable=True,
                ))

            # SQ with zero criteria — legitimate when the SQ splits into nested
            # parts instead (criteria XOR sub_questions)
            if len(sq.criteria) == 0 and len(sq.sub_questions) == 0:
                # A SCORED part with no criteria is a misread worth one retry; a part the
                # document gives NO points (0 — multisubject Phase 2) is a fact about the
                # document: retrying would only tempt the model to invent criteria for it.
                # CS parts always carry points, so CS behaviour is unchanged.
                issues.append(ValidationIssue(
                    code="SQ_ZERO_CRITERIA",
                    message=f"{qid}.{sq.sub_question_id}: Sub-question has no criteria. "
                    "Check rubric table for criteria prefixed with this sub-question identifier.",
                    retryable=sq.points > 0,
                ))

        # Duplicate sub-question IDs
        sq_ids = [sq.sub_question_id for sq in q.sub_questions]
        seen = set()
        for sid in sq_ids:
            if sid in seen:
                issues.append(ValidationIssue(
                    code="DUPLICATE_SQ_ID",
                    message=f"{qid}: Duplicate sub-question ID '{sid}'. Each sub-question must have a unique identifier.",
                    retryable=True,
                ))
            seen.add(sid)

        # --- SUB_CRITERIA SUM CHECKS (retryable) ---
        # Each criterion with a nested table must have sub_criteria that sum to criterion.points (when sub_criteria exist).

        all_criteria_for_q = list(q.criteria) + [c for sq in q.sub_questions for c in sq.criteria]
        for c in all_criteria_for_q:
            if c.sub_criteria:
                sub_sum = sum(sc.points for sc in c.sub_criteria)
                if abs(sub_sum - c.points) > _SUM_TOLERANCE:
                    issues.append(ValidationIssue(
                        code="POINT_MISMATCH_SUBCRITERIA",
                        message=(
                            f"{qid} criterion '{c.description[:60]}': "
                            f"sub_criteria sum to {sub_sum} but criterion.points is {c.points}. "
                            f"Fix sub_criteria so they sum to {c.points}. "
                            f"Do NOT also list the nested-table rows as separate top-level criteria."
                        ),
                        retryable=True,
                    ))

        # --- POINT SUM CHECKS ---
        # Authority hierarchy: Q.total_points (from document header) is fixed.
        # Children (sub-questions / criteria) must sum to it, not the other way around.

        direct_sum = sum(c.points for c in q.criteria)
        sq_sum = sum(sq.points for sq in q.sub_questions)
        computed = direct_sum + sq_sum
        if abs(computed - q.total_points) > _SUM_TOLERANCE:
            issues.append(PointMismatchIssue(
                code="POINT_MISMATCH_Q",
                message=(
                    f"{qid}: Your sub-questions/criteria sum to {computed} points, "
                    f"but the document header declares {q.total_points} points for this question. "
                    f"Fix the sub-question point allocations so they sum to {q.total_points}. "
                    f"Do NOT change {qid}.total_points — it is set by the document header and is authoritative."
                ),
                retryable=True,
                scope=qid,
                computed=computed,
                declared=q.total_points,
            ))

        # SQ-level: children (criteria, or nested parts) must sum to declared points.
        # The retry message deliberately frames BOTH possibilities — a misread OR a
        # faithful teacher inconsistency — and forbids reconciliation. "Adjust your
        # values to sum to N" would instruct the model to falsify faithful extractions
        # (the exact deduction-erasing failure the never-reconcile rule exists to stop);
        # a persistent mismatch is downgraded to a rubric_mismatch annotation instead.
        for sq in q.sub_questions:
            if sq.criteria and sq.sub_questions:
                issues.append(ValidationIssue(
                    code="SQ_STRUCTURE_EXCLUSIVITY",
                    message=(
                        f"{qid}.{sq.sub_question_id}: has BOTH criteria and nested "
                        f"sub_questions. A sub-question has one or the other, never both — "
                        f"move the criteria under the nested parts they belong to."
                    ),
                    retryable=True,
                ))
                continue
            child_sum = (sum(isq.points for isq in sq.sub_questions)
                         if sq.sub_questions else sum(c.points for c in sq.criteria))
            if abs(child_sum - sq.points) > _SUM_TOLERANCE:
                issues.append(PointMismatchIssue(
                    code="POINT_MISMATCH_SQ",
                    message=(
                        f"{qid}.{sq.sub_question_id}: children sum to {child_sum}, "
                        f"but the sub-question declares {sq.points} points. Re-check the "
                        f"document: either you misread a point value (fix it to what is "
                        f"written), or the teacher's own numbers are inconsistent — in "
                        f"that case COPY them faithfully and do NOT invent adjustments."
                    ),
                    retryable=True,
                    scope=f"{qid}.{sq.sub_question_id}",
                    computed=child_sum,
                    declared=sq.points,
                ))
            for isq in sq.sub_questions:
                icsum = sum(c.points for c in isq.criteria)
                if isq.criteria and abs(icsum - isq.points) > _SUM_TOLERANCE:
                    issues.append(PointMismatchIssue(
                        code="POINT_MISMATCH_SQ",
                        message=(
                            f"{qid}.{sq.sub_question_id}.{isq.sub_question_id}: criteria "
                            f"sum to {icsum}, but the declared score line says {isq.points} "
                            f"points. Re-check the document: fix a misread, or if the "
                            f"teacher's own numbers are inconsistent, COPY them faithfully "
                            f"— do NOT invent adjustments."
                        ),
                        retryable=True,
                        scope=f"{qid}.{sq.sub_question_id}.{isq.sub_question_id}",
                        computed=icsum,
                        declared=isq.points,
                    ))

    # Rubric-level: question headers must sum to 100 — a misread-detection prior that
    # is only defensible when EVERY question is mandatory. With selection groups the
    # offered total legitimately exceeds the achievable total (899371: 6×25=150,
    # choose 4 → 100) and the exam's real total need not be 100 at all (employee:
    # choose 1 of 15/50/35 → a 50-point test). Firing here would fabricate a
    # rubric_mismatch annotation on a correct extraction, so the check applies only
    # to no-selection documents; per-question and per-group checks carry the signal
    # for the rest.
    q_total = sum(q.total_points for q in extraction.questions)
    if not extraction.selection_groups and abs(q_total - 100) > _SUM_TOLERANCE:
        suspect = [
            f"Q{q.question_number}={q.total_points}"
            for q in extraction.questions
        ]
        issues.append(PointMismatchIssue(
            code="POINT_MISMATCH_RUBRIC",
            message=(
                f"Question totals sum to {q_total} (expected 100). "
                f"Check each question header in the document for its declared point value: {', '.join(suspect)}. "
                f"Extract total_points exactly as stated in each question header."
            ),
            retryable=True,
            scope="RUBRIC",
            computed=q_total,
            declared=100.0,
        ))

    # Selection satisfiability — a 'choose k of N' group with fewer than k extracted
    # questions is the "choose 4 of 1" bug; retryable so the model re-extracts the
    # missed/merged questions.
    extracted_numbers = {q.question_number for q in extraction.questions}
    issues.extend(_selection_satisfiability_issues(extraction.selection_groups, extracted_numbers))

    return issues


def _build_retry_feedback(issues: List[ValidationIssue]) -> str:
    """Format retryable issues as LLM correction feedback."""
    retryable = [i for i in issues if i.retryable]
    if not retryable:
        return ""

    lines = []
    if any(i.code in _MISMATCH_CODES for i in retryable):
        lines.append(
            "NOTE for POINT_MISMATCH errors: correct them ONLY if you can identify "
            "a clear extraction mistake (wrong point value copied, missing or duplicate criterion). "
            "If the original document already has this mismatch, keep your extraction faithful "
            "to the document — do NOT invent or adjust point values to satisfy the sum."
            # Hallucination risk: an over-helpful LLM might change point values to satisfy the
            # constraint rather than leaving the faithful mismatch in place. The fingerprint check
            # in _extract_with_retry handles cases where the LLM hallucinated a "fix" — the
            # fingerprint changes, so it's not downgraded. Monitor logs for unexpected churn.
        )
    for i, issue in enumerate(retryable, 1):
        lines.append(f"{i}. {issue.message}")

    return "\n".join(lines)


def _is_point_mismatch(issue: ValidationIssue) -> bool:
    """The never-retry issue class (PIPELINE 3.1.0 / PR B): POINT_MISMATCH_* —
    the PointMismatchIssue codes (Q/SQ/RUBRIC) plus POINT_MISMATCH_SUBCRITERIA."""
    return issue.code.startswith("POINT_MISMATCH")


def _get_mismatch_fingerprints(issues: List[ValidationIssue]) -> set:
    """Return fingerprints of all currently retryable PointMismatchIssue instances."""
    return {
        i.fingerprint()
        for i in issues
        if isinstance(i, PointMismatchIssue) and i.retryable
    }


def _downgrade_persistent_mismatches(
    issues: List[ValidationIssue],
    persistent_fps: set,
) -> List[ValidationIssue]:
    """Convert mismatch issues whose fingerprint survived the previous retry to non-retryable warnings.

    Persistent = same (scope, computed, declared) after the LLM was given correction feedback.
    This is strong evidence the document owns the mismatch, not the extraction.
    """
    result = []
    for issue in issues:
        if (
            isinstance(issue, PointMismatchIssue)
            and issue.retryable
            and issue.fingerprint() in persistent_fps
        ):
            if issue.code == "POINT_MISMATCH_SQ":
                warning_message = (
                    f"אזהרה: סכום הקריטריונים של תת-שאלה {issue.scope} הוא {issue.computed:.4g} נקודות, "
                    f"אך תת-השאלה מצהירה על {issue.declared:.4g} נקודות — "
                    f"ייתכן שמדובר בשגיאה בשאלון המקורי. יש לבדוק ידנית."
                )
            elif issue.code == "POINT_MISMATCH_Q":
                warning_message = (
                    f"אזהרה: סכום הנקודות של תת-השאלות ב{issue.scope} הוא {issue.computed:.4g} נקודות, "
                    f"אך כותרת השאלה מצהירה על {issue.declared:.4g} נקודות — "
                    f"ייתכן שמדובר בשגיאה בשאלון המקורי. יש לבדוק ידנית."
                )
            else:  # POINT_MISMATCH_RUBRIC
                warning_message = (
                    f"אזהרה: סכום הנקודות של כל השאלות הוא {issue.computed:.4g} נקודות במקום 100 — "
                    f"ייתכן שמדובר בשגיאה בשאלון המקורי. יש לבדוק ידנית."
                )
            result.append(dc_replace(
                issue,
                code="RUBRIC_MISMATCH_WARNING",
                message=warning_message,
                retryable=False,
            ))
            logger.info(
                "[RUBRIC_MISMATCH] teacher rubric error detected — scope=%s computed=%s declared=%s",
                issue.scope, issue.computed, issue.declared,
            )
        else:
            result.append(issue)
    return result


# =============================================================================
# STEP 1: EXTRACT WITH RETRY LOOP
# =============================================================================

def _extraction_prompt_version(profile=None) -> str:
    """D-16 stamp: `3.10.0-fixsource` for CS (unchanged), `…+<subject>` otherwise."""
    if profile is None:
        return EXTRACTION_PROMPT_VERSION
    from app.subjects import prompt_version
    return prompt_version(EXTRACTION_PROMPT_VERSION, profile)


async def _extract_with_retry(
    rendered_text: str,
    emit: Optional[Callable[..., Awaitable[None]]] = None,
    deadline: Optional["_Deadline"] = None,
    tracer: Any = NULL_TRACER,
    profile: Any = None,
) -> Tuple[RubricExtraction, List[ValidationIssue], int, Dict[str, Any]]:
    """Extract → Clean → Validate → Retry if needed.

    Persistent mismatch detection: if the identical point mismatch (same scope,
    same computed/declared values) survives a retry unchanged, the document owns
    the mismatch — not the extraction. These are downgraded to non-retryable
    RUBRIC_MISMATCH_WARNING issues so they surface as Annotations rather than
    burning another LLM call.

    Returns:
        (extraction, remaining_issues, retry_count, llm_meta) where llm_meta
        accumulates token usage across ALL attempts (cost is total spend, not
        last-call spend) and carries the LAST call's finish_reason + model (the
        returned extraction came from the last call, so its finish_reason is the
        one that determines validity).
    """
    retry_count = 0
    error_feedback = None
    all_seen_fps: set = set()  # fingerprints seen across ALL previous attempts (accumulates)
    llm_meta: Dict[str, Any] = {"input_tokens": 0, "output_tokens": 0,
                                "reasoning_tokens": 0, "cached_tokens": 0,
                                "finish_reason": None, "model": None}

    dl = deadline or _Deadline(None)
    entry_need = _llm_timeout_s() + _DEADLINE_ENTRY_RESERVE_S   # (1) T + 20

    for attempt in range(_MAX_RETRIES + 1):
        # PR-2 deadline layer (1): refuse to START a logical call we cannot afford.
        # This is sound only because the transport layer ALSO refuses attempts that
        # do not fit — a logical call is up to (attempts x T), not one T.
        if not dl.can_fit(entry_need):
            raise ExtractionError(
                f"time budget exhausted after {attempt} validation attempt(s) "
                f"(need {entry_need:.0f}s to start another, {dl.remaining():.0f}s left)"
            )

        # LLM call
        if emit is not None:
            await emit("llm_call", attempt=attempt + 1,
                       detail="retry with correction feedback" if error_feedback else None)
        extraction, call_meta = await _call_llm(rendered_text, error_feedback, deadline=dl, tracer=tracer,
                                                profile=profile)
        llm_meta["input_tokens"] += call_meta["input_tokens"]
        llm_meta["output_tokens"] += call_meta["output_tokens"]
        llm_meta["reasoning_tokens"] += call_meta.get("reasoning_tokens", 0) or 0
        llm_meta["cached_tokens"] += call_meta.get("cached_tokens", 0) or 0
        llm_meta["finish_reason"] = call_meta["finish_reason"]
        llm_meta["model"] = call_meta["model"]

        # Clean (remove 0-point criteria)
        extraction = _clean_extraction(extraction)

        # Validate
        if emit is not None:
            await emit("validate", attempt=attempt + 1,
                       input_tokens=llm_meta["input_tokens"],
                       output_tokens=llm_meta["output_tokens"])
        with tracer.operation("validate", attempt=attempt + 1) as _v:
            issues = _validate_extraction(extraction)
            _v.set(n_issues=len(issues),
                   issues=[{"code": i.code, "message": i.message, "retryable": i.retryable}
                           for i in issues])

        # After any retry: downgrade mismatches whose fingerprint was seen in ANY
        # previous attempt. Using an accumulated set (not just the last round)
        # handles the case where the LLM temporarily worsens a mismatch on one
        # retry (different fingerprint) then reverts to the original on the next —
        # the mismatch is still persistent, just not monotonically so.
        if all_seen_fps:
            current_fps = _get_mismatch_fingerprints(issues)
            persistent = current_fps & all_seen_fps
            if persistent:
                issues = _downgrade_persistent_mismatches(issues, persistent)
                logger.info(
                    f"[VALIDATE] Downgraded {len(persistent)} persistent mismatch(es) "
                    f"to rubric warnings: {persistent}"
                )

        retryable = [i for i in issues if i.retryable]

        # PIPELINE 3.1.0 (PR B): point-mismatches never TRIGGER a retry. With both
        # never-reconcile tripwires live (annotation_match + pedagogical_match), a
        # retry can only "succeed" on a faithful teacher error by falsifying the
        # numbers — pure cost plus an explicit temptation to reconcile (measured:
        # 5/5 recurrence, $0.92/352s per burn, 0 genuine misreads on the corpus).
        # A genuine misread still surfaces as the same teacher-visible
        # rubric_mismatch annotation — the designed review-first channel. Other
        # retryable classes (empty text, structure, duplicates, parse) still retry,
        # and mismatches are then re-evaluated after that retry exactly as before.
        trigger = [i for i in retryable if not _is_point_mismatch(i)]

        if not trigger:
            if retryable:
                # Only point-mismatches remain: no retry will occur, so downgrade
                # IMMEDIATELY through the same _downgrade_persistent_mismatches
                # path the post-retry flow uses — the resulting
                # RUBRIC_MISMATCH_WARNING (and its rubric_mismatch annotation via
                # _build_response) is identical in type and anchor.
                fps = _get_mismatch_fingerprints(issues)
                if fps:
                    issues = _downgrade_persistent_mismatches(issues, fps)
                    logger.info(
                        f"[VALIDATE] Attempt {attempt + 1}: {len(fps)} point-mismatch(es) "
                        f"downgraded to rubric warnings WITHOUT retry (non-retryable class)"
                    )
            logger.info(f"[VALIDATE] Attempt {attempt + 1}: PASS ({len(issues)} flag-only issues)")
            return extraction, issues, retry_count, llm_meta

        if attempt < _MAX_RETRIES:
            # Build feedback and retry
            retry_count += 1
            all_seen_fps.update(_get_mismatch_fingerprints(issues))  # accumulate, never replace
            error_feedback = _build_retry_feedback(issues)
            with tracer.operation("retry_decision", attempt=attempt + 1) as _rd:
                _rd.set(trigger_codes=[i.code for i in trigger])
                _rd.blob("feedback_out", error_feedback)
            if emit is not None:
                await emit("retry", attempt=attempt + 1,
                           detail=f"{len(retryable)} retryable issue(s)")
            logger.warning(
                f"[VALIDATE] Attempt {attempt + 1}: {len(retryable)} retryable issues → retrying\n"
                + "\n".join(f"  • {i}" for i in retryable)
            )
        else:
            # Max retries exhausted — return with remaining issues
            logger.warning(
                f"[VALIDATE] Attempt {attempt + 1}: {len(retryable)} retryable issues remain after {_MAX_RETRIES} retries"
            )
            return extraction, issues, retry_count, llm_meta

    # Should never reach here, but satisfy type checker
    return extraction, issues, retry_count, llm_meta


# =============================================================================
# STEP 2: BUILD ONTOLOGY OBJECTS
# =============================================================================

def _build_criterion(cid: str, idx: int, ext: CriterionExtraction) -> Criterion:
    from app.services.criterion_identity import new_uid
    pts = Decimal(str(ext.points))
    sub_criteria = (
        [
            SubCriterion(
                sub_criterion_id=f"{cid}.sc{i}",
                uid=new_uid(),          # [P-0] stable identity, minted here
                index=i,
                description=sc.description,
                points=Decimal(str(sc.points)),
            )
            for i, sc in enumerate(ext.sub_criteria)
        ]
        if ext.sub_criteria else None
    )
    return Criterion(
        criterion_id=cid,
        uid=new_uid(),                  # [P-0] stable identity, minted here
        index=idx,
        description=ext.description,
        points=pts,
        sub_criteria=sub_criteria,
    )


def _build_response(
    extraction: RubricExtraction,
    name: str,
    validation_issues: List[ValidationIssue],
    profile: Any = None,
) -> Tuple[ExtractRubricResponse, List[str]]:
    """Build real ontology objects from validated extraction.

    Returns (response, warnings). `profile` (subject seam) supplies the subject
    key and the default question type; None ⇒ the CS baseline, byte-identical
    to the pre-seam output (`coding_task` on every question, subject CS).
    """
    if profile is None:
        from app.subjects import get_profile as _get_subject_profile
        profile = _get_subject_profile("computer_science")
    warnings: List[str] = []
    questions: List[Question] = []

    for q in extraction.questions:
        qid = f"q{q.question_number}"

        sqs: List[SubQuestion] = []
        for si, sq in enumerate(q.sub_questions):
            sid = sq.sub_question_id
            crits = [_build_criterion(f"{qid}.{sid}.c{i}", i, c) for i, c in enumerate(sq.criteria)]
            inner: List[SubQuestion] = []
            for ii, isq in enumerate(sq.sub_questions):
                iid = isq.sub_question_id
                icrits = [_build_criterion(f"{qid}.{sid}.{iid}.c{i}", i, c)
                          for i, c in enumerate(isq.criteria)]
                inner.append(SubQuestion(
                    sub_question_id=iid, index=ii, text=isq.text,
                    points=Decimal(str(isq.points)), example_solution=isq.example_solution,
                    criteria=icrits,
                ))
            sqs.append(SubQuestion(
                sub_question_id=sid, index=si, text=sq.text,
                points=Decimal(str(sq.points)), example_solution=sq.example_solution,
                criteria=crits, sub_questions=inner,
            ))

        direct = [_build_criterion(f"{qid}.c{i}", i, c) for i, c in enumerate(q.criteria)]

        questions.append(Question(
            # Amendment 2 (ruled 2026-09-08): the extractor emits no type — the
            # question gets the SUBJECT PROFILE's default (CS: coding_task, as always).
            question_id=qid, question_type=profile.default_question_type,
            question_text=q.question_text, total_points=Decimal(str(q.total_points)),
            criteria=direct, sub_questions=sqs, example_solution=q.example_solution,
        ))

    # Persistent mismatch issues (downgraded in _extract_with_retry) become WARNING annotations.
    # severity=WARNING gates save with teacher acknowledgment — the teacher must verify the
    # original rubric's point allocation before the draft can be compiled to a contract.
    mismatch_annotations: List[Annotation] = [
        Annotation(
            annotation_type="rubric_mismatch",
            severity=AnnotationSeverity.WARNING,
            message=issue.message,
            # RUBRIC scope = global annotation; Q/SQ scopes → lowercase to match frontend question_id
            # e.g. "Q2" → "q2", "Q2.א" → "q2.א"  (Hebrew chars unaffected by .lower())
            target_id=None if issue.scope == "RUBRIC" else issue.scope.lower(),
        )
        for issue in validation_issues
        if isinstance(issue, PointMismatchIssue) and issue.code == "RUBRIC_MISMATCH_WARNING"
    ]

    # Selection groups (FP1): map question numbers to q{n} ids. A member number with
    # no extracted question is a WARNING string, deliberately NOT an annotation —
    # annotations are GT-compared by the eval (annotation_match), so a spurious one
    # fabricates a gate failure; warnings are teacher-visible but unscored.
    extracted_ids = {q.question_id for q in questions}
    selection_groups: List[SelectionGroup] = []
    for gi, g in enumerate(extraction.selection_groups):
        member_ids = [f"q{n}" for n in g.question_numbers]
        for mid in member_ids:
            if mid not in extracted_ids:
                warnings.append(
                    f"[SELECTION_DANGLING_MEMBER] group sg{gi} references {mid}, "
                    f"which was not extracted as a question (contributes 0 to achievable)."
                )
        selection_groups.append(SelectionGroup(
            group_id=f"sg{gi}", choose_k=g.choose_k,
            of_question_ids=member_ids, label=g.label,
        ))

    resp = ExtractRubricResponse(
        rubric_id=str(uuid4()), rubric_name=name or extraction.document_title or "",
        subject=profile.key, total_points=Decimal(str(extraction.total_points)),
        questions=questions,
        selection_groups=selection_groups,
        annotations=mismatch_annotations,
        extraction_metadata={"pipeline_version": PIPELINE_VERSION, "method": "structured_output_v3",
                             # Tier-B prompt identity travels with the run (2026-08-24): a
                             # change to that prompt is otherwise invisible to provenance.
                             "tier_b_prompt_version": _tier_b_prompt_version()},
    )

    # Convert non-mismatch validation issues to human-readable warnings
    for issue in validation_issues:
        if issue.code != "RUBRIC_MISMATCH_WARNING":
            warnings.append(f"[{issue.code}] {issue.message}")

    # Step 2b: Compilation preflight — verify INV-1 will pass
    preflight_warnings = _compilation_preflight(resp)
    warnings.extend(preflight_warnings)

    return resp, warnings


# =============================================================================
# STEP 2b: COMPILATION PREFLIGHT
# =============================================================================

def _compilation_preflight(response: ExtractRubricResponse) -> List[str]:
    """Simulate compilation checks (INV-1, INV-3) to catch issues before save.

    These are the exact checks ContractCompiler runs. If they fail here,
    they'll fail at save time with a CompilationError.
    """
    warnings: List[str] = []

    for q in response.questions:
        # INV-1 check 1: Q total vs criteria + SQ
        direct_sum = sum(c.points for c in q.criteria)
        sq_sum = sum(sq.points for sq in q.sub_questions)
        declared = q.total_points
        diff = abs(declared - (direct_sum + sq_sum))
        if diff > Decimal(str(_COMPILE_TOLERANCE)):
            warnings.append(
                f"[PREFLIGHT_INV1] {q.question_id}: criteria+SQ sum "
                f"({direct_sum + sq_sum}) differs from total ({declared}) by {diff}"
            )

        # INV-1 check 2: each SQ (recursively) — parent nodes vs nested-part sums,
        # leaf nodes vs criteria sums. Mirrors the ontology's recursive
        # StructureExclusivity shape (criteria XOR sub_questions).
        def _walk_sq(sq, path):
            if sq.sub_questions:
                child_sum = sum(isq.points for isq in sq.sub_questions)
                d = abs(sq.points - child_sum)
                if d > Decimal(str(_COMPILE_TOLERANCE)):
                    warnings.append(
                        f"[PREFLIGHT_INV1] {path}: nested-part sum "
                        f"({child_sum}) differs from SQ points ({sq.points}) by {d}"
                    )
                for isq in sq.sub_questions:
                    _walk_sq(isq, f"{path}.{isq.sub_question_id}")
            else:
                sq_crit_sum = sum(c.points for c in sq.criteria)
                sq_diff = abs(sq.points - sq_crit_sum)
                if sq_diff > Decimal(str(_COMPILE_TOLERANCE)):
                    warnings.append(
                        f"[PREFLIGHT_INV1] {path}: criteria sum "
                        f"({sq_crit_sum}) differs from SQ points ({sq.points}) by {sq_diff}"
                    )
        for sq in q.sub_questions:
            _walk_sq(sq, f"{q.question_id}.{sq.sub_question_id}")

        # INV-3: if sub_criteria present, their sum must equal criterion.points (vacuous otherwise)
        for c in q.all_criteria:
            if not c.sub_criteria:
                continue
            sub_sum = sum(sc.points for sc in c.sub_criteria)
            c_diff = abs(c.points - sub_sum)
            if c_diff > Decimal(str(_COMPILE_TOLERANCE)):
                warnings.append(
                    f"[PREFLIGHT_INV3] {c.criterion_id}: sub_criteria sum ({sub_sum}) "
                    f"differs from points ({c.points}) by {c_diff}"
                )

    return warnings


# =============================================================================
# PUBLIC API
# =============================================================================

async def extract_rubric_from_docx(
    file_bytes: bytes,
    extraction_config: Optional[ExtractionConfig] = None,
    name: Optional[str] = None,
    description: Optional[str] = None,
    question_purposes: Optional[Dict[str, str]] = None,
    test_topic: Optional[str] = None,
    on_progress: Optional[OnProgress] = None,
    deadline_seconds: Optional[float] = None,
    tracer: Optional[Any] = None,
    source_filename: Optional[str] = None,
) -> ExtractionResult:
    """Extract rubric from DOCX — v3 pipeline with validation + retry.

    `source_filename` (multisubject Phase 2a, D-8): selects the render stage —
    a PDF is rasterized into the rubric-read stage; a DOCX takes the deterministic
    render unless it is pages-as-images (then the same stage). None ⇒ DOCX.

    on_progress: optional pure-data stage callback (see ProgressEvent). None
    (default) is byte-identical to pre-seam behavior; failures are swallowed.

    tracer: optional injected tracelog (see trace.py). None (default) resolves to a
    no-op NULL_TRACER — byte-identical to no tracing. Captures the full span tree
    (render / llm_call generations / validate issues / retry feedback) for debugging
    the model's thought process; the caller owns persistence via tracer.finish().

    deadline_seconds (PR-2): total wall budget for THIS extraction. None (default)
    => unbounded => byte-identical to pre-PR-2 behavior. The eval runner passes
    None, so eval runs and the gate are untouched BY CONSTRUCTION — the deadline
    path is production-only (the PR-1 task runner passes 840 - pre-work elapsed).
    A controlled in-budget failure (durable `failed` + readable message + working
    retry) beats a Cloud Run SIGKILL into a stranded 'extracting' row.
    """
    from .parser_render import render_docx_to_markdown

    config = extraction_config or ExtractionConfig()
    # Subject seam: the profile selects the F-1 fragment, the default question
    # type and the D-16 stamp. An unknown key raises here, before any LLM call
    # (the API already 422'd it; a stale queued row fails loudly, never as CS).
    from app.subjects import get_profile as _get_subject_profile
    profile = _get_subject_profile(config.subject)
    start = time.time()
    metrics = ExtractionMetrics()
    deadline = _Deadline(deadline_seconds)
    tr = _resolve_tracer(tracer)  # NULL_TRACER when off ⇒ byte-identical

    async def _emit(stage: str, **kw: Any) -> None:
        await _emit_progress(on_progress, ProgressEvent(
            stage=stage, elapsed_s=round(time.time() - start, 2), **kw))

    try:
        # Step 0: Parse + Render
        with tr.operation("render") as _rsp:
            t0 = time.time()
            # Render stage selection (Phase 2a): DOCX-with-text → the deterministic
            # render, byte-identical to render_docx_to_markdown; pages-as-images
            # DOCX or any PDF → rubric-read/rr1.0 over the page images.
            from .image_render import render_source
            rendered, render_report = await render_source(
                file_bytes, source_filename,
                deadline_s=(deadline.remaining() if deadline.bounded else None))
            metrics.render_time_seconds = time.time() - t0
            metrics.rendered_chars = len(rendered)
            _rsp.set(chars=len(rendered), stage=render_report.stage).blob("rendered_markdown", rendered)
        render_report.log(job_label=f"name={name!r}")
        logger.info(f"v3 Step 0: {len(rendered)} chars in {metrics.render_time_seconds:.2f}s "
                    f"(stage={render_report.stage})")
        await _emit("render", detail=f"{len(rendered)} chars")

        # Step 1: Extract + Clean + Validate + Retry
        t1 = time.time()
        with tr.operation("extract_loop") as _elsp:
            extraction, issues, retry_count, llm_meta = await _extract_with_retry(
                rendered, emit=_emit if on_progress is not None else None,
                deadline=deadline, tracer=tr, profile=profile)
            _elsp.set(retries=retry_count, n_remaining_issues=len(issues))
        metrics.llm_time_seconds = time.time() - t1
        metrics.retry_count = retry_count
        metrics.input_tokens = llm_meta["input_tokens"]
        metrics.output_tokens = llm_meta["output_tokens"]
        metrics.reasoning_tokens = llm_meta.get("reasoning_tokens", 0)
        metrics.cached_tokens = llm_meta.get("cached_tokens", 0)
        metrics.finish_reason = llm_meta["finish_reason"]
        metrics.llm_model = llm_meta["model"]

        # Step 2: Build ontology objects (the subject is stamped from the job's
        # profile here — never from the model, D-10)
        await _emit("build")
        rubric_name = name or test_topic or ""
        response, warnings = _build_response(extraction, rubric_name, issues, profile=profile)
        if profile.rescale_to_exam:
            # D-13 (Phase 2b): the teacher's per-question-100 weights → the exam's
            # real total on the 0.25 grid. Deterministic code, never the model.
            from .rescale_to_exam import rescale_to_exam
            response = rescale_to_exam(response)
        if description:
            response.description = description

        # Step 2c: Pedagogical-mistake detection (best-effort; never breaks extraction).
        # Tier A (deterministic point-sum / selection-normalization) always runs; Tier B
        # (LLM adjudication of a structural trigger) runs only when enabled, and only when
        # a trigger fires. Read-only over the faithful Draft; runs in a thread so the sync
        # LLM .invoke does not stall the event loop.
        #
        # A5 — ADVISORY-SCAN PROVENANCE. Whether this scan completed is a property of
        # THIS extraction, so it is stamped into extraction_metadata alongside the other
        # provenance, and therefore survives into the saved draft. A job-level warning
        # cannot: it is not part of the draft and vanishes on reopen, which would let an
        # empty advisory list read as a clean bill of health after a partial scan — the
        # exact silence the honesty rule exists to prevent.
        advisory_scan_reason: Optional[str] = None
        try:
            await _emit("pedagogical", detail="start")
            # B4: swallowed Tier-B failures surface as pipeline warnings — they set
            # requires_review (an unadjudicated structural anomaly warrants review-first)
            # and reach the eval artifacts instead of dying in stdout.
            step2c_warnings: List[str] = []

            # PR-2 deadline layer (3): Tier B is SEPARATE LLM work that runs AFTER
            # the validation loop — since D6, one call PER ANOMALOUS QUESTION.
            # Without this guard a loop that legitimately spent its budget could
            # still launch Tier-B calls and blow straight past the Cloud Run kill.
            # The entry check requires room for ONE attempt; each subsequent
            # per-question call re-checks the deadline inside the shared transport
            # layer and degrades per-question (the detector's isolation), so a
            # budget exhausted mid-scan keeps every fix already chosen. Tier B is
            # BEST-EFFORT (its failures already degrade to warnings), so when the
            # budget cannot hold one attempt we SKIP it — the extraction still
            # succeeds with Tier A results, exactly as it does when Tier B fails.
            # The string is deliberately distinct from a Tier-B transport failure
            # so artifacts can never conflate the two.
            adjudicator = None
            tier_b_need = _llm_timeout_s() + _DEADLINE_ATTEMPT_RESERVE_S
            if config.detect_pedagogical_mistakes:
                if deadline.can_fit(tier_b_need):
                    adjudicator = _make_adjudicator(deadline=deadline)
                else:
                    skip_msg = (
                        f"Tier B skipped: time budget — {deadline.remaining():.0f}s left, "
                        f"need {tier_b_need:.0f}s for one attempt. Tier A results kept."
                    )
                    logger.warning(f"v3 Step 2c: {skip_msg}")
                    step2c_warnings.append(skip_msg)
                    advisory_scan_reason = "tier_b_skipped_time_budget"
            else:
                advisory_scan_reason = "tier_b_disabled"

            with tr.operation("pedagogical", tier_b_enabled=adjudicator is not None) as _psp:
                response.pedagogical_mistakes = await asyncio.to_thread(
                    detect_pedagogical_mistakes, response, rendered,
                    llm=adjudicator, warnings_sink=step2c_warnings,
                )
                _psp.set(mistakes=[{"kind": getattr(m.kind, "value", str(m.kind)),
                                    "target": getattr(m, "target_id", None)}
                                   for m in (response.pedagogical_mistakes or [])])
            await _emit("pedagogical", detail="done")
            warnings.extend(step2c_warnings)
            if response.pedagogical_mistakes:
                logger.info(
                    f"v3 Step 2c: {len(response.pedagogical_mistakes)} pedagogical mistake(s) detected"
                )
        except Exception as e:
            logger.warning(f"v3 Step 2c pedagogical-mistake detection failed (non-fatal): {e}")
            warnings.append(f"Step 2c pedagogical-mistake detection failed (non-fatal): {e}")
            advisory_scan_reason = "detector_failed"

        # Stamp the outcome. 'complete' is claimed ONLY when the full scan ran; every
        # other path names WHY it did not, and a draft with no stamp at all (saved
        # before this version) is treated as unknowable — never as complete.
        response.extraction_metadata["advisory_scan"] = "partial" if advisory_scan_reason else "complete"
        if advisory_scan_reason:
            response.extraction_metadata["advisory_scan_reason"] = advisory_scan_reason

        metrics.total_time_seconds = time.time() - start
        metrics.num_questions = len(response.questions)
        metrics.num_criteria = response.num_criteria

        logger.info(
            f"v3 complete: {metrics.num_questions}q, {metrics.num_criteria}c, "
            f"{len(warnings)}w, {retry_count} retries, {metrics.total_time_seconds:.1f}s"
        )
        await _emit("complete",
                    input_tokens=metrics.input_tokens, output_tokens=metrics.output_tokens,
                    detail=f"{metrics.num_questions}q, {metrics.num_criteria}c")

        return ExtractionResult(
            response=response,
            metadata={
                "pipeline_version": PIPELINE_VERSION,
                "subject": config.subject,
                # D-16: the stamp the job row and the eval record carry.
                "prompt_version": _extraction_prompt_version(profile),
                "retry_count": retry_count,
                # Phase 2a: which render stage ran, and the OMML/image counts (P-3).
                "render": render_report.as_dict(),
            },
            metrics=metrics, warnings=warnings,
            requires_review=len(warnings) > 0 or bool(response.pedagogical_mistakes),
        )
    except Exception as e:
        logger.error(f"v3 pipeline error: {e}", exc_info=True)
        raise ExtractionError(f"Pipeline failed: {e}") from e