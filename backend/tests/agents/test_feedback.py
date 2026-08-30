"""
PR-G4 — feedback at four layers.

Feedback is a property of the PRICED RESULT, not of the grading decision. It
runs once per test, strictly after pricing, on input that can only describe what
was already decided. Folding it into the grader would let the same call that
picks a verdict also argue for it — and the prose would anchor the verdict.

Pure where it can be; the LLM seam is a fake. No provider is ever called.
"""
from decimal import Decimal

import pytest

from app.schemas.graded_test_draft import Check


def _check(cid, verdict="met", points="3", quote="q"):
    return Check(check_id=cid, text=cid, kind="required", points=Decimal(points),
                 partial_fraction=Decimal("0.5"), verdict=verdict, quote=quote,
                 quote_status="exact", basis_he="", confidence=0.9)


# ---------------------------------------------------------------------------
# feedback-stale-derived-from-basis-hash  (OD-G4.1)
# ---------------------------------------------------------------------------

def test_basis_hash_covers_the_ordered_verdict_vector_and_nothing_else():
    """OD-G4.1: the hash is the ORDERED EFFECTIVE VERDICT VECTOR only.

    Points are derived FROM verdicts, so including them would make the hash
    change when nothing the text depends on changed. Quotes likewise: the
    feedback describes what was credited and what was missing, not which span
    was cited."""
    from app.agents.feedback.staleness import basis_hash

    base = [_check("k1", "met"), _check("k2", "not_met")]
    same_points_differ = [_check("k1", "met", points="99"),
                          _check("k2", "not_met", points="1")]
    same_quote_differs = [_check("k1", "met", quote="totally other span"),
                          _check("k2", "not_met", quote=None)]

    assert basis_hash(base) == basis_hash(same_points_differ), "points must not matter"
    assert basis_hash(base) == basis_hash(same_quote_differs), "quotes must not matter"

    verdict_changed = [_check("k1", "partially_met"), _check("k2", "not_met")]
    assert basis_hash(base) != basis_hash(verdict_changed)

    reordered = [_check("k2", "not_met"), _check("k1", "met")]
    assert basis_hash(base) != basis_hash(reordered), "the vector is ORDERED"


def test_feedback_is_stale_exactly_when_its_basis_moved():
    """Staleness is derived, never stored as a flag someone must remember to
    set: the text carries the hash of the verdicts it was written for."""
    from app.agents.feedback.staleness import basis_hash, is_stale
    from app.schemas.graded_test_draft import FeedbackText

    checks = [_check("k1", "met")]
    text = FeedbackText(text="כל הכבוד", basis_hash=basis_hash(checks))

    assert is_stale(text, checks) is False
    assert is_stale(text, [_check("k1", "not_met")]) is True


# ---------------------------------------------------------------------------
# feedback-gender-neutral-lint
# ---------------------------------------------------------------------------

def test_gender_neutral_lint_flags_gendered_address_and_passes_neutral_prose():
    """Parent spec C2: 2nd-person PAST tense and nominal forms only.

    Hebrew past-tense 2nd person is written identically for both genders
    unvocalised (כתבת), which is exactly why the rule picks it. Present tense
    and imperatives are not, and neither are the אתה/אתם pronouns."""
    from app.agents.feedback.lint import gender_neutral_violations

    assert gender_neutral_violations("הגדרת נכון את מערך הצוברים. חסרה בדיקת טווח.") == []
    assert gender_neutral_violations("סכימת הדירוגים בוצעה כראוי; נותרה בעיה בגבולות.") == []

    assert gender_neutral_violations("אתה צריך לבדוק את הטווח")
    assert gender_neutral_violations("שימי לב לגבולות הלולאה")
    assert gender_neutral_violations("בדוק את התנאי")


def test_lint_does_not_flag_the_accusative_particle():
    """`את` is both a feminine pronoun and the accusative particle, and the
    particle is unavoidable in ordinary Hebrew. Flagging it would make the lint
    fire on every correct sentence — a check nobody can pass trains the
    click-through reflex (the INV-6 lesson)."""
    from app.agents.feedback.lint import gender_neutral_violations

    assert gender_neutral_violations("הגדרת את המערך ואתחלת את כל התאים") == []


# ---------------------------------------------------------------------------
# feedback-failure-does-not-block-draft
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_failure_leaves_the_draft_landed_with_none():
    """A failed feedback call must never cost the teacher her grade. The draft
    lands with feedback=None and an INFO annotation — review-first, not guess.
    `None` is a first-class wire state the frontend renders honestly, not an
    error condition (R-9)."""
    from app.agents.feedback.agent import FeedbackAgent

    class _Boom:
        async def ainvoke(self, *_a, **_kw):
            raise RuntimeError("provider down")

    agent = FeedbackAgent(llm=_Boom(), model_version="fake")
    block, annotations = await agent.generate(scopes=[("q1", "prompt text")])

    assert block is None
    assert annotations and annotations[0].annotation_type == "feedback_unavailable"
    assert annotations[0].severity.value.lower() == "info"


# ---------------------------------------------------------------------------
# feedback-call-runs-after-pricing-once-per-test
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_feedback_runs_once_per_test_on_already_priced_verdicts(monkeypatch):
    """ONE call for the whole test, and its input is the priced view — verdicts
    and quotes, never points and never the total. A per-scope call would cost N
    times as much and lose the cross-scope patterns the summary needs; seeing
    points would let the prose justify a number instead of describing the work.
    """
    import app.agents.feedback.runner as runner_mod
    from app.agents.feedback.schemas import FeedbackResponse, ScopeFeedback
    from app.schemas.graded_test_draft import (
        CriterionOutcome, GradedTestDraft, ScopeOutcome)

    calls = []

    class _Runner:
        async def ainvoke(self, messages):
            calls.append(messages[-1].content)
            return FeedbackResponse(
                scopes=[ScopeFeedback(scope_id="q1", text="הגדרת נכון את המערך.")],
                summary="שני דפוסים חוזרים.")

    class _LLM:
        def with_structured_output(self, _schema):
            return _Runner()

    monkeypatch.setattr(runner_mod.settings, "feedback_model_key", "fake-model",
                        raising=False)
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model",
                        lambda *a, **kw: _LLM())

    leaf = CriterionOutcome(
        criterion_id="q1.c0", description="d", points_possible=Decimal("3"),
        points_awarded=Decimal("3"), reasoning="r", confidence=0.9,
        sub_criterion_outcomes=None, checks=[_check("q1.c0.k1", "met")])
    scope = ScopeOutcome(
        scope_kind="direct", question_id="q1", points_possible=Decimal("3"),
        points_awarded=Decimal("3"), min_confidence=0.9,
        criterion_outcomes=[leaf], graded_by="llm", input_tokens=1, output_tokens=1)
    draft = GradedTestDraft(
        rubric_contract_version="rc", transcription_contract_version="tc",
        model_version="m", prompt_version="p", plan_version="plan/v1",
        scope_outcomes=[scope], llm_calls_count=1, grading_duration_ms=1,
        total_input_tokens=1, total_output_tokens=1)

    out = await runner_mod.attach_feedback(draft)

    assert len(calls) == 1, "feedback must be ONE call per test, not per scope"
    sent = calls[0]
    assert "3" not in sent.replace("q1.c0", ""), "points/total must not reach the model"
    assert out.feedback is not None
    assert out.feedback.scopes["q1"].text.startswith("הגדרת")
    # stamped with the verdict vector it was written for
    from app.agents.feedback.staleness import basis_hash
    assert out.feedback.scopes["q1"].basis_hash == basis_hash([_check("q1.c0.k1", "met")])


# ---------------------------------------------------------------------------
# feedback-contract-carries-effective-text
# ---------------------------------------------------------------------------

def test_contract_carries_the_effective_text_and_says_who_wrote_it():
    """Her edit wins and is recorded as hers (OD-G4.2). The returned exam
    renders from the contract, so what she approved is what the student gets."""
    from app.services.graded_test_contract_compiler import _freeze_feedback
    from app.schemas.graded_test_draft import (
        FeedbackBlock, FeedbackText, GradedTestOverrides)

    block = FeedbackBlock(
        scopes={"q1": FeedbackText(text="model text q1"),
                "q2": FeedbackText(text="model text q2")},
        summary=FeedbackText(text="model summary"),
        model_version="m", prompt_version="p")

    class _Draft:
        feedback = block

    overrides = GradedTestOverrides(feedback={"q1": "המורה כתבה כאן",
                                              "summary": "סיכום של המורה"})
    frozen = _freeze_feedback(_Draft(), overrides)

    assert frozen.scopes["q1"].text == "המורה כתבה כאן"
    assert frozen.scopes["q1"].was_edited is True
    assert frozen.scopes["q2"].text == "model text q2"
    assert frozen.scopes["q2"].was_edited is False
    assert frozen.summary.text == "סיכום של המורה" and frozen.summary.was_edited
