"""
OptionsVerifyGrader — grader-v6 (PR_grader_v6_options.md §6, M3).

The model picks one OPTION per plan check, with evidence; it never sees a value
(§6.1) or a real id (AM-G17). Everything numeric is the ONE v6 pricer's
(`services/pricing_v6.price`), run once over the WHOLE test, because charge groups
and caps cross checks (§7.2). Orchestration is v5's, imported not forked (§0.4):
the bounded-parallel semaphore, the skip path, OD-R1's one automatic re-grade of a
failed scope, per-scope failure isolation, and D3 totality.

Per scope:
    render (values-free, aliased) → sc_n calls → closed world on check aliases
    (`strip_out_of_world`, no rekey: an alias has nothing to romanise) → a foreign
    option is MISSING → duplicates: first wins + a scope flag → median over OPTION
    VALUES across calls (AM-G8), evidence from the first call agreeing → quote
    status for every non-default option (credit and fault alike, §6.3).
Per test:
    DraftV6Content (the plan copy + selections) → price → explainer (an injected
    async callable; none ⇒ the deterministic fallback line for every credit
    terminal) → the GradedTestDraft ENVELOPE, whose outcomes carry the pricer's
    awards as a projection (M3: the v5 scorer measures v6 with the same code).

The evidence gate is the PRICER's (AM-G2, Q-8): post-validation records
`quote_status` and keeps the claimed option.
"""
from __future__ import annotations

import asyncio
import logging
import random
import time
from decimal import Decimal
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence, Tuple

from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.explainer.fallback import compose_reasoning_he
from app.agents.grader.grader import (
    RETRY_BACKOFF_MAX,
    RETRY_BACKOFF_MIN,
    _build_failure_result,
    _build_skip_result,
    _get_terminal_map,
    _scope_target_id,
    bounded_invoke,
    effective_scope_concurrency,
    is_permanent_provider_error,
)
from app.agents.grader.grader_v5 import V5_TRANSIENT_EXCEPTIONS
from app.agents.grader.llm_factory import serves_requested
from app.agents.grader.plan_schemas import (CheckVerdictV6, GradingPlanV6, PlanCheckV6,
                                            ScopeVerdictsV6)
from app.agents.grader.plan_values import plan_hash as compute_plan_hash
from app.agents.grader.validator import quote_match_status, strip_out_of_world
from app.agents.grader.verifier_prompt_v6 import (VERIFIER_V6_PROMPT_VERSION,
                                                  build_verifier_v6_message,
                                                  verifier_aliases, verifier_v6_system_prompt)
from app.schemas.gradable import GradableScope, GradableTest
from app.schemas.graded_test_draft import (CriterionOutcome, GradedTestDraft, GradingAnnotation,
                                           ScopeOutcome, SubCriterionOutcome)
from app.schemas.graded_test_draft_v6 import (CheckRecordV6, DraftV6Content, ExplanationV6,
                                              ScopeRecordV6, UsageV6)
from app.schemas.ontology_types import (AnnotationSeverity, AnswerQuotation, FlaggedOutcome,
                                        FlagReason, QuoteValidationStatus)
from app.services.grading_inputs import scope_answer
from app.services.pricing_v6 import (PricedTest, SelectionGroupView, SelectionView, ViewTerminal,
                                     price)
from app.services.provider_billing import first_billing_exhausted

logger = logging.getLogger(__name__)

ZERO = Decimal("0")
_VERIFIED = ("exact", "fuzzy")

# (content, priced, gradable_test) → an object with .explanations, .usage, .payloads
Explain = Callable[[DraftV6Content, PricedTest, GradableTest], Awaitable[Any]]


class _Verdict:
    __slots__ = ("option_id", "evidence_quote", "absence_pointer_he")

    def __init__(self, option_id: str, evidence_quote: str, absence_pointer_he: str):
        self.option_id = option_id
        self.evidence_quote = evidence_quote
        self.absence_pointer_he = absence_pointer_he


class _ScopeRun:
    """One scope's result before pricing."""

    def __init__(self, scope: GradableScope, checks: List[PlanCheckV6], record: ScopeRecordV6,
                 verdicts: Dict[str, _Verdict], annotations: List[GradingAnnotation],
                 scope_flags: List[FlaggedOutcome], check_flags: Dict[str, List[str]]):
        self.scope, self.checks, self.record = scope, checks, record
        self.verdicts, self.annotations = verdicts, annotations
        self.scope_flags, self.check_flags = scope_flags, check_flags


def _median_option(check: PlanCheckV6, votes: Sequence[_Verdict]) -> _Verdict:
    """[AM-G8] the consensus is the MEDIAN over option values; the evidence comes
    from the first call whose option has that value."""
    values = sorted(check.option(v.option_id).value for v in votes)
    med = values[len(values) // 2]
    return next(v for v in votes if check.option(v.option_id).value == med)


class OptionsVerifyGrader:
    """grade(gradable_test) -> GradedTestDraft (envelope + the v6 block)."""

    def __init__(self, plan: GradingPlanV6, contract, *, llm, model_version: str,
                 profile, sc_n: int = 1, explain: Optional[Explain] = None,
                 explainer_prompt_version: Optional[str] = None) -> None:
        if sc_n < 1 or sc_n % 2 == 0:
            raise ValueError(f"sc_n must be an odd positive integer, got {sc_n}")
        recomputed = compute_plan_hash(plan.terminals, plan.checks)
        if recomputed != plan.plan_hash:            # §9.1: the copy must re-hash to the pin
            raise ValueError(f"plan_hash mismatch: stamped {plan.plan_hash[:12]}, "
                             f"content {recomputed[:12]}")
        self._plan = plan
        self._contract = contract
        self._precision = Decimal(str(contract.numeric_policy.precision))
        self._model_version = model_version
        self._profile = profile
        self._sc_n = sc_n
        self._explain = explain
        self._explainer_prompt_version = explainer_prompt_version
        self._system = verifier_v6_system_prompt(profile)
        self._structured_llm = llm.with_structured_output(ScopeVerdictsV6, include_raw=True)
        self._plan_terminals = {t.terminal_id: t for t in plan.terminals}
        self.billing_exhausted: Optional[BaseException] = None       # [A-8] reported upward

    # ── one call ─────────────────────────────────────────────────────────────
    async def _invoke_once(self, user_msg: str, usage: UsageV6) -> ScopeVerdictsV6:
        result: Dict[str, Any] = await bounded_invoke(self._structured_llm, [
            SystemMessage(content=self._system), HumanMessage(content=user_msg)])
        raw = result.get("raw")
        meta = (getattr(raw, "usage_metadata", None) or {}) if raw is not None else {}
        rmeta = dict(getattr(raw, "response_metadata", None) or {}) if raw is not None else {}
        served = rmeta.get("model") or rmeta.get("model_name")
        usage.calls += 1
        usage.input_tokens += int(meta.get("input_tokens") or 0)
        usage.output_tokens += int(meta.get("output_tokens") or 0)
        usage.cached_input_tokens += int((meta.get("input_token_details") or {}).get("cache_read") or 0)
        if served:
            if served not in usage.served_models:
                usage.served_models.append(served)
            if not serves_requested(self._model_version, served):
                usage.model_fallback = True                        # [AM-G18]
        if result.get("parsing_error") or result.get("parsed") is None:
            raise ValueError(f"LLM parse failure: {result.get('parsing_error')!r}"[:300])
        return result["parsed"]

    # ── verification of one scope (sc_n calls → consensus) ───────────────────
    async def _verify(self, scope: GradableScope, checks: List[PlanCheckV6], usage: UsageV6
                      ) -> Tuple[Dict[str, _Verdict], List[GradingAnnotation],
                                 List[FlaggedOutcome], Dict[str, List[str]]]:
        aliases = verifier_aliases(checks)
        user_msg = build_verifier_v6_message(scope, checks, aliases)
        target = _scope_target_id(scope)
        by_id = {c.check_id: c for c in checks}
        annotations: List[GradingAnnotation] = []
        scope_flags: List[FlaggedOutcome] = []
        check_flags: Dict[str, List[str]] = {}
        per_call: List[Dict[str, _Verdict]] = []
        for _ in range(self._sc_n):
            parsed = await self._invoke_once(user_msg, usage)
            # [CWV-1 / AM-G17] closed world over the call's check aliases, no rekey
            in_world, cw_flags, cw_anns = strip_out_of_world(
                parsed.verdicts, key=lambda v: v.check_id, known=aliases.checks.issued("c"),
                scope_id=target, describe=lambda v: f"option={v.option_id}")
            scope_flags.extend(cw_flags)
            annotations.extend(cw_anns)
            call_map: Dict[str, _Verdict] = {}
            for v in in_world:
                real = aliases.checks.real(v.check_id)
                if real in call_map:                               # duplicate: the first wins
                    scope_flags.append(FlaggedOutcome(
                        criterion_id=real, reason=FlagReason.CLOSED_WORLD_VIOLATION,
                        message=f"duplicate verdict for {v.check_id}; the first was kept"))
                    logger.warning(f"v6_duplicate_verdict scope={target} check={real}")
                    continue
                option = aliases.option_real(real, v.option_id)
                if option is None:                                 # §6.3: a foreign option is missing
                    check_flags.setdefault(real, []).append("foreign_option")
                    logger.warning(f"v6_foreign_option scope={target} check={real} "
                                   f"returned={v.option_id}")
                    continue
                call_map[real] = _Verdict(option, v.evidence_quote or "",
                                          v.absence_pointer_he or "")
            per_call.append(call_map)
        consensus: Dict[str, _Verdict] = {}
        for cid, check in by_id.items():
            votes = [m[cid] for m in per_call if cid in m]
            if votes:
                consensus[cid] = _median_option(check, votes)
        return consensus, annotations, scope_flags, check_flags

    # ── one scope, isolated ──────────────────────────────────────────────────
    def _scope_checks(self, scope: GradableScope) -> List[PlanCheckV6]:
        tids = list(_get_terminal_map(scope))
        missing = [t for t in tids if t not in self._plan_terminals]
        if missing:   # V6-style totality: a firing here is a wiring bug — LOUD
            raise RuntimeError(f"plan {self._plan.plan_hash[:12]} lacks terminals {missing} "
                               f"for scope {_scope_target_id(scope)}")
        wanted = set(tids)
        return [c for c in self._plan.checks if c.priced_terminal_id in wanted]

    async def _grade_scope(self, scope: GradableScope) -> _ScopeRun:
        checks = self._scope_checks(scope)
        usage = UsageV6(model=self._model_version)
        record = ScopeRecordV6(question_id=scope.question_id, sub_question_id=scope.sub_question_id,
                               graded_by="llm", usage=usage)
        if scope.alignment == "answer_missing" or not scope.student_answer_text:
            skip = _build_skip_result(scope)
            record = record.model_copy(update={"graded_by": "skipped_no_answer", "usage": None})
            return _ScopeRun(scope, checks, record, {}, list(skip.annotations), [], {})
        if not checks:
            return _ScopeRun(scope, checks, record.model_copy(update={"usage": None}), {}, [], [], {})

        target = _scope_target_id(scope)
        retry_count = 0
        try:
            consensus, anns, sflags, cflags = await self._verify(scope, checks, usage)
        except Exception as e:                                     # noqa: BLE001 — §3.6
            if is_permanent_provider_error(e):
                logger.error(f"v6_scope_failed_permanent scope={target} "
                             f"exc={type(e).__name__}: {str(e)[:300]}")
                return self._failed(scope, checks, record, e, 0)
            retry_count = 1                                        # [OD-R1] once, any exception
            kind = "transient" if isinstance(e, V5_TRANSIENT_EXCEPTIONS) else "content"
            logger.warning(f"v6_scope_retry scope={target} kind={kind} "
                           f"exc={type(e).__name__}: {str(e)[:300]}")
            await asyncio.sleep(random.uniform(RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX))
            try:
                consensus, anns, sflags, cflags = await self._verify(scope, checks, usage)
            except Exception as e2:                                # noqa: BLE001
                logger.error(f"v6_scope_failed_after_retry scope={target} "
                             f"exc={type(e2).__name__}: {str(e2)[:300]}")
                return self._failed(scope, checks, record, e2, 1)
        record = record.model_copy(update={
            "retry_count": retry_count, "flags": [f.reason.value for f in sflags]})
        return _ScopeRun(scope, checks, record, consensus, anns, sflags, cflags)

    def _failed(self, scope, checks, record, exc, retry_count) -> _ScopeRun:
        """[OD-R1] a scope that failed twice: every check its default (PRC-1), and
        the standard `llm_failure` annotation — the checks stay, so she can decide."""
        self.billing_exhausted = first_billing_exhausted(self.billing_exhausted, exc)   # [A-8]
        failure = _build_failure_result(scope, exc, retry_count=retry_count)
        record = record.model_copy(update={"graded_by": "failed", "retry_count": retry_count})
        return _ScopeRun(scope, checks, record, {}, list(failure.annotations), [], {})

    # ── the whole test ───────────────────────────────────────────────────────
    def _selection(self) -> SelectionView:
        c = self._contract
        return SelectionView(
            total_points=c.total_points,
            question_order=[q.question_id for q in c.questions],
            groups=[SelectionGroupView(of_question_ids=list(g.of_question_ids), choose_k=g.choose_k)
                    for g in (c.selection_groups or [])])

    def _content(self, runs: List[_ScopeRun]) -> DraftV6Content:
        order = {c.check_id: i for i, c in enumerate(self._plan.checks)}
        records: List[CheckRecordV6] = []
        view_terminals: List[ViewTerminal] = []
        for run in runs:
            for tid in _get_terminal_map(run.scope):
                view_terminals.append(ViewTerminal(
                    terminal_id=tid, question_id=run.scope.question_id,
                    sub_question_id=run.scope.sub_question_id,
                    points_possible=self._plan_terminals[tid].points_possible))
            answer = run.scope.student_answer_text or ""
            for check in run.checks:
                v = run.verdicts.get(check.check_id)
                flags = list(run.check_flags.get(check.check_id, []))
                if v is None:
                    records.append(CheckRecordV6(plan=check, plan_index=order[check.check_id],
                                                 flags=flags))
                    continue
                status = None
                if v.option_id != check.default_option.option_id:   # §6.3: every non-default option
                    st = quote_match_status(v.evidence_quote, answer)
                    status = st.value if st is not None else "not_found"
                records.append(CheckRecordV6(
                    plan=check, plan_index=order[check.check_id], model_option_id=v.option_id,
                    evidence_quote=v.evidence_quote, absence_pointer_he=v.absence_pointer_he,
                    quote_status=status, flags=flags))
        records.sort(key=lambda r: r.plan_index)
        scope_usages = [r.record.usage for r in runs if r.record.usage is not None]
        verifier = UsageV6(model=self._model_version,
                           calls=sum(u.calls for u in scope_usages),
                           input_tokens=sum(u.input_tokens for u in scope_usages),
                           output_tokens=sum(u.output_tokens for u in scope_usages),
                           cached_input_tokens=sum(u.cached_input_tokens for u in scope_usages),
                           served_models=sorted({m for u in scope_usages for m in u.served_models}),
                           model_fallback=any(u.model_fallback for u in scope_usages))
        return DraftV6Content(
            plan_hash=self._plan.plan_hash, config_hash=self._plan.config_hash,
            pack=self._plan.subject_pack, verifier_prompt_version=VERIFIER_V6_PROMPT_VERSION,
            explainer_prompt_version=self._explainer_prompt_version,
            precision=self._precision, terminals=list(self._plan.terminals),
            view_terminals=view_terminals, selection=self._selection(), checks=records,
            scopes=[r.record for r in runs], verifier_usage=verifier)

    async def grade(self, gradable_test: GradableTest) -> GradedTestDraft:
        t0 = time.monotonic()
        sem = asyncio.Semaphore(effective_scope_concurrency(len(gradable_test.scopes)))

        async def _bounded(scope: GradableScope) -> _ScopeRun:
            async with sem:
                return await self._grade_scope(scope)

        raw = await asyncio.gather(*(_bounded(s) for s in gradable_test.scopes),
                                   return_exceptions=True)
        runs: List[_ScopeRun] = []
        for scope, r in zip(gradable_test.scopes, raw):
            if isinstance(r, Exception):
                if isinstance(r, RuntimeError) and "lacks terminals" in str(r):
                    raise r                                        # a wiring bug is never isolated
                logger.error(f"v6_unexpected_scope_exception scope={_scope_target_id(scope)} "
                             f"exc={type(r).__name__}: {str(r)[:300]}")
                checks = self._scope_checks(scope)
                record = ScopeRecordV6(question_id=scope.question_id,
                                       sub_question_id=scope.sub_question_id, graded_by="failed")
                r = self._failed(scope, checks, record, r, 0)
            runs.append(r)
        assert len(runs) == len(gradable_test.scopes), "D3 totality violated"

        content = self._content(runs)
        priced = price(content.to_view())

        explanations: List[ExplanationV6] = []
        if self._explain is not None:
            outcome = await self._explain(content, priced, gradable_test)
            explanations = list(outcome.explanations)
            content = content.model_copy(update={
                "explainer_usage": outcome.usage,
                "explainer_payloads": list(getattr(outcome, "payloads", None) or [])})
        else:
            view = content.to_view()
            explanations = [ExplanationV6(terminal_id=t.terminal_id,
                                          text_he=compose_reasoning_he(priced, view, t.terminal_id),
                                          source="fallback")
                            for t in priced.terminals if self._is_credit_terminal(t.terminal_id)]
        content = content.model_copy(update={"explanations": explanations})
        return self._envelope(gradable_test, runs, content, priced, explanations,
                              int((time.monotonic() - t0) * 1000))

    def _is_credit_terminal(self, terminal_id: str) -> bool:
        return any(c.role == "credit" and c.priced_terminal_id == terminal_id
                   for c in self._plan.checks)

    # ── the envelope: the pricer's awards, projected for the v5 scorer ───────
    def _envelope(self, gradable_test, runs, content, priced: PricedTest, explanations,
                  duration_ms) -> GradedTestDraft:
        by_tid = {t.terminal_id: t for t in priced.terminals}
        resolved = {r.check_id: r for r in priced.checks}
        lines = {e.terminal_id: e.text_he for e in explanations}
        records = {c.plan.check_id: c for c in content.checks}
        outcomes: List[ScopeOutcome] = []
        annotations: List[GradingAnnotation] = []
        for run in runs:
            annotations.extend(run.annotations)
            gated = self._gated_annotations(run, resolved, records)
            annotations.extend(gated)

            def leaf(tid: str) -> Dict[str, Any]:
                pt = by_tid[tid]
                spans = [AnswerQuotation(quote_text=records[c.check_id].evidence_quote,
                                         validation_status=QuoteValidationStatus(
                                             records[c.check_id].quote_status))
                         for c in run.checks
                         if c.priced_terminal_id == tid
                         and records[c.check_id].quote_status in _VERIFIED
                         and records[c.check_id].evidence_quote
                         and resolved[c.check_id].option_id == records[c.check_id].model_option_id]
                return dict(points_awarded=pt.awarded, reasoning=lines.get(tid, ""),
                            confidence=0.0,           # AM-G8: v6 has no confidence; 0.0 is a placeholder
                            evidence_quote=spans[0] if spans else None, evidence_quotes=spans,
                            flags=[FlaggedOutcome(criterion_id=tid, reason=FlagReason(f),
                                                  message=f"v6 pricer: {f}") for f in pt.flags
                                   if f in FlagReason._value2member_map_])

            criterion_outcomes: List[CriterionOutcome] = []
            for criterion in run.scope.criteria:
                if criterion.sub_criteria:
                    subs = [SubCriterionOutcome(sub_criterion_id=sc.sub_criterion_id,
                                                description=sc.description, points_possible=sc.points,
                                                **leaf(sc.sub_criterion_id))
                            for sc in criterion.sub_criteria]
                    criterion_outcomes.append(CriterionOutcome(
                        criterion_id=criterion.criterion_id, description=criterion.description,
                        points_possible=criterion.points,
                        points_awarded=sum((s.points_awarded for s in subs), ZERO),
                        reasoning="", confidence=0.0, evidence_quote=None,
                        sub_criterion_outcomes=subs, flags=[]))
                else:
                    criterion_outcomes.append(CriterionOutcome(
                        criterion_id=criterion.criterion_id, description=criterion.description,
                        points_possible=criterion.points, sub_criterion_outcomes=None,
                        **leaf(criterion.criterion_id)))
            usage = run.record.usage
            outcomes.append(ScopeOutcome(
                scope_kind=run.scope.scope_kind, question_id=run.scope.question_id,
                sub_question_id=run.scope.sub_question_id, points_possible=run.scope.points,
                points_awarded=sum((co.points_awarded for co in criterion_outcomes), ZERO),
                min_confidence=0.0, criterion_outcomes=criterion_outcomes,
                flags=list(run.scope_flags), graded_by=run.record.graded_by,
                student_answer=scope_answer(run.scope), retry_count=run.record.retry_count,
                input_tokens=usage.input_tokens if usage else 0,
                output_tokens=usage.output_tokens if usage else 0,
                cached_input_tokens=usage.cached_input_tokens if usage else None))

        v = content.verifier_usage
        from app.subjects import prompt_version as _subject_prompt_version
        return GradedTestDraft(
            rubric_contract_version=gradable_test.rubric_contract_version,
            transcription_contract_version=gradable_test.transcription_contract_version,
            model_version=self._model_version,
            prompt_version=_subject_prompt_version(VERIFIER_V6_PROMPT_VERSION, self._profile),
            plan_version=None,                # a v5 field (PR-G1 per-check records); v6 stamps v6.plan_hash
            served_models=(v.served_models or None) if v else None,
            scope_outcomes=outcomes, teacher_overrides={}, annotations=annotations,
            unmatched_transcription_answers=list(gradable_test.unmatched_transcription_answers),
            llm_calls_count=sum(1 for r in runs if r.record.graded_by == "llm"),
            grading_duration_ms=duration_ms,
            total_input_tokens=v.input_tokens if v else 0,
            total_output_tokens=v.output_tokens if v else 0,
            total_cached_input_tokens=v.cached_input_tokens if v else None,
            v6=content.model_dump(mode="json"))

    def _gated_annotations(self, run: _ScopeRun, resolved, records) -> List[GradingAnnotation]:
        """The pricer REFUSED a credit claim (an unverified span). The v5 scorer reads
        exactly this annotation to classify the claim (fabricated vs stitched)."""
        out = []
        for c in run.checks:
            r = resolved.get(c.check_id)
            if c.role != "credit" or r is None or r.source != "gated":
                continue
            rec = records[c.check_id]
            out.append(GradingAnnotation(
                severity=AnnotationSeverity.WARNING, target_id=c.priced_terminal_id,
                annotation_type="evidence_unverified",
                message=f"הבדיקה '{c.description_he}' סומנה כמתקיימת אך הציטוט לא נמצא "
                        f"בתשובת התלמיד — לא ניתן זיכוי",
                metadata={"check_id": c.check_id, "claimed_option": r.claimed_option_id,
                          "quote_text": rec.evidence_quote[:200]}))
        return out
