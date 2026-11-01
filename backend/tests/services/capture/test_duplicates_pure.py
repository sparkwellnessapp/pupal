"""
SCN-13 DuplicateIsDerived — the grouping rule, with zero mocks.

A duplicate is a pure function of the batch's saved claims: the same student
id, or the same typed name while no student is confirmed. A typed name is
never matched to a student here (OD-B6). The 2026-10-30 production sequence
(a pair that split when one half was named) is pinned below.
"""
from __future__ import annotations

import uuid

from app.services.capture.duplicates import Claim, claimant_count, duplicate_groups


def _id() -> uuid.UUID:
    return uuid.uuid4()


def test_one_submission_per_student_is_no_duplicate():
    a, b = Claim(_id(), _id(), None), Claim(_id(), _id(), None)
    assert duplicate_groups([a, b]) == {}
    assert claimant_count([a, b]) == 2


def test_two_sets_for_one_student_are_one_group():
    s = _id()
    a, b, c = Claim(_id(), s, None), Claim(_id(), s, None), Claim(_id(), _id(), None)
    groups = duplicate_groups([a, b, c])
    assert set(groups) == {a.submission_id, b.submission_id}
    assert groups[a.submission_id] == groups[b.submission_id] == tuple(
        sorted([a.submission_id, b.submission_id]))
    assert claimant_count([a, b, c]) == 2


def test_the_same_typed_name_groups_regardless_of_order_and_spacing():
    a = Claim(_id(), None, "דני כהן")
    b = Claim(_id(), None, "  כהן   דני ")            # D16: token-order independent
    c = Claim(_id(), None, "רון לוי")
    groups = duplicate_groups([a, b, c])
    assert set(groups) == {a.submission_id, b.submission_id}
    assert claimant_count([a, b, c]) == 2


def test_a_typed_name_never_joins_a_confirmed_student():
    """OD-B6: the typed «דני כהן» is not the confirmed student called that —
    the teacher links it, and only then do the two form a group."""
    s = _id()
    confirmed = Claim(_id(), s, None)
    typed = Claim(_id(), None, "דני כהן")
    assert duplicate_groups([confirmed, typed]) == {}
    linked = Claim(typed.submission_id, s, "דני כהן")   # after resolve-pending
    assert set(duplicate_groups([confirmed, linked])) == {confirmed.submission_id,
                                                          typed.submission_id}


def test_a_typed_name_is_ignored_once_a_student_is_set():
    """A row with a student claims the student, whatever was typed."""
    a = Claim(_id(), _id(), "דני כהן")
    b = Claim(_id(), None, "דני כהן")
    assert duplicate_groups([a, b]) == {}


def test_a_blank_typed_name_claims_no_one():
    assert duplicate_groups([Claim(_id(), None, None), Claim(_id(), None, "   ")]) == {}


def test_the_production_split_cannot_happen_by_construction():
    """2026-10-30: two link submissions typed one name; the teacher named the
    EARLIER one; the later one kept a name claim and the pair split, so the
    dialog showed one photo and «keep» had no student. Here the group stays
    whole for as long as both are typed — and naming one half is refused
    while they are a group (resolve_pending → duplicate_unresolved), so the
    only way out is the teacher's keep."""
    first, later = Claim(_id(), None, "נועה בר"), Claim(_id(), None, "נועה בר")
    groups = duplicate_groups([first, later])
    assert groups[first.submission_id] == groups[later.submission_id]
    assert len(groups[first.submission_id]) == 2


def test_three_sets_are_one_group():
    s = _id()
    claims = [Claim(_id(), s, None) for _ in range(3)]
    groups = duplicate_groups(claims)
    assert len(set(groups.values())) == 1 and len(next(iter(groups.values()))) == 3
    assert claimant_count(claims) == 1
