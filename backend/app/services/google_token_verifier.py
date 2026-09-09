"""The impure half of Sign in with Google: proving a `credential` came from Google.

Split from `google_identity` on purpose. Everything there is a pure function of
its arguments and is tested with literals; everything here touches the network
and the settings, and is the ONE place a test stubs. Keeping the boundary sharp
is what lets the security rule (`decide_link`) be tested without a mock in sight.
"""
from __future__ import annotations

import asyncio
import logging

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from ..config import settings
from .google_identity import GoogleClaims


logger = logging.getLogger(__name__)


class GoogleAuthUnavailable(RuntimeError):
    """No client ID is configured, so nothing can be verified.

    Distinct from "this token is bad": it is OUR misconfiguration, and it must
    surface as a 503, never as a 401 that would tell a teacher her perfectly
    good Google account was rejected.
    """


class GoogleTokenInvalid(ValueError):
    """The credential is not a token we will accept. Deliberately carries no
    detail to the client — signature, audience, issuer and expiry failures are
    one answer, because distinguishing them only helps whoever is probing."""


async def verify_google_credential(credential: str) -> GoogleClaims:
    """Verify a Google ID token and return the claims we act on.

    `verify_oauth2_token` checks the SIGNATURE against Google's rotating public
    keys, the `aud` claim against our client ID, and `exp`. `GoogleClaims`
    then asserts `iss`, `sub` and `email_verified` (see that module).

    Run in a worker thread: the google-auth verifier is synchronous and fetches
    (and caches) Google's certificates over the network. Called inline it would
    block the event loop for every other request on this instance — the same
    reason the transcription pipeline never holds a DB connection across an LLM
    call.
    """
    client_id = (settings.google_oauth_client_id or "").strip()
    if not client_id:
        # Fail LOUD and closed. An empty audience would make
        # verify_oauth2_token skip the aud check entirely, which would accept
        # tokens minted for any other Google app — the exact hole this
        # parameter exists to close.
        raise GoogleAuthUnavailable("google_oauth_client_id is not configured")

    if not credential or not isinstance(credential, str):
        raise GoogleTokenInvalid("no credential supplied")

    def _verify() -> dict:
        return google_id_token.verify_oauth2_token(
            credential, google_requests.Request(), client_id
        )

    try:
        claims = await asyncio.to_thread(_verify)
    except ValueError as e:
        # Bad signature, wrong audience, expired, malformed — one answer.
        # Logged WITHOUT the credential: it is a bearer token until it expires.
        logger.info("Google credential rejected: %s", e)
        raise GoogleTokenInvalid(str(e)) from e
    except Exception as e:
        # Certificate fetch failed, DNS, timeout — ours, not hers.
        logger.warning("Google token verification unavailable: %s", e)
        raise GoogleAuthUnavailable(str(e)) from e

    return GoogleClaims.from_verified_token(claims)
