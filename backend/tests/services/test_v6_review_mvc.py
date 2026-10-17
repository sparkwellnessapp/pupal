"""[grader-v6 MVC, owner rulings 2026-10-17 §7] her overlay over a v6 draft, the v6 approval
gate and contract, and v6 feedback — pure: no DB, no provider. The draft is a REAL v6 draft,
graded by `OptionsVerifyGrader` on the scripted model the grader's own tests use."""
from __future__ import annotations

import asyncio
from decimal import Decimal as D

import pytest

from app.agents.grader.grader_v6 import OptionsVerifyGrader
from app.agents.grader.plan_schemas import GradingPlanV6
from app.schemas.graded_test_draft import GradedTestOverrides
from app.schemas.graded_test_draft_v6 import v6_content
from app.services.graded_test_contract_compiler import GateError, compile_graded_test
from app.services.pricing_v6 import price
from app.services.v6_review import (CheckPatchV6, OverlayPatchV6, merge_overlay, overlay_doc,
                                    overlay_of, overlay_violations, review, undecided_checks)
from app.subjects import get_profile
from tests.agents.test_grader_v6 import MODEL, _Fake, _full
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle


def _grade(pick=_full, gradable=None):
    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    bundle = load_bundle("din_ezra", require_gt=False)
    agent = OptionsVerifyGrader(plan, bundle.rubric_contract, llm=_Fake(pick), model_version=MODEL,
                                profile=get_profile("computer_science"))
    draft = asyncio.run(agent.grade(gradable or bundle.gradable_test))
    return draft, bundle


@pytest.fixture(scope="module")
def graded():
    return _grade()


def _with(draft, overlay):
    o = draft.teacher_overrides.model_copy(update={"v6": overlay_doc(overlay)})
    return draft.model_copy(update={"teacher_overrides": o}), o


def _a_ladder(content):
    return next(c.plan for c in content.checks if c.plan.role == "credit" and len(c.plan.options) > 2)


def test_a_v5_draft_has_no_v6_review(graded):
    draft, _b = graded
    assert review(draft.model_copy(update={"v6": None}), draft.teacher_overrides) is None


def test_merge_sets_withdraws_and_leaves_the_rest(graded):
    draft, _b = graded
    content = v6_content(draft)
    a, b = [c.plan for c in content.checks if c.plan.role == "credit"][:2]
    o1 = merge_overlay(overlay_of(draft.teacher_overrides), OverlayPatchV6(
        checks={a.check_id: CheckPatchV6(option_id=a.default_option.option_id, comment="x"),
                b.check_id: CheckPatchV6(comment="only a note")},
        terminal_points={a.priced_terminal_id: D("0")}))
    assert o1.checks[a.check_id].option_id == a.default_option.option_id
    assert o1.checks[b.check_id].option_id is None and o1.checks[b.check_id].comment == "only a note"
    o2 = merge_overlay(o1, OverlayPatchV6(checks={a.check_id: None},
                                          terminal_points={a.priced_terminal_id: None}))
    assert a.check_id not in o2.checks and b.check_id in o2.checks      # untouched key stays
    assert not o2.terminal_points


def test_cw3_extended_to_checks_options_and_the_v61_fields(graded):
    draft, _b = graded
    content = v6_content(draft)
    plan = _a_ladder(content)
    from app.services.pricing_v6 import CheckDecision, PricingOverlay
    bad = PricingOverlay(checks={
        "q9.c0.c1": CheckDecision(option_id="full"),
        plan.check_id: CheckDecision(option_id="o-not-there", amount=D("1"), evidence_disputed=True)},
        terminal_points={"q9.c0": D("1"), plan.priced_terminal_id: D("999")})
    kinds = sorted(v.kind for v in overlay_violations(content, bad))
    assert kinds == ["closed_world", "closed_world", "closed_world", "not_supported", "not_supported",
                     "out_of_bounds"]
    grid = PricingOverlay(terminal_points={plan.priced_terminal_id: D("0.1")})
    assert [v.kind for v in overlay_violations(content, grid)] == ["off_grid"]


def test_the_line_she_reads(graded):
    draft, _b = graded
    content = v6_content(draft)
    plan = _a_ladder(content)
    tid = plan.priced_terminal_id
    untouched = review(draft, draft.teacher_overrides)
    recorded = {x.terminal_id: x.text_he for x in content.explanations}
    assert untouched.lines[tid][0] == recorded[tid]                      # Vivi's line, as written
    flipped, o = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(
        checks={plan.check_id: CheckPatchV6(option_id=plan.default_option.option_id)})))
    r = review(flipped, o)
    assert r.lines[tid][1] == "fallback"                                 # her edit: the composer's line
    assert r.final.total_score <= r.ai.total_score
    pinned, o = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(
        terminal_points={tid: D("0")})))
    r = review(pinned, o)
    assert r.lines[tid][1] == "teacher_override"                         # she set the grade


def test_od4_undecided_only_where_a_call_should_have_answered():
    def drop_all(role, opts):                    # the model answers nothing: every pick missing
        return "o999"
    draft, _b = _grade(pick=drop_all)
    content = v6_content(draft)
    r = review(draft, draft.teacher_overrides)
    undecided = undecided_checks(content, r.ai, r.overlay)
    llm_scopes = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "llm"}
    assert undecided and llm_scopes
    skipped = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "skipped_no_answer"}
    scope_of = {t.terminal_id: (t.question_id, t.sub_question_id) for t in content.view_terminals}
    plans = {c.plan.check_id: c.plan for c in content.checks}
    assert not any(scope_of[plans[c].priced_terminal_id] in skipped for c in undecided)
    with pytest.raises(GateError) as e:
        compile_graded_test(draft, draft.teacher_overrides, _b.rubric_contract)
    assert {v.violation_kind for v in e.value.violations} >= {"undecided_check"}
    # she decides every one → the gate opens
    decided, o = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(checks={
        c: CheckPatchV6(option_id=plans[c].default_option.option_id) for c in undecided})))
    compile_graded_test(decided, o, _b.rubric_contract)


def test_approval_prices_with_the_one_pricer_and_freezes_the_v6_facts(graded):
    draft, bundle = graded
    content = v6_content(draft)
    plan = _a_ladder(content)
    mid = plan.options[1].option_id
    flipped, o = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(
        checks={plan.check_id: CheckPatchV6(option_id=mid, comment="חלקי")})))
    contract = compile_graded_test(flipped, o, bundle.rubric_contract)
    final = price(content.to_view(), overlay_of(o))
    assert contract.total_score == final.total_score
    assert contract.v6.plan_hash == content.plan_hash and contract.v6.config_hash == content.config_hash
    frozen = {c.check_id: c for c in contract.v6.checks}
    assert frozen[plan.check_id].effective_option_id == mid and frozen[plan.check_id].was_overridden
    assert frozen[plan.check_id].teacher_comment == "חלקי"
    lines = {t.terminal_id: t for t in contract.v6.terminals}
    assert lines[plan.priced_terminal_id].reasoning_source == "fallback"
    terminal = next(t for s in contract.scope_outcomes for t in s.terminal_outcomes
                    if t.terminal_id == plan.priced_terminal_id)
    assert terminal.was_overridden and terminal.teacher_comment == "חלקי"


def test_approval_refuses_an_overlay_outside_the_closed_world(graded):
    draft, bundle = graded
    from app.services.pricing_v6 import CheckDecision, PricingOverlay
    bad, o = _with(draft, PricingOverlay(checks={"q9.c0.c1": CheckDecision(option_id="full")}))
    with pytest.raises(GateError) as e:
        compile_graded_test(bad, o, bundle.rubric_contract)
    assert [v.violation_kind for v in e.value.violations] == ["closed_world"]


def test_v6_feedback_reads_the_option_that_priced(graded):
    from app.agents.feedback.prompt import render_scope_v6
    draft, _b = graded
    content = v6_content(draft)
    priced = price(content.to_view())
    scope = next((s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "llm")
    text = render_scope_v6(content, priced, scope)
    in_scope = {t.terminal_id for t in content.view_terminals if (t.question_id, t.sub_question_id) == scope}
    credit = next(c for c in content.checks if c.plan.priced_terminal_id in in_scope and c.plan.role == "credit")
    assert credit.plan.description_he in text and credit.plan.options[0].label_he in text
    assert "נקודות" not in text                                          # no points, anywhere
