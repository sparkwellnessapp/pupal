"""
PR-G8 — the two pure numbers on a batch card: look_count and the ETA.

Both are pure functions with zero mocks. They are the numbers a teacher plans
her evening around, so each has one job and neither may invent a figure it does
not have the inputs for.
"""
from decimal import Decimal

import pytest

from app.schemas.graded_test_draft import (
    Check, CriterionOutcome, GradedTestDraft, ScopeOutcome)
from app.schemas.ontology_types import FlaggedOutcome, FlagReason


def _check(cid, verdict="met", quote_status="exact"):
    return Check(check_id=cid, text=cid, kind="required", points=Decimal("3"),
                 partial_fraction=Decimal("0.5"), verdict=verdict,
                 quote="q" if quote_status else None, quote_status=quote_status,
                 basis_he="", confidence=0.9)


def _draft(scopes, plan_version="plan/v1"):
    """plan_version=None builds a V3-ERA draft — no checks, and the PR-G1
    validator correctly refuses to call it v5."""
    return GradedTestDraft(
        rubric_contract_version="rc", transcription_contract_version="tc",
        model_version="m", prompt_version="p", plan_version=plan_version,
        scope_outcomes=scopes, llm_calls_count=1, grading_duration_ms=1,
        total_input_tokens=1, total_output_tokens=1)


def _scope(checks=None, graded_by="llm", flags=None, qid="q1"):
    leaf = CriterionOutcome(
        criterion_id=f"{qid}.c0", description="d", points_possible=Decimal("3"),
        points_awarded=Decimal("3"), reasoning="r", confidence=0.9,
        sub_criterion_outcomes=None, checks=checks,
        flags=flags or [])
    return ScopeOutcome(
        scope_kind="direct", question_id=qid, points_possible=Decimal("3"),
        points_awarded=Decimal("3"), min_confidence=0.9,
        criterion_outcomes=[leaf], graded_by=graded_by,
        input_tokens=1, output_tokens=1)


# ---------------------------------------------------------------------------
# look-count-includes-met-with-notfound
# ---------------------------------------------------------------------------

def test_look_count_includes_a_met_check_whose_quote_was_not_found():
    """THE case this number exists for: the model claimed a check was met and
    cited a span that is not in the answer. That is invented credit, and it is
    invisible in the score — the points look ordinary. If look_count misses it,
    nothing routes the teacher's eye there."""
    from app.services.look_count import look_count

    clean = _draft([_scope(checks=[_check("k1", "met", "exact")])])
    invented = _draft([_scope(checks=[_check("k1", "met", "not_found")])])

    assert look_count(clean) == 0
    assert look_count(invented) == 1


def test_look_count_counts_each_deterministic_marker_once():
    """Fuzzy evidence, bounds-clamped, closed-world, a skipped scope and a
    failed scope each earn exactly one look — no double counting when a scope
    carries several."""
    from app.services.look_count import look_count

    assert look_count(_draft([_scope(checks=[_check("k1", "met", "fuzzy")])])) == 1
    assert look_count(_draft([_scope(checks=[_check("k1")], graded_by="skipped_no_answer")])) == 1
    assert look_count(_draft([_scope(checks=[_check("k1")], graded_by="failed")])) == 1

    clamped = _scope(checks=[_check("k1")], flags=[FlaggedOutcome(
        criterion_id="q1.c0", reason=FlagReason.BOUNDS_CLAMPED, message="x")])
    assert look_count(_draft([clamped])) == 1

    both = _scope(checks=[_check("k1", "met", "not_found"), _check("k2", "met", "fuzzy")])
    assert look_count(_draft([both])) == 2, "two distinct markers, two looks"


def test_look_count_ignores_an_excluded_scope():
    """A scope excluded by selection was never owed — it is not a thing to look
    at, and counting it would send her hunting for a problem that does not
    exist (the needs_eyes over-count lesson, §3.5a)."""
    from app.services.look_count import look_count
    assert look_count(_draft([_scope(checks=None, graded_by="excluded_by_selection")])) == 0


# ---------------------------------------------------------------------------
# eta-two-stage / eta-never-constant
# ---------------------------------------------------------------------------

def test_eta_is_unknown_without_a_latency_profile():
    """No profile ⇒ `unknown`, and the client says «עוד רגע». Inventing a
    number here would be a confident guess about the one thing she is waiting
    on."""
    from app.services.eta import estimate_eta
    got = estimate_eta(profile_p50=None, scope_count=6, landed_durations=[])
    assert got["kind"] == "unknown" and got["seconds"] is None


def test_eta_first_stage_scales_with_WAVES_not_a_constant():
    """Before anything lands, the estimate comes from the model's p50 scaled by
    WAVE COUNT — the fixtures are 6-scope (two waves at MAX_CONCURRENT_SCOPES=5),
    so the profile is normalised by that. A 15-scope test is three waves and
    must not be told the same number as a 6-scope one."""
    from app.services.eta import estimate_eta

    six = estimate_eta(profile_p50=120.0, scope_count=6, landed_durations=[])
    fifteen = estimate_eta(profile_p50=120.0, scope_count=15, landed_durations=[])

    assert six["kind"] == "first_landing"
    assert six["seconds"] == 120          # 120 * ceil(6/5)=2 waves / 2 = 120
    assert fifteen["seconds"] == 180      # 120 * ceil(15/5)=3 / 2 = 180
    assert fifteen["seconds"] != six["seconds"], "the ETA must not be constant"


def test_eta_second_stage_uses_p90_of_what_this_batch_actually_did():
    """Once tests start landing, this batch's own observed durations beat any
    profile — same provider, same evening, same queue depth."""
    from app.services.eta import estimate_eta

    got = estimate_eta(profile_p50=120.0, scope_count=6,
                       landed_durations=[100.0, 110.0, 300.0])
    assert got["kind"] == "remaining"
    assert got["seconds"] == 300          # p90 of the observed landings


# ---------------------------------------------------------------------------
# Code-review findings on G8 (2026-08-31)
# ---------------------------------------------------------------------------

def test_look_count_covers_v3_drafts_without_double_counting_v5():
    """v3-era drafts carry no checks, so their quote problems exist only as
    FLAGS. Counting those flags unconditionally would double-count a v5 leaf —
    once as the flag, once as the check's quote_status — so they count only
    where there are no checks."""
    from app.services.look_count import look_count

    v3_leaf = _scope(checks=None, flags=[FlaggedOutcome(
        criterion_id="q1.c0", reason=FlagReason.QUOTE_NOT_FOUND, message="x")])
    assert look_count(_draft([v3_leaf], plan_version=None)) == 1, (
        "a v3 quote problem must route her eye")

    v5_leaf = _scope(checks=[_check("k1", "met", "not_found")],
                     flags=[FlaggedOutcome(criterion_id="q1.c0",
                                           reason=FlagReason.QUOTE_NOT_FOUND,
                                           message="x")])
    assert look_count(_draft([v5_leaf])) == 1, "the same problem counted twice"


def test_eta_scope_count_follows_the_leaf_rule_for_nested_rubrics():
    """Scopes are LEAVES at any depth (PR-3): a sub-question WITH children
    contributes no scope of its own. A naive len(sub_questions) over-counts
    every nested rubric and quotes an ETA for waves that never run."""
    from app.api.v0.batch_grading import _count_leaf_scopes

    flat = {"questions": [{"sub_questions": [{}, {}, {}]}]}
    assert _count_leaf_scopes(flat) == 3

    nested = {"questions": [{"sub_questions": [
        {"sub_questions": [{}, {}]},      # a parent: 2 leaves, not 1
        {},                                # a leaf
    ]}]}
    assert _count_leaf_scopes(nested) == 3, "the parent must not count as a scope"

    direct = {"questions": [{}, {}]}       # no sub-questions: each is its own scope
    assert _count_leaf_scopes(direct) == 2
