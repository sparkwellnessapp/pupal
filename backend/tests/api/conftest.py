"""
API test fixtures for S2 auth tests.

Uses FastAPI TestClient (synchronous) against a real database.
Two users (A and B) are created once per session via the signup endpoint.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.api.auth_helpers import signup_verified


MINIMAL_DRAFT = {
    "schema_version": "2.0",
    "rubric_name": "Test Rubric",
    "subject": "computer_science",
    "total_points": "100",
    "questions": [
        {
            "question_id": "q1",
            "question_text": "What is a variable?",
            "total_points": "100",
            "criteria": [
                {
                    "criterion_id": "q1.c0",
                    "index": 0,
                    "description": "Correct definition",
                    "points": "100",
                }
            ],
            "sub_questions": [],
        }
    ],
}


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _signup(client: TestClient, tag: str) -> dict:
    """A usable, signed-in user.

    [024] Signup alone no longer returns a session — an address nobody proved
    gets none (owner ruling A4) — so this goes through the shared
    signup-then-verify helper. Every fixture below keeps the same shape it had.
    """
    return signup_verified(
        client,
        email=f"test_{tag}_{uuid4().hex[:8]}@s2test.com",
        full_name=f"Test {tag}",
    )


@pytest.fixture(scope="session")
def user_a(client):
    return _signup(client, "UserA")


@pytest.fixture(scope="session")
def user_b(client):
    return _signup(client, "UserB")


@pytest.fixture(scope="session")
def headers_a(user_a):
    return {"Authorization": f"Bearer {user_a['access_token']}"}


@pytest.fixture(scope="session")
def headers_b(user_b):
    return {"Authorization": f"Bearer {user_b['access_token']}"}


@pytest.fixture(scope="session")
def rubric_a(client, headers_a):
    """Create a rubric owned by user A. Returns the save response JSON."""
    resp = client.post(
        "/api/v0/rubrics/save_ontology_draft",
        json={
            "name": "User A Rubric",
            "draft": MINIMAL_DRAFT,
            "acknowledged_warning_ids": ["narrowness_issue:q1.c0"],
        },
        headers=headers_a,
    )
    assert resp.status_code == 201, f"Rubric creation failed: {resp.text}"
    data = resp.json()
    assert "rubric_id" in data, f"No rubric_id in response: {data}"
    return data


@pytest.fixture(scope="session")
def student_a(client, headers_a):
    """Create a student owned by user A. Returns the create response JSON."""
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": "תלמיד א", "notes": "test student"},
        headers=headers_a,
    )
    assert resp.status_code == 201, f"Student creation failed: {resp.text}"
    return resp.json()


@pytest.fixture(scope="session")
def class_a(client, headers_a):
    """Create a class owned by user A. Returns the create response JSON."""
    resp = client.post(
        "/api/v0/classroom/classes",
        json={"name": "כיתה א", "school_year": "2024"},
        headers=headers_a,
    )
    assert resp.status_code == 201, f"Class creation failed: {resp.text}"
    return resp.json()
