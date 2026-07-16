"""
S2 auth tests — verifies ownership-scoping pattern on rubric endpoints.

Test numbering follows the PR spec §8:
  1  Unauthenticated → 401
  2  Invalid token → 401
  3  Own resource → 200
  4  Other user's resource → 404 (cross-tenant isolation)
  5  List is scoped (cross-tenant isolation)
  6  Ownership cannot be spoofed via request body (cross-tenant isolation)
  7  Stubbed grading endpoints return 501
"""


# ---------------------------------------------------------------------------
# Test 1 — Unauthenticated → 401
# ---------------------------------------------------------------------------

def test_1_unauthenticated_returns_401(client):
    resp = client.get("/api/v0/rubrics")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 2 — Invalid token → 401
# ---------------------------------------------------------------------------

def test_2_invalid_token_returns_401(client):
    resp = client.get("/api/v0/rubrics", headers={"Authorization": "Bearer garbage.token.value"})
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Test 3 — Own resource → 200
# ---------------------------------------------------------------------------

def test_3_own_resource_returns_200(client, headers_a, rubric_a):
    rubric_id = rubric_a["rubric_id"]
    resp = client.get(f"/api/v0/rubrics/{rubric_id}", headers=headers_a)
    assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Test 4 — Other user's resource → 404 (never 403 or 200)
# ---------------------------------------------------------------------------

def test_4_other_users_resource_returns_404(client, headers_b, rubric_a):
    rubric_id = rubric_a["rubric_id"]
    resp = client.get(f"/api/v0/rubrics/{rubric_id}", headers=headers_b)
    assert resp.status_code == 404, (
        f"Expected 404 but got {resp.status_code}. "
        "Cross-tenant isolation broken: user B can see user A's rubric."
    )


# ---------------------------------------------------------------------------
# Test 5 — List is scoped: user A's list contains A's rubric, not B's
# ---------------------------------------------------------------------------

def test_5_list_is_scoped(client, headers_a, headers_b, rubric_a):
    rubric_id = rubric_a["rubric_id"]

    # A's list must contain A's rubric
    resp_a = client.get("/api/v0/rubrics", headers=headers_a)
    assert resp_a.status_code == 200
    ids_a = [str(r["id"]) for r in resp_a.json().get("rubrics", [])]
    assert rubric_id in ids_a, "User A's rubric not in A's own list"

    # B's list must NOT contain A's rubric
    resp_b = client.get("/api/v0/rubrics", headers=headers_b)
    assert resp_b.status_code == 200
    ids_b = [str(r["id"]) for r in resp_b.json().get("rubrics", [])]
    assert rubric_id not in ids_b, (
        "Cross-tenant isolation broken: user A's rubric appeared in user B's list."
    )


# ---------------------------------------------------------------------------
# Test 6 — Ownership cannot be spoofed via request body
# ---------------------------------------------------------------------------

def test_6_ownership_not_spoofable(client, headers_a, user_b):
    from tests.api.conftest import MINIMAL_DRAFT

    # SaveOntologyDraftRequest has no user_id field — but verify that
    # the created rubric's user_id equals the authenticated user, not any
    # body-supplied value.  We confirm via: the rubric appears in A's list,
    # and NOT in B's list, even though we're authenticated as A.
    resp = client.post(
        "/api/v0/rubrics/save_ontology_draft",
        json={
            "name": "Spoof Attempt Rubric",
            "draft": MINIMAL_DRAFT,
            "acknowledged_warning_ids": ["narrowness_issue:q1.c0"],
        },
        headers=headers_a,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert "rubric_id" in data
    new_id = data["rubric_id"]

    # Created rubric must belong to user A (authenticated user)
    resp_a = client.get(f"/api/v0/rubrics/{new_id}", headers=headers_a)
    assert resp_a.status_code == 200, "Rubric not accessible by the authenticated creator"

    # Must NOT be accessible by user B
    resp_b = client.get(f"/api/v0/rubrics/{new_id}", headers={"Authorization": f"Bearer {user_b['access_token']}"})
    assert resp_b.status_code == 404, (
        "Cross-tenant isolation broken: user B can see user A's newly created rubric."
    )


# ---------------------------------------------------------------------------
# Test 7 — Stubbed grading endpoints return 501
# ---------------------------------------------------------------------------

def test_7_stubbed_grading_endpoints_return_501(client, headers_a):
    resp_list = client.get("/api/v0/grading/graded_tests", headers=headers_a)
    assert resp_list.status_code == 501, (
        f"Expected 501 from stubbed endpoint, got {resp_list.status_code}"
    )

    # Use a random UUID for the detail endpoint
    from uuid import uuid4
    fake_id = uuid4()
    resp_detail = client.get(f"/api/v0/grading/graded_test/{fake_id}", headers=headers_a)
    assert resp_detail.status_code == 501, (
        f"Expected 501 from stubbed endpoint, got {resp_detail.status_code}"
    )
