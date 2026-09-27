"""grader-v6 Phase 1 — plan types, deterministic IDs, value builders, hashing.

Pure, zero mocks (PR_grader_v6_options.md §3.1–§3.3, §3.5; AM-G4 one rounding
rule; Q-10 note checks).
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.agents.grader.plan_schemas import (
    CheckOption,
    GradingPlanV6,
    PackRef,
    PartialFraction,
    PlanCheckV6,
    TerminalPlanV6,
)
from app.agents.grader.plan_values import (
    ABSENT_LEVEL_LABEL,
    check_id,
    config_hash,
    count_options,
    credit_binary_options,
    credit_ladder_options,
    even_split,
    fault_options,
    levels_options,
    note_options,
    plan_hash,
    snap_half_up,
)

GRID = D("0.25")


# ── IDs (§3.2) ───────────────────────────────────────────────────────────────

def test_ids_are_assigned_by_code():
    assert check_id("q1.א.c0", "credit", 1) == "q1.א.c0.c1"
    assert check_id("q1.א.c0", "fault", 2) == "q1.א.c0.f2"
    assert check_id("q1.א.c0", "note", 1) == "q1.א.c0.n1"
    with pytest.raises(ValueError):
        check_id("q1", "credit", 0)                 # 1-based
    with pytest.raises(ValueError):
        check_id("q1", "tariff", 1)                 # closed role vocabulary

    opts = credit_binary_options(D("4"), "full label", "absent label")
    assert [o.option_id for o in opts] == ["full", "absent"]
    lad, _ = credit_ladder_options(
        D("3"), "full", [("half", PartialFraction.HALF), ("quarter", PartialFraction.QUARTER)],
        "absent", GRID)
    assert [o.option_id for o in lad] == ["full", "p1", "p2", "absent"]     # descending value
    cnt = count_options(D("3"), 4, GRID)
    assert [o.option_id for o in cnt] == ["n4", "n3", "n2", "n1", "n0"]
    flt = fault_options([("m1", D("2"), "direct access"), ("m2", D("3"), "neither")], "no fault")
    assert [o.option_id for o in flt] == ["none", "f1", "f2"]
    assert [o.marker_id for o in flt] == [None, "m1", "m2"]
    assert [o.option_id for o in note_options("observed text")] == ["none", "observed"]


# ── values (§3.3, AM-G4) ─────────────────────────────────────────────────────

def test_snap_half_up_is_the_one_rounding_rule():
    assert snap_half_up(D("1.875"), GRID) == D("2.00")          # 7.5 grid units → 8
    assert snap_half_up(D("1.874"), GRID) == D("1.75")
    assert snap_half_up(D("0.125"), GRID) == D("0.25")          # half rounds UP
    assert snap_half_up(D("3"), GRID) == D("3")


def test_partial_fraction_snaps_to_grid_and_collapses():
    # HALF of 3 = 1.5 on the grid; QUARTER of 3 = 0.75
    opts, collapsed = credit_ladder_options(
        D("3"), "full", [("most", PartialFraction.THREE_QUARTERS),
                         ("half", PartialFraction.HALF)], "absent", GRID)
    assert [o.value for o in opts] == [D("3"), D("2.25"), D("1.5"), D("0")]
    assert collapsed == []
    # 0.25 × QUARTER = 0.0625 → snaps to 0 → collapses (value 0)
    opts, collapsed = credit_ladder_options(
        D("0.25"), "full", [("q", PartialFraction.QUARTER)], "absent", GRID)
    assert [o.option_id for o in opts] == ["full", "absent"]
    assert collapsed == ["q"]
    # 0.5 × THREE_QUARTERS = 0.375 → snaps UP to 0.5 == max → collapses
    opts, collapsed = credit_ladder_options(
        D("0.5"), "full", [("tq", PartialFraction.THREE_QUARTERS)], "absent", GRID)
    assert [o.option_id for o in opts] == ["full", "absent"]
    assert collapsed == ["tq"]
    # two partials that land on the same value → the second collapses (duplicate)
    opts, collapsed = credit_ladder_options(
        D("1"), "full", [("h", PartialFraction.HALF), ("q", PartialFraction.QUARTER),
                         ("h2", PartialFraction.HALF)], "absent", GRID)
    assert [o.value for o in opts] == [D("1"), D("0.5"), D("0.25"), D("0")]
    assert collapsed == ["h2"]


def test_count_values_snap_half_up_and_top_is_exact():
    # E8 [AM-G4]: N=8, P=3, k=5 → 1.875 → 2.00
    opts = count_options(D("3"), 8, GRID)
    by_id = {o.option_id: o.value for o in opts}
    assert by_id["n5"] == D("2.00")
    assert by_id["n8"] == D("3")                  # exactly points_possible
    assert by_id["n0"] == D("0")
    assert opts[0].label_he == "8 מתוך 8 נכונים"
    # neighbouring counts may share a value (AM-G4 exempts count from uniqueness)
    many = count_options(D("3"), 40, GRID)
    values = [o.value for o in many]
    assert len(values) == 41
    assert values == sorted(values, reverse=True)
    assert len(set(values)) < len(values)
    with pytest.raises(ValueError):
        count_options(D("3"), 41, GRID)            # N > 40 → STOP and report (§3.3)


def test_levels_add_absent_only_when_missing():
    opts = levels_options([("band A", D("40")), ("band B", D("30")), ("band C", D("0"))])
    assert [o.option_id for o in opts] == ["L1", "L2", "L3"]
    opts = levels_options([("band A", D("40")), ("band B", D("30"))])
    assert [o.option_id for o in opts] == ["L1", "L2", "absent"]
    assert opts[-1].value == D("0") and opts[-1].label_he == ABSENT_LEVEL_LABEL


def test_merged_markers_take_the_lenient_amount():
    # a fault option whose marker absorbed another (merged, P-6) takes −min(amounts)
    opts = fault_options([("m1", [D("3"), D("2")], "same condition")], "no fault")
    assert opts[1].value == D("-2")
    opts = fault_options([("m1", D("0.5"), "x")], "no fault")
    assert opts[0].value == D("0") and opts[1].value == D("-0.5")


def test_even_split_residual_goes_to_the_first_components():
    assert even_split(D("5"), 2, GRID) == [D("2.50"), D("2.50")]
    assert even_split(D("1"), 3, GRID) == [D("0.50"), D("0.25"), D("0.25")]   # OD-9
    assert sum(even_split(D("7.75"), 4, GRID)) == D("7.75")


# ── hashing (§3.5) ───────────────────────────────────────────────────────────

def _tiny_plan(label="full") -> GradingPlanV6:
    t = TerminalPlanV6(terminal_id="q1.c0", points_possible=D("4"),
                       interpretation_notes_he=[])
    c = PlanCheckV6(
        check_id="q1.c0.c1", role="credit", shape="binary",
        description_he="עדכון התכונה people", source_span="עדכון התכונה people",
        options=credit_binary_options(D("4"), label, "absent"),
        priced_terminal_id="q1.c0", origin="compiler")
    return GradingPlanV6(
        plan_schema="plan/v6",
        plan_hash=plan_hash([t], [c]),
        config_hash=config_hash(compiler_version="c", planner_model="m",
                                planner_prompt_version="p", pack_id="cs", pack_version="1"),
        rubric_contract_version="00000000-0000-0000-0000-000000000000",
        subject_pack=PackRef(pack_id="cs", pack_version="1"),
        terminals=[t], checks=[c])


def test_plan_hash_is_canonical_content_hash():
    a, b = _tiny_plan(), _tiny_plan()
    assert a.plan_hash == b.plan_hash and len(a.plan_hash) == 64
    # a content change moves the hash
    assert _tiny_plan(label="other").plan_hash != a.plan_hash
    # Decimal spelling does not: 4 and 4.00 are one value
    t1 = TerminalPlanV6(terminal_id="t", points_possible=D("4"), interpretation_notes_he=[])
    t2 = TerminalPlanV6(terminal_id="t", points_possible=D("4.00"), interpretation_notes_he=[])
    assert plan_hash([t1], []) == plan_hash([t2], [])
    # NFC: a decomposed Hebrew string hashes like its composed form
    import unicodedata
    s = "שָׁלוֹם"
    ta = TerminalPlanV6(terminal_id="t", points_possible=D("1"),
                        interpretation_notes_he=[unicodedata.normalize("NFC", s)])
    tb = TerminalPlanV6(terminal_id="t", points_possible=D("1"),
                        interpretation_notes_he=[unicodedata.normalize("NFD", s)])
    assert plan_hash([ta], []) == plan_hash([tb], [])


def test_config_hash_covers_every_config_input():
    base = dict(compiler_version="c", planner_model="m", planner_prompt_version="p",
                pack_id="cs", pack_version="1")
    h = config_hash(**base)
    for k in base:
        assert config_hash(**{**base, k: base[k] + "x"}) != h


def test_plan_types_are_frozen():
    plan = _tiny_plan()
    with pytest.raises(Exception):
        plan.checks[0].options[0].value = D("1")                   # type: ignore[misc]
    with pytest.raises(Exception):
        plan.plan_hash = "x"                                       # type: ignore[misc]
    assert isinstance(plan.checks[0].options[0], CheckOption)
