"""
S3 classroom tests — students, classes, membership, and dependency guards.

Test numbering follows the PR spec §7:
  1  Auth required → 401
  2  Create + read round-trip
  3  Cross-tenant isolation → 404
  4  Uniqueness conflict → 409; session recovers
  5  Membership both-ownership check → 404
  6  Membership idempotency → 204 (no-op)
  7  Delete dependency guard → 409
  8  Delete happy path → 204; resource gone
"""
from uuid import UUID, uuid4

import sqlalchemy


# ---------------------------------------------------------------------------
# Helper: sync psycopg2 engine for direct DB inserts in dependency-guard tests
# ---------------------------------------------------------------------------

def _sync_engine():
    from app.config import settings
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    return sqlalchemy.create_engine(sync_url)


# ---------------------------------------------------------------------------
# Test 1 — Auth required (401)
# ---------------------------------------------------------------------------

def test_1_unauthenticated_students_returns_401(client):
    assert client.get("/api/v0/classroom/students").status_code == 401


def test_1_unauthenticated_classes_returns_401(client):
    assert client.get("/api/v0/classroom/classes").status_code == 401


def test_1_unauthenticated_create_student_returns_401(client):
    assert client.post("/api/v0/classroom/students", json={"full_name": "x"}).status_code == 401


# ---------------------------------------------------------------------------
# Test 2 — Create + read round-trip
# ---------------------------------------------------------------------------

def test_2_student_create_and_fetch(client, headers_a):
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": "רחל כהן", "notes": "some notes"},
        headers=headers_a,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["full_name"] == "רחל כהן"
    assert data["notes"] == "some notes"
    assert "id" in data
    assert "user_id" not in data  # ownership never in response

    detail = client.get(f"/api/v0/classroom/students/{data['id']}", headers=headers_a)
    assert detail.status_code == 200
    assert detail.json()["full_name"] == "רחל כהן"
    assert "classes" in detail.json()


def test_2_class_create_and_fetch(client, headers_a):
    resp = client.post(
        "/api/v0/classroom/classes",
        json={"name": "כיתה ז'", "school_year": "2025"},
        headers=headers_a,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "כיתה ז'"
    assert data["school_year"] == "2025"
    assert data["student_count"] == 0

    classes_resp = client.get("/api/v0/classroom/classes", headers=headers_a)
    assert classes_resp.status_code == 200
    ids = [c["id"] for c in classes_resp.json()["classes"]]
    assert data["id"] in ids


# ---------------------------------------------------------------------------
# Test 3 — Cross-tenant isolation
# ---------------------------------------------------------------------------

def test_3_student_cross_tenant_detail_returns_404(client, headers_b, student_a):
    resp = client.get(f"/api/v0/classroom/students/{student_a['id']}", headers=headers_b)
    assert resp.status_code == 404, (
        "Cross-tenant isolation broken: user B can see user A's student."
    )


def test_3_class_cross_tenant_detail_returns_404(client, headers_b, class_a):
    resp = client.get(f"/api/v0/classroom/classes/{class_a['id']}", headers=headers_b)
    assert resp.status_code == 404, (
        "Cross-tenant isolation broken: user B can see user A's class."
    )


def test_3_student_list_is_scoped(client, headers_a, headers_b, student_a):
    ids_b = [s["id"] for s in client.get("/api/v0/classroom/students", headers=headers_b).json()["students"]]
    assert student_a["id"] not in ids_b, (
        "Cross-tenant isolation broken: user A's student appeared in user B's list."
    )


def test_3_class_list_is_scoped(client, headers_a, headers_b, class_a):
    ids_b = [c["id"] for c in client.get("/api/v0/classroom/classes", headers=headers_b).json()["classes"]]
    assert class_a["id"] not in ids_b, (
        "Cross-tenant isolation broken: user A's class appeared in user B's list."
    )


# ---------------------------------------------------------------------------
# Test 4 — Uniqueness conflict → 409; session recovers
# ---------------------------------------------------------------------------

def test_4_duplicate_student_name_returns_409(client, headers_a, student_a):
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": student_a["full_name"]},
        headers=headers_a,
    )
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    # Session must recover — a valid create in the same session must succeed
    resp2 = client.post(
        "/api/v0/classroom/students",
        json={"full_name": f"שם ייחודי {uuid4().hex[:6]}"},
        headers=headers_a,
    )
    assert resp2.status_code == 201, f"Session did not recover after 409: {resp2.text}"


def test_4_duplicate_class_name_returns_409(client, headers_a, class_a):
    resp = client.post(
        "/api/v0/classroom/classes",
        json={"name": class_a["name"]},
        headers=headers_a,
    )
    assert resp.status_code == 409, f"Expected 409, got {resp.status_code}: {resp.text}"

    resp2 = client.post(
        "/api/v0/classroom/classes",
        json={"name": f"כיתה ייחודית {uuid4().hex[:6]}"},
        headers=headers_a,
    )
    assert resp2.status_code == 201, f"Session did not recover after 409: {resp2.text}"


# ---------------------------------------------------------------------------
# Test 5 — Membership both-ownership check → 404
# ---------------------------------------------------------------------------

def test_5_membership_cross_tenant(client, headers_a, headers_b, student_a, class_a):
    # Create a class owned by user B
    resp_b_class = client.post(
        "/api/v0/classroom/classes",
        json={"name": f"כיתה של ב {uuid4().hex[:6]}"},
        headers=headers_b,
    )
    assert resp_b_class.status_code == 201
    b_class_id = resp_b_class.json()["id"]

    # B cannot add A's student to B's own class (student not owned by B)
    resp = client.post(
        f"/api/v0/classroom/classes/{b_class_id}/students",
        json={"student_id": student_a["id"]},
        headers=headers_b,
    )
    assert resp.status_code == 404, (
        f"Cross-tenant isolation broken: user B added user A's student. Got {resp.status_code}"
    )

    # A cannot add A's student to B's class (class not owned by A)
    resp = client.post(
        f"/api/v0/classroom/classes/{b_class_id}/students",
        json={"student_id": student_a["id"]},
        headers=headers_a,
    )
    assert resp.status_code == 404, (
        f"Cross-tenant isolation broken: user A added to user B's class. Got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# Test 6 — Membership idempotency
# ---------------------------------------------------------------------------

def test_6_membership_add_idempotent(client, headers_a, student_a, class_a):
    url = f"/api/v0/classroom/classes/{class_a['id']}/students"
    body = {"student_id": student_a["id"]}

    assert client.post(url, json=body, headers=headers_a).status_code == 204
    assert client.post(url, json=body, headers=headers_a).status_code == 204  # no-op, not 409


def test_6_membership_remove_idempotent(client, headers_a, student_a, class_a):
    # Ensure the student is a member first
    url = f"/api/v0/classroom/classes/{class_a['id']}/students"
    client.post(url, json={"student_id": student_a["id"]}, headers=headers_a)

    remove_url = f"{url}/{student_a['id']}"
    assert client.delete(remove_url, headers=headers_a).status_code == 204
    assert client.delete(remove_url, headers=headers_a).status_code == 204  # no-op, not 404


# ---------------------------------------------------------------------------
# Test 7 — Delete dependency guard → 409
# ---------------------------------------------------------------------------

def test_7a_class_delete_guard(client, headers_a, class_a, rubric_a, user_a):
    """Insert a GradingBatch row directly, then assert DELETE /classes/{id} returns 409."""
    from app.models.grading import GradingBatch

    batch_id = uuid4()
    engine = _sync_engine()
    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(GradingBatch.__table__).values(
                id=batch_id,
                user_id=UUID(user_a["user"]["id"]),
                rubric_id=UUID(rubric_a["rubric_id"]),
                rubric_contract_version=rubric_a.get("contract_version", "test-v1"),
                class_id=UUID(class_a["id"]),
                status="pending",
            )
        )

    try:
        resp = client.delete(f"/api/v0/classroom/classes/{class_a['id']}", headers=headers_a)
        assert resp.status_code == 409, (
            f"Expected 409 (class has grading_batches), got {resp.status_code}: {resp.text}"
        )
    finally:
        with engine.begin() as conn:
            conn.execute(
                sqlalchemy.delete(GradingBatch.__table__).where(
                    GradingBatch.__table__.c.id == batch_id
                )
            )
        engine.dispose()


def test_7b_student_delete_guard(client, headers_a, student_a, rubric_a, user_a):
    """Insert Transcription + GradedTest rows directly, then assert DELETE /students/{id} returns 409."""
    from app.models.transcription import Transcription
    from app.models.grading import GradedTest

    transcription_id = uuid4()
    graded_test_id = uuid4()
    engine = _sync_engine()

    with engine.begin() as conn:
        conn.execute(
            sqlalchemy.insert(Transcription.__table__).values(
                id=transcription_id,
                user_id=UUID(user_a["user"]["id"]),
                rubric_id=UUID(rubric_a["rubric_id"]),
                student_id=None,  # constraint: student_id must be NULL when status='transcribed'
                gcs_uri="gs://test-bucket/test-path.pdf",
                gcs_bucket="test-bucket",
                gcs_object_path="test-path.pdf",
                filename="test.pdf",
                draft_json=[],  # empty list, psycopg2 serializes JSONB automatically
                status="transcribed",
            )
        )
        conn.execute(
            sqlalchemy.insert(GradedTest.__table__).values(
                id=graded_test_id,
                user_id=UUID(user_a["user"]["id"]),
                rubric_id=UUID(rubric_a["rubric_id"]),
                transcription_id=transcription_id,
                student_id=UUID(student_a["id"]),
                rubric_contract_version=rubric_a.get("contract_version", "test-v1"),
                student_name=student_a["full_name"],
                status="pending",
                llm_calls_count=0,
                grading_duration_ms=0,
            )
        )

    try:
        resp = client.delete(f"/api/v0/classroom/students/{student_a['id']}", headers=headers_a)
        assert resp.status_code == 409, (
            f"Expected 409 (student has graded_tests), got {resp.status_code}: {resp.text}"
        )
    finally:
        with engine.begin() as conn:
            conn.execute(
                sqlalchemy.delete(GradedTest.__table__).where(
                    GradedTest.__table__.c.id == graded_test_id
                )
            )
            conn.execute(
                sqlalchemy.delete(Transcription.__table__).where(
                    Transcription.__table__.c.id == transcription_id
                )
            )
        engine.dispose()


# ---------------------------------------------------------------------------
# Test 8 — Delete happy path → 204; resource gone
# ---------------------------------------------------------------------------

def test_8_student_delete_happy_path(client, headers_a):
    resp = client.post(
        "/api/v0/classroom/students",
        json={"full_name": f"למחוק {uuid4().hex[:6]}"},
        headers=headers_a,
    )
    assert resp.status_code == 201
    student_id = resp.json()["id"]

    assert client.delete(f"/api/v0/classroom/students/{student_id}", headers=headers_a).status_code == 204
    assert client.get(f"/api/v0/classroom/students/{student_id}", headers=headers_a).status_code == 404


def test_8_class_delete_happy_path(client, headers_a):
    resp = client.post(
        "/api/v0/classroom/classes",
        json={"name": f"למחוק {uuid4().hex[:6]}"},
        headers=headers_a,
    )
    assert resp.status_code == 201
    class_id = resp.json()["id"]

    assert client.delete(f"/api/v0/classroom/classes/{class_id}", headers=headers_a).status_code == 204
    assert client.get(f"/api/v0/classroom/classes/{class_id}", headers=headers_a).status_code == 404


def test_8_delete_cascades_class_memberships(client, headers_a):
    # Create a student + class, add student to class, delete student → class still exists, membership gone
    s = client.post("/api/v0/classroom/students", json={"full_name": f"tmp {uuid4().hex[:6]}"}, headers=headers_a).json()
    c = client.post("/api/v0/classroom/classes", json={"name": f"tmp {uuid4().hex[:6]}"}, headers=headers_a).json()
    client.post(f"/api/v0/classroom/classes/{c['id']}/students", json={"student_id": s["id"]}, headers=headers_a)

    # Delete student
    client.delete(f"/api/v0/classroom/students/{s['id']}", headers=headers_a)

    # Class still exists; its member list is now empty
    detail = client.get(f"/api/v0/classroom/classes/{c['id']}", headers=headers_a).json()
    member_ids = [m["id"] for m in detail.get("students", [])]
    assert s["id"] not in member_ids
