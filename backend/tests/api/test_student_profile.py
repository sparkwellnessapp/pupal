"""
Student profile (Part A) — the one query, its endpoint, the roster count and
the interim delete, against the Vivi-Test database with real auth and real
rows. No mocks (PR_student_profile.md §8.1).

Named invariants under test:
  LST-1 ApprovedOnly       only status='approved' rows appear or are counted
  LST-2 OneRowPerChain     chain = (transcription_id, rubric_id); the row shown is
                           the approved row with the greatest approved_at
  LST-3 SingleGradeSource  displayed totals come from the dedicated columns, and
                           for every approved row those equal the contract's
  LST-4 CountEqualsList    badge, profile count and len(list) share ONE
                           definition; the roster count is ONE grouped statement
  LST-5 OwnerScoped        every read is scoped by current_user.id; cross-tenant
                           is 404; a foreign graded_test never leaks
  (M-A2's interim 409 `student_has_data` is replaced by Part B's purge; its
   cases live on in tests/api/test_student_purge_endpoints.py)
  OD-3 / UI-4              `notes` is gone from every response and ignored on input
"""
from __future__ import annotations

import asyncio
import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import event, text


SIGNED = "/api/v0/classroom/students/{id}/signed-tests"


# ---------------------------------------------------------------------------
# row helpers — the same session shape as test_returned_exam_endpoints.py
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _session():
    from app.database import AsyncSessionLocal, engine

    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            yield db
    finally:
        await engine.dispose(close=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _student(client, headers, name: str) -> str:
    resp = client.post("/api/v0/classroom/students", json={"full_name": name}, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _rubric(user_id: str, name: str) -> str:
    from app.models.grading import Rubric

    async with _session() as db:
        r = Rubric(user_id=uuid.UUID(user_id), name=name, contract_version="cv-test",
                   contract_json={"contract_version": "cv-test"})
        db.add(r)
        await db.commit()
        return str(r.id)


async def _batch(user_id: str, rubric_id: str, *, name=None, created_at=None,
                 class_id=None, stamp_default=None) -> str:
    from app.models.grading import GradingBatch

    async with _session() as db:
        b = GradingBatch(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            rubric_contract_version="cv-test", name=name,
            class_id=uuid.UUID(class_id) if class_id else None,
            status="in_progress", test_count=0,
            stamp_position_default=stamp_default,
            started_at=_now(), created_at=created_at or _now())
        db.add(b)
        await db.commit()
        return str(b.id)


async def _transcription(user_id: str, rubric_id: str, *, batch_id=None,
                         created_at=None, page_count=1) -> str:
    """`status='transcribed'` keeps `student_id` NULL (the 008 CHECK); the
    profile keys on `graded_tests.student_id` (FA-2), never on this column."""
    from app.models.transcription import Transcription

    async with _session() as db:
        t = Transcription(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            batch_id=uuid.UUID(batch_id) if batch_id else None,
            gcs_uri="gs://test-bucket/x.pdf", gcs_bucket="test-bucket",
            gcs_object_path="tests/x.pdf", filename="x.pdf",
            draft_json={"student_name_suggestion": None, "page_count": page_count,
                        "answers": [], "annotations": []},
            status="transcribed", created_at=created_at or _now())
        db.add(t)
        await db.commit()
        return str(t.id)


async def _approved_transcription(user_id: str, rubric_id: str, student_id: str) -> str:
    """An APPROVED transcription carries the student (gate-assigned) — the one
    other row kind that references her, for the interim delete guard."""
    from app.models.transcription import Transcription

    async with _session() as db:
        t = Transcription(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            student_id=uuid.UUID(student_id),
            gcs_uri="gs://test-bucket/x.pdf", gcs_bucket="test-bucket",
            gcs_object_path="tests/x.pdf", filename="x.pdf",
            draft_json={"page_count": 1, "answers": [], "annotations": []},
            contract_json={"answers": []}, approved_at=_now(),
            status="approved")
        db.add(t)
        await db.commit()
        return str(t.id)


def _draft(stamp=None) -> dict:
    from app.schemas.graded_test_draft import GradedTestOverrides, StampPosition
    from app.services.returned_exam import OVERLAY_KEY

    overlay = GradedTestOverrides(
        stamp_position=StampPosition(**stamp) if stamp else None)
    return {
        "rubric_contract_version": "rc", "transcription_contract_version": "tc",
        "model_version": "m", "prompt_version": "p", "plan_version": None,
        "scope_outcomes": [], "llm_calls_count": 1, "grading_duration_ms": 1,
        "total_input_tokens": 1, "total_output_tokens": 1,
        OVERLAY_KEY: json.loads(overlay.model_dump_json()),
    }


async def _graded(user_id: str, rubric_id: str, transcription_id: str, student_id: str, *,
                  status: str, batch_id=None, approved_at=None,
                  score="85.5", possible="100", stamp=None,
                  supersedes: str | None = None, row_id: str | None = None) -> str:
    """One graded_tests row of the given status, shaped so the 008 CHECK and
    RGC-1 accept it. `supersedes` links a chain the way `extend_chain` does:
    the predecessor's `regraded_to_id` is pointed at the NEW id first (the FK
    is deferrable), then the successor is inserted, so the one-leaf-per-chain
    index never sees two leaves."""
    from app.models.grading import GradedTest

    new_id = uuid.UUID(row_id) if row_id else uuid.uuid4()
    draft = contract = None
    approved = None
    error = None
    if status == "approved":
        approved = approved_at or _now()
        draft = _draft(stamp)
        contract = {
            "contract_version": str(uuid.uuid4()),
            "rubric_contract_version": "rc", "transcription_contract_version": "tc",
            "model_version": "m", "prompt_version": "p",
            "total_score": score, "total_possible": possible,
            "percentage": "0", "scope_outcomes": [],
            "approved_at": approved.isoformat(),
        }
    elif status == "draft":
        draft = _draft(stamp)
    elif status == "failed":
        error = "boom"

    async with _session() as db:
        if supersedes:
            await db.execute(
                text("UPDATE graded_tests SET regraded_to_id = :new WHERE id = :old"),
                {"new": new_id, "old": uuid.UUID(supersedes)})
        row = GradedTest(
            id=new_id,
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            batch_id=uuid.UUID(batch_id) if batch_id else None,
            transcription_id=uuid.UUID(transcription_id),
            student_id=uuid.UUID(student_id),
            rubric_contract_version="rc", status=status,
            student_name="x", draft_json=draft, contract_json=contract,
            approved_at=approved, error_message=error,
            total_score=Decimal(score) if status == "approved" else None,
            total_possible=Decimal(possible) if status == "approved" else None,
            regraded_from_id=uuid.UUID(supersedes) if supersedes else None)
        db.add(row)
        await db.commit()
        return str(new_id)


def _ids(payload: dict) -> list[str]:
    return [t["graded_test_id"] for t in payload["signed_tests"]]


def _get(client, headers, student_id: str) -> dict:
    resp = client.get(SIGNED.format(id=student_id), headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _roster_count(client, headers, student_id: str) -> int:
    resp = client.get("/api/v0/classroom/students", headers=headers)
    assert resp.status_code == 200, resp.text
    (item,) = [s for s in resp.json()["students"] if s["id"] == student_id]
    return item["signed_tests_count"]


# ---------------------------------------------------------------------------
# LST-1 / LST-2 — what counts as the student's test
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_chain_with_a_draft_leaf_shows_the_approved_row_once(client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid)
        t = await _transcription(uid, rid, batch_id=b)
        r1 = await _graded(uid, rid, t, sid, status="approved", batch_id=b)
        r2 = await _graded(uid, rid, t, sid, status="draft", batch_id=b, supersedes=r1)
        return r1, r2
    r1, r2 = asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    assert _ids(payload) == [r1]
    assert r2 not in _ids(payload)
    assert payload["signed_tests_count"] == 1
    assert _roster_count(client, headers_a, sid) == 1


@pytest.mark.integration
def test_a_reapproved_chain_shows_only_its_latest_approved_row(client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid)
        t = await _transcription(uid, rid, batch_id=b)
        r1 = await _graded(uid, rid, t, sid, status="approved", batch_id=b,
                           approved_at=_now() - timedelta(hours=2), score="70")
        r2 = await _graded(uid, rid, t, sid, status="approved", batch_id=b,
                           approved_at=_now() - timedelta(hours=1), score="92",
                           supersedes=r1)
        return r1, r2
    r1, r2 = asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    assert _ids(payload) == [r2]
    assert Decimal(payload["signed_tests"][0]["total_score"]) == Decimal("92")
    assert payload["signed_tests_count"] == 1


@pytest.mark.integration
def test_unapproved_statuses_are_absent_and_uncounted(client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid)
        for status in ("draft", "failed", "pending", "grading"):
            t = await _transcription(uid, rid, batch_id=b)
            await _graded(uid, rid, t, sid, status=status, batch_id=b)
    asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    assert payload["signed_tests"] == []
    assert payload["signed_tests_count"] == 0
    assert payload["truncated"] is False
    assert _roster_count(client, headers_a, sid) == 0
    detail = client.get(f"/api/v0/classroom/students/{sid}", headers=headers_a).json()
    assert detail["signed_tests_count"] == 0


@pytest.mark.integration
def test_two_scans_are_two_rows_and_one_scan_under_two_rubrics_is_two_rows(
        client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        rid2 = await _rubric(uid, "מחוון שני")
        b = await _batch(uid, rid)
        t1 = await _transcription(uid, rid, batch_id=b)
        t2 = await _transcription(uid, rid, batch_id=b)
        a = await _graded(uid, rid, t1, sid, status="approved", batch_id=b)
        c = await _graded(uid, rid, t2, sid, status="approved", batch_id=b)
        # The same physical scan graded under a second rubric is a second chain.
        d = await _graded(uid, rid2, t1, sid, status="approved", batch_id=b)
        return {a, c, d}
    expected = asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    assert set(_ids(payload)) == expected
    assert payload["signed_tests_count"] == 3 == len(payload["signed_tests"])


# ---------------------------------------------------------------------------
# OD-6 / M-A3 — ordering
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_rows_order_by_upload_date_newest_first_with_the_batchless_fallback_and_stable_ties(
        client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")
    now = _now()

    async def seed():
        old_b = await _batch(uid, rid, created_at=now - timedelta(days=3))
        new_b = await _batch(uid, rid, created_at=now - timedelta(days=1))
        t_old = await _transcription(uid, rid, batch_id=old_b, created_at=now - timedelta(days=3))
        t_new = await _transcription(uid, rid, batch_id=new_b, created_at=now - timedelta(days=1))
        # Batch-less: the upload date falls back to the scan's own created_at.
        t_mid = await _transcription(uid, rid, created_at=now - timedelta(days=2))
        old = await _graded(uid, rid, t_old, sid, status="approved", batch_id=old_b)
        new = await _graded(uid, rid, t_new, sid, status="approved", batch_id=new_b)
        mid = await _graded(uid, rid, t_mid, sid, status="approved")
        # A tie on upload date (same batch) breaks on approved_at DESC, then id.
        t_tie = await _transcription(uid, rid, batch_id=new_b, created_at=now - timedelta(days=1))
        tie_earlier = await _graded(uid, rid, t_tie, sid, status="approved", batch_id=new_b,
                                    approved_at=now - timedelta(hours=5))
        return old, new, mid, tie_earlier
    old, new, mid, tie_earlier = asyncio.run(seed())

    ids = _ids(_get(client, headers_a, sid))
    assert ids == [new, tie_earlier, mid, old], ids
    # `uploaded_at` on the wire is the batch's creation, or the scan's when batch-less.
    payload = _get(client, headers_a, sid)
    by_id = {t["graded_test_id"]: t for t in payload["signed_tests"]}
    assert by_id[mid]["exam"]["batch_id"] is None
    assert by_id[mid]["exam"]["uploaded_at"] is not None
    assert by_id[new]["exam"]["uploaded_at"] > by_id[mid]["exam"]["uploaded_at"] \
        > by_id[old]["exam"]["uploaded_at"]


# ---------------------------------------------------------------------------
# §5.2 — the payload shape a row renders from
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_the_row_payload_carries_the_event_the_approval_the_grade_and_the_thumbnail(
        client, headers_a, user_a, rubric_a, class_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")
    approved_at = _now() - timedelta(minutes=30)

    async def seed():
        b = await _batch(uid, rid, name="מבחן מחצית", class_id=class_a["id"],
                         stamp_default={"corner": "br", "source": "manual"})
        t = await _transcription(uid, rid, batch_id=b, page_count=3)
        overlay = await _graded(uid, rid, t, sid, status="approved", batch_id=b,
                                approved_at=approved_at, score="85.5", possible="100",
                                stamp={"x": 0.4, "y": 0.6, "source": "manual"})
        t2 = await _transcription(uid, rid, batch_id=b, page_count=2)
        default = await _graded(uid, rid, t2, sid, status="approved", batch_id=b,
                                approved_at=approved_at - timedelta(minutes=1))
        t3 = await _transcription(uid, rid, page_count=0)
        bare = await _graded(uid, rid, t3, sid, status="approved",
                             approved_at=approved_at - timedelta(minutes=2))
        # FA-9's consequence, pinned apart from the line above: a BATCH-LESS
        # test still has a page-1 image here. The returned PAGE cannot show the
        # scan without a batch (it reads `page_count` off the batch payload),
        # but this endpoint reads the transcription's own `draft_json`, so
        # «no batch» and «no image» are different facts and only the second
        # one draws the placeholder.
        t4 = await _transcription(uid, rid, page_count=2)
        lone = await _graded(uid, rid, t4, sid, status="approved",
                             approved_at=approved_at - timedelta(minutes=3))
        return b, t, t4, overlay, default, bare, lone
    b, t, t4, overlay, default, bare, lone = asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    by_id = {r["graded_test_id"]: r for r in payload["signed_tests"]}

    row = by_id[overlay]
    assert row["exam"] == {
        "batch_id": b, "name": "מבחן מחצית", "rubric_name": "User A Rubric",
        "class_name": class_a["name"], "uploaded_at": row["exam"]["uploaded_at"],
    }
    assert datetime.fromisoformat(row["approved_at"]) == approved_at
    # LST-3 / OD-7: the dedicated columns, serialised exactly as the returned
    # page's payload serialises them (a Decimal string — never a float).
    assert isinstance(row["total_score"], str) and Decimal(row["total_score"]) == Decimal("85.5")
    assert Decimal(row["total_possible"]) == Decimal("100")
    # OD-8 / FA-4: the SAME page-1 resource the pile cards fetch, plus the
    # stamp position RESOLVED server-side: the test's own overlay wins.
    thumb = row["thumbnail"]
    assert thumb["page1_image_url"].startswith(f"/api/v0/transcriptions/{t}/pages/1/image")
    assert thumb["stamp_position"]["x"] == 0.4 and thumb["stamp_position"]["y"] == 0.6
    assert thumb["stamp_position"]["corner"] is None

    # No overlay → the batch default.
    assert by_id[default]["thumbnail"]["stamp_position"]["corner"] == "br"
    # Neither → null (the client draws the auto corner, as the returned page does).
    assert by_id[bare]["thumbnail"]["stamp_position"] is None
    # A scan with no rendered pages offers no image, never a broken one
    # (M-A8: the row still renders and still links; the client draws the
    # neutral placeholder).
    assert by_id[bare]["thumbnail"]["page1_image_url"] is None
    assert by_id[bare]["exam"]["name"] is None and by_id[bare]["exam"]["class_name"] is None
    assert by_id[bare]["exam"]["rubric_name"] == "User A Rubric"

    # …and a BATCH-LESS test with pages DOES get one. «No batch» is not «no
    # image» on this surface, whatever the returned page can show.
    lone_row = by_id[lone]
    assert lone_row["exam"]["batch_id"] is None
    assert lone_row["thumbnail"]["page1_image_url"].startswith(
        f"/api/v0/transcriptions/{t4}/pages/1/image")
    assert lone_row["thumbnail"]["stamp_position"] is None


# ---------------------------------------------------------------------------
# LST-4 — one definition, one grouped statement
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_count_equals_list_for_a_mixed_history(client, headers_a, user_a, rubric_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid)
        t1 = await _transcription(uid, rid, batch_id=b)
        r1 = await _graded(uid, rid, t1, sid, status="approved", batch_id=b,
                           approved_at=_now() - timedelta(hours=3))
        await _graded(uid, rid, t1, sid, status="draft", batch_id=b, supersedes=r1)
        t2 = await _transcription(uid, rid, batch_id=b)
        await _graded(uid, rid, t2, sid, status="failed", batch_id=b)
        t3 = await _transcription(uid, rid, batch_id=b)
        await _graded(uid, rid, t3, sid, status="approved", batch_id=b)
    asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    assert payload["signed_tests_count"] == len(payload["signed_tests"]) == 2
    assert _roster_count(client, headers_a, sid) == 2
    detail = client.get(f"/api/v0/classroom/students/{sid}", headers=headers_a).json()
    assert detail["signed_tests_count"] == 2


#: The statement that makes the roster SELECT recognisable in a capture.
_ROSTER_SELECT = "FROM students"


def _roster_request_statements(client, headers) -> list[str]:
    """Every statement THIS request issued — and ONLY those.

    ⚠ ATTRIBUTED BY CONNECTION, and that is the whole point. A listener on the
    engine hears the entire PROCESS, not one request, and this process is not
    quiet: in dev `JOBS_EXECUTION_MODE=inline`, so the plan build that the
    rubric fixture kicks runs as an `asyncio.create_task` on its own session
    and writes `grading_plans` whenever it gets the loop. Its statements landed
    inside the listener's window and the assertion read 6-vs-5 after
    `tests/test_schema_canon.py` and 5-vs-5 alone — an order-dependent gate,
    which is no gate at all.

    A request holds ONE connection for its whole life and a concurrent task
    cannot be sharing it, so the group carrying the roster SELECT is exactly
    this request's work. Neighbours land in other groups and are ignored — not
    tolerated by a looser bound, which would have hidden a real N+1 too.
    """
    from app.database import engine

    seen: list[tuple[int, str]] = []

    def on_execute(conn, cursor, statement, parameters, context, executemany):
        seen.append((id(conn), statement))

    event.listen(engine.sync_engine, "before_cursor_execute", on_execute)
    try:
        resp = client.get("/api/v0/classroom/students", headers=headers)
        assert resp.status_code == 200, resp.text
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", on_execute)

    groups: dict[int, list[str]] = {}
    for conn_id, statement in seen:
        groups.setdefault(conn_id, []).append(statement)
    mine = [g for g in groups.values() if any(_ROSTER_SELECT in s for s in g)]
    assert len(mine) == 1, (
        "the roster SELECT must appear on exactly one connection; "
        f"saw {len(mine)} of {len(groups)} group(s): {groups}"
    )
    return mine[0]


@pytest.mark.integration
def test_the_roster_count_is_one_grouped_statement_regardless_of_student_count(
        client, headers_b, user_b):
    """No N+1: the roster with n students issues the same statements as the
    roster with n+30 — and the badge counts come from ONE grouped statement
    (LST-4), not one per student.

    User B, so user A's growing roster in the other tests cannot move the
    baseline between the two measurements. `rubric_a` is deliberately NOT
    requested: it kicks the inline plan build whose writes polluted this
    measurement (see `_roster_request_statements`), and this test never needed
    a rubric.
    """
    _student(client, headers_b, f"ספירה {uuid.uuid4().hex[:6]}")
    before = _roster_request_statements(client, headers_b)
    for _ in range(30):
        _student(client, headers_b, f"ספירה {uuid.uuid4().hex[:6]}")
    after = _roster_request_statements(client, headers_b)

    assert len(before) == len(after), (before, after)
    # Name the defect directly, not only its symptom: the counts are ONE
    # grouped statement over the leaves, at either roster size.
    for statements in (before, after):
        assert sum("signed_leaves" in s for s in statements) == 1, statements


# ---------------------------------------------------------------------------
# LST-5 — owner scoped
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_another_users_student_is_404_and_a_foreign_row_never_leaks(
        client, headers_a, headers_b, user_a, user_b, rubric_a):
    uid_a, uid_b, rid = user_a["user"]["id"], user_b["user"]["id"], rubric_a["rubric_id"]
    sid_a = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")
    sid_b = _student(client, headers_b, f"פרופיל {uuid.uuid4().hex[:6]}")

    assert client.get(SIGNED.format(id=sid_b), headers=headers_a).status_code == 404
    assert client.get(SIGNED.format(id=uuid.uuid4()), headers=headers_a).status_code == 404
    assert client.get(SIGNED.format(id=sid_a)).status_code == 401

    async def seed():
        # A row OWNED by user B that (illegitimately) names user A's student.
        rid_b = await _rubric(uid_b, "של ב")
        t = await _transcription(uid_b, rid_b)
        await _graded(uid_b, rid_b, t, sid_a, status="approved")
    # Since migration 032 (AM-B4, PRV-10) the DATABASE refuses that row:
    # graded_tests_student_tenant_fkey. The leak this test guarded against is
    # now unrepresentable, not merely filtered out by the user_id scope.
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError):
        asyncio.run(seed())

    payload = _get(client, headers_a, sid_a)
    assert payload["signed_tests"] == [] and payload["signed_tests_count"] == 0
    assert _roster_count(client, headers_a, sid_a) == 0


# ---------------------------------------------------------------------------
# LST-3 — parity between the columns and the contract, on every approved row
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_the_profile_shows_the_columns_and_the_columns_equal_the_contract(
        client, headers_a, user_a, rubric_a):
    """OD-7 reads the dedicated columns; LST-3 says those equal the contract's
    totals on every approved row. The approval endpoint is what keeps them
    equal (it writes both from the contract in one commit — pinned in
    test_graded_test_approval.py); this pins the reading half: what the
    profile serialises is the column, and the column is the contract.

    Scoped to rows THIS suite seeds: other suites hand-insert approved rows
    with NULL columns as fixtures for endpoints that never read them, so a
    database-wide check would fail on fixture debt, not on the product.
    (Production was checked directly on 2026-09-19: 7 approved rows, 0 with
    NULL columns, 0 disagreeing with their contract.)"""
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid)
        ids = []
        for score, possible in (("85.5", "100"), ("64", "80"), ("100", "100")):
            t = await _transcription(uid, rid, batch_id=b)
            ids.append(await _graded(uid, rid, t, sid, status="approved", batch_id=b,
                                     score=score, possible=possible))
        return ids
    ids = asyncio.run(seed())

    payload = _get(client, headers_a, sid)
    by_id = {r["graded_test_id"]: r for r in payload["signed_tests"]}
    assert set(by_id) == set(ids)

    async def columns_and_contracts():
        async with _session() as db:
            rows = (await db.execute(text("""
                SELECT id::text AS id, total_score, total_possible,
                       contract_json->>'total_score'    AS c_score,
                       contract_json->>'total_possible' AS c_possible
                FROM graded_tests WHERE id = ANY(CAST(:ids AS uuid[]))
            """), {"ids": ids})).all()
            return {r.id: r for r in rows}
    db_rows = asyncio.run(columns_and_contracts())

    for gid in ids:
        row, shown = db_rows[gid], by_id[gid]
        # the column IS the contract …
        assert row.total_score == Decimal(row.c_score)
        assert row.total_possible == Decimal(row.c_possible)
        # … and the profile shows the column.
        assert Decimal(shown["total_score"]) == row.total_score
        assert Decimal(shown["total_possible"]) == row.total_possible


# ---------------------------------------------------------------------------
# §5.3 — the cap
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_the_cap_truncates_the_list_but_never_the_count(client, headers_a, user_a, rubric_a):
    from app.services.student_signed_tests import signed_tests_for_student

    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"פרופיל {uuid.uuid4().hex[:6]}")

    async def seed_and_read():
        b = await _batch(uid, rid)
        for _ in range(3):
            t = await _transcription(uid, rid, batch_id=b)
            await _graded(uid, rid, t, sid, status="approved", batch_id=b)
        async with _session() as db:
            return await signed_tests_for_student(
                db, uuid.UUID(uid), uuid.UUID(sid), cap=2)
    result = asyncio.run(seed_and_read())
    assert result.count == 3
    assert len(result.rows) == 2
    assert result.truncated is True


# ---------------------------------------------------------------------------
# §5.4 / M-A2 — the interim delete
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# OD-3 / UI-4 — notes is gone
# ---------------------------------------------------------------------------

def test_notes_is_absent_from_every_response_and_ignored_on_every_request(client, headers_a):
    name = f"ללא הערות {uuid.uuid4().hex[:6]}"
    created = client.post("/api/v0/classroom/students",
                          json={"full_name": name, "notes": "ignored"}, headers=headers_a)
    assert created.status_code == 201, created.text
    assert "notes" not in created.json()
    assert created.json()["signed_tests_count"] == 0
    sid = created.json()["id"]

    patched = client.patch(f"/api/v0/classroom/students/{sid}",
                           json={"full_name": name + " ב", "notes": "ignored"}, headers=headers_a)
    assert patched.status_code == 200, patched.text
    assert "notes" not in patched.json()

    detail = client.get(f"/api/v0/classroom/students/{sid}", headers=headers_a).json()
    assert "notes" not in detail
    assert detail["classes"] == [] and detail["signed_tests_count"] == 0

    listed = client.get("/api/v0/classroom/students", headers=headers_a).json()["students"]
    assert all("notes" not in s for s in listed)
    assert all("signed_tests_count" in s for s in listed)


# ---------------------------------------------------------------------------
# Part A item 4 — ONE page 1 for a test, whichever surface draws it
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_a_batched_tests_page_1_is_the_same_resource_on_the_profile_the_pile_and_the_returned_page(
        client, headers_a, user_a, rubric_a):
    """The profile resolves page 1 from the transcription's own `draft_json`;
    the returned page resolves it through the batch payload; the pile reads the
    batch feed. For a BATCHED test all three must name the same page.

    Three facts, each necessary:
      1. profile == pile, as strings — both are minted server-side by
         `thumbnail.page_image_path`, so one function feeds both.
      2. the returned page asks for `/api/v0/transcriptions/{tid}/pages/1/image`
         (`frontend/src/lib/api.ts::transcriptionPagePath`, pinned there too),
         which is that same path WITHOUT the `?v=` pin, for the same
         transcription the approved payload names.
      3. the unpinned route serves the CURRENT variant — exactly the one the
         pin names — so the bytes are the same; only the cache promise differs
         (a year `immutable` when pinned, 60 s when not).
    """
    from app.services import thumbnail

    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    sid = _student(client, headers_a, f"עמוד 1 {uuid.uuid4().hex[:6]}")

    async def seed():
        b = await _batch(uid, rid, name="עמוד ראשון")
        t = await _transcription(uid, rid, batch_id=b, page_count=4)
        g = await _graded(uid, rid, t, sid, status="approved", batch_id=b)
        return b, t, g
    batch_id, transcription_id, graded_id = asyncio.run(seed())

    profile_path = next(
        r["thumbnail"]["page1_image_url"] for r in _get(client, headers_a, sid)["signed_tests"]
        if r["graded_test_id"] == graded_id)

    feed = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
    assert feed.status_code == 200, feed.text
    pile_path = next(g["page1_image_url"] for g in feed.json()["graded_tests"]
                     if g["graded_test_id"] == graded_id)

    approved = client.get(f"/api/v0/grading/graded_test/{graded_id}", headers=headers_a)
    assert approved.status_code == 200, approved.text
    returned_page_path = f"/api/v0/transcriptions/{approved.json()['transcription_id']}/pages/1/image"

    # 1
    assert profile_path == pile_path
    # 2
    base, _, query = profile_path.partition("?")
    assert base == returned_page_path
    assert approved.json()["transcription_id"] == transcription_id
    # 3
    token = query.removeprefix("v=")
    pinned_variant, pinned = thumbnail.resolve_variant(token)
    unpinned_variant, unpinned_is_pinned = thumbnail.resolve_variant(None)
    assert pinned is True and unpinned_is_pinned is False
    assert pinned_variant == unpinned_variant
