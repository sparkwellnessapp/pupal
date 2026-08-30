"""
selection_expectation — the "choose k of N" review rule (pure, no mocks).

The rule cases live in tests/fixtures/selection_expectation_cases.json,
consumed IN PLACE by this file AND by the frontend mirror's test
(frontend/src/utils/selection-expectation.test.ts) — one ground truth.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.schemas.transcription import AnswerSpaceSelectionGroup
from app.services.selection_expectation import (
    answer_space_groups,
    expected_empty_keys,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "selection_expectation_cases.json"
CASES = json.loads(FIXTURE.read_text(encoding="utf-8"))["cases"]


# ---------------------------------------------------------------------------
# expected_empty_keys — fixture-driven (the cross-pinned rule)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_expected_empty_keys_fixture_case(case):
    groups = [AnswerSpaceSelectionGroup(**g) for g in case["groups"]]
    answers = [(q, sub, text) for q, sub, text in case["answers"]]
    got = expected_empty_keys(answers, groups)
    want = {(q, sub) for q, sub in case["expected_empty"]}
    assert got == want


# ---------------------------------------------------------------------------
# answer_space_groups — contract → answer-space translation
# ---------------------------------------------------------------------------

def _contract_json(question_ids: list[str], groups: list[dict]) -> dict:
    """Minimal contract dict: one direct criterion per question so the
    contract validates; points are irrelevant to this module."""
    # Point sums are the COMPILER's concern (INV-1..4 fire at compile time);
    # model_validate only checks shape, so a flat total is fine here.
    return {
        "rubric_id": "r1",
        "contract_version": "v-test",
        "subject": "computer_science",
        "numeric_policy": {},   # all-default NumericPolicy
        "total_points": str(Decimal(10) * len(question_ids)),
        "questions": [
            {
                "question_id": qid,
                "question_text": f"שאלה {qid}",
                "total_points": "10",
                "criteria": [{
                    "criterion_id": f"{qid}.c0",
                    "index": 0,
                    "description": "crit",
                    "points": "10",
                }],
            }
            for qid in question_ids
        ],
        "selection_groups": [
            {"group_id": f"sg{i}", **g} for i, g in enumerate(groups)
        ],
    }


def test_groups_map_qN_ids_to_numbers():
    cj = _contract_json(
        ["q1", "q2", "q3", "q4", "q5", "q6"],
        [{"choose_k": 2, "of_question_ids": ["q4", "q5", "q6"]}],
    )
    groups = answer_space_groups(cj)
    assert len(groups) == 1
    assert groups[0].choose_k == 2
    assert groups[0].question_numbers == [4, 5, 6]


def test_non_qN_ids_fall_back_to_position():
    # Same rule as gradable_compiler._q_num: non-'qN' id → array index + 1.
    cj = _contract_json(
        ["intro", "qB"],
        [{"choose_k": 1, "of_question_ids": ["intro", "qB"]}],
    )
    groups = answer_space_groups(cj)
    assert groups[0].question_numbers == [1, 2]


def test_dangling_member_id_is_dropped():
    cj = _contract_json(
        ["q1", "q2"],
        [{"choose_k": 1, "of_question_ids": ["q2", "q9"]}],
    )
    groups = answer_space_groups(cj)
    assert groups[0].question_numbers == [2]


def test_selection_free_contract_and_missing_contract_yield_empty():
    assert answer_space_groups(_contract_json(["q1"], [])) == []
    assert answer_space_groups(None) == []
    assert answer_space_groups({}) == []
