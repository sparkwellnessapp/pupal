"""
PLAN COMPILER v2 — Stage 2 (segmenter) and 2b (router), with a FAKE model.

No provider is ever called. The fake exposes the grader agents' surface
(`with_structured_output(schema, include_raw=True).ainvoke(messages)`) and
answers from the skeleton itself, so the tests pin the POLICY:

  * the output types cannot carry a number, a kind, an amount or a count;
  * exactly the requested slots, in order — anything else is a retry;
  * V9 / V10 run on every entry with the validator's own rules; a failure
    retries ONCE with the errors verbatim, then the span is SUBSTITUTED and
    the slot flagged — a plan is never blocked on wording;
  * an equivalence note without a licensing citation is dropped, not retried;
  * the envelope stops the run before it can be exceeded;
  * routing replaces a monolith's single check with N even-split checks on the
    ½-lattice, keeps its tariffs, and keeps the monolith when the model fails.
"""
from __future__ import annotations

import asyncio
import hashlib
from decimal import Decimal
from types import SimpleNamespace
from typing import Callable, Dict, List

import pytest

from app.agents.grader.plan_validator import validate_plan
from app.agents.plan_compiler import compile_contract
from app.agents.plan_compiler.assemble import assemble_plan
from app.agents.plan_compiler.route import (RoutedComponent, RouterResponse, apply_routing,
                                            route_monoliths)
from app.agents.plan_compiler.segment import (EnvelopeExceeded, SegmentedSlot, SegmenterResponse,
                                              segment_skeleton, substitute, validate_entries)
from app.agents.plan_compiler.stage0 import contract_scopes, scope_label, terminals_of
from app.agents.plan_gen.prompt import scope_corpus
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

D = Decimal


# ── the fake ────────────────────────────────────────────────────────────────

class _Runner:
    def __init__(self, llm, schema):
        self.llm, self.schema = llm, schema

    async def ainvoke(self, messages):
        self.llm.calls.append(messages)
        parsed = self.llm.respond(messages[-1].content, self.schema, len(self.llm.calls))
        return {"raw": SimpleNamespace(usage_metadata={"input_tokens": 1000, "output_tokens": 300,
                                                       "input_token_details": {}},
                                       response_metadata={"model_name": "fake"}),
                "parsed": parsed, "parsing_error": None}


class FakeLLM:
    def __init__(self, respond: Callable):
        self.respond, self.calls = respond, []

    def with_structured_output(self, schema, include_raw=True):
        assert include_raw
        return _Runner(self, schema)


@pytest.fixture(scope="module")
def hobby():
    b = load_bundle("dan_basiuk")
    contract = b.rubric_contract
    sk = compile_contract(contract, exam_id="hobby_tvshow", rubric_contract_sha256="0" * 64)
    corpora, solutions, questions, points, scopes = {}, {}, {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = scope_label(key)
        corpora[lbl] = scope_corpus(q, sub)
        node = sub or q
        sol = getattr(node, "example_solution", None) or getattr(q, "example_solution", None)
        if sol:
            solutions[lbl] = sol
        questions[lbl] = getattr(sub, "text", "") if sub else getattr(q, "question_text", "")
        for tid, pts in terminals_of(node):
            points[tid], scopes[tid] = pts, lbl
    return dict(contract=contract, skeleton=sk, corpora=corpora, solutions=solutions,
                questions=questions, points=points, scopes=scopes,
                precision=D(str(contract.numeric_policy.precision)))


def _slot_ids_in(message: str) -> List[str]:
    # a repair suffix also says «· slot ids must be …»; real slot lines carry an id with dots
    return [line.split("slot ")[1].split(" ")[0] for line in message.splitlines()
            if line.strip().startswith("· slot ") and "." in line.split("slot ")[1].split(" ")[0]]


def _faithful(skeleton, override: Dict[str, dict] | None = None):
    """A responder that words every slot from the skeleton's own spans (the
    A0 placeholder — valid by construction), with per-slot overrides."""
    by_slot = {s.slot_id: (t, s) for t in skeleton.terminals for s in t.slots}

    def respond(message, schema, n):
        entries = []
        for sid in _slot_ids_in(message):
            t, s = by_slot[sid]
            desc, quote, note = substitute(s, t)
            e = dict(slot_id=sid, rubric_quote=quote or "", description_he=desc, equivalence_note=note or "")
            e.update((override or {}).get(sid, {}))
            entries.append(SegmentedSlot(**e))
        return SegmenterResponse(entries=entries)
    return respond


def _run(coro):
    return asyncio.run(coro)


# ── design law ──────────────────────────────────────────────────────────────

def test_output_types_cannot_carry_a_number_a_kind_or_an_anchor():
    for model in (SegmentedSlot, RoutedComponent):
        assert not {"points", "kind", "tariff_amount", "unit_count", "charge_group"} & set(model.model_fields)
    # cite-then-claim: the quote / evidence is decoded before the claim
    assert list(SegmentedSlot.model_fields)[:2] == ["slot_id", "rubric_quote"]
    assert list(RoutedComponent.model_fields)[0] == "evidence_span"


# ── segmenter ───────────────────────────────────────────────────────────────

def test_faithful_wording_assembles_a_plan_the_validator_accepts(hobby):
    llm = FakeLLM(_faithful(hobby["skeleton"]))
    run = _run(segment_skeleton(hobby["skeleton"], llm, corpora=hobby["corpora"],
                                solutions=hobby["solutions"], cost_fn=lambda i, o, c: 0.001,
                                envelope_usd=2.0))
    slots = [s.slot_id for t in hobby["skeleton"].terminals for s in t.slots]
    assert set(run.wording) == set(slots)
    assert run.substituted == [] and run.notes_dropped == {}
    assert len(run.calls) == len({t.scope for t in hobby["skeleton"].terminals})     # one call per scope
    assert run.clean_first_try == len(run.calls)
    assert abs(run.cost_usd - 0.001 * len(run.calls)) < 1e-9
    plan = assemble_plan(hobby["skeleton"], run.wording, segmenter_prompt_version="segmenter/v1",
                         segmenter_model="fake")
    assert plan.segmenter_model == "fake" and plan.compiler_version == "plan-compiler/v2.0"
    errors = validate_plan(plan, contract_terminal_points=hobby["points"], terminal_scopes=hobby["scopes"],
                           precision=hobby["precision"], scope_corpora=hobby["corpora"])
    assert errors == [], errors


def test_a_point_value_in_the_description_retries_once_then_substitutes(hobby):
    bad = {"q1.ג.c3.k1": {"description_he": "לולאה נכונה, אחרת להוריד 1"}}
    llm = FakeLLM(_faithful(hobby["skeleton"], bad))
    run = _run(segment_skeleton(hobby["skeleton"], llm, corpora=hobby["corpora"],
                                solutions=hobby["solutions"], cost_fn=lambda i, o, c: 0.0,
                                envelope_usd=2.0))
    attempts = [c for c in run.calls if c.scope == "q1.ג"]
    assert [c.attempt for c in attempts] == [1, 2]
    assert any("point value" in e for e in attempts[0].errors)
    assert "FAILED VALIDATION" in llm.calls[-1][-1].content or any(
        "FAILED VALIDATION" in m[-1].content for m in llm.calls)
    assert run.substituted == ["q1.ג.c3.k1"]
    assert "להוריד" not in run.wording["q1.ג.c3.k1"][0]
    # the tariff on the same terminal kept the model's wording
    assert "q1.ג.c3.t1" not in run.substituted
    assert any(f.code == "segmenter_substituted" for f in run.flags)


def test_a_wrong_slot_set_retries_then_substitutes_the_whole_scope(hobby):
    faithful = _faithful(hobby["skeleton"])

    def respond(message, schema, n):
        r = faithful(message, schema, n)
        if "SCOPE: q2.ג" in message:
            return SegmenterResponse(entries=r.entries[:-1])        # one slot short
        return r
    llm = FakeLLM(respond)
    run = _run(segment_skeleton(hobby["skeleton"], llm, corpora=hobby["corpora"],
                                solutions=hobby["solutions"], cost_fn=lambda i, o, c: 0.0,
                                envelope_usd=2.0))
    scope_slots = [s.slot_id for t in hobby["skeleton"].terminals if t.scope == "q2.ג" for s in t.slots]
    assert set(run.substituted) == set(scope_slots)
    assert all(sid in run.wording for sid in scope_slots)


def test_an_unlicensed_equivalence_note_is_dropped_and_a_licensed_one_kept(hobby):
    sol = hobby["solutions"]["q1.ג"]
    licence = sol.strip().splitlines()[1].strip()          # a real line of the solution
    over = {"q1.ג.c3.k1": {"equivalence_note": "מותר גם לולאת while כי אין הגבלה"},
            "q1.ג.c4.k1": {"equivalence_note": f"מותר צורה זו כי הפתרון לדוגמה עושה «{licence}»"}}
    llm = FakeLLM(_faithful(hobby["skeleton"], over))
    run = _run(segment_skeleton(hobby["skeleton"], llm, corpora=hobby["corpora"],
                                solutions=hobby["solutions"], cost_fn=lambda i, o, c: 0.0,
                                envelope_usd=2.0))
    assert "q1.ג.c3.k1" in run.notes_dropped and run.wording["q1.ג.c3.k1"][2] is None
    assert run.wording["q1.ג.c4.k1"][2] and licence in run.wording["q1.ג.c4.k1"][2]
    assert not [c for c in run.calls if c.scope == "q1.ג" and c.attempt == 2], "a note is never a retry"


def test_the_envelope_stops_the_run_before_it_is_exceeded(hobby):
    llm = FakeLLM(_faithful(hobby["skeleton"]))
    with pytest.raises(EnvelopeExceeded):
        _run(segment_skeleton(hobby["skeleton"], llm, corpora=hobby["corpora"],
                              solutions=hobby["solutions"], cost_fn=lambda i, o, c: 1.5,
                              envelope_usd=2.0))
    assert len(llm.calls) == 2         # $1.5 after one call is under $2; the second reaches $3 → stop


def test_validate_entries_names_the_slot_and_the_rule():
    slots = [SimpleNamespace(slot_id="t.k1", kind="required", flags=())]
    corpus = "בדיקה אם המערך מלא, להחזיר false\nשורה שנייה של הרובריקה"
    lines = frozenset(l.replace(" ", "") for l in corpus.split("\n"))
    good = [SegmentedSlot(slot_id="t.k1", rubric_quote="בדיקה אם המערך מלא", description_he="המערך נבדק")]
    assert validate_entries(good, slots, corpus=corpus, corpus_lines=lines) == ([], {})
    bad = [SegmentedSlot(slot_id="t.k1", rubric_quote="טקסט שלא נאמר מעולם", description_he="2 נקודות על כך")]
    errs, _ = validate_entries(bad, slots, corpus=corpus, corpus_lines=lines)
    assert any(e.startswith("t.k1:") and "point value" in e for e in errs)
    assert any(e.startswith("t.k1:") and "verbatim" in e for e in errs)


# ── router ──────────────────────────────────────────────────────────────────

def _components_from_solution(solution: str, n: int) -> List[RoutedComponent]:
    lines = [l.strip() for l in solution.splitlines() if len(l.strip()) >= 12][:n]
    return [RoutedComponent(evidence_span=l, name_he=f"רכיב {i + 1}") for i, l in enumerate(lines)]


def test_routing_splits_the_monolith_on_the_half_lattice_and_keeps_tariffs(hobby):
    sk = hobby["skeleton"]
    t = sk.terminal("q2.א.c1")                       # P=10, routed, the UpdateRate reference
    assert t.routed and len(t.earn_slots) == 1
    comps = _components_from_solution(hobby["solutions"]["q2.א"], 4)
    new = apply_routing(t, comps, hobby["precision"])
    assert [s.points for s in new.earn_slots] == [D("2.5")] * 4
    assert sum(s.points for s in new.earn_slots) == D(10) and not new.routed
    assert all("routed_component" in s.flags for s in new.earn_slots)
    # a 5-point monolith over 3 components: 2 / 1.5 / 1.5 (OD-22 lattice, residual first)
    t0 = sk.terminal("q2.א.c0")
    new0 = apply_routing(t0, _components_from_solution(hobby["solutions"]["q2.א"], 3), hobby["precision"])
    assert [s.points for s in new0.earn_slots] == [D(2), D("1.5"), D("1.5")]
    # tariffs survive routing
    t3 = sk.terminal("q2.ב.c3.s3")
    new3 = apply_routing(t3, _components_from_solution(hobby["solutions"]["q2.ב"], 2), hobby["precision"])
    assert len(new3.tariff_slots) == 1 and [s.points for s in new3.earn_slots] == [D("2.5"), D("2.5")]


def test_route_monoliths_retries_once_and_keeps_the_monolith_on_failure(hobby):
    sk = hobby["skeleton"]
    routed = [t for t in sk.terminals if t.routed]

    def respond(message, schema, n):
        tid = message.splitlines()[0].split("TERMINAL: ")[1]
        scope = sk.terminal(tid).scope
        if tid == "q1.א.c1":                                    # never grounded → fails twice
            return RouterResponse(components=[RoutedComponent(evidence_span="טקסט בדוי לגמרי", name_he="א"),
                                              RoutedComponent(evidence_span="עוד טקסט בדוי", name_he="ב")])
        return RouterResponse(components=_components_from_solution(hobby["solutions"][scope], 3))
    llm = FakeLLM(respond)
    run = _run(route_monoliths(sk, llm, corpora=hobby["corpora"], solutions=hobby["solutions"],
                               questions=hobby["questions"], cost_fn=lambda i, o, c: 0.01,
                               envelope_usd=1.0))
    assert run.failed == ["q1.א.c1"]
    assert [c.attempt for c in run.calls if c.terminal_id == "q1.א.c1"] == [1, 2]
    kept = run.skeleton.terminal("q1.א.c1")
    assert kept.routed and len(kept.earn_slots) == 1
    for t in routed:
        if t.terminal_id != "q1.א.c1":
            nt = run.skeleton.terminal(t.terminal_id)
            assert not nt.routed and len(nt.earn_slots) == 3
            assert sum(s.points for s in nt.earn_slots) == t.points_possible
    assert abs(run.cost_usd - 0.01 * len(run.calls)) < 1e-9
    # the rest of the skeleton is untouched
    assert run.skeleton.terminal("q1.ב.c3") == sk.terminal("q1.ב.c3")


def test_the_routed_skeleton_segments_and_validates_end_to_end(hobby):
    sk = hobby["skeleton"]

    def respond_route(message, schema, n):
        tid = message.splitlines()[0].split("TERMINAL: ")[1]
        return RouterResponse(components=_components_from_solution(hobby["solutions"][sk.terminal(tid).scope], 3))
    rr = _run(route_monoliths(sk, FakeLLM(respond_route), corpora=hobby["corpora"],
                              solutions=hobby["solutions"], questions=hobby["questions"],
                              cost_fn=lambda i, o, c: 0.0, envelope_usd=1.0))
    sr = _run(segment_skeleton(rr.skeleton, FakeLLM(_faithful(rr.skeleton)), corpora=hobby["corpora"],
                               solutions=hobby["solutions"], cost_fn=lambda i, o, c: 0.0, envelope_usd=2.0))
    plan = assemble_plan(rr.skeleton, sr.wording, segmenter_prompt_version="segmenter/v1",
                         segmenter_model="fake-haiku", router_model="fake-sonnet")
    assert plan.router_model == "fake-sonnet"
    errors = validate_plan(plan, contract_terminal_points=hobby["points"], terminal_scopes=hobby["scopes"],
                           precision=hobby["precision"], scope_corpora=hobby["corpora"])
    assert errors == [], errors
    assert len(plan.terminal("q2.א.c1").checks) == 3
