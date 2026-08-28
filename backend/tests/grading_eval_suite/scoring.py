"""
THE scorer — pure function over (GradedTestDraft, FixtureBundle) -> TrialScore.

No agent import, no I/O, no LLM. Instrument-immutable: this file is never
edited to make a number pass (PLAYBOOK STOP list; the §17.7 discipline).

Tier semantics [mission §6]:
  Tier 0  validity — transport/wall => invalid trial; parse failure => VALID,
          scored as the failed scope production would show [R6].
  Tier 1  tripwires — gate from run one, no distribution needed.
  Tier 2  agreement — UNGATED-WATCHED until thresholds are pre-registered
          from the baseline distribution (the A4/INV-6 lesson).
  Tier 3  diagnostics — reported every run.

Selection law [§5]: totals on BOTH sides run through the REAL
`selection_scoring.score_with_selection`; the denominator is
`contract.total_points`, never re-derived; a scope excluded under the GT-side
derivation is never scored as an agreement error.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from app.schemas.graded_test_draft import GradedTestDraft, ScopeOutcome
from app.services.selection_scoring import ScopeScore, score_with_selection

from .fixtures import FixtureBundle, ScopeKey, TerminalInfo
from .schemas import TerminalScore, TrialScore

# [C-4] Grade-boundary set for the flip metric — DEFAULT PROPOSAL, owner confirms
# or amends in GRADING_GT_CONVENTIONS.md before Phase C. Pass convention: >= b passes
# ("pass line 55 certain").
C4_BOUNDARIES = (55, 65, 75, 85, 95)

# [R4'] Two-level tolerance. Terminal tolerance = numeric_policy.precision (from
# the contract, per fixture). Test-total tolerance = 1.0 point (owner's number).
SHIPPABLE_TOLERANCE = Decimal("1.0")

# [DL-1] compensating_error (PROVISIONAL definition, PLAYBOOK-documented):
# total looks shippable while >= 2 points of terminal disagreement cancelled.
COMPENSATING_TOTAL_MAX = Decimal("1.0")
COMPENSATING_CANCELLED_MIN = Decimal("2.0")

# Exception classes raised by the grader's failure path that mean TRANSPORT
# (trial-invalidating [§7]); ValueError is the parse-failure class [R6].
_PARSE_EXCEPTION_CLASSES = {"ValueError"}


def _quote_fragments_all_present(quote_text: str, answer_text: str) -> bool:
    """[DL-2 SPLIT, 2026-08-27] Do ALL of a quote's constituent fragments appear
    VERBATIM in the answer? This is the classification signal between a stitched
    citation (real ink joined across a gap) and a fabricated one (invented ink).

    Deliberately NOT a re-scoring of the quote: the validator's 0.85 fuzzy bar is
    untouched and still decides `not_found`. This only re-LABELS an already-failed
    quote. Whitespace-normalized + casefolded, matching the validator's own
    normalization. Fragments shorter than 8 normalized chars are ignored as
    non-discriminating."""
    norm_answer = " ".join((answer_text or "").lower().split())
    frags = [" ".join(f.lower().split()) for f in (quote_text or "").splitlines()]
    frags = [f for f in frags if len(f) >= 8]
    if not frags:
        return False
    return all(f in norm_answer for f in frags)


def _scope_target(scope_key: ScopeKey) -> str:
    q, s = scope_key
    return q if s is None else f"{q}.{s}"


def _walk_outcome_terminals(outcome: ScopeOutcome):
    """Yield (terminal_id, awarded, confidence, evidence_quote, flag_reasons,
    evidence_quotes). The 6th element is the grader-v5 DECLARED span list
    (None on the v3 single-quote path)."""
    for co in outcome.criterion_outcomes:
        if co.sub_criterion_outcomes:
            for so in co.sub_criterion_outcomes:
                yield (so.sub_criterion_id, so.points_awarded, so.confidence,
                       so.evidence_quote, [f.reason.value for f in so.flags],
                       so.evidence_quotes)
        else:
            yield (co.criterion_id, co.points_awarded, co.confidence,
                   co.evidence_quote, [f.reason.value for f in co.flags],
                   co.evidence_quotes)


def _classify_failed_scopes(draft: GradedTestDraft) -> Tuple[List[str], List[str]]:
    """Split graded_by=='failed' scopes into (parse, transport) by the
    llm_failure annotation's exception_class [R6/§7]. Unknown class => transport
    (conservative: invalidate rather than silently score an artifact)."""
    exc_by_target: Dict[str, str] = {}
    for ann in draft.annotations:
        if ann.annotation_type == "llm_failure":
            exc_by_target[ann.target_id] = str(
                (ann.metadata or {}).get("exception_class", ""))
    parse, transport = [], []
    for outcome in draft.scope_outcomes:
        if outcome.graded_by != "failed":
            continue
        target = _scope_target((outcome.question_id, outcome.sub_question_id))
        exc = exc_by_target.get(target, "")
        (parse if exc in _PARSE_EXCEPTION_CLASSES else transport).append(target)
    return parse, transport


def score_trial(draft: GradedTestDraft,
                bundle: FixtureBundle,
                *,
                trial_index: int,
                cost_usd_value: Optional[float],
                cost_ceiling: float,
                latency_s: Optional[float] = None,
                provisional: bool = False,
                scope_filter: Optional[Set[ScopeKey]] = None,
                per_scope_cost: Optional[Dict[str, float]] = None,
                rerun_count: int = 0,
                rerun_reason: Optional[str] = None,
                invalid_reason: Optional[str] = None) -> TrialScore:
    if bundle.gt is None:
        raise ValueError(f"{bundle.name}: cannot score without GT (R1).")
    gt = bundle.gt
    infos = bundle.terminal_infos
    precision = bundle.rubric_contract.numeric_policy.precision
    subset = scope_filter is not None

    ts = TrialScore(fixture=bundle.name, trial_index=trial_index,
                    provisional=provisional or subset,
                    diagnostic_subset=subset,
                    rerun_count=rerun_count, rerun_reason=rerun_reason,
                    cost_usd=cost_usd_value, latency_s=latency_s,
                    input_tokens=draft.total_input_tokens,
                    output_tokens=draft.total_output_tokens,
                    per_scope_cost_usd=dict(per_scope_cost or {}))

    tier1: List[str] = []

    # ---- Tier 0: validity [§7] --------------------------------------------
    parse_scopes, transport_scopes = _classify_failed_scopes(draft)
    ts.parse_failed_scopes = parse_scopes                     # [R6] scored below
    ts.transport_failed_scopes = transport_scopes
    if invalid_reason:
        ts.valid, ts.invalid_reason = False, invalid_reason
    elif transport_scopes:
        ts.valid = False
        ts.invalid_reason = (f"transport failure in scope(s) "
                             f"{', '.join(transport_scopes)} — trial invalid, "
                             f"counted, excluded from aggregates")
    ts.graded_by_counts = {
        v: sum(1 for o in draft.scope_outcomes if o.graded_by == v)
        for v in ("llm", "skipped_no_answer", "failed", "excluded_by_selection")}
    ts.skipped_scopes = [
        _scope_target((o.question_id, o.sub_question_id))
        for o in draft.scope_outcomes if o.graded_by == "skipped_no_answer"]
    ts.fallback_scopes = list(bundle.gradable_test.parent_answer_fallback_scopes)

    # ---- [T1-CW] closed world: draft ids must live inside the contract -----
    contract_scope_keys = set(bundle.scope_keys)
    if scope_filter is not None:
        contract_scope_keys &= scope_filter
    draft_terminals: Dict[str, Tuple[Decimal, float, object, List[str]]] = {}
    for outcome in draft.scope_outcomes:
        key = (outcome.question_id, outcome.sub_question_id)
        if key not in contract_scope_keys:
            tier1.append(f"[T1-CW] closed_world: draft scope {_scope_target(key)} "
                         f"is not a contract scope")
            continue
        for tid, awarded, conf, quote, flags, quotes in _walk_outcome_terminals(outcome):
            if tid not in infos or infos[tid].scope_key != key:
                tier1.append(f"[T1-CW] closed_world: terminal {tid!r} is outside "
                             f"the contract universe")
                continue
            draft_terminals[tid] = (awarded, conf, quote, flags, quotes)

    # coverage: every in-scope contract terminal must appear in the draft
    # (the agent's D3 totality, re-checked independently — defense in depth)
    wanted_terminals = {tid: info for tid, info in infos.items()
                        if info.scope_key in contract_scope_keys}
    missing = set(wanted_terminals) - set(draft_terminals)
    if missing:
        tier1.append(f"[T1-CW] draft_terminal_missing: {sorted(missing)}")

    # ---- [T1-SKIP] skip agreement -----------------------------------------
    outcome_by_key = {(o.question_id, o.sub_question_id): o
                      for o in draft.scope_outcomes}
    ungradable_keys = {(u.question_id, u.sub_question_id)
                       for u in gt.ungradable_scopes}
    for scope in bundle.gradable_test.scopes:
        key = (scope.question_id, scope.sub_question_id)
        if key not in contract_scope_keys:
            continue
        outcome = outcome_by_key.get(key)
        if outcome is None:
            continue                       # already a [T1-CW] totality failure
        answer_empty = (scope.alignment == "answer_missing"
                        or not scope.student_answer_text)
        if answer_empty and outcome.graded_by == "llm":
            v = (f"[T1-SKIP] scope {_scope_target(key)} has no student answer "
                 f"but was graded_by=llm (a guess, not a skip)")
            tier1.append(v)
            ts.skip_agreement_violations.append(_scope_target(key))
        if key in ungradable_keys and outcome.graded_by == "llm":
            # [C-2] on a GT-ungradable scope the correct behavior is a flag,
            # not a confident award: positive points with ZERO flags anywhere
            # in the scope is the violation.
            has_flags = bool(outcome.flags) or any(
                flags for _, _, _, _, flags, _ in _walk_outcome_terminals(outcome))
            if outcome.points_awarded > 0 and not has_flags:
                v = (f"[T1-SKIP] ungradable scope {_scope_target(key)} received an "
                     f"unflagged positive award (guess where a flag was owed)")
                tier1.append(v)
                ts.skip_agreement_violations.append(_scope_target(key))

    # ---- Selection [§5]: totals through the REAL module -------------------
    gt_by_scope: Dict[ScopeKey, Decimal] = {}
    for t in gt.terminals:
        info = infos[t.terminal_id]
        gt_by_scope[info.scope_key] = gt_by_scope.get(info.scope_key, Decimal("0")) + t.awarded
    ai_by_scope: Dict[ScopeKey, Decimal] = {}
    for outcome in draft.scope_outcomes:
        key = (outcome.question_id, outcome.sub_question_id)
        if key in contract_scope_keys:
            ai_by_scope[key] = outcome.points_awarded

    excluded_gt: Set[ScopeKey] = set()
    excluded_ai: Set[ScopeKey] = set()
    if not subset:
        gt_scoring = score_with_selection(
            [ScopeScore(q, s, a) for (q, s), a in sorted(gt_by_scope.items(),
                                                         key=lambda kv: str(kv[0]))],
            bundle.rubric_contract)
        ai_scoring = score_with_selection(
            [ScopeScore(q, s, a) for (q, s), a in sorted(ai_by_scope.items(),
                                                         key=lambda kv: str(kv[0]))],
            bundle.rubric_contract)
        excluded_gt, excluded_ai = set(gt_scoring.excluded), set(ai_scoring.excluded)
        ts.exclusion_mismatch = excluded_gt != excluded_ai
        # [T1-SELECTION] arithmetic guard: the denominator IS the contract total.
        if gt_scoring.total_possible != bundle.rubric_contract.total_points:
            tier1.append("[T1-SELECTION] selection_denominator: score_with_selection "
                         "returned a denominator that is not contract.total_points")
        ts.gt_total = str(gt_scoring.total_score)
        ts.ai_total = str(ai_scoring.total_score)
        ts.total_possible = str(bundle.rubric_contract.total_points)

    # ---- Per-terminal agreement -------------------------------------------
    gt_map = {t.terminal_id: t for t in gt.terminals}
    # answer text per scope — needed by the [DL-2 SPLIT] stitched/fabricated classifier
    scope_answer: Dict[ScopeKey, Optional[str]] = {
        (s.question_id, s.sub_question_id): s.student_answer_text
        for s in bundle.gradable_test.scopes}
    # [grader-v5] the pricer's credit REFUSALS: an evidence_unverified
    # annotation records a met/partially_met claim on an unverifiable span.
    # The credit was already refused; the CLAIM is the trust offense and it
    # gates, classified by the same DL-2 fragments signal as a failed quote.
    unverified_claims: Dict[str, List[str]] = {}
    for ann in draft.annotations:
        if ann.annotation_type == "evidence_unverified":
            unverified_claims.setdefault(ann.target_id, []).append(
                str((ann.metadata or {}).get("quote_text", "")))
    quote_counts: Dict[str, int] = {}
    for tid, info in sorted(wanted_terminals.items()):
        if tid not in draft_terminals:
            continue                       # counted under [T1-CW] already
        awarded, conf, quote, flags, quotes = draft_terminals[tid]
        g = gt_map[tid]
        delta = awarded - g.awarded
        answer_text = scope_answer.get(info.scope_key)
        stitched = False
        fabricated = False

        if quotes is not None:
            # ── grader-v5 declared multi-span path [V5-A 2026-08-28] ───────
            # Aggregate status over declared spans: worst wins. The SUT stores
            # only verified spans; a not_found here is a SUT lie (defense in
            # depth) and classifies exactly like a v3 failed quote. Declared
            # spans verified individually are NEVER stitched — separate spans
            # over non-adjacent ink is the honest citation the E8 T1-STITCHED
            # finding asked for.
            statuses = [q.validation_status.value if q.validation_status else None
                        for q in quotes]
            if not statuses:
                quote_status = None
            elif any(st == "not_found" for st in statuses):
                quote_status = "not_found"
            elif any(st == "fuzzy" for st in statuses):
                quote_status = "fuzzy"
            else:
                quote_status = "exact"
            for q, st in zip(quotes, statuses):
                if st == "not_found":
                    if _quote_fragments_all_present(q.quote_text, answer_text):
                        stitched = True
                    else:
                        fabricated = True
            burden_evidence = awarded > 0 and not quotes
        else:
            # ── v3 single-quote path (unchanged) ───────────────────────────
            quote_status = None
            if quote is not None:
                quote_status = quote.validation_status.value if quote.validation_status else None

            # [DL-2 SPLIT] a failed quote on a positive award is EITHER fabricated
            # (ink absent) OR stitched (all ink real, joined across a gap). Both gate.
            failed_quote = (awarded > 0 and quote is not None
                            and quote_status == "not_found")
            if failed_quote:
                if _quote_fragments_all_present(quote.quote_text, answer_text):
                    stitched = True                                  # [T1-STITCHED]
                else:
                    fabricated = True                                # [T1-FABRICATED]
            burden_evidence = (awarded > 0
                               and (quote is None or quote_status == "not_found"))
        # [grader-v5] refusal claims gate on EITHER branch — the signal is the
        # annotation, not the span storage (a terminal whose every span was
        # refused stores an empty list, and must still gate on the claim)
        for claimed in unverified_claims.get(tid, []):
            if _quote_fragments_all_present(claimed, answer_text):
                stitched = True
            else:
                fabricated = True
        quote_counts[quote_status or "none"] = quote_counts.get(quote_status or "none", 0) + 1
        excluded = info.scope_key in excluded_gt

        row = TerminalScore(
            terminal_id=tid, question_id=info.question_id,
            sub_question_id=info.sub_question_id,
            gt_awarded=str(g.awarded), ai_awarded=str(awarded),
            delta=str(delta), abs_delta=str(abs(delta)),
            within_precision=abs(delta) <= precision,           # [R4'] terminal level
            exact=delta == 0,
            quote_status=quote_status, ai_confidence=conf,
            gt_evidence_exists=g.evidence_exists,
            ai_flags=list(flags),
            burden_precision=abs(delta) > precision,
            burden_evidence=burden_evidence,
            fabricated_evidence=fabricated,
            evidence_stitched=stitched,
            excluded_by_selection=excluded,
            ungradable_scope=info.scope_key in ungradable_keys,   # [C-2]
            gt_note=g.note,                                       # [item 6]
        )
        ts.terminals.append(row)
        if fabricated:
            # fabrication is a model-trust tripwire — it fires even on an
            # excluded scope (the behavior, not the arithmetic, is the offense)
            tier1.append(f"[T1-FABRICATED] fabricated_evidence at {tid}: positive "
                         f"award on a quote the student never wrote")
        if stitched:
            # [T1-STITCHED] real ink, non-contiguous, presented as one span —
            # a citation defect, not a trust catastrophe, but it breaks
            # span-highlighting and shows a teacher a broken citation.
            tier1.append(f"[T1-STITCHED] evidence_stitched at {tid}: positive award "
                         f"on real but NON-CONTIGUOUS ink presented as one quote")
    ts.quote_status_counts = quote_counts

    # ---- Tier 2 aggregates over INCLUDED terminals [§6] --------------------
    # [C-2, ratified 2026-08-24]: ungradable-scope terminals are excluded from
    # ALL Tier-2 agreement metrics (MAE, within-precision, exact, edit_burden,
    # compensating-error input); their best-guess awards participate ONLY in
    # the totals above (already summed into gt_by_scope/ai_by_scope).
    included = [t for t in ts.terminals
                if not t.excluded_by_selection and not t.ungradable_scope]
    if included and not subset:
        abs_deltas = [Decimal(t.abs_delta) for t in included]
        ts.mae = float(sum(abs_deltas) / len(abs_deltas))
        ts.within_precision_rate = sum(t.within_precision for t in included) / len(included)
        ts.exact_rate = sum(t.exact for t in included) / len(included)
        ts.edit_burden = (sum(t.burden_precision for t in included)
                          + sum(t.burden_evidence for t in included))
        gt_total_d = Decimal(ts.gt_total)
        ai_total_d = Decimal(ts.ai_total)
        total_delta = ai_total_d - gt_total_d
        ts.total_delta = str(total_delta)
        ts.shippable = abs(total_delta) <= SHIPPABLE_TOLERANCE     # [R4'] test level
        possible = Decimal(ts.total_possible)
        if possible > 0:
            ts.gt_pct = float(gt_total_d / possible * 100)
            ts.ai_pct = float(ai_total_d / possible * 100)
            ts.boundary_flips = [b for b in C4_BOUNDARIES
                                 if (ts.gt_pct >= b) != (ts.ai_pct >= b)]   # [C-4]
        cancelled = sum(abs_deltas) - abs(total_delta)
        ts.compensating_error = (abs(total_delta) <= COMPENSATING_TOTAL_MAX
                                 and cancelled >= COMPENSATING_CANCELLED_MIN)  # [DL-1]

    # ---- [T1-COST] registry-priced ceiling [§6] ----------------------------
    if cost_usd_value is not None and cost_usd_value > cost_ceiling:
        tier1.append(f"[T1-COST] cost ${cost_usd_value:.4f} exceeds the "
                     f"${cost_ceiling:.2f}/test ceiling")

    ts.tier1_failures = tier1
    ts.tier1_pass = ts.valid and not tier1
    return ts
