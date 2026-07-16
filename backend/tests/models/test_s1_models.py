"""
S1 model tests — verifies the ORM layer mirrors migration 008 exactly.

Test numbering follows the PR spec §8:
  1  App boots (mapper configuration valid)
  2a-f  Round-trip for each of the six new/rebuilt models
  3  Relationships traverse in both directions
  4  Self-referential revision chain traverses both directions
  5  M:N via ClassMembership association object
  6  Unique constraints fire (IntegrityError on duplicate)
  7  CHECK constraint fires — transcriptions_approval_consistency (DB-level)
  8  Partial unique index fires — idx_graded_tests_one_leaf_per_chain (DB-level)
"""
import uuid
import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.exc import IntegrityError

from app.models import (
    User, Rubric, Student, Class, ClassMembership,
    Transcription, GradingBatch, GradedTest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_user(session, email=None):
    u = User(
        email=email or f"test+{uuid.uuid4().hex[:8]}@example.com",
        full_name="Test User",
        password_hash="x",
    )
    session.add(u)
    session.flush()
    return u


def make_rubric(session, user):
    r = Rubric(
        user_id=user.id,
        name="Test Rubric",
        draft_json={"schema_version": "2.0", "questions": []},
        contract_json={"schema_version": "2.0", "questions": []},
        contract_version="v1",
    )
    session.add(r)
    session.flush()
    return r


def make_student(session, user, full_name=None):
    s = Student(
        user_id=user.id,
        full_name=full_name or f"Student {uuid.uuid4().hex[:6]}",
    )
    session.add(s)
    session.flush()
    return s


def make_transcription(session, user, rubric, student=None):
    """
    Passing a student yields an APPROVED transcription — not a 'transcribed' one.

    LCY-1 (transcriptions_approval_consistency, migration 008): a transcription
    is student-less until it is approved. 'transcribed' REQUIRES student_id IS
    NULL; 'approved' REQUIRES student_id, contract_json and approved_at all set.
    So a 'transcribed' row carrying a student is not merely unusual — the DB
    CHECK forbids it, and student.transcriptions can only ever contain approved
    rows.
    """
    approved = student is not None
    t = Transcription(
        user_id=user.id,
        rubric_id=rubric.id,
        student_id=student.id if approved else None,
        gcs_uri="gs://bucket/object",
        gcs_bucket="bucket",
        gcs_object_path="object",
        draft_json={"answers": []},
        contract_json={"answers": []} if approved else None,
        approved_at=datetime.now(timezone.utc) if approved else None,
        status="approved" if approved else "transcribed",
    )
    session.add(t)
    session.flush()
    return t


def make_graded_test(session, user, rubric, transcription, student, batch=None):
    gt = GradedTest(
        user_id=user.id,
        rubric_id=rubric.id,
        transcription_id=transcription.id,
        student_id=student.id,
        batch_id=batch.id if batch else None,
        rubric_contract_version="v1",
        student_name=student.full_name,
        status="pending",
    )
    session.add(gt)
    session.flush()
    return gt


# ---------------------------------------------------------------------------
# Test 1: App boots — mapper configuration valid
# ---------------------------------------------------------------------------

def test_app_boots():
    import app.main  # noqa: F401 — mapper config is finalized on import


# ---------------------------------------------------------------------------
# Test 2: Round-trips for each of the six models
# ---------------------------------------------------------------------------

def test_student_round_trip(session):
    user = make_user(session)
    s = Student(user_id=user.id, full_name="Alice", notes="top student")
    session.add(s)
    session.commit()

    fetched = session.get(Student, s.id)
    assert fetched.full_name == "Alice"
    assert fetched.notes == "top student"
    assert fetched.user_id == user.id


def test_class_round_trip(session):
    user = make_user(session)
    c = Class(user_id=user.id, name="Class A", school_year="2024")
    session.add(c)
    session.commit()

    fetched = session.get(Class, c.id)
    assert fetched.name == "Class A"
    assert fetched.school_year == "2024"


def test_class_membership_round_trip(session):
    user = make_user(session)
    student = make_student(session, user)
    school_class = Class(user_id=user.id, name="Class B")
    session.add(school_class)
    session.flush()

    cm = ClassMembership(class_id=school_class.id, student_id=student.id)
    session.add(cm)
    session.commit()

    fetched = session.get(ClassMembership, {"class_id": school_class.id, "student_id": student.id})
    assert fetched is not None
    assert fetched.class_id == school_class.id
    assert fetched.student_id == student.id


def test_transcription_round_trip(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    t = Transcription(
        user_id=user.id,
        rubric_id=rubric.id,
        gcs_uri="gs://b/o",
        gcs_bucket="b",
        gcs_object_path="o",
        filename="test.pdf",
        draft_json={"answers": [{"q": 1, "text": "hello"}]},
        status="transcribed",
    )
    session.add(t)
    session.commit()

    fetched = session.get(Transcription, t.id)
    assert fetched.filename == "test.pdf"
    assert fetched.status == "transcribed"
    assert fetched.draft_json == {"answers": [{"q": 1, "text": "hello"}]}


def test_grading_batch_round_trip(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    batch = GradingBatch(
        user_id=user.id,
        rubric_id=rubric.id,
        rubric_contract_version="v1",
        name="Batch 1",
        status="pending",
    )
    session.add(batch)
    session.commit()

    fetched = session.get(GradingBatch, batch.id)
    assert fetched.name == "Batch 1"
    assert fetched.status == "pending"
    assert fetched.rubric_contract_version == "v1"


def test_graded_test_round_trip(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    student = make_student(session, user)
    transcription = make_transcription(session, user, rubric)

    gt = GradedTest(
        user_id=user.id,
        rubric_id=rubric.id,
        transcription_id=transcription.id,
        student_id=student.id,
        rubric_contract_version="v1",
        student_name=student.full_name,
        status="pending",
        llm_calls_count=0,
        grading_duration_ms=0,
    )
    session.add(gt)
    session.commit()

    fetched = session.get(GradedTest, gt.id)
    assert fetched.status == "pending"
    assert fetched.student_name == student.full_name
    assert fetched.total_score is None
    assert fetched.llm_calls_count == 0


# ---------------------------------------------------------------------------
# Test 3: Relationships traverse in both directions
# ---------------------------------------------------------------------------

def test_relationships_traverse(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    student = make_student(session, user)
    transcription = make_transcription(session, user, rubric, student)
    gt = make_graded_test(session, user, rubric, transcription, student)
    session.commit()

    session.expire_all()

    # User → children
    assert any(s.id == student.id for s in user.students)
    assert any(t.id == transcription.id for t in user.transcriptions)
    assert any(g.id == gt.id for g in user.graded_tests)

    # Reverse (child → user)
    assert student.user.id == user.id
    assert transcription.user.id == user.id
    assert gt.user.id == user.id

    # Rubric → graded_tests / transcriptions
    assert any(g.id == gt.id for g in rubric.graded_tests)
    assert any(t.id == transcription.id for t in rubric.transcriptions)

    # Student → transcriptions / graded_tests
    assert any(t.id == transcription.id for t in student.transcriptions)
    assert any(g.id == gt.id for g in student.graded_tests)

    # GradedTest → transcription (many-to-one)
    assert gt.transcription.id == transcription.id
    assert gt.student.id == student.id
    assert gt.rubric.id == rubric.id


# ---------------------------------------------------------------------------
# Test 4: Self-referential revision chain traverses both directions
# ---------------------------------------------------------------------------

def test_revision_chain(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    student = make_student(session, user)

    # R1: the original graded test (leaf: regraded_to_id is NULL)
    transcription1 = make_transcription(session, user, rubric)
    r1 = make_graded_test(session, user, rubric, transcription1, student)

    # R2: the regrade of R1 — needs a second transcription to satisfy
    # the partial unique index (transcription_id, rubric_id) WHERE regraded_to_id IS NULL
    transcription2 = make_transcription(session, user, rubric)
    r2 = GradedTest(
        user_id=user.id,
        rubric_id=rubric.id,
        transcription_id=transcription2.id,
        student_id=student.id,
        rubric_contract_version="v1",
        student_name=student.full_name,
        status="pending",
        regraded_from_id=r1.id,
    )
    session.add(r2)
    session.flush()

    # Link R1 → R2 (mark R1 as superseded)
    r1.regraded_to_id = r2.id
    session.flush()
    session.commit()

    session.expire_all()

    r1_fresh = session.get(GradedTest, r1.id)
    r2_fresh = session.get(GradedTest, r2.id)

    assert r1_fresh.regraded_to.id == r2_fresh.id, "R1.regraded_to should be R2"
    assert r2_fresh.regraded_from.id == r1_fresh.id, "R2.regraded_from should be R1"


# ---------------------------------------------------------------------------
# Test 5: M:N via ClassMembership association object
# ---------------------------------------------------------------------------

def test_class_membership_m2n(session):
    user = make_user(session)
    student = make_student(session, user, full_name="Bob")
    school_class = Class(user_id=user.id, name="Math 101")
    session.add(school_class)
    session.flush()

    cm = ClassMembership(class_id=school_class.id, student_id=student.id)
    session.add(cm)
    session.commit()

    session.expire_all()

    assert school_class.memberships[0].student.id == student.id
    assert student.class_memberships[0].school_class.id == school_class.id


# ---------------------------------------------------------------------------
# Test 6: Unique constraints fire
# ---------------------------------------------------------------------------

def test_student_unique_constraint(session):
    user = make_user(session)
    session.add(Student(user_id=user.id, full_name="Duplicate"))
    session.flush()

    session.add(Student(user_id=user.id, full_name="Duplicate"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


def test_class_unique_constraint(session):
    user = make_user(session)
    session.add(Class(user_id=user.id, name="Duplicate Class"))
    session.flush()

    session.add(Class(user_id=user.id, name="Duplicate Class"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# ---------------------------------------------------------------------------
# Test 7: DB-level CHECK — transcriptions_approval_consistency
# ---------------------------------------------------------------------------

def test_transcription_approval_check(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    student = make_student(session, user)

    # status='approved' but contract_json=NULL violates the CHECK constraint
    bad = Transcription(
        user_id=user.id,
        rubric_id=rubric.id,
        student_id=student.id,
        gcs_uri="gs://b/o",
        gcs_bucket="b",
        gcs_object_path="o",
        draft_json={"answers": []},
        contract_json=None,       # violates: approved requires contract_json NOT NULL
        approved_at=None,         # also violates: approved requires approved_at NOT NULL
        status="approved",
    )
    session.add(bad)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()


# ---------------------------------------------------------------------------
# Test 8: DB-level partial unique index — idx_graded_tests_one_leaf_per_chain
# ---------------------------------------------------------------------------

def test_graded_test_leaf_partial_index(session):
    user = make_user(session)
    rubric = make_rubric(session, user)
    student = make_student(session, user)
    transcription = make_transcription(session, user, rubric)

    # First graded test — leaf (regraded_to_id IS NULL)
    gt1 = make_graded_test(session, user, rubric, transcription, student)
    session.flush()

    # Second graded test with same (transcription_id, rubric_id) and regraded_to_id IS NULL
    # violates the partial unique index
    gt2 = GradedTest(
        user_id=user.id,
        rubric_id=rubric.id,
        transcription_id=transcription.id,
        student_id=student.id,
        rubric_contract_version="v1",
        student_name=student.full_name,
        status="pending",
    )
    session.add(gt2)
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()
