"""What the feedback writer is told, and when its text is out of date — v6 (feedback.inputs).

Pure: no DB, no provider. The draft is a REAL v6 draft (the v6 grader on the scripted model,
`test_v6_review_mvc._grade`). The defect these pin: every v6 rewrite used to describe its
scope through the v5 renderer, which reads checks a v6 envelope does not carry, so the model
was told «אין בדיקות לסעיף זה» for every question — and every v6 text carried the same
meaningless basis, so nothing could ever be stale.
"""
from __future__ import annotations

import pytest

from app.agents.feedback.inputs import (LEGACY_V6_BASIS, feedback_inputs, scope_id_of,
                                        stale_feedback_scopes, v6_basis)
from app.schemas.graded_test_draft import FeedbackBlock, FeedbackText
from app.schemas.graded_test_draft_v6 import v6_content
from app.services.v6_review import CheckPatchV6, OverlayPatchV6, merge_overlay, overlay_of
from tests.services.test_v6_review_mvc import _a_ladder, _grade, _with


@pytest.fixture(scope="module")
def graded():
    return _grade()


def _with_feedback(draft, *, legacy=False, empty=()):
    block = FeedbackBlock(
        scopes={i.scope_id: FeedbackText(text="" if i.scope_id in empty else "משוב",
                                         basis_hash=LEGACY_V6_BASIS if legacy else i.basis)
                for i in feedback_inputs(draft, None)},
        summary=FeedbackText(text="סיכום"), model_version="m", prompt_version="p")
    return draft.model_copy(update={"feedback": block})


def _flip(draft):
    """Her decision on the ladder check: its middle option. -> (draft, scope id it lives in)."""
    content = v6_content(draft)
    plan = _a_ladder(content)
    flipped, overrides = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(
        checks={plan.check_id: CheckPatchV6(option_id=plan.options[1].option_id)})))
    vt = next(t for t in content.view_terminals if t.terminal_id == plan.priced_terminal_id)
    scope = vt.question_id if vt.sub_question_id is None else f"{vt.question_id}.{vt.sub_question_id}"
    return flipped, overrides, scope, plan


def test_a_v6_scope_is_described_from_its_own_block(graded):
    draft, _b = graded
    inputs = feedback_inputs(draft, None)
    assert inputs and [i.scope_id for i in inputs] == [
        scope_id_of(so) for so in draft.scope_outcomes if so.graded_by == "llm"]
    for i in inputs:
        assert i.rendered != "אין בדיקות לסעיף זה."
        assert i.basis == v6_basis(i.rendered)              # no notes: input IS the basis text
    described = "\n".join(i.rendered for i in inputs)
    assert v6_content(draft).checks[0].plan.description_he in described


def test_her_decision_makes_exactly_its_scope_stale(graded):
    draft, _b = graded
    noted = _with_feedback(draft)
    assert stale_feedback_scopes(noted, noted.teacher_overrides) == []
    flipped, overrides, scope, plan = _flip(noted)
    assert stale_feedback_scopes(flipped, overrides) == [scope]
    # and the rewrite is told what SHE decided
    rendered = {i.scope_id: i.rendered for i in feedback_inputs(flipped, overrides)}[scope]
    assert f"[{plan.options[1].label_he}] {plan.description_he}" in rendered


def test_a_legacy_v6_text_is_judged_against_vivis_own_price(graded):
    """Before v6 had a basis every text carried the empty-vector hash. It was written at
    grade time from Vivi's price — the only writer that produced it — so that is its basis:
    not stale as it stands, stale once she moves a decision."""
    draft, _b = graded
    legacy = _with_feedback(draft, legacy=True)
    assert stale_feedback_scopes(legacy, legacy.teacher_overrides) == []
    flipped, overrides, scope, _plan = _flip(legacy)
    assert stale_feedback_scopes(flipped, overrides) == [scope]


def test_her_notes_reach_the_writer_but_never_make_the_text_stale(graded):
    draft, _b = graded
    noted = _with_feedback(draft)
    content = v6_content(draft)
    plan = _a_ladder(content)
    with_note, overrides = _with(noted, merge_overlay(overlay_of(None), OverlayPatchV6(
        terminal_comments={plan.priced_terminal_id: "הבנת את הרעיון"})))
    assert stale_feedback_scopes(with_note, overrides) == []
    before = {i.scope_id: i for i in feedback_inputs(noted, None)}
    after = {i.scope_id: i for i in feedback_inputs(with_note, overrides)}
    changed = [sid for sid in after if after[sid].rendered != before[sid].rendered]
    assert len(changed) == 1
    assert "הבנת את הרעיון" in after[changed[0]].rendered
    assert "אין לחזור עליהן ואין לסתור אותן" in after[changed[0]].rendered
    assert after[changed[0]].basis == before[changed[0]].basis


def test_a_scope_with_no_vivi_text_has_nothing_to_be_stale(graded):
    draft, _b = graded
    _flipped, _o, scope, _p = _flip(draft)
    empty = _with_feedback(draft, empty=(scope,))
    flipped, overrides, _s, _p = _flip(empty)
    assert scope not in stale_feedback_scopes(flipped, overrides)
    assert stale_feedback_scopes(draft, draft.teacher_overrides) == []     # no block at all


def test_a_v5_draft_reports_no_v6_staleness(graded):
    draft, _b = graded
    assert stale_feedback_scopes(_with_feedback(draft).model_copy(update={"v6": None}), None) == []


@pytest.mark.asyncio
async def test_grade_time_feedback_is_stamped_with_the_v6_basis(graded, monkeypatch):
    import app.agents.feedback.runner as runner_mod
    from app.agents.feedback.schemas import FeedbackResponse, ScopeFeedback
    draft, _b = graded
    ids = [i.scope_id for i in feedback_inputs(draft, None)]

    class _Runner:
        async def ainvoke(self, messages):
            return FeedbackResponse(scopes=[ScopeFeedback(scope_id=s, text="משוב") for s in ids],
                                    summary="סיכום")

    class _LLM:
        def with_structured_output(self, _schema, include_raw=False):
            return _Runner()

    monkeypatch.setattr(runner_mod.settings, "feedback_model_key", "fake-model", raising=False)
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model", lambda *a, **k: _LLM())
    out = await runner_mod.attach_feedback(draft)
    assert set(out.feedback.scopes) == set(ids)
    assert all(t.basis_hash not in ("", LEGACY_V6_BASIS) for t in out.feedback.scopes.values())
    assert stale_feedback_scopes(out, out.teacher_overrides) == []
    flipped, overrides, scope, _p = _flip(out)
    assert stale_feedback_scopes(flipped, overrides) == [scope]
