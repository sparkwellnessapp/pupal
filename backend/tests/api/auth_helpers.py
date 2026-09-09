"""Signing a test user up, after signup stopped issuing sessions (migration 024).

ONE helper, imported by conftest and by every module that used to roll its own
`_fresh_user`. Before this, four files each knew how to make a user; the wire
change would have had to be applied to all four, which is exactly the
duplication that makes a breaking change expensive.

WHY THE PATCH. The code is bcrypt-hashed the moment it is minted, so nothing —
not the database, not a log — can hand it back. That is the property we want in
production and the obstacle in tests. Rather than adding a back door to the real
code path (an env var that fixes the code, a debug field on the response), the
helper pins the GENERATOR for the duration of the signup call only. Production
code is untouched, the patch cannot outlive the `with` block, and the real
generator keeps its own unit tests in tests/services/test_verification_codes.py.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

#: The code every helper-made signup uses. Fixed, so a test can also drive the
#: verify endpoint by hand (wrong-code cases pass something else).
TEST_CODE = "123456"


def signup_pending(client, email: str, password: str = "testpass123",
                   full_name: str = "מורה לבדיקה"):
    """Create an account and stop BEFORE verifying. Returns the raw response.

    The account exists and is unusable — which is the state the Google linking
    rule treats as untrustworthy, so tests that exercise A3 need exactly this.
    """
    with patch("app.services.email_verification.generate_code", return_value=TEST_CODE):
        return client.post(
            "/api/v0/auth/signup",
            json={"email": email, "password": password, "full_name": full_name},
        )


def verify(client, email: str, code: str = TEST_CODE):
    """Redeem a code. Returns the raw response so a caller can assert failures."""
    return client.post("/api/v0/auth/verify-email", json={"email": email, "code": code})


def signup_verified(client, tag: str = "user", *, email: str | None = None,
                    password: str = "testpass123",
                    full_name: str = "מורה לבדיקה") -> dict:
    """The full happy path: signup → verify → a usable session.

    Returns the same `{access_token, user}` shape signup itself used to return,
    so a caller that only wanted "a logged-in user" reads unchanged.
    """
    email = email or f"{tag}_{uuid4().hex[:10]}@s2test.com"

    pending = signup_pending(client, email, password, full_name)
    assert pending.status_code == 200, f"signup failed: {pending.text}"
    body = pending.json()
    assert body["verification_required"] is True
    assert "access_token" not in body, (
        "signup must NOT issue a session before the address is proven (A4)"
    )

    verified = verify(client, email)
    assert verified.status_code == 200, f"verification failed: {verified.text}"
    return verified.json()


def auth_headers(payload: dict) -> dict:
    return {"Authorization": f"Bearer {payload['access_token']}"}
