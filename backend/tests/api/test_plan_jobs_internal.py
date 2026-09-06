"""
/internal/plan-jobs/{id}/run — the Cloud Tasks target for plan builds.

Same contract as the other internal targets: 403 without the shared secret
(and without a valid OIDC bearer), 200 on every authorised call, and a
redelivery / unknown id is a no-op. No provider is involved: an unknown row
never reaches the builder.
"""
from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from pydantic import SecretStr

from app.config import settings as app_settings


def test_rejects_without_a_token(client):
    resp = client.post(f"/internal/plan-jobs/{uuid4()}/run")
    assert resp.status_code == 403


def test_rejects_a_wrong_token(client):
    with patch.object(app_settings, "internal_task_token", SecretStr("right")):
        resp = client.post(f"/internal/plan-jobs/{uuid4()}/run",
                           headers={"X-Internal-Token": "wrong"})
    assert resp.status_code == 403


def test_unknown_row_is_a_200_no_op(client):
    """A redelivery of an already-claimed row, or a row that no longer exists,
    must answer 200 — a non-2xx would make the queue redeliver work the row
    already accounts for."""
    job_id = uuid4()
    with patch.object(app_settings, "internal_task_token", SecretStr("sekret")):
        resp = client.post(f"/internal/plan-jobs/{job_id}/run",
                           headers={"X-Internal-Token": "sekret"})
    assert resp.status_code == 200
    assert resp.json() == {"job_id": str(job_id), "ran": False}


def test_the_route_is_hidden_from_the_schema(client):
    """W-3: the teacher never learns the concept — the plan surface has no
    public route and the internal one is not in the OpenAPI document."""
    schema = client.get("/openapi.json").json()
    assert not any("plan" in path.lower() for path in schema["paths"])
