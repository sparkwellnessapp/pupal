"""grader-v6 explainer — the call, the fallback, the wall (PR_grader_v6_options.md §7.2, §7.5).
Fake chat models only: no provider is ever constructed (tests/conftest.py's guard).

  test_invalid_line_falls_back_for_that_terminal_only
  test_explainer_timeout_falls_back_and_test_still_drafts
  test_explainer_not_retried_on_content_failure
  test_typed_amount_makes_line_teacher_decided
  test_explainer_skips_excluded_skipped_and_failed_scopes (the call half)
  + usage and served-model provenance, the one log line, and the §13.4 replay.
"""
from __future__ import annotations

import asyncio
import logging
from decimal import Decimal

import httpx
import openai
import pytest

import app.agents.explainer.explainer as explainer_mod
from app.agents.explainer.copy import MACHINE_VOCABULARY, MANUAL_HE
from app.agents.explainer.explainer import explain_test
from app.agents.explainer.fallback import compose_reasoning_he
from app.agents.explainer.payload import payload_from_dict
from app.agents.explainer.replay import replay_payloads
from app.services.pricing_v6 import CheckDecision
from app.subjects import get_profile
from tests.agents.explainer_cases import (MODEL_ID, FakeLLM, XSel, aliases_of, echo, make_content,
                                          materials, ok, priced_of)
from tests.services.pricing_v6_cases import binary, fault, overlay, term

D = Decimal
CS = get_profile("computer_science")
A, B, C = "q1.c0", "q1.c1", "q2.c0"
TEXTS = {("q1", None): {A: "עדכון הערך דרך SetValue (4 נק'). גישה ישירה — יורדו 2 נק'.",
                        B: "הדפסת התוצאה (2 נק')"},
         ("q2", None): {C: "החזרת הסכום (3 נק')"}}


@pytest.fixture(autouse=True)
def _no_backoff(monkeypatch):
    monkeypatch.setattr(explainer_mod, "_retry_backoff_s", lambda: 0.0)


def _case(ov=None):
    ca = binary(f"{A}.c1", A, 4, desc="עדכון הערך", full="הערך מעודכן", absent="הערך אינו מעודכן")
    fa = fault(f"{A}.f1", A, [("m1", 2, "העדכון בגישה ישירה")], requires=f"{A}.c1",
               desc="גישה ישירה")
    cb = binary(f"{B}.c1", B, 2, desc="הדפסת התוצאה", absent="התוצאה אינה מודפסת")
    cc = binary(f"{C}.c1", C, 3, desc="החזרת הסכום")
    content = make_content(
        [term(A, 4), term(B, 2), term(C, 3, q="q2")],
        [XSel(ca, "full", evidence="obj.value = 5;"), XSel(fa, "f1", evidence="obj.value = 5;"),
         XSel(cb, "absent", quote=None, pointer="התוצאה מוחזרת ולא מודפסת"),
         XSel(cc, "full", evidence="return total;")])
    return content, priced_of(content, ov), materials(TEXTS)


GOOD = {"q1": {"t1": "הערך עודכן בגישה ישירה ולא דרך SetValue, ולכן ירדו 2 נקודות.",
               "t2": "התוצאה מוחזרת ולא מודפסת, ולכן אין נקודות על הסעיף."},
        "q2": {"t1": "הסכום total מוחזר, כנדרש."}}


def _scope_of(message: str) -> str:
    return "q1" if "ראשונה" in message else "q2"


def good_llm(**raw_kw) -> FakeLLM:
    return echo(lambda alias, msg: GOOD[_scope_of(msg)][alias], **raw_kw)


async def _explain(llm, ov=None, **kw):
    content, priced, mats = _case(ov)
    result = await explain_test(content, priced, mats, llm=llm, model_id=MODEL_ID, profile=CS, **kw)
    return content, priced, result


def _by_tid(result):
    return {e.terminal_id: e for e in result.explanations}


# ── the happy path, usage and provenance ─────────────────────────────────────

async def test_one_call_per_scope_and_one_line_per_credit_terminal(caplog) -> None:
    llm = good_llm()
    with caplog.at_level(logging.INFO, logger="app.agents.explainer.explainer"):
        content, priced, result = await _explain(llm)
    assert len(llm.calls) == 2                                      # q1, q2 — in parallel
    assert [e.terminal_id for e in result.explanations] == [A, B, C]   # plan order
    by = _by_tid(result)
    assert {t: (e.source, e.text_he) for t, e in by.items()} == {
        A: ("model", GOOD["q1"]["t1"]), B: ("model", GOOD["q1"]["t2"]), C: ("model", GOOD["q2"]["t1"])}
    assert set(llm.systems) == {llm.systems[0]}                     # one cached prefix
    u = result.usage
    assert (u.model, u.calls, u.input_tokens, u.output_tokens, u.cached_input_tokens) == \
        (MODEL_ID, 2, 200, 40, 120)
    assert (u.served_models, u.model_fallback) == ([MODEL_ID], False)
    assert result.payloads == []
    done = [r.getMessage() for r in caplog.records if r.getMessage().startswith("explainer_done")]
    assert len(done) == 1
    assert "lines=3 model=3 fallback=0 teacher=0 failed_rules=none" in done[0]


async def test_a_call_served_by_another_model_is_flagged() -> None:
    _c, _p, result = await _explain(good_llm(model="claude-sonnet-5"))
    assert result.usage.served_models == ["claude-sonnet-5"] and result.usage.model_fallback
    _c, _p, result = await _explain(good_llm(model=f"{MODEL_ID}-20261001"))
    assert not result.usage.model_fallback                         # a dated snapshot is the model


# ── E-1..E-5 → fallback, per terminal ────────────────────────────────────────

async def test_invalid_line_falls_back_for_that_terminal_only() -> None:
    bad = f"ה{MACHINE_VOCABULARY[3]} קבע שהתוצאה אינה מודפסת"     # «מודל» — E-3
    llm = echo(lambda alias, msg: bad if (_scope_of(msg), alias) == ("q1", "t2")
               else GOOD[_scope_of(msg)][alias])
    content, priced, result = await _explain(llm)
    by = _by_tid(result)
    assert (by[A].source, by[C].source) == ("model", "model")       # the others are untouched
    assert by[B].source == "fallback" and by[B].failed_rules == ["E-3"]
    assert by[B].text_he == compose_reasoning_he(priced, content.to_view(), B)
    assert any("failed=E-3" in t for t in result.telemetry)


async def test_a_line_missing_or_misaddressed_fails_e1() -> None:
    llm = FakeLLM(lambda msg, n: ok([("t1", GOOD["q1"]["t1"]), ("t7", "שורה")])
                  if _scope_of(msg) == "q1" else ok([("t1", GOOD["q2"]["t1"])]))
    _c, _p, result = await _explain(llm)
    by = _by_tid(result)
    assert by[A].source == "model"
    assert (by[B].source, by[B].failed_rules) == ("fallback", ["E-1"])
    assert any("alias_dropped" in t and "t7" in t for t in result.telemetry)


async def test_several_rules_are_all_recorded() -> None:
    bad = "אני חושב שירדו 7 נקודות " + "א" * 200                     # E-2, E-4, E-5
    llm = echo(lambda alias, msg: bad if alias == "t1" and _scope_of(msg) == "q2"
               else GOOD[_scope_of(msg)][alias])
    _c, _p, result = await _explain(llm)
    assert _by_tid(result)[C].failed_rules == ["E-2", "E-4", "E-5"]


# ── the wall ─────────────────────────────────────────────────────────────────

async def test_explainer_timeout_falls_back_and_test_still_drafts() -> None:
    async def slow(lines):
        await asyncio.sleep(5)
        return ok(lines)

    def respond(msg, n):
        lines = [(a, GOOD[_scope_of(msg)][a]) for a in aliases_of(msg)]
        return slow(lines) if _scope_of(msg) == "q2" else ok(lines)

    llm = FakeLLM(respond)
    content, priced, result = await _explain(llm, timeout_s=0.2)    # returns: no exception
    by = _by_tid(result)
    assert (by[A].source, by[B].source) == ("model", "model")      # q1 finished in time
    assert by[C].source == "fallback" and by[C].failed_rules == []
    assert by[C].text_he == compose_reasoning_he(priced, content.to_view(), C)
    assert any(t.startswith("timeout") and "q2" in t for t in result.telemetry)
    assert result.usage.calls == 2


# ── retries: transport once, content never ───────────────────────────────────

def _connection_error() -> Exception:
    return openai.APIConnectionError(request=httpx.Request("POST", "https://provider.invalid"))


async def test_explainer_not_retried_on_content_failure() -> None:
    # (a) the provider answered, the output did not parse: ONE call, E-1 fallbacks
    llm = FakeLLM(lambda msg, n: {"raw": None, "parsed": None, "parsing_error": "bad json"})
    _c, _p, result = await _explain(llm)
    assert len(llm.calls) == 2                                      # one per scope, no retry
    assert all(e.source == "fallback" and e.failed_rules == ["E-1"] for e in result.explanations)

    # (b) a content exception: ONE call per scope, fallbacks with no rule (no line came back)
    def boom(msg, n):
        raise ValueError("structured output did not validate")
    llm = FakeLLM(boom)
    _c, _p, result = await _explain(llm)
    assert len(llm.calls) == 2
    assert all(e.source == "fallback" and e.failed_rules == [] for e in result.explanations)
    assert any("call_failed kind=content" in t for t in result.telemetry)

    # (c) an invalid LINE is not retried either: the call count stays one per scope
    llm = echo(lambda alias, msg: "PL-10")
    _c, _p, result = await _explain(llm)
    assert len(llm.calls) == 2


async def test_a_transient_transport_error_is_retried_exactly_once() -> None:
    seen = {"q1": 0, "q2": 0}

    def flaky(msg, n):
        scope = _scope_of(msg)
        seen[scope] += 1
        if seen[scope] == 1:
            raise _connection_error()
        return ok([(a, GOOD[scope][a]) for a in aliases_of(msg)])

    llm = FakeLLM(flaky)
    _c, _p, result = await _explain(llm)
    assert seen == {"q1": 2, "q2": 2}
    assert all(e.source == "model" for e in result.explanations)
    assert result.usage.calls == 4

    def down(msg, n):
        raise _connection_error()
    llm = FakeLLM(down)
    _c, _p, result = await _explain(llm)
    assert len(llm.calls) == 4                                      # 2 scopes × (1 + one retry)
    assert all(e.source == "fallback" for e in result.explanations)


async def test_a_permanent_provider_error_is_not_retried() -> None:
    def denied(msg, n):
        raise openai.AuthenticationError(
            "bad key", response=httpx.Response(401, request=httpx.Request("POST", "https://x.invalid")),
            body=None)
    llm = FakeLLM(denied)
    _c, _p, result = await _explain(llm)
    assert len(llm.calls) == 2
    assert any("kind=permanent" in t for t in result.telemetry)


# ── she decided ──────────────────────────────────────────────────────────────

async def test_typed_amount_makes_line_teacher_decided() -> None:
    """[AM-G3] a typed amount on ANY check of a terminal: «הציון נקבע ידנית», and no call
    is made for it."""
    llm = good_llm()
    _c, priced, result = await _explain(llm, overlay({f"{C}.c1": CheckDecision(amount=D("1"))}))
    assert next(t for t in priced.terminals if t.terminal_id == C).typed
    by = _by_tid(result)
    assert (by[C].text_he, by[C].source, by[C].failed_rules) == (MANUAL_HE, "teacher_override", [])
    assert len(llm.calls) == 1                                      # q2's only terminal: no call
    assert all(_scope_of(m) == "q1" for m in llm.calls)

    # a terminal override likewise; its scope-mate is still explained
    llm = good_llm()
    _c, _p, result = await _explain(llm, overlay(pins={A: 3}))
    by = _by_tid(result)
    assert (by[A].text_he, by[A].source) == (MANUAL_HE, "teacher_override")
    assert by[B].source == "model"
    (q1_message,) = [m for m in llm.calls if _scope_of(m) == "q1"]
    assert aliases_of(q1_message) == ["t1"] and TEXTS[("q1", None)][A] not in q1_message


async def test_explainer_skips_excluded_skipped_and_failed_scopes() -> None:
    cs = [binary(f"q{i}.c0.c1", f"q{i}.c0", 2, desc=f"רכיב {i}") for i in range(1, 6)]
    content = make_content(
        [term(f"q{i}.c0", 2, q=f"q{i}") for i in range(1, 6)],
        [XSel(cs[0], "full", evidence="a"), XSel(cs[1], "absent", quote=None),
         XSel(cs[2], "absent", quote=None), XSel(cs[3], "absent", quote=None),
         XSel(cs[4], "full", evidence="b")],
        groups=[(["q4", "q5"], 1)],
        graded_by={("q2", None): "skipped_no_answer", ("q3", None): "failed",
                   ("q4", None): "excluded_by_selection"})
    texts = {(f"q{i}", None): {f"q{i}.c0": f"רכיב {i} (2 נק')"} for i in range(1, 6)}
    llm = echo(lambda alias, msg: "הרכיב קיים, כנדרש.")
    result = await explain_test(content, priced_of(content), materials(texts), llm=llm,
                                model_id=MODEL_ID, profile=CS)
    assert len(llm.calls) == 2                                      # q1 and q5 only (D-6)
    by = _by_tid(result)
    assert [e.terminal_id for e in result.explanations] == [f"q{i}.c0" for i in range(1, 6)]
    assert {t for t, e in by.items() if e.source == "model"} == {"q1.c0", "q5.c0"}
    assert all(by[t].source == "fallback" and by[t].failed_rules == []
               for t in ("q2.c0", "q3.c0", "q4.c0"))


async def test_bad_materials_degrade_that_scope_only(caplog) -> None:
    content, priced, _m = _case()
    mats = materials({("q1", None): TEXTS[("q1", None)]})          # q2's text is missing
    llm = good_llm()
    with caplog.at_level(logging.ERROR, logger="app.agents.explainer.explainer"):
        result = await explain_test(content, priced, mats, llm=llm, model_id=MODEL_ID, profile=CS)
    by = _by_tid(result)
    assert (by[A].source, by[C].source) == ("model", "fallback")
    assert any(r.getMessage().startswith("explainer_input_error scope=q2") for r in caplog.records)


# ── §13.4 arm B: the recorded payloads replay on another model ───────────────

async def test_recorded_payloads_replay_without_a_pricer() -> None:
    _c, _p, result = await _explain(good_llm(), record_payloads=True)
    assert len(result.payloads) == 2
    assert [payload_from_dict(p).question_id for p in result.payloads] == ["q1", "q2"]

    other = "claude-haiku-4-5"
    invalid = echo(lambda alias, msg: "אני חושב שהכול תקין" if _scope_of(msg) == "q2"
                   else GOOD["q1"][alias], model=other)
    replay = await replay_payloads(result.payloads, llm=invalid, model_id=other, profile=CS,
                                   timeout_s=5)
    lines = {ln.terminal_id: ln for ln in replay.lines}
    assert (lines[A].source, lines[A].text_he) == ("model", GOOD["q1"]["t1"])
    assert (lines[C].source, lines[C].failed_rules) == ("fallback", ("E-5",))
    recorded_fallback = payload_from_dict(result.payloads[1]).terminals[0].fallback_he
    assert lines[C].text_he == recorded_fallback
    assert replay.usage.model == other and replay.usage.calls == 2


async def test_replay_keeps_students_apart() -> None:
    """Two students' copies of one scope share terminal ids; each keeps its own line."""
    _c, _p, r1 = await _explain(good_llm(), record_payloads=True)
    payloads = [r1.payloads[1], r1.payloads[1]]                    # the same q2 payload, twice
    calls = []

    def respond(msg, n):
        calls.append(n)
        text = "הסכום total מוחזר, כנדרש." if n == 1 else "PL-10"
        return ok([("t1", text)])
    replay = await replay_payloads(payloads, llm=FakeLLM(respond), model_id=MODEL_ID,
                                   profile=CS, timeout_s=5)
    assert sorted(ln.source for ln in replay.lines) == ["fallback", "model"]
