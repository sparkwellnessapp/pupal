"""D-13 — the router's string payload, decoded exactly once, on RECORDED Sonnet 5
outputs (tests/fixtures/router_sonnet5_recorded.json: the raw tool-call args of the 10
monoliths that failed routing in the 2026-09-28 rebuild; every one carries
`components` as a JSON string). No provider is called: a fake model replays them."""
from __future__ import annotations

import json
import logging
from dataclasses import replace
from pathlib import Path

import pytest
from langchain_core.messages import AIMessage

from app.agents.plan_compiler.route import (RouterResponse, decode_string_payload,
                                            route_monoliths, validate_components)
from tests.grading_eval_suite.tools.compile_plan import discover_exams
from tests.grading_eval_suite.tools.segment_plan import _compile, _scope_maps

RECORDED = json.loads((Path(__file__).resolve().parents[1] / "fixtures" /
                       "router_sonnet5_recorded.json").read_text(encoding="utf-8"))["records"]


def _result(args, parsed=None, error="components: Input should be a valid list"):
    raw = AIMessage(content="", tool_calls=[{"name": "RouterResponse", "args": args, "id": "t1"}],
                    usage_metadata={"input_tokens": 10, "output_tokens": 10, "total_tokens": 20})
    return {"raw": raw, "parsed": parsed, "parsing_error": ValueError(error) if error else None}


@pytest.mark.parametrize("rec", RECORDED, ids=[r["terminal_id"] for r in RECORDED])
def test_the_recorded_string_payload_decodes_exactly_once(rec):
    assert rec["kind"] == "components_is_string" and not rec["parsed_ok"]
    got = decode_string_payload(_result(rec["tool_call_args"]))
    assert isinstance(got, RouterResponse) and len(got.components) >= 1
    assert all(c.evidence_span and c.name_he for c in got.components)


@pytest.mark.parametrize("value", [
    "not json at all",
    json.dumps(json.dumps({"components": []})),                 # a string inside the string: twice ≠ once
    json.dumps({"components": [], "extra": 1}),                 # not the expected object
    json.dumps({"parts": []}),
    json.dumps([{"name_he": "חסר שדה"}]),                       # a component missing its evidence
])
def test_anything_else_stays_a_routing_failure(value):
    assert decode_string_payload(_result({"components": value})) is None


def test_a_parsed_list_or_a_missing_tool_call_is_not_decoded():
    assert decode_string_payload(_result({"components": []})) is None
    no_call = {"raw": AIMessage(content="x"), "parsed": None, "parsing_error": ValueError("x")}
    assert decode_string_payload(no_call) is None


class _Replay:
    def __init__(self, results):
        self.results = list(results)

    def with_structured_output(self, schema, include_raw=True):
        return self

    async def ainvoke(self, messages):
        return self.results.pop(0)


@pytest.mark.parametrize("exam", ["bagrut_899371", "hobby_tvshow"])
async def test_route_monoliths_routes_the_recorded_outputs(exam):
    """The real router loop, fed the recorded payloads: nothing is 'unparseable'
    any more; a monolith fails only where its evidence genuinely does not ground."""
    exams = discover_exams()
    contract, skeleton = _compile(exam, exams[exam])
    corpora, solutions, questions = _scope_maps(contract)
    for rec in (r for r in RECORDED if r["exam"] == exam):
        only = replace(skeleton, terminals=tuple(
            replace(t, routed=(t.terminal_id == rec["terminal_id"])) for t in skeleton.terminals))
        replay = _Replay([_result(rec["tool_call_args"])] * 2)
        run = await route_monoliths(only, replay, corpora=corpora, solutions=solutions,
                                    questions=questions, cost_fn=lambda i, o, c: 0.0,
                                    envelope_usd=1.0)
        assert rec["terminal_id"] in run.decoded
        assert not any("unparseable" in e for call in run.calls for e in call.errors), rec["terminal_id"]
        comps = decode_string_payload(_result(rec["tool_call_args"])).components
        grounded = not validate_components(comps, corpus=corpora[rec["scope"]])
        assert (rec["terminal_id"] not in run.failed) is grounded, rec["terminal_id"]


async def test_a_failed_route_logs_a_warning_with_its_ids(caplog):
    exams = discover_exams()
    contract, skeleton = _compile("hobby_tvshow", exams["hobby_tvshow"])
    corpora, solutions, questions = _scope_maps(contract)
    tid = next(t.terminal_id for t in skeleton.terminals if t.routed)
    scope = skeleton.terminal(tid).scope
    only = replace(skeleton, terminals=tuple(replace(t, routed=(t.terminal_id == tid))
                                             for t in skeleton.terminals))
    garbage = _result({"components": "not json"})
    with caplog.at_level(logging.WARNING, logger="app.agents.plan_compiler.route"):
        run = await route_monoliths(only, _Replay([garbage, garbage]), corpora=corpora,
                                    solutions=solutions, questions=questions,
                                    cost_fn=lambda i, o, c: 0.0, envelope_usd=1.0)
    assert run.failed == [tid]
    assert any(r.levelno == logging.WARNING and f"route_failed scope={scope} terminal={tid}" in r.getMessage()
               for r in caplog.records)
