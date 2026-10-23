"""
A student-data graph for the purge tests, seeded into Vivi-Test with real
rows, plus the objects a fake bucket should hold for it.

One base graph, and small mutations for the cases that must REFUSE or BLOCK,
so every test reads as "the base, plus this one thing".

The base graph (all under one teacher U, one rubric R, one batch B):

    S  (the student being purged), in class C
       t_alpha  approved scan, job j_alpha, chain g_alpha_r1 (approved) → g_alpha_r2 (draft leaf)
                thumbs: two pages + one SUPERSEDED variant (found only by listing, M-B7)
       t_beta   approved scan, job j_beta, g_beta (approved, returned-exam key)
                returned_exams: the current key + one SUPERSEDED key
    S2 (control) t_delta approved scan, job j_delta, g_delta (approved) — must survive
    —  t_gamma  never assigned (`transcribed`, student NULL), job j_gamma (OD-B6)
    —  j_failed a failed upload, no transcription
    B.transcription_failures: one entry naming t_alpha's file, one naming nobody's

Teardown is EXPLICIT and in dependency order — graded-test chains in one
statement, then jobs, transcriptions, memberships, students — so it works the
same before and after migration 032 (census F: never lean on a cascade).
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

BUCKET = "purge-test-bucket"


@asynccontextmanager
async def session():
    """Loop-safe session (the Part A shape): drop pooled connections without
    closing them on entry and exit, so no event loop inherits another's."""
    from app.database import AsyncSessionLocal, engine

    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            yield db
    finally:
        await engine.dispose(close=False)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def scan_path(user_id: uuid.UUID) -> str:
    return f"transcriptions/{user_id}/{uuid.uuid4()}.pdf"


@dataclass
class Graph:
    user_id: uuid.UUID
    owns_user: bool
    rubric_id: uuid.UUID
    batch_id: uuid.UUID
    class_id: uuid.UUID
    student_id: uuid.UUID
    other_student_id: uuid.UUID
    t: dict[str, uuid.UUID] = field(default_factory=dict)
    j: dict[str, uuid.UUID] = field(default_factory=dict)
    g: dict[str, uuid.UUID] = field(default_factory=dict)
    scans: dict[str, str] = field(default_factory=dict)
    filenames: dict[str, str] = field(default_factory=dict)
    student_name: str = ""
    extra_batches: list[uuid.UUID] = field(default_factory=list)
    extra_students: list[uuid.UUID] = field(default_factory=list)
    pdf_ids: list[uuid.UUID] = field(default_factory=list)
    objects: set[tuple[str, str]] = field(default_factory=set)
    student_keys: set[str] = field(default_factory=lambda: {"alpha", "beta"})
    # [036] capture subtrees, by key: {"sub", "pages", "versions", "student"}.
    # A capture's transcription is t[key]; its jobs are j[f"{key}_v1"], j[f"{key}_v2"].
    captures: dict[str, dict] = field(default_factory=dict)
    link_id: uuid.UUID | None = None

    # ---- what a correct plan for S contains -------------------------------
    def expected_rows(self) -> dict[str, set[uuid.UUID]]:
        return {
            "class_memberships": {self.class_id},
            "graded_tests": {self.g[k] for k in self.g if k.split("_")[0] in self.student_keys},
            "transcription_jobs": {self.j[k] for k in self.j if k.split("_")[0] in self.student_keys},
            "transcriptions": {self.t[k] for k in self.student_keys},
            "capture_pages": {p for k in self._own_captures() for p in self.captures[k]["pages"]},
            "capture_versions": {v for k in self._own_captures() for v in self.captures[k]["versions"]},
            "capture_submissions": {self.captures[k]["sub"] for k in self._own_captures()},
            "students": {self.student_id},
        }

    def _own_captures(self) -> list[str]:
        return [k for k, c in self.captures.items() if c["student"] == self.student_id]

    def expected_objects(self) -> set[tuple[str, str]]:
        own_t = {str(self.t[k]) for k in self.student_keys}
        own_g = {str(self.g[k]) for k in self.g if k.split("_")[0] in self.student_keys}
        own_scans = {self.scans[k] for k in self.student_keys}
        own_subs = {str(self.captures[k]["sub"]) for k in self._own_captures()}
        return {(b, n) for (b, n) in self.objects
                if n in own_scans
                or (n.startswith("thumbs/") and n.split("/")[1] in own_t)
                or (n.startswith("returned_exams/") and n.split("/")[1] in own_g)
                or (n.startswith("captures/") and n.split("/")[1] in own_subs)}

    def control_objects(self) -> set[tuple[str, str]]:
        return self.objects - self.expected_objects()


async def _add_scan(db, g: Graph, key: str, *, student_id, batch_id, job_status="completed",
                    bucket=BUCKET) -> None:
    from app.models.transcription import Transcription
    from app.models.transcription_job import TranscriptionJob

    tid = uuid.uuid4()
    path = scan_path(g.user_id)
    filename = f"scan-{key}.pdf"
    approved = student_id is not None
    db.add(Transcription(
        id=tid, user_id=g.user_id, rubric_id=g.rubric_id, batch_id=batch_id,
        student_id=student_id, gcs_uri=f"gs://{bucket}/{path}", gcs_bucket=bucket,
        gcs_object_path=path, filename=filename,
        draft_json={"page_count": 2, "answers": [], "annotations": []},
        contract_json={"answers": []} if approved else None,
        approved_at=_now() if approved else None,
        status="approved" if approved else "transcribed"))
    await db.flush()
    if job_status is not None:
        jid = uuid.uuid4()
        db.add(TranscriptionJob(
            id=jid, user_id=g.user_id, batch_id=batch_id, rubric_id=g.rubric_id,
            status=job_status, source_gcs_object_path=path, source_filename=filename,
            transcription_id=tid, started_at=_now(),
            finished_at=_now() if job_status in ("completed", "failed") else None,
            error_message="boom" if job_status == "failed" else None))
        g.j[key] = jid
    g.t[key] = tid
    g.scans[key] = path
    g.filenames[key] = filename
    g.objects.add((BUCKET, path))
    for page in (1, 2):
        g.objects.add((BUCKET, f"thumbs/{tid}/p{page}_1200x80-150.webp"))


async def _add_graded(db, g: Graph, key: str, *, transcription_key: str, student_id,
                      status: str, batch_id=None, supersedes: str | None = None,
                      returned_keys: tuple[str, ...] = ()) -> None:
    from app.models.grading import GradedTest

    gid = uuid.uuid4()
    approved = status == "approved"
    draft = {"rubric_contract_version": "rc", "scope_outcomes": []} if status in ("approved", "draft") else None
    contract = ({"contract_version": str(uuid.uuid4()), "total_score": "80",
                 "total_possible": "100", "scope_outcomes": []} if approved else None)
    if supersedes:
        await db.execute(text("UPDATE graded_tests SET regraded_to_id = :new WHERE id = :old"),
                         {"new": gid, "old": g.g[supersedes]})
    db.add(GradedTest(
        id=gid, user_id=g.user_id, rubric_id=g.rubric_id, batch_id=batch_id,
        transcription_id=g.t[transcription_key], student_id=student_id,
        rubric_contract_version="rc", status=status, student_name="x",
        filename=g.filenames[transcription_key],
        draft_json=draft, contract_json=contract,
        approved_at=_now() if approved else None,
        error_message="boom" if status == "failed" else None,
        total_score=Decimal("80") if approved else None,
        total_possible=Decimal("100") if approved else None,
        returned_exam_key=returned_keys[0] if returned_keys else None,
        regraded_from_id=g.g[supersedes] if supersedes else None))
    await db.flush()
    g.g[key] = gid
    for k in returned_keys:
        g.objects.add((BUCKET, f"returned_exams/{gid}/{k}.pdf"))


async def seed_graph(*, user_id: uuid.UUID | None = None) -> Graph:
    from app.models.classroom import Class, ClassMembership
    from app.models.grading import GradingBatch, Rubric
    from app.models.student import Student
    from app.models.transcription_job import TranscriptionJob
    from app.models.user import User

    async with session() as db:
        owns_user = user_id is None
        if owns_user:
            user_id = uuid.uuid4()
            db.add(User(id=user_id, email=f"purge_{uuid.uuid4().hex[:10]}@s2test.com",
                        full_name="Purge Test Teacher", password_hash="x"))
            await db.flush()
        rubric_id, batch_id, class_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        s, s2 = uuid.uuid4(), uuid.uuid4()
        tag = uuid.uuid4().hex[:6]
        db.add(Rubric(id=rubric_id, user_id=user_id, name=f"purge-{tag}",
                      contract_version="cv-test", contract_json={"contract_version": "cv-test"}))
        db.add(Class(id=class_id, user_id=user_id, name=f"purge-class-{tag}"))
        db.add(Student(id=s, user_id=user_id, full_name=f"תלמידה לבדיקה {tag}"))
        db.add(Student(id=s2, user_id=user_id, full_name=f"תלמיד ביקורת {tag}"))
        await db.flush()
        db.add(GradingBatch(
            id=batch_id, user_id=user_id, rubric_id=rubric_id, rubric_contract_version="cv-test",
            name=f"purge-batch-{tag}", status="in_progress", test_count=5,
            started_at=_now(), transcription_failures=[
                {"filename": "scan-alpha.pdf", "error": "x", "at": _now().isoformat(),
                 "net_verdict": None},
                {"filename": "scan-unrelated.pdf", "error": "x", "at": _now().isoformat(),
                 "net_verdict": None},
            ]))
        db.add(ClassMembership(class_id=class_id, student_id=s))
        await db.flush()

        g = Graph(user_id=user_id, owns_user=owns_user, rubric_id=rubric_id, batch_id=batch_id,
                  class_id=class_id, student_id=s, other_student_id=s2,
                  student_name=f"תלמידה לבדיקה {tag}")
        await _add_scan(db, g, "alpha", student_id=s, batch_id=batch_id)
        await _add_scan(db, g, "beta", student_id=s, batch_id=batch_id)
        await _add_scan(db, g, "delta", student_id=s2, batch_id=batch_id)
        await _add_scan(db, g, "gamma", student_id=None, batch_id=batch_id)
        # A superseded thumbnail variant nobody could reconstruct from a row.
        g.objects.add((BUCKET, f"thumbs/{g.t['alpha']}/p1_800x70-110.webp"))

        await _add_graded(db, g, "alpha_r1", transcription_key="alpha", student_id=s,
                          status="approved", batch_id=batch_id)
        await _add_graded(db, g, "alpha_r2", transcription_key="alpha", student_id=s,
                          status="draft", batch_id=batch_id, supersedes="alpha_r1")
        await _add_graded(db, g, "beta", transcription_key="beta", student_id=s,
                          status="approved", batch_id=batch_id,
                          returned_keys=("k-current", "k-superseded"))
        await _add_graded(db, g, "delta", transcription_key="delta", student_id=s2,
                          status="approved", batch_id=batch_id, returned_keys=("k-delta",))

        # A failed upload: its object landed, no transcription exists, nothing
        # attributes it to anyone. It must survive every student's purge.
        jf, failed_path = uuid.uuid4(), scan_path(user_id)
        g.objects.add((BUCKET, failed_path))
        db.add(TranscriptionJob(
            id=jf, user_id=user_id, batch_id=batch_id, rubric_id=rubric_id, status="failed",
            source_gcs_object_path=failed_path, source_filename="scan-failed.pdf",
            transcription_id=None, started_at=_now(), finished_at=_now(),
            error_message="boom"))
        g.j["failed"] = jf
        await db.commit()
    return g


# ---------------------------------------------------------------------------
# mutations — "the base, plus this one thing"
# ---------------------------------------------------------------------------

async def add_pdf(g: Graph, graded_key: str, path: str) -> uuid.UUID:
    pid = uuid.uuid4()
    async with session() as db:
        await db.execute(text(
            "INSERT INTO graded_test_pdfs (id, graded_test_id, rubric_id, created_at, gcs_uri, "
            " gcs_bucket, gcs_object_path, filename) VALUES (:id, :g, :r, now(), :uri, :b, :p, 'x.pdf')"),
            {"id": pid, "g": g.g[graded_key], "r": g.rubric_id,
             "uri": f"gs://{BUCKET}/{path}", "b": BUCKET, "p": path})
        await db.commit()
    g.pdf_ids.append(pid)
    g.objects.add((BUCKET, path))
    return pid


async def add_legacy_batch_scan(g: Graph) -> uuid.UUID:
    """A pre-jobs-era batch: test_count > 0 and ZERO jobs, holding one of S's
    approved scans (census E)."""
    from app.models.grading import GradingBatch

    lb = uuid.uuid4()
    async with session() as db:
        db.add(GradingBatch(id=lb, user_id=g.user_id, rubric_id=g.rubric_id,
                            rubric_contract_version="cv-test", name="legacy", status="completed",
                            test_count=2, started_at=_now(), transcription_failures=[]))
        await db.flush()
        await _add_scan(db, g, "legacy", student_id=g.student_id, batch_id=lb, job_status=None)
        await db.commit()
    g.extra_batches.append(lb)
    g.student_keys.add("legacy")
    return lb


async def add_graded_blocker(g: Graph, status: str) -> uuid.UUID:
    """One of S's scans with a grade in flight (`pending` / `grading`)."""
    async with session() as db:
        await _add_scan(db, g, f"blk{status}", student_id=g.student_id, batch_id=g.batch_id)
        await _add_graded(db, g, f"blk{status}", transcription_key=f"blk{status}",
                          student_id=g.student_id, status=status, batch_id=g.batch_id)
        await db.commit()
    g.student_keys.add(f"blk{status}")
    return g.g[f"blk{status}"]


async def add_running_job_on(g: Graph, key: str) -> uuid.UUID:
    from app.models.transcription_job import TranscriptionJob

    jid = uuid.uuid4()
    async with session() as db:
        db.add(TranscriptionJob(
            id=jid, user_id=g.user_id, batch_id=g.batch_id, rubric_id=g.rubric_id,
            status="running", source_gcs_object_path=g.scans[key],
            source_filename=g.filenames[key], transcription_id=g.t[key], started_at=_now()))
        await db.commit()
    g.j[f"{key}_running"] = jid
    return jid


async def point_scan_at(g: Graph, key: str, *, path: str | None = None,
                        bucket: str | None = None) -> None:
    async with session() as db:
        if path is not None:
            await db.execute(text("UPDATE transcriptions SET gcs_object_path = :p WHERE id = :t"),
                             {"p": path, "t": g.t[key]})
        if bucket is not None:
            await db.execute(text("UPDATE transcriptions SET gcs_bucket = :b WHERE id = :t"),
                             {"b": bucket, "t": g.t[key]})
        await db.commit()


async def add_student(g: Graph, *, draft_only: bool = False, scan_only: bool = False) -> uuid.UUID:
    """Another student of the same teacher: with nothing attributable, with one
    scan whose only grade is an unapproved draft, or with one approved scan and
    no grade at all (the dialog's cases, PR §15)."""
    from app.models.student import Student

    sid = uuid.uuid4()
    async with session() as db:
        db.add(Student(id=sid, user_id=g.user_id, full_name=f"תלמיד נוסף {uuid.uuid4().hex[:6]}"))
        await db.flush()
        if scan_only:
            await _add_scan(db, g, f"scan{len(g.extra_students)}", student_id=sid,
                            batch_id=g.batch_id)
        if draft_only:
            key = f"draft{len(g.extra_students)}"
            await _add_scan(db, g, key, student_id=sid, batch_id=g.batch_id)
            await _add_graded(db, g, key, transcription_key=key, student_id=sid,
                              status="draft", batch_id=g.batch_id)
        await db.commit()
    g.extra_students.append(sid)
    return sid


async def add_capture(g: Graph, key: str, *, student_id=None, pending_name: str | None = None,
                      approve: bool = False) -> uuid.UUID:
    """[036] A saved capture submission with two pages and two versions:
    v1 superseded (its job failed and was WITHDRAWN, no transcription), v2
    current (its job completed: a `transcribed` scan at the version's PDF
    path, or `approve=True` -> approved for `student_id`). With `student_id`
    it is a teacher capture CONFIRMED for that student; with `pending_name`
    it is a student-link capture whose typed name was never resolved.
    `key` must not contain "_" (the graph keys jobs by its prefix)."""
    from app.models.capture import CaptureLink, CapturePage, CaptureSubmission, CaptureVersion
    from app.models.transcription import Transcription
    from app.models.transcription_job import TranscriptionJob
    from app.services.capture import paths

    assert "_" not in key
    sub = uuid.uuid4()
    async with session() as db:
        if pending_name is not None and g.link_id is None:
            g.link_id = uuid.uuid4()
            db.add(CaptureLink(id=g.link_id, batch_id=g.batch_id, user_id=g.user_id,
                               token_hash=uuid.uuid4().bytes, exam_date=_now().date()))
            await db.flush()
        db.add(CaptureSubmission(
            id=sub, batch_id=g.batch_id, user_id=g.user_id,
            source="teacher" if pending_name is None else "student_link",
            link_id=None if pending_name is None else g.link_id,
            device_secret_hash=None if pending_name is None else uuid.uuid4().bytes,
            student_id=student_id,
            student_state="confirmed" if student_id is not None else "pending",
            pending_student_name=pending_name, status="draft"))
        await db.flush()
        pages = [uuid.uuid4(), uuid.uuid4()]
        for i, pid in enumerate(pages, 1):
            db.add(CapturePage(
                id=pid, submission_id=sub, raw_gcs_uri=f"gs://{BUCKET}/{paths.raw_path(sub, pid)}",
                preview_gcs_uri=f"gs://{BUCKET}/{paths.preview_path(sub, pid)}",
                content_type="image/jpeg", status="analyzed", image_w=3000, image_h=4000,
                corners=[[0, 0], [1, 0], [1, 1], [0, 1]], corners_source="full_frame", position=i))
            g.objects.add((BUCKET, paths.raw_path(sub, pid)))
            g.objects.add((BUCKET, paths.preview_path(sub, pid)))
        versions = [uuid.uuid4(), uuid.uuid4()]
        for n, vid in enumerate(versions, 1):
            db.add(CaptureVersion(id=vid, submission_id=sub, version_no=n,
                                  pages_snapshot=[{"page_id": str(p)} for p in pages],
                                  scan_pipeline_version="scan-v1.0"))
            g.objects.add((BUCKET, paths.pdf_path(sub, vid)))
        await db.flush()
        await db.execute(text("UPDATE capture_submissions SET status = 'saved', "
                              "current_version_id = :v WHERE id = :s"),
                         {"v": versions[1], "s": sub})

        j1 = uuid.uuid4()
        db.add(TranscriptionJob(
            id=j1, user_id=g.user_id, batch_id=g.batch_id, rubric_id=g.rubric_id, status="failed",
            source_gcs_object_path=paths.pdf_path(sub, versions[0]), source_filename=f"{key}.pdf",
            capture_version_id=versions[0], withdrawn_at=_now(), started_at=_now(),
            finished_at=_now(), error_message="boom"))
        tid, path = uuid.uuid4(), paths.pdf_path(sub, versions[1])
        db.add(Transcription(
            id=tid, user_id=g.user_id, rubric_id=g.rubric_id, batch_id=g.batch_id,
            student_id=student_id if approve else None, gcs_uri=f"gs://{BUCKET}/{path}",
            gcs_bucket=BUCKET, gcs_object_path=path, filename=f"{key}.pdf",
            draft_json={"page_count": 2, "answers": [], "annotations": []},
            contract_json={"answers": []} if approve else None,
            approved_at=_now() if approve else None,
            status="approved" if approve else "transcribed"))
        await db.flush()
        j2 = uuid.uuid4()
        db.add(TranscriptionJob(
            id=j2, user_id=g.user_id, batch_id=g.batch_id, rubric_id=g.rubric_id,
            status="completed", source_gcs_object_path=path, source_filename=f"{key}.pdf",
            capture_version_id=versions[1], transcription_id=tid, started_at=_now(),
            finished_at=_now()))
        await db.commit()
    g.objects.add((BUCKET, f"thumbs/{tid}/p1_1200x80-150.webp"))
    g.t[key], g.scans[key], g.filenames[key] = tid, path, f"{key}.pdf"
    g.j[f"{key}_v1"], g.j[f"{key}_v2"] = j1, j2
    g.captures[key] = {"sub": sub, "pages": pages, "versions": versions, "student": student_id}
    if student_id == g.student_id:
        g.student_keys.add(key)
    return sub


async def set_graded_student(g: Graph, graded_key: str, student_id: uuid.UUID) -> None:
    async with session() as db:
        await db.execute(text("UPDATE graded_tests SET student_id = :s WHERE id = :g"),
                         {"s": student_id, "g": g.g[graded_key]})
        await db.commit()


# ---------------------------------------------------------------------------
# observation + teardown
# ---------------------------------------------------------------------------

async def row_counts(g: Graph) -> dict[str, int]:
    """Every seeded row, by table — the "nothing touched" witness."""
    q = {
        "students": ("SELECT COUNT(*) FROM students WHERE id = ANY(:ids)",
                     [g.student_id, g.other_student_id]),
        "class_memberships": ("SELECT COUNT(*) FROM class_memberships WHERE class_id = ANY(:ids)",
                              [g.class_id]),
        "transcriptions": ("SELECT COUNT(*) FROM transcriptions WHERE id = ANY(:ids)",
                           list(g.t.values())),
        "transcription_jobs": ("SELECT COUNT(*) FROM transcription_jobs WHERE id = ANY(:ids)",
                               list(g.j.values())),
        "graded_tests": ("SELECT COUNT(*) FROM graded_tests WHERE id = ANY(:ids)",
                         list(g.g.values())),
        "graded_test_pdfs": ("SELECT COUNT(*) FROM graded_test_pdfs WHERE id = ANY(:ids)",
                             g.pdf_ids),
        "grading_batches": ("SELECT COUNT(*) FROM grading_batches WHERE id = ANY(:ids)",
                            [g.batch_id, *g.extra_batches]),
        "rubrics": ("SELECT COUNT(*) FROM rubrics WHERE id = ANY(:ids)", [g.rubric_id]),
        "users": ("SELECT COUNT(*) FROM users WHERE id = ANY(:ids)", [g.user_id]),
        "capture_submissions": ("SELECT COUNT(*) FROM capture_submissions WHERE id = ANY(:ids)",
                                [c["sub"] for c in g.captures.values()]),
        "capture_pages": ("SELECT COUNT(*) FROM capture_pages WHERE id = ANY(:ids)",
                          [p for c in g.captures.values() for p in c["pages"]]),
        "capture_versions": ("SELECT COUNT(*) FROM capture_versions WHERE id = ANY(:ids)",
                             [v for c in g.captures.values() for v in c["versions"]]),
    }
    out = {}
    async with session() as db:
        for table, (sql, ids) in q.items():
            out[table] = (await db.execute(text(sql), {"ids": ids})).scalar_one()
    return out


async def batch_state(batch_id: uuid.UUID) -> tuple[int, list]:
    async with session() as db:
        row = (await db.execute(text(
            "SELECT test_count, transcription_failures FROM grading_batches WHERE id = :b"),
            {"b": batch_id})).one()
    return row[0], row[1]


async def drop_graph(g: Graph) -> None:
    """Explicit, dependency-ordered, idempotent. Deletes by the seeded ids only,
    so it is safe on a shared session user (`user_a`)."""
    ts, js, gs = list(g.t.values()), list(g.j.values()), list(g.g.values())
    subs = [c["sub"] for c in g.captures.values()]
    stmts = [
        ("DELETE FROM graded_test_pdfs WHERE id = ANY(:ids) OR graded_test_id = ANY(:gs)",
         {"ids": g.pdf_ids, "gs": gs}),
        # Whole chains in ONE statement: NO ACTION checks at statement end, and
        # regraded_to_id is deferred to commit.
        ("DELETE FROM graded_tests WHERE id = ANY(:gs) OR transcription_id = ANY(:ts)",
         {"gs": gs, "ts": ts}),
        ("DELETE FROM transcription_jobs WHERE id = ANY(:js) OR transcription_id = ANY(:ts)",
         {"js": js, "ts": ts}),
        ("DELETE FROM transcriptions WHERE id = ANY(:ts)", {"ts": ts}),
        # [036] pages, then versions + submissions together (they reference each other)
        ("DELETE FROM capture_pages WHERE submission_id = ANY(:subs)", {"subs": subs}),
        ("WITH v AS (DELETE FROM capture_versions WHERE submission_id = ANY(:subs) RETURNING 1)"
         " DELETE FROM capture_submissions WHERE id = ANY(:subs)", {"subs": subs}),
        ("DELETE FROM capture_links WHERE batch_id = :b", {"b": g.batch_id}),
        ("DELETE FROM class_memberships WHERE class_id = :c", {"c": g.class_id}),
        ("DELETE FROM students WHERE id = ANY(:ss)",
         {"ss": [g.student_id, g.other_student_id, *g.extra_students]}),
        ("DELETE FROM classes WHERE id = :c", {"c": g.class_id}),
        ("DELETE FROM transcription_jobs WHERE batch_id = ANY(:bs)",
         {"bs": [g.batch_id, *g.extra_batches]}),
        ("DELETE FROM grading_batches WHERE id = ANY(:bs)", {"bs": [g.batch_id, *g.extra_batches]}),
        ("DELETE FROM rubrics WHERE id = :r", {"r": g.rubric_id}),
    ]
    if g.owns_user:
        stmts.append(("DELETE FROM users WHERE id = :u", {"u": g.user_id}))
    async with session() as db:
        for sql, params in stmts:
            await db.execute(text(sql), params)
        await db.commit()
