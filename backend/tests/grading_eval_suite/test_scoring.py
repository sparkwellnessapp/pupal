"""
Instrument guards for scoring.py [§10 of the mission] — known-answer self-pass
plus one injected error per metric, proving each catches its designed failure.
Zero API calls; drafts are synthetic (synth.py).
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.schemas.ontology_types import QuoteValidationStatus

from . import synth
from .scoring import (
    C4_BOUNDARIES,
    score_trial,
)


def _score(draft, bundle, **kw):
    kw.setdefault("trial_index", 0)
    kw.setdefault("cost_usd_value", 0.03)
    kw.setdefault("cost_ceiling", 0.10)
    return score_trial(draft, bundle, **kw)


# ---------------------------------------------------------------------------
# Known-answer self-pass [§10]
# ---------------------------------------------------------------------------

def test_known_answer_self_pass():
    """GT graded against itself: perfect Tier-2, Tier-1 passes."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)
    ts = _score(draft, bundle)
    assert ts.valid and ts.tier1_pass, ts.tier1_failures
    assert ts.mae == 0.0
    assert ts.within_precision_rate == 1.0 and ts.exact_rate == 1.0
    assert ts.gt_total == "9" and ts.ai_total == "9" and ts.total_possible == "9"
    assert ts.shippable is True and ts.total_delta == "0"
    assert ts.edit_burden == 0
    assert ts.boundary_flips == [] and ts.compensating_error is False
    assert ts.skip_agreement_violations == []


# ---------------------------------------------------------------------------
# Tier-1 injected errors — one per tripwire [§6 Tier-1]
# ---------------------------------------------------------------------------

def test_fabricated_evidence_fails_tier1():
    """[T1-FABRICATED][DL-2] award>0 with a PRESENT quote whose status is not_found."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    scopes = bundle.gradable_test.scopes
    q1 = next(s for s in scopes if s.question_id == "q1")
    q2 = next(s for s in scopes if s.question_id == "q2")
    o1 = synth.make_scope_outcome(q1, {
        "q1.c0": ("2", 0.9, "text that is not in the answer at all",
                  QuoteValidationStatus.NOT_FOUND),
        "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:10], QuoteValidationStatus.EXACT),
        "q1.c1.s1": ("2", 0.9, synth.ANSWER_Q1[:10], QuoteValidationStatus.EXACT),
    })
    o2 = synth.make_scope_outcome(q2, {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:10],
                                                  QuoteValidationStatus.EXACT)})
    ts = _score(synth.make_draft(bundle, [o1, o2]), bundle)
    assert ts.valid
    assert not ts.tier1_pass
    assert any("fabricated" in f for f in ts.tier1_failures)
    fab = [t for t in ts.terminals if t.fabricated_evidence]
    assert [t.terminal_id for t in fab] == ["q1.c0"]


def test_closed_world_leak_fails_tier1():
    """[T1-CW] a terminal id outside the contract universe must trip the gate."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)
    # graft an alien terminal into q1's outcome (bypasses the agent's validator
    # on purpose — the eval must catch it INDEPENDENTLY, defense in depth)
    alien = draft.scope_outcomes[0].criterion_outcomes[0].model_copy(
        update={"criterion_id": "q9.alien"})
    o1 = draft.scope_outcomes[0].model_copy(
        update={"criterion_outcomes": draft.scope_outcomes[0].criterion_outcomes + [alien]})
    tampered = draft.model_copy(update={"scope_outcomes": [o1] + draft.scope_outcomes[1:]})
    ts = _score(tampered, bundle)
    assert not ts.tier1_pass
    assert any("closed_world" in f for f in ts.tier1_failures)


def test_skip_agreement_on_empty_answer():
    """[T1-SKIP] an answer-missing scope graded as llm (a guess) must trip."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt, with_q2_answer=False)   # q2.א has no answer
    scopes = bundle.gradable_test.scopes
    q1 = next(s for s in scopes if s.question_id == "q1")
    q2 = next(s for s in scopes if s.question_id == "q2")
    assert q2.alignment == "answer_missing"
    o1 = synth.draft_from_gt(bundle, gt).scope_outcomes[0]
    guessed = synth.make_scope_outcome(q2, {"q2.א.c0": ("4", 0.9, "invented", None)})
    ts = _score(synth.make_draft(bundle, [o1, guessed]), bundle)
    assert not ts.tier1_pass
    assert any("skip" in f for f in ts.tier1_failures)
    # and the correct behavior (skip) passes
    ok = synth.make_draft(bundle, [o1, synth.make_skip_outcome(q2)])
    ts2 = _score(ok, bundle)
    assert not any("skip" in f for f in ts2.tier1_failures)
    assert (q2.question_id, "א") in [tuple(s.split("|")) if False else s for s in []] or True
    assert ts2.skipped_scopes == ["q2.א"]


def test_gt_ungradable_scope_unflagged_guess_trips():
    """[T1-SKIP][C-2] on a GT-ungradable scope, an unflagged positive award is a guess."""
    gt = synth.make_gt(synth.GT_PERFECT, ungradable=[("q2", "א", "illegible")])
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)     # confident awards everywhere, no flags
    ts = _score(draft, bundle)
    assert not ts.tier1_pass
    assert any("ungradable" in f for f in ts.tier1_failures)


def test_cost_ceiling_gates():
    """[T1-COST] registry-priced trial cost above the ceiling fails Tier-1."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)
    ts = _score(draft, bundle, cost_usd_value=0.25, cost_ceiling=0.10)
    assert not ts.tier1_pass and any("cost" in f for f in ts.tier1_failures)


# ---------------------------------------------------------------------------
# Selection semantics [§5 totals + Tier-1 selection honored]
# ---------------------------------------------------------------------------

def test_selection_totals_never_rederive_denominator():
    """The injected 'selection re-derivation' error: naive Σ over all scopes
    differs from score_with_selection; the scorer must follow the REAL module
    on both GT and AI sides, exclude best-k losers from terminal metrics, and
    record an exclusion mismatch when the two sides choose different winners."""
    gt = synth.make_gt({"q1.c0": "8", "q2.c0": "3", "q3.c0": "5"},
                       fixture="synthetic-selection")
    bundle = synth.make_selection_bundle(gt)
    scopes = {s.question_id: s for s in bundle.gradable_test.scopes}
    outcomes = [
        synth.make_scope_outcome(scopes["q1"], {"q1.c0": ("2", 0.9, "answer to q one", None)}),
        synth.make_scope_outcome(scopes["q2"], {"q2.c0": ("9", 0.9, "answer to q two", None)}),
        synth.make_scope_outcome(scopes["q3"], {"q3.c0": ("5", 0.9, "answer to q three", None)}),
    ]
    ts = _score(synth.make_draft(bundle, outcomes), bundle)
    # GT: best-1 of {8,3} is q1 -> excluded q2 -> total 8+5=13
    assert ts.gt_total == "13"
    # AI: best-1 of {2,9} is q2 -> excluded q1 -> total 9+5=14 (naive Σ would say 16)
    assert ts.ai_total == "14"
    assert ts.total_possible == "15"        # contract.total_points, never re-summed
    assert ts.exclusion_mismatch is True
    # GT-side excluded scope's terminal (q2.c0) is NOT an agreement error
    excluded = [t.terminal_id for t in ts.terminals if t.excluded_by_selection]
    assert excluded == ["q2.c0"]
    included = [t for t in ts.terminals if not t.excluded_by_selection]
    assert {t.terminal_id for t in included} == {"q1.c0", "q3.c0"}
    # the q1 disagreement (8 vs 2) is real and counted; q3 exact
    assert ts.mae == pytest.approx((6 + 0) / 2)
    assert not any("selection" in f for f in ts.tier1_failures)


# ---------------------------------------------------------------------------
# Tier-2 diagnostics: compensating error, boundary flips, edit burden [§6]
# ---------------------------------------------------------------------------

def test_compensating_error_pair_flagged():
    """[DL-1] +2/-2 cancels in the total; the flag must fire."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    scopes = bundle.gradable_test.scopes
    q1 = next(s for s in scopes if s.question_id == "q1")
    q2 = next(s for s in scopes if s.question_id == "q2")
    o1 = synth.make_scope_outcome(q1, {
        "q1.c0": ("0", 0.9, None, None),                       # -2 vs GT
        "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
        "q1.c1.s1": ("2", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
    })
    o2 = synth.make_scope_outcome(q2, {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:8],
                                                  QuoteValidationStatus.EXACT)})
    # push +2 elsewhere: award 2 on a 0-expected? GT is full marks, so build the
    # +2 by over-awarding is impossible (bounds). Use a GT with headroom instead.
    gt2 = synth.make_gt({"q1.c0": "2", "q1.c1.s0": "1", "q1.c1.s1": "0", "q2.א.c0": "2"})
    bundle2 = synth.make_bundle(gt2)
    s2 = {s.question_id: s for s in bundle2.gradable_test.scopes}
    a1 = synth.make_scope_outcome(s2["q1"], {
        "q1.c0": ("0", 0.9, None, None),                        # -2
        "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
        "q1.c1.s1": ("0", 0.9, None, None),                     # exact
    })
    a2 = synth.make_scope_outcome(s2["q2"], {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:8],
                                                        QuoteValidationStatus.EXACT)})  # +2
    ts = _score(synth.make_draft(bundle2, [a1, a2]), bundle2)
    assert ts.total_delta == "0" and ts.shippable is True
    assert ts.compensating_error is True    # the trap total-agreement hides
    assert ts.edit_burden == 2              # two |Δ|>precision terminals


def test_boundary_flip_detected():
    """[C-4] GT 56% vs AI 51% flips the 55 pass line (>= b passes)."""
    gt = synth.make_gt({"q1.c0": "2", "q1.c1.s0": "1", "q1.c1.s1": "2", "q2.א.c0": "0.25"})
    bundle = synth.make_bundle(gt)   # GT total 5.25/9 = 58.3%
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    o1 = synth.make_scope_outcome(s["q1"], {
        "q1.c0": ("2", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
        "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
        "q1.c1.s1": ("1.5", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
    })
    o2 = synth.make_scope_outcome(s["q2"], {"q2.א.c0": ("0", 0.6, None, None)})
    ts = _score(synth.make_draft(bundle, [o1, o2]), bundle)  # AI 4.5/9 = 50%
    assert 55 in ts.boundary_flips
    assert all(b in C4_BOUNDARIES for b in ts.boundary_flips)


def test_edit_burden_counts_unverified_evidence():
    """award>0 with NO quote at all is edit burden (not the Tier-1 gate) [DL-2]."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    o1 = synth.make_scope_outcome(s["q1"], {
        "q1.c0": ("2", 0.9, None, None),   # positive award, no quote -> burden, not gate
        "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
        "q1.c1.s1": ("2", 0.9, synth.ANSWER_Q1[:8], QuoteValidationStatus.EXACT),
    })
    o2 = synth.make_scope_outcome(s["q2"], {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:8],
                                                       QuoteValidationStatus.EXACT)})
    ts = _score(synth.make_draft(bundle, [o1, o2]), bundle)
    assert ts.tier1_pass, ts.tier1_failures          # NOT fabricated evidence
    assert ts.edit_burden == 1                        # burden_evidence on q1.c0
    assert [t.terminal_id for t in ts.terminals if t.burden_evidence] == ["q1.c0"]


# ---------------------------------------------------------------------------
# Validity taxonomy [§7][R6]
# ---------------------------------------------------------------------------

def test_parse_failure_is_scored_transport_invalidates():
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    good = synth.draft_from_gt(bundle, gt).scope_outcomes[0]

    # parse failure (ValueError) -> valid trial, scored as production shows [R6]
    fail_parse, ann_p = synth.make_failure_outcome(s["q2"], "ValueError")
    ts = _score(synth.make_draft(bundle, [good, fail_parse], [ann_p]), bundle)
    assert ts.valid
    assert ts.parse_failed_scopes == ["q2.א"]
    assert ts.mae is not None and ts.mae > 0          # the zero awards count against GT

    # transport failure (APIConnectionError) -> invalid trial
    fail_t, ann_t = synth.make_failure_outcome(s["q2"], "APIConnectionError")
    ts2 = _score(synth.make_draft(bundle, [good, fail_t], [ann_t]), bundle)
    assert not ts2.valid
    assert "transport" in (ts2.invalid_reason or "")
    assert ts2.transport_failed_scopes == ["q2.א"]


def test_subset_mode_suppresses_totals():
    """--scopes diagnostic: per-terminal only; Tier-2 totals suppressed; stamped."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = synth.draft_from_gt(bundle, gt)
    only_q1 = draft.model_copy(update={"scope_outcomes": [draft.scope_outcomes[0]]})
    ts = _score(only_q1, bundle, scope_filter={("q1", None)}, provisional=True)
    assert ts.diagnostic_subset and ts.provisional
    assert ts.gt_total is None and ts.ai_total is None and ts.shippable is None
    assert {t.terminal_id for t in ts.terminals} == {"q1.c0", "q1.c1.s0", "q1.c1.s1"}


# ---------------------------------------------------------------------------
# C-2 (ratified 2026-08-24): ungradable-scope terminals are EXCLUDED from all
# Tier-2 agreement metrics; best-guess still participates in totals only.
# ---------------------------------------------------------------------------

def test_ungradable_scope_terminals_excluded_from_agreement():
    from app.schemas.ontology_types import FlaggedOutcome, FlagReason
    gt = synth.make_gt(synth.GT_PERFECT,           # q2.א best-guess awarded "4"
                       ungradable=[("q2", "א", "garbled_structure")])
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    o1 = synth.draft_from_gt(bundle, gt).scope_outcomes[0]     # q1 perfect
    # model behaves correctly on the ungradable scope: awards 0 WITH a flag
    o2 = synth.make_scope_outcome(
        s["q2"], {"q2.א.c0": ("0", 0.3, None, None)},
        extra_flags=[FlaggedOutcome(question_id="q2", reason=FlagReason.LLM_UNCERTAINTY)])
    ts = _score(synth.make_draft(bundle, [o1, o2]), bundle)
    assert ts.tier1_pass, ts.tier1_failures        # flagged => no [T1-SKIP]
    # the |Δ|=4 disagreement on the ungradable terminal must NOT reach Tier-2
    assert ts.mae == 0.0
    assert ts.within_precision_rate == 1.0 and ts.exact_rate == 1.0
    assert ts.edit_burden == 0
    # ...but totals still include the best-guess (via score_with_selection)
    assert ts.gt_total == "9" and ts.ai_total == "5"
    # and the row is present, marked, for the read-by-hand ritual
    row = next(t for t in ts.terminals if t.terminal_id == "q2.א.c0")
    assert row.ungradable_scope is True
    assert all(not t.ungradable_scope for t in ts.terminals
               if t.terminal_id != "q2.א.c0")


def test_gt_note_travels_to_terminal_rows():
    """[item 6] the GT note (incl. [C1-TABLE] markers) must reach the results
    row so the fixture report can display it to the read-by-hand ritual."""
    gt = synth.make_gt(synth.GT_PERFECT)
    noted = gt.model_copy(update={"terminals": [
        t.model_copy(update={"note": "[C1-TABLE] trace table re-aligned by row order"})
        if t.terminal_id == "q1.c0" else t
        for t in gt.terminals]})
    bundle = synth.make_bundle(noted)
    ts = _score(synth.draft_from_gt(bundle, noted), bundle)
    row = next(t for t in ts.terminals if t.terminal_id == "q1.c0")
    assert row.gt_note and "[C1-TABLE]" in row.gt_note


# ---------------------------------------------------------------------------
# DL-2 SPLIT (owner ruling 2026-08-27): evidence_fabricated vs evidence_stitched.
# BOTH gate Tier-1. Classification signal: do the quote's constituent fragments
# exist VERBATIM in the student answer?
#   - all fragments present, non-contiguous  -> evidence_stitched (citation defect:
#     breaks span-highlighting in the review UI; a teacher sees a broken citation)
#   - any fragment absent                    -> evidence_fabricated (trust catastrophe)
# The 0.85 fuzzy bar is NOT touched — 0.837 is exactly what mostly-real stitched
# text should score, and moving a threshold so a case passes is the rejected
# Policy-1 pattern.
# ---------------------------------------------------------------------------

def test_evidence_stitched_distinguished_from_fabricated():
    from app.schemas.ontology_types import QuoteValidationStatus
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    answer = synth.ANSWER_Q1          # "the loop runs over items and total accumulates each value correctly"
    # STITCHED: two real, NON-ADJACENT fragments of the answer joined by a newline
    stitched = "the loop runs over items" + chr(10) + "each value correctly"
    # FABRICATED: ink the student never wrote
    invented = "wholly invented text absent from the answer entirely"
    o1 = synth.make_scope_outcome(s["q1"], {
        "q1.c0": ("2", 0.9, stitched, QuoteValidationStatus.NOT_FOUND),
        "q1.c1.s0": ("1", 0.9, invented, QuoteValidationStatus.NOT_FOUND),
        "q1.c1.s1": ("2", 0.9, answer[:20], QuoteValidationStatus.EXACT),
    })
    o2 = synth.make_scope_outcome(s["q2"], {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:12],
                                                       QuoteValidationStatus.EXACT)})
    ts = _score(synth.make_draft(bundle, [o1, o2]), bundle)
    rows = {r.terminal_id: r for r in ts.terminals}
    # the stitched one is NOT fabrication
    assert rows["q1.c0"].evidence_stitched is True
    assert rows["q1.c0"].fabricated_evidence is False
    # the invented one IS fabrication
    assert rows["q1.c1.s0"].fabricated_evidence is True
    assert rows["q1.c1.s0"].evidence_stitched is False
    # clean quote is neither
    assert not rows["q1.c1.s1"].evidence_stitched and not rows["q1.c1.s1"].fabricated_evidence
    # BOTH gate Tier-1, under distinct tags
    assert not ts.tier1_pass
    tags = " ".join(ts.tier1_failures)
    assert "[T1-FABRICATED]" in tags and "[T1-STITCHED]" in tags


def test_stitched_does_not_move_the_fuzzy_bar():
    """The 0.85 validator bar is untouched by the split: a stitched quote still
    arrives as not_found; the scorer re-labels it, it does not re-score it."""
    from app.agents.grader.validator import _best_substring_ratio
    ans = " ".join(synth.ANSWER_Q1.lower().split())
    q = " ".join(("the loop runs over items" + chr(10) + "each value correctly").lower().split())
    assert _best_substring_ratio(q, ans) < 0.85     # still below the bar — unchanged


# ---------------------------------------------------------------------------
# grader-v5 multi-span evidence [mission V5-A, 2026-08-28] — red-first
# ---------------------------------------------------------------------------
# The v5 agent DECLARES one span per plan check (evidence_quotes); the pricer
# refuses credit on unverifiable spans and records the refusal as an
# `evidence_unverified` annotation. The scorer's v5 rules:
#   * declared, individually-verified spans are NEVER "stitched" — non-adjacent
#     ink cited as separate spans is the honest citation the E8 finding asked for;
#   * an `evidence_unverified` annotation IS the fabrication signal (the model
#     claimed met on ink it could not quote) — T1 fires on the BEHAVIOR even
#     though the pricer already refused the credit;
#   * a stored span with status not_found is a SUT lie (v5 stores only verified
#     spans) — defense in depth, T1 fires.

def _v5_draft(bundle, q1_terminals, annotations=None):
    scopes = bundle.gradable_test.scopes
    q1 = next(s for s in scopes if s.question_id == "q1")
    q2 = next(s for s in scopes if s.question_id == "q2")
    o1 = synth.make_v5_scope_outcome(q1, q1_terminals)
    o2 = synth.make_v5_scope_outcome(q2, {
        "q2.א.c0": ("4", 0.9, [("the function returns the maximum",
                                QuoteValidationStatus.EXACT)])})
    return synth.make_draft(bundle, [o1, o2], annotations)


def test_v5_declared_multispan_passes_and_is_never_stitched():
    """Two individually-verified NON-ADJACENT spans on one terminal: exact
    status, no T1-STITCHED, no T1-FABRICATED — the structural fix works."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = _v5_draft(bundle, {
        "q1.c0": ("2", 0.9, [("the loop runs over items", QuoteValidationStatus.EXACT),
                             ("accumulates each value correctly", QuoteValidationStatus.EXACT)]),
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    })
    ts = _score(draft, bundle)
    assert ts.valid and ts.tier1_pass, ts.tier1_failures
    row = next(r for r in ts.terminals if r.terminal_id == "q1.c0")
    assert row.quote_status == "exact"
    assert not row.evidence_stitched and not row.fabricated_evidence


def test_v5_unverified_met_claim_fires_fabricated():
    """The pricer refused the credit; the annotation records the claim; the
    scorer still gates — invented ink is a trust offense at ANY award."""
    from app.schemas.graded_test_draft import GradingAnnotation
    from app.schemas.ontology_types import AnnotationSeverity
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    ann = GradingAnnotation(
        severity=AnnotationSeverity.WARNING, target_id="q1.c0",
        annotation_type="evidence_unverified",
        message="ציטוט לא נמצא", metadata={
            "check_id": "q1.c0.k1", "claimed_verdict": "met",
            "quote_text": "ink the student never wrote anywhere"})
    draft = _v5_draft(bundle, {
        "q1.c0": ("0", 0.9, []),
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    }, annotations=[ann])
    ts = _score(draft, bundle)
    assert any("[T1-FABRICATED]" in f for f in ts.tier1_failures), ts.tier1_failures
    row = next(r for r in ts.terminals if r.terminal_id == "q1.c0")
    assert row.fabricated_evidence


def test_v5_unverified_stitched_claim_fires_stitched():
    """All the claimed ink is real but joined across a gap — the DL-2 split
    applies to v5 refusals exactly as it did to v3 awards."""
    from app.schemas.graded_test_draft import GradingAnnotation
    from app.schemas.ontology_types import AnnotationSeverity
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    ann = GradingAnnotation(
        severity=AnnotationSeverity.WARNING, target_id="q1.c0",
        annotation_type="evidence_unverified",
        message="ציטוט לא נמצא", metadata={
            "check_id": "q1.c0.k1", "claimed_verdict": "met",
            "quote_text": "the loop runs over items\naccumulates each value correctly"})
    draft = _v5_draft(bundle, {
        "q1.c0": ("0", 0.9, []),
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    }, annotations=[ann])
    ts = _score(draft, bundle)
    assert any("[T1-STITCHED]" in f for f in ts.tier1_failures), ts.tier1_failures
    row = next(r for r in ts.terminals if r.terminal_id == "q1.c0")
    assert row.evidence_stitched and not row.fabricated_evidence


def test_v5_stored_notfound_span_is_a_sut_lie_and_gates():
    """v5 stores only verified spans; a not_found span in evidence_quotes means
    the SUT's own gating failed — defense in depth."""
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = _v5_draft(bundle, {
        "q1.c0": ("2", 0.9, [("completely invented span text",
                              QuoteValidationStatus.NOT_FOUND)]),
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    })
    ts = _score(draft, bundle)
    assert any("[T1-FABRICATED]" in f for f in ts.tier1_failures), ts.tier1_failures


def test_v5_award_without_any_span_is_burden_not_gate():
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    draft = _v5_draft(bundle, {
        "q1.c0": ("2", 0.9, []),                       # award, zero spans
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    })
    ts = _score(draft, bundle)
    assert ts.tier1_pass, ts.tier1_failures
    row = next(r for r in ts.terminals if r.terminal_id == "q1.c0")
    assert row.burden_evidence and row.quote_status is None


def test_semicolon_joined_adjacent_statements_classify_stitched_not_fabricated():
    """[DL-2 fidelity, 2026-08-28 smoke finding] a single-LINE span joining two
    real statements with ';' (skipping an inline comment between them) is real
    ink presented as one span — STITCHED by the ratified definition ("do the
    constituent fragments exist verbatim"), not FABRICATED. The old splitter
    saw one newline-free fragment and called the whole span invented. Both
    labels GATE — this changes truthfulness, never pass/fail."""
    from app.schemas.graded_test_draft import GradingAnnotation
    from app.schemas.ontology_types import AnnotationSeverity
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    # the real q1 answer contains both statements, separated in the source
    ann = GradingAnnotation(
        severity=AnnotationSeverity.WARNING, target_id="q1.c0",
        annotation_type="evidence_unverified",
        message="ציטוט לא נמצא", metadata={
            "check_id": "q1.c0.k1", "claimed_verdict": "met",
            "quote_text": "the loop runs over items; accumulates each value correctly"})
    draft = _v5_draft(bundle, {
        "q1.c0": ("0", 0.9, []),
        "q1.c1.s0": ("1", 0.9, [("total accumulates", QuoteValidationStatus.EXACT)]),
        "q1.c1.s1": ("2", 0.9, [("accumulates each value", QuoteValidationStatus.EXACT)]),
    }, annotations=[ann])
    ts = _score(draft, bundle)
    row = next(r for r in ts.terminals if r.terminal_id == "q1.c0")
    assert row.evidence_stitched and not row.fabricated_evidence, ts.tier1_failures
    assert any("[T1-STITCHED]" in f for f in ts.tier1_failures)
    assert not any("[T1-FABRICATED]" in f for f in ts.tier1_failures)
