"""
Auth canon tests for the users router (CLAUDE.md §9).

Background — the defect these tests pin down:

  `users.py` shipped with a LOCAL `get_current_user` that read a `user_id`
  QUERY PARAMETER and trusted it. It never read the Authorization header, so it
  failed in BOTH directions at once:

    * it rejected valid session tokens  (GET /api/v0/users/me -> 401), and
    * it accepted anonymous callers     (GET /api/v0/users/me/rubrics
      ?user_id=<victim> with no Authorization header -> 200), including an
      unauthenticated WRITE via PUT /me/subject-matters.

  The rule it broke (§9) exists precisely because two auth implementations
  cannot stay in agreement. So the fix deletes the local one rather than
  repairing it, and `test_users_routes_use_canonical_auth` below is the
  structural guard that keeps a replacement from sneaking back in.

A second, independent defect surfaced while building the control case for the
above: `User.is_subscription_active` compared a naive `datetime.utcnow()` with a
timezone-aware `trial_ends_at` (the DB columns are TIMESTAMPTZ), raising
TypeError for every `trial` user — which 500'd login, /auth/me and /auth/refresh
for 271 of 273 live users. `test_login_succeeds_for_trial_user` and
`test_users_me_accepts_valid_session` pin that.

These tests use REAL session tokens from the real signup endpoint (the harness
never fakes the auth dependency — faking it would bypass the exact code under
test).
"""
from datetime import timedelta
from uuid import uuid4

import pytest
from jose import jwt

from app.api.v0 import users as users_module
from app.api.v0.auth import get_current_user as CANONICAL_GET_CURRENT_USER
from app.services.auth_service import ALGORITHM, auth_service


# The profile endpoint that SURVIVED consolidation. `users.py` carried a
# byte-identical duplicate at /api/v0/users/me with no caller; the frontend has
# always called this one (frontend/src/lib/auth.tsx), so this is the shape that
# must not change.
PROFILE_ENDPOINT = "/api/v0/auth/me"

# Every route the users router exposes, as (method, path, json_body).
# Ownership-scoped paths use a random UUID: an unauthenticated caller must be
# stopped by AUTH (401) before ownership is ever consulted (404).
USERS_ROUTES = [
    ("GET", "/api/v0/users/subject-matters", None),
    ("GET", "/api/v0/users/me/subject-matters", None),
    ("PUT", "/api/v0/users/me/subject-matters", {"subject_matter_ids": []}),
    ("GET", "/api/v0/users/me/rubrics", None),
    ("GET", "/api/v0/users/me/graded-tests", None),
    ("POST", f"/api/v0/users/rubrics/{uuid4()}/share", {"email": "x@s2test.com", "permission": "view"}),
    ("GET", f"/api/v0/users/rubrics/{uuid4()}/shares", None),
    ("DELETE", f"/api/v0/users/rubrics/{uuid4()}/shares/{uuid4()}", None),
]

ROUTE_IDS = [f"{m} {p.split('?')[0]}" for m, p, _ in USERS_ROUTES]


def _call(client, method, path, body=None, headers=None):
    kwargs = {"headers": headers} if headers else {}
    if body is not None:
        kwargs["json"] = body
    return client.request(method, path, **kwargs)


# ---------------------------------------------------------------------------
# 1 — The reported symptom: a valid session token must be accepted.
#     RED before the fix (500: the naive/aware TypeError for a `trial` user).
# ---------------------------------------------------------------------------

def test_users_me_accepts_valid_session(client, headers_a):
    resp = client.get(PROFILE_ENDPOINT, headers=headers_a)
    assert resp.status_code == 200, (
        f"A valid session token was refused by {PROFILE_ENDPOINT}: "
        f"{resp.status_code} {resp.text[:200]}"
    )
    body = resp.json()
    assert body["email"]
    assert body["is_subscription_active"] in (True, False)


def test_login_succeeds_for_trial_user(client):
    """A brand-new user is `trial`; login must serialize that user, not 500.

    Regression for models/user.py: `datetime.utcnow() < self.trial_ends_at`
    compared naive against the TIMESTAMPTZ-backed (aware) value and raised
    TypeError inside the response builder, AFTER authentication had succeeded.
    """
    email = f"trial_{uuid4().hex[:8]}@s2test.com"
    signup = client.post(
        "/api/v0/auth/signup",
        json={"email": email, "password": "testpass123", "full_name": "Trial User"},
    )
    assert signup.status_code == 200, signup.text
    assert signup.json()["user"]["subscription_status"] == "trial"

    login = client.post("/api/v0/auth/login", json={"email": email, "password": "testpass123"})
    assert login.status_code == 200, (
        f"Login 500'd for a trial user (the naive/aware datetime defect): "
        f"{login.status_code} {login.text[:200]}"
    )

    token = login.json()["access_token"]
    me = client.get(PROFILE_ENDPOINT, headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, f"{PROFILE_ENDPOINT} 500'd for a trial user: {me.text[:200]}"
    assert me.json()["is_subscription_active"] is True


# ---------------------------------------------------------------------------
# 2 — Rejection axes. The deleted local verifier was WEAKER on every one of
#     these: it checked no signature, no expiry, no algorithm, no header.
# ---------------------------------------------------------------------------

def test_users_me_rejects_invalid_token_401(client):
    resp = client.get(PROFILE_ENDPOINT, headers={"Authorization": "Bearer garbage.token.value"})
    assert resp.status_code == 401


@pytest.mark.parametrize("method,path,body", USERS_ROUTES, ids=ROUTE_IDS)
def test_no_credentials_rejected_401(client, method, path, body):
    """No Authorization header → 401 on EVERY users route.

    Pre-fix this returned 200 for the routes carrying the local dependency.
    """
    resp = _call(client, method, path, body)
    assert resp.status_code == 401, (
        f"{method} {path} answered {resp.status_code} with NO credentials. "
        "Anonymous access to a user-owned resource."
    )


@pytest.mark.parametrize("method,path,body", USERS_ROUTES, ids=ROUTE_IDS)
def test_user_id_query_param_is_not_authentication(client, user_a, method, path, body):
    """The exploit, per route: `?user_id=<victim>` must NOT authenticate.

    The deleted dependency read exactly this parameter and trusted it, so an
    anonymous caller who knew a user's UUID became that user — including for
    the PUT, an unauthenticated write to someone else's account.
    """
    victim_id = user_a["user"]["id"]
    sep = "&" if "?" in path else "?"
    resp = _call(client, method, f"{path}{sep}user_id={victim_id}", body)
    assert resp.status_code == 401, (
        f"{method} {path} answered {resp.status_code} for an ANONYMOUS caller "
        f"supplying ?user_id=<victim>. The query parameter is authenticating."
    )


def test_expired_token_rejected_401(client, user_a):
    """Expiry is enforced. The local verifier had no concept of expiry."""
    expired = auth_service.create_access_token(
        user_a["user"]["id"], user_a["user"]["email"], expires_delta=timedelta(seconds=-3600)
    )
    resp = client.get(PROFILE_ENDPOINT, headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401, "An EXPIRED token was accepted."


def test_forged_signature_rejected_401(client, user_a):
    """Signature is verified. The local verifier checked no signature at all."""
    forged = jwt.encode(
        {"sub": str(user_a["user"]["id"]), "email": user_a["user"]["email"]},
        "not-the-real-signing-key",
        algorithm=ALGORITHM,
    )
    resp = client.get(PROFILE_ENDPOINT, headers={"Authorization": f"Bearer {forged}"})
    assert resp.status_code == 401, "A token signed with the WRONG KEY was accepted."


# ---------------------------------------------------------------------------
# 3 — The structural guard. This is what makes the bug class unrepeatable.
# ---------------------------------------------------------------------------

def _dependency_callables(route):
    """Flatten a route's dependency tree into the callables it resolves."""
    found = []

    def walk(dependant):
        for sub in dependant.dependencies:
            if sub.call is not None:
                found.append(sub.call)
            walk(sub)

    walk(route.dependant)
    return found


def test_users_routes_use_canonical_auth():
    """Every users route authenticates via the ONE shared dependency.

    A future local `get_current_user` in users.py cannot come back without
    turning this red — which is the entire point (§9: one implementation).
    """
    routes = [r for r in users_module.router.routes if hasattr(r, "dependant")]
    assert routes, "No routes introspected — the guard would vacuously pass."

    offenders = []
    for route in routes:
        calls = _dependency_callables(route)
        if CANONICAL_GET_CURRENT_USER not in calls:
            offenders.append(f"{sorted(route.methods)} {route.path} — no canonical auth dependency")

        # A look-alike that is not the canonical object is exactly the defect.
        for call in calls:
            name = getattr(call, "__name__", "")
            if "current_user" in name and call is not CANONICAL_GET_CURRENT_USER:
                offenders.append(
                    f"{sorted(route.methods)} {route.path} — rogue auth dependency "
                    f"{getattr(call, '__module__', '?')}.{name}"
                )

    assert not offenders, "Routes not on the canonical auth dependency:\n  " + "\n  ".join(offenders)


def test_users_module_defines_no_local_auth():
    """users.py must not define its own auth resolver at module level."""
    local = users_module.__dict__.get("get_current_user")
    assert local is None or local is CANONICAL_GET_CURRENT_USER, (
        "users.py defines a LOCAL get_current_user again. Import the shared one "
        "from .auth instead (CLAUDE.md §9)."
    )


def test_no_route_accepts_a_user_id_parameter():
    """No users route may take `user_id` as a query/path parameter.

    Ownership comes from the authenticated principal, never from the request
    (§9: a caller-supplied user_id is a privilege-escalation bug).
    """
    offenders = []
    for route in users_module.router.routes:
        if not hasattr(route, "dependant"):
            continue
        params = route.dependant.query_params + route.dependant.path_params
        for p in params:
            if p.name == "user_id":
                offenders.append(f"{sorted(route.methods)} {route.path}")
    assert not offenders, f"Routes taking a caller-supplied user_id: {offenders}"


# ---------------------------------------------------------------------------
# 4 — /me consolidation: one profile endpoint, shape unchanged for its caller.
# ---------------------------------------------------------------------------

def test_duplicate_users_me_is_gone(client, headers_a):
    """/api/v0/users/me was a caller-less duplicate of /api/v0/auth/me."""
    resp = client.get("/api/v0/users/me", headers=headers_a)
    assert resp.status_code == 404, (
        f"Expected the duplicate /api/v0/users/me to be gone, got {resp.status_code}."
    )


def test_profile_contract_unchanged(client, headers_a):
    """Pin the surviving profile shape to what frontend/src/lib/auth.tsx reads."""
    resp = client.get(PROFILE_ENDPOINT, headers=headers_a)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    expected = {
        "id", "email", "full_name", "subscription_status", "started_trial_at",
        "started_pro_at", "trial_ends_at", "is_subscription_active",
        "subject_matters", "created_at",
    }
    assert expected <= set(body), f"Profile lost field(s): {expected - set(body)}"
    assert isinstance(body["subject_matters"], list)
    assert isinstance(body["is_subscription_active"], bool)


# ---------------------------------------------------------------------------
# 5 — Ownership (§9): scoped reads, cross-tenant → 404 (never 403).
# ---------------------------------------------------------------------------

def test_rubric_list_is_scoped_to_authenticated_user(client, headers_a, headers_b, rubric_a):
    """A's rubric appears in A's list and NOT in B's — with no user_id in sight."""
    rubric_id = rubric_a["rubric_id"]

    resp_a = client.get("/api/v0/users/me/rubrics", headers=headers_a)
    assert resp_a.status_code == 200, resp_a.text
    assert rubric_id in [str(r["id"]) for r in resp_a.json()["rubrics"]]

    resp_b = client.get("/api/v0/users/me/rubrics", headers=headers_b)
    assert resp_b.status_code == 200, resp_b.text
    assert rubric_id not in [str(r["id"]) for r in resp_b.json()["rubrics"]], (
        "Cross-tenant leak: user A's rubric appeared in user B's list."
    )


def test_cross_tenant_share_read_returns_404(client, headers_b, rubric_a):
    """B asking for the shares of A's rubric gets 404, never 403."""
    resp = client.get(f"/api/v0/users/rubrics/{rubric_a['rubric_id']}/shares", headers=headers_b)
    assert resp.status_code == 404, (
        f"Expected 404 for a cross-tenant rubric, got {resp.status_code} "
        "(403 would leak that the rubric exists)."
    )


def test_cross_tenant_share_create_returns_404(client, headers_b, user_a, rubric_a):
    """B cannot share A's rubric."""
    resp = client.post(
        f"/api/v0/users/rubrics/{rubric_a['rubric_id']}/share",
        json={"email": user_a["user"]["email"], "permission": "view"},
        headers=headers_b,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:160]}"


def test_cross_tenant_share_delete_returns_404(client, headers_b, rubric_a):
    """B cannot delete shares on A's rubric."""
    resp = client.delete(
        f"/api/v0/users/rubrics/{rubric_a['rubric_id']}/shares/{uuid4()}",
        headers=headers_b,
    )
    assert resp.status_code == 404, f"Expected 404, got {resp.status_code}: {resp.text[:160]}"


def test_graded_tests_list_is_scoped(client, headers_a, headers_b):
    """Both users get 200 and only ever their own rows."""
    for headers in (headers_a, headers_b):
        resp = client.get("/api/v0/users/me/graded-tests", headers=headers)
        assert resp.status_code == 200, resp.text
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# 6 — Boundary guard, from the codebase-wide search gate.
#
# `rubric_generator.py` declares five routes with NO auth dependency at all, on
# paths that COLLIDE with `rubric_management.py`'s authenticated routes. They are
# unreachable today only because main.py registers rubric_management FIRST and
# Starlette is first-match-wins — the same order-is-load-bearing property
# CLAUDE.md §8 already flags for rubric_extraction_jobs.
#
# That router is out of this PR's scope (the finding is SURFACED, not fixed).
# This test changes no behavior; it pins the safe state so that reordering the
# registrations — or deleting the shadowing routes — turns red here instead of
# silently publishing five unauthenticated rubric endpoints.
# ---------------------------------------------------------------------------

SHADOWED_RUBRIC_PATHS = [
    ("POST", "/api/v0/rubrics/save_ontology_draft", {"name": "x", "draft": {}}),
    ("PUT", f"/api/v0/rubrics/{uuid4()}/draft", {"draft": {}}),
    ("POST", f"/api/v0/rubrics/{uuid4()}/compile", {}),
    ("GET", f"/api/v0/rubrics/{uuid4()}", None),
    ("GET", "/api/v0/rubrics", None),
]


@pytest.mark.parametrize(
    "method,path,body", SHADOWED_RUBRIC_PATHS,
    ids=[f"{m} {p.split('?')[0]}" for m, p, _ in SHADOWED_RUBRIC_PATHS],
)
def test_rubric_paths_require_auth(client, method, path, body):
    resp = _call(client, method, path, body)
    assert resp.status_code == 401, (
        f"{method} {path} answered {resp.status_code} unauthenticated. The "
        "authenticated rubric_management route must shadow the auth-less "
        "rubric_generator route of the same path — check main.py registration order."
    )
