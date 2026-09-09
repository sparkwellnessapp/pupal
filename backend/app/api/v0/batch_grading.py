"""
S11 Batch grading endpoints.

POST /api/v0/batches                         — create + eager transcription fan-out
GET  /api/v0/batches                         — list (user-scoped)
GET  /api/v0/batches/{id}                    — detail + live roll-up + per-test triage
POST /api/v0/batches/{id}/accept_clean       — bulk-accept clean transcriptions
POST /api/v0/batches/{id}/accept/{tid}       — accept one flagged transcription
"""
from __future__ import annotations

import asyncio
import logging
import math
import unicodedata
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from typing import Optional
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from ...api.deps import get_owned_or_404
from ...api.guards import ensure_answer_keys_match_draft
from ...config import settings
from ...database import get_db, get_db_context
from ...models.classroom import Class, ClassMembership
from ...models.grading import GradedTest, GradingBatch, Rubric
from ...models.student import Student
from ...models.transcription import Transcription
from ...models.transcription_job import TranscriptionJob
from ...models.user import User
from ...schemas.batch import (
    AcceptCleanRequest,
    AcceptCleanResponse,
    AcceptCleanSkippedItem,
    AcceptOneTranscriptionRequest,
    ActiveJobItem,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchDetailResponse,
    BatchFileAppendResponse,
    BatchListItem,
    BatchRenameRequest,
    BatchRenameResponse,
    BatchRollup,
    BatchTranscriptionItem,
    FlagVerdictResponse,
    GradeAnswerInputItem,
    ReturnedExamManifest,
    ReturnedExamManifestItem,
    TranscriptionFailureItem,
)
from ...schemas.transcription import (
    AnswerSpaceSelectionGroup,
    TranscriptionContract,
    TranscriptionContractAnswer,
    TranscriptionDraft,
    TranscriptionReview,
)
from ...services.batch_triage import FlagVerdict, compute_flag_verdict, match_student
from ...services.selection_expectation import answer_space_groups
from ...services.cloud_tasks_service import (
    enqueue_grading_task_or_log,
    enqueue_transcription_task,
    verify_task_request,
)
from ...services.grading_job_liveness import reap_expired as reap_expired_grading
from ...schemas.graded_test_contract import GradedTestContract
from ...schemas.graded_test_draft import StampPosition
from ...services.gcs_service import get_gcs_service
from ...services.returned_exam import (
    OVERLAY_KEY,
    ExamRow,
    apply_stamp_default_to_draft,
    current_cache_key,
    effective_stamp_position,
    gcs_object_path,
    manifest_partition,
    unique_zip_entry_names,
)
from ...services.transcription_job_liveness import expired_condition as job_expired_condition
from ...services.transcription_job_liveness import reap_expired as reap_expired_jobs
from ...services.grading_inputs import transcription_contract_version
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v0/batches", tags=["batches"])
internal_router = APIRouter(prefix="/internal/transcription-jobs", tags=["internal"])

async def _enqueue_transcription_or_mark_failed(job_id: UUID) -> None:
    """Hand a committed job to the substrate (Cloud Tasks migration). If the
    enqueue itself fails, the row must not rot as unreachable-'queued' — mark
    it failed so the teacher sees a durable, retryable state (the retry
    endpoint re-enqueues from GCS). Own short session: the request session is
    closed by the time this runs."""
    try:
        await enqueue_transcription_task(job_id)
    except Exception as e:
        logger.exception("transcription_enqueue_failed",
                         extra={"job_id": str(job_id)})
        now = datetime.now(timezone.utc)
        async with get_db_context() as db:
            await db.execute(
                update(TranscriptionJob)
                .where(TranscriptionJob.id == job_id,
                       TranscriptionJob.status == "queued")
                .values(status="failed",
                        error_message=f"enqueue failed: {type(e).__name__}: {str(e)[:300]}",
                        finished_at=now, updated_at=now)
            )
            await db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _derive_batch_status(rollup: BatchRollup) -> str:
    """Derive the batch's aggregate status from child counts. Never stored.

    `dead` counts grading failures, ledgered transcription failures
    (migration 015) and declared-but-never-received files (025/R9) — a batch
    whose every document failed is 'failed', not an eternal 'in_progress' (the
    poll gate keys off this status).

    [Stage A / Defect D] The upload refusal is FIRST and it is explicit. With
    `total = max(expected, jobs)` the arithmetic below already cannot reach
    'completed' while files are outstanding (approved ≤ landed ≤ total), so
    this clause is belt to that braces — deliberately, because the thing it
    prevents is the one failure this surface cannot have: a batch that KEEPS
    COMPUTING and confidently reports "completed" while nine files are still
    climbing the wire (§3.5a). A future change to how `total` is derived must
    not be able to reopen it.
    """
    if rollup.uploading > 0:
        return "in_progress"
    dead = rollup.failed + rollup.transcription_failed + rollup.not_received
    if rollup.total > 0 and dead >= rollup.total:
        return "failed"
    if dead > 0 and rollup.total > 0:
        non_failed = rollup.total - dead
        if rollup.approved >= non_failed:
            return "partially_completed"
    if rollup.total > 0 and rollup.approved == rollup.total:
        return "completed"
    return "in_progress"


def _needs_eyes(transcription: Transcription, verdict: FlagVerdict) -> bool:
    """THE needs-eyes rule, one definition (Ruling 1; ZC-1 v2 2026-08-23).

    v2 (owner refinement): an IDENTITY-PENDING item — content clean, the ONLY
    flag a successfully-extracted new student name (`student_unassigned`),
    untouched — does NOT need her eyes: its home is the CLEAN panel, its name
    rides the identity wave, and creating the student converges it to
    bulk-acceptable. Δ1 still outranks: a touched row needs her regardless.

    NOTE the amended relationship to accept_clean: refusals = needs_eyes +
    identity-pending (accept_clean still refuses pending items — the verdict
    is flagged — but they are counted CLEAN-side; the client excludes them
    from the bulk POST count). This predicate is the SERVER half of a
    cross-language rule — `isIdentityPending` in zone-assignment.ts is the
    frontend half; twin tests reference each other.
    """
    if transcription.status != "transcribed":
        return False
    if transcription.review_json is not None:
        return True
    if not verdict.review_needed:
        return False
    return any(r != "student_unassigned" for r in verdict.reasons)


def _as_utc(dt: datetime) -> datetime:
    """Aware-UTC coercion before any comparison (CLAUDE.md §13). These columns
    ARE TIMESTAMPTZ, so the driver already hands back aware datetimes — but the
    rule is 'never compare a stored timestamp against a bare now()', and the one
    place this codebase skipped it 500'd /auth/login for 271 of 273 users."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def _last_append_at(
    batch: GradingBatch, jobs: list[TranscriptionJob],
) -> Optional[datetime]:
    """When this batch last RECEIVED a file — the clock the R9 backstop runs on.

    Deliberately NOT `batch.updated_at`: a rename, a settings change or a
    re-declare all touch that, and none of them is evidence that a file is
    still coming. The newest job's `created_at` is the append itself; before
    the first append the batch's own creation is the honest start of the wait.
    """
    stamps = [_as_utc(j.created_at) for j in jobs if j.created_at is not None]
    if stamps:
        return max(stamps)
    return _as_utc(batch.created_at) if batch.created_at is not None else None


def _upload_declaration_expired(
    batch: GradingBatch, jobs: list[TranscriptionJob], now: datetime,
) -> bool:
    """Has the batch gone quiet long enough that outstanding files are dead?

    The clock is the LAST APPEND, and before the first append it is the batch's
    own creation — which is R9 read literally ("no append for the TTL"), and is
    deliberate rather than a fallback: after 90 minutes without a single file
    landing, "she walked away" is the overwhelmingly likelier reading, and a
    batch that can never reach a terminal status is the trap LIV-1 exists to
    prevent. It also SELF-HEALS: a late first append makes the newest append
    recent, so the very next read reports `uploading` again.

    The one true degradation is an UNREADABLE clock — no timestamps at all —
    where this returns False and the batch keeps saying "still uploading". The
    two errors are not symmetric: calling a live upload dead lets the batch
    claim a terminal status while her files are on the wire (the Defect D lie,
    one stage earlier), while calling a dead upload live costs only a batch that
    waits. Prefer the honest wait.
    """
    last = _last_append_at(batch, jobs)
    if last is None:
        return False
    return now - last > timedelta(minutes=settings.upload_declaration_ttl_minutes)


def _build_rollup(
    batch: GradingBatch,
    transcriptions: list[Transcription],
    graded_tests: list[GradedTest],
    jobs: list[TranscriptionJob] | None = None,
    needs_eyes: int = 0,
    now: Optional[datetime] = None,
) -> BatchRollup:
    transcribed = sum(1 for t in transcriptions if t.status == "transcribed")
    approved_t = sum(1 for t in transcriptions if t.status == "approved")
    grading = sum(1 for g in graded_tests if g.status in ("pending", "grading"))
    draft = sum(1 for g in graded_tests if g.status == "draft")
    approved_g = sum(1 for g in graded_tests if g.status == "approved")
    failed = sum(1 for g in graded_tests if g.status == "failed")
    total = batch.test_count

    if jobs:
        # Cloud Tasks batches: job rows ARE the truth — "in flight" is a
        # fact, never an inference over absence. Callers reap expired jobs
        # before building the rollup, so active means genuinely active.
        # B9.5: total too — appends grow the batch, so COUNT(jobs) is the
        # denominator; the stored test_count column is legacy-only. (For
        # pre-B9 post-016 batches the two are identical by the Σ invariant.)
        transcribing = sum(1 for j in jobs if j.status in ("queued", "running"))
        transcription_failed = sum(1 for j in jobs if j.status == "failed")
        total = len(jobs)
    else:
        # LEGACY (pre-migration-016 batches): the 015 ledger + row-count
        # inference. Kept read-only for historical batches; no new writes.
        transcription_failed = len(batch.transcription_failures or [])
        transcribing = max(0, total - len(transcriptions) - transcription_failed)

    # ── [Stage A, migration 025] The UPLOAD stage, one step before transcribing.
    #
    # Applied AFTER both branches above and never inside either, because the
    # legacy branch INFERS `transcribing` from `total` — folding the declared
    # count into that subtraction would report files that have not arrived as
    # documents whose VLM call is in flight. Same number, opposite meaning.
    #
    # `expected` NULL ⇒ every value below is untouched and this batch's rollup
    # is byte-identical to the pre-025 response. That is the whole compatibility
    # story: legacy rows AND clients that never learned to declare.
    uploading = 0
    not_received = 0
    landed = len(jobs) if jobs else 0
    declared = batch.expected_test_count
    if declared is not None:
        outstanding = max(0, declared - landed)
        if outstanding > 0:
            if _upload_declaration_expired(
                batch, list(jobs or []), now or datetime.now(timezone.utc)
            ):
                not_received = outstanding
            else:
                uploading = outstanding
        # `max`, not `declared`: appends are allowed for as long as the batch
        # exists, so jobs CAN outrun the declaration. The denominator must never
        # be smaller than the work that actually arrived.
        total = max(declared, landed)

    return BatchRollup(
        uploading=uploading,
        not_received=not_received,
        transcribing=transcribing,
        transcribed=transcribed,
        needs_eyes=needs_eyes,
        approved_transcription=approved_t,
        grading=grading,
        draft=draft,
        approved=approved_g,
        failed=failed,
        transcription_failed=transcription_failed,
        total=total,
    )


def _approved_answers(t: Transcription) -> list[GradeAnswerInputItem] | None:
    """B6: the frozen contract's answers for an APPROVED transcription.
    Per-item degradation: a corrupt contract_json omits the field with a
    warning — one bad row must never 500 the whole batch read."""
    if t.status != "approved" or t.contract_json is None:
        return None
    try:
        contract = TranscriptionContract.model_validate(t.contract_json)
    except Exception:
        logger.warning("corrupt_contract_json_omitted",
                       extra={"transcription_id": str(t.id)})
        return None
    return [
        GradeAnswerInputItem(
            question_number=a.question_number,
            sub_question_id=a.sub_question_id,
            answer_text=a.answer_text,
        )
        for a in contract.answers
    ]


async def _verdict_inputs(
    db: AsyncSession,
    batch: GradingBatch,
    user_id: UUID,
    rubric: Rubric | None = None,
) -> tuple[list[Student], list[AnswerSpaceSelectionGroup]]:
    """The flag-verdict inputs, assembled ONE way for every consumer (B1/OD1):
    get_batch's triage and accept_clean's server-side clean enforcement must
    judge with byte-identical inputs. Do NOT duplicate this assembly.

    Roster for student auto-matching: the batch's class when one is set (the
    teacher's declared scope), otherwise ALL the teacher's students — names
    are unique per teacher (students_unique_name_per_user), so a normalized-
    exact match is never ambiguous. Owner-ruled 2026-08-12: a class-less
    batch previously matched against an EMPTY roster, so auto-assign could
    never fire even when the student already existed.

    Selection awareness: groups from the rubric contract, in answer space,
    so "choose k of N" empties are expected — not flagged missing.
    """
    if batch.class_id:
        roster: list[Student] = await _roster_for_class(db, batch.class_id, user_id)
    else:
        roster = await _roster_all(db, user_id)

    if rubric is None:
        rubric = await db.get(Rubric, batch.rubric_id)
    selection_groups = answer_space_groups(rubric.contract_json if rubric else None)
    return roster, selection_groups


async def _roster_for_class(db: AsyncSession, class_id: UUID, user_id: UUID) -> list[Student]:
    """The ONE roster query for a class-scoped batch. Shared verbatim by the
    single and bulk paths so ORDERING is identical — Postgres' collation for
    Hebrew names is not the same as Python's `sorted()`, and a bulk path that
    re-sorted in Python would hand `match_student` a differently-ordered
    roster. Same SQL, same order, byte-identical inputs."""
    return list((await db.execute(
        select(Student)
        .join(ClassMembership, ClassMembership.student_id == Student.id)
        .where(ClassMembership.class_id == class_id, Student.user_id == user_id)
        .order_by(Student.full_name)
    )).scalars().all())


async def _roster_all(db: AsyncSession, user_id: UUID) -> list[Student]:
    """The class-less roster (owner ruling 2026-08-12: a class-less batch
    matches against ALL the teacher's students, never an empty list)."""
    return list((await db.execute(
        select(Student)
        .where(Student.user_id == user_id)
        .order_by(Student.full_name)
    )).scalars().all())


async def _verdict_inputs_bulk(
    db: AsyncSession,
    batches: list[GradingBatch],
    user_id: UUID,
) -> tuple[
    dict[UUID, tuple[list[Student], list[AnswerSpaceSelectionGroup]]],
    set[UUID],
]:
    """`_verdict_inputs` for MANY batches — one definition, two call shapes
    (closeout/Ruling 1).

    WHY THIS EXISTS: the list page needs a needs-eyes count per batch, and the
    verdict inputs are batch-scoped (roster by the batch's CLASS, selection
    groups from the batch's RUBRIC). A single user-wide roster would be a
    DIFFERENT predicate — the fork the ruling forbids. So instead of calling
    the single helper N times, this groups the work by the two keys that
    actually determine the answer: `class_id` and `rubric_id`. At ~20 batches
    across 3 classes that is ~5 queries instead of ~40, and every roster comes
    from the SAME SQL the single path uses.

    Verified by a differential test over adversarial fixtures, not asserted.

    Returns (inputs_by_batch_id, degraded_batch_ids). A degraded batch is one
    whose selection groups could not be resolved — its verdicts would be
    computed against the WRONG inputs, so the caller must OMIT its count
    rather than publish one it cannot stand behind (see the policy note at
    the degradation site below).
    """
    rosters: dict[UUID | None, list[Student]] = {}
    for class_id in {b.class_id for b in batches if b.class_id}:
        rosters[class_id] = await _roster_for_class(db, class_id, user_id)
    if any(b.class_id is None for b in batches):
        rosters[None] = await _roster_all(db, user_id)

    rubric_ids = {b.rubric_id for b in batches}
    rubrics: dict[UUID, Rubric] = {}
    if rubric_ids:
        rubrics = {
            r.id: r for r in (await db.execute(
                select(Rubric).where(Rubric.id.in_(rubric_ids))
            )).scalars().all()
        }

    # Selection groups per DISTINCT rubric (not per batch), so a rubric shared
    # by five batches is parsed once.
    #
    # ── POLICY (owner-ruled at closeout): DISPLAY PATHS TOLERATE, CONSUMING
    # ── PATHS REFUSE. This is a ruling, not an inconsistency to clean up.
    #
    # `answer_space_groups` validates the contract and is documented to raise
    # loudly on a malformed one ("a loud bug, not a case to paper over").
    # That is right for get_batch, which is the CONSUMING path: a bad contract
    # there means grading is about to eat garbage, and CLAUDE.md §0.5 says a
    # firing guard usually means the logic is wrong.
    #
    # `list_batches` is a DISPLAY path: it reads the contract only to compute
    # a count on a navigation surface, and consumes nothing. Letting one
    # corrupt rubric blind the teacher to EVERY batch she owns is a
    # catastrophic response to a cosmetic need — and it fails in the worst
    # direction, because the list is how she would navigate to fix the very
    # rubric that broke it.
    #
    # So here the failure degrades, and it degrades BY OMISSION rather than by
    # guessing: the rubric is recorded as degraded, its batches publish NO
    # needs-eyes figure, and the client renders the coarser truth instead of a
    # confidently wrong number. (Computing the verdict with empty selection
    # groups would over-count — every "choose k of N" empty would read as a
    # missing answer.) Same rule as D10's hero stats: omit, never invent.
    groups_by_rubric: dict[UUID, list[AnswerSpaceSelectionGroup]] = {}
    degraded_rubrics: set[UUID] = set()
    for rid in rubric_ids:
        rubric = rubrics.get(rid)
        try:
            groups_by_rubric[rid] = answer_space_groups(
                rubric.contract_json if rubric else None
            )
        except Exception:
            # Visible, never silent: the rubric is named so the bad row is
            # findable without reproducing the render.
            logger.warning(
                "corrupt_contract_json_needs_eyes_omitted",
                extra={"rubric_id": str(rid)},
            )
            groups_by_rubric[rid] = []
            degraded_rubrics.add(rid)

    out: dict[UUID, tuple[list[Student], list[AnswerSpaceSelectionGroup]]] = {}
    degraded_batches: set[UUID] = set()
    for b in batches:
        out[b.id] = (rosters.get(b.class_id, []), groups_by_rubric.get(b.rubric_id, []))
        if b.rubric_id in degraded_rubrics:
            degraded_batches.add(b.id)
    return out, degraded_batches


# ---------------------------------------------------------------------------
# POST /batches — create + fan out transcription
# ---------------------------------------------------------------------------

@router.post("", response_model=BatchCreateResponse, status_code=201)
async def create_batch(
    body: BatchCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchCreateResponse:
    """
    B9 intake v2 — metadata-only create. Files arrive ONE PER REQUEST via
    POST /batches/{id}/files: the legacy every-PDF-in-one-multipart body hit
    Cloud Run's 32MB request ceiling at ~5 scans, so a 30–40 test batch (the
    target scenario) could not transit it. Jobs enqueue as files land — the
    first ghost can resolve before the last upload. Appends are allowed for
    as long as the batch exists (no separate "start").
    """
    rubric = await get_owned_or_404(db, Rubric, body.rubric_id, current_user.id)
    if not rubric.is_compiled:
        raise HTTPException(400, "המחוון לא עבר קומפילציה")
    if body.class_id is not None:
        await get_owned_or_404(db, Class, body.class_id, current_user.id)

    name = body.name.strip() if body.name and body.name.strip() else None
    batch = GradingBatch(
        user_id=current_user.id,
        rubric_id=body.rubric_id,
        rubric_contract_version=rubric.contract_version,
        name=name,
        class_id=body.class_id,
        status="in_progress",
        test_count=0,
        # [Stage A, R9] What she DECLARED. Recorded at create time BECAUSE it is
        # a fact only the client holds — the server can never infer it later
        # from the absence of a file (Defect D). None from a client that has not
        # shipped the declaration yet, which is why nothing downstream may
        # require it.
        expected_test_count=body.expected_test_count,
        started_at=datetime.now(timezone.utc),
    )
    db.add(batch)
    await db.commit()

    logger.info("batch_created", extra={
        "batch_id": str(batch.id),
        "class_id": str(body.class_id) if body.class_id else None,
        "expected_test_count": body.expected_test_count,
    })
    return BatchCreateResponse(
        batch_id=str(batch.id), test_count=0,
        expected_test_count=body.expected_test_count,
    )


async def _existing_append(
    db: AsyncSession, batch_id: UUID, client_file_id: UUID,
) -> Optional[BatchFileAppendResponse]:
    """The idempotent-append body: a retried request that already committed
    returns the EXISTING job — same shape, no new test (B9.3)."""
    existing = (await db.execute(
        select(TranscriptionJob).where(
            TranscriptionJob.batch_id == batch_id,
            TranscriptionJob.client_file_id == client_file_id,
        )
    )).scalar_one_or_none()
    if existing is None:
        return None
    count = (await db.execute(
        select(func.count()).select_from(TranscriptionJob)
        .where(TranscriptionJob.batch_id == batch_id)
    )).scalar_one()
    return BatchFileAppendResponse(
        job_id=str(existing.id),
        filename=existing.source_filename,
        test_count=int(count),
    )


#: [Stage D] Above this, the number is not a teacher's uplink.
#:
#: A client clock one millisecond AHEAD of the server's yields a duration of one
#: millisecond and a rate in the tens of Gbit/s — a value that passes every
#: other guard while being pure fiction. 2 Gbit/s is far above any real
#: residential or school uplink and far below what skew produces.
_MAX_PLAUSIBLE_UPLINK_KBPS = 2_000_000


def _client_elapsed_ms(started_ms: Optional[str],
                       received_ms: float) -> Optional[int]:
    """[Stage D] How long the transfer took, by the client's clock.

    Logged in its own right rather than left to be back-computed from the rate:
    `bytes*8/kbps` recovers it only when the rate SURVIVED its guards, and an
    append that took a plausible time from a client whose clock is skewed is
    exactly the row worth seeing. Same soundness rules as the rate.
    """
    if not started_ms:
        return None
    try:
        started = float(started_ms)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(started):
        return None
    elapsed = received_ms - started
    if elapsed <= 0 or elapsed > 86_400_000:
        return None
    return int(elapsed)


def _uplink_kbps(size_bytes: int, started_ms: Optional[str],
                 now_ms: float) -> Optional[int]:
    """[Stage D] Observed uplink for ONE append, in kbit/s, or None.

    THE POINT (and the limit of what this may be used for): the whole latency
    diagnosis rests on ONE teacher's link — 3.67 Mbps measured on a live batch,
    and a ~2.0 Mbps figure INFERRED by fitting the reported four-to-six minutes
    to the measured payload. Neither is a fleet distribution, and whether the
    byte-reduction work (Stage E/F) is worth its eval risk at all depends on
    what the real spread turns out to be. So: measure it.

    LOG ONLY, never a control input (R11). Nothing branches on this number.

    The clock is the CLIENT's, sent as a header, so the value carries the
    client's clock skew and the whole server-side queue time. That is fine for
    a distribution and useless for anything else — which is precisely why this
    returns None rather than a guess whenever the arithmetic is not sound:
    a missing header, an unparseable one, a negative or zero duration (skew),
    or an implausible duration. Publishing a fabricated Mbps into the logs that
    decide a model-input change would be the same confident-wrong-number
    failure this codebase keeps closing (§3.5a).
    """
    if not started_ms:
        return None
    try:
        started = float(started_ms)
    except (TypeError, ValueError):
        return None
    # `float("nan")` PARSES, and NaN fails every comparison below silently —
    # `nan <= 0` and `nan > 86_400_000` are both False — so control would reach
    # `int(... / nan)` and raise ValueError. That raise lands at the log line,
    # i.e. AFTER the GCS upload, AFTER the job row committed and AFTER the task
    # was enqueued: the file is accepted and will transcribe, but the teacher
    # gets a 500 and re-uploads multiple megabytes for nothing. `inf` is caught
    # here too, on the same principle.
    if not math.isfinite(started):
        return None
    elapsed_ms = now_ms - started
    # 24h guards a clock set to the epoch; <=0 guards ordinary skew.
    if elapsed_ms <= 0 or elapsed_ms > 86_400_000:
        return None
    kbps = int(size_bytes * 8 / elapsed_ms)          # bytes/ms → kbit/s
    return None if kbps > _MAX_PLAUSIBLE_UPLINK_KBPS else kbps


@router.post("/{batch_id}/files", response_model=BatchFileAppendResponse)
async def append_batch_file(
    batch_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="One student-test PDF"),
    client_file_id: UUID = Form(..., description="Client-generated idempotency key"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchFileAppendResponse:
    """
    Append one file to a batch (B9): validate (B7, BEFORE GCS — don't store
    garbage) → GCS upload → FOR-UPDATE-serialized job INSERT → commit →
    enqueue. Idempotent on (batch_id, client_file_id). NO silent drop remains
    on any intake path — every rejection is a 422 with a §3.2 reason, every
    downstream failure lands as a durable, retryable failed job.
    """
    await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)

    # ── B7: honest per-file validation, §3.2 reasons verbatim ──
    pdf_bytes = await file.read()
    # [Stage D] The transfer is OVER here: `read()` returns once the body has
    # arrived. Stopping the clock at the log line instead would fold the GCS
    # upload, the FOR-UPDATE insert, the commit and the Cloud Tasks enqueue into
    # a number labelled "uplink" — and under exactly the contention Stage C
    # exists to fix (appends measured at 0.43s → 15.6s when they overlap a
    # transcription) a 3 MB file on a fast link would report ~1.6 Mbit/s instead
    # of ~20. That is not noise: it is a plausible-looking figure biased LOW,
    # i.e. biased toward arguing FOR the eval-risky byte reduction the number is
    # supposed to judge.
    received_at_ms = datetime.now(timezone.utc).timestamp() * 1000.0
    if not pdf_bytes:
        raise HTTPException(422, "קובץ ריק")
    if pdf_bytes[:5] != b"%PDF-":
        raise HTTPException(422, "לא קובץ PDF")
    max_mb = settings.batch_max_upload_file_mb
    if len(pdf_bytes) > max_mb * 1024 * 1024:
        raise HTTPException(422, f"גדול מדי ({max_mb}MB)")

    # ── Idempotency fast-path (network-ambiguous retry) ──
    existing = await _existing_append(db, batch_id, client_file_id)
    if existing is not None:
        return existing

    # ── Durable BEFORE anything runs: bytes → GCS (unchanged path scheme).
    # A GCS failure 502s THIS file only; the batch and its other documents
    # are untouched (the legacy all-or-nothing create is gone). ──
    gcs = get_gcs_service()
    object_path = f"transcriptions/{current_user.id}/{uuid4()}.pdf"
    try:
        await run_in_threadpool(
            gcs.upload_bytes, pdf_bytes, object_path, "application/pdf")
    except Exception:
        # NB: `filename` is a reserved LogRecord attribute — never use it as
        # an `extra` key (it raises KeyError from inside the logger).
        logger.exception("batch_append_upload_failed", extra={
            "batch_id": str(batch_id), "source_filename": file.filename,
        })
        raise HTTPException(
            502, f"ההעלאה של {file.filename or 'הקובץ'} נכשלה — נסי שוב")

    # ── Append serialization (B9.4): FOR UPDATE on the batch row makes
    # doc_priority = current job count race-free under the client's parallel
    # uploads. The lock is held for the count+insert+commit only — never
    # across the GCS round-trip above. ──
    locked_batch = (await db.execute(
        select(GradingBatch).where(GradingBatch.id == batch_id).with_for_update()
    )).scalar_one()
    count = int((await db.execute(
        select(func.count()).select_from(TranscriptionJob)
        .where(TranscriptionJob.batch_id == batch_id)
    )).scalar_one())
    job = TranscriptionJob(
        user_id=current_user.id,
        batch_id=batch_id,
        rubric_id=locked_batch.rubric_id,
        status="queued",
        source_gcs_object_path=object_path,
        source_filename=file.filename,
        doc_priority=count,              # upload order — within-doc depth-first
        client_file_id=client_file_id,
    )
    db.add(job)
    # test_count maintained under the same lock — the column stays honest for
    # humans reading the table, but the rollup's truth for jobs-batches is
    # COUNT(jobs) (B9.5).
    locked_batch.test_count = count + 1
    try:
        await db.commit()
    except IntegrityError:
        # Concurrent duplicate of the same client_file_id: the partial unique
        # index collapses the race into the idempotent path.
        await db.rollback()
        existing = await _existing_append(db, batch_id, client_file_id)
        if existing is not None:
            return existing
        raise
    job_id = job.id
    # Release the connection before the enqueue round-trip (pooler discipline).
    await db.close()

    # Enqueue AFTER commit. A failed enqueue marks ITS job failed — durable +
    # retryable (red card) — never an unreachable 'queued' row.
    await _enqueue_transcription_or_mark_failed(job_id)

    # [Stage D] The fleet-uplink measurement. `uplink_kbps` is None whenever the
    # arithmetic is not sound (no header, skew, NaN, an implausible rate) — an
    # omitted figure, never a fabricated one.
    #
    # ⚠ THE NUMBERS GO IN THE MESSAGE, not only in `extra`. This service
    # configures logging with `basicConfig(format=...%(message)s)` and nothing
    # else — no dictConfig, no JSON formatter, no google-cloud-logging — so an
    # `extra=` key is attached to the LogRecord and then never rendered. Every
    # `extra=` in this file is invisible in Cloud Run today. That is survivable
    # for a breadcrumb; it is fatal for a MEASUREMENT, and this line exists only
    # to be queried in a week. `extra` is kept alongside so the fields are
    # already structured if a formatter is ever added.
    elapsed_ms = _client_elapsed_ms(
        request.headers.get("x-upload-started-ms"), received_at_ms)
    kbps = _uplink_kbps(
        len(pdf_bytes), request.headers.get("x-upload-started-ms"),
        received_at_ms)
    logger.info(
        "batch_file_appended batch=%s job=%s prio=%d bytes=%d "
        "client_elapsed_ms=%s uplink_kbps=%s",
        batch_id, job_id, count, len(pdf_bytes),
        "-" if elapsed_ms is None else elapsed_ms,
        "-" if kbps is None else kbps,
        extra={
            "batch_id": str(batch_id), "job_id": str(job_id),
            "doc_priority": count,
            "bytes": len(pdf_bytes),
            "client_elapsed_ms": elapsed_ms,
            "uplink_kbps": kbps,
        },
    )
    return BatchFileAppendResponse(
        job_id=str(job_id), filename=file.filename, test_count=count + 1,
    )


# ---------------------------------------------------------------------------
# GET /batches — list
# ---------------------------------------------------------------------------

@router.get("", response_model=list[BatchListItem])
async def list_batches(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[BatchListItem]:
    """List all batches for the current user, newest first."""
    # B10: ONE user-scoped bulk reap pass (both kinds) BEFORE any status read —
    # a lapsed batch must show its failure on the list, not only after someone
    # opens its detail page. Never a per-batch reap loop.
    reaped = await reap_expired_jobs(db, user_id=current_user.id)
    reaped += await reap_expired_grading(db, user_id=current_user.id)
    if reaped:
        await db.commit()

    batches = (await db.execute(
        select(GradingBatch)
        .where(GradingBatch.user_id == current_user.id)
        .order_by(GradingBatch.created_at.desc())
    )).scalars().all()

    # B4: display names batch-fetched up front — zero per-batch round-trips
    # added to the existing (known, out-of-scope) N+1.
    rubric_names: dict = dict((await db.execute(
        select(Rubric.id, Rubric.name).where(Rubric.user_id == current_user.id)
    )).all())
    class_names: dict = dict((await db.execute(
        select(Class.id, Class.name).where(Class.user_id == current_user.id)
    )).all())

    # Ruling 1: verdict inputs for EVERY batch, grouped by the two keys that
    # determine them (class_id, rubric_id) — ~5 queries for ~20 batches across
    # 3 classes instead of ~40, using the same roster SQL the single path uses.
    verdict_inputs, degraded_batches = await _verdict_inputs_bulk(
        db, list(batches), current_user.id)

    items = []
    for batch in batches:
        transcriptions = (await db.execute(
            select(Transcription).where(Transcription.batch_id == batch.id)
        )).scalars().all()
        graded_tests = (await db.execute(
            select(GradedTest).where(GradedTest.batch_id == batch.id)
        )).scalars().all()
        jobs = (await db.execute(
            select(TranscriptionJob).where(TranscriptionJob.batch_id == batch.id)
        )).scalars().all()
        roster, selection_groups = verdict_inputs[batch.id]
        # Degrade by OMISSION: this batch's selection groups are unresolvable,
        # so any count would be wrong in a specific direction (over-counting
        # selection empties as missing answers). None ⇒ the client renders the
        # coarser truth for this row only.
        needs_eyes_count: int | None = None if batch.id in degraded_batches else 0
        for t in (transcriptions if needs_eyes_count is not None else []):
            if t.status != "transcribed":
                continue                     # cheap exit before any parsing
            if t.review_json is not None:
                needs_eyes_count += 1        # Δ1 touched — no verdict needed
                continue
            try:
                d = TranscriptionDraft.model_validate(t.draft_json)
            except Exception:
                # A corrupt draft cannot be judged clean — it needs her eyes.
                # (Mirrors _approved_answers' per-item degradation: one bad
                # row never 500s a list read.)
                logger.warning("corrupt_draft_json_counted_needs_eyes",
                               extra={"transcription_id": str(t.id)})
                needs_eyes_count += 1
                continue
            v = compute_flag_verdict(
                d, match_student(d.student_name_suggestion, roster),
                selection_groups=selection_groups,
            )
            if _needs_eyes(t, v):
                needs_eyes_count += 1
        rollup = _build_rollup(batch, list(transcriptions), list(graded_tests), list(jobs),
                               needs_eyes=needs_eyes_count)
        items.append(BatchListItem(
            id=batch.id,
            name=batch.name,
            rubric_id=batch.rubric_id,
            class_id=batch.class_id,
            rubric_name=rubric_names.get(batch.rubric_id),
            class_name=class_names.get(batch.class_id) if batch.class_id else None,
            status=_derive_batch_status(rollup),
            created_at=batch.created_at.isoformat(),
            rollup=rollup,
        ))
    return items


# ---------------------------------------------------------------------------
# PATCH /batches/{id} — rename (B5)
# ---------------------------------------------------------------------------

@router.patch("/{batch_id}", response_model=BatchRenameResponse)
async def rename_batch(
    batch_id: UUID,
    body: BatchRenameRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchRenameResponse:
    """Rename a batch (B5) and set its returned-exam options (PR-G9).

    Only the fields PRESENT in the body are written, so the rename call and the
    settings call share an endpoint without either clobbering the other.

    Both returned-exam settings feed the render cache key, so changing either
    invalidates every cached PDF in the batch. We CLEAR those keys and report
    the count rather than leaving them: a stale PDF is not a slightly-old page,
    it is a document showing points or a stamp the teacher has since changed,
    and it looks entirely correct. Serving it silently is the one outcome this
    feature cannot have (§3.5a).
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)

    # [Stage A, R9] THE RE-DECLARE — how a file that will never land stops
    # blocking completion. Refused BELOW the number of files that already
    # arrived: a declaration is a claim about the future, and it cannot retract
    # work the batch is already holding. Note what is NOT here — the server
    # never lowers this on its own; every downward move is the client saying
    # "that file is not coming" after a terminal verdict or her explicit remove.
    #
    # VALIDATED FIRST, before this handler mutates anything. The count below is
    # a query, and a query autoflushes whatever is already pending on the
    # session — so validating after the rename would push a half-applied PATCH
    # to the database on its way to raising 422.
    if body.expected_test_count is not None:
        landed = int((await db.execute(
            select(func.count()).select_from(TranscriptionJob)
            .where(TranscriptionJob.batch_id == batch_id)
        )).scalar_one())
        if body.expected_test_count < landed:
            raise HTTPException(
                status_code=422,
                detail=f"כבר התקבלו {landed} קבצים במקבץ — לא ניתן להצהיר על פחות",
            )
        batch.expected_test_count = body.expected_test_count

    if body.name is not None:
        name = body.name.strip()
        if not name:
            raise HTTPException(status_code=422, detail="שם המקבץ לא יכול להיות ריק")
        if len(name) > 255:
            raise HTTPException(status_code=422, detail="שם המקבץ ארוך מדי (עד 255 תווים)")
        batch.name = name

    settings_changed = False
    stamp_applied = 0

    if (body.appendix_include_criteria is not None
            and bool(batch.appendix_include_criteria) != body.appendix_include_criteria):
        batch.appendix_include_criteria = body.appendix_include_criteria
        settings_changed = True

    if body.stamp_position_default is not None:
        new_default = body.stamp_position_default.model_dump(mode="json")
        if batch.stamp_position_default != new_default:
            batch.stamp_position_default = new_default
            settings_changed = True
        # «Apply to all»: clear the picker's guesses so they inherit the new
        # default, and leave every position the teacher placed herself.
        rows = (await db.execute(select(GradedTest).where(
            GradedTest.batch_id == batch_id,
            GradedTest.user_id == current_user.id))).scalars().all()
        for row in rows:
            if not row.draft_json:
                continue
            updated, changed = apply_stamp_default_to_draft(row.draft_json)
            if changed:
                row.draft_json = updated
                stamp_applied += 1
        settings_changed = settings_changed or stamp_applied > 0

    invalidated = 0
    if settings_changed:
        invalidated = (await db.execute(
            update(GradedTest)
            .where(GradedTest.batch_id == batch_id,
                   GradedTest.user_id == current_user.id,
                   GradedTest.returned_exam_key.isnot(None))
            .values(returned_exam_key=None)
        )).rowcount or 0

    batch.updated_at = datetime.now(timezone.utc)
    await db.commit()
    logger.info("batch_patched", extra={"batch_id": str(batch_id),
                                        "invalidated": invalidated,
                                        "stamp_applied": stamp_applied,
                                        "expected_test_count": batch.expected_test_count})
    return BatchRenameResponse(
        batch_id=str(batch.id), name=batch.name,
        appendix_include_criteria=bool(batch.appendix_include_criteria),
        stamp_position_default=(StampPosition.model_validate(batch.stamp_position_default)
                                if batch.stamp_position_default else None),
        invalidated_count=invalidated, stamp_applied_count=stamp_applied,
        expected_test_count=batch.expected_test_count)


# ---------------------------------------------------------------------------
# PR-G9 — returned exams: manifest + approved-only ZIP
# ---------------------------------------------------------------------------

async def _exam_rows(db, batch_id, user_id):
    """Every live test in the batch, paired with the key its cached PDF needs."""
    batch = await get_owned_or_404(db, GradingBatch, batch_id, user_id)
    rows = (await db.execute(select(GradedTest).where(
        GradedTest.batch_id == batch_id,
        GradedTest.user_id == user_id,
        GradedTest.regraded_to_id.is_(None),      # leaves only — the live grade
    ))).scalars().all()

    exam_rows, by_id = [], {}
    for row in rows:
        current = None
        if row.status == "approved" and row.contract_json:
            try:
                contract = GradedTestContract.model_validate(row.contract_json)
                stamp = effective_stamp_position(
                    (row.draft_json or {}).get(OVERLAY_KEY, {}).get("stamp_position"),
                    batch.stamp_position_default)
                current = current_cache_key(
                    contract, stamp, bool(batch.appendix_include_criteria))
            except Exception:                       # noqa: BLE001
                # An unreadable contract is a real problem, but it must not blank
                # the manifest. `current` stays None, so the row lands in
                # `excluded_stale` — honest: we cannot prove this PDF is current,
                # so we do not ship it.
                logger.warning("returned_exam_key_uncomputable",
                               extra={"graded_test_id": str(row.id)})
        exam_rows.append(ExamRow(graded_test_id=str(row.id),
                                 student_name=row.student_name,
                                 status=row.status,
                                 cached_key=row.returned_exam_key,
                                 current_key=current))
        by_id[str(row.id)] = row
    return batch, exam_rows, by_id


@router.get("/{batch_id}/returned-exams/manifest", response_model=ReturnedExamManifest)
async def returned_exams_manifest(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReturnedExamManifest:
    """What the ZIP will contain, and what it will not — with the reason."""
    _batch, exam_rows, _by_id = await _exam_rows(db, batch_id, current_user.id)
    part = manifest_partition(exam_rows)

    def items(key):
        return [ReturnedExamManifestItem(graded_test_id=UUID(r.graded_test_id),
                                         student_name=r.student_name)
                for r in part[key]]

    return ReturnedExamManifest(
        included=items("included"),
        excluded_not_approved=items("excluded_not_approved"),
        excluded_stale=items("excluded_stale"))


@router.get("/{batch_id}/returned-exams.zip")
async def returned_exams_zip(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approved, current exams only — the same partition the manifest reports.

    An excluded test is never substituted with a draft render or an older PDF.
    A class set with a stated hole in it is recoverable; a class set with a
    wrong document silently inside it is not.
    """
    batch, exam_rows, by_id = await _exam_rows(db, batch_id, current_user.id)
    included = manifest_partition(exam_rows)["included"]
    if not included:
        raise HTTPException(status_code=404,
                            detail="אין מבחנים מוכנים להורדה עדיין")

    gcs = get_gcs_service()
    # Names minted for the WHOLE set at once: uniqueness is a property of the
    # archive, not of one entry, so it cannot be decided one student at a time.
    entry_names = unique_zip_entry_names(batch.name,
                                         [e.student_name for e in included])
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for entry, entry_name in zip(included, entry_names):
            row = by_id[entry.graded_test_id]
            path = gcs_object_path(row.id, entry.cached_key)
            try:
                pdf = await run_in_threadpool(gcs.download_bytes, path)
            except Exception:                       # noqa: BLE001
                # The key said this render exists and it does not. Omit it — the
                # manifest is the contract for what is inside, and one missing
                # object is not a reason to fail the other twenty-nine.
                logger.warning("returned_exam_object_missing",
                               extra={"graded_test_id": entry.graded_test_id,
                                      "path": path})
                continue
            archive.writestr(entry_name, pdf)

    buffer.seek(0)
    stem = unicodedata.normalize("NFC", (batch.name or "מקבץ").strip())
    filename = f"{stem}_מוחזרים.zip"
    return StreamingResponse(
        buffer, media_type="application/zip",
        headers={"Content-Disposition":
                 "attachment; filename*=UTF-8''" + quote(filename)})


# ---------------------------------------------------------------------------
# GET /batches/{id} — detail + live roll-up
# ---------------------------------------------------------------------------

@router.get("/{batch_id}", response_model=BatchDetailResponse)
async def get_batch(
    batch_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> BatchDetailResponse:
    """
    Full batch detail with live roll-up and per-test triage.
    Poll target for both the transcription-review phase and the grading phase.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)

    # LIV-1 doors, BEFORE any status read (expiry is terminal on read):
    # orphaned transcription jobs → failed (retryable, no re-upload); stuck
    # grading runs → failed (the revision-retry chain). Must precede the
    # graded_tests/jobs selects or this response reports corpses as alive.
    reaped = await reap_expired_jobs(db, batch_id=batch_id)
    reaped += await reap_expired_grading(db, batch_id=batch_id)
    if reaped:
        await db.commit()

    # Deterministic order (Δ10): without ORDER BY, Postgres row order is
    # unspecified and can change between polls — the review route's prev/next
    # cursor depends on this being stable. (created_at, id) = upload order.
    transcriptions = (await db.execute(
        select(Transcription)
        .where(Transcription.batch_id == batch_id)
        .order_by(Transcription.created_at, Transcription.id)
    )).scalars().all()

    graded_tests = (await db.execute(
        select(GradedTest).where(GradedTest.batch_id == batch_id)
    )).scalars().all()

    # Index graded_tests by transcription_id for O(1) lookup
    gt_by_tid: dict[str, GradedTest] = {
        str(gt.transcription_id): gt for gt in graded_tests
    }

    # Shared verdict-input assembly (B1): roster scope + selection groups come
    # from ONE helper so accept_clean's enforcement judges with byte-identical
    # inputs to this endpoint's triage. The Rubric row is loaded once here and
    # passed through so B4 can expose its name without a second query.
    rubric = await db.get(Rubric, batch.rubric_id)
    roster, selection_groups = await _verdict_inputs(
        db, batch, current_user.id, rubric=rubric
    )
    class_name: str | None = None
    if batch.class_id:
        class_name = (await db.execute(
            select(Class.name).where(Class.id == batch.class_id,
                                     Class.user_id == current_user.id)
        )).scalar_one_or_none()

    # Build per-test items
    test_items: list[BatchTranscriptionItem] = []
    needs_eyes_count = 0
    for t in transcriptions:
        draft = TranscriptionDraft.model_validate(t.draft_json)
        student_match = match_student(draft.student_name_suggestion, roster)
        verdict: FlagVerdict = compute_flag_verdict(
            draft, student_match, selection_groups=selection_groups
        )
        # Ruling 1: counted from the SAME verdict this endpoint already
        # computed for the item — the detail page and the list page can never
        # disagree about a batch, because one of them is not recomputing.
        if _needs_eyes(t, verdict):
            needs_eyes_count += 1
        gt = gt_by_tid.get(str(t.id))
        test_items.append(BatchTranscriptionItem(
            transcription_id=t.id,
            filename=t.filename,
            transcription_status=t.status,
            created_at=t.created_at.isoformat(),
            draft=draft,
            review=(
                TranscriptionReview.model_validate(t.review_json)
                if t.review_json is not None else None
            ),
            student_name_suggestion=draft.student_name_suggestion,
            matched_student_id=student_match.student_id,
            matched_student_name=student_match.student_name,
            flag_verdict=FlagVerdictResponse(
                review_needed=verdict.review_needed,
                reasons=verdict.reasons,
            ),
            approved_answers=_approved_answers(t),
            graded_test_id=gt.id if gt else None,
            graded_test_status=gt.status if gt else None,
            total_score=str(gt.total_score) if gt and gt.total_score is not None else None,
            total_possible=str(gt.total_possible) if gt and gt.total_possible is not None else None,
        ))

    jobs = list((await db.execute(
        select(TranscriptionJob)
        .where(TranscriptionJob.batch_id == batch_id)
        .order_by(TranscriptionJob.doc_priority)
    )).scalars().all())

    # Failure cards: failed JOB rows (retryable — job_id present) for Cloud
    # Tasks batches; the read-only 015 ledger for legacy batches.
    if jobs:
        failure_items = [
            TranscriptionFailureItem(
                filename=j.source_filename,
                error=j.error_message or "",
                at=(j.finished_at or j.updated_at).isoformat(),
                net_verdict=j.net_verdict,
                job_id=str(j.id),
            )
            for j in jobs if j.status == "failed"
        ]
    else:
        failure_items = [
            TranscriptionFailureItem.model_validate(f)
            for f in (batch.transcription_failures or [])
        ]

    # B3: in-flight ghosts from the ALREADY-fetched job rows (zero added
    # queries; the SELECT above runs after the reap and orders by
    # doc_priority, so active means genuinely active, in upload order).
    active_jobs = [
        ActiveJobItem(
            filename=j.source_filename,
            state=j.status,
            created_at=j.created_at.isoformat(),
            started_at=j.started_at.isoformat() if j.started_at else None,
            attempt_count=j.attempt_count,
        )
        for j in jobs if j.status in ("queued", "running")
    ]

    rollup = _build_rollup(batch, list(transcriptions), list(graded_tests), jobs,
                           needs_eyes=needs_eyes_count)
    # [PR-G8] the grading half of the feed. Scope count comes from the rubric
    # contract when it parses; the ETA degrades to `unknown` rather than
    # guessing a wave count from nothing.
    scope_count = 0
    try:
        if rubric is not None and rubric.contract_json:
            scope_count = _count_leaf_scopes(rubric.contract_json)
    except Exception:                                # noqa: BLE001
        scope_count = 0
    # [PR-G8] Page-1 thumbnail addressing. Costs NO query: these rows are the
    # ones already loaded above, and `page_count` is the same figure the page
    # routes range-check against — so the feed cannot offer a url the route
    # would 404.
    page_counts = {
        str(t.id): int((t.draft_json or {}).get("page_count") or 0)
        for t in transcriptions
    }
    graded_feed, graded_eta = _build_graded_feed(
        list(graded_tests), scope_count, page_counts)
    return BatchDetailResponse(
        selection_groups=selection_groups,
        transcription_failures=failure_items,
        active_jobs=active_jobs,
        id=batch.id,
        name=batch.name,
        rubric_id=batch.rubric_id,
        class_id=batch.class_id,
        rubric_name=rubric.name if rubric else None,
        class_name=class_name,
        status=_derive_batch_status(rollup),
        started_at=batch.started_at.isoformat() if batch.started_at else None,
        completed_at=batch.completed_at.isoformat() if batch.completed_at else None,
        created_at=batch.created_at.isoformat(),
        rollup=rollup,
        transcriptions=test_items,
        graded_tests=graded_feed,
        eta=graded_eta,
    )


def _count_leaf_scopes(contract_json: dict) -> int:
    """Scopes as the gradable compiler counts them: LEAVES at any depth (PR-3).

    A sub-question that has children contributes NO scope of its own, so a
    naive `len(sub_questions)` over-counts every nested rubric and would quote
    the teacher a wave count — and therefore an ETA — for waves that never run.
    """
    def leaves(node) -> int:
        children = node.get("sub_questions") or []
        if not children:
            return 1
        return sum(leaves(child) for child in children)

    return sum(leaves(q) for q in (contract_json.get("questions") or []))


def _build_graded_feed(graded_tests, rubric_contract_scope_count: int,
                       page_counts: dict[str, int] | None = None):
    """[PR-G8, §1.5] The grading half of the batch feed, plus the ETA.

    `total_awarded` is the EFFECTIVE (overlay-priced) figure — the pencil number
    on the card — read from the row aggregate the pricer already wrote, never
    re-summed here (§5: no consumer re-derives the total).

    The ETA's second stage uses THIS batch's own landings; the first stage falls
    back to the model's measured p50, and to `unknown` when there is no profile.
    """
    from app.schemas.batch import BatchEta, BatchGradedItem
    from app.services.eta import estimate_eta
    from app.services.look_count import look_count
    from app.services.thumbnail import page_image_path
    from app.schemas.graded_test_draft import GradedTestDraft

    page_counts = page_counts or {}
    items, landed = [], []
    for gt in graded_tests:
        looks = None
        if gt.draft_json:
            try:
                looks = look_count(GradedTestDraft.model_validate(gt.draft_json))
            except Exception:                       # noqa: BLE001
                # DEGRADE BY OMISSION, never by guessing (§3.5a). Reporting 0
                # here would say "nothing to look at" — a confident wrong
                # answer in the dangerous direction, since it is precisely the
                # unparseable drafts that most need her eye. `null` lets the
                # client render "unknown" instead of a reassuring zero.
                logger.warning("look_count_unavailable",
                               extra={"graded_test_id": str(gt.id)})
        if gt.draft_created_at and gt.grading_started_at:
            landed.append((gt.draft_created_at - gt.grading_started_at).total_seconds())

        items.append(BatchGradedItem(
            graded_test_id=gt.id,
            student_id=gt.student_id,
            student_name=gt.student_name,
            status=gt.status,
            landed_at=gt.draft_created_at.isoformat() if gt.draft_created_at else None,
            opened_at=gt.opened_at.isoformat() if gt.opened_at else None,
            total_awarded=gt.total_score,
            look_count=looks,
            # Omitted — not guessed — when this test's transcription has no
            # page 1 (§3.5a). Offering a url the route would 404 renders a
            # broken-image glyph, which reads as "this test is damaged".
            page1_image_url=(
                page_image_path(gt.transcription_id, 1)
                if page_counts.get(str(gt.transcription_id), 0) >= 1 else None
            ),
        ))

    profile = (settings.latency_profile or {}).get(settings.grader_model_key or "")
    eta = estimate_eta(profile_p50=profile,
                       scope_count=rubric_contract_scope_count,
                       landed_durations=landed)
    return items, BatchEta(**eta)


def _accept_clean_halt_message(filename: str | None) -> str:
    """E2: the halt message a teacher can act on. Names the file when known —
    she chose files, not UUIDs — and states plainly that nothing was accepted,
    because the optimistic dimming she just watched revert implies otherwise."""
    if filename:
        return f'האישור המרוכז נעצר על הקובץ "{filename}" — אף מבחן לא אושר. אפשר לאשר אותו בנפרד ואז לנסות שוב.'
    return "האישור המרוכז נעצר — אף מבחן לא אושר."


# ---------------------------------------------------------------------------
# POST /batches/{id}/accept_clean — bulk-accept clean transcriptions
# ---------------------------------------------------------------------------

@router.post("/{batch_id}/accept_clean", response_model=AcceptCleanResponse)
async def accept_clean(
    batch_id: UUID,
    body: AcceptCleanRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AcceptCleanResponse:
    """
    Bulk-accept clean transcriptions (no teacher edits needed).
    For each item:
      - Recomputes the flag verdict SERVER-side (B1/OD1 — "clean" is a
        server-guaranteed property; the client's filter is belt, this is
        suspenders): review_needed ⇒ skipped {"flagged"}, row untouched.
      - Builds the contract from the transcription's draft answers (accepted as-is).
      - Updates the transcription to 'approved' with student assignment.
      - Inserts a pending GradedTest with batch_id.
      - Enqueues one grading Cloud Task per item (after the single commit).

    All items are committed in a single transaction. Every non-accepted item
    is REPORTED in `skipped` — nothing is silently dropped.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    # Same verdict inputs get_batch uses (shared helper — B1). The roster is
    # read NOW, so a student created between the client's render and this POST
    # legitimately flips an item clean (that is convergence, not a race bug).
    roster, selection_groups = await _verdict_inputs(db, batch, current_user.id)

    queued = 0
    skipped: list[AcceptCleanSkippedItem] = []
    graded_test_ids: list[UUID] = []
    # E2 (closeout, owner-ruled MINIMAL fix — transaction semantics UNCHANGED):
    # this endpoint is all-or-nothing by design, and B1's server-side skip
    # already absorbs flagged/edited/approved rows, so a mid-loop RAISE is
    # rare. The hazard is what happens when it does: one poisoned row aborts
    # the whole bulk accept, the teacher's optimistic dimming reverts, and
    # nothing tells her WHICH row — so she re-clicks forever. The response
    # below names the offending transcription (id + filename) and the reason.
    # Per-item commits with partial-success reporting are BACKLOGGED, to be
    # promoted only if this ever actually fires.
    current_item_id: str | None = None
    current_filename: str | None = None
    try:
        for item in body.items:
            current_item_id = str(item.transcription_id)
            current_filename = None
            # Fresh per-item read INSIDE this transaction — the Δ1 overlay check
            # below must see an overlay written from another tab up to this moment,
            # never a stale prefetch.
            transcription = await get_owned_or_404(
                db, Transcription, item.transcription_id, current_user.id
            )
            current_filename = transcription.filename
            if transcription.batch_id != batch_id:
                raise HTTPException(400, f"Transcription {item.transcription_id} does not belong to batch {batch_id}")
            if transcription.status != "transcribed":
                # Idempotent repost / approved via another path — reported, not
                # silently dropped (B1: the dashboard surfaces every skip).
                skipped.append(AcceptCleanSkippedItem(
                    transcription_id=str(transcription.id),
                    skipped_reason="already_approved",
                ))
                continue
            # Teacher-touched ⇒ not "clean" (Δ1): a saved review overlay must never
            # be silently discarded by a bulk accept that reads the draft as-is.
            # Checked BEFORE the verdict so an edited row keeps its Δ1 reason.
            if transcription.review_json is not None:
                skipped.append(AcceptCleanSkippedItem(
                    transcription_id=str(transcription.id),
                    skipped_reason="has_review_edits",
                ))
                continue

            draft = TranscriptionDraft.model_validate(transcription.draft_json)

            # B1/OD1 — server-side clean enforcement: recompute the verdict with
            # the live roster + selection groups. A flagged item never freezes a
            # machine-text contract, no matter what the client selected.
            verdict = compute_flag_verdict(
                draft,
                match_student(draft.student_name_suggestion, roster),
                selection_groups=selection_groups,
            )
            if verdict.review_needed:
                skipped.append(AcceptCleanSkippedItem(
                    transcription_id=str(transcription.id),
                    skipped_reason="flagged",
                ))
                continue

            # Build contract from draft answers (clean accept = no edits)
            contract = TranscriptionContract(
                answers=[
                    TranscriptionContractAnswer(
                        question_number=a.question_number,
                        sub_question_id=a.sub_question_id,
                        answer_text=a.answer_text,
                    )
                    for a in draft.answers
                ]
            )

            student = await get_owned_or_404(db, Student, item.student_id, current_user.id)
            now = datetime.now(timezone.utc)

            # Atomic: approve transcription (satisfies CHECK constraint)
            transcription.contract_json = contract.model_dump(mode="json")
            transcription.student_id = student.id
            transcription.student_name = student.full_name
            transcription.status = "approved"
            transcription.approved_at = now
            transcription.updated_at = now
            # Always None here (the Δ1 guard above skipped overlay rows), but the
            # null-out is uniform across all three approval paths: part of the
            # transition write, not a mutation of an approved row (LCY-1).
            transcription.review_json = None

            # Insert pending graded_test with batch_id
            graded_test = GradedTest(
                user_id=current_user.id,
                rubric_id=batch.rubric_id,
                transcription_id=transcription.id,
                student_id=student.id,
                student_name=student.full_name,
                filename=transcription.filename,
                rubric_contract_version=batch.rubric_contract_version,
                # [029] The OTHER pinned input (see services/grading_inputs). Read
                # AFTER the approval write above, so it is the contract the grader
                # will actually consume. Recorded, never inferred.
                transcription_contract_version=transcription_contract_version(transcription),
                status="pending",
                batch_id=batch_id,
            )
            db.add(graded_test)
            await db.flush()

            graded_test_ids.append(graded_test.id)
            queued += 1

    except HTTPException as exc:
        # Preserve the original status (404 student, 400 wrong-batch) but
        # re-raise with the item NAMED. `detail` is a dict: FastAPI passes it
        # through as the JSON body, and the client reads .transcription_id.
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "error": "accept_clean_failed",
                "transcription_id": current_item_id,
                "filename": current_filename,
                "reason": str(exc.detail),
                "accepted": 0,
                # `message_he` is the established structured-detail field the
                # frontend seam already extracts (normalizeError) — so this
                # surfaces as an ACTIONABLE Hebrew string on both bulk call
                # sites with zero client change. The filename is embedded
                # because a teacher cannot act on a UUID.
                "message_he": _accept_clean_halt_message(current_filename),
            },
        ) from exc
    except Exception as exc:
        logger.exception(
            "batch_accept_clean_failed",
            extra={"batch_id": str(batch_id), "failed_transcription": current_item_id},
        )
        raise HTTPException(
            status_code=500,
            detail={
                "error": "accept_clean_failed",
                "transcription_id": current_item_id,
                "filename": current_filename,
                "reason": f"{type(exc).__name__}: {exc}",
                "accepted": 0,
                "message_he": _accept_clean_halt_message(current_filename),
            },
        ) from exc

    await db.commit()
    # Release the connection before the enqueue round-trips.
    await db.close()

    # Enqueue AFTER commit (the handler claims the row by CAS). A failed
    # enqueue leaves a durable pending row — the grading dispatch backstop
    # (grading_job_liveness) reaps it to failed → the revision-retry chain.
    await asyncio.gather(*(
        enqueue_grading_task_or_log(gt_id) for gt_id in graded_test_ids
    ))
    logger.info(
        "batch_accept_clean",
        extra={"batch_id": str(batch_id), "queued": queued, "skipped": len(skipped)},
    )
    # `skipped` is additive: the pre-Phase-4 client parses this response with a
    # plain res.json() and ignores unknown fields (verified — plan Δ18).
    return AcceptCleanResponse(accepted=queued, skipped=skipped)


# ---------------------------------------------------------------------------
# POST /batches/{id}/accept/{transcription_id} — accept one flagged test
# ---------------------------------------------------------------------------

@router.post("/{batch_id}/accept/{transcription_id}")
async def accept_one(
    batch_id: UUID,
    transcription_id: UUID,
    body: AcceptOneTranscriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Accept a single (possibly flagged) transcription with teacher-reviewed answers.
    Same commit pattern as accept_clean but uses the body's answers instead of
    pulling from draft_json, allowing the teacher to correct any detected issues.
    """
    batch = await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)
    transcription = await get_owned_or_404(db, Transcription, transcription_id, current_user.id)

    if transcription.batch_id != batch_id:
        raise HTTPException(400, f"Transcription {transcription_id} does not belong to batch {batch_id}")
    if transcription.status != "transcribed":
        return {"accepted": 0, "message": "already accepted"}

    # B2: the approval write validates no LESS than the overlay save — the
    # same full-snapshot key-multiset guard, the same 422 detail (shared
    # constant in api/guards.py). Runs before any mutation: on mismatch the
    # row is untouched and no GradedTest exists.
    draft = TranscriptionDraft.model_validate(transcription.draft_json)
    ensure_answer_keys_match_draft(draft, body.answers)

    contract = TranscriptionContract(
        answers=[
            TranscriptionContractAnswer(
                question_number=a.question_number,
                sub_question_id=a.sub_question_id,
                answer_text=a.answer_text,
            )
            for a in body.answers
        ]
    )

    student = await get_owned_or_404(db, Student, body.student_id, current_user.id)
    now = datetime.now(timezone.utc)

    transcription.contract_json = contract.model_dump(mode="json")
    transcription.student_id = student.id
    transcription.student_name = student.full_name
    transcription.status = "approved"
    transcription.approved_at = now
    transcription.updated_at = now
    # Part of the 'transcribed'→'approved' transition write, not a mutation of
    # an approved row (LCY-1): the overlay's job ends at approval.
    transcription.review_json = None

    graded_test = GradedTest(
        user_id=current_user.id,
        rubric_id=batch.rubric_id,
        transcription_id=transcription.id,
        student_id=student.id,
        student_name=student.full_name,
        filename=transcription.filename,
        rubric_contract_version=batch.rubric_contract_version,
        # [029] The OTHER pinned input (see services/grading_inputs). Read
        # AFTER the approval write above, so it is the contract the grader
        # will actually consume. Recorded, never inferred.
        transcription_contract_version=transcription_contract_version(transcription),
        status="pending",
        batch_id=batch_id,
    )
    db.add(graded_test)
    await db.flush()
    graded_test_id = graded_test.id
    await db.commit()
    # Release the connection before the enqueue round-trip.
    await db.close()

    await enqueue_grading_task_or_log(graded_test_id)

    logger.info("batch_accept_one", extra={
        "batch_id": str(batch_id),
        "transcription_id": str(transcription_id),
    })
    return {"accepted": 1}


# ---------------------------------------------------------------------------
# POST /batches/{id}/jobs/{job_id}/retry — per-document retry (no re-upload)
# ---------------------------------------------------------------------------

@router.post("/{batch_id}/jobs/{job_id}/retry")
async def retry_transcription_job(
    batch_id: UUID,
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Re-queue a failed job, or any EXPIRED active one (LIV-1: a dispatch
    lost past the queued backstop, or a worker whose heartbeat lapsed). The
    source PDF is in GCS — the teacher never re-uploads.

    Atomic CAS: the WHERE encodes exactly the legal retry sources; the full
    reset satisfies the 'queued' arm of the status-consistency CHECK
    (error/verdict/timestamps cleared; attempt_count survives — it counts
    claims, and increments again at the next claim)."""
    await get_owned_or_404(db, GradingBatch, batch_id, current_user.id)

    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(TranscriptionJob)
        .where(
            TranscriptionJob.id == job_id,
            TranscriptionJob.batch_id == batch_id,
            ((TranscriptionJob.status == "failed") | job_expired_condition(now)),
        )
        .values(status="queued", error_message=None, net_verdict=None,
                started_at=None, finished_at=None, updated_at=now)
    )
    if result.rowcount == 0:
        await db.rollback()
        raise HTTPException(status_code=409, detail="המשימה עדיין פעילה או שכבר הושלמה")
    await db.commit()
    await db.close()

    await _enqueue_transcription_or_mark_failed(job_id)
    logger.info("transcription_job_retried",
                extra={"job_id": str(job_id), "batch_id": str(batch_id)})
    return {"job_id": str(job_id), "status": "queued"}


# ---------------------------------------------------------------------------
# INTERNAL: Cloud Tasks target — NOT behind get_current_user
# ---------------------------------------------------------------------------

@internal_router.post("/{job_id}/run", include_in_schema=False)
async def run_transcription_job_task(job_id: UUID, request: Request) -> dict:
    """Executes the transcription INSIDE this request (CPU guaranteed for its
    duration). Idempotent: the runner's first statement is the queued→running
    CAS — a duplicate delivery (the queue runs maxAttempts=3) or an
    already-terminal row is a 200 no-op. Always 200 on auth success: a non-2xx
    would trigger a redelivery of work the row already accounts for."""
    reason = verify_task_request(request)
    if reason is not None:
        logger.warning("internal_transcription_run_rejected",
                       extra={"job_id": str(job_id), "reason": reason})
        raise HTTPException(status_code=403, detail="Forbidden")

    from ...services.transcription_job_runner import run_transcription_job

    ran = await run_transcription_job(job_id)
    return {"job_id": str(job_id), "ran": ran}
