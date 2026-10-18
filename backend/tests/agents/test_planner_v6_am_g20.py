"""[AM-G20, owner rulings 2026-10-18 Item C] rule 7(a)/(b) evaluated on the TEACHER'S criterion
(planner-v6.3): when the planner splits a non_binary criterion worth 2 or more, every non_binary
part carries a partial whatever its own share; binary parts stay binary; a criterion under 2
still takes none. planner-v6.2 is unchanged. Pure: the LLM is never called."""
from __future__ import annotations

import asyncio
from decimal import Decimal as D

import pytest

from app.agents.grader.plan_schemas import PartialFraction
from app.agents.plan_compiler.stage1_v6 import V6Component, V6Scope, V6Terminal
from app.agents.planner.assemble import MappingError, map_scope
from app.agents.planner.planner import plan_scope
from app.agents.planner.prompt import (AM_G20_VERSIONS, PLANNER_PROMPT_V63, PLANNER_PROMPT_VERSION,
                                       am_g20_applies, planner_system_prompt)
from app.agents.planner.schemas import (PlannedCredit, PlannedPartial, PlannedTerminal,
                                        ScopePlanOutput)

G = D("0.25")
HALF = PartialFraction.HALF


def _monolith(points="3", text="איזון המשוואה, קביעת התוצרים וציון המצב הצבירה"):
    t = V6Terminal("q9.c0", "q9", D(points), text, "components",
                   components=(V6Component("q9.c0.k1", text, D(points)),), fixed=False)
    return V6Scope("q9", (t,), (), question_text="שאלה", example_solution="")


def _part(ref, element, partial=False):
    partials = [PlannedPartial(label_he=f"החלק {ref} קיים אך חלקי", fraction=HALF, teacher_span=None)] \
        if partial else []
    return PlannedCredit(component_ref=ref, description_he=f"חלק {ref}", source_span="איזון המשוואה",
                         element=element, full_label_he=f"החלק {ref} מלא",
                         absent_label_he=f"החלק {ref} חסר", partials=partials)


def _split(*parts):
    return ScopePlanOutput(terminals=[PlannedTerminal(terminal_id="t1", decomposition="split",
                                                      credits=list(parts))])


def test_v63_every_non_binary_part_of_a_split_needs_a_partial_whatever_its_share():
    out = _split(_part("n1", "non_binary"), _part("n2", "binary"), _part("n3", "non_binary", True))
    with pytest.raises(MappingError) as e:
        map_scope(_monolith("3"), out, G, am_g20=True)
    errs = [m for m in e.value.errors if "rule 7a" in m]
    assert len(errs) == 1 and "'n1'" in errs[0] and "from a criterion worth 2 points or more" in errs[0]


def test_v62_unchanged_a_one_point_part_takes_no_partial():
    out = _split(_part("n1", "non_binary"), _part("n2", "binary"), _part("n3", "non_binary", True))
    with pytest.raises(MappingError) as e:
        map_scope(_monolith("3"), out, G)                           # planner-v6.2: the part's own value
    assert any("'n3'" in m and "worth less than 2 points" in m and "rule 7b" in m for m in e.value.errors)
    assert not any("'n1'" in m for m in e.value.errors)


def test_v63_a_valid_split_maps_with_partials_on_its_non_binary_parts():
    out = _split(_part("n1", "non_binary", True), _part("n2", "binary"), _part("n3", "non_binary", True))
    _t, checks, _d, _tel = map_scope(_monolith("3"), out, G, am_g20=True)
    by = {c.check_id.rsplit(".", 1)[1]: c for c in checks}
    assert [o.value for o in by["c1"].options] == [D(1), D("0.5"), D(0)]          # 1-point part, a ladder
    assert (by["c2"].shape, [o.value for o in by["c2"].options]) == ("binary", [D(1), D(0)])
    assert by["c3"].shape == "ladder"


def test_v63_a_binary_part_stays_binary():
    out = _split(_part("n1", "non_binary", True), _part("n2", "binary", True))
    with pytest.raises(MappingError) as e:
        map_scope(_monolith("3"), out, G, am_g20=True)
    assert any("'n2'" in m and "is binary" in m and "rule 7b" in m for m in e.value.errors)


def test_v63_a_criterion_under_two_points_still_takes_no_partial():
    out = _split(_part("n1", "non_binary", True), _part("n2", "binary"))
    with pytest.raises(MappingError) as e:
        map_scope(_monolith("1.5"), out, G, am_g20=True)
    assert any("'n1'" in m and "from a criterion worth less than 2 points" in m for m in e.value.errors)


def test_v63_fixed_components_are_her_own_criteria():
    """A component she enumerated IS a criterion she priced: a 1-point component stays under the line."""
    t = V6Terminal("q9.c0", "q9", D("4"), "איזון (1) ותוצרים (3)", "components",
                   components=(V6Component("q9.c0.k1", "איזון", D("1")),
                               V6Component("q9.c0.k2", "תוצרים", D("3"))), fixed=True)
    scope = V6Scope("q9", (t,), (), question_text="שאלה", example_solution="")
    out = ScopePlanOutput(terminals=[PlannedTerminal(terminal_id="t1", decomposition="as_compiled", credits=[
        _part("k1", "non_binary", True), _part("k2", "non_binary", True)])])
    with pytest.raises(MappingError) as e:
        map_scope(scope, out, G, am_g20=True)
    assert any("'q9.c0.k1'" in m and "less than 2 points" in m for m in e.value.errors)
    assert not any("'q9.c0.k2'" in m for m in e.value.errors)     # her 3-point component keeps its partial


def test_plan_scope_carries_am_g20_through_repair_and_lenient():
    """The same output twice: under v6.3 the missing partial survives the failed repair only as
    telemetry (never invented); under v6.2 the output was valid all along."""
    out = _split(_part("n1", "non_binary"), _part("n2", "binary"))

    async def call(system, user):
        return out, {"cost_usd": 0.0}

    v63 = asyncio.run(plan_scope(_monolith("3"), precision=G, system_prompt="s", user_message="u",
                                 call=call, am_g20=True))
    assert v63.origin == "repaired"
    assert any(x.startswith("am_g19_partial_missing q9.c0/n1") for x in v63.telemetry)
    v62 = asyncio.run(plan_scope(_monolith("3"), precision=G, system_prompt="s", user_message="u", call=call))
    assert v62.origin == "planner" and len(v62.usage) == 1


def test_the_prompt_versions_are_selectable_and_v62_is_the_default():
    from app.config import settings
    from app.subjects import get_profile
    cs = get_profile("computer_science")
    assert planner_system_prompt(cs) == planner_system_prompt(cs, PLANNER_PROMPT_VERSION)
    v63 = planner_system_prompt(cs, PLANNER_PROMPT_V63)
    assert "teacher's CRITERION" in v63 and "teacher's CRITERION" not in planner_system_prompt(cs)
    assert am_g20_applies(PLANNER_PROMPT_V63) and not am_g20_applies(PLANNER_PROMPT_VERSION)
    assert AM_G20_VERSIONS == (PLANNER_PROMPT_V63,)
    assert settings.v6_planner_prompt_version == PLANNER_PROMPT_VERSION == "planner-v6.2"
    with pytest.raises(ValueError):
        planner_system_prompt(cs, "planner-v9")
