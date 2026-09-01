"""
Plan generation — the structural guarantees, with no provider calls.

These pin the things that must be true regardless of what any model returns:
the terminal set is derived, ids are minted here, and RULING 1's
"the generator may only emit `generated`" is structural rather than checked.
"""
from __future__ import annotations

from decimal import Decimal

import pytest


def _contract():
    from tests.grading_eval_suite.fixtures import load_bundle
    return load_bundle("dan_basiuk").rubric_contract


# ---------------------------------------------------------------------------
# RULING 1 — generator-cannot-self-label-a-check-as-ruling
# ---------------------------------------------------------------------------

def test_generator_cannot_self_label_a_check_as_ruling():
    """Structural, not policed: `GeneratedCheck` has no `source` field, so the
    model cannot claim one. Without this V9 would be voluntary — anything the
    model failed to ground it would simply relabel."""
    from app.agents.plan_gen.schemas import GeneratedCheck

    assert "source" not in GeneratedCheck.model_fields

    # and pydantic must not quietly accept it as an extra
    check = GeneratedCheck(rubric_quote="x" * 20, description_he="d",
                           kind="required", points=Decimal("1"),
                           source="ruling")            # type: ignore[call-arg]
    assert getattr(check, "source", None) != "ruling"


def test_raw_json_claiming_a_ruling_is_rejected():
    """The second door: a draft assembled from JSON rather than the typed
    output. Silently rewriting it to "generated" would hide a model trying to
    exempt itself from grounding."""
    from app.agents.plan_gen.schemas import (
        SelfLabelledCheckError, reject_self_labelled)

    reject_self_labelled({"terminals": [{"checks": [{"check_id": "a",
                                                     "source": "generated"}]}]})
    with pytest.raises(SelfLabelledCheckError):
        reject_self_labelled({"terminals": [{"checks": [{"check_id": "a.k1",
                                                         "source": "ruling"}]}]})


def test_minted_checks_are_always_generated():
    from app.agents.plan_gen.generator import _to_plan_checks
    from app.agents.plan_gen.schemas import GeneratedCheck, GeneratedTerminal

    term = GeneratedTerminal(
        terminal_id="q1.א.c0", points_possible=Decimal("4"),
        checks=[GeneratedCheck(rubric_quote="q" * 20, description_he="a",
                               kind="required", points=Decimal("4"))])
    checks = _to_plan_checks("q1.א.c0", term)
    assert [c.source for c in checks] == ["generated"]
    assert [c.check_id for c in checks] == ["q1.א.c0.k1"], "ids are minted here"


# ---------------------------------------------------------------------------
# the terminal set is DERIVED
# ---------------------------------------------------------------------------

def test_scopes_are_leaves_and_terminals_match_the_contract():
    """The generator must not be able to invent structure (V6). Its scope list
    and terminal set are pure functions of the contract, and must agree with
    what the gradable compiler produces."""
    from app.agents.plan_gen.generator import contract_scopes, terminals_of
    from tests.grading_eval_suite.fixtures import load_bundle

    bundle = load_bundle("dan_basiuk")
    scopes = contract_scopes(bundle.rubric_contract)

    assert [k for k, _, _ in scopes] == [
        (s.question_id, s.sub_question_id) for s in bundle.gradable_test.scopes]

    derived = {tid for _, q, sub in scopes for tid, _ in terminals_of(sub or q)}
    assert derived == set(bundle.terminal_infos), (
        "the derived terminal set disagrees with the contract's")
    assert len(derived) == 38


def test_derived_points_match_the_contract_exactly():
    from app.agents.plan_gen.generator import contract_scopes, terminals_of
    from tests.grading_eval_suite.fixtures import load_bundle

    bundle = load_bundle("dan_basiuk")
    for _, q, sub in contract_scopes(bundle.rubric_contract):
        for tid, points in terminals_of(sub or q):
            assert points == bundle.terminal_infos[tid].points, tid


# ---------------------------------------------------------------------------
# the corpus the model sees IS the corpus V9 checks against
# ---------------------------------------------------------------------------

def test_the_model_sees_exactly_what_v9_will_check_against():
    """If the model were shown text the validator cannot see, an ungrounded
    quote would be an artefact of the harness rather than a real failure."""
    from app.agents.plan_gen.prompt import scope_corpus
    from tests.grading_eval_suite.fixtures import load_bundle

    contract = load_bundle("dan_basiuk").rubric_contract
    q1 = contract.questions[0]
    corpus = scope_corpus(q1, q1.sub_questions[0])
    assert "כותרת ותכונות המחלקה Hobby" in corpus
    assert q1.sub_questions[0].example_solution in corpus


def test_nosol_variant_strips_every_example_solution():
    """V-nosol measures whether v5 can ship to a teacher whose rubric has no
    embedded solution — which is all six production rubrics today."""
    from app.agents.plan_gen.prompt import scope_corpus
    from tests.grading_eval_suite.fixtures import load_bundle

    contract = load_bundle("dan_basiuk").rubric_contract
    q1 = contract.questions[0]
    sub = q1.sub_questions[0]
    stripped = scope_corpus(q1, sub, include_solution=False)
    assert sub.example_solution, "fixture precondition: this scope HAS a solution"
    assert sub.example_solution not in stripped
    assert "כותרת ותכונות המחלקה Hobby" in stripped, "criterion text must survive"
