"""
In-house scanning — the capture service through its HTTP surface
(PR_in_house_scanning.md §6, §10).

  SCN-1  PageCap            25 concurrent page creates → exactly 20 land
  SCN-6  DurableBeforeSave  an awaiting page refuses the save; a failed analysis does not
  SCN-7  LinkScope          one device cannot read or edit another's submission
  SCN-8  StudentConfirmed   a teacher capture never saves without a confirmed student
  SCN-9  NoRosterExposure   identify returns one display name or nothing
  SCN-2/3 versions          each save freezes a version and withdraws the previous job
  D1 / D5 / D6              conflicts, the replace dialog, late resubmission
  OD-9                      the job filename, unique within the batch
  D2 / OD-5                 the handoff is single-use and batch-scoped

GCS and scan-service are in-memory fakes; "today" is pinned; nothing here
reaches a network.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from pydantic import SecretStr
from sqlalchemy import text

from app.services.capture.scan_client import AnalyzeResult, set_scan_client
from tests.api.test_batch_grading import _fresh_loop_session
from tests.api.test_capture_batch_side import _batch, _drop

pytestmark = pytest.mark.integration

EXAM_DAY = date(2026, 11, 4)
QUAD = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]


class FakeGcs:
    def __init__(self):
        self.objects: dict[str, int] = {}

    def generate_signed_url(self, path, minutes=60, *, method="GET", content_type=None, headers=None):
        return f"https://signed.test/{method}/{path}"

    def object_size(self, path):
        return self.objects.get(path)

    def copy_object(self, source, dest):
        self.objects[dest] = self.objects.get(source, 0)
        return dest


class FakeScan:
    def __init__(self):
        self.fail = False

    async def analyze(self, raw_uri, preview_uri_out, *, timeout_s):
        if self.fail:
            raise TimeoutError("scan-service did not answer")
        return AnalyzeResult(image_w=3000, image_h=4000, corners=QUAD, corners_source="auto_contour",
                             confidence=0.5, preview_uri=preview_uri_out,
                             quality={"blur": 120.0, "short_side_px": 2400, "glare_ratio": 0.0,
                                      "verdict": "ok", "reasons": []})


@pytest.fixture
def env(monkeypatch, user_a, rubric_a):
    from app.config import settings
    from app.services.capture import links

    monkeypatch.setattr(settings, "capture_enabled", True)
    monkeypatch.setattr(settings, "capture_token_secret", SecretStr("test-capture-secret"))
    monkeypatch.setattr(settings, "frontend_base_url", "https://app.test")
    monkeypatch.setattr(links, "today_il", lambda now=None: EXAM_DAY)
    gcs, scan = FakeGcs(), FakeScan()
    set_scan_client(scan)
    batch_id = asyncio.run(_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    enqueue = AsyncMock()
    with patch("app.services.capture.submissions._gcs", return_value=gcs), \
         patch("app.services.batch_ingest.enqueue_transcription_task", enqueue):
        yield {"batch": batch_id, "gcs": gcs, "scan": scan, "enqueue": enqueue,
               "user": user_a["user"]["id"]}
    set_scan_client(None)
    asyncio.run(_drop(batch_id))


def _sql(sql, **params):
    async def go():
        async with _fresh_loop_session() as db:
            r = await db.execute(text(sql), params)
            await db.commit()
            try:
                return r.all()
            except Exception:
                return None
    return asyncio.run(go())


def _students(env, *names):
    """Students of user A, in the batch's class."""
    out = []
    class_id = _sql("SELECT class_id FROM grading_batches WHERE id = :b", b=env["batch"])[0][0]
    for name in names:
        sid = uuid.uuid4()
        _sql("INSERT INTO students (id, user_id, full_name, created_at, updated_at) "
             "VALUES (:i, :u, :n, now(), now())", i=sid, u=uuid.UUID(env["user"]), n=name)
        _sql("INSERT INTO class_memberships (class_id, student_id, created_at) VALUES (:c, :s, now())",
             c=class_id, s=sid)
        out.append(sid)
    return out


def _link(client, headers, env, **body) -> str:
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-link", headers=headers,
                    json={"exam_date": EXAM_DAY.isoformat(),
                          "new_class_name": f"כיתת צילום {uuid.uuid4().hex[:6]}", **body})
    assert r.status_code == 201, r.text
    return r.json()["url"].rsplit("/s/", 1)[1]


def _uniq(base):
    return f"{base} {uuid.uuid4().hex[:5]}"


S = "/api/v0/capture/s"


def _create(client, token, name, confirm=True):
    r = client.post(f"{S}/{token}/submissions", json={"name": name, "confirm_match": confirm})
    assert r.status_code == 201, r.text
    return r.json()["submission_id"], {"X-Capture-Device": r.json()["device_secret"]}


def _page(client, base, sub, headers, env, *, upload=True):
    r = client.post(f"{base}/submissions/{sub}/pages", json={"content_type": "image/jpeg"},
                    headers=headers)
    assert r.status_code == 201, r.text
    page = r.json()
    if upload:
        env["gcs"].objects[page["upload_url"].split("/PUT/", 1)[1]] = 1234
        u = client.post(f"{base}/submissions/{sub}/pages/{page['page_id']}/uploaded", headers=headers)
        assert u.status_code == 200, u.text
    return page["page_id"]


def _jobs(env):
    return _sql("SELECT id, source_filename, source_gcs_object_path, withdrawn_at, capture_version_id "
                "FROM transcription_jobs WHERE batch_id = :b ORDER BY created_at", b=env["batch"])


# ---------------------------------------------------------------------------
# the feature flag, the link
# ---------------------------------------------------------------------------

def test_every_capture_route_is_404_while_the_flag_is_off(client, headers_a, user_a, rubric_a):
    assert client.get(f"/api/v0/batches/{uuid.uuid4()}/capture-link", headers=headers_a).status_code == 404
    assert client.get(f"{S}/whatever").status_code == 404


def test_a_link_needs_a_class_and_is_one_per_batch(client, headers_a, env):
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-link", headers=headers_a,
                    json={"exam_date": EXAM_DAY.isoformat()})
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "class_required")
    token = _link(client, headers_a, env)
    assert _sql("SELECT class_id FROM grading_batches WHERE id = :b", b=env["batch"])[0][0] is not None
    again = client.post(f"/api/v0/batches/{env['batch']}/capture-link", headers=headers_a,
                        json={"exam_date": EXAM_DAY.isoformat(), "new_class_name": "x"})
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "link_exists")
    # OD-4: the same URL every time it is shown, never stored
    shown = client.get(f"/api/v0/batches/{env['batch']}/capture-link", headers=headers_a).json()
    assert shown["url"].endswith(token) and shown["state"] == "open"
    assert _sql("SELECT COUNT(*) FROM capture_links WHERE token_hash = :t",
                t=token.encode())[0][0] == 0                    # the token itself is nowhere


def test_rotate_kills_the_old_url_close_and_reopen(client, headers_a, env, monkeypatch):
    from app.services.capture import links

    old = _link(client, headers_a, env)
    new = client.post(f"/api/v0/batches/{env['batch']}/capture-link/rotate-token",
                      headers=headers_a).json()["url"].rsplit("/s/", 1)[1]
    assert new != old
    assert client.get(f"{S}/{old}").status_code == 404
    assert client.get(f"{S}/{new}").json()["state"] == "open"
    client.post(f"/api/v0/batches/{env['batch']}/capture-link/close", headers=headers_a)
    assert client.get(f"{S}/{new}").json()["state"] == "closed"
    r = client.post(f"{S}/{new}/submissions", json={"name": "x", "confirm_match": False})
    assert (r.status_code, r.json()["detail"]["state"]) == (410, "closed")
    monkeypatch.setattr(links, "today_il", lambda now=None: date(2026, 11, 5))
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-link/reopen", headers=headers_a)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "reopen_not_today")
    monkeypatch.setattr(links, "today_il", lambda now=None: EXAM_DAY)
    assert client.post(f"/api/v0/batches/{env['batch']}/capture-link/reopen",
                       headers=headers_a).json()["state"] == "open"


def test_before_the_exam_day_the_link_says_so_and_refuses_writes(client, headers_a, env, monkeypatch):
    from app.services.capture import links

    token = _link(client, headers_a, env)
    monkeypatch.setattr(links, "today_il", lambda now=None: date(2026, 11, 3))
    assert client.get(f"{S}/{token}").json()["state"] == "not_yet_open"
    assert client.post(f"{S}/{token}/identify", json={"name": "x"}).status_code == 410


def test_student_responses_never_leak_a_referrer_or_get_cached(client, env, headers_a):
    token = _link(client, headers_a, env)
    for r in (client.get(f"{S}/{token}"), client.get(f"{S}/not-a-token")):
        assert r.headers["referrer-policy"] == "no-referrer"
        assert r.headers["cache-control"] == "no-store"


# ---------------------------------------------------------------------------
# SCN-9, D16 — identify
# ---------------------------------------------------------------------------

def test_identify_returns_one_display_name_and_nothing_else(client, headers_a, env):
    token = _link(client, headers_a, env)
    a, b = _uniq("דני"), _uniq("רות")
    _students(env, f"{a} כהן", f"{b} לוי")
    r = client.post(f"{S}/{token}/identify", json={"name": f"כהן {a}"})   # surname first (D16)
    assert r.json() == {"match": {"display_name": f"{a} כהן"}}
    assert client.post(f"{S}/{token}/identify", json={"name": "מישהו אחר"}).json() == {"match": None}


def test_a_name_two_students_share_matches_neither(client, headers_a, env):
    token = _link(client, headers_a, env)
    n = _uniq("נועה")
    _students(env, f"{n} שמש", f"שמש {n}")
    assert client.post(f"{S}/{token}/identify", json={"name": f"{n} שמש"}).json() == {"match": None}


def test_a_client_sent_student_id_is_ignored(client, headers_a, env):
    token = _link(client, headers_a, env)
    (victim,) = _students(env, _uniq("יעל"))
    r = client.post(f"{S}/{token}/submissions",
                    json={"name": "שם שלא קיים", "confirm_match": True, "student_id": str(victim)})
    sub = r.json()["submission_id"]
    assert _sql("SELECT student_id, student_state FROM capture_submissions WHERE id = :s",
                s=uuid.UUID(sub))[0] == (None, "pending")


# ---------------------------------------------------------------------------
# D1, SCN-7 — a submission belongs to its device
# ---------------------------------------------------------------------------

def test_the_same_name_from_a_second_device_is_a_conflict_and_never_touches_the_first(
        client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("אורי")
    _students(env, name)
    base = f"{S}/{token}"
    sub_a, dev_a = _create(client, token, name)
    _page(client, base, sub_a, dev_a, env)
    assert client.post(f"{base}/submissions/{sub_a}/save", headers=dev_a).status_code == 200
    raw = client.post(f"{S}/{token}/submissions", json={"name": name, "confirm_match": True})
    assert raw.status_code == 201 and set(raw.json()) == {"submission_id", "device_secret"}  # same shape
    sub_b, dev_b = raw.json()["submission_id"], {"X-Capture-Device": raw.json()["device_secret"]}
    _page(client, base, sub_b, dev_b, env)
    assert client.post(f"{base}/submissions/{sub_b}/save", headers=dev_b).status_code == 200
    states = dict(_sql("SELECT id::text, student_state FROM capture_submissions WHERE id IN (:a, :b)",
                       a=uuid.UUID(sub_a), b=uuid.UUID(sub_b)))
    assert states == {sub_a: "confirmed", sub_b: "conflict"}   # judged at B's save (D1/D5)
    # D1: the student is never told — her own view carries no state at all
    own = client.get(f"{base}/submissions/{sub_b}", headers=dev_b).json()
    assert "student_state" not in own and "student" not in own and own["display_name"] == name
    assert "student_state" not in client.get(f"{base}", headers=dev_b).json()["own_submission"]
    # SCN-7: neither device can read or edit the other's submission
    assert client.get(f"{S}/{token}/submissions/{sub_a}", headers=dev_b).status_code == 404
    assert client.post(f"{S}/{token}/submissions/{sub_a}/pages", headers=dev_b,
                       json={"content_type": "image/jpeg"}).status_code == 404
    assert client.get(f"{S}/{token}/submissions/{sub_a}").status_code == 404   # no device at all
    assert len(client.get(f"{S}/{token}/submissions/{sub_a}", headers=dev_a).json()["pages"]) == 1
    # reopening the link on device A goes straight back to A's submission
    assert client.get(f"{S}/{token}", headers=dev_a).json()["own_submission"]["submission_id"] == sub_a


# ---------------------------------------------------------------------------
# SCN-1 — the page cap, under concurrency
# ---------------------------------------------------------------------------

def test_twenty_five_concurrent_page_creates_land_exactly_twenty(client, headers_a, env):
    from app.database import AsyncSessionLocal, engine
    from app.services.capture import submissions as svc
    from app.services.capture.actors import CaptureError, StudentActor

    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, "שם", confirm=False)
    link = _sql("SELECT id, user_id FROM capture_links WHERE batch_id = :b", b=env["batch"])[0]
    from app.services.capture import tokens
    actor = StudentActor(link_id=link[0], batch_id=env["batch"], user_id=link[1],
                         device_hash=tokens.sha256(dev["X-Capture-Device"]))

    async def one():
        async with AsyncSessionLocal() as db:
            try:
                await svc.create_page(db, actor, uuid.UUID(sub), "image/jpeg")
                await db.commit()
                return True
            except CaptureError as exc:
                assert exc.code == "page_cap"
                return False

    async def all25():
        await engine.dispose(close=False)
        try:
            return await asyncio.gather(*(one() for _ in range(25)))
        finally:
            await engine.dispose(close=False)

    results = asyncio.run(all25())
    assert results.count(True) == 20
    rows = _sql("SELECT position FROM capture_pages WHERE submission_id = :s AND deleted_at IS NULL "
                "ORDER BY position", s=uuid.UUID(sub))
    assert [r[0] for r in rows] == list(range(1, 21))


# ---------------------------------------------------------------------------
# SCN-6, save, versions (SCN-2/3), OD-9
# ---------------------------------------------------------------------------

def test_a_page_still_uploading_refuses_the_save_and_a_failed_analysis_does_not(client, headers_a, env):
    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, _uniq("גל"), confirm=False)
    base = f"{S}/{token}"
    waiting = _page(client, base, sub, dev, env, upload=False)
    r = client.post(f"{base}/submissions/{sub}/save", headers=dev)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "uploads_pending")
    assert r.json()["detail"]["page_ids"] == [waiting]
    # the upload is confirmed against GCS, not the client's word
    assert client.post(f"{base}/submissions/{sub}/pages/{waiting}/uploaded",
                       headers=dev).json()["detail"]["code"] == "upload_not_found"
    client.delete(f"{base}/submissions/{sub}/pages/{waiting}", headers=dev)
    env["scan"].fail = True                                   # D9: analysis down
    page = _page(client, base, sub, dev, env)
    view = client.get(f"{base}/submissions/{sub}", headers=dev).json()["pages"][0]
    assert (view["page_id"], view["status"], view["corners_source"]) == (page, "analyze_failed", "full_frame")
    saved = client.post(f"{base}/submissions/{sub}/save", headers=dev)
    assert saved.status_code == 200 and saved.json()["version_no"] == 1
    env["enqueue"].assert_awaited()


def test_each_save_freezes_a_version_and_withdraws_the_last(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("שירה")
    _students(env, name)
    sub, dev = _create(client, token, name)
    base = f"{S}/{token}"
    page = _page(client, base, sub, dev, env)
    assert client.post(f"{base}/submissions/{sub}/save", headers=dev).json()["version_no"] == 1
    client.patch(f"{base}/submissions/{sub}/pages/{page}", headers=dev, json={"rotation": 90})
    assert client.post(f"{base}/submissions/{sub}/save", headers=dev).json()["version_no"] == 2
    (j1, f1, p1, w1, v1), (j2, f2, p2, w2, v2) = _jobs(env)
    assert w1 is not None and w2 is None                       # SCN-3 / D7
    assert f1 == f2 == f"{name}.pdf"                           # OD-9 — a withdrawn name is free
    assert p2 == f"captures/{sub}/{v2}.pdf"                    # SCN-4's deterministic path
    snapshots = _sql("SELECT version_no, pages_snapshot FROM capture_versions WHERE submission_id = :s "
                     "ORDER BY version_no", s=uuid.UUID(sub))
    assert [s[1][0]["rotation"] for s in snapshots] == [0, 90]  # SCN-2: v1 frozen as it was
    detail = client.get(f"/api/v0/batches/{env['batch']}", headers=headers_a).json()
    assert detail["rollup"]["total"] == 1
    # Arrival order over every job (v2 never shares the withdrawn v1's slot),
    # and the human-facing count is the LIVE one.
    assert [r[0] for r in _sql("SELECT doc_priority FROM transcription_jobs WHERE batch_id = :b "
                               "ORDER BY created_at", b=env["batch"])] == [0, 1]
    assert _sql("SELECT test_count FROM grading_batches WHERE id = :b", b=env["batch"])[0][0] == 1


def test_a_resubmission_after_approval_becomes_a_new_conflict_never_a_replacement(
        client, headers_a, env):
    """D6 — and the teacher sees «נשלחה גרסה חדשה» as a late_resubmission row."""
    token = _link(client, headers_a, env)
    name = _uniq("מאיה")
    (sid,) = _students(env, name)
    sub, dev = _create(client, token, name)
    base = f"{S}/{token}"
    _page(client, base, sub, dev, env)
    client.post(f"{base}/submissions/{sub}/save", headers=dev)
    (job_id, *_rest), = _jobs(env)
    tid = uuid.uuid4()
    _sql("INSERT INTO transcriptions (id, user_id, rubric_id, batch_id, student_id, student_name, gcs_uri, "
         "gcs_bucket, gcs_object_path, draft_json, contract_json, approved_at, status, created_at, updated_at) "
         "SELECT :t, user_id, rubric_id, id, :s, 'x', 'gs://b/x', 'b', 'x', '{}'::jsonb, '{}'::jsonb, "
         "now(), 'approved', now(), now() FROM grading_batches WHERE id = :b", t=tid, s=sid, b=env["batch"])
    _sql("UPDATE transcription_jobs SET status='completed', finished_at=now(), transcription_id=:t "
         "WHERE id = :j", t=tid, j=job_id)
    r = client.post(f"{base}/submissions/{sub}/save", headers=dev)
    assert r.status_code == 200
    rows = _sql("SELECT id::text, student_state, conflict_note FROM capture_submissions "
                "WHERE batch_id = :b ORDER BY created_at", b=env["batch"])
    assert rows[0] == (sub, "confirmed", None)                 # the approved one, untouched
    assert rows[1][1:] == ("conflict", "late_resubmission")
    late = rows[1][0]
    assert r.json()["submission_id"] == late                   # the client continues there
    assert _jobs(env)[0][3] is None                            # its job was NOT withdrawn
    # its photos are its OWN objects (a purge of one never deletes the other's)
    late_raws = [r[0] for r in _sql("SELECT raw_gcs_uri FROM capture_pages WHERE submission_id = :s",
                                    s=uuid.UUID(late))]
    assert late_raws and all(f"captures/{late}/" in u for u in late_raws)
    assert all(u.split("/", 3)[3] in env["gcs"].objects for u in late_raws)
    # saving again from the same device re-versions THAT late copy — no third submission
    assert client.post(f"{base}/submissions/{sub}/save", headers=dev).json()["submission_id"] == late
    assert len(_sql("SELECT 1 FROM capture_submissions WHERE batch_id = :b", b=env["batch"])) == 2
    panel = client.get(f"/api/v0/batches/{env['batch']}/capture-submissions", headers=headers_a).json()
    assert {r["conflict_note"] for r in panel["rows"]} == {None, "late_resubmission"}
    # and the approved scan is never re-attributed to someone else
    other = _students(env, _uniq("אחר"))[0]
    teacher = f"/api/v0/capture/teacher/{env['batch']}"
    moved = client.put(f"{teacher}/submissions/{sub}/student", headers=headers_a,
                       json={"student_id": str(other)})
    assert (moved.status_code, moved.json()["detail"]["code"]) == (409, "already_approved")


def test_two_exams_under_one_name_get_distinct_filenames(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("עדי")
    _students(env, name)
    base = f"{S}/{token}"
    sub1, dev1 = _create(client, token, name)                       # confirmed
    sub2, dev2 = _create(client, token, f"{name} ", confirm=False)  # typed, pending
    for sub, dev in ((sub1, dev1), (sub2, dev2)):
        _page(client, base, sub, dev, env)
        assert client.post(f"{base}/submissions/{sub}/save", headers=dev).status_code == 200
    assert sorted(j[1] for j in _jobs(env)) == sorted([f"{name}.pdf", f"{name} (2).pdf"])


# ---------------------------------------------------------------------------
# the teacher page — SCN-8, D5
# ---------------------------------------------------------------------------

def _teacher_sub(client, headers, env):
    r = client.post(f"/api/v0/capture/teacher/{env['batch']}/submissions", headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["submission_id"]


def test_a_teacher_capture_never_saves_without_a_confirmed_student(client, headers_a, env):
    _link(client, headers_a, env)
    base = f"/api/v0/capture/teacher/{env['batch']}"
    sub = _teacher_sub(client, headers_a, env)
    _page(client, base, sub, headers_a, env)
    r = client.post(f"{base}/submissions/{sub}/save", headers=headers_a)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "student_not_confirmed")
    made = client.put(f"{base}/submissions/{sub}/student", headers=headers_a,
                      json={"create": {"name": _uniq("תלמיד חדש")}})
    assert made.status_code == 200 and made.json()["student_state"] == "confirmed"
    assert client.post(f"{base}/submissions/{sub}/save", headers=headers_a).status_code == 200


def test_assigning_an_already_submitted_student_asks_and_replace_discards_the_other(
        client, headers_a, env):
    _link(client, headers_a, env)
    (sid,) = _students(env, _uniq("ליה"))
    base = f"/api/v0/capture/teacher/{env['batch']}"
    first, second = _teacher_sub(client, headers_a, env), _teacher_sub(client, headers_a, env)
    _page(client, base, first, headers_a, env)
    client.put(f"{base}/submissions/{first}/student", headers=headers_a, json={"student_id": str(sid)})
    client.post(f"{base}/submissions/{first}/save", headers=headers_a)
    r = client.put(f"{base}/submissions/{second}/student", headers=headers_a, json={"student_id": str(sid)})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "student_already_submitted")
    assert r.json()["detail"]["existing_submission_id"] == first and r.json()["detail"]["page_count"] == 1
    r = client.put(f"{base}/submissions/{second}/student", headers=headers_a,
                   json={"student_id": str(sid), "replace_existing": True})
    assert r.status_code == 200
    assert _sql("SELECT status FROM capture_submissions WHERE id = :s", s=uuid.UUID(first))[0][0] == "discarded"
    assert _jobs(env)[0][3] is not None                        # its job withdrawn (D7)


# ---------------------------------------------------------------------------
# the panel — pending (R1) and conflicts
# ---------------------------------------------------------------------------

def test_a_pending_name_is_approved_as_a_new_student_once(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("טל")
    sub, dev = _create(client, token, name, confirm=False)
    _page(client, f"{S}/{token}", sub, dev, env)
    client.post(f"{S}/{token}/submissions/{sub}/save", headers=dev)
    url = f"/api/v0/batches/{env['batch']}/capture-submissions/{sub}/resolve-pending"
    body = client.post(url, headers=headers_a, json={"approve_new": True}).json()
    (row,) = body["rows"]
    assert row["student_state"] == "confirmed" and row["student"]["display_name"] == name
    assert body["counter"]["submitted_students"] == 1 and body["counter"]["roster_size"] == 1
    again = client.post(url, headers=headers_a, json={"approve_new": True})
    assert again.json()["detail"]["code"] == "not_pending"


def test_approving_a_name_that_already_exists_offers_linking(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("רון")
    _sql("INSERT INTO students (id, user_id, full_name, created_at, updated_at) "
         "VALUES (gen_random_uuid(), :u, :n, now(), now())", u=uuid.UUID(env["user"]), n=name)
    sub, dev = _create(client, token, name, confirm=False)   # not in the class → pending
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-submissions/{sub}/resolve-pending",
                    headers=headers_a, json={"approve_new": True})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "student_exists")


def test_an_abandoned_draft_never_makes_a_real_submission_a_conflict(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("נועה")
    _students(env, name)
    base = f"{S}/{token}"
    _create(client, token, name)                               # opened, then abandoned
    b, dev_b = _create(client, token, name)
    _page(client, base, b, dev_b, env)
    assert client.post(f"{base}/submissions/{b}/save", headers=dev_b).status_code == 200
    assert _sql("SELECT student_state FROM capture_submissions WHERE id = :s",
                s=uuid.UUID(b))[0][0] == "confirmed"


def test_a_discarded_submission_cannot_be_resolved(client, headers_a, env):
    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, _uniq("גיל"), confirm=False)
    _page(client, f"{S}/{token}", sub, dev, env)
    client.post(f"{S}/{token}/submissions/{sub}/save", headers=dev)
    _sql("UPDATE capture_submissions SET status = 'discarded' WHERE id = :s", s=uuid.UUID(sub))
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-submissions/{sub}/resolve-pending",
                    headers=headers_a, json={"approve_new": True})
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "submission_discarded")


def test_a_blank_name_is_refused_at_the_door(client, headers_a, env):
    token = _link(client, headers_a, env)
    for path in ("identify", "submissions"):
        assert client.post(f"{S}/{token}/{path}", json={"name": "   "}).status_code == 422
    sub = _teacher_sub(client, headers_a, env)
    r = client.put(f"/api/v0/capture/teacher/{env['batch']}/submissions/{sub}/student",
                   headers=headers_a, json={"create": {"name": "  "}})
    assert r.status_code == 422


def test_a_mirrored_quad_is_refused(client, headers_a, env):
    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, _uniq("דן"), confirm=False)
    page = _page(client, f"{S}/{token}", sub, dev, env)
    mirrored = [[0.9, 0.1], [0.1, 0.1], [0.1, 0.9], [0.9, 0.9]]   # TL<->TR swapped: counter-clockwise
    r = client.patch(f"{S}/{token}/submissions/{sub}/pages/{page}", headers=dev,
                     json={"corners": mirrored})
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "invalid_corners")


def test_the_signed_put_is_write_once(client, headers_a, env):
    token = _link(client, headers_a, env)
    sub, dev = _create(client, token, _uniq("רז"), confirm=False)
    r = client.post(f"{S}/{token}/submissions/{sub}/pages", json={"content_type": "image/jpeg"},
                    headers=dev)
    assert r.json()["required_headers"]["x-goog-if-generation-match"] == "0"


def test_keep_this_resolves_a_conflict_by_discarding_the_competitor(client, headers_a, env):
    token = _link(client, headers_a, env)
    name = _uniq("אביב")
    (sid,) = _students(env, name)
    base = f"{S}/{token}"
    a, dev_a = _create(client, token, name)
    b, dev_b = _create(client, token, name)                    # conflict (D1)
    for sub, dev in ((a, dev_a), (b, dev_b)):
        _page(client, base, sub, dev, env)
        client.post(f"{base}/submissions/{sub}/save", headers=dev)
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-submissions/{b}/resolve-conflict",
                    headers=headers_a, json={"action": "keep_this"})
    assert r.status_code == 200, r.text
    assert dict(_sql("SELECT id::text, status FROM capture_submissions WHERE batch_id = :b",
                     b=env["batch"])) == {a: "discarded", b: "saved"}


# ---------------------------------------------------------------------------
# D2 / OD-5 — the handoff
# ---------------------------------------------------------------------------

def test_the_handoff_is_single_use_and_its_session_reaches_only_its_batch(client, headers_a, env):
    _link(client, headers_a, env)
    r = client.post(f"/api/v0/batches/{env['batch']}/capture-handoff", headers=headers_a)
    handoff = r.json()["handoff_url"].split("handoff=", 1)[1]
    ex = client.post("/api/v0/capture/handoff/exchange", json={"handoff_token": handoff})
    assert ex.status_code == 200
    again = client.post("/api/v0/capture/handoff/exchange", json={"handoff_token": handoff})
    assert (again.status_code, again.json()["detail"]["code"]) == (410, "handoff_invalid")
    session = {"Authorization": f"CaptureSession {ex.json()['capture_session']}"}
    assert client.get(f"/api/v0/capture/teacher/{env['batch']}", headers=session).status_code == 200
    assert client.get(f"/api/v0/capture/teacher/{uuid.uuid4()}", headers=session).status_code == 401
    # not a login: rejected by every other route, as a Bearer token too
    assert client.get(f"/api/v0/batches/{env['batch']}", headers=session).status_code == 401
    bearer = {"Authorization": f"Bearer {ex.json()['capture_session']}"}
    assert client.get("/api/v0/auth/me", headers=bearer).status_code == 401


# ---------------------------------------------------------------------------
# OD-10 — the batch payloads say a capture link exists
# ---------------------------------------------------------------------------

def test_the_batch_payloads_carry_the_capture_link_state(client, headers_a, env):
    detail = lambda: client.get(f"/api/v0/batches/{env['batch']}", headers=headers_a).json()  # noqa: E731
    assert detail()["capture_link_state"] is None
    _link(client, headers_a, env)
    assert detail()["capture_link_state"] == "open"
    (row,) = [b for b in client.get("/api/v0/batches", headers=headers_a).json()
              if b["id"] == str(env["batch"])]
    assert row["capture_link_state"] == "open"


# ---------------------------------------------------------------------------
# review fixes
# ---------------------------------------------------------------------------

def test_the_rate_limit_key_is_the_address_cloud_run_appended():
    """The LAST X-Forwarded-For hop is the one Google's front end saw; the first
    is whatever the client sent, and keying on it minted a fresh bucket per
    request."""
    from types import SimpleNamespace

    from app.api.v0.capture_student import _client_ip

    req = lambda xff: SimpleNamespace(headers={"x-forwarded-for": xff},  # noqa: E731
                                      client=SimpleNamespace(host="10.0.0.1"))
    assert _client_ip(req("1.2.3.4, 203.0.113.7")) == "203.0.113.7"
    assert _client_ip(req("203.0.113.7")) == "203.0.113.7"
    assert _client_ip(req("")) == "10.0.0.1"


def test_a_class_on_one_school_address_is_never_rate_limited(client, headers_a, env):
    """30 students identify from ONE public IP within a minute (typos included)."""
    token = _link(client, headers_a, env)
    codes = {client.post(f"{S}/{token}/identify", json={"name": f"תלמיד {i}"},
                         headers={"X-Forwarded-For": "198.51.100.9"}).status_code
             for i in range(45)}
    assert codes == {200}


def test_resume_shows_content_and_at_most_one_empty_group(client, headers_a, env):
    _link(client, headers_a, env)
    base = f"/api/v0/capture/teacher/{env['batch']}"
    with_page = client.post(f"{base}/submissions", headers=headers_a).json()["submission_id"]
    _page(client, base, with_page, headers_a, env)
    for _ in range(3):                                         # three abandoned empty groups
        client.post(f"{base}/submissions", headers=headers_a)
    drafts = client.get(base, headers=headers_a).json()["drafts"]
    assert len(drafts) == 2 and drafts[0]["submission_id"] == with_page
    assert drafts[1]["pages"] == []
