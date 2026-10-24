"""
The capture tokens — pure (rulings OD-4, OD-5, D1).

  link token     HMAC-SHA256(capture_token_secret, "capture-link:{id}:{gen}"),
                 first 16 bytes, base64url → 22 characters (OD-4). Never
                 stored: `capture_links.token_hash` = sha256(token) is the
                 lookup key, and the token itself is RECOMPUTED whenever the
                 teacher re-shows the QR. Rotation bumps the generation.
  device secret  32 random bytes, base64url, returned ONCE to the student's
                 browser at submission creation (D1); sha256 at rest.
  handoff token  32 random bytes — the one-time, 10-minute QR the desktop
                 shows the phone (D2, OD-5); sha256 at rest.
  session token  32 random bytes — what the handoff is exchanged for: a
                 batch-scoped 12-hour capture session; sha256 at rest.

Opaque random tokens, not JWTs, for the session (OD-5): a JWT signed with the
login secret and carrying `sub` would be accepted by `get_current_user` as a
full login. An opaque token cannot be, and needs no new secret.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from uuid import UUID


class CaptureNotConfigured(RuntimeError):
    """`capture_token_secret` is unset: no link token can be derived."""


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def sha256(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


def link_token(secret: str, link_id: UUID, generation: int) -> str:
    if not secret:
        raise CaptureNotConfigured("capture_token_secret is not set")
    mac = hmac.new(secret.encode("utf-8"), f"capture-link:{link_id}:{generation}".encode("ascii"),
                   hashlib.sha256).digest()
    return _b64(mac[:16])


def random_token() -> str:
    """32 random bytes, base64url (43 characters)."""
    return _b64(secrets.token_bytes(32))


def same_hash(a: bytes, b: bytes) -> bool:
    return hmac.compare_digest(a, b)
