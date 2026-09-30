"""Stage 1 → planner input, and the exact inverse of the amount mask (§5.2, D-LAW-2);
the AM-G17 aliases every planner payload is addressed by."""
from __future__ import annotations

import re
from decimal import Decimal as D

import pytest

from app.agents.grader.payload_aliases import ALIAS_PATTERN, AliasTable
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6
from app.agents.planner.examples import FEW_SHOTS
from app.agents.planner.inputs import AMOUNT_MASK
from app.agents.planner.planner import plan_scope
from app.agents.planner.prompt import planner_system_prompt, render_scope_input
from app.agents.planner.stage1_input import planner_aliases, scope_planner_input, unmask_span
from app.subjects import get_profile
from tests.grading_eval_suite.fixtures import load_bundle

EXAMS = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}


@pytest.fixture(scope="module")
def stage1():
    return {e: compile_stage1_v6(load_bundle(f, require_gt=False).rubric_contract, exam_id=e,
                                 rubric_contract_sha256="x") for e, f in EXAMS.items()}


@pytest.mark.parametrize("exam", sorted(EXAMS))
def test_every_scope_of_both_exams_renders_without_its_marker_amounts(stage1, exam):
    for scope in stage1[exam].scopes:
        inp = scope_planner_input(scope)
        text = render_scope_input(inp)
        for m in inp.markers:
            assert m.text_span in text
        for m in scope.markers:
            # the marker's own span reaches the planner only masked
            if m.amount is not None and any(ch.isdigit() for ch in m.text_span):
                assert m.text_span not in text or AMOUNT_MASK in m.text_span


# the rendered positions an id occupies (prompt.render_scope_input)
_ID_LISTS = re.compile(r"^(?:terminal_id \([^)]*\)|marker_id): (.*)$", re.M)
_COMPONENT_LINE = re.compile(r"^  (\S+): (.*?) \[(?:monolith|fixed)\](?: · for a split: (.*))?$", re.M)
_TERMINAL_HEAD = re.compile(r"^=== TERMINAL (\S+) · ", re.M)
_COMPONENT = re.compile(r"^  (\S+) \[(?:fixed|monolith)\]: «", re.M)
_MARKER = re.compile(r"^  (\S+) \[(?:deduct|no_deduct)\] written in (\S+) · candidate anchors: (.*)$", re.M)
_NOTE = re.compile(r"^  (\S+): «", re.M)


def _rendered_ids(text: str) -> list:
    ids = []
    for m in _ID_LISTS.finditer(text):
        ids += [] if m.group(1) == "none" else m.group(1).split(", ")
    for m in _COMPONENT_LINE.finditer(text):
        ids += [m.group(1)] + m.group(2).split(", ") + (m.group(3).split(", ") if m.group(3) else [])
    ids += _TERMINAL_HEAD.findall(text) + _COMPONENT.findall(text)
    for m in _MARKER.finditer(text):
        ids += [m.group(1), m.group(2)] + m.group(3).split(", ")
    notes = text.split("=== NOTE CHECKS (compiled, read-only) ===")
    if len(notes) > 1:
        ids += _NOTE.findall(notes[1].split("\n\n")[0])
    return ids


def _real_ids(scope) -> list:
    return ([t.terminal_id for t in scope.terminals]
            + [c.component_id for t in scope.terminals for c in t.components]
            + [m.marker_id for m in scope.markers])


def _fresh_scope_id(scope, text) -> bool:
    return not re.search(rf"(?<![\w.]){re.escape(scope.scope)}(?![\w.])", text)


async def test_payload_ids_are_ascii_aliases(stage1):
    """[AM-G17] Every id a planner payload shows is a call-scoped ASCII alias
    (^[a-z]\\d+$). No real id reaches the model: not in the first call, not in the
    few-shots, not in the ONE repair call's validator messages."""
    for exam, s1 in stage1.items():
        for scope in s1.scopes:
            text = render_scope_input(scope_planner_input(scope))
            ids = _rendered_ids(text)
            assert ids, (exam, scope.scope)
            bad = [i for i in ids if not ALIAS_PATTERN.fullmatch(i)]
            assert not bad, (exam, scope.scope, bad)
            leaked = [r for r in _real_ids(scope) if r in text]
            assert not leaked, (exam, scope.scope, leaked)
            assert "=== SCOPE ===" in text and f"=== SCOPE {scope.scope}" not in text

    system = planner_system_prompt(get_profile("computer_science"))
    for ex in FEW_SHOTS:
        out = ex.output
        ids = ([t.terminal_id for t in out.terminals]
               + [c.component_ref for t in out.terminals for c in t.credits]
               + [x for f in out.faults for x in (f.anchor_terminal_id, f.requires_component_ref,
                                                   *(o.marker_id for o in f.options)) if x]
               + [x for d in out.dispositions for x in (d.marker_id, d.merged_into_marker_id) if x])
        assert all(ALIAS_PATTERN.fullmatch(i) for i in ids), (ex.title, ids)
        assert all(ALIAS_PATTERN.fullmatch(i) for i in _rendered_ids(render_scope_input(ex.input)))
    assert not re.search(r"\bq\d+\.[\w.]+", system)             # no real-shaped id in the system prompt

    # the repair call: the validator's messages name real ids; the model reads aliases
    scope = stage1["hobby_tvshow"].scope("q1.ג")
    fixed = next(t for t in scope.terminals if t.fixed)
    from app.agents.planner.schemas import PlannedCredit, PlannedTerminal, ScopePlanOutput
    wrong = ScopePlanOutput(terminals=[PlannedTerminal(
        terminal_id=planner_aliases(scope).alias(fixed.terminal_id), decomposition="split",
        credits=[PlannedCredit(component_ref=r, description_he="x", source_span="x",
                               full_label_he="x", absent_label_he="x") for r in ("n1", "n2")])])
    seen = []

    async def call(system_, user_):
        seen.append(user_)
        return wrong, {}

    r = await plan_scope(scope, precision=D("0.25"), system_prompt="S",
                         user_message=render_scope_input(scope_planner_input(scope)), call=call)
    assert r.origin == "fallback" and len(seen) == 2
    assert any(t.terminal_id in e for e in r.errors for t in scope.terminals)   # not vacuous
    leaked = [x for x in _real_ids(scope) if x in seen[1]]
    assert not leaked and _fresh_scope_id(scope, seen[1]), leaked


def test_the_alias_table_is_pure_and_its_redaction_is_exact():
    ids = ["q1.א.c1", "q1.א.c10", "q1.א.c1.k1"]
    t1 = AliasTable((("t", ids[:2]), ("k", ids[2:])), named={"q1.א": "this scope"})
    t2 = AliasTable((("t", ids[:2]), ("k", ids[2:])), named={"q1.א": "this scope"})
    assert [t1.alias(i) for i in ids] == [t2.alias(i) for i in ids] == ["t1", "t2", "k1"]
    assert t1.real("t2") == "q1.א.c10" and t1.real("t9") is None and t1.real(None) is None
    msg = "q1.א.c10: bad; q1.א.c1.k1 and q1.א.c1.c2 in q1.א (not q1.אב, not xq1.א.c1)"
    assert t1.redact(msg) == "t2: bad; k1 and t1.c2 in this scope (not q1.אב, not xq1.א.c1)"
    with pytest.raises(ValueError):
        AliasTable((("t", ["a"]), ("k", ["a"])))


def test_unmask_span_is_the_exact_inverse_of_the_mask():
    teacher = "אם לא בדקו null להוריד 2 ; אם רצו עד length להוריד 1"
    assert unmask_span(f"אם לא בדקו null להוריד {AMOUNT_MASK}", [teacher]) == "אם לא בדקו null להוריד 2"
    assert unmask_span("אין מסכה כאן", [teacher]) == "אין מסכה כאן"
    assert unmask_span(f"להוריד {AMOUNT_MASK}", [teacher]) is None          # ambiguous: two matches
    assert unmask_span(f"משפט שלא קיים {AMOUNT_MASK}", [teacher]) is None
