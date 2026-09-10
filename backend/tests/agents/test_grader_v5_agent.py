"""
PlanVerifyGrader integration tests — LLM faked, zero OpenAI calls.

The fake is injected through the D6 seam (llm=...) rather than patched, which
also pins the seam's contract: a chat model exposing with_structured_output()
whose ainvoke returns the include_raw dict shape.
"""
from decimal import Decimal
from typing import List
from unittest.mock import MagicMock

import pytest

from app.agents.grader import grader_v5 as grader_v5_mod
from app.agents.grader.grader_v5 import PlanVerifyGrader
from app.agents.grader.plan_schemas import (
    CheckVerdict,
    GradingPlan,
    PlanCheck,
    ScopeVerificationResponse,
    TerminalPlan,
)
from app.agents.grader.verifier_prompt import (
    VERIFIER_PROMPT_VERSION,
    VERIFIER_SYSTEM_PROMPT,
    build_verifier_message,
)
from app.schemas.gradable import GradableCriterion, GradableScope, GradableTest
from app.schemas.ontology_types import FlagReason, NumericPolicy

ANSWER = "the student wrote a loop here\nand a null check there"


def _scope(question_id="q1", criterion_id="c1", pts="3", answer=ANSWER,
           alignment="matched"):
    return GradableScope(
        scope_kind="direct", question_id=question_id,
        criteria=[GradableCriterion(criterion_id=criterion_id,
                                    description="crit", points=Decimal(pts))],
        points=Decimal(pts), student_answer_text=answer, alignment=alignment)


def _gradable(scopes):
    return GradableTest(rubric_contract_version="rc-v1",
                        transcription_contract_version="tc-v1",
                        scopes=scopes, unmatched_transcription_answers=[],
                        total_points=sum(s.points for s in scopes))


def _plan(terminals):
    return GradingPlan(plan_version="test-plan/v1", exam_id="ex",
                       rubric_contract_sha256="0" * 64, terminals=terminals)


def _basic_plan():
    return _plan([TerminalPlan(terminal_id="c1", points_possible=Decimal("3"), checks=[
        PlanCheck(check_id="c1.k1", description_he="לולאה", kind="required",
                  points=Decimal("2")),
        PlanCheck(check_id="c1.k2", description_he="בדיקת null", kind="required",
                  points=Decimal("1")),
    ])])


def _verdict(cid, verdict="met", quote="the student wrote a loop here",
             basis="נמצא", conf=0.9):
    return CheckVerdict(check_id=cid, evidence_quote=quote, basis_he=basis,
                        verdict=verdict, confidence=conf)


class FakeLLM:
    """Chat-model stand-in for the seam: returns queued responses in order,
    then repeats the last one. Raises queued exceptions in place."""

    def __init__(self, responses: List):
        self._responses = list(responses)
        self.calls: List = []

    def with_structured_output(self, schema, include_raw=False):
        assert schema is ScopeVerificationResponse and include_raw
        outer = self

        class _Runner:
            async def ainvoke(self, messages):
                outer.calls.append(messages)
                item = (outer._responses.pop(0) if len(outer._responses) > 1
                        else outer._responses[0])
                if isinstance(item, Exception):
                    raise item
                raw = MagicMock()
                raw.usage_metadata = {
                    "input_tokens": 100, "output_tokens": 40,
                    "input_token_details": {"cache_read": 25}}
                # [COST_TRUTH] the provider-reported id the agents must capture
                raw.response_metadata = {"model_name": "fake-model-2026-01-01"}
                return {"raw": raw, "parsed": item, "parsing_error": None}
        return _Runner()


def _agent(plan, responses, sc_n=1):
    return PlanVerifyGrader(plan, NumericPolicy(), llm=FakeLLM(responses),
                            model_version="fake-model", sc_n=sc_n)


@pytest.mark.asyncio
async def test_grade_path_prices_from_verdicts():
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "not_met", quote="", basis="חיפשתי בדיקת null — אין")])
    draft = await _agent(_basic_plan(), [resp]).grade(_gradable([_scope()]))

    assert draft.prompt_version == VERIFIER_PROMPT_VERSION == "grader-v5.4"
    assert draft.plan_version == "test-plan/v1"
    assert draft.model_version == "fake-model"
    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.points_awarded == Decimal("2")            # 2 (met) + 0 (not_met)
    assert co.evidence_quotes and co.evidence_quotes[0].quote_text \
        == "the student wrote a loop here"
    assert co.evidence_quote.quote_text == "the student wrote a loop here"
    assert "חיפשתי בדיקת null" in co.reasoning
    assert draft.total_cached_input_tokens == 25
    assert draft.scope_outcomes[0].cached_input_tokens == 25
    # [COST_TRUTH] served id captured from response metadata, distinct from
    # model_version (the request)
    assert draft.served_models == ["fake-model-2026-01-01"]


@pytest.mark.asyncio
async def test_fabricated_span_earns_nothing_and_flags():
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met", quote="totally invented ink about arrays"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    draft = await _agent(_basic_plan(), [resp]).grade(_gradable([_scope()]))
    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.points_awarded == Decimal("1")            # only the real span earns
    assert any(f.reason == FlagReason.EVIDENCE_UNVERIFIED for f in co.flags)
    assert any(a.annotation_type == "evidence_unverified" for a in draft.annotations)


@pytest.mark.asyncio
async def test_missing_verdict_is_flagged_not_credited():
    resp = ScopeVerificationResponse(verdicts=[_verdict("c1.k1", "met")])
    draft = await _agent(_basic_plan(), [resp]).grade(_gradable([_scope()]))
    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.points_awarded == Decimal("2")
    assert any(f.reason == FlagReason.UNVERIFIED_CHECK for f in co.flags)
    assert co.confidence == 0.0                          # min over checks


@pytest.mark.asyncio
async def test_closed_world_extra_check_id_annotated_and_dropped():
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"), _verdict("c1.k2", "met",
                                           quote="and a null check there"),
        _verdict("ghost.k9", "met")])
    draft = await _agent(_basic_plan(), [resp]).grade(_gradable([_scope()]))
    assert draft.scope_outcomes[0].points_awarded == Decimal("3")
    assert any(a.annotation_type == "closed_world_violation"
               and a.target_id == "ghost.k9" for a in draft.annotations)


@pytest.mark.asyncio
async def test_skip_path_untouched():
    draft = await _agent(_basic_plan(), [
        ScopeVerificationResponse(verdicts=[])]).grade(
        _gradable([_scope(answer=None, alignment="answer_missing")]))
    so = draft.scope_outcomes[0]
    assert so.graded_by == "skipped_no_answer"
    assert so.points_awarded == Decimal("0")


@pytest.mark.asyncio
async def test_sc3_median_wins():
    """Three calls disagree on c1.k1 (met, not_met, met) — the ordinal median
    is met; c1.k2 is unanimous. Tokens sum across the three calls."""
    r_met = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    r_not = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "not_met", quote="", basis="לא נמצא"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    draft = await _agent(_basic_plan(), [r_met, r_not, r_met], sc_n=3).grade(
        _gradable([_scope()]))
    so = draft.scope_outcomes[0]
    assert so.criterion_outcomes[0].points_awarded == Decimal("3")
    assert so.input_tokens == 300 and so.output_tokens == 120


# ---------------------------------------------------------------------------
# [OD-R1, owner-ruled 2026-09-10] A failed scope is re-graded automatically.
#
# This block REPLACES `test_parse_failure_degrades_to_failed_scope_no_retry`,
# which pinned the opposite rule (GA-3/R6: "deterministic parse failure at temp
# 0 — never retried"). That premise is false — §17.5 records this model class
# answering identically-framed input three different ways at temperature 0 —
# and it was load-bearing: on graded_test e372e6f1 the un-retried ValueError
# zeroed a 16-point scope and left a test that could never be approved.
# ---------------------------------------------------------------------------

class FlakyParseLLM(FakeLLM):
    """`parsing_error` on the first N calls, then the queued response."""

    def __init__(self, responses: List, failures: int = 1):
        super().__init__(responses)
        self.failures = failures

    def with_structured_output(self, schema, include_raw=False):
        outer = self
        healthy = super().with_structured_output(schema, include_raw)

        class _Runner:
            async def ainvoke(self, messages):
                if outer.failures > 0:
                    outer.failures -= 1
                    outer.calls.append(messages)
                    return {"raw": None, "parsed": None,
                            "parsing_error": "bad json"}
                return await healthy.ainvoke(messages)
        return _Runner()


@pytest.fixture
def no_backoff(monkeypatch):
    """The retry sleeps 0.5-2.0s in production; the suite need not."""
    monkeypatch.setattr(grader_v5_mod, "RETRY_BACKOFF_MIN", 0.0)
    monkeypatch.setattr(grader_v5_mod, "RETRY_BACKOFF_MAX", 0.0)


@pytest.mark.asyncio
async def test_a_parse_failure_is_retried_and_she_never_learns_of_it(no_backoff):
    """The whole point of the ruling: a blip that heals leaves no trace."""
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    fake = FlakyParseLLM([resp], failures=1)
    draft = await PlanVerifyGrader(
        _basic_plan(), NumericPolicy(), llm=fake,
        model_version="fake-model").grade(_gradable([_scope()]))

    so = draft.scope_outcomes[0]
    assert len(fake.calls) == 2                     # failed once, re-graded once
    assert so.graded_by == "llm"                    # healed — not "failed"
    assert so.retry_count == 1
    assert so.points_awarded == Decimal("3")
    assert not any(a.annotation_type == "llm_failure" for a in draft.annotations)


@pytest.mark.asyncio
async def test_two_parse_failures_fail_the_scope_but_leave_her_its_checks(no_backoff):
    """The fallback must be REACHABLE. A crashed scope used to arrive with its
    criteria and NO checks, so there was nothing on screen to override — and
    since the blocking annotation is cleared only BY overriding, the row was a
    dead end for everyone."""
    fake = FlakyParseLLM([ScopeVerificationResponse(verdicts=[])], failures=2)
    draft = await PlanVerifyGrader(
        _basic_plan(), NumericPolicy(), llm=fake,
        model_version="fake-model").grade(_gradable([_scope()]))

    so = draft.scope_outcomes[0]
    assert len(fake.calls) == 2                     # one retry, then it stops
    assert so.graded_by == "failed" and so.points_awarded == Decimal("0")
    assert so.retry_count == 1

    failures = [a for a in draft.annotations if a.annotation_type == "llm_failure"]
    assert len(failures) == 1
    # The CAUSE travels with the annotation — «ValueError» alone was the only
    # record of the live incident anywhere, logs included (§8).
    assert "LLM parse failure" in failures[0].message

    checks = [c for co in so.criterion_outcomes for c in (co.checks or [])]
    assert [c.check_id for c in checks] == ["c1.k1", "c1.k2"]
    assert all(c.verdict == "not_met" and c.confidence == 0.0 for c in checks)


@pytest.mark.asyncio
async def test_a_billing_failure_is_never_retried(no_backoff):
    """The one carve-out. A permanent 429 fails every scope of every test, so a
    retry recovers nothing and doubles the cost of a run already lost."""
    fake = FakeLLM([RuntimeError("Error code: 429 - insufficient_quota")])
    draft = await PlanVerifyGrader(
        _basic_plan(), NumericPolicy(), llm=fake,
        model_version="fake-model").grade(_gradable([_scope()]))

    so = draft.scope_outcomes[0]
    assert len(fake.calls) == 1                     # asked once, not twice
    assert so.graded_by == "failed" and so.retry_count == 0


def test_check_verdict_decode_order_is_evidence_first():
    """The grader-v2 lever carried into v5: the verdict is decoded AFTER the
    evidence span and the basis text. Pinned at schema AND prompt level."""
    want = ["check_id", "evidence_quote", "basis_he", "verdict", "confidence",
            "units_correct"]          # [compiler v2, C3] the count, appended AFTER the pin
    assert list(CheckVerdict.model_fields) == want
    assert list(CheckVerdict.model_json_schema()["properties"]) == want
    fmt = VERIFIER_SYSTEM_PROMPT[VERIFIER_SYSTEM_PROMPT.index("OUTPUT FORMAT"):]
    # anchor on the field-listing lines ("  <name> ") — a bare substring match
    # would hit "verdict" inside the word "verdicts"
    positions = [fmt.index(f"\n  {f} ") for f in want[:5]]
    assert positions == sorted(positions)
    # [compiler v2, OD-18] the count is NOT in the pinned system prompt — the
    # grader-v5.3 package stays byte-identical; a counted check explains
    # `units_correct` in the USER message, and only when such a check is present.
    assert "units_correct" not in VERIFIER_SYSTEM_PROMPT
    from app.agents.grader.verifier_prompt import _COUNTED_RULE
    assert "units_correct" in _COUNTED_RULE


def test_verifier_prompt_is_point_blind_and_carries_the_two_proven_clauses():
    assert "SURFACE FORM IS NEVER A DEFECT" in VERIFIER_SYSTEM_PROMPT
    assert "is the authority on naming and form" in VERIFIER_SYSTEM_PROMPT
    # v5.1 ruling 2: the PL-9 wrong-target clause, owner text verbatim
    assert "דמיון מבני לחישוב אחר אינו נוכחות חלקית" in VERIFIER_SYSTEM_PROMPT
    # v5.3 ruling R-D: the C-1 object-literalism principle, owner verbatim
    assert "מדרגים את הדיו, לא את הכוונה" in VERIFIER_SYSTEM_PROMPT
    # v5.1 ruling 3: the basis-lean contract
    assert "basis_he is LEAN" in VERIFIER_SYSTEM_PROMPT
    # the killed magnitude language must not resurface
    assert "DEDUCTION SIZE" not in VERIFIER_SYSTEM_PROMPT
    assert "points_awarded" not in VERIFIER_SYSTEM_PROMPT
    # rendering shows no numeric point values for the checks
    msg = build_verifier_message(_scope(), _basic_plan().terminals)
    assert "VERIFY THESE" in msg and "c1.k1, c1.k2" in msg
    assert "(3" not in msg and "pts" not in msg


def test_sc_n_must_be_odd():
    with pytest.raises(ValueError):
        PlanVerifyGrader(_basic_plan(), NumericPolicy(), llm=FakeLLM([]), sc_n=2)


# ---------------------------------------------------------------------------
# CascadeGrader (Stage 3, FP2) — router + two-tier accounting, zero API calls
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_cascade_routes_on_partially_met_and_champion_wins():
    from app.agents.grader.grader_cascade import CascadeGrader
    base_resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "partially_met"),          # router trigger
        _verdict("c1.k2", "met", quote="and a null check there")])
    champ_resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    agent = CascadeGrader(_basic_plan(), NumericPolicy(),
                          base_llm=FakeLLM([base_resp]),
                          champion_llm=FakeLLM([champ_resp]),
                          base_model_version="base-model",
                          champion_model_version="champ-model")
    draft = await agent.grade(_gradable([_scope()]))
    co = draft.scope_outcomes[0].criterion_outcomes[0]
    assert co.points_awarded == Decimal("3")          # champion verdicts won
    assert any(a.annotation_type == "cascade_routed" for a in draft.annotations)
    assert draft.cascade_usage["base-model"]["input"] == 100
    assert draft.cascade_usage["champ-model"]["input"] == 100
    assert draft.model_version == "cascade:base-model+champ-model"
    assert agent.routed_scopes == ["q1"]


@pytest.mark.asyncio
async def test_cascade_clean_scope_never_escalates():
    from app.agents.grader.grader_cascade import CascadeGrader
    base_resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "not_met", quote="", basis="חיפשתי — אין")])
    champ = FakeLLM([ScopeVerificationResponse(verdicts=[])])
    agent = CascadeGrader(_basic_plan(), NumericPolicy(),
                          base_llm=FakeLLM([base_resp]), champion_llm=champ,
                          base_model_version="base-model",
                          champion_model_version="champ-model")
    draft = await agent.grade(_gradable([_scope()]))
    assert champ.calls == []                          # champion never invoked
    assert draft.cascade_usage["champ-model"]["input"] == 0
    assert agent.routed_scopes == []
    assert draft.scope_outcomes[0].criterion_outcomes[0].points_awarded == Decimal("2")


@pytest.mark.asyncio
async def test_cascade_routes_on_low_confidence_and_unverified_span():
    from app.agents.grader.grader_cascade import CascadeGrader
    # low confidence
    r1 = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met", conf=0.5),
        _verdict("c1.k2", "met", quote="and a null check there")])
    # unverified span on met
    r2 = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met", quote="invented ink entirely"),
        _verdict("c1.k2", "met", quote="and a null check there")])
    for base_resp in (r1, r2):
        champ = FakeLLM([ScopeVerificationResponse(verdicts=[
            _verdict("c1.k1", "met"),
            _verdict("c1.k2", "met", quote="and a null check there")])])
        agent = CascadeGrader(_basic_plan(), NumericPolicy(),
                              base_llm=FakeLLM([base_resp]), champion_llm=champ,
                              base_model_version="b", champion_model_version="c")
        await agent.grade(_gradable([_scope()]))
        assert agent.routed_scopes == ["q1"], "router must fire"


# ---------------------------------------------------------------------------
# Prompt-pin guard (owner ruling 2026-08-31, item 3)
# ---------------------------------------------------------------------------

def test_sonnet_prompt_pin_is_v53_and_v6_is_an_artifact_not_a_pin():
    """v6 was killed on both arms (2026-08-30). The pin rolled back to v5.3 and
    v6 is retained only as a dated artifact OUTSIDE the SUT, so the rollback is
    a byte-identity restore. This guard fails if v6 is ever silently re-pinned."""
    from pathlib import Path
    # [OD-W6] v5.4 = v5.3's system prompt byte-identical + the conditional
    # counted rule in the user message (PLAN COMPILER v2).
    assert VERIFIER_PROMPT_VERSION == "grader-v5.4"

    # v6's distinctive text must NOT be live in the prompt
    for marker in ("<verdict_standard>", "Omit entirely for met",
                   "grade the ink, not the"):
        assert marker not in VERIFIER_SYSTEM_PROMPT, (
            f"v6 text {marker!r} is live in the verifier prompt — v6 is KILLED "
            f"and must stay an artifact (owner ruling 2026-08-31 item 3)")

    # ...and the artifact must still exist, carrying the text and the verdict
    art = Path(__file__).resolve().parents[1] / "grading_eval_suite" / "GRADER_V6_ARTIFACT.md"
    assert art.exists(), "the v6 artifact was deleted; it is the dated record"
    body = art.read_text(encoding="utf-8")
    assert "KILLED on both k=3 arms" in body
    assert "Omit entirely for met" in body          # the text is preserved
    assert "torn-rule is recorded UNTESTED" in body  # and so is the ruling


# ---------------------------------------------------------------------------
# Multisubject seam (2026-09-08, D-16): the subject selects the verifier SYSTEM
# prompt and the stamp. CS is byte-identical (pinned elsewhere); a non-CS
# subject carries `+<key>` on the draft and never sees the code-trace rules.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_non_cs_subject_stamps_the_suffix_and_swaps_the_system_prompt():
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "not_met", quote="", basis="חיפשתי — אין")])
    llm = FakeLLM([resp])
    agent = PlanVerifyGrader(_basic_plan(), NumericPolicy(), llm=llm,
                             model_version="fake-model", subject="english")
    draft = await agent.grade(_gradable([_scope()]))

    assert draft.prompt_version == "grader-v5.4+english"
    system_text = llm.calls[0][0].content
    assert "SURFACE FORM IS NEVER A DEFECT" not in system_text      # the CS rule 5
    assert "VERIFY WHAT THE WRITTEN CODE DOES" not in system_text   # the CS rule 3
    assert "3. VERIFY WHAT THE STUDENT WROTE" in system_text
    assert "6. VERDICT MEANINGS" in system_text                     # rules 6-8 kept


@pytest.mark.asyncio
async def test_cs_subject_is_the_default_and_keeps_the_pinned_stamp():
    resp = ScopeVerificationResponse(verdicts=[
        _verdict("c1.k1", "met"),
        _verdict("c1.k2", "not_met", quote="", basis="חיפשתי — אין")])
    llm = FakeLLM([resp])
    draft = await PlanVerifyGrader(_basic_plan(), NumericPolicy(), llm=llm,
                                   model_version="fake-model").grade(_gradable([_scope()]))
    assert draft.prompt_version == VERIFIER_PROMPT_VERSION == "grader-v5.4"
    assert "SURFACE FORM IS NEVER A DEFECT" in llm.calls[0][0].content


def test_unknown_subject_refuses_at_construction():
    with pytest.raises(ValueError):
        PlanVerifyGrader(_basic_plan(), NumericPolicy(), llm=FakeLLM([]),
                         model_version="fake-model", subject="physics")
