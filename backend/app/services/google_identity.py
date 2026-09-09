"""Sign in with Google — the pure half.

Everything here is a function of its arguments: no database, no network, no
clock beyond what is passed in. That is the point. The account-linking rule is
the one place in this codebase where a plausible-looking implementation is a
real vulnerability, so it is a table a reviewer can read in thirty seconds and a
test can enumerate exhaustively — not a branch buried in an endpoint.

THE RULE (owner ruling A3): a Google identity is linked to an existing account
only when that account's email was PROVEN. Matching email addresses is how a
candidate is FOUND; it is never why a link is allowed.

Why that matters, concretely: signup used to write a row for any address with no
proof of control, so an attacker could pre-register victim@school.org. If a
matching email were sufficient, the victim's later Google sign-in would land on
the attacker's row and both credentials would open one account. That is
Microsoft's "nOAuth" (2023) and the Sign in with Apple JWT flaw (2020).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class GoogleClaimsError(ValueError):
    """The ID token was structurally valid but says something we refuse to act
    on. Distinct from a signature/audience failure, which never gets this far."""


@dataclass(frozen=True)
class GoogleClaims:
    """The subset of a verified Google ID token this product uses.

    `subject` is the token's `sub` — THE identity. Google's own guidance: "Only
    use Google ID token `sub` field as identifier as it is unique among all
    Google Accounts and never reused… don't use email address as an identifier
    because a Google Account can have multiple email addresses at different
    points in time."
    """

    subject: str
    email: str
    email_verified: bool
    full_name: Optional[str] = None

    @classmethod
    def from_verified_token(cls, claims: dict) -> "GoogleClaims":
        """Build from the dict `verify_oauth2_token` returned.

        The signature, `aud` and `exp` are already checked by the library before
        this is reached. What is checked HERE is everything the library does not
        decide for us:

        * `iss` — asserted rather than assumed. It is the claim that says Google
          issued this token, and it costs one comparison.
        * `sub` — must be present and non-empty, because it is the identity.
        * `email_verified` — must be true. Google can itself hold an address it
          has not verified, and treating one as proof re-opens the pre-account
          hijacking hole this whole module exists to close.
        """
        issuer = claims.get("iss")
        if issuer not in ("accounts.google.com", "https://accounts.google.com"):
            raise GoogleClaimsError(f"unexpected issuer: {issuer!r}")

        subject = (claims.get("sub") or "").strip()
        if not subject:
            raise GoogleClaimsError("token carries no subject (sub)")

        email = (claims.get("email") or "").strip().lower()
        if not email:
            raise GoogleClaimsError("token carries no email")

        # Google sends this as a real bool, but has historically also sent the
        # strings "true"/"false" through some surfaces. Accept only an explicit
        # truth; anything else — including a missing claim — is NOT proof.
        raw_verified = claims.get("email_verified")
        verified = raw_verified is True or raw_verified == "true"
        if not verified:
            raise GoogleClaimsError("Google has not verified this address")

        name = (claims.get("name") or "").strip() or None
        return cls(subject=subject, email=email, email_verified=True, full_name=name)


class LinkOutcome(str, Enum):
    """What to do with a verified Google identity. Exactly four outcomes."""

    #: `google_id` is already on an account — the ordinary returning sign-in.
    SIGN_IN_EXISTING_GOOGLE = "sign_in_existing_google"
    #: No Google account, but an existing account with this email PROVED it.
    LINK_TO_VERIFIED_EMAIL = "link_to_verified_email"
    #: An account holds this email but never proved it. A3: refuse (nOAuth).
    REFUSE_UNVERIFIED_EMAIL = "refuse_unverified_email"
    #: Nobody holds this identity or this address — a new teacher.
    CREATE_NEW = "create_new"


@dataclass(frozen=True)
class AccountFacts:
    """What the database knows about a candidate row, reduced to the two facts
    the rule depends on. Deliberately NOT the ORM object: this keeps the rule
    testable with literals and unable to reach for anything else."""

    user_id: str
    email_verified: bool


def decide_link(
    by_google_id: Optional[AccountFacts],
    by_email: Optional[AccountFacts],
) -> LinkOutcome:
    """The whole of A3, in one function.

    `by_google_id` — the account already carrying this token's `sub`, if any.
    `by_email`     — the account carrying this token's email address, if any.

    Order matters. The `sub` match is checked FIRST and unconditionally wins: it
    is the identity, it was proven by Google seconds ago, and an account that
    already carries it is the same person by definition — whatever the email
    now says. This is also what makes a Google user who later changed her Gmail
    address keep her account instead of silently getting a second one.
    """
    if by_google_id is not None:
        return LinkOutcome.SIGN_IN_EXISTING_GOOGLE

    if by_email is None:
        return LinkOutcome.CREATE_NEW

    # An account holds this address. Linking is authorized by PROOF, never by
    # the address matching — that match is exactly what an attacker controls.
    if by_email.email_verified:
        return LinkOutcome.LINK_TO_VERIFIED_EMAIL

    return LinkOutcome.REFUSE_UNVERIFIED_EMAIL
