"""The account-linking rule (owner ruling A3) and Google claim handling.

Zero mocks and zero I/O — the point of `decide_link` being pure is that the one
security decision in Sign in with Google can be enumerated exhaustively instead
of being inferred from an endpoint's behaviour.
"""
import itertools

import pytest

from app.services.google_identity import (
    AccountFacts,
    GoogleClaims,
    GoogleClaimsError,
    LinkOutcome,
    decide_link,
)


def facts(verified: bool, user_id: str = "u1") -> AccountFacts:
    return AccountFacts(user_id=user_id, email_verified=verified)


# --- the truth table ---------------------------------------------------------

def test_returning_google_user_signs_in():
    assert decide_link(facts(True), None) is LinkOutcome.SIGN_IN_EXISTING_GOOGLE


def test_new_identity_and_new_address_creates():
    assert decide_link(None, None) is LinkOutcome.CREATE_NEW


def test_links_into_an_account_that_PROVED_its_address():
    assert decide_link(None, facts(True)) is LinkOutcome.LINK_TO_VERIFIED_EMAIL


def test_REFUSES_an_account_that_never_proved_its_address():
    """THE nOAuth GUARD. An attacker who pre-registers victim@school.org must not
    receive the victim's Google identity. If this test ever goes green the other
    way, Sign in with Google is an account-takeover feature."""
    assert decide_link(None, facts(False)) is LinkOutcome.REFUSE_UNVERIFIED_EMAIL


@pytest.mark.parametrize("email_verified", [True, False])
def test_the_sub_match_wins_regardless_of_the_email_row(email_verified):
    """`sub` is the identity and Google just proved it. A different account
    holding the same address never overrides that — which is also what keeps a
    teacher who CHANGED her Gmail address on her own account instead of
    silently acquiring a second one."""
    outcome = decide_link(facts(True, "google-user"), facts(email_verified, "email-user"))
    assert outcome is LinkOutcome.SIGN_IN_EXISTING_GOOGLE


def test_every_input_combination_is_decided():
    """No input falls through to None — a missing branch here would be an
    endpoint crashing on a real teacher's sign-in."""
    for g, e in itertools.product([None, facts(True), facts(False)], repeat=2):
        assert isinstance(decide_link(g, e), LinkOutcome)


# --- claim handling ----------------------------------------------------------

def base_claims(**over) -> dict:
    claims = {
        "iss": "https://accounts.google.com",
        "sub": "1234567890",
        "email": "Michal@School.org",
        "email_verified": True,
        "name": "מיכל כהן",
    }
    claims.update(over)
    return claims


def test_accepts_a_well_formed_token():
    c = GoogleClaims.from_verified_token(base_claims())
    assert c.subject == "1234567890"
    assert c.full_name == "מיכל כהן"


def test_lower_cases_the_email_so_lookup_is_stable():
    """Google may echo the address as typed; our users.email lookups must not
    depend on which capitalisation arrived."""
    assert GoogleClaims.from_verified_token(base_claims()).email == "michal@school.org"


@pytest.mark.parametrize("iss", ["accounts.google.com", "https://accounts.google.com"])
def test_accepts_both_documented_issuers(iss):
    assert GoogleClaims.from_verified_token(base_claims(iss=iss)).subject


@pytest.mark.parametrize("iss", ["https://accounts.google.com.evil.test", "", None,
                                 "https://accounts.example.com"])
def test_rejects_any_other_issuer(iss):
    with pytest.raises(GoogleClaimsError):
        GoogleClaims.from_verified_token(base_claims(iss=iss))


@pytest.mark.parametrize("verified", [False, None, "false", 0, "TRUE"])
def test_rejects_an_address_google_has_not_verified(verified):
    """Not proof ⇒ not accepted. Anything but an explicit truth is refused,
    including a MISSING claim — the silent case is the dangerous one."""
    with pytest.raises(GoogleClaimsError):
        GoogleClaims.from_verified_token(base_claims(email_verified=verified))


def test_accepts_the_string_form_google_has_historically_sent():
    assert GoogleClaims.from_verified_token(base_claims(email_verified="true")).email_verified


@pytest.mark.parametrize("sub", ["", "   ", None])
def test_rejects_a_token_with_no_subject(sub):
    """`sub` IS the identity; without it there is nothing to key the account on."""
    with pytest.raises(GoogleClaimsError):
        GoogleClaims.from_verified_token(base_claims(sub=sub))


@pytest.mark.parametrize("email", ["", None])
def test_rejects_a_token_with_no_email(email):
    with pytest.raises(GoogleClaimsError):
        GoogleClaims.from_verified_token(base_claims(email=email))


def test_missing_name_is_none_not_the_string_none():
    c = GoogleClaims.from_verified_token(base_claims(name=None))
    assert c.full_name is None
