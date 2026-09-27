"""CWV-5 NoMachineVocabulary — grading annotation copy.

No teacher-facing grading string names a plan/check id or speaks of «המודל».
Two halves: a STATIC scan of every Hebrew string literal in the grader package
(so a new constructor cannot slip past), and DYNAMIC renders of the constructors
this PR touches, fed Hebrew ids, asserting no internal id leaks into the text.
"""
from __future__ import annotations

import ast
import re
from decimal import Decimal
from pathlib import Path

from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan
from app.agents.grader.pricer import price_scope

GRADER = Path(__file__).resolve().parents[2] / "app" / "agents" / "grader"
MACHINE = re.compile(r"מודל")                    # «המודל», «מהמודל», «מודל החזיר»
INTERNAL_ID = re.compile(r"\bq\d+\.")


def _hebrew_literals(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                                    ast.ClassDef))
                  and n.body and isinstance(n.body[0], ast.Expr)
                  and isinstance(n.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                and id(node) not in docstrings and re.search(r"[א-ת]", node.value)):
            yield node.lineno, node.value


def test_no_grader_string_speaks_of_the_model():
    offenders = [f"{p.name}:{line}: {text[:60]}"
                 for p in sorted(GRADER.glob("*.py"))
                 for line, text in _hebrew_literals(p) if MACHINE.search(text)]
    assert offenders == []


def test_the_closed_world_annotation_names_no_id():
    from app.agents.grader.validator import strip_out_of_world
    _kept, _flags, annotations = strip_out_of_world(
        ["q1.a.1.c0.k1"], key=lambda i: i, known={"q1.א.1.c0.k1"}, scope_id="q1.א.1")
    for a in annotations:
        assert not INTERNAL_ID.search(a.message) and not MACHINE.search(a.message)


def test_the_no_verdict_check_speaks_her_language():
    plan = [TerminalPlan(terminal_id="q1.א.1.c0", points_possible=Decimal("12"),
                         checks=[PlanCheck(check_id="q1.א.1.c0.k1",
                                           description_he="כל התאים נכונים",
                                           kind="required", points=Decimal("12"))])]
    priced = price_scope(plan, {}, Decimal("0.25"))["q1.א.1.c0"]
    texts = [a.message for a in priced.annotations] + [c.basis_he for c in priced.checks]
    for text in texts:
        assert not INTERNAL_ID.search(text) and not MACHINE.search(text), text
