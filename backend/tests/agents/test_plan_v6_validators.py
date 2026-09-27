"""grader-v6 Phase 1 — validators V12–V20 (PR_grader_v6_options.md §3.4, as
amended: AM-G1 no home terminals, AM-G4 count exemption, Q-10 note shape,
Q-11 folds precede markers). Pure, zero mocks."""
from __future__ import annotations

from decimal import Decimal as D
from typing import List

from app.agents.grader.plan_schemas import (
    CheckOption,
    DeductionMarker,
    MarkerDisposition,
    PlanCheckV6,
    TerminalPlanV6,
)
from app.agents.grader.plan_validator_v6 import (
    PlanContext,
    SkeletonComponent,
    validate_plan_v6,
    v19_fault_leak_candidates,
)
from app.agents.grader.plan_values import (
    count_options,
    credit_binary_options,
    credit_ladder_options,
    fault_options,
    note_options,
)

GRID = D("0.25")
TEACHER = "עדכון נכון של התכונה people בעזרת SetPeople ו-GetPeople אם לא השתמשו בפעולה הפנימית להוריד 2"


def _credit(cid="t1.c1", max_value=D("4"), span="עדכון נכון של התכונה people", **kw):
    return PlanCheckV6(check_id=cid, role="credit", shape="binary",
                       description_he="עדכון התכונה people", source_span=span,
                       options=credit_binary_options(max_value, "עודכן", "לא עודכן"),
                       priced_terminal_id=kw.pop("tid", "t1"), origin="planner", **kw)


def _fault(cid="t1.f1", markers=(("m1", D("2"), "העדכון בגישה ישירה"),), **kw):
    return PlanCheckV6(check_id=cid, role="fault", shape="fault",
                       description_he="אופן העדכון", source_span=kw.pop("span", "להוריד 2"),
                       options=fault_options(list(markers), "ללא טעות"),
                       priced_terminal_id=kw.pop("tid", "t1"), origin="planner", **kw)


def _marker(mid="m1", amount=D("2"), home="t1", anchors=("t1",), group=None,
            polarity="deduct", text="אם לא השתמשו בפעולה הפנימית להוריד 2"):
    return DeductionMarker(marker_id=mid, home_terminal_id=home, amount=amount,
                           polarity=polarity, text_span=text, charge_group=group,
                           candidate_anchors=list(anchors))


def _ctx(terminals: List[TerminalPlanV6], **kw) -> PlanContext:
    scopes = kw.pop("scopes", {t.terminal_id: "q1" for t in terminals})
    return PlanContext(
        precision=GRID,
        contract_terminal_points={t.terminal_id: t.points_possible for t in terminals},
        terminal_scopes=scopes,
        terminal_texts=kw.pop("terminal_texts", {t.terminal_id: TEACHER for t in terminals}),
        scope_question_text=kw.pop("scope_question_text", {"q1": ""}),
        scope_example_solution=kw.pop("scope_example_solution", {"q1": ""}),
        markers=kw.pop("markers", []),
        dispositions=kw.pop("dispositions", []),
        skeleton=kw.pop("skeleton", {}),
    )


def _t(tid="t1", p=D("4")):
    return TerminalPlanV6(terminal_id=tid, points_possible=p, interpretation_notes_he=[])


def _errs(checks, terminals=None, **kw):
    terminals = terminals or [_t()]
    return validate_plan_v6(terminals, checks, _ctx(terminals, **kw))


def _has(errs, tag):
    return any(e.startswith(tag) for e in errs)


def test_a_clean_plan_passes():
    m = _marker()
    errs = _errs([_credit(), _fault(requires="t1.c1")], markers=[m],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")])
    assert errs == []


# ── V12 OptionShape ──────────────────────────────────────────────────────────

def test_v12_rejects_credit_without_top_or_zero():
    no_zero = _credit().model_copy(update={"options": [
        CheckOption(option_id="full", label_he="x", value=D("4")),
        CheckOption(option_id="p1", label_he="y", value=D("2"))]})
    assert _has(_errs([no_zero]), "V12")
    no_top = _credit().model_copy(update={"options": [
        CheckOption(option_id="full", label_he="x", value=D("0")),
        CheckOption(option_id="absent", label_he="y", value=D("0"))]})
    assert _has(_errs([no_top]), "V12")


def test_v12_rejects_non_decreasing_options():
    bad = _credit().model_copy(update={"shape": "ladder", "options": [
        CheckOption(option_id="full", label_he="x", value=D("4")),
        CheckOption(option_id="p1", label_he="y", value=D("1")),
        CheckOption(option_id="p2", label_he="z", value=D("2")),
        CheckOption(option_id="absent", label_he="w", value=D("0"))]})
    assert _has(_errs([bad]), "V12")
    # count is exempt from uniqueness (AM-G4) but must still not increase
    cnt = PlanCheckV6(check_id="t1.c1", role="credit", shape="count", description_he="d",
                      source_span="עדכון נכון של התכונה people",
                      options=count_options(D("4"), 40, GRID), priced_terminal_id="t1",
                      origin="compiler")
    assert not _has(_errs([cnt]), "V12")


def test_v12_rejects_fault_without_none_first():
    bad = _fault().model_copy(update={"options": list(reversed(_fault().options))})
    assert _has(_errs([_credit(), bad], markers=[_marker()],
                      dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")]), "V12")
    positive = _fault().model_copy(update={"options": [
        CheckOption(option_id="none", label_he="n", value=D("0")),
        CheckOption(option_id="f1", label_he="x", value=D("1"), marker_id="m1")]})
    assert _has(_errs([_credit(), positive], markers=[_marker()],
                      dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")]), "V12")


def test_v12_note_shape_is_none_observed_zero():
    ok = PlanCheckV6(check_id="t1.n1", role="note", shape="note", description_he="n",
                     source_span="עדכון נכון של התכונה people",
                     options=note_options("הערה"), priced_terminal_id="t1", origin="compiler")
    assert not _has(_errs([_credit(), ok]), "V12")
    bad = ok.model_copy(update={"options": [
        CheckOption(option_id="none", label_he="n", value=D("0")),
        CheckOption(option_id="observed", label_he="o", value=D("-1"))]})
    assert _has(_errs([_credit(), bad]), "V12")


# ── V13 CreditSum ────────────────────────────────────────────────────────────

def test_v13_credit_sum_equals_points_possible():
    assert _has(_errs([_credit(max_value=D("3"))]), "V13")
    two = [_credit("t1.c1", D("3")), _credit("t1.c2", D("1"))]
    assert not _has(_errs(two), "V13")


# ── V14 MarkerDisposition ────────────────────────────────────────────────────

def test_v14_every_marker_disposed_exactly_once():
    m1, m2 = _marker("m1"), _marker("m2", D("3"))
    errs = _errs([_credit(), _fault(requires="t1.c1")], markers=[m1, m2],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")])
    assert _has(errs, "V14")                                            # m2 undisposed
    errs = _errs([_credit()], markers=[m1],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="not_a_deduction")])
    assert _has(errs, "V14")                                            # no reason_he
    errs = _errs([_credit()], markers=[m1],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="not_a_deduction",
                                                 reason_he="מתאר את הרכיב עצמו")])
    assert not _has(errs, "V14")


def test_v14_no_deduct_marker_never_a_fault_option():
    m = _marker(polarity="no_deduct")
    errs = _errs([_credit(), _fault(requires="t1.c1")], markers=[m],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")])
    assert _has(errs, "V14")


def test_v14_fault_value_equals_marker_amount():
    m = _marker(amount=D("3"))
    errs = _errs([_credit(), _fault(requires="t1.c1")], markers=[m],     # option −2 ≠ −3
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")])
    assert _has(errs, "V14")
    # merged: the kept option carries −min(amounts)
    ma, mb = _marker("m1", D("3")), _marker("m2", D("2"))
    f = _fault(markers=(("m1", [D("3"), D("2")], "x"),), requires="t1.c1")
    errs = _errs([_credit(), f], markers=[ma, mb], dispositions=[
        MarkerDisposition(marker_id="m1", disposition="fault"),
        MarkerDisposition(marker_id="m2", disposition="merged", merged_into_marker_id="m1",
                          reason_he="אותו תנאי, סכומים שונים")])
    assert not _has(errs, "V14")


def test_v14_fault_members_share_one_charge_group():
    ma, mb = _marker("m1", group="g1"), _marker("m2", D("3"), group="g2")
    f = _fault(markers=(("m1", D("2"), "x"), ("m2", D("3"), "y")), requires="t1.c1",
               charge_group="g1")
    errs = _errs([_credit(), f], markers=[ma, mb], dispositions=[
        MarkerDisposition(marker_id="m1", disposition="fault"),
        MarkerDisposition(marker_id="m2", disposition="fault")])
    assert _has(errs, "V14")


# ── V15 RequiresShape ────────────────────────────────────────────────────────

def test_v15_requires_only_fault_to_same_terminal_credit():
    other = [_t("t1"), _t("t2")]
    m = _marker(anchors=("t1", "t2"))
    disp = [MarkerDisposition(marker_id="m1", disposition="fault")]
    # requires a credit check on ANOTHER terminal
    errs = _errs([_credit("t1.c1"), _credit("t2.c1", tid="t2"), _fault(requires="t2.c1")],
                 terminals=other, markers=[m], dispositions=disp)
    assert _has(errs, "V15")
    # requires on a credit check
    errs = _errs([_credit(requires="t1.c1")])
    assert _has(errs, "V15")
    # requires an unknown id
    errs = _errs([_credit(), _fault(requires="t1.c9")], markers=[m], dispositions=disp)
    assert _has(errs, "V15")


def test_v15_rejects_requires_chain():
    m1, m2 = _marker("m1"), _marker("m2")
    disp = [MarkerDisposition(marker_id="m1", disposition="fault"),
            MarkerDisposition(marker_id="m2", disposition="fault")]
    f1 = _fault("t1.f1", requires="t1.c1")
    f2 = _fault("t1.f2", markers=(("m2", D("2"), "y"),), requires="t1.f1")
    assert _has(_errs([_credit(), f1, f2], markers=[m1, m2], dispositions=disp), "V15")


# ── V16 SourceSpan ───────────────────────────────────────────────────────────

def test_v16_source_span_must_be_verbatim():
    assert _has(_errs([_credit(span="עדכון שלא נכתב בכלל")]), "V16")
    # whitespace-collapsed and NFC-normalized substring passes
    assert not _has(_errs([_credit(span="עדכון   נכון\nשל התכונה people")]), "V16")
    # the scope's example solution is an allowed source
    errs = _errs([_credit(span="this.workshops[i].SetPeople(total)")],
                 scope_example_solution={"q1": "x; this.workshops[i].SetPeople(total); y"})
    assert not _has(errs, "V16")


# ── V17 Grid ─────────────────────────────────────────────────────────────────

def test_v17_values_on_grid():
    off = _credit().model_copy(update={"shape": "ladder", "options": [
        CheckOption(option_id="full", label_he="x", value=D("4")),
        CheckOption(option_id="p1", label_he="y", value=D("1.1")),
        CheckOption(option_id="absent", label_he="z", value=D("0"))]})
    assert _has(_errs([off]), "V17")


# ── V18 Placement ────────────────────────────────────────────────────────────

def test_v18_anchor_in_every_member_candidates():
    terms = [_t("t1"), _t("t2")]
    ma, mb = _marker("m1", anchors=("t1", "t2")), _marker("m2", D("3"), anchors=("t2",))
    f = _fault(markers=(("m1", D("2"), "x"), ("m2", D("3"), "y")), requires="t1.c1")
    errs = _errs([_credit("t1.c1"), _credit("t2.c1", tid="t2"), f], terminals=terms,
                 markers=[ma, mb], dispositions=[
                     MarkerDisposition(marker_id="m1", disposition="fault"),
                     MarkerDisposition(marker_id="m2", disposition="fault")])
    assert _has(errs, "V18")                        # t1 is not in m2's candidates
    # priced terminal in another scope
    errs = _errs([_credit("t1.c1"), _credit("t2.c1", tid="t2"),
                  _fault(markers=(("m1", D("2"), "x"),), tid="t2", requires="t2.c1")],
                 terminals=terms, markers=[_marker("m1", anchors=("t1", "t2"))],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")],
                 scopes={"t1": "q1", "t2": "q2"})
    assert _has(errs, "V18")


# ── V19 FaultLeakCandidate — telemetry, never blocks ─────────────────────────

def test_v19_is_telemetry_and_never_blocks():
    m = _marker(text="אם עדכנו את people ישירות במקום SetPeople להוריד 2")
    credit = _credit().model_copy(update={"description_he": "עדכון people בעזרת SetPeople"})
    f = _fault(requires="t1.c1")
    cands = v19_fault_leak_candidates([credit, f], [m])
    assert cands == [("t1.f1", "t1.c1", ["SetPeople", "people"])]
    errs = _errs([credit, f], markers=[m],
                 dispositions=[MarkerDisposition(marker_id="m1", disposition="fault")])
    assert not _has(errs, "V19")


# ── V20 SkeletonConformity ───────────────────────────────────────────────────

def test_v20_as_compiled_matches_skeleton():
    skel = {"t1": [SkeletonComponent(source_span="עדכון נכון של התכונה people", points=D("3")),
                   SkeletonComponent(source_span="SetPeople ו-GetPeople", points=D("1"))]}
    good = [_credit("t1.c1", D("3")),
            _credit("t1.c2", D("1"), span="SetPeople ו-GetPeople")]
    assert not _has(_errs(good, skeleton=skel), "V20")
    reordered = [_credit("t1.c1", D("1"), span="SetPeople ו-GetPeople"),
                 _credit("t1.c2", D("3"))]
    assert _has(_errs(reordered, skeleton=skel), "V20")
    merged = [_credit("t1.c1", D("4"))]
    assert _has(_errs(merged, skeleton=skel), "V20")
    # a ladder on a fixed component keeps its max and span — conforms
    lad, _ = credit_ladder_options(D("3"), "a", [("b", __import__(
        "app.agents.grader.plan_schemas", fromlist=["PartialFraction"]).PartialFraction.HALF)],
        "c", GRID)
    ladder = _credit("t1.c1", D("3")).model_copy(update={"shape": "ladder", "options": lad})
    assert not _has(_errs([ladder, good[1]], skeleton=skel), "V20")
