"""[SRG] OptionsVerifyGrader.regrade — a one-scope regrade grafted into a prior v6 draft
(owner rulings 2026-11-01). No provider is ever called: the scripted fake of
test_grader_v6 answers from the rendered message.

SRG-2 is pinned three ways: regrading NOTHING reproduces the prior draft; regrading
EVERYTHING equals a fresh full grade; regrading ONE scope leaves every other scope's
outcome, records and lines byte-identical."""
from __future__ import annotations

import pytest

from app.agents.grader.grader_v6 import OptionsVerifyGrader
from app.agents.grader.plan_schemas import GradingPlanV6
from app.schemas.graded_test_draft_v6 import v6_content
from app.subjects import get_profile
from tests.agents.test_grader_v6 import MODEL, _Fake
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle


@pytest.fixture(scope="module")
def hobby():
    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    return plan, load_bundle("din_ezra", require_gt=False)


def _full(role, opts):
    return opts[0]


def _default(role, opts):
    return opts[-1] if role == "CREDIT" else opts[0]


def _grader(plan, bundle, pick, **kw):
    return OptionsVerifyGrader(plan, bundle.rubric_contract, llm=_Fake(pick), model_version=MODEL,
                               profile=get_profile("computer_science"), **kw)


def _key(so):
    return (so.question_id, so.sub_question_id)


def _no_clock(draft):
    return draft.model_dump(mode="json", exclude={"grading_duration_ms"})


def _answered(test):
    return [s for s in test.scopes if s.student_answer_text]


async def test_regrading_nothing_reproduces_the_prior_draft(hobby):
    plan, bundle = hobby
    prior = await _grader(plan, bundle, _full).grade(bundle.gradable_test)
    out = await _grader(plan, bundle, _full).regrade(bundle.gradable_test, prior, [])
    assert _no_clock(out.draft) == _no_clock(prior)
    assert out.verifier_usage == [] and out.explainer_usage is None


async def test_regrading_everything_equals_a_full_grade(hobby):
    plan, bundle = hobby
    test = bundle.gradable_test
    prior = await _grader(plan, bundle, _default).grade(test)
    fresh = await _grader(plan, bundle, _full).grade(test)
    out = await _grader(plan, bundle, _full).regrade(test, prior, [_key(s) for s in test.scopes])
    assert _no_clock(out.draft) == _no_clock(fresh)


async def test_regrading_one_scope_leaves_every_other_scope_untouched(hobby):
    plan, bundle = hobby
    test = bundle.gradable_test
    prior = await _grader(plan, bundle, _full).grade(test)
    target = _answered(test)[0]
    edited = test.model_copy(update={"scopes": [
        s.model_copy(update={"student_answer_text": "תשובה מתוקנת"}) if s is target else s
        for s in test.scopes]})
    fake = _Fake(_default)
    out = await OptionsVerifyGrader(plan, bundle.rubric_contract, llm=fake, model_version=MODEL,
                                    profile=get_profile("computer_science")).regrade(
        edited, prior, [_key(target)])
    assert fake.calls == 1                                     # only the edited scope was called
    before = {_key(so): so for so in prior.scope_outcomes}
    after = {_key(so): so for so in out.draft.scope_outcomes}
    for k, so in after.items():
        if k == _key(target):
            assert so.student_answer.text == "תשובה מתוקנת"
            assert so != before[k]
        else:
            assert so == before[k]                             # SRG-2
    pc, nc = v6_content(prior), v6_content(out.draft)
    target_tids = {t.terminal_id for t in nc.view_terminals
                   if (t.question_id, t.sub_question_id) == _key(target)}
    assert [c for c in nc.checks if c.plan.priced_terminal_id not in target_tids] == \
           [c for c in pc.checks if c.plan.priced_terminal_id not in target_tids]
    assert [e for e in nc.explanations if e.terminal_id not in target_tids] == \
           [e for e in pc.explanations if e.terminal_id not in target_tids]
    assert len(out.verifier_usage) == 1


async def test_a_regraded_scope_loses_its_old_annotations(hobby):
    """A scope that failed carries `llm_failure`; regraded cleanly, that note is gone and
    every other scope's annotations stay."""
    plan, bundle = hobby
    test = bundle.gradable_test
    target = _answered(test)[0]
    failing = _Fake(_full, fail_times=10 ** 6)
    prior = await OptionsVerifyGrader(plan, bundle.rubric_contract, llm=failing, model_version=MODEL,
                                      profile=get_profile("computer_science")).grade(test)
    assert any(a.annotation_type == "llm_failure" for a in prior.annotations)
    out = await _grader(plan, bundle, _full).regrade(test, prior, [_key(target)])
    tid = f"{target.question_id}.{target.sub_question_id}" if target.sub_question_id else target.question_id
    assert not [a for a in out.draft.annotations
                if a.annotation_type == "llm_failure" and a.target_id == tid]
    others = [a for a in prior.annotations if a.annotation_type == "llm_failure" and a.target_id != tid]
    assert others and all(a in out.draft.annotations for a in others)


async def test_regrade_refuses_a_prior_from_another_plan(hobby):
    plan, bundle = hobby
    prior = await _grader(plan, bundle, _full).grade(bundle.gradable_test)
    doc = dict(prior.v6)
    doc["plan_hash"] = "0" * 64
    alien = prior.model_copy(update={"v6": doc})
    with pytest.raises(ValueError, match="SRG-3"):
        await _grader(plan, bundle, _full).regrade(bundle.gradable_test, alien, [])


async def test_regrade_refuses_a_test_with_another_scope_set(hobby):
    plan, bundle = hobby
    test = bundle.gradable_test
    prior = await _grader(plan, bundle, _full).grade(test)
    short = test.model_copy(update={"scopes": test.scopes[1:]})
    with pytest.raises(ValueError, match="SRG-3"):
        await _grader(plan, bundle, _full).regrade(short, prior, [])


async def test_the_explainer_is_asked_for_the_regraded_scopes_only(hobby):
    plan, bundle = hobby
    test = bundle.gradable_test
    asked = []

    class _Out:
        def __init__(self, explanations):
            self.explanations, self.usage, self.payloads = explanations, None, []

    async def explain(content, priced, gradable_test, only=None):
        asked.append(only)
        from app.schemas.graded_test_draft_v6 import ExplanationV6
        return _Out([ExplanationV6(terminal_id=t.terminal_id, text_he="שורה חדשה", source="model")
                     for t in content.terminals])

    prior = await _grader(plan, bundle, _full).grade(test)
    target = _answered(test)[0]
    out = await _grader(plan, bundle, _full, explain=explain).regrade(test, prior, [_key(target)])
    assert asked == [{_key(target)}]
    nc = v6_content(out.draft)
    target_tids = {t.terminal_id for t in nc.view_terminals
                   if (t.question_id, t.sub_question_id) == _key(target)}
    new = [e for e in nc.explanations if e.text_he == "שורה חדשה"]
    assert new and {e.terminal_id for e in new} <= target_tids


def test_the_stamp_says_when_prior_context_is_rendered(hobby, monkeypatch):
    plan, bundle = hobby
    monkeypatch.delenv("GRADER_PRIOR_CONTEXT_ENABLED", raising=False)
    off = _grader(plan, bundle, _full).prompt_version
    monkeypatch.setenv("GRADER_PRIOR_CONTEXT_ENABLED", "true")
    on = _grader(plan, bundle, _full).prompt_version
    assert "+priorctx" not in off and on == off.replace(off.split("+")[0],
                                                        off.split("+")[0] + "+priorctx", 1)
