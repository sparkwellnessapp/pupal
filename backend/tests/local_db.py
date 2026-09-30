"""A-10 — where a test session may point its database, and the local cluster's address.

ONE place for both facts, because they must agree: `scripts/local_test_db.py` starts
the cluster at this address, and `tests/conftest.py` accepts localhost ONLY at this
address. Nothing here imports the app (conftest runs it before Settings exists).

The rule the guard enforces (it fails CLOSED):
  * no DATABASE_URL at all            → allowed (nothing to connect to; the offline
                                         CI battery runs this way);
  * the local test cluster             → allowed: 127.0.0.1/localhost AND port 55717;
  * Vivi-Test (Supabase eqnbojbxsdafwtxvuyuy) → allowed, pooler only with that tenant;
  * anything else — production included, and any OTHER local Postgres (the machine's
    own service on 5432) → refused.
"""
from __future__ import annotations

from typing import NamedTuple, Optional
from urllib.parse import urlparse

LOCAL_HOST = "127.0.0.1"
LOCAL_PORT = 55717
LOCAL_DATABASE = "vivi_test"
# The role the app connects as. Named `postgres`, NOSUPERUSER + BYPASSRLS, owning the
# schema — the same shape the Supabase `postgres` role has on Vivi-Test.
LOCAL_APP_ROLE = "postgres"
LOCAL_DATABASE_URL = (
    f"postgresql+asyncpg://{LOCAL_APP_ROLE}@{LOCAL_HOST}:{LOCAL_PORT}/{LOCAL_DATABASE}")

# `VIVI_TEST_DB=local` is the explicit opt-in; unset (or `remote`) is today's behaviour.
SELECT_ENV = "VIVI_TEST_DB"

VIVI_TEST_TENANT = "eqnbojbxsdafwtxvuyuy"


class DbTarget(NamedTuple):
    host: str
    port: Optional[int]
    user: str


def resolve_db_target(url: Optional[str]) -> Optional[DbTarget]:
    """None when there is no URL at all; otherwise the (host, port, user) it names."""
    if not url:
        return None
    p = urlparse(url.replace("postgresql+asyncpg://", "postgresql://", 1)
                    .replace("postgresql+psycopg2://", "postgresql://", 1))
    return DbTarget(p.hostname or "", p.port, p.username or "")


def is_local_cluster(target: Optional[DbTarget]) -> bool:
    return (target is not None and target.host in ("127.0.0.1", "localhost")
            and target.port == LOCAL_PORT)


def is_allowed_test_target(url: Optional[str]) -> bool:
    target = resolve_db_target(url)
    if target is None:
        return True
    if is_local_cluster(target):
        return True
    if target.host == "aws-0-eu-central-1.pooler.supabase.com":
        return target.user.endswith("." + VIVI_TEST_TENANT)
    return target.host == f"db.{VIVI_TEST_TENANT}.supabase.co"
