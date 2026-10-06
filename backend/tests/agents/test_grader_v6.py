"""grader-v6 verifier (PR_grader_v6_options.md §6, §14 Phase 3). No provider is
ever called: a scripted fake model answers from the rendered message."""
from __future__ import annotations

import json
import re
from decimal import Decimal as D

import pytest
from langchain_core.messages import AIMessage

from app.agents.grader.grader_v6 import OptionsVerifyGrader
from app.agents.grader.payload_aliases import ALIAS_PATTERN
from app.agents.grader.plan_schemas import (CheckVerdictV6, GradingPlanV6, ScopeVerdictsV6)
from app.agents.grader.verifier_prompt_v6 import (build_verifier_v6_message, verifier_aliases,
                                                  verifier_v6_system_prompt)
from app.schemas.graded_test_draft_v6 import v6_content
from app.services.pricing_v6 import price
from app.subjects import get_profile
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

MODEL = "claude-sonnet-5-5"


@pytest.fixture(scope="module")
def hobby():
    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    return plan, load_bundle("din_ezra", require_gt=False)


_CHECK_LINE = re.compile(r"^(c\d+) \[(CREDIT|FAULT|NOTE)\] ", re.M)
_OPT_LINE = re.compile(r"^   (o\d+): ", re.M)


def _parse_message(text):
    """{check alias: (role, [option aliases])} from a rendered user message."""
    out, current = {}, None
    for line in text.splitlines():
        m = _CHECK_LINE.match(line)
        if m:
            current = m.group(1)
            out[current] = (m.group(2), [])
            continue
        m = _OPT_LINE.match(line)
        if m and current:
            out[current][1].append(m.group(1))
    return out


class _Fake:
    """Answers every check with `pick(role, options, answer)`; scriptable."""

    def __init__(self, pick, *, extra=(), served=MODEL, fail_times=0, quote=None):
        self.pick, self.extra, self.served, self.fail_times = pick, list(extra), served, fail_times
        self.quote, self.calls, self.messages = quote, 0, []

    def with_structured_output(self, schema, include_raw=True):
        assert schema is ScopeVerdictsV6 and include_raw
        return self

    async def ainvoke(self, messages):
        self.calls += 1
        user = messages[-1].content
        self.messages.append(user)
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ValueError("boom")
        answer = user.split("STUDENT ANSWER")[1].split("═" * 79)[1].strip().splitlines()
        first_line = answer[0] if answer else ""
        verdicts = []
        n = self.messages.count(user) - 1           # this scope message's own call number
        for cid, (role, opts) in _parse_message(user).items():
            o = self.pick(role, opts, n) if self.pick.__code__.co_argcount == 3 else self.pick(role, opts)
            default = opts[-1] if role == "CREDIT" else opts[0]
            q = "" if o == default else (self.quote if self.quote is not None else first_line)
            verdicts.append(CheckVerdictV6(check_id=cid, evidence_quote=q,
                                           absence_pointer_he="אין תשובה" if (role == "CREDIT" and o == default) else "",
                                           option_id=o))
        verdicts += self.extra
        raw = AIMessage(content="", usage_metadata={"input_tokens": 100, "output_tokens": 10,
                                                    "total_tokens": 110},
                        response_metadata={"model": self.served})
        return {"raw": raw, "parsed": ScopeVerdictsV6(verdicts=verdicts), "parsing_error": None}


def _grader(plan, bundle, fake, **kw):
    return OptionsVerifyGrader(plan, bundle.rubric_contract, llm=fake, model_version=MODEL,
                               profile=get_profile("computer_science"), **kw)


def _full(role, opts):
    return opts[0] if role == "CREDIT" else opts[0]


# ── output contract ─────────────────────────────────────────────────────────

def test_check_verdict_v6_decode_order_is_evidence_first():
    assert list(CheckVerdictV6.model_fields) == ["check_id", "evidence_quote",
                                                 "absence_pointer_he", "option_id"]
    props = list(ScopeVerdictsV6.model_json_schema()["$defs"]["CheckVerdictV6"]["properties"])
    assert props.index("evidence_quote") < props.index("option_id")


def test_verifier_payload_has_no_values(hobby):
    """§6.1: no option value and no points reach the verifier. Proof by invariance:
    change every option value (and every terminal's points) and the rendered
    message is byte-identical; and every id in it is an AM-G17 alias."""
    plan, bundle = hobby
    shifted = [c.model_copy(update={"options": [o.model_copy(update={"value": o.value * 7 + 3})
                                                 for o in c.options]}) for c in plan.checks]
    for scope in bundle.gradable_test.scopes:
        tids = {t for c in scope.criteria for t in ([s.sub_criterion_id for s in c.sub_criteria]
                                                   if c.sub_criteria else [c.criterion_id])}
        checks = [c for c in plan.checks if c.priced_terminal_id in tids]
        other = [c for c in shifted if c.priced_terminal_id in tids]
        msg = build_verifier_v6_message(scope, checks, verifier_aliases(checks))
        assert msg == build_verifier_v6_message(scope, other, verifier_aliases(other))
        checks_part = msg.split("CHECKS")[1].split("STUDENT ANSWER")[0]
        for c in checks:
            assert c.check_id not in msg and c.priced_terminal_id not in msg
        ids = re.findall(r"^\s*([a-z]\d+)(?::| \[)", checks_part, re.M)
        assert ids and all(ALIAS_PATTERN.fullmatch(i) for i in ids)


# ── the whole path: verify → price → envelope ──────────────────────────────

async def test_grade_prices_with_the_one_pricer_and_projects_its_awards(hobby):
    plan, bundle = hobby
    fake = _Fake(_full)
    draft = await _grader(plan, bundle, fake).grade(bundle.gradable_test)
    content = v6_content(draft)
    assert content is not None and content.plan_hash == plan.plan_hash
    priced = price(content.to_view())
    awards = {t.terminal_id: t.awarded for t in priced.terminals}
    for so in draft.scope_outcomes:
        for co in so.criterion_outcomes:
            leaves = co.sub_criterion_outcomes or [co]
            for leaf in leaves:
                tid = getattr(leaf, "sub_criterion_id", None) or leaf.criterion_id
                assert leaf.points_awarded == awards[tid]
    # every graded check has a selection; every credit terminal has a line
    graded = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "llm"}
    assert graded
    credit_tids = {c.plan.priced_terminal_id for c in content.checks if c.plan.role == "credit"}
    assert {e.terminal_id for e in content.explanations} == credit_tids
    assert draft.served_models == [MODEL] and not content.verifier_usage.model_fallback


async def test_unknown_check_dropped_and_flagged(hobby):
    plan, bundle = hobby
    fake = _Fake(_full, extra=[CheckVerdictV6(check_id="c99", evidence_quote="", absence_pointer_he="",
                                              option_id="o1")])
    draft = await _grader(plan, bundle, fake).grade(bundle.gradable_test)
    assert any(a.annotation_type == "closed_world_violation" and a.severity.value == "info"
               for a in draft.annotations)
    assert any(f.reason.value == "closed_world_violation" for so in draft.scope_outcomes for f in so.flags)


async def test_foreign_option_treated_as_missing(hobby):
    plan, bundle = hobby
    draft = await _grader(plan, bundle, _Fake(lambda role, opts: "o42")).grade(bundle.gradable_test)
    content = v6_content(draft)
    graded = [c for c in content.checks if any(
        s.graded_by == "llm" for s in content.scopes)]
    assert all(c.model_option_id is None for c in graded)
    assert any("foreign_option" in c.flags for c in content.checks)
    priced = price(content.to_view())
    assert all(t.awarded == 0 for t in priced.terminals)                 # PRC-1 defaults


async def test_duplicate_verdict_first_wins_and_flags(hobby):
    plan, bundle = hobby
    dup = CheckVerdictV6(check_id="c1", evidence_quote="", absence_pointer_he="אין תשובה",
                         option_id="o9")                                 # second c1: ignored
    draft = await _grader(plan, bundle, _Fake(_full, extra=[dup])).grade(bundle.gradable_test)
    flags = [f for so in draft.scope_outcomes for f in so.flags
             if f.reason.value == "closed_world_violation" and "duplicate" in f.message]
    assert flags


async def test_quote_policy_identical_for_fault_options(hobby):
    """§6.3: every non-default option's quote is checked, fault and credit alike;
    a fabricated quote is recorded `not_found` and the PRICER gates it."""
    plan, bundle = hobby

    def worst(role, opts):
        return opts[-1] if role == "FAULT" and len(opts) > 1 else opts[0]

    draft = await _grader(plan, bundle, _Fake(worst, quote="זה לא כתוב בתשובה בכלל")).grade(
        bundle.gradable_test)
    content = v6_content(draft)
    chosen_non_default = [c for c in content.checks if c.model_option_id is not None
                          and c.model_option_id != c.plan.default_option.option_id]
    roles = {c.plan.role for c in chosen_non_default}
    assert {"credit", "fault"} <= roles
    assert all(c.quote_status == "not_found" for c in chosen_non_default)
    priced = price(content.to_view())
    gated = {r.check_id for r in priced.checks if r.source == "gated"}
    assert {c.plan.check_id for c in chosen_non_default if c.plan.evidence_required} <= gated
    assert any(a.annotation_type == "evidence_unverified" for a in draft.annotations)


async def test_scope_failure_defaults_all_checks(hobby, monkeypatch):
    import app.agents.grader.grader_v6 as g6
    monkeypatch.setattr(g6, "RETRY_BACKOFF_MIN", 0)
    monkeypatch.setattr(g6, "RETRY_BACKOFF_MAX", 0)
    plan, bundle = hobby
    fake = _Fake(_full, fail_times=10_000)
    draft = await _grader(plan, bundle, fake).grade(bundle.gradable_test)
    content = v6_content(draft)
    graded_scopes = [s for s in content.scopes if s.graded_by != "skipped_no_answer"]
    assert graded_scopes and all(s.graded_by == "failed" and s.retry_count == 1 for s in graded_scopes)
    assert all(c.model_option_id is None for c in content.checks)
    assert any(a.annotation_type == "llm_failure" for a in draft.annotations)
    assert all(so.points_awarded == 0 for so in draft.scope_outcomes)


async def test_sc_n_consensus_is_the_median_over_option_values(hobby):
    """AM-G8: three calls pick full / absent / full → the median value is full."""
    plan, bundle = hobby
    def pick(role, opts, n):
        return opts[-1] if n == 1 else opts[0]     # call 0: full · call 1: absent · call 2: full

    draft = await _grader(plan, bundle, _Fake(pick), sc_n=3).grade(bundle.gradable_test)
    content = v6_content(draft)
    credit = [c for c in content.checks if c.plan.role == "credit" and c.model_option_id]
    assert credit and all(c.model_option_id == c.plan.options[0].option_id for c in credit)


async def test_a_fallback_served_call_is_flagged_model_fallback(hobby):
    plan, bundle = hobby
    draft = await _grader(plan, bundle, _Fake(_full, served="claude-sonnet-5")).grade(
        bundle.gradable_test)
    assert v6_content(draft).verifier_usage.model_fallback


def test_a_plan_that_does_not_rehash_is_refused(hobby):
    plan, bundle = hobby
    bad = plan.model_copy(update={"plan_hash": "0" * 64})
    with pytest.raises(ValueError, match="plan_hash"):
        _grader(bad, bundle, _Fake(_full))
