"""
`app.scripts.rebatch_capture` — a capture batch's saved photo sets, copied into a
new batch on another rubric (ops, 2026-11-02).

Seeded the way capture save leaves a batch (two confirmed sets with real-shaped
object paths, one discarded set, one empty draft); GCS is an in-memory fake and
the enqueue a recorder — nothing here reaches a network.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select, text

from app.config import settings
from app.scripts import rebatch_capture as rb
from app.services.capture import paths
from tests.api.test_batch_grading import _fresh_loop_session
from tests.api.test_capture_batch_side import _draft, _drop, _student
from tests.api.conftest import MINIMAL_DRAFT

pytestmark = pytest.mark.integration

NOW = lambda: datetime.now(timezone.utc)                                    # noqa: E731
BUCKET = settings.gcs_bucket_name


class FakeGCS:
    def __init__(self, objects=None, fail_on_copy: int | None = None):
        self.objects = dict(objects or {})
        self.fail_on_copy = fail_on_copy
        self.copies = 0

    def object_size(self, path):
        return len(self.objects[path]) if path in self.objects else None

    def copy_object(self, src, dst):
        self.copies += 1
        if self.fail_on_copy == self.copies:
            raise RuntimeError("copy failed")
        self.objects[dst] = self.objects[src]
        return dst

    def delete_folder(self, prefix):
        gone = [k for k in self.objects if k.startswith(prefix)]
        for k in gone:
            del self.objects[k]
        return len(gone)


async def _batch(user_id, rubric_id, class_id) -> uuid.UUID:
    from app.models.grading import GradingBatch
    async with _fresh_loop_session() as db:
        b = GradingBatch(user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
                         rubric_contract_version="old-v1", name="מבחן · 2.11.2026",
                         class_id=uuid.UUID(class_id), status="in_progress", test_count=0,
                         started_at=NOW())
        db.add(b)
        await db.commit()
        return b.id


async def _saved_set(user_id, rubric_id, batch_id, student_id, objects, *, status="saved",
                     pages=2, with_pdf=True) -> uuid.UUID:
    """A set exactly as capture save leaves it: pages under the set's prefix, a
    version snapshot, a live completed job and its `transcribed` scan."""
    from app.models.capture import CapturePage, CaptureSubmission, CaptureVersion
    from app.models.transcription import Transcription
    from app.models.transcription_job import TranscriptionJob

    uid, rid = uuid.UUID(user_id), uuid.UUID(rubric_id)
    async with _fresh_loop_session() as db:
        sub = CaptureSubmission(batch_id=batch_id, user_id=uid, source="teacher",
                                student_id=student_id,
                                student_state="confirmed" if student_id else "unassigned",
                                status="draft")
        db.add(sub)
        await db.flush()
        if status == "draft":
            await db.commit()
            return sub.id
        snapshot = []
        for i in range(1, pages + 1):
            pid = uuid.uuid4()
            raw, prev = paths.raw_path(sub.id, pid), paths.preview_path(sub.id, pid)
            objects[raw], objects[prev] = b"raw%d" % i, b"prev%d" % i
            db.add(CapturePage(id=pid, submission_id=sub.id, raw_gcs_uri=paths.gs_uri(BUCKET, raw),
                               preview_gcs_uri=paths.gs_uri(BUCKET, prev),
                               content_type="image/jpeg", status="analyzed", image_w=10,
                               image_h=20, corners=[[0, 0], [1, 0], [1, 1], [0, 1]],
                               corners_source="auto_model", rotation=90, position=i))
            snapshot.append({"page_id": str(pid), "raw_gcs_uri": paths.gs_uri(BUCKET, raw),
                             "content_type": "image/jpeg",
                             "corners": [[0, 0], [1, 0], [1, 1], [0, 1]], "rotation": 90})
        version = CaptureVersion(submission_id=sub.id, version_no=1, pages_snapshot=snapshot,
                                 scan_pipeline_version="scan-v1.0")
        db.add(version)
        await db.flush()
        await db.execute(text("UPDATE capture_submissions SET status=:st, current_version_id=:v "
                              "WHERE id=:s"), {"st": status, "v": version.id, "s": sub.id})
        pdf = paths.pdf_path(sub.id, version.id)
        if with_pdf:
            objects[pdf] = b"%PDF"
        t = Transcription(user_id=uid, rubric_id=rid, batch_id=batch_id,
                          gcs_uri=paths.gs_uri(BUCKET, pdf), gcs_bucket=BUCKET,
                          gcs_object_path=pdf, filename="x.pdf", draft_json=_draft(),
                          status="transcribed")
        db.add(t)
        await db.flush()
        db.add(TranscriptionJob(user_id=uid, batch_id=batch_id, rubric_id=rid, status="completed",
                                source_gcs_object_path=pdf, source_filename=f"{sub.id}.pdf",
                                capture_version_id=version.id, transcription_id=t.id,
                                withdrawn_at=NOW() if status == "discarded" else None,
                                finished_at=NOW()))
        await db.commit()
        return sub.id


@pytest.fixture
def rubric_new(client, headers_a):
    r = client.post("/api/v0/rubrics/save_ontology_draft", headers=headers_a, json={
        "name": "User A Rubric (corrected)", "draft": MINIMAL_DRAFT,
        "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]})
    assert r.status_code == 201, r.text
    return r.json()["rubric_id"]


@pytest.fixture
def seeded(user_a, rubric_a, class_a):
    uid, rid = user_a["user"]["id"], rubric_a["rubric_id"]
    objects: dict = {}
    batch_id = asyncio.run(_batch(uid, rid, class_a["id"]))
    s1, _ = asyncio.run(_student(uid))
    s2, _ = asyncio.run(_student(uid))
    sets = [asyncio.run(_saved_set(uid, rid, batch_id, s1, objects)),
            asyncio.run(_saved_set(uid, rid, batch_id, s2, objects, pages=3, with_pdf=False))]
    asyncio.run(_saved_set(uid, rid, batch_id, s1, objects, status="discarded"))
    asyncio.run(_saved_set(uid, rid, batch_id, None, objects, status="draft"))
    made: list = [batch_id]
    yield {"user": uid, "rubric": rid, "batch": batch_id, "students": (s1, s2), "sets": sets,
           "objects": objects, "made": made}
    for b in made:
        asyncio.run(_drop(b))


def _run(seeded, rubric_id, *, apply, gcs, enqueued=None):
    async def record(job_id):
        enqueued.append(job_id)
    new = asyncio.run(rb.run(seeded["batch"], uuid.UUID(rubric_id), apply=apply, gcs=gcs,
                             session_factory=_fresh_loop_session,
                             enqueue=record if enqueued is not None else None))
    if new is not None:
        seeded["made"].append(new)
    return new


async def _rows(sql, **params):
    async with _fresh_loop_session() as db:
        return (await db.execute(text(sql), params)).mappings().all()


def test_dry_run_writes_nothing(seeded, rubric_new):
    gcs = FakeGCS(seeded["objects"])
    assert _run(seeded, rubric_new, apply=False, gcs=gcs) is None
    assert gcs.copies == 0
    rows = asyncio.run(_rows("SELECT name FROM grading_batches WHERE user_id = :u AND name LIKE 'מבחן · 2.11.2026%'",
                             u=seeded["user"]))
    assert [r["name"] for r in rows] == ["מבחן · 2.11.2026"]


def test_apply_copies_every_saved_set_into_a_new_batch_on_the_new_rubric(seeded, rubric_new, class_a):
    gcs, enqueued = FakeGCS(seeded["objects"]), []
    new = _run(seeded, rubric_new, apply=True, gcs=gcs, enqueued=enqueued)

    (b,) = asyncio.run(_rows("SELECT b.*, r.contract_version AS rcv FROM grading_batches b "
                             "JOIN rubrics r ON r.id = b.rubric_id WHERE b.id = :b", b=new))
    assert str(b["rubric_id"]) == rubric_new and b["rubric_contract_version"] == b["rcv"]
    assert str(b["class_id"]) == class_a["id"] and b["name"] == "מבחן · 2.11.2026"
    assert b["status"] == "in_progress" and b["test_count"] == 2

    (old,) = asyncio.run(_rows("SELECT name FROM grading_batches WHERE id = :b", b=seeded["batch"]))
    assert old["name"] == "מבחן · 2.11.2026" + rb.OLD_SUFFIX

    subs = asyncio.run(_rows("SELECT * FROM capture_submissions WHERE batch_id = :b ORDER BY created_at", b=new))
    assert {s["student_id"] for s in subs} == set(seeded["students"])     # discarded + draft skipped
    assert all(s["status"] == "saved" and s["student_state"] == "confirmed"
               and s["source"] == "teacher" for s in subs)

    jobs = asyncio.run(_rows("SELECT * FROM transcription_jobs WHERE batch_id = :b", b=new))
    assert sorted(enqueued) == sorted(j["id"] for j in jobs) and len(jobs) == 2
    for sub in subs:
        (v,) = asyncio.run(_rows("SELECT * FROM capture_versions WHERE id = :v", v=sub["current_version_id"]))
        pages = asyncio.run(_rows("SELECT * FROM capture_pages WHERE submission_id = :s ORDER BY position",
                                  s=sub["id"]))
        assert [str(p["id"]) for p in pages] == [s["page_id"] for s in v["pages_snapshot"]]
        assert [p["position"] for p in pages] == list(range(1, len(pages) + 1))
        prefix = paths.submission_prefix(sub["id"])
        for p, snap in zip(pages, v["pages_snapshot"]):
            raw = paths.split_gs_uri(p["raw_gcs_uri"])[1]
            assert raw.startswith(prefix) and snap["raw_gcs_uri"] == p["raw_gcs_uri"]
            assert gcs.objects[raw].startswith(b"raw")
            assert gcs.objects[paths.split_gs_uri(p["preview_gcs_uri"])[1]].startswith(b"prev")
            assert (p["rotation"], p["corners_source"], snap["rotation"]) == (90, "auto_model", 90)
        (job,) = [j for j in jobs if j["capture_version_id"] == v["id"]]
        assert job["status"] == "queued" and job["withdrawn_at"] is None
        assert job["source_gcs_object_path"] == paths.pdf_path(sub["id"], v["id"])
        assert str(job["rubric_id"]) == rubric_new
    # the compiled PDF is copied where it existed; the other set's step 0 compiles it
    pdfs = [j["source_gcs_object_path"] in gcs.objects for j in jobs]
    assert sorted(pdfs) == [False, True]


def test_a_second_run_is_refused(seeded, rubric_new):
    _run(seeded, rubric_new, apply=True, gcs=FakeGCS(seeded["objects"]), enqueued=[])
    with pytest.raises(rb.Refused, match="already renamed"):
        _run(seeded, rubric_new, apply=False, gcs=FakeGCS(seeded["objects"]))


def test_a_failed_copy_writes_nothing_and_leaves_no_objects(seeded, rubric_new):
    gcs = FakeGCS(seeded["objects"], fail_on_copy=3)
    before = set(gcs.objects)
    with pytest.raises(RuntimeError):
        _run(seeded, rubric_new, apply=True, gcs=gcs, enqueued=[])
    assert set(gcs.objects) == before
    rows = asyncio.run(_rows("SELECT name FROM grading_batches WHERE id = :b", b=seeded["batch"]))
    assert rows[0]["name"] == "מבחן · 2.11.2026"
    n = asyncio.run(_rows("SELECT count(*) AS n FROM grading_batches WHERE user_id = :u "
                          "AND rubric_id = :r", u=seeded["user"], r=rubric_new))
    assert n[0]["n"] == 0


def test_two_sets_claiming_one_student_are_refused(seeded, rubric_new):
    asyncio.run(_saved_set(seeded["user"], seeded["rubric"], seeded["batch"],
                           seeded["students"][0], seeded["objects"]))
    with pytest.raises(rb.Refused, match="two saved sets"):
        _run(seeded, rubric_new, apply=False, gcs=FakeGCS(seeded["objects"]))
