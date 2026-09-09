"""Verified email signup, through the real endpoints.

Nothing is mocked except the code GENERATOR (see auth_helpers): the code is
bcrypt-hashed the instant it is minted, so pinning the generator for the
duration of a signup call is the only way to know what to submit — and it beats
adding a back door to production code.

The email provider is `console` by default, so no test can send real mail.
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.email_service import EmailResult
from app.services.verification_codes import MAX_ATTEMPTS
from tests.api.auth_helpers import TEST_CODE, signup_pending, signup_verified, verify


def fresh_email(tag: str = "ev") -> str:
    return f"{tag}_{uuid4().hex[:10]}@s2test.com"


# --- signup no longer hands out a session ------------------------------------

def test_signup_returns_no_session(client):
    """OWNER RULING A4. If this ever returns a token again, an address nobody
    proved becomes a usable account — and the Google linking rule loses the
    property it depends on."""
    resp = signup_pending(client, fresh_email())
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["verification_required"] is True
    assert "access_token" not in body
    assert "user" not in body


def test_an_unverified_account_cannot_log_in(client):
    """The account exists, the password is right, and it still opens nothing."""
    email = fresh_email("unver")
    signup_pending(client, email)

    resp = client.post("/api/v0/auth/login",
                       json={"email": email, "password": "testpass123"})
    # 403 and not 401: the password was RIGHT. The distinction is what lets the
    # client open the verification panel instead of claiming she mistyped it.
    assert resp.status_code == 403, (
        "an unverified account logged in — A4 is not being enforced"
    )


def test_verifying_issues_a_working_session(client):
    email = fresh_email("ok")
    signup_pending(client, email)

    resp = verify(client, email)
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]

    me = client.get("/api/v0/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_after_verifying_the_password_works(client):
    email = fresh_email("pw")
    signup_verified(client, email=email)

    resp = client.post("/api/v0/auth/login",
                       json={"email": email, "password": "testpass123"})
    assert resp.status_code == 200, resp.text


# --- the code itself ---------------------------------------------------------

def test_a_wrong_code_is_refused(client):
    email = fresh_email("wrong")
    signup_pending(client, email)

    resp = verify(client, email, code="999999")
    assert resp.status_code == 400


def test_a_code_is_single_use(client):
    email = fresh_email("reuse")
    signup_pending(client, email)
    assert verify(client, email).status_code == 200

    again = verify(client, email)
    assert again.status_code == 400, "a consumed code was accepted twice"


def test_attempts_are_capped_and_then_the_code_is_dead(client):
    """Five wrong guesses kill the code — the right one no longer works."""
    email = fresh_email("brute")
    signup_pending(client, email)

    for _ in range(MAX_ATTEMPTS):
        assert verify(client, email, code="000000").status_code == 400

    blocked = verify(client, email, code="000000")
    assert blocked.status_code == 429

    correct = verify(client, email, code=TEST_CODE)
    assert correct.status_code == 429, "the attempt cap did not survive a correct guess"


def test_an_unknown_address_gets_the_same_answer_as_a_wrong_code(client):
    """Otherwise this endpoint answers 'does this teacher have an account?'."""
    resp = verify(client, f"nobody_{uuid4().hex[:10]}@s2test.com")
    assert resp.status_code == 400


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 34 56", "",
                                  "١٢٣٤٥٦"])
def test_malformed_codes_are_rejected_by_validation(client, code):
    """«١٢٣٤٥٦» is Arabic-Indic 123456: it renders like a code and would slip
    through a Unicode-aware \\d pattern."""
    resp = client.post("/api/v0/auth/verify-email",
                       json={"email": fresh_email(), "code": code})
    assert resp.status_code == 422


# --- resend ------------------------------------------------------------------

def test_resend_is_uniform_for_unknown_addresses(client):
    """202 and the same body, always — no enumeration oracle."""
    known = fresh_email("known")
    signup_pending(client, known)
    unknown = f"nobody_{uuid4().hex[:10]}@s2test.com"

    a = client.post("/api/v0/auth/resend-code", json={"email": known})
    b = client.post("/api/v0/auth/resend-code", json={"email": unknown})

    assert a.status_code == b.status_code == 202
    assert a.json() == b.json(), "the response distinguishes a real address"


def test_resend_is_uniform_for_already_verified_addresses(client):
    email = fresh_email("done")
    signup_verified(client, email=email)

    resp = client.post("/api/v0/auth/resend-code", json={"email": email})
    assert resp.status_code == 202


def test_the_cooldown_does_not_leak_through_the_status_code(client):
    """A second resend is inside the 60s cooldown and is silently not sent —
    but the caller cannot tell, which is the point."""
    email = fresh_email("cool")
    signup_pending(client, email)

    first = client.post("/api/v0/auth/resend-code", json={"email": email})
    second = client.post("/api/v0/auth/resend-code", json={"email": email})

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()


# --- the send is part of the transaction -------------------------------------

def test_a_failed_send_rolls_the_whole_signup_back(client):
    """A teacher must never be left holding an address she can neither use nor
    re-register because the code went nowhere."""
    email = fresh_email("bounce")

    with patch("app.services.email_verification.send_verification_code",
               new=AsyncMock(return_value=EmailResult(success=False, error="boom"))):
        resp = client.post("/api/v0/auth/signup",
                           json={"email": email, "password": "testpass123",
                                 "full_name": "מורה"})
    assert resp.status_code == 502

    # The address is free again — proof the user row was rolled back.
    retry = signup_pending(client, email)
    assert retry.status_code == 200, (
        "the failed signup left an account behind; the address is now unusable"
    )


def test_a_duplicate_signup_is_still_refused(client):
    email = fresh_email("dup")
    signup_pending(client, email)

    again = signup_pending(client, email)
    assert again.status_code == 400
