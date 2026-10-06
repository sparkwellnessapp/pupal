"""The shipped insertion_cases.json must validate against the shipped GT (§3.4).
A GT edit that breaks an arrow case — an anchor that no longer locates, a draft
that no longer conforms — fails here, instead of silently zeroing Bet 3's gold."""
from .check_gt_consistency import _raw_ink  # noqa: F401  (import-time sanity)
from .insertion_cases import validate


def test_the_shipped_cases_validate():
    rep = validate()
    assert rep.checked >= 5
    assert not rep.failures, rep.failures
