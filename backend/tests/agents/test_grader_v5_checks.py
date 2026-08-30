"""
PR-G1 — v5 checks on the production wire.

Census A established this is PLUMBING, not modelling: the verifier already
produces the whole record (`AssessedVerdict{check_id, verdict, confidence,
basis_he, quote_text, quote_status}`) and the pricer consumes it — but
`PricedTerminal` keeps none of it, so `_leaf_fields` serialises six aggregate
fields and the per-check truth is discarded. No new model call, no prompt
change, no re-grade: stop throwing the data away.

Zero provider calls (CLAUDE.md §8): the pricer is pure and the agent seam is a
fake.
"""
from decimal import Decimal

import pytest

from app.agents.grader.pricer import AssessedVerdict, price_scope
from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan
from app.schemas.ontology_types import QuoteValidationStatus

PRECISION = Decimal("0.25")


def _plan(terminal_id: str = "q1.c0") -> TerminalPlan:
    return TerminalPlan(
        terminal_id=terminal_id,
        points_possible=Decimal("4"),
        checks=[
            PlanCheck(check_id=f"{terminal_id}.k1", description_he="הצהרת המערך",
                      kind="required", points=Decimal("3")),
            PlanCheck(check_id=f"{terminal_id}.k2", description_he="שם משתנה שגוי",
                      kind="tariff", tariff_amount=Decimal("1")),
            PlanCheck(check_id=f"{terminal_id}.k3", description_he="הערה בלבד",
                      kind="note_only"),
        ],
    )


def _verdicts(terminal_id: str = "q1.c0"):
    return {
        f"{terminal_id}.k1": AssessedVerdict(
            check_id=f"{terminal_id}.k1", verdict="met", confidence=0.94,
            basis_he="", quote_text="int[] arr = new int[25];",
            quote_status=QuoteValidationStatus.EXACT),
        f"{terminal_id}.k2": AssessedVerdict(
            check_id=f"{terminal_id}.k2", verdict="not_met", confidence=0.8,
            basis_he="השם תקין", quote_text="", quote_status=None),
        f"{terminal_id}.k3": AssessedVerdict(
            check_id=f"{terminal_id}.k3", verdict="partially_met", confidence=0.55,
            basis_he="חלקי", quote_text="cw(x)", quote_status=QuoteValidationStatus.FUZZY),
    }


# ---------------------------------------------------------------------------
# draft-persists-v5-checks
# ---------------------------------------------------------------------------

def test_pricer_carries_the_check_record_it_already_has():
    """The pricer decides every verdict's price; it must stop discarding the
    verdicts. Pure — this is the seam where the data was being dropped."""
    priced = price_scope([_plan()], _verdicts(), PRECISION)["q1.c0"]

    assert hasattr(priced, "checks"), "PricedTerminal still discards the checks"
    by_id = {c.check_id: c for c in priced.checks}
    assert set(by_id) == {"q1.c0.k1", "q1.c0.k2", "q1.c0.k3"}

    k1 = by_id["q1.c0.k1"]
    assert k1.verdict == "met"
    assert k1.text == "הצהרת המערך"           # the plan's own phrasing
    assert k1.kind == "required"
    assert k1.points == Decimal("3")
    assert k1.quote == "int[] arr = new int[25];"
    assert k1.quote_status == "exact"
    assert k1.confidence == 0.94

    k2 = by_id["q1.c0.k2"]
    assert k2.kind == "tariff" and k2.tariff == Decimal("1")
    assert k2.quote is None and k2.quote_status is None   # not_met, no evidence
    assert k2.basis_he == "השם תקין"

    assert by_id["q1.c0.k3"].quote_status == "fuzzy"


def test_check_carries_what_the_client_needs_to_reprice():
    """§1.1 makes the terminal's awarded_points DERIVED and has the frontend
    re-derive it from checks[].verdict. That is only possible if each check
    carries its own pricing inputs — kind, points, tariff, partial_fraction.
    A verdict plus a bare `tariff` cannot price a `required` check."""
    priced = price_scope([_plan()], _verdicts(), PRECISION)["q1.c0"]
    for c in priced.checks:
        for field in ("kind", "points", "tariff", "partial_fraction"):
            assert hasattr(c, field), f"Check lacks {field}: cannot be re-priced client-side"


def test_check_has_no_audit_field():
    """R-8: `audit` is reserved out of v1 — dropped from the wire, not shipped
    dark. It lands with the audit spec."""
    from app.schemas.graded_test_draft import Check
    assert "audit" not in Check.model_fields


# ---------------------------------------------------------------------------
# checks-required-under-v5-pin  (OD-G1.3)
# ---------------------------------------------------------------------------

def test_checks_required_under_v5_pin():
    """Optional on the type (v3 drafts have none and must stay parseable),
    validator-required whenever plan_version is set."""
    from app.schemas.graded_test_draft import CriterionOutcome, GradedTestDraft, ScopeOutcome

    leaf = CriterionOutcome(
        criterion_id="q1.c0", description="d", points_possible=Decimal("4"),
        points_awarded=Decimal("3"), reasoning="r", confidence=0.9,
        sub_criterion_outcomes=None, checks=None,
    )
    scope = ScopeOutcome(
        scope_kind="direct", question_id="q1", points_possible=Decimal("4"),
        points_awarded=Decimal("3"), min_confidence=0.9,
        criterion_outcomes=[leaf], graded_by="llm", input_tokens=1, output_tokens=1,
    )
    common = dict(
        rubric_contract_version="rc", transcription_contract_version="tc",
        model_version="m", prompt_version="p", scope_outcomes=[scope],
        llm_calls_count=1, grading_duration_ms=1,
        total_input_tokens=1, total_output_tokens=1,
    )

    # v3 draft: no plan_version, no checks — still valid
    GradedTestDraft(**common)

    # v5 draft: plan_version set, terminal without checks — refused
    with pytest.raises(Exception) as ei:
        GradedTestDraft(**common, plan_version="hobby_tvshow/v3")
    assert "check" in str(ei.value).lower()


# ---------------------------------------------------------------------------
# Code-review findings (2026-08-31) — both are defects in PR-G1 as landed
# ---------------------------------------------------------------------------

def test_checks_validator_tolerates_a_scope_that_was_skipped_then_excluded():
    """BUG: the validator skipped only `failed` and `skipped_no_answer`, but
    graded_by has FOUR states. `excluded_by_selection` is applied AFTER grading
    by grading_runner's model_copy, and it OVERWRITES the previous value — so a
    scope the student left blank that also misses the best-k cut ends up
    `excluded_by_selection` with checks=None.

    On a choose-k exam that is the common case, not a corner: the questions a
    student skips are exactly the ones excluded. The draft would be written
    fine and then fail to re-parse on every GET / draft / approve.

    The precise rule is 'the LLM produced verdicts', i.e. graded_by == 'llm'.
    """
    from app.schemas.graded_test_draft import CriterionOutcome, GradedTestDraft, ScopeOutcome

    leaf = CriterionOutcome(
        criterion_id="q1.c0", description="d", points_possible=Decimal("4"),
        points_awarded=Decimal("0"), reasoning="", confidence=0.0,
        sub_criterion_outcomes=None, checks=None,
    )
    scope = ScopeOutcome(
        scope_kind="direct", question_id="q1", points_possible=Decimal("4"),
        points_awarded=Decimal("0"), min_confidence=0.0,
        criterion_outcomes=[leaf], graded_by="excluded_by_selection",
        input_tokens=0, output_tokens=0,
    )
    GradedTestDraft(
        rubric_contract_version="rc", transcription_contract_version="tc",
        model_version="m", prompt_version="p", plan_version="hobby_tvshow/v3",
        scope_outcomes=[scope], llm_calls_count=0, grading_duration_ms=1,
        total_input_tokens=0, total_output_tokens=0,
    )


def test_check_keeps_the_span_the_model_cited_even_when_it_is_not_found():
    """BUG: `quote` was dropped whenever the span failed validation, so an
    invented-credit case reached the teacher as `quote=None,
    quote_status="not_found"` — she could see THAT a citation failed but not
    WHAT was cited, which is the one thing needed to judge it.

    §1.1: quote is 'the verbatim span the model cited (None when not_met with
    no evidence)'. Not-found is evidence of a problem, not absence of evidence.
    """
    plan = TerminalPlan(
        terminal_id="q1.c0", points_possible=Decimal("3"),
        checks=[PlanCheck(check_id="q1.c0.k1", description_he="הצהרה",
                          kind="required", points=Decimal("3"))])
    verdicts = {"q1.c0.k1": AssessedVerdict(
        check_id="q1.c0.k1", verdict="met", confidence=0.9, basis_he="",
        quote_text="int[] invented = new int[9];",
        quote_status=QuoteValidationStatus.NOT_FOUND)}

    priced = price_scope([plan], verdicts, PRECISION)["q1.c0"]
    check = priced.checks[0]

    assert check.quote_status == "not_found"
    assert check.quote == "int[] invented = new int[9];", (
        "the cited span was dropped — the teacher cannot see what was claimed")
    # and no credit was given for it
    assert priced.points_awarded == Decimal("0")
