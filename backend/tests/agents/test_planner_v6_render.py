"""G2 plan render — every criterion and every check appears, offline (fallback plan)."""
from __future__ import annotations

import asyncio

from app.agents.grader.plan_schemas import PackRef
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.planner import assemble_plan, plan_all
from app.agents.planner.render import render_plan_md
from tests.grading_eval_suite.fixtures import load_bundle


def test_render_lists_every_criterion_check_and_marker():
    s1 = compile_stage1_v6(load_bundle("din_ezra", require_gt=False).rubric_contract,
                           exam_id="hobby_tvshow", rubric_contract_sha256="x")

    async def offline(system, user):
        raise RuntimeError("offline")

    results = asyncio.run(plan_all(s1, system_prompt="S", render=lambda s: s.scope, call=offline))
    plan = assemble_plan(results, config_hash="0" * 64, rubric_contract_version="v",
                         pack=PackRef(pack_id="p", pack_version="0"))
    md = render_plan_md("hobby", plan, s1, results)
    for t in plan.terminals:
        assert f"### {t.terminal_id} " in md
    for c in plan.checks:
        assert f"**{c.check_id}**" in md
    for s in s1.scopes:
        for m in s.markers:
            assert f"`{m.marker_id}`" in md
