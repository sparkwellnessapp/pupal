"""
The purge PLAN — read-only, and the whole of the purge's discovery (PR §12,
AM-B5; docs/PURGE_CENSUS.md §19).

The unit is a TRANSCRIPTION SUBTREE: the scan, its jobs, `thumbs/{id}/`, and
every graded-test chain on it with `returned_exams/{id}/`. A student's purge
is the subtrees of her scans, plus her CAPTURE SUBTREES (036), plus her
memberships, plus the student row. Execution deletes exactly this plan and
discovers nothing (PRV-6).

A capture subtree is a `capture_submissions` row naming her, its pages, its
frozen versions, every job compiled from those versions, those jobs'
transcriptions — approved or not, current or withdrawn — and everything under
`captures/{submission_id}/`. An unapproved capture transcription is hers to
delete where an unassigned upload is not: a human (she, or her teacher)
CONFIRMED the student on the capture submission; nothing was name-matched. A
submission holding only a typed, unresolved name is not hers (OD-B6): once
compiled it is an unassigned scan, counted below like any other.

The plan REFUSES — raising `PurgeRefused`, having made no storage call — when
it cannot promise a correct purge:

  selection_mismatch  her graded tests found through her scans differ from
                      those naming her (PRV-10, AM-B5): one of the two
                      selections is wrong, and deleting either would be a guess
  dead_table_rows     a `graded_test_pdfs` row sits under her grades: the
                      table is dead (ruled 2026-09-23), so a live writer is news
  unknown_bucket      a scan names a bucket outside the known set
  unsafe_target       a scan path outside the PRV-11 allow-list
  shared_object       a scan another row still points at (PRV-12)
  capture_mismatch    a scan compiled from her capture submission was approved
                      for ANOTHER student — the approval paths write the
                      approved student back onto the submission (OD-3), so a
                      disagreement is news, and deleting the photos under it
                      would delete someone else's exam

Blockers (a grade `pending`/`grading`, a job `queued`/`running`) do not refuse
the PLAN — the preview shows them — they refuse the purge (PRV-5).

Never on a name match (OD-B6): unassigned scans in her batches are COUNTED,
with their job ids, for the verify report and the audit line. They are not
hers to delete, and the teacher has nothing to do about them.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.capture.paths import split_gs_uri
from app.services.student_signed_tests import signed_tests_count

from .storage import GuardedStorage
from .targets import (
    UnsafeStorageTarget, captures_prefix, returned_exams_prefix, thumbs_prefix, validate_target,
)

BLOCKING_GRADE = ("pending", "grading")
BLOCKING_JOB = ("queued", "running")
OBJECT_FAMILIES = ("transcriptions", "thumbs", "returned_exams", "captures")


class StudentNotFound(LookupError):
    """Not hers, or not there: the caller answers 404 either way (PRV-4)."""


class PurgeRefused(Exception):
    def __init__(self, reason: str, detail: str = ""):
        super().__init__(f"{reason}: {detail}" if detail else reason)
        self.reason = reason
        self.detail = detail


class PurgeBlocked(Exception):
    """A grade or a job is in flight for her (PRV-5, M-B5)."""

    def __init__(self, count: int):
        super().__init__(f"grading_in_progress: {count}")
        self.count = count


@dataclass(frozen=True)
class UnassignedScans:
    count: int
    job_ids: frozenset[UUID]


@dataclass(frozen=True)
class PurgePlan:
    user_id: UUID
    student_id: UUID
    # table → ids; class_memberships is keyed by class id (its PK is (class, student)).
    rows: Mapping[str, frozenset[UUID]]
    # (bucket, name), found by LISTING (M-B7) — never reconstructed.
    objects: frozenset[tuple[str, str]]
    # (bucket, prefix-or-scan) the plan listed: what verify re-lists.
    listed: frozenset[tuple[str, str]]
    batch_recounts: frozenset[UUID]
    legacy_count_batches: frozenset[UUID]          # census E: no jobs ⇒ never recomputed
    failure_scrubs: Mapping[UUID, int]             # batch → 015-ledger entries naming her files
    scrub_filenames: frozenset[str]
    blockers: tuple[UUID, ...]
    unassigned: UnassignedScans
    signed_tests_count: int

    @property
    def case(self) -> str:
        """The Delete dialog's three cases (PR §15)."""
        if self.signed_tests_count > 0:
            return "signed_tests"
        if (self.rows["transcriptions"] or self.rows["graded_tests"]
                or self.rows["capture_submissions"]):
            return "data_only"
        return "nothing"

    def summary(self) -> dict:
        """The preview: counts only — no object name, no filename, and no
        unassigned scans, which are not the teacher's to act on (OD-B6)."""
        return {
            "student_id": str(self.student_id),
            "case": self.case,
            "signed_tests_count": self.signed_tests_count,
            "blockers": len(self.blockers),
            "counts": {t: len(ids) for t, ids in self.rows.items() if t != "students"},
            "objects": {f: sum(1 for (_, n) in self.objects if n.startswith(f + "/"))
                        for f in OBJECT_FAMILIES},
        }


async def _ids(db: AsyncSession, sql: str, **params) -> list:
    return list((await db.execute(text(sql), params)).all())


async def plan_purge(db: AsyncSession, *, user_id: UUID, student_id: UUID,
                     storage: GuardedStorage) -> PurgePlan:
    owned = await db.scalar(text("SELECT id FROM students WHERE id = :s AND user_id = :u"),
                            {"s": student_id, "u": user_id})
    if owned is None:
        raise StudentNotFound(str(student_id))

    # --- her capture subtrees (036) -----------------------------------------
    submissions = [r[0] for r in await _ids(
        db, "SELECT id FROM capture_submissions WHERE student_id = :s", s=student_id)]
    version_rows = await _ids(
        db, "SELECT id, submission_id FROM capture_versions WHERE submission_id = ANY(:subs)",
        subs=submissions)
    versions = [r[0] for r in version_rows]
    page_rows = await _ids(
        db, "SELECT id, submission_id, raw_gcs_uri FROM capture_pages "
            "WHERE submission_id = ANY(:subs)", subs=submissions)
    pages = [r[0] for r in page_rows]
    # A capture PDF lives beside its submission's photos (capture/paths.py), so
    # a job with no scan yet takes its bucket from the photos' recorded uri.
    sub_bucket = {r[1]: split_gs_uri(r[2])[0] for r in page_rows}
    bucket_of_version = {r[0]: sub_bucket.get(r[1]) for r in version_rows}
    capture_scans = await _ids(
        db, "SELECT t.id, t.student_id FROM transcription_jobs j "
            "JOIN transcriptions t ON t.id = j.transcription_id "
            "WHERE j.capture_version_id = ANY(:v)", v=versions)
    foreign = sorted(str(r[0]) for r in capture_scans if r[1] not in (None, student_id))
    if foreign:
        raise PurgeRefused("capture_mismatch",
                           f"compiled from her capture submissions, approved for another "
                           f"student: transcriptions {foreign}")

    scans = await _ids(db, "SELECT id, batch_id, gcs_bucket, gcs_object_path, filename "
                           "FROM transcriptions WHERE student_id = :s OR id = ANY(:c)",
                       s=student_id, c=[r[0] for r in capture_scans])
    t_ids = [r[0] for r in scans]
    by_scan = await _ids(db, "SELECT id, status, batch_id FROM graded_tests "
                             "WHERE transcription_id = ANY(:t)", t=t_ids)
    by_student = {r[0] for r in await _ids(
        db, "SELECT id FROM graded_tests WHERE student_id = :s", s=student_id)}
    g_ids = {r[0] for r in by_scan}
    if g_ids != by_student:
        raise PurgeRefused("selection_mismatch", (
            f"through her scans only: {sorted(map(str, g_ids - by_student))}; "
            f"naming her only: {sorted(map(str, by_student - g_ids))}"))

    # A capture job is hers through its VERSION — including one still queued,
    # failed, or withdrawn with no transcription at all.
    jobs = await _ids(db, "SELECT id, status, batch_id, source_gcs_object_path, source_filename, "
                          "transcription_id, capture_version_id FROM transcription_jobs "
                          "WHERE transcription_id = ANY(:t) OR capture_version_id = ANY(:v)",
                      t=t_ids, v=versions)
    j_ids = [r[0] for r in jobs]
    pdfs = await _ids(db, "SELECT id FROM graded_test_pdfs WHERE graded_test_id = ANY(:g)",
                      g=list(g_ids))
    if pdfs:
        raise PurgeRefused("dead_table_rows",
                           f"graded_test_pdfs rows under her grades: {sorted(str(r[0]) for r in pdfs)}")
    classes = {r[0] for r in await _ids(
        db, "SELECT class_id FROM class_memberships WHERE student_id = :s", s=student_id)}

    blockers = tuple(sorted([r[0] for r in by_scan if r[1] in BLOCKING_GRADE]
                            + [r[0] for r in jobs if r[1] in BLOCKING_JOB], key=str))

    # --- storage targets: every check BEFORE any storage call ---------------
    # A refusal names the ROW, never the path: a path that failed the
    # allow-list may well be a filename, i.e. a student's name, and the detail
    # is logged (OD-B4).
    bucket_of = {r[0]: r[2] for r in scans}
    rows_of: dict[tuple[str, str], list[str]] = {}
    for tid, _, bucket, path, _ in scans:
        rows_of.setdefault((bucket, path), []).append(f"transcription {tid}")
    for jid, _, _, path, _, tid, cv in jobs:
        # a job's scan lives in its scan's bucket; a capture job with no scan
        # yet, beside its submission's photos
        bucket = bucket_of[tid] if tid is not None else bucket_of_version.get(cv)
        rows_of.setdefault((bucket, path), []).append(f"job {jid}")
    scan_objects = set(rows_of)
    for key in sorted(scan_objects):
        if key[0] not in storage.known_buckets:
            raise PurgeRefused("unknown_bucket", f"{key[0]!r}, named by {', '.join(rows_of[key])}")
    for key in sorted(scan_objects):
        try:
            validate_target(key[0], key[1], known_buckets=storage.known_buckets)
        except UnsafeStorageTarget:
            raise PurgeRefused("unsafe_target",
                               f"a path outside the allow-list, named by {', '.join(rows_of[key])}") from None
    for bucket, path in sorted(scan_objects):
        others = await db.scalar(text(
            # :p meets a varchar and a text column; one explicit type for both.
            "SELECT (SELECT COUNT(*) FROM transcriptions "
            "         WHERE gcs_bucket = CAST(:b AS text) AND gcs_object_path = CAST(:p AS text)"
            "           AND NOT (id = ANY(:t)))"
            "     + (SELECT COUNT(*) FROM transcription_jobs "
            "         WHERE source_gcs_object_path = CAST(:p AS text) AND NOT (id = ANY(:j)))"),
            {"b": bucket, "p": path, "t": t_ids, "j": j_ids})
        if others:
            raise PurgeRefused("shared_object", f"the scan of {', '.join(rows_of[(bucket, path)])} "
                                                f"is also referenced by {others} row(s) outside the plan")

    # --- batches: recount from jobs, or exclude (census E) -------------------
    batches = {r[1] for r in scans} | {r[2] for r in by_scan} | {r[2] for r in jobs}
    batches.discard(None)
    with_jobs = {r[0] for r in await _ids(
        db, "SELECT DISTINCT batch_id FROM transcription_jobs WHERE batch_id = ANY(:b)",
        b=list(batches))}
    her_files = {r[4] for r in scans if r[4]} | {r[4] for r in jobs if r[4]}
    scrubs: dict[UUID, int] = {}
    for bid, failures in await _ids(
            db, "SELECT id, transcription_failures FROM grading_batches WHERE id = ANY(:b)",
            b=list(batches)):
        n = sum(1 for f in (failures or []) if isinstance(f, dict) and f.get("filename") in her_files)
        if n:
            scrubs[bid] = n
    # Her unapproved CAPTURE scans are NULL-student too, and they are in the
    # plan — they are hers, not unassigned.
    unassigned_t = [r[0] for r in await _ids(
        db, "SELECT id FROM transcriptions WHERE batch_id = ANY(:b) AND student_id IS NULL "
            "AND NOT (id = ANY(:t))",
        b=list(batches), t=t_ids)]
    unassigned_jobs = {r[0] for r in await _ids(
        db, "SELECT id FROM transcription_jobs WHERE transcription_id = ANY(:t)", t=unassigned_t)}

    # --- objects, by LISTING in every known bucket (M-B7) ---------------------
    targets = sorted(
        {(kb, thumbs_prefix(t)) for kb in storage.known_buckets for t in t_ids}
        | {(kb, returned_exams_prefix(g)) for kb in storage.known_buckets for g in g_ids}
        | {(kb, captures_prefix(sub)) for kb in storage.known_buckets for sub in submissions}
        | scan_objects)

    def _list() -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        for bucket, target in targets:
            names = storage.list_prefix(bucket, target)
            if target.endswith("/"):
                found.update((bucket, n) for n in names)
            else:
                found.update((bucket, n) for n in names if n == target)   # a scan: exact only
        return found

    objects = await asyncio.to_thread(_list)

    return PurgePlan(
        user_id=user_id, student_id=student_id,
        rows={
            "class_memberships": frozenset(classes),
            "graded_tests": frozenset(g_ids),
            "transcription_jobs": frozenset(j_ids),
            "transcriptions": frozenset(t_ids),
            "capture_pages": frozenset(pages),
            "capture_versions": frozenset(versions),
            "capture_submissions": frozenset(submissions),
            "students": frozenset({student_id}),
        },
        objects=frozenset(objects),
        listed=frozenset(targets),
        batch_recounts=frozenset(batches & with_jobs),
        legacy_count_batches=frozenset(batches - with_jobs),
        failure_scrubs=scrubs,
        scrub_filenames=frozenset(her_files),
        blockers=blockers,
        unassigned=UnassignedScans(count=len(unassigned_t), job_ids=frozenset(unassigned_jobs)),
        signed_tests_count=await signed_tests_count(db, user_id, student_id),
    )
