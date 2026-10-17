"""[AM-G19, owner 2026-10-06] Rule 7 amended — partial credit decided per credit, ENFORCED in
code (planner/assemble.py), never left to the prompt alone. Pure: the LLM is never called.

  (a) every planner credit states `element`; a non_binary credit worth 2 or more has a partial
  (b) a binary credit, and any credit under 2, has none — unless her own text states it
      (`teacher_span`, verbatim; its figure, when it has one, is the partial's value)
  strict → the repair call; lenient (after a failed repair) → drop / report, never invent;
  off → a planner-v6.1 recording, its plan and hash unchanged.
"""
from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.agents.grader import plan_values as pv
from app.agents.grader.plan_schemas import PartialFraction
from app.agents.plan_compiler.stage1_v6 import V6Component, V6Scope, V6Terminal
from app.agents.planner.assemble import MappingError, map_scope, validate_scope
from app.agents.planner.planner import plan_scope
from app.agents.planner.schemas import (PlannedCredit, PlannedPartial, PlannedTerminal,
                                        ScopePlanOutput)

G = D("0.25")
HALF, THREE_Q = PartialFraction.HALF, PartialFraction.THREE_QUARTERS


def _scope(points="4", text="סכימת ערכי המערך והחזרת הסכום", comps=None):
    comps = comps or ((f"q9.c0.k1", text, D(points)),)
    t = V6Terminal("q9.c0", "q9", D(points), text, "components",
                   components=tuple(V6Component(i, s, D(v)) for i, s, v in comps),
                   fixed=len(comps) >= 2)
    return V6Scope("q9", (t,), (), question_text="שאלה", example_solution="")


def _credit(ref="k1", element="non_binary", partials=(), span="סכימת ערכי המערך"):
    return PlannedCredit(component_ref=ref, description_he="סכימה", source_span=span, element=element,
                         full_label_he="הסכום מחושב ומוחזר", absent_label_he="אין סכימה של ערכי המערך",
                         partials=[PlannedPartial(label_he=l, fraction=f, teacher_span=ts)
                                   for l, f, ts in partials])


def _out(credit, decomposition="ladder"):
    return ScopePlanOutput(terminals=[PlannedTerminal(terminal_id="t1", decomposition=decomposition,
                                                      credits=[credit])])


def test_a_non_binary_credit_worth_two_or_more_needs_a_partial():
    with pytest.raises(MappingError) as e:
        map_scope(_scope("4"), _out(_credit(), "binary"), G)
    assert any("rule 7a" in m and "non_binary" in m for m in e.value.errors)


def test_a_two_level_ladder_maps_and_records_the_element():
    out = _out(_credit(partials=[("סכימה עם החלקה אחת בערכי המערך", THREE_Q, None),
                                 ("רק חלק מערכי המערך נסכמים", HALF, None)]))
    terminals, checks, disps, _tel = map_scope(_scope("4"), out, G)
    (c,) = checks
    assert (c.element, c.shape, [o.value for o in c.options]) == ("non_binary", "ladder",
                                                                  [D(4), D(3), D(2), D(0)])
    assert validate_scope(_scope("4"), terminals, checks, disps, G) == []


def test_a_binary_credit_takes_no_partial_however_much_it_is_worth():
    out = _out(_credit(element="binary", partials=[("הוחזר ערך אחר", HALF, None)]))
    with pytest.raises(MappingError) as e:
        map_scope(_scope("4"), out, G)
    assert any("rule 7b" in m and "binary" in m for m in e.value.errors)
    _t, (c,), _d, _ = map_scope(_scope("4"), _out(_credit(element="binary"), "binary"), G)
    assert (c.element, c.shape) == ("binary", "binary")


def test_a_small_credit_keeps_only_the_partial_her_text_states():
    text = "סכימת ערכי המערך (1 נק', חצי נקודה אם נסכם רק חלק מהמערך)"
    scope = _scope("1", text=text)
    unbacked = _out(_credit(partials=[("רק חלק מערכי המערך נסכמים", HALF, None)]))
    with pytest.raises(MappingError) as e:
        map_scope(scope, unbacked, G)
    assert any("worth less than 2 points" in m for m in e.value.errors)

    stated = _out(_credit(partials=[("רק חלק מערכי המערך נסכמים", HALF,
                                     "חצי נקודה אם נסכם רק חלק מהמערך")]))
    _t, (c,), _d, tel = map_scope(scope, stated, G)
    assert [o.value for o in c.options] == [D(1), D("0.5"), D(0)]
    assert any(x.startswith("partial_teacher_stated") for x in tel)

    wrong_value = _out(_credit(partials=[("רק חלק מערכי המערך נסכמים", PartialFraction.QUARTER,
                                          "חצי נקודה אם נסכם רק חלק מהמערך")]))
    with pytest.raises(MappingError) as e:
        map_scope(scope, wrong_value, G)
    assert any("another value" in m for m in e.value.errors)

    invented = _out(_credit(partials=[("רק חלק מערכי המערך נסכמים", HALF, "חצי נקודה על כל דבר")]))
    with pytest.raises(MappingError) as e:
        map_scope(scope, invented, G)
    assert any("not verbatim" in m for m in e.value.errors)


def test_a_split_credit_is_judged_on_its_even_share():
    """A 3-point monolith split in two: 1.5 each, both under 2 — neither needs a partial."""
    out = ScopePlanOutput(terminals=[PlannedTerminal(terminal_id="t1", decomposition="split", credits=[
        _credit("n1", span="סכימת ערכי המערך"), _credit("n2", element="binary", span="והחזרת הסכום")])])
    _t, checks, _d, _ = map_scope(_scope("3"), out, G)
    assert [(c.element, c.options[0].value) for c in checks] == [("non_binary", D("1.5")),
                                                                 ("binary", D("1.5"))]


def test_a_missing_element_is_a_repairable_error_in_strict_mode_only():
    no_element = _credit(element=None)
    with pytest.raises(MappingError) as e:
        map_scope(_scope("1"), _out(no_element, "binary"), G)
    assert any("states no element" in m for m in e.value.errors)
    _t, (c,), _d, tel = map_scope(_scope("1"), _out(no_element, "binary"), G, am_g19="lenient")
    assert c.element is None and any(x.startswith("am_g19_element_missing") for x in tel)


def test_lenient_drops_an_unbacked_partial_and_reports_a_missing_one_never_invents():
    out = _out(_credit(element="binary", partials=[("הוחזר ערך אחר", HALF, None)]))
    _t, (c,), _d, tel = map_scope(_scope("4"), out, G, am_g19="lenient")
    assert c.shape == "binary" and any(x.startswith("am_g19_partial_dropped") for x in tel)
    _t, (c,), _d, tel = map_scope(_scope("4"), _out(_credit(), "binary"), G, am_g19="lenient")
    assert c.shape == "binary" and any(x.startswith("am_g19_partial_missing") for x in tel)


def test_off_mode_is_a_v61_plan_byte_for_byte():
    """A planner-v6.1 recording carries no element: replayed with rule 7 off, every check's
    element is None and the plan hash is what an element-less plan always hashed to."""
    out = _out(_credit(element="binary"), "binary")
    terms, checks, _d, _ = map_scope(_scope("4"), out, G, am_g19="off")
    assert all(c.element is None for c in checks)
    with_element = [c.model_copy(update={"element": "binary"}) for c in checks]
    assert pv.plan_hash(terms, checks) != pv.plan_hash(terms, with_element)
    doc = pv._check_doc(checks[0])
    assert "element" not in doc                       # an older plan's hash never moves


class _Script:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    async def __call__(self, system, user):
        self.calls += 1
        return self.replies.pop(0), {}


async def test_a_repair_that_still_breaks_only_rule_7_is_taken_leniently_not_thrown_away():
    """The fallback is binary everywhere: it would lose every partial the planner wrote. A
    repaired output that fails rule 7 alone is kept, the gap reported."""
    stingy = _out(_credit(), "binary")                     # non_binary 4 with no partial, twice
    r = await plan_scope(_scope("4"), precision=G, system_prompt="S", user_message="U",
                         call=_Script(stingy, stingy))
    assert r.origin == "repaired"
    assert any(x.startswith("am_g19_partial_missing") for x in r.telemetry)
    assert any(x.startswith("am_g19_downgraded") for x in r.telemetry)
    assert all(c.origin == "planner" for c in r.checks)


async def test_rule_7_is_off_for_a_v61_replay():
    stingy = _out(_credit(element=None), "binary")
    r = await plan_scope(_scope("4"), precision=G, system_prompt="S", user_message="U",
                         call=_Script(stingy), am_g19=False)
    assert r.origin == "planner" and r.checks[0].element is None
