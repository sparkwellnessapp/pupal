"""[SRG] the pure parts of a teacher's grading-gate answer correction (owner rulings
2026-11-01): which answer a scope reads (D3/D4), the corrected contract (FIG-1, the
first-approved text), SRG-1's regrade set, D5's clearing, and D6's feedback merge.
Zero mocks."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest

from app.schemas.graded_test_draft import FeedbackBlock, FeedbackText
from app.schemas.graded_test_draft_v6 import v6_content
from app.schemas.transcription import (Figure, TranscriptionContract,
                                       TranscriptionContractAnswer)
from app.services import gradable_compiler
from app.services.pricing_v6 import CheckDecision, PricingOverlay
from app.services.scope_regrade import (RegradeRefused, affected_scopes, answer_key_for,
                                        clear_scope_decisions, corrected_contract, merge_feedback,
                                        question_numbers)
from app.services.v6_review import overlay_doc, overlay_of
from tests.services.test_v6_review_mvc import _grade

NO_CHECKS = SimpleNamespace(checks=[])        # SRG-1 compares what the grader reads; checks optional


def _tc(*answers):
    return TranscriptionContract(answers=[
        TranscriptionContractAnswer(question_number=q, sub_question_id=s, answer_text=t)
        for q, s, t in answers])


@pytest.fixture(scope="module")
def math_contract():
    from tests.grading_eval_suite.tools import v6_smoke
    _entry, contract = v6_smoke.load_subject("mathematics")
    return contract


@pytest.fixture(scope="module")
def graded():
    return _grade()


# ── which answer a scope reads ────────────────────────────────────────────────

def test_a_leaf_reads_its_own_answer_or_its_ancestors(math_contract):
    q3 = question_numbers(math_contract)["q3"]
    own = gradable_compiler.compile(math_contract, _tc((q3, "א.1", "a"), (q3, "ב", "b")))
    by = {(s.question_id, s.sub_question_id): s for s in own.scopes}
    assert answer_key_for(by[("q3", "א.1")], q3) == (q3, "א.1")          # own
    assert answer_key_for(by[("q3", "ב.2")], q3) == (q3, "ב")            # D3: the shared answer
    assert answer_key_for(by[("q3", "א.2")], q3) == (q3, "א.2")          # D4: missing → its own key


# ── the corrected contract ───────────────────────────────────────────────────

def test_a_correction_replaces_one_answer_and_freezes_a_new_version():
    tc = _tc((1, "א", "x=2"), (1, "ב", "y"))
    new = corrected_contract(tc, (1, "א"), "x=3")
    assert new.contract_version != tc.contract_version
    a, b = new.answers
    assert (a.answer_text, a.original_text) == ("x=3", "x=2")
    assert b == tc.answers[1]


def test_the_original_is_the_first_approved_text_across_corrections():
    tc = _tc((1, "א", "x=2"))
    twice = corrected_contract(corrected_contract(tc, (1, "א"), "x=3"), (1, "א"), "x=4")
    assert twice.answers[0].original_text == "x=2"
    restored = corrected_contract(twice, (1, "א"), "x=2")
    assert restored.answers[0].original_text is None                     # back to what was approved


def test_an_unchanged_text_is_no_correction():
    tc = _tc((1, "א", "x=2"))
    assert corrected_contract(tc, (1, "א"), "x=2") is None
    assert corrected_contract(tc, (2, None), "   ") is None              # nothing added


def test_a_missing_answer_is_added_with_an_empty_original():
    new = corrected_contract(_tc((1, "א", "x")), (2, None), "התלמיד כן ענה")
    added = new.answers[-1]
    assert (added.question_number, added.sub_question_id, added.original_text) == (2, None, "")


def test_the_original_text_is_omitted_until_there_is_one():
    assert "original_text" not in _tc((1, "א", "x")).model_dump(mode="json")["answers"][0]


def test_a_correction_may_not_drop_a_figure_line():
    """D9 + FIG-1: figure lines are read-only here; dropping one is refused, never detached."""
    fig = Figure(figure_no=1, page_number=1)
    tc = TranscriptionContract(answers=[TranscriptionContractAnswer(
        question_number=1, sub_question_id=None, answer_text="[איור 1: גרף]\nf(x)=x", figures=[fig])])
    kept = corrected_contract(tc, (1, None), "[איור 1: גרף]\nf(x)=x^2")
    assert kept.answers[0].figures == [fig]
    with pytest.raises(RegradeRefused) as e:
        corrected_contract(tc, (1, None), "f(x)=x^2")
    assert (e.value.status, e.value.code) == (422, "figure_line_removed")


def test_the_compiler_carries_the_original_to_every_scope_that_reads_it(math_contract):
    q3 = question_numbers(math_contract)["q3"]
    tc = corrected_contract(_tc((q3, "א", "old")), (q3, "א"), "new")
    test = gradable_compiler.compile(math_contract, tc)
    leaves = [s for s in test.scopes if s.question_id == "q3" and s.sub_question_id.startswith("א.")]
    assert leaves and all(s.student_answer_text == "new" and s.student_answer_original_text == "old"
                          and s.answer_source == "inherited" for s in leaves)
    others = [s for s in test.scopes if s not in leaves]
    assert all(s.student_answer_original_text is None for s in others)


# ── SRG-1: the regrade set ───────────────────────────────────────────────────

def _sids(keys):
    return {f"{q}.{s}" if s else q for q, s in keys}


def test_the_regrade_set_is_the_scope_and_the_siblings_that_share_its_answer(math_contract, monkeypatch):
    monkeypatch.delenv("GRADER_PRIOR_CONTEXT_ENABLED", raising=False)
    q3 = question_numbers(math_contract)["q3"]
    tc = _tc((q3, "א", "old"), (q3, "ב", "b"), (1, "א", "q1"))
    old = gradable_compiler.compile(math_contract, tc)
    new = gradable_compiler.compile(math_contract, corrected_contract(tc, (q3, "א"), "new"))
    assert _sids(affected_scopes(old, new, NO_CHECKS)) == {"q3.א.1", "q3.א.2", "q3.א.3"}


def test_with_prior_context_on_the_later_parts_that_read_it_are_regraded_too(math_contract, monkeypatch):
    """D12: while the flag renders earlier answers into later parts' prompts, an edit
    changes those prompts — and SRG-1 follows the prompt, not a rule about it."""
    monkeypatch.setenv("GRADER_PRIOR_CONTEXT_ENABLED", "true")
    q3 = question_numbers(math_contract)["q3"]
    tc = _tc((q3, "א.1", "a1"), (q3, "א.2", "a2"), (q3, "ב", "b"))
    old = gradable_compiler.compile(math_contract, tc)
    new = gradable_compiler.compile(math_contract, corrected_contract(tc, (q3, "א.2"), "fixed"))
    got = _sids(affected_scopes(old, new, NO_CHECKS))
    assert "q3.א.2" in got and "q3.א.1" not in got
    assert {"q3.א.3", "q3.ב.1", "q3.ב.2", "q3.ב.3"} <= got               # every later part of q3
    assert not any(s.startswith("q1") for s in got)                      # never another question


# ── D5: her decisions on a regraded scope ────────────────────────────────────

def test_clearing_takes_her_picks_and_pins_and_keeps_her_notes(graded):
    draft, _bundle = graded
    content = v6_content(draft)
    target = (content.scopes[0].question_id, content.scopes[0].sub_question_id)
    tids = {t.terminal_id for t in content.view_terminals
            if (t.question_id, t.sub_question_id) == target}
    mine = [c.plan for c in content.checks if c.plan.priced_terminal_id in tids]
    other = next(c.plan for c in content.checks if c.plan.priced_terminal_id not in tids)
    overlay = PricingOverlay(
        checks={mine[0].check_id: CheckDecision(option_id=mine[0].options[0].option_id, comment="נימוק"),
                mine[-1].check_id: CheckDecision(option_id=mine[-1].options[0].option_id),
                other.check_id: CheckDecision(option_id=other.options[0].option_id)},
        terminal_points={sorted(tids)[0]: 0},
        terminal_comments={sorted(tids)[0]: "הערה לתלמיד"})
    overrides = draft.teacher_overrides.model_copy(update={"v6": overlay_doc(overlay),
                                                           "feedback": {"summary": "שלי"}})
    out, n = clear_scope_decisions(overrides, content, {target})
    kept = overlay_of(out)
    assert n == (3 if mine[0].check_id != mine[-1].check_id else 2)
    assert kept.checks[mine[0].check_id] == CheckDecision(comment="נימוק")       # the note stays
    assert mine[-1].check_id not in kept.checks or mine[-1].check_id == mine[0].check_id
    assert kept.checks[other.check_id] == overlay.checks[other.check_id]         # another scope's
    assert kept.terminal_points == {}
    assert kept.terminal_comments == overlay.terminal_comments                   # her note to him
    assert out.feedback == {"summary": "שלי"}                                    # her own text


def test_clearing_nothing_returns_her_overrides_untouched(graded):
    draft, _b = graded
    content = v6_content(draft)
    out, n = clear_scope_decisions(draft.teacher_overrides, content,
                                   {(content.scopes[0].question_id, content.scopes[0].sub_question_id)})
    assert (out, n) == (draft.teacher_overrides, 0)


# ── D6: feedback ──────────────────────────────────────────────────────────────

def _block(scopes, summary):
    return FeedbackBlock(scopes={k: FeedbackText(text=v, basis_hash=f"h-{v}") for k, v in scopes.items()},
                         summary=FeedbackText(text=summary), model_version="m", prompt_version="p")


def test_feedback_rewrites_the_regraded_scope_and_the_summary_only():
    prior = _block({"q1.א": "old-a", "q1.ב": "old-b"}, "old summary")
    new = _block({"q1.א": "new-a", "q1.ב": "new-b"}, "new summary")
    out = merge_feedback(prior, new, {"q1.א"}, {})
    assert out.scopes["q1.א"].text == "new-a" and out.scopes["q1.ב"].text == "old-b"
    assert out.summary.text == "new summary"


def test_her_own_feedback_text_stands():
    prior = _block({"q1.א": "old-a"}, "old summary")
    new = _block({"q1.א": "new-a"}, "new summary")
    out = merge_feedback(prior, new, {"q1.א"}, {"q1.א": "שלה", "summary": "שלה"})
    assert out.scopes["q1.א"].text == "old-a" and out.summary.text == "old summary"


def test_a_failed_feedback_call_changes_nothing_and_a_gap_is_filled():
    prior = _block({"q1.א": "old-a"}, "s")
    assert merge_feedback(prior, None, {"q1.א"}, {}) is prior
    filled = merge_feedback(prior, _block({"q1.א": "new-a", "q2": "new-2"}, "s2"), set(), {})
    assert filled.scopes["q2"].text == "new-2" and filled.scopes["q1.א"].text == "old-a"


def test_a_scope_no_longer_graded_by_the_model_loses_its_text():
    prior = _block({"q1.א": "old-a"}, "s")
    out = merge_feedback(prior, _block({}, "s2"), {"q1.א"}, {})
    assert "q1.א" not in out.scopes
