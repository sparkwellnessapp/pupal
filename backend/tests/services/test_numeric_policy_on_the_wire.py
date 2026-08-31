"""
The rounding rule travels with the grade (OD-F8).

The client re-prices the overlay locally so a flipped verdict updates the score
instantly. It can only match the server if it rounds the same way — and
`numeric_policy` was not on the graded-test response at all.

This is the exact failure `selection_scoring.py` was written to end: two places
computing the same number, the teacher reviewing one and a DIFFERENT one
freezing into the immutable contract. Hardcoding 0.25 in the browser works for
the pilot rubric and is silently wrong for the first rubric that rounds to
halves — the worst kind of wrong, because both numbers look right.

THREE fields, not one. `precision` alone is not enough: a client rounding
half_up against a server rounding half_even disagrees on every exact .5, which
is precisely where a 0.25 grid puts its boundaries.
"""
from __future__ import annotations

from decimal import Decimal


def test_numeric_policy_is_on_the_graded_test_responses():
    from app.schemas.graded_test_responses import (
        GradedTestApprovedResponse, GradedTestDraftResponse)

    for model in (GradedTestDraftResponse, GradedTestApprovedResponse):
        assert "numeric_policy" in model.model_fields, (
            f"{model.__name__} does not carry the rounding rule — the client "
            f"cannot re-price without guessing it")


def test_the_policy_carries_everything_the_client_rounds_with():
    from app.schemas.ontology_types import NumericPolicy

    policy = NumericPolicy()
    for field in ("precision", "rounding_mode", "sum_tolerance"):
        assert field in NumericPolicy.model_fields, field

    # the pilot's grid, pinned so a default change is a deliberate act
    assert policy.precision == Decimal("0.25")
    assert policy.rounding_mode == "half_up"


def test_policy_serialises_as_a_string_not_a_float():
    """Decimal must cross the wire as a string. A float `0.25` invites the
    client to do binary-float arithmetic on money-like values, which is how
    0.1 + 0.2 stops equalling 0.3 in someone's grade."""
    from app.schemas.ontology_types import NumericPolicy

    dumped = NumericPolicy().model_dump(mode="json")
    assert isinstance(dumped["precision"], str), dumped["precision"]
    assert isinstance(dumped["sum_tolerance"], str), dumped["sum_tolerance"]
