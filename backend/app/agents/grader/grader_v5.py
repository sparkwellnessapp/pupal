"""
PlanVerifyGrader — the grader-v5 Plan/Verify/Price agent (mission §3, fixed
architecture): the model emits VERDICTS + evidence per plan check, never a
number; pricer.py converts verdicts to points deterministically.

Orchestration skeleton is GraderAgent's, imported not forked (§0.4): the same
bounded-parallel semaphore, the same skip path for missing answers, the same
per-scope failure isolation to a flagged zero-outcome, the same D3 totality
invariant. What changes is the inside of one scope:

    render checks (point-blind) → ScopeVerificationResponse
    → closed-world on check ids → per-SPAN quote validation
    → price_scope() → outcomes carrying evidence_quotes (multi-span)

SC-3 self-consistency (sc_n=3, cheap-tier configs): n independent verifier
calls per scope; per-check verdict = MEDIAN on the ordinal scale
(not_met < partially_met < met); evidence/basis/confidence from the first
call agreeing with the median; token usage summed across calls.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import anthropic
import openai
from google.genai import errors as genai_errors
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.grader.grader import (
    effective_scope_concurrency,
    bounded_invoke,
    RETRY_BACKOFF_MAX,
    RETRY_BACKOFF_MIN,
    _ScopeResult,
    _build_failure_result,
    _build_skip_result,
    _capture_served_model,
    _get_terminal_map,
    _scope_target_id,
)
from app.agents.grader.llm_factory import build_chat_model
from app.agents.grader.plan_schemas import (
    CheckVerdict,
    GradingPlan,
    ScopeVerificationResponse,
    TerminalPlan,
)
from app.agents.grader.pricer import AssessedVerdict, PricedTerminal, price_scope
from app.agents.grader.validator import quote_match_status
from app.agents.grader.verifier_prompt import (
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SYSTEM_PROMPT,
    build_verifier_message,
    scope_terminal_plans,
)
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
    FlagReason,
    NumericPolicy,
)

logger = logging.getLogger(__name__)

# The v3 tuple is OpenAI-only; the seam runs Anthropic entrants too. Same
# semantics: transport blips retried once in-agent (the factory already
# disabled the SDKs' hidden retry layers), content failures never.
V5_TRANSIENT_EXCEPTIONS = (
    asyncio.TimeoutError,                     # [PR-G2] the per-scope wall
    openai.APITimeoutError,
    openai.RateLimitError,
    openai.APIConnectionError,
    openai.InternalServerError,
    anthropic.APITimeoutError,
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.InternalServerError,
    # gemini (owner reversal 2026-08-28): 5xx retries once in-agent; a 429
    # (ClientError) deliberately does NOT — the class alone can't be told from
    # a 400 without code inspection, and the runner's D7 re-run owns that path.
    genai_errors.ServerError,
)

_ORDINAL = {"not_met": 0, "partially_met": 1, "met": 2}
_ORDINAL_INV = {0: "not_met", 1: "partially_met", 2: "met"}


def _median_verdict(verdicts: List[str]) -> str:
    ranks = sorted(_ORDINAL[v] for v in verdicts)
    return _ORDINAL_INV[ranks[len(ranks) // 2]]


class PlanVerifyGrader:
    """grade(gradable_test) -> GradedTestDraft, same contract as GraderAgent."""

    def __init__(self,
                 plan: GradingPlan,
                 numeric_policy: Optional[NumericPolicy] = None,
                 *,
                 llm=None,
                 model_version: Optional[str] = None,
                 sc_n: int = 1) -> None:
        if sc_n < 1 or sc_n % 2 == 0:
            raise ValueError(f"sc_n must be an odd positive integer, got {sc_n}")
        self._plan = plan
        self._plan_terminals: Dict[str, TerminalPlan] = {
            t.terminal_id: t for t in plan.terminals}
        self._policy = numeric_policy or NumericPolicy()
        self._model_version = model_version or settings.openai_model
        self._served_models: set = set()   # [COST_TRUTH] provider-reported ids
        self._sc_n = sc_n
        base = llm if llm is not None else build_chat_model(
            "openai", settings.openai_model)
        self._structured_llm = base.with_structured_output(
            ScopeVerificationResponse, include_raw=True)

    # ── one verifier call ────────────────────────────────────────────────────
    async def _invoke_once(self, user_msg: str
                           ) -> Tuple[ScopeVerificationResponse, int, int, Optional[int]]:
        result: Dict[str, Any] = await bounded_invoke(self._structured_llm, [
            SystemMessage(content=VERIFIER_SYSTEM_PROMPT),
            HumanMessage(content=user_msg),
        ])
        if result.get("parsing_error"):
            # Deterministic parse failure at temp 0 — never retried (R6/GA-3).
            raise ValueError(f"LLM parse failure: {result['parsing_error']}")
        _capture_served_model(result.get("raw"), self._served_models)
        usage = (result["raw"].usage_metadata or {}) if result.get("raw") else {}
        cached = (usage.get("input_token_details") or {}).get("cache_read")
        return (result["parsed"], usage.get("input_tokens", 0),
                usage.get("output_tokens", 0), cached)

    async def _verify_scope(self, scope: GradableScope,
                            terminal_plans: List[TerminalPlan]
                            ) -> Tuple[Dict[str, CheckVerdict], List[GradingAnnotation],
                                       int, int, Optional[int]]:
        """sc_n independent calls → median-consensus verdict per check.
        Returns (verdict per check_id, closed-world annotations, tokens...)."""
        user_msg = build_verifier_message(scope, terminal_plans)
        known_ids = {c.check_id for tp in terminal_plans for c in tp.checks}

        per_call: List[Dict[str, CheckVerdict]] = []
        annotations: List[GradingAnnotation] = []
        in_tok = out_tok = 0
        cached_tok: Optional[int] = None
        for _ in range(self._sc_n):
            parsed, i, o, c = await self._invoke_once(user_msg)
            in_tok += i
            out_tok += o
            if c is not None:
                cached_tok = (cached_tok or 0) + c
            call_map: Dict[str, CheckVerdict] = {}
            for v in parsed.verdicts:
                if v.check_id not in known_ids:
                    annotations.append(GradingAnnotation(
                        severity=AnnotationSeverity.ERROR,
                        target_id=v.check_id,
                        annotation_type="closed_world_violation",
                        message=f"המודל החזיר פסיקה לבדיקה לא מוכרת: {v.check_id}",
                        metadata={"extra_id": v.check_id,
                                  "scope": _scope_target_id(scope)},
                    ))
                    continue
                call_map.setdefault(v.check_id, v)   # first occurrence wins
            per_call.append(call_map)

        consensus: Dict[str, CheckVerdict] = {}
        for cid in known_ids:
            votes = [m[cid] for m in per_call if cid in m]
            if not votes:
                continue                              # pricer flags UNVERIFIED_CHECK
            med = _median_verdict([v.verdict for v in votes])
            consensus[cid] = next(v for v in votes if v.verdict == med)
        return consensus, annotations, in_tok, out_tok, cached_tok

    # ── outcome assembly from priced terminals ───────────────────────────────
    def _assemble(self, scope: GradableScope,
                  priced: Dict[str, PricedTerminal]
                  ) -> Tuple[List[CriterionOutcome], List[float], List[GradingAnnotation]]:
        criterion_outcomes: List[CriterionOutcome] = []
        confidences: List[float] = []
        annotations: List[GradingAnnotation] = []

        def _leaf_fields(pt: PricedTerminal) -> Dict[str, Any]:
            annotations.extend(pt.annotations)
            confidences.append(pt.confidence)
            return dict(
                points_awarded=pt.points_awarded,
                reasoning=pt.reasoning,
                confidence=pt.confidence,
                evidence_quote=pt.evidence_quotes[0] if pt.evidence_quotes else None,
                # [] (not None) when no span verified: the presence of the
                # field marks the v5 path for the eval scorer
                evidence_quotes=pt.evidence_quotes,
                checks=pt.checks,          # [PR-G1] the per-check record
                flags=pt.flags,
            )

        for criterion in scope.criteria:
            if criterion.sub_criteria:
                subs = [SubCriterionOutcome(
                    sub_criterion_id=sc.sub_criterion_id,
                    description=sc.description,
                    points_possible=sc.points,
                    **_leaf_fields(priced[sc.sub_criterion_id]),
                ) for sc in criterion.sub_criteria]
                criterion_outcomes.append(CriterionOutcome(
                    criterion_id=criterion.criterion_id,
                    description=criterion.description,
                    points_possible=criterion.points,
                    points_awarded=sum((s.points_awarded for s in subs), Decimal("0")),
                    reasoning="",
                    confidence=min((s.confidence for s in subs), default=0.0),
                    evidence_quote=None,
                    sub_criterion_outcomes=subs,
                    flags=[],
                ))
            else:
                criterion_outcomes.append(CriterionOutcome(
                    criterion_id=criterion.criterion_id,
                    description=criterion.description,
                    points_possible=criterion.points,
                    sub_criterion_outcomes=None,
                    **_leaf_fields(priced[criterion.criterion_id]),
                ))
        return criterion_outcomes, confidences, annotations

    # ── one scope, isolated ──────────────────────────────────────────────────
    async def _grade_scope(self, scope: GradableScope) -> _ScopeResult:
        if scope.alignment == "answer_missing" or not scope.student_answer_text:
            return _build_skip_result(scope)

        terminal_ids = list(_get_terminal_map(scope))
        missing_plan = [t for t in terminal_ids if t not in self._plan_terminals]
        if missing_plan:
            # validator rule V6 makes this impossible on the honest path — a
            # firing here is a pre-flight wiring bug, and it must be LOUD.
            raise RuntimeError(
                f"plan {self._plan.plan_version!r} lacks terminals {missing_plan} "
                f"for scope {_scope_target_id(scope)} — the plan was not "
                f"validated against this contract")
        terminal_plans = scope_terminal_plans(scope, self._plan_terminals)

        t0 = time.monotonic()
        retry_count = 0
        try:
            consensus, cw_annotations, in_tok, out_tok, cached = \
                await self._verify_scope(scope, terminal_plans)
        except V5_TRANSIENT_EXCEPTIONS as e:
            retry_count = 1
            logger.warning("v5_transient_retry", extra={
                "exception_class": type(e).__name__,
                "question_id": scope.question_id,
                "sub_question_id": scope.sub_question_id})
            await asyncio.sleep(random.uniform(RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX))
            try:
                consensus, cw_annotations, in_tok, out_tok, cached = \
                    await self._verify_scope(scope, terminal_plans)
            except Exception as e2:
                logger.error("v5_scope_failed_after_retry", extra={
                    "exception_class": type(e2).__name__,
                    "question_id": scope.question_id})
                return _build_failure_result(scope, e2, retry_count=1)
        except Exception as e:
            logger.error("v5_scope_failed_no_retry", extra={
                "exception_class": type(e).__name__,
                "question_id": scope.question_id})
            return _build_failure_result(scope, e, retry_count=0)

        # ── per-span quote validation → pricing (both deterministic) ────────
        answer = scope.student_answer_text or ""
        assessed: Dict[str, AssessedVerdict] = {
            cid: AssessedVerdict(
                check_id=cid,
                verdict=v.verdict,
                confidence=v.confidence,
                basis_he=v.basis_he,
                quote_text=v.evidence_quote,
                quote_status=quote_match_status(v.evidence_quote, answer),
            ) for cid, v in consensus.items()}
        priced = price_scope(terminal_plans, assessed, self._policy.precision)
        criterion_outcomes, confidences, price_annotations = \
            self._assemble(scope, priced)

        scope_points = sum((co.points_awarded for co in criterion_outcomes),
                           Decimal("0"))
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info("v5_scope_graded", extra={
            "question_id": scope.question_id,
            "sub_question_id": scope.sub_question_id,
            "graded_by": "llm", "retry_count": retry_count,
            "duration_ms": duration_ms,
            "points_awarded": str(scope_points),
            "input_tokens": in_tok, "output_tokens": out_tok})

        return _ScopeResult(
            outcome=ScopeOutcome(
                scope_kind=scope.scope_kind,
                question_id=scope.question_id,
                sub_question_id=scope.sub_question_id,
                points_possible=scope.points,
                points_awarded=scope_points,
                min_confidence=min(confidences) if confidences else 0.0,
                criterion_outcomes=criterion_outcomes,
                flags=[],
                graded_by="llm",
                retry_count=retry_count,
                input_tokens=in_tok,
                output_tokens=out_tok,
                cached_input_tokens=cached,
            ),
            annotations=cw_annotations + price_annotations,
        )

    # ── the whole test ───────────────────────────────────────────────────────
    async def grade(self, gradable_test: GradableTest) -> GradedTestDraft:
        t0 = time.monotonic()
        sem = asyncio.Semaphore(
            effective_scope_concurrency(len(gradable_test.scopes)))

        async def _bounded(scope: GradableScope) -> _ScopeResult:
            async with sem:
                return await self._grade_scope(scope)

        raw_results = await asyncio.gather(
            *(_bounded(s) for s in gradable_test.scopes), return_exceptions=True)

        scope_outcomes: List[ScopeOutcome] = []
        all_annotations: List[GradingAnnotation] = []
        for i, result in enumerate(raw_results):
            if isinstance(result, Exception):
                logger.error("v5_unexpected_scope_exception",
                             extra={"scope_index": i,
                                    "exception_class": type(result).__name__},
                             exc_info=result)
                result = _build_failure_result(
                    gradable_test.scopes[i], result, retry_count=0)
            scope_outcomes.append(result.outcome)
            all_annotations.extend(result.annotations)

        assert len(scope_outcomes) == len(gradable_test.scopes), (
            f"Output totality violated: {len(scope_outcomes)} outcomes for "
            f"{len(gradable_test.scopes)} scopes")

        cached_vals = [so.cached_input_tokens for so in scope_outcomes
                       if so.cached_input_tokens is not None]
        return GradedTestDraft(
            rubric_contract_version=gradable_test.rubric_contract_version,
            transcription_contract_version=gradable_test.transcription_contract_version,
            model_version=self._model_version,
            prompt_version=VERIFIER_PROMPT_VERSION,
            plan_version=self._plan.plan_version,
            served_models=sorted(self._served_models) or None,
            scope_outcomes=scope_outcomes,
            teacher_overrides={},
            annotations=all_annotations,
            unmatched_transcription_answers=list(
                gradable_test.unmatched_transcription_answers),
            llm_calls_count=sum(1 for so in scope_outcomes if so.graded_by == "llm"),
            grading_duration_ms=int((time.monotonic() - t0) * 1000),
            total_input_tokens=sum(so.input_tokens for so in scope_outcomes),
            total_output_tokens=sum(so.output_tokens for so in scope_outcomes),
            total_cached_input_tokens=sum(cached_vals) if cached_vals else None,
        )
