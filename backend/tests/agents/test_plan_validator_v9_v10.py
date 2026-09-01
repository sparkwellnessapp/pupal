"""
V9 (rubric-quote grounding) and V10 (point-blindness).

Both rules were CALIBRATED against the ratified hand plan, not derived from
first principles — and the first-principles versions were wrong:

  · "rubric_quote must be a verbatim span of the criterion text" rejected 46 of
    the hand plan's 80 checks. Real authoring elides with «…», joins with an
    em-dash, silently fixes typos in the teacher's source, and cites the whole
    contract (question spec, example solution) rather than one criterion.
  · "description_he may not contain digits" flagged 24, every one a false
    positive — «אתחול ב-0» is code talk, not an answer key.

The calibrated rules ground 73/80 of the hand plan, and the ungrounded
remainder is dominated by its `ruling`-sourced checks, which V9 exempts by
design. That is the point: V9 mechanically separates the generated layer from
the durable ruling layer.
"""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal
from pathlib import Path

import pytest

from app.agents.grader.plan_schemas import GradingPlan
from app.agents.grader.plan_validator import quote_is_grounded, validate_plan

PLAN = Path("app/agents/grader/plans/hobby_tvshow.plan.json")


def _tight(t):
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", t or ""))


def _corpus() -> str:
    """Everything the teacher wrote, anywhere on the path."""
    from tests.grading_eval_suite.fixtures import load_bundle

    parts = []

    def collect(node):
        for attr in ("question_text", "text", "title", "example_solution",
                     "description", "evaluation_guidance", "notes"):
            value = getattr(node, attr, None)
            if isinstance(value, str):
                parts.append(value)
        for attr in ("trace_tables", "context_tables"):
            value = getattr(node, attr, None)
            if value:
                parts.append(json.dumps(value, ensure_ascii=False))
        for c in getattr(node, "criteria", []) or []:
            collect(c)
            for sc in (getattr(c, "sub_criteria", None) or []):
                collect(sc)
        for s in getattr(node, "sub_questions", []) or []:
            collect(s)

    for q in load_bundle("dan_basiuk").rubric_contract.questions:
        collect(q)
    return " ".join(parts)


# ---------------------------------------------------------------------------
# V9
# ---------------------------------------------------------------------------

def test_v9_accepts_an_elided_quote():
    """«יצירת 2 מונה … + אתחולם» — authors elide. Requiring one verbatim span
    would reject the ratified plan's own convention."""
    corpus = _tight("יצירת 2 מונה לחוגים ספורטיביים ולא ספורטיביים + אתחולם באפס")
    assert quote_is_grounded("יצירת 2 מונה … + אתחולם", corpus)


def test_v9_survives_a_typo_in_the_teachers_source():
    """The real contract contains «countHobbiesאו» with the space missing. An
    honest citation that puts the space back must not read as hallucinated."""
    corpus = _tight("לולאה מ-0 עד countHobbiesאו עד hobbies.length")
    assert quote_is_grounded("עד countHobbies או עד hobbies.length", corpus)


def test_v9_rejects_an_invented_quote():
    """The rule still has to catch the thing it exists for."""
    corpus = _tight("סעיף א: כותרת ותכונות המחלקה Hobby")
    assert not quote_is_grounded("המחלקה חייבת לממש ממשק IComparable", corpus)


def test_v9_rejects_a_fragment_too_short_to_mean_anything():
    assert not quote_is_grounded("…", _tight("any corpus at all"))
    assert not quote_is_grounded("", _tight("any corpus at all"))


def test_v9_exempts_ruling_sourced_checks():
    """A `ruling` check cites a RULING, not rubric text. Grounding it is not
    merely wrong, it is impossible — and the hand plan has exactly two."""
    from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan

    ruling = PlanCheck(check_id="t.k1", description_he="x", kind="required",
                       points=Decimal("1"), source="ruling",
                       rubric_quote="Owner-ruled −1 (GT note, dan)")
    errs = validate_plan(
        GradingPlan(plan_version="p", exam_id="e", rubric_contract_sha256="h",
                    terminals=[TerminalPlan(terminal_id="t",
                                            points_possible=Decimal("1"),
                                            checks=[ruling])]),
        contract_terminal_points={"t": Decimal("1")},
        terminal_scopes={"t": "q1"}, precision=Decimal("0.25"),
        scope_corpora={"q1": "nothing resembling that quote"})
    assert not [e for e in errs if e.startswith("V9")], errs


# ---------------------------------------------------------------------------
# V10
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,flagged", [
    ("אתחול ב-0", False),                       # code talk, not points
    ("מונה לחוגים הספורטיביים + אתחול ב-0", False),
    ("[PL-10/AUDIT-3] השמה ליעד שאינו מוכרז", False),   # a ruling tag has digits
    ("להוריד 2 נקודות אם לא בדקו", True),
    ("שווה 3 נקודות", True),
])
def test_v10_flags_point_text_and_not_bare_digits(text, flagged):
    from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan

    check = PlanCheck(check_id="t.k1", description_he=text, kind="required",
                      points=Decimal("1"), rubric_quote="q")
    errs = validate_plan(
        GradingPlan(plan_version="p", exam_id="e", rubric_contract_sha256="h",
                    terminals=[TerminalPlan(terminal_id="t",
                                            points_possible=Decimal("1"),
                                            checks=[check])]),
        contract_terminal_points={"t": Decimal("1")},
        terminal_scopes={"t": "q1"}, precision=Decimal("0.25"))
    assert bool([e for e in errs if e.startswith("V10")]) is flagged, errs


# ---------------------------------------------------------------------------
# the reference artifact
# ---------------------------------------------------------------------------

def test_the_ratified_plan_is_point_blind():
    """V10 admits zero exceptions on the reference plan. If this ever fails,
    the rule drifted — not the plan."""
    plan = GradingPlan.model_validate_json(PLAN.read_text(encoding="utf-8"))
    from app.agents.grader.plan_validator import _POINT_TEXT

    offenders = [c.check_id for t in plan.terminals for c in t.checks
                 if _POINT_TEXT.search(c.description_he or "")]
    assert not offenders, offenders


def test_v9_grounds_the_bulk_of_the_ratified_plan():
    """73 of 80 at calibration. Pinned as a floor so a change to the matching
    rule that quietly loosens or tightens it shows up here.

    The remainder is the layer-1 residue: owner rulings and authorial
    normalisations of the teacher's text.
    """
    plan = GradingPlan.model_validate_json(PLAN.read_text(encoding="utf-8"))
    corpus = _tight(_corpus())
    grounded = sum(1 for t in plan.terminals for c in t.checks
                   if quote_is_grounded(c.rubric_quote or "", corpus))
    total = sum(len(t.checks) for t in plan.terminals)
    assert total == 80
    assert grounded >= 73, f"only {grounded}/{total} grounded — the rule tightened"
