"""
GraderAgent — bounded-parallel, exception-isolating grading orchestrator.

grade(gradable_test) -> GradedTestDraft

Design invariants:
  D1 — No persistence. Returns a GradedTestDraft in memory; S8 persists it.
  D2 — Bounded parallel (Semaphore 5). return_exceptions=True for isolation.
  D3 — Output totality: len(scope_outcomes) == len(scopes) always.
  GA-3 — One surgical transient retry per scope; no retry on content failures.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import openai
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.schemas.gradable import GradableScope, GradableTest
from app.schemas.graded_test_draft import (
    CriterionOutcome,
    GradedTestDraft,
    GradingAnnotation,
    ScopeOutcome,
    SubCriterionOutcome,
)
from app.schemas.ontology_types import (
    AnnotationSeverity,
    FlaggedOutcome,
    FlagReason,
    NumericPolicy,
)
from app.agents.grader.prompt import GRADING_PROMPT_VERSION, SYSTEM_PROMPT, build_user_message
from app.agents.grader.schemas import QuestionGradingResponse
from app.agents.grader.validator import ValidatedTerminalGrade, validate_scope_grading

logger = logging.getLogger(__name__)

MAX_CONCURRENT_SCOPES = 5
RETRY_BACKOFF_MIN = 0.5   # seconds
RETRY_BACKOFF_MAX = 2.0   # seconds — jitter prevents rate-limit re-collision

# Transient transport failures — same input retried once will likely succeed.
# Non-transient (schema parse failures, auth errors, ValueError from parsing_error)
# are NOT retried per GA-3.
TRANSIENT_EXCEPTIONS = (
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.InternalServerError,
)


@dataclass
class _ScopeResult:
    """Internal wrapper returned by _grade_scope — carries outcome + its annotations."""
    outcome: ScopeOutcome
    annotations: List[GradingAnnotation] = field(default_factory=list)


def _scope_target_id(scope: GradableScope) -> str:
    if scope.sub_question_id:
        return f"{scope.question_id}.{scope.sub_question_id}"
    return scope.question_id


def _get_terminal_map(scope: GradableScope) -> Dict[str, Decimal]:
    """Map each terminal criterion ID → its max points. Mirrors validator helper."""
    terminals: Dict[str, Decimal] = {}
    for criterion in scope.criteria:
        if criterion.sub_criteria:
            for sc in criterion.sub_criteria:
                terminals[sc.sub_criterion_id] = sc.points
        else:
            terminals[criterion.criterion_id] = criterion.points
    return terminals


def _build_zero_criterion_outcomes(
    scope: GradableScope,
    flag_reason: FlagReason,
) -> List[CriterionOutcome]:
    """Build zero-point CriterionOutcomes for every criterion in a scope."""
    outcomes: List[CriterionOutcome] = []
    for criterion in scope.criteria:
        flag = FlaggedOutcome(criterion_id=criterion.criterion_id, reason=flag_reason)
        if criterion.sub_criteria:
            sub_outcomes = [
                SubCriterionOutcome(
                    sub_criterion_id=sc.sub_criterion_id,
                    description=sc.description,
                    points_possible=sc.points,
                    points_awarded=Decimal("0"),
                    reasoning="",
                    confidence=0.0,
                    evidence_quote=None,
                    flags=[FlaggedOutcome(criterion_id=sc.sub_criterion_id, reason=flag_reason)],
                )
                for sc in criterion.sub_criteria
            ]
            outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id,
                description=criterion.description,
                points_possible=criterion.points,
                points_awarded=Decimal("0"),
                reasoning="",
                confidence=0.0,
                evidence_quote=None,
                sub_criterion_outcomes=sub_outcomes,
                flags=[],
            ))
        else:
            outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id,
                description=criterion.description,
                points_possible=criterion.points,
                points_awarded=Decimal("0"),
                reasoning="",
                confidence=0.0,
                evidence_quote=None,
                sub_criterion_outcomes=None,
                flags=[flag],
            ))
    return outcomes


def _build_skip_result(scope: GradableScope) -> _ScopeResult:
    criterion_outcomes = _build_zero_criterion_outcomes(scope, FlagReason.NO_ANSWER)
    annotation = GradingAnnotation(
        severity=AnnotationSeverity.INFO,
        target_id=_scope_target_id(scope),
        annotation_type="no_answer",
        message="אין תשובת תלמיד לסעיף זה — ניתנו 0 נקודות",
        metadata={"scope_kind": scope.scope_kind, "alignment": scope.alignment},
    )
    return _ScopeResult(
        outcome=ScopeOutcome(
            scope_kind=scope.scope_kind,
            question_id=scope.question_id,
            sub_question_id=scope.sub_question_id,
            points_possible=scope.points,
            points_awarded=Decimal("0"),
            min_confidence=0.0,
            criterion_outcomes=criterion_outcomes,
            flags=[FlaggedOutcome(
                question_id=scope.question_id,
                reason=FlagReason.NO_ANSWER,
            )],
            graded_by="skipped_no_answer",
            retry_count=0,
            input_tokens=0,
            output_tokens=0,
        ),
        annotations=[annotation],
    )


def _build_failure_result(
    scope: GradableScope,
    exc: Exception,
    retry_count: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> _ScopeResult:
    criterion_outcomes = _build_zero_criterion_outcomes(scope, FlagReason.LLM_UNCERTAINTY)
    annotation = GradingAnnotation(
        severity=AnnotationSeverity.ERROR,
        target_id=_scope_target_id(scope),
        annotation_type="llm_failure",
        message=f"שגיאת LLM בדירוג הסעיף: {type(exc).__name__}",
        metadata={"exception_class": type(exc).__name__, "retry_count": retry_count},
    )
    return _ScopeResult(
        outcome=ScopeOutcome(
            scope_kind=scope.scope_kind,
            question_id=scope.question_id,
            sub_question_id=scope.sub_question_id,
            points_possible=scope.points,
            points_awarded=Decimal("0"),
            min_confidence=0.0,
            criterion_outcomes=criterion_outcomes,
            flags=[FlaggedOutcome(
                question_id=scope.question_id,
                reason=FlagReason.LLM_UNCERTAINTY,
                message=str(exc)[:200],
            )],
            graded_by="failed",
            retry_count=retry_count,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        ),
        annotations=[annotation],
    )


def _assemble_criterion_outcomes(
    scope: GradableScope,
    vg_map: Dict[str, ValidatedTerminalGrade],
) -> Tuple[List[CriterionOutcome], List[float]]:
    """
    Build CriterionOutcome list from validated terminal grades.
    Returns (criterion_outcomes, all_terminal_confidences).
    """
    criterion_outcomes: List[CriterionOutcome] = []
    all_terminal_confidences: List[float] = []

    for criterion in scope.criteria:
        if criterion.sub_criteria:
            # Branch criterion — aggregate sub-outcomes
            sub_outcomes: List[SubCriterionOutcome] = []
            for sc in criterion.sub_criteria:
                vg = vg_map[sc.sub_criterion_id]
                sub_outcomes.append(SubCriterionOutcome(
                    sub_criterion_id=sc.sub_criterion_id,
                    description=sc.description,
                    points_possible=sc.points,
                    points_awarded=vg.points_awarded,
                    reasoning=vg.reasoning,
                    confidence=vg.confidence,
                    evidence_quote=vg.evidence_quote,
                    flags=vg.flags,
                ))
                all_terminal_confidences.append(vg.confidence)

            branch_confidence = min(so.confidence for so in sub_outcomes) if sub_outcomes else 0.0
            branch_points = sum(so.points_awarded for so in sub_outcomes)

            criterion_outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id,
                description=criterion.description,
                points_possible=criterion.points,
                points_awarded=branch_points,
                reasoning="",  # branch has no own reasoning — children carry it
                confidence=branch_confidence,
                evidence_quote=None,
                sub_criterion_outcomes=sub_outcomes,
                flags=[],
            ))
        else:
            # Leaf criterion — direct grade
            vg = vg_map[criterion.criterion_id]
            criterion_outcomes.append(CriterionOutcome(
                criterion_id=criterion.criterion_id,
                description=criterion.description,
                points_possible=criterion.points,
                points_awarded=vg.points_awarded,
                reasoning=vg.reasoning,
                confidence=vg.confidence,
                evidence_quote=vg.evidence_quote,
                sub_criterion_outcomes=None,
                flags=vg.flags,
            ))
            all_terminal_confidences.append(vg.confidence)

    return criterion_outcomes, all_terminal_confidences


class GraderAgent:
    """
    Stupid-simple grading agent: one LLM call per scope, structured output,
    deterministic post-validation, no ReAct, no multi-step reasoning.

    Args:
        numeric_policy: Precision and rounding policy for points.
            Defaults to NumericPolicy() (0.25 precision) when not supplied.
            Callers with access to the rubric contract should pass its policy.
    """

    def __init__(self, numeric_policy: Optional[NumericPolicy] = None) -> None:
        self._policy = numeric_policy or NumericPolicy()
        self._llm = ChatOpenAI(
            model=settings.openai_model,
            temperature=0.0,
            max_tokens=8192,
            api_key=settings.openai_api_key,
        )
        # include_raw=True: result is {"raw": AIMessage, "parsed": Model|None, "parsing_error": ...}
        # This surfaces usage_metadata for token/cost capture (S8).
        # parse failures → parsing_error is non-None; treated as non-transient (GA-3: no retry).
        self._structured_llm = self._llm.with_structured_output(
            QuestionGradingResponse, include_raw=True
        )

    async def _grade_scope(self, scope: GradableScope) -> _ScopeResult:
        """Grade one scope. Never raises — degrades to a flagged zero-outcome on failure."""

        # ── Skip path ────────────────────────────────────────────────────────
        if scope.alignment == "answer_missing" or not scope.student_answer_text:
            return _build_skip_result(scope)

        # ── Grade path with 1 transient retry (GA-3) ─────────────────────────
        t0 = time.monotonic()
        retry_count = 0
        accumulated_in_tokens = 0
        accumulated_out_tokens = 0

        async def _invoke() -> Tuple[QuestionGradingResponse, int, int]:
            """
            Returns (parsed_response, input_tokens, output_tokens).
            Raises ValueError on parsing_error (non-transient, GA-3: no retry).
            Raises transport exceptions for transient failures (retried once).
            """
            user_msg = build_user_message(scope)
            result: Dict[str, Any] = await self._structured_llm.ainvoke([
                SystemMessage(content=SYSTEM_PROMPT),
                HumanMessage(content=user_msg),
            ])
            if result.get("parsing_error"):
                # Deterministic parse failure at temperature=0.0 — never retry (GA-3).
                raise ValueError(f"LLM parse failure: {result['parsing_error']}")
            usage = (result["raw"].usage_metadata or {}) if result.get("raw") else {}
            return (
                result["parsed"],
                usage.get("input_tokens", 0),
                usage.get("output_tokens", 0),
            )

        try:
            response, in_tok, out_tok = await _invoke()
            accumulated_in_tokens += in_tok
            accumulated_out_tokens += out_tok
        except TRANSIENT_EXCEPTIONS as e:
            # Transport blip — retry once with jitter (GA-3 allows this)
            retry_count = 1
            logger.warning(
                "transient_llm_error_retrying",
                extra={
                    "exception_class": type(e).__name__,
                    "question_id": scope.question_id,
                    "sub_question_id": scope.sub_question_id,
                },
            )
            await asyncio.sleep(random.uniform(RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX))
            try:
                response, in_tok, out_tok = await _invoke()
                accumulated_in_tokens += in_tok
                accumulated_out_tokens += out_tok
            except Exception as e2:
                logger.error(
                    "scope_grade_failed_after_retry",
                    extra={
                        "exception_class": type(e2).__name__,
                        "question_id": scope.question_id,
                    },
                )
                return _build_failure_result(
                    scope, e2, retry_count=1,
                    input_tokens=accumulated_in_tokens,
                    output_tokens=accumulated_out_tokens,
                )
        except Exception as e:
            # Non-transient (ValueError from parsing_error, auth error, etc.) — GA-3: no retry
            logger.error(
                "scope_grade_failed_no_retry",
                extra={
                    "exception_class": type(e).__name__,
                    "question_id": scope.question_id,
                },
            )
            return _build_failure_result(
                scope, e, retry_count=0,
                input_tokens=accumulated_in_tokens,
                output_tokens=accumulated_out_tokens,
            )

        # ── Post-validation and assembly ──────────────────────────────────────
        validation_result = validate_scope_grading(response, scope, self._policy)
        vg_map = {vg.terminal_id: vg for vg in validation_result.validated_grades}
        criterion_outcomes, terminal_confidences = _assemble_criterion_outcomes(scope, vg_map)

        scope_points = sum(co.points_awarded for co in criterion_outcomes)
        min_conf = min(terminal_confidences) if terminal_confidences else 0.0

        # Scope-level flags: only closed-world violations bubble up to scope
        scope_flags = [
            f
            for vg in validation_result.validated_grades
            for f in vg.flags
            if f.reason == FlagReason.CLOSED_WORLD_VIOLATION
        ]

        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "scope_graded",
            extra={
                "question_id": scope.question_id,
                "sub_question_id": scope.sub_question_id,
                "scope_kind": scope.scope_kind,
                "graded_by": "llm",
                "retry_count": retry_count,
                "duration_ms": duration_ms,
                "terminal_count": len(vg_map),
                "points_awarded": str(scope_points),
                "points_possible": str(scope.points),
                "input_tokens": accumulated_in_tokens,
                "output_tokens": accumulated_out_tokens,
            },
        )

        return _ScopeResult(
            outcome=ScopeOutcome(
                scope_kind=scope.scope_kind,
                question_id=scope.question_id,
                sub_question_id=scope.sub_question_id,
                points_possible=scope.points,
                points_awarded=scope_points,
                min_confidence=min_conf,
                criterion_outcomes=criterion_outcomes,
                flags=scope_flags,
                graded_by="llm",
                retry_count=retry_count,
                input_tokens=accumulated_in_tokens,
                output_tokens=accumulated_out_tokens,
            ),
            annotations=validation_result.annotations,
        )

    async def grade(self, gradable_test: GradableTest) -> GradedTestDraft:
        """
        Grade all scopes in bounded parallel and return a complete GradedTestDraft.

        Invariant: len(draft.scope_outcomes) == len(gradable_test.scopes) always.
        No persistence. Returns the in-memory artifact; S8 persists it.
        """
        t0 = time.monotonic()
        sem = asyncio.Semaphore(MAX_CONCURRENT_SCOPES)

        async def _bounded(scope: GradableScope) -> _ScopeResult:
            async with sem:
                return await self._grade_scope(scope)

        raw_results = await asyncio.gather(
            *(_bounded(s) for s in gradable_test.scopes),
            return_exceptions=True,
        )

        scope_outcomes: List[ScopeOutcome] = []
        all_annotations: List[GradingAnnotation] = []

        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                # Unexpected bug escaped _grade_scope — should not normally happen
                logger.error(
                    "unexpected_scope_exception",
                    extra={"scope_index": i, "exception_class": type(result).__name__},
                    exc_info=result,
                )
                scope_result = _build_failure_result(
                    gradable_test.scopes[i], result, retry_count=0
                )
            else:
                scope_result = result

            scope_outcomes.append(scope_result.outcome)
            all_annotations.extend(scope_result.annotations)

        # D3 — output totality invariant
        assert len(scope_outcomes) == len(gradable_test.scopes), (
            f"Output totality violated: {len(scope_outcomes)} outcomes for "
            f"{len(gradable_test.scopes)} scopes"
        )

        llm_calls = sum(1 for so in scope_outcomes if so.graded_by == "llm")
        duration_ms = int((time.monotonic() - t0) * 1000)
        total_input_tokens  = sum(so.input_tokens  for so in scope_outcomes)
        total_output_tokens = sum(so.output_tokens for so in scope_outcomes)

        graded_by_counts = {
            v: sum(1 for so in scope_outcomes if so.graded_by == v)
            for v in ("llm", "skipped_no_answer", "failed")
        }
        logger.info(
            "grade_completed",
            extra={
                "rubric_contract_version": gradable_test.rubric_contract_version,
                "transcription_contract_version": gradable_test.transcription_contract_version,
                "model_version": settings.openai_model,
                "prompt_version": GRADING_PROMPT_VERSION,
                "llm_calls_count": llm_calls,
                "grading_duration_ms": duration_ms,
                "scope_count": len(scope_outcomes),
                "graded_by": graded_by_counts,
                "retried_scopes": sum(1 for so in scope_outcomes if so.retry_count > 0),
                "annotation_count": len(all_annotations),
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
            },
        )

        return GradedTestDraft(
            rubric_contract_version=gradable_test.rubric_contract_version,
            transcription_contract_version=gradable_test.transcription_contract_version,
            model_version=settings.openai_model,
            prompt_version=GRADING_PROMPT_VERSION,
            scope_outcomes=scope_outcomes,
            teacher_overrides={},
            annotations=all_annotations,
            unmatched_transcription_answers=list(gradable_test.unmatched_transcription_answers),
            llm_calls_count=llm_calls,
            grading_duration_ms=duration_ms,
            total_input_tokens=total_input_tokens,
            total_output_tokens=total_output_tokens,
        )
