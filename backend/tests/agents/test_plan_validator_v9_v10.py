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

# The ratified hand plan is the calibration artefact for V9/V10. It lives in the
# eval suite only: the production copy retired with the file-based pin
# (PLAN_production_wiring.md, OD-W7) — production plans live in grading_plans.
PLAN = Path("tests/grading_eval_suite/plans/hobby_tvshow.plan.json")


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


# ---------------------------------------------------------------------------
# V9 REFINEMENT — owner-ratified 2026-09-04, verified 113/113 by the reviewer.
#
# The anti-triviality guard (RULING 3) was written for PROSE and misfires on two
# shapes that are honest citations of the teacher's own text:
#   * a complete row of a solution TABLE, which normalises to <10 characters
#     («||F|5|1||» is 9) yet is a whole unit of what the teacher wrote;
#   * a quote containing a LITERAL dash from the rubric («… — 2 נק'»), which the
#     elision splitter cut into a 4-character fragment.
#
# Three clauses: whole-quote first; the ≥10 guard applies to FRAGMENTS and
# SUB-LINE spans only — a quote equal to an entire corpus line grounds
# regardless of length; and dashes are NOT elision markers (only … / ...).
# ---------------------------------------------------------------------------

SOLUTION_TABLE = "\n".join([
    "עקבו בעזרת טבלת מעקב אחר הפעולה",
    "|  | F | 8 | 0 | 6 |",
    "|  | F | 5 | 1 |  |",
    "|  | F | 4 | 2 |  |",
    "| T | T | 3 | 4 |  |",
])


def test_a_whole_table_row_grounds_even_though_it_is_short():
    """«||F|5|1||» is 9 non-whitespace characters — under the guard — but it is
    an ENTIRE line of the teacher's solution table, not a two-token fragment
    plucked from a block of prose. The guard exists to reject the latter."""
    from app.agents.grader.plan_validator import quote_is_grounded

    corpus = _tight(SOLUTION_TABLE)
    lines = frozenset(_tight(l) for l in SOLUTION_TABLE.splitlines() if _tight(l))
    for row in ("|  | F | 5 | 1 |  |", "|  | F | 4 | 2 |  |", "|  | F | 8 | 0 | 6 |"):
        assert quote_is_grounded(row, corpus, lines), (
            f"a complete solution-table row was rejected as a trivial citation: {row!r}")


def test_a_dash_in_the_rubric_is_not_an_elision_marker():
    """The teacher writes «הבנת הבדיקה — 2 נק'». Splitting on that dash left a
    4-character fragment and failed an honest verbatim quote."""
    from app.agents.grader.plan_validator import quote_is_grounded

    source = "הבנת הבדיקה של מחלק ללא שארית — 2 נק'"
    corpus = _tight(source)
    lines = frozenset([corpus])
    assert quote_is_grounded(source, corpus, lines), (
        "a verbatim quote containing a literal dash was split and rejected")


def test_the_guard_still_rejects_a_two_token_citation_into_a_solution_block():
    """The refinement must not open the hole the guard was written to close: a
    short SUB-LINE span inside a long block is still evidence of nothing."""
    from app.agents.grader.plan_validator import quote_is_grounded

    block = "הפעולה סורקת את המערך ומחזירה את הערך הגדול ביותר שנמצא בו"
    corpus = _tight(block)
    lines = frozenset([corpus])
    assert not quote_is_grounded("המערך", corpus, lines), (
        "a two-token sub-line citation grounded — the anti-triviality guard is gone")


def test_elision_still_splits_on_ellipsis_and_every_fragment_must_ground():
    from app.agents.grader.plan_validator import quote_is_grounded

    corpus = _tight("יצירת 2 מונה נוסף לספירה ואתחולם באפס בתחילת הפעולה")
    lines = frozenset([corpus])
    assert quote_is_grounded("יצירת 2 מונה נוסף … באפס בתחילת הפעולה", corpus, lines)
    assert not quote_is_grounded("יצירת 2 מונה נוסף … ממשק IComparable", corpus, lines), (
        "a quote whose second fragment is absent grounded anyway")


# ---------------------------------------------------------------------------
# The scope-label collision (found 2026-09-04, diagnosing 11 phantom V9 failures)
# ---------------------------------------------------------------------------

def test_scope_labels_are_unique_per_leaf_on_a_depth_2_exam():
    """`_scope_of` carried the leaf's OWN sub_question_id, not its full path.

    `bagrut_899371`'s q1 has two sub-questions (א, ב) whose children are BOTH
    named `1` and `2`, so four distinct leaves produced two labels. The
    corpus map is keyed by that label, so the second write won and q1.א's
    checks were grounded against q1.ב's text: 11 spurious V9 failures on a plan
    whose quotes were verbatim.

    Depth-1 exams cannot expose this, which is why hobby never did — so the
    guard has to be driven by the depth-2 exam.
    """
    from collections import Counter

    from app.agents.plan_compiler.stage0 import contract_scopes, scope_label as _scope_label
    from tests.grading_eval_suite.fixtures import load_bundle

    contract = load_bundle("bagrut_899371.din_ezra",
                           require_gt=False).rubric_contract
    labels = [_scope_label(k) for k, _, _ in contract_scopes(contract)]

    dupes = [lbl for lbl, n in Counter(labels).items() if n > 1]
    assert not dupes, (
        f"scope labels collide: {dupes}. Two leaves share a corpus key, so V9 "
        f"grounds one scope's quotes against another scope's text.")
    assert len(labels) == 13, f"expected 13 leaf scopes, got {len(labels)}"
    assert "q1.א.1" in labels and "q1.ב.1" in labels, (
        "the label is not the full path — the two branches are indistinguishable")


def test_a_scope_label_matches_its_terminals_prefix():
    """The label and the terminal ids must agree, because `terminal_scopes`
    maps one to the other and V9 looks the corpus up by it."""
    from app.agents.plan_compiler.stage0 import (
        contract_scopes, terminals_of, scope_label as _scope_label)
    from tests.grading_eval_suite.fixtures import load_bundle

    contract = load_bundle("bagrut_899371.din_ezra",
                           require_gt=False).rubric_contract
    for key, question, sub in contract_scopes(contract):
        label = _scope_label(key)
        for tid, _pts in terminals_of(sub or question):
            assert tid.startswith(label + "."), (
                f"terminal {tid} does not sit under its scope label {label!r}")
