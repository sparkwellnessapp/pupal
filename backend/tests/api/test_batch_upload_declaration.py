"""
Stage A (UPLOAD_LATENCY_PLAN.md) — a batch can say "still uploading".

THE DEFECT THIS PINS (Defect D). B9 intake creates the batch row EMPTY and each
landed file inserts its own job, so the rollup's denominator is COUNT(jobs) —
the files that ARRIVED. Mid-upload a ten-file batch with one file in has a total
of one, and if that one is transcribed and approved the status derivation returns
"completed" while nine files are still climbing the wire. It does not blur the
number; it keeps computing and returns a confident wrong one (§3.5a).

Migration 025 records what she DECLARED. The gap is `uploading`, and after
`upload_declaration_ttl_minutes` of silence it becomes `not_received` — dead, so
the batch reaches a terminal status instead of waiting forever for a teacher who
closed the tab.

Two layers, deliberately:
  * PURE tests over `_build_rollup` / `_derive_batch_status` — zero mocks, every
    branch including the ones a live batch is awkward to force (an expired
    declaration, appends outrunning the declaration).
  * LIVE-DB tests over the real endpoints — the wire, the persistence, the 422.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional

import pytest
import sqlalchemy

from app.api.v0.batch_grading import (
    _build_rollup,
    _derive_batch_status,
    _last_append_at,
)
from app.config import settings
from tests.api.test_batch_exposure import _insert_batch, _insert_job
from tests.api.test_transcription_review import (
    _cleanup_batch,
    _sync_engine,
    _user_id,
)


# ---------------------------------------------------------------------------
# Pure layer — stand-ins carrying only what the rollup reads.
# ---------------------------------------------------------------------------

NOW = datetime(2026, 9, 4, 12, 0, tzinfo=timezone.utc)


@dataclass
class FakeBatch:
    expected_test_count: Optional[int] = None
    test_count: int = 0
    transcription_failures: list = field(default_factory=list)
    created_at: Optional[datetime] = NOW


@dataclass
class FakeJob:
    status: str = "completed"
    created_at: Optional[datetime] = NOW


@dataclass
class FakeTranscription:
    status: str = "transcribed"


@dataclass
class FakeGraded:
    status: str = "approved"


def _rollup(batch, jobs=None, transcriptions=None, graded=None, now=NOW):
    return _build_rollup(
        batch, transcriptions or [], graded or [], jobs, now=now,
    )


def _fresh_jobs(n: int, status: str = "completed") -> list[FakeJob]:
    return [FakeJob(status=status) for _ in range(n)]


# --- the legacy population: NOTHING may change -----------------------------

def test_legacy_batch_without_a_declaration_is_byte_identical():
    """expected NULL ⇒ the pre-025 response, field for field.

    This is the whole backward-compatibility story and it covers TWO
    populations at once: batches created before 025, and batches created by a
    client that has not shipped the declaration (the backend deploys before
    Vercel does). Neither may see a behaviour change.
    """
    batch = FakeBatch(expected_test_count=None)
    jobs = _fresh_jobs(3)
    r = _rollup(batch, jobs, transcriptions=[FakeTranscription("approved")] * 3,
                graded=[FakeGraded()] * 3)

    assert r.uploading == 0
    assert r.not_received == 0
    assert r.total == 3                      # COUNT(jobs), exactly as before
    assert _derive_batch_status(r) == "completed"


def test_legacy_pre_016_batch_still_infers_transcribing_from_test_count():
    """The 015-ledger fallback is untouched: no job rows ⇒ the old inference."""
    batch = FakeBatch(expected_test_count=None, test_count=4,
                      transcription_failures=[{"filename": "x.pdf"}])
    r = _rollup(batch, jobs=None, transcriptions=[FakeTranscription()])
    assert r.total == 4
    assert r.transcription_failed == 1
    assert r.transcribing == 2               # 4 − 1 row − 1 ledgered failure
    assert r.uploading == 0 and r.not_received == 0


# --- the defect itself -----------------------------------------------------

def test_declared_but_unlanded_files_block_completed():
    """THE Defect-D case. One file in, transcribed and approved, nine to go."""
    batch = FakeBatch(expected_test_count=10)
    r = _rollup(batch, _fresh_jobs(1),
                transcriptions=[FakeTranscription("approved")],
                graded=[FakeGraded()])

    assert r.uploading == 9
    assert r.total == 10                     # the honest denominator
    assert r.approved == 1
    assert _derive_batch_status(r) == "in_progress"


def test_the_refusal_holds_even_if_total_is_someone_elses_number():
    """Belt AND braces: the status refusal does not rely on `total`.

    `_derive_batch_status` is handed a rollup only — so this constructs the
    contradiction the arithmetic cannot currently produce (approved == total
    WITH files outstanding) and proves the explicit clause is what stops it.
    A future change to how `total` is derived must not be able to reopen
    Defect D.
    """
    from app.schemas.batch import BatchRollup
    r = BatchRollup(
        uploading=5, not_received=0, transcribing=0, transcribed=0,
        approved_transcription=0, grading=0, draft=0, approved=2, failed=0,
        transcription_failed=0, total=2,
    )
    assert _derive_batch_status(r) == "in_progress"


def test_uploading_counts_down_as_files_land():
    batch = FakeBatch(expected_test_count=3)
    assert _rollup(batch, jobs=None).uploading == 3       # nothing landed yet
    assert _rollup(batch, _fresh_jobs(1)).uploading == 2
    assert _rollup(batch, _fresh_jobs(3)).uploading == 0


def test_appends_beyond_the_declaration_never_shrink_the_denominator():
    """Appends are allowed for as long as the batch exists, so jobs CAN outrun
    the declaration. `total` is max(declared, landed) — never the smaller."""
    batch = FakeBatch(expected_test_count=1)
    r = _rollup(batch, _fresh_jobs(4))
    assert r.total == 4
    assert r.uploading == 0


# --- the backstop (R9) -----------------------------------------------------

def _stale() -> datetime:
    return NOW - timedelta(minutes=settings.upload_declaration_ttl_minutes + 1)


def test_backstop_reports_not_received_after_the_ttl():
    """She closed the tab. The outstanding files are dead, not in flight —
    so the batch reaches a terminal status instead of an eternal in_progress."""
    batch = FakeBatch(expected_test_count=3, created_at=_stale())
    jobs = [FakeJob(created_at=_stale())]
    r = _rollup(batch, jobs, transcriptions=[FakeTranscription("approved")],
                graded=[FakeGraded()])

    assert r.uploading == 0
    assert r.not_received == 2
    assert r.total == 3
    # dead=2, non_failed=1, approved=1 ⇒ she got what did arrive.
    assert _derive_batch_status(r) == "partially_completed"


def test_backstop_does_not_fire_while_appends_are_still_arriving():
    """An OLD batch whose newest append is recent is still uploading: the clock
    is the last append, not the batch's age."""
    batch = FakeBatch(expected_test_count=3, created_at=_stale())
    jobs = [FakeJob(created_at=_stale()), FakeJob(created_at=NOW)]
    r = _rollup(batch, jobs)
    assert r.uploading == 1 and r.not_received == 0


def test_a_batch_where_nothing_ever_arrived_expires_to_failed():
    batch = FakeBatch(expected_test_count=4, created_at=_stale())
    r = _rollup(batch, jobs=None)
    assert r.not_received == 4 and r.uploading == 0
    assert _derive_batch_status(r) == "failed"


def test_unknowable_clock_degrades_to_still_uploading():
    """The two errors are not symmetric. Calling a live upload dead lets the
    batch claim a terminal status while her files are on the wire — Defect D one
    stage earlier. Calling a dead upload live costs a batch that keeps saying
    'still uploading'. With no readable clock we take the honest wait."""
    batch = FakeBatch(expected_test_count=2, created_at=None)
    r = _rollup(batch, jobs=None)
    assert r.uploading == 2 and r.not_received == 0


def test_last_append_at_prefers_the_newest_job_over_batch_creation():
    batch = FakeBatch(created_at=_stale())
    assert _last_append_at(batch, []) == _stale()
    assert _last_append_at(batch, [FakeJob(created_at=NOW),
                                   FakeJob(created_at=_stale())]) == NOW


def test_naive_timestamps_are_coerced_before_comparison():
    """CLAUDE.md §13: never compare a stored timestamp against a bare now().
    A naive value must not raise — it 500'd /auth/login for 271 of 273 users."""
    naive = NOW.replace(tzinfo=None)
    batch = FakeBatch(expected_test_count=2, created_at=naive)
    r = _rollup(batch, [FakeJob(created_at=naive)])
    assert r.uploading == 1


def test_uploading_and_not_received_are_mutually_exclusive():
    for landed, created in ((0, NOW), (1, NOW), (0, _stale()), (1, _stale())):
        batch = FakeBatch(expected_test_count=3, created_at=created)
        r = _rollup(batch, [FakeJob(created_at=created)] * landed or None)
        assert not (r.uploading and r.not_received), (landed, created)


# ---------------------------------------------------------------------------
# Live-DB layer — the wire, the persistence, the 422.
# ---------------------------------------------------------------------------

def _expected_column(batch_id: str) -> Optional[int]:
    engine = _sync_engine()
    with engine.connect() as conn:
        row = conn.execute(
            sqlalchemy.text("SELECT expected_test_count FROM grading_batches "
                            "WHERE id = :id"),
            {"id": batch_id},
        ).fetchone()
    engine.dispose()
    return None if row is None else row[0]


def _set_expected(batch_id: str, n: Optional[int]) -> None:
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE grading_batches SET expected_test_count = :n "
                            "WHERE id = :id"),
            {"n": n, "id": batch_id},
        )
        conn.commit()
    engine.dispose()


@pytest.mark.integration
def test_create_persists_and_echoes_the_declaration(client, headers_a, rubric_a):
    resp = client.post("/api/v0/batches",
                       json={"rubric_id": rubric_a["rubric_id"],
                             "expected_test_count": 7},
                       headers=headers_a)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    batch_id = body["batch_id"]
    try:
        assert body["expected_test_count"] == 7
        assert _expected_column(batch_id) == 7
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        assert detail["rollup"]["uploading"] == 7
        assert detail["rollup"]["total"] == 7
        assert detail["status"] == "in_progress"
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_create_without_a_declaration_stays_null(client, headers_a, rubric_a):
    """The pre-Stage-A client. Backend deploys first; it must keep working."""
    resp = client.post("/api/v0/batches",
                       json={"rubric_id": rubric_a["rubric_id"]},
                       headers=headers_a)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    batch_id = body["batch_id"]
    try:
        assert body["expected_test_count"] is None
        assert _expected_column(batch_id) is None
        rollup = client.get(f"/api/v0/batches/{batch_id}",
                            headers=headers_a).json()["rollup"]
        assert rollup["uploading"] == 0
        assert rollup["not_received"] == 0
        assert rollup["total"] == 0
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_negative_declaration_is_rejected(client, headers_a, rubric_a):
    resp = client.post("/api/v0/batches",
                       json={"rubric_id": rubric_a["rubric_id"],
                             "expected_test_count": -1},
                       headers=headers_a)
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
def test_redeclare_lowers_uploading(client, user_a, headers_a, rubric_a):
    """R9's client half: a file that will never land is re-declared away."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 3)
    _insert_job(user_id, batch_id, rubric_a["rubric_id"], "queued", 0, "a.pdf")
    try:
        before = client.get(f"/api/v0/batches/{batch_id}",
                            headers=headers_a).json()["rollup"]
        assert before["uploading"] == 2

        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"expected_test_count": 1}, headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["expected_test_count"] == 1

        after = client.get(f"/api/v0/batches/{batch_id}",
                           headers=headers_a).json()["rollup"]
        assert after["uploading"] == 0
        assert after["total"] == 1
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_redeclare_below_landed_is_refused(client, user_a, headers_a, rubric_a):
    """A declaration is a claim about the future. It cannot retract work the
    batch is already holding."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 3)
    for i in range(2):
        _insert_job(user_id, batch_id, rubric_a["rubric_id"], "queued", i, f"{i}.pdf")
    try:
        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"expected_test_count": 1}, headers=headers_a)
        assert resp.status_code == 422, resp.text
        assert "2" in resp.json()["detail"]
        assert _expected_column(batch_id) == 3          # unchanged
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_redeclare_equal_to_landed_is_allowed(client, user_a, headers_a, rubric_a):
    """The boundary: "everything that is coming has come" is the normal way an
    upload ends when one file was rejected."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 5)
    _insert_job(user_id, batch_id, rubric_a["rubric_id"], "queued", 0, "a.pdf")
    try:
        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"expected_test_count": 1}, headers=headers_a)
        assert resp.status_code == 200, resp.text
        rollup = client.get(f"/api/v0/batches/{batch_id}",
                            headers=headers_a).json()["rollup"]
        assert rollup["uploading"] == 0 and rollup["total"] == 1
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_rename_alone_does_not_touch_the_declaration(client, user_a, headers_a,
                                                     rubric_a):
    """Field-present semantics: the PATCH is a settings patch, and each field
    is written only when it is IN the body."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 4)
    try:
        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"name": "מקבץ בדיקה"}, headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert resp.json()["expected_test_count"] == 4
        assert _expected_column(batch_id) == 4
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_the_server_never_lowers_the_declaration_itself(client, user_a,
                                                        headers_a, rubric_a):
    """R9, the half that is easy to lose: the backstop REPORTS, it never
    writes. `not_received` is a read-time fact — the column still says what she
    declared, so a later append is still measured against the truth."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 3)
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE grading_batches SET created_at = now() - "
                            "make_interval(mins => :m) WHERE id = :id"),
            {"m": settings.upload_declaration_ttl_minutes + 5, "id": batch_id},
        )
        conn.commit()
    engine.dispose()
    try:
        rollup = client.get(f"/api/v0/batches/{batch_id}",
                            headers=headers_a).json()["rollup"]
        assert rollup["not_received"] == 3
        assert rollup["uploading"] == 0
        assert _expected_column(batch_id) == 3          # NOT rewritten
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_list_and_detail_agree_about_uploading(client, user_a, headers_a,
                                               rubric_a):
    """The two rollup consumers share one builder — they cannot disagree."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 5)
    _insert_job(user_id, batch_id, rubric_a["rubric_id"], "queued", 0, "a.pdf")
    try:
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a).json()
        rows = client.get("/api/v0/batches", headers=headers_a).json()
        row = next(r for r in rows if r["id"] == batch_id)
        assert row["rollup"]["uploading"] == detail["rollup"]["uploading"] == 4
        assert row["rollup"]["total"] == detail["rollup"]["total"] == 5
        assert row["status"] == detail["status"] == "in_progress"
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_cross_tenant_redeclare_is_404(client, user_a, headers_a, headers_b,
                                       rubric_a):
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 2)
    try:
        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"expected_test_count": 9}, headers=headers_b)
        assert resp.status_code == 404, resp.text
        assert _expected_column(batch_id) == 2
    finally:
        _cleanup_batch(batch_id, [])


# ---------------------------------------------------------------------------
# Review fix — a declaration is a client number, and §9 says a request body
# never becomes an authoritative value without validation.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_absurd_declaration_is_refused(client, headers_a, rubric_a):
    """Unbounded, this number locks the batch to in_progress and renders
    "1000000000 מבחנים" on every surface for the whole backstop window."""
    resp = client.post("/api/v0/batches",
                       json={"rubric_id": rubric_a["rubric_id"],
                             "expected_test_count": 1_000_000_000},
                       headers=headers_a)
    assert resp.status_code == 422, resp.text


@pytest.mark.integration
def test_the_ceiling_matches_the_upload_surface_cap(client, headers_a, rubric_a):
    """50 is the client's own MAX_FILES, so the bound she can reach through the
    UI is the bound the server enforces — 50 passes, 51 does not."""
    from app.schemas.batch import MAX_DECLARED_TEST_COUNT
    assert MAX_DECLARED_TEST_COUNT == 50

    ok = client.post("/api/v0/batches",
                     json={"rubric_id": rubric_a["rubric_id"],
                           "expected_test_count": MAX_DECLARED_TEST_COUNT},
                     headers=headers_a)
    assert ok.status_code == 201, ok.text
    try:
        over = client.post("/api/v0/batches",
                           json={"rubric_id": rubric_a["rubric_id"],
                                 "expected_test_count": MAX_DECLARED_TEST_COUNT + 1},
                           headers=headers_a)
        assert over.status_code == 422, over.text
    finally:
        _cleanup_batch(ok.json()["batch_id"], [])


@pytest.mark.integration
def test_redeclare_is_bounded_too(client, user_a, headers_a, rubric_a):
    """The PATCH is the same promotion of a client number; same ceiling."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 3)
    try:
        resp = client.patch(f"/api/v0/batches/{batch_id}",
                            json={"expected_test_count": 999}, headers=headers_a)
        assert resp.status_code == 422, resp.text
        assert _expected_column(batch_id) == 3
    finally:
        _cleanup_batch(batch_id, [])


@pytest.mark.integration
def test_a_late_first_append_reopens_the_upload(client, user_a, headers_a, rubric_a):
    """The backstop clocks on the last append, and before the first one on the
    batch's own creation — R9 read literally. That means a batch with NO appends
    can expire while a very slow first file is still climbing. It SELF-HEALS:
    the moment that file lands, the newest append is recent and the batch
    reports `uploading` again rather than staying dead."""
    user_id = _user_id(user_a)
    batch_id = _insert_batch(user_id, rubric_a["rubric_id"])
    _set_expected(batch_id, 3)
    engine = _sync_engine()
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("UPDATE grading_batches SET created_at = now() - "
                            "make_interval(mins => :m) WHERE id = :id"),
            {"m": settings.upload_declaration_ttl_minutes + 5, "id": batch_id},
        )
        conn.commit()
    engine.dispose()
    try:
        expired = client.get(f"/api/v0/batches/{batch_id}",
                             headers=headers_a).json()["rollup"]
        assert expired["not_received"] == 3 and expired["uploading"] == 0

        _insert_job(user_id, batch_id, rubric_a["rubric_id"], "queued", 0, "late.pdf")

        healed = client.get(f"/api/v0/batches/{batch_id}",
                            headers=headers_a).json()["rollup"]
        assert healed["uploading"] == 2, "a fresh append must reopen the window"
        assert healed["not_received"] == 0
    finally:
        _cleanup_batch(batch_id, [])
