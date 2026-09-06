"""
W-2: every contract write kicks a plan build, after the commit, and nothing
about it reaches the teacher's response.

The kick itself is exercised at the service level (test_plan_kick.py); here
the three endpoints are pinned to CALL it with the right rubric — on success
only — and the responses are pinned to carry no plan vocabulary (W-3).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch
from uuid import UUID

from tests.api.conftest import MINIMAL_DRAFT


def _kick():
    return patch("app.api.v0.rubric_management.kick_plan_build", new_callable=AsyncMock)


def test_save_kicks_a_build_for_the_new_rubric(client, headers_a):
    with _kick() as kick:
        resp = client.post("/api/v0/rubrics/save_ontology_draft",
                           json={"name": "trigger test", "draft": MINIMAL_DRAFT,
                                 "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
                           headers=headers_a)
    assert resp.status_code == 201, resp.text
    rubric_id = resp.json()["rubric_id"]
    kick.assert_awaited_once_with(UUID(rubric_id))
    body = resp.text.lower()
    assert "grading_plan" not in body and "plan_version" not in body and "wording_source" not in body


def test_a_save_blocked_by_warnings_kicks_nothing(client, headers_a):
    with _kick() as kick:
        resp = client.post("/api/v0/rubrics/save_ontology_draft",
                           json={"name": "trigger test 2", "draft": MINIMAL_DRAFT},
                           headers=headers_a)
    assert resp.status_code in (200, 201)
    if resp.json().get("status") == "warnings_require_acknowledgment":
        kick.assert_not_awaited()
    else:                                              # no warnings on this draft: the kick fires
        kick.assert_awaited_once()


def test_update_and_compile_kick_for_the_existing_rubric(client, headers_a, rubric_a):
    rubric_id = rubric_a["rubric_id"]
    with _kick() as kick:
        resp = client.put(f"/api/v0/rubrics/{rubric_id}/draft",
                          json={"draft": MINIMAL_DRAFT,
                                "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
                          headers=headers_a)
    assert resp.status_code == 200, resp.text
    kick.assert_awaited_once_with(UUID(rubric_id))

    with _kick() as kick:
        resp = client.post(f"/api/v0/rubrics/{rubric_id}/compile",
                           json={"acknowledged_warning_ids": ["narrowness_issue:q1.c0"]},
                           headers=headers_a)
    assert resp.status_code == 200, resp.text
    if resp.json().get("status") == "success":
        kick.assert_awaited_once_with(UUID(rubric_id))
    else:
        kick.assert_not_awaited()


def test_the_rubric_detail_carries_no_plan(client, headers_a, rubric_a):
    resp = client.get(f"/api/v0/rubrics/{rubric_a['rubric_id']}", headers=headers_a)
    assert resp.status_code == 200
    keys = " ".join(resp.json().keys()).lower()
    assert "grading_plan" not in keys and "plan_version" not in keys
