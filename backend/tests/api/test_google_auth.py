"""Sign in with Google, end to end through the real endpoint.

Google itself is stubbed at EXACTLY ONE seam — `verify_google_credential`, the
only function that talks to Google — so everything downstream of it (the nonce,
the linking rule, account creation, the session) runs for real against the real
database.

The auth dependency is never faked: these routes are public by design, and the
sessions they issue are checked by using them.
"""
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.services.google_identity import GoogleClaims
from app.services.google_token_verifier import (
    GoogleAuthUnavailable,
    GoogleTokenInvalid,
)
from tests.api.auth_helpers import signup_pending, signup_verified


def claims(email: str, sub: str | None = None, name: str = "מיכל כהן") -> GoogleClaims:
    return GoogleClaims(
        subject=sub or f"sub-{uuid4().hex[:12]}",
        email=email.lower(),
        email_verified=True,
        full_name=name,
    )


def fresh_email(tag: str = "g") -> str:
    return f"{tag}_{uuid4().hex[:10]}@s2test.com"


def get_nonce(client) -> str:
    resp = client.get("/api/v0/auth/google/nonce")
    assert resp.status_code == 200, resp.text
    return resp.json()["nonce"]


def sign_in(client, google_claims: GoogleClaims, *, nonce: str | None = None):
    """POST /auth/google with Google stubbed to return `google_claims`."""
    nonce = nonce or get_nonce(client)
    with patch("app.api.v0.auth.verify_google_credential",
               new=AsyncMock(return_value=google_claims)):
        return client.post("/api/v0/auth/google",
                           json={"credential": "stub-credential", "nonce": nonce})


# --- the nonce ---------------------------------------------------------------

def test_nonce_endpoint_is_public_and_returns_a_fresh_value(client):
    a, b = get_nonce(client), get_nonce(client)
    assert a and b and a != b, "nonces must not repeat"


def test_a_nonce_cannot_be_used_twice(client):
    """THE REPLAY GUARD. A stolen credential is a bearer token for ~1h; the
    nonce is what makes our acceptance of it single-use."""
    nonce = get_nonce(client)
    c = claims(fresh_email())

    first = sign_in(client, c, nonce=nonce)
    assert first.status_code == 200, first.text

    replay = sign_in(client, c, nonce=nonce)
    assert replay.status_code == 401, "a spent nonce was accepted a second time"


def test_an_unknown_nonce_is_refused(client):
    resp = sign_in(client, claims(fresh_email()), nonce="never-issued-by-us")
    assert resp.status_code == 401


def test_a_rejected_sign_in_does_not_spend_the_nonce_silently(client):
    """The nonce is consumed inside the same transaction as the sign-in, so a
    failed verification rolls it back — she can press the button again."""
    nonce = get_nonce(client)
    with patch("app.api.v0.auth.verify_google_credential",
               new=AsyncMock(side_effect=GoogleTokenInvalid("bad signature"))):
        bad = client.post("/api/v0/auth/google",
                          json={"credential": "x", "nonce": nonce})
    assert bad.status_code == 401

    ok = sign_in(client, claims(fresh_email()), nonce=nonce)
    assert ok.status_code == 200, "the nonce was burned by a failed attempt"


# --- token failures ----------------------------------------------------------

def test_an_invalid_token_is_401(client):
    with patch("app.api.v0.auth.verify_google_credential",
               new=AsyncMock(side_effect=GoogleTokenInvalid("wrong audience"))):
        resp = client.post("/api/v0/auth/google",
                           json={"credential": "x", "nonce": get_nonce(client)})
    assert resp.status_code == 401
    assert "Google" in resp.json()["detail"]


def test_a_misconfigured_server_is_503_not_401(client):
    """OURS, not hers. A 401 here would send a teacher to debug her own Google
    account over a missing environment variable."""
    with patch("app.api.v0.auth.verify_google_credential",
               new=AsyncMock(side_effect=GoogleAuthUnavailable("no client id"))):
        resp = client.post("/api/v0/auth/google",
                           json={"credential": "x", "nonce": get_nonce(client)})
    assert resp.status_code == 503


# --- the linking matrix, through the real endpoint ---------------------------

def test_a_new_google_user_gets_an_account_and_a_working_session(client):
    email = fresh_email("gnew")
    resp = sign_in(client, claims(email, name="מיכל כהן"))
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body["user"]["email"] == email
    assert body["user"]["full_name"] == "מיכל כהן"
    # A brand-new teacher, so she lands in onboarding like everyone else.
    assert body["user"]["onboarding_completed_at"] is None

    me = client.get("/api/v0/auth/me",
                    headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200, "the session Google sign-in issued does not work"


def test_the_same_google_account_returns_to_the_same_row(client):
    email = fresh_email("gret")
    c = claims(email)

    first = sign_in(client, c).json()
    second = sign_in(client, c).json()
    assert first["user"]["id"] == second["user"]["id"]


def test_a_changed_gmail_address_still_finds_her_account(client):
    """`sub` is the identity, not the email — Google accounts can change
    address. Without this, a teacher who changed hers would silently acquire a
    second Vivi account and lose her rubrics."""
    sub = f"sub-{uuid4().hex[:12]}"
    first = sign_in(client, claims(fresh_email("old"), sub=sub)).json()
    second = sign_in(client, claims(fresh_email("new"), sub=sub)).json()
    assert first["user"]["id"] == second["user"]["id"]


def test_links_into_an_account_that_verified_its_email(client):
    """She signed up with a password and proved the address; signing in with
    Google on the same address is the same person."""
    email = fresh_email("glink")
    existing = signup_verified(client, email=email)

    resp = sign_in(client, claims(email))
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["id"] == existing["user"]["id"], "a second account was created"


def test_REFUSES_to_link_into_an_UNVERIFIED_account(client):
    """THE nOAuth GUARD, at the endpoint.

    The password account exists but nobody proved the address — it could have
    been registered by an attacker who typed the victim's address. Linking here
    would hand that attacker her Google identity.
    """
    email = fresh_email("gunver")
    pending = signup_pending(client, email)
    assert pending.status_code == 200, pending.text

    resp = sign_in(client, claims(email))
    assert resp.status_code == 409, (
        f"an unverified account accepted a Google link: {resp.status_code}"
    )


def test_the_refusal_does_not_create_a_second_account_either(client):
    """Refusing must not quietly fall through to CREATE_NEW — that would give
    the attacker's row and the victim's row the same address."""
    email = fresh_email("gdup")
    signup_pending(client, email)

    assert sign_in(client, claims(email)).status_code == 409
    # The address is still owned by the pending signup, so verifying it works.
    from tests.api.auth_helpers import verify
    assert verify(client, email).status_code == 200


# --- shape -------------------------------------------------------------------

def test_google_users_are_verified_by_construction(client):
    """No code is emailed to a Google signup: Google already proved the address
    and the token was refused unless `email_verified` was true."""
    email = fresh_email("gver")
    token = sign_in(client, claims(email)).json()["access_token"]

    # A verified account can log in through the ordinary session path.
    me = client.get("/api/v0/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == email


def test_a_google_account_cannot_be_entered_with_a_password(client):
    """password_hash is NULL for a Google signup, and authenticate_user refuses
    a row without one — so guessing a password can never open it."""
    email = fresh_email("gpw")
    sign_in(client, claims(email))

    resp = client.post("/api/v0/auth/login",
                       json={"email": email, "password": "testpass123"})
    assert resp.status_code == 401


@pytest.mark.parametrize("body", [
    {"credential": "", "nonce": "n"},
    {"nonce": "n"},
    {"credential": "c"},
    {},
])
def test_malformed_bodies_are_422_not_500(client, body):
    resp = client.post("/api/v0/auth/google", json=body)
    assert resp.status_code == 422
