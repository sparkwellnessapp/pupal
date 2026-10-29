r"""QM-1 — a math subject's quote is matched in the math match form. Pure, zero network.

The defect: the verifier quotes «the SHORTEST verbatim span», which in a math answer is a
piece of a formula (`2\ln x - 1 = 0` out of `\(f'(x)=0 \Rightarrow 2\ln x - 1 = 0\)`). The
old check canonicalised the answer's spans and left the fragment raw, so the student's own
marks came back NOT_FOUND and the pricer refused the credit.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.grader.validator import quote_match_status
from app.schemas.ontology_types import QuoteValidationStatus
from app.services.math_notation.quote_match import match_form, match_form_at

VECTORS_PATH = Path(__file__).parents[1] / "fixtures" / "math_quote_match_vectors.json"
VECTORS = json.loads(VECTORS_PATH.read_text(encoding="utf-8"))


def test_the_vectors_are_what_the_generator_writes():
    """The client reads this file; it can only move with the implementation."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "gen", Path(__file__).parents[2] / "scripts" / "gen_math_quote_match_vectors.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    assert gen.build() == VECTORS, "run: python scripts/gen_math_quote_match_vectors.py"


@pytest.mark.parametrize("case", VECTORS["quotes"], ids=[c["name"] for c in VECTORS["quotes"]])
def test_a_quote_finds_the_students_marks_and_only_them(case):
    assert case["contained"] is case["expected"]
    status = quote_match_status(case["quote"], VECTORS["answer"], math_notation=True)
    if case["expected"]:
        assert status == QuoteValidationStatus.EXACT
    else:
        assert status != QuoteValidationStatus.EXACT


def test_the_bare_fragment_the_old_check_refused():
    answer = r"\(f(x) = 2x^2 + 1\)"
    assert quote_match_status("2x^2+1", answer) == QuoteValidationStatus.NOT_FOUND   # plain rule
    assert quote_match_status("2x^2+1", answer, math_notation=True) == QuoteValidationStatus.EXACT
    assert quote_match_status("x^2", answer, math_notation=True) == QuoteValidationStatus.EXACT


def test_without_the_flag_the_plain_rule_is_untouched():
    """A CS answer is never put through the math form — `\\(` is ordinary text in a regex."""
    answer = r'Pattern p = Pattern.compile("\\(\\d+\\)"); for (int i = 0; i < n; i++) {}'
    assert quote_match_status("i < n; i++", answer) == QuoteValidationStatus.EXACT
    assert quote_match_status("while (i <= n)", answer) == QuoteValidationStatus.NOT_FOUND
    assert quote_match_status(r'"\\(\\d+\\)"', answer) == QuoteValidationStatus.EXACT


def test_the_offsets_point_at_the_students_marks():
    text = r"נקודה \((\sqrt e, -2.25)\) ולכן"
    form, starts, ends = match_form_at(text)
    q = match_form(r"\sqrt{e}")
    at = form.index(q)
    assert text[starts[at]:ends[at + len(q) - 1]] == r"\sqrt e"


async def test_the_v6_grader_verifies_a_bare_fragment_under_mathematics_only():
    """End to end through the real grader: the scripted model quotes `2x^2+1` from
    `\\(f(x) = 2x^2 + 1\\)`. Under mathematics every claimed span verifies; under CS the
    plain rule is kept, byte for byte."""
    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.agents.grader.plan_schemas import GradingPlanV6
    from app.schemas.graded_test_draft_v6 import v6_content
    from app.subjects import get_profile
    from tests.agents.test_grader_v6 import MODEL, _Fake, _full
    from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle

    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    bundle = load_bundle("din_ezra", require_gt=False)
    answer = r"\(f(x) = 2x^2 + 1\)"
    test = bundle.gradable_test.model_copy(update={"scopes": [
        s.model_copy(update={"student_answer_text": answer}) for s in bundle.gradable_test.scopes]})

    for subject, expected in (("mathematics", {"exact"}), ("computer_science", {"not_found"})):
        grader = OptionsVerifyGrader(plan, bundle.rubric_contract, llm=_Fake(_full, quote="2x^2+1"),
                                     model_version=MODEL, profile=get_profile(subject))
        draft = await grader.grade(test)
        statuses = {r.quote_status for r in v6_content(draft).checks if r.quote_status}
        assert statuses == expected, subject
