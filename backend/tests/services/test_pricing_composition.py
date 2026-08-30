"""
PR-G5 — override overlay v2 and pricing composition.

`app/services/pricing.py` is THE composition point: grading, `/draft`,
`/approve`, the batch feed's `total_awarded` and the fixture generator all price
through it, so a teacher can never review one number and have a different one
frozen (the §5 catastrophe in miniature).

R-2 branch B (production count = 0): an override is a VERDICT on a CHECK. There
is no `points_awarded` on an override and no dual-path pricer — points are
derived, always, in one direction.

Pure: zero mocks, no DB, no provider.
"""
from decimal import Decimal

import pytest

from app.schemas.graded_test_draft import Check

PRECISION = Decimal("0.25")


def _check(cid, kind="required", points="0", tariff=None, verdict="met",
           quote_status="exact", charge_group=None):
    return Check(check_id=cid, text=cid, kind=kind, points=Decimal(points),
                 tariff=None if tariff is None else Decimal(tariff),
                 partial_fraction=Decimal("0.5"), verdict=verdict,
                 quote="q" if quote_status else None, quote_status=quote_status,
                 basis_he="", confidence=0.9, charge_group=charge_group)


# ---------------------------------------------------------------------------
# the arithmetic itself — one implementation, shared with the grading pricer
# ---------------------------------------------------------------------------

def test_required_check_prices_met_partial_and_not_met():
    from app.services.pricing import price_scope_checks

    got = price_scope_checks(
        [("t1", Decimal("4"), [_check("t1.k1", points="4", verdict="met")]),
         ("t2", Decimal("4"), [_check("t2.k1", points="4", verdict="partially_met")]),
         ("t3", Decimal("4"), [_check("t3.k1", points="4", verdict="not_met")])],
        PRECISION)
    assert got == {"t1": Decimal("4"), "t2": Decimal("2"), "t3": Decimal("0")}


def test_ai_met_on_an_unverified_span_earns_nothing():
    """Evidence gating: the MODEL does not get credit for a citation that is
    not in the answer. This is the invented-credit guard."""
    from app.services.pricing import price_scope_checks

    got = price_scope_checks(
        [("t1", Decimal("4"), [_check("t1.k1", points="4", verdict="met",
                                      quote_status="not_found")])], PRECISION)
    assert got["t1"] == Decimal("0")


def test_a_teacher_override_is_not_evidence_gated():
    """...but the TEACHER is the authority (§2). She has the paper in front of
    her; refusing her credit because the MODEL's citation did not validate would
    make her argue with the machine about a fact she can see. Gating protects
    against the model inventing credit, not against the teacher deciding."""
    from app.services.pricing import price_scope_checks

    overridden = _check("t1.k1", points="4", verdict="met", quote_status="not_found")
    got = price_scope_checks([("t1", Decimal("4"), [overridden])], PRECISION,
                             overridden_check_ids={"t1.k1"})
    assert got["t1"] == Decimal("4")


def test_tariff_charge_group_is_deduped_across_the_whole_scope():
    """Same defect, charged once per scope — the first firing member pays the
    MAX fired amount. Composition is scope-wide for exactly this reason."""
    from app.services.pricing import price_scope_checks

    got = price_scope_checks(
        [("t1", Decimal("5"), [_check("t1.k1", points="5", verdict="met"),
                               _check("t1.k2", kind="tariff", tariff="1",
                                      verdict="not_met", charge_group="g")]),
         ("t2", Decimal("5"), [_check("t2.k1", points="5", verdict="met"),
                               _check("t2.k2", kind="tariff", tariff="2",
                                      verdict="not_met", charge_group="g")])],
        PRECISION)
    # one charge of MAX(1,2)=2, paid by the first firing member
    assert got["t1"] == Decimal("3") and got["t2"] == Decimal("5")


def test_note_only_never_moves_points():
    from app.services.pricing import price_scope_checks
    got = price_scope_checks(
        [("t1", Decimal("4"), [_check("t1.k1", points="4", verdict="met"),
                               _check("t1.k2", kind="note_only", verdict="not_met")])],
        PRECISION)
    assert got["t1"] == Decimal("4")


def test_award_is_clamped_and_snapped_to_the_grid():
    from app.services.pricing import price_scope_checks
    got = price_scope_checks(
        [("t1", Decimal("2"), [_check("t1.k1", points="2", verdict="met"),
                               _check("t1.k2", kind="tariff", tariff="5",
                                      verdict="not_met")])], PRECISION)
    assert got["t1"] == Decimal("0"), "never negative"


# ---------------------------------------------------------------------------
# pricer-parity: the grading pricer and the composer are ONE arithmetic
# ---------------------------------------------------------------------------

def test_compose_with_no_overlay_reproduces_the_grading_pricer():
    """The parity that makes one pricer true. If these ever diverge, the teacher
    reviews one number and a different one freezes."""
    from app.agents.grader.pricer import AssessedVerdict, price_scope
    from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan
    from app.schemas.ontology_types import QuoteValidationStatus
    from app.services.pricing import price_scope_checks

    plan = TerminalPlan(terminal_id="t1", points_possible=Decimal("4"), checks=[
        PlanCheck(check_id="t1.k1", description_he="a", kind="required", points=Decimal("3")),
        PlanCheck(check_id="t1.k2", description_he="b", kind="tariff",
                  tariff_amount=Decimal("1")),
    ])
    verdicts = {
        "t1.k1": AssessedVerdict("t1.k1", "partially_met", 0.9, "", "q",
                                 QuoteValidationStatus.EXACT),
        "t1.k2": AssessedVerdict("t1.k2", "not_met", 0.9, "", "", None),
    }
    priced = price_scope([plan], verdicts, PRECISION)["t1"]
    composed = price_scope_checks([("t1", Decimal("4"), priced.checks)], PRECISION)

    assert composed["t1"] == priced.points_awarded


# ---------------------------------------------------------------------------
# the overlay shape (R-2 branch B)
# ---------------------------------------------------------------------------

def test_override_is_a_verdict_on_a_check_with_no_points_path():
    from app.schemas.graded_test_draft import GradedTestOverrides, TeacherOverride

    assert "points_awarded" not in TeacherOverride.model_fields, (
        "R-2 branch B: production count is 0, so there is ONE representation of "
        "an override and no dual-path pricer")
    for required in ("check_id", "verdict"):
        assert TeacherOverride.model_fields[required].is_required()

    ov = GradedTestOverrides()
    assert ov.terminals == {} and ov.feedback == {} and ov.stamp_position is None


# ---------------------------------------------------------------------------
# contract-points-derived-from-verdicts (R-9 condition i)
# ---------------------------------------------------------------------------

def test_contract_points_are_derived_from_verdicts_on_both_sides():
    """Removing `points_awarded` from the override must NOT cost the eval suite
    its points-level gold: the contract still carries ai_points_awarded and
    final_points_awarded, and BOTH are derived by the pricer — ai from the AI
    verdicts, final from the effective ones. Copying the draft's stored points
    for the AI side would reintroduce a second source of truth."""
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from services.test_graded_test_contract_compiler import (            # noqa: E402
        _draft, _leaf_criterion, _ov, _rubric_contract, _scope)
    from app.services.graded_test_contract_compiler import compile_graded_test

    crit = _leaf_criterion(points_possible="5", points_awarded="4")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])

    contract = compile_graded_test(draft, _ov("q1.c0", "q1.c0.k1", "met"),
                                   _rubric_contract())
    t = contract.scope_outcomes[0].terminal_outcomes[0]

    assert t.ai_points_awarded == Decimal("4")     # derived from the AI verdict
    assert t.final_points_awarded == Decimal("5")  # derived from hers
    assert t.was_overridden is True
    # and the per-check provenance survives the freeze
    check = t.checks[0]
    assert check.ai_verdict == "partially_met" and check.final_verdict == "met"


def test_override_preserves_proposal_provenance():
    """What the AI said is immutable. Her decision rides beside it — the
    contract never overwrites the model's verdict with hers."""
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from services.test_graded_test_contract_compiler import (            # noqa: E402
        _draft, _leaf_criterion, _ov, _rubric_contract, _scope)
    from app.services.graded_test_contract_compiler import compile_graded_test

    crit = _leaf_criterion(points_possible="5", points_awarded="5")   # AI said met
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])

    contract = compile_graded_test(draft, _ov("q1.c0", "q1.c0.k1", "not_met",
                                              comment="לא מופיע בתשובה"),
                                   _rubric_contract())
    check = contract.scope_outcomes[0].terminal_outcomes[0].checks[0]

    assert check.ai_verdict == "met"          # the AI's record, untouched
    assert check.final_verdict == "not_met"   # hers, beside it
    assert check.was_overridden is True
    assert check.teacher_comment == "לא מופיע בתשובה"


def test_revert_clears_the_override_and_its_note():
    """Reverting is removing the decision from the sparse overlay — not writing
    an override that happens to agree with the AI. The difference is visible:
    was_overridden goes back to False and the note is gone."""
    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    from services.test_graded_test_contract_compiler import (            # noqa: E402
        _draft, _leaf_criterion, _no_ov, _ov, _rubric_contract, _scope)
    from app.services.graded_test_contract_compiler import compile_graded_test

    crit = _leaf_criterion(points_possible="5", points_awarded="5")
    draft = _draft(scope_outcomes=[_scope(criterion_outcomes=[crit])])

    overridden = compile_graded_test(
        draft, _ov("q1.c0", "q1.c0.k1", "not_met", comment="נמחק"), _rubric_contract())
    assert overridden.scope_outcomes[0].terminal_outcomes[0].checks[0].was_overridden

    reverted = compile_graded_test(draft, _no_ov(), _rubric_contract())
    t = reverted.scope_outcomes[0].terminal_outcomes[0]
    assert t.checks[0].was_overridden is False
    assert t.checks[0].teacher_comment is None
    assert t.final_points_awarded == t.ai_points_awarded == Decimal("5")
