"""
PLAN COMPILER v2 — Stage 0 (derive) guards, with no provider calls.

Carried over from `test_plan_gen_structure.py` when the Opus decomposer was
retired (R-4): the scope list and the terminal set are pure functions of the
contract and must agree with what the gradable compiler produces (V6), and the
scope corpus is exactly what V9 checks against. The generator's RULING-1 tests
(`GeneratedCheck` has no `source`) retired with the generator — the compiler
has no model output type to self-label.
"""
from __future__ import annotations


def _bundle():
    from tests.grading_eval_suite.fixtures import load_bundle
    return load_bundle("dan_basiuk")


# ---------------------------------------------------------------------------
# the terminal set is DERIVED
# ---------------------------------------------------------------------------

def test_scopes_are_leaves_and_terminals_match_the_contract():
    """The compiler must not be able to invent structure (V6). Its scope list
    and terminal set are pure functions of the contract, and must agree with
    what the gradable compiler produces."""
    from app.agents.plan_compiler.stage0 import contract_scopes, terminals_of

    bundle = _bundle()
    scopes = contract_scopes(bundle.rubric_contract)

    assert [k for k, _, _ in scopes] == [
        (s.question_id, s.sub_question_id) for s in bundle.gradable_test.scopes]

    derived = {tid for _, q, sub in scopes for tid, _ in terminals_of(sub or q)}
    assert derived == set(bundle.terminal_infos), (
        "the derived terminal set disagrees with the contract's")
    assert len(derived) == 38


def test_derived_points_match_the_contract_exactly():
    from app.agents.plan_compiler.stage0 import contract_scopes, terminals_of

    bundle = _bundle()
    for _, q, sub in contract_scopes(bundle.rubric_contract):
        for tid, points in terminals_of(sub or q):
            assert points == bundle.terminal_infos[tid].points, tid


def test_depth_2_scopes_carry_the_full_path_and_never_collide():
    """R-1 (ratified): bagrut's q1.א and q1.ב both have children `1` and `2`;
    the scope key is the FULL path, so four leaves are four keys."""
    from app.agents.plan_compiler.stage0 import contract_scopes, scope_label
    from tests.grading_eval_suite.fixtures import load_bundle

    bundle = load_bundle("bagrut_899371.din_ezra", require_gt=False)
    keys = [k for k, _, _ in contract_scopes(bundle.rubric_contract)]
    labels = [scope_label(k) for k in keys]
    assert len(labels) == len(set(labels)), labels
    assert {"q1.א.1", "q1.א.2", "q1.ב.1", "q1.ב.2"} <= set(labels)
    assert labels == [f"{s.question_id}.{s.sub_question_id}" if s.sub_question_id else s.question_id
                      for s in bundle.gradable_test.scopes]


# ---------------------------------------------------------------------------
# the corpus the compiler quotes from IS the corpus V9 checks against
# ---------------------------------------------------------------------------

def test_the_corpus_is_exactly_what_v9_will_check_against():
    from app.agents.plan_gen.prompt import scope_corpus

    contract = _bundle().rubric_contract
    q1 = contract.questions[0]
    corpus = scope_corpus(q1, q1.sub_questions[0])
    assert "כותרת ותכונות המחלקה Hobby" in corpus
    assert q1.sub_questions[0].example_solution in corpus


def test_nosol_variant_strips_every_example_solution():
    """V-nosol measures whether v5 can ship to a teacher whose rubric has no
    embedded solution — which is all six production rubrics today."""
    from app.agents.plan_gen.prompt import scope_corpus

    contract = _bundle().rubric_contract
    q1 = contract.questions[0]
    sub = q1.sub_questions[0]
    stripped = scope_corpus(q1, sub, include_solution=False)
    assert sub.example_solution, "fixture precondition: this scope HAS a solution"
    assert sub.example_solution not in stripped
    assert "כותרת ותכונות המחלקה Hobby" in stripped, "criterion text must survive"
