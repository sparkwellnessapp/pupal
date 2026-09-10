"""Produce-or-reuse the returned exam PDF for ONE approved graded test.

WHY THIS MODULE EXISTS. The bytes a student receives were reachable from two
places that disagreed about what a cache MISS means:

  * `GET /graded_test/{id}/returned-exam` rendered on a miss — "the key is a
    claim about the object, and the object is the truth".
  * `GET /batches/{id}/returned-exams.zip` treated a miss as a reason to
    WITHHOLD the exam.

Since the single-test preview was the ONLY writer of `graded_tests
.returned_exam_key`, a teacher who approved a batch and clicked «הורדת כל
המבחנים המוחזרים» downloaded nothing at all — every row had a NULL key, so every
row was excluded. Observed live on a five-test batch: all five approved, all five
with frozen contracts, all five omitted, and the modal told her no test had been
approved.

The cache is an OPTIMISATION, not a gate. Both callers now come here, so a miss
means the same thing on every path: render it.

THE FRESHNESS RULE IS UNCHANGED AND IS THE POINT. The key covers every input that
can change a pixel; when it does not match, this re-renders rather than serving
the old object. A returned exam rendered under a superseded contract looks
entirely correct and is the one failure this feature cannot have (§3.5a) — so
"stale" stops being a reason to EXCLUDE an exam and becomes a reason to REBUILD
it.
"""
import logging

from fastapi.concurrency import run_in_threadpool

from ..models.grading import GradedTest, GradingBatch
from ..models.transcription import Transcription
from ..schemas.graded_test_contract import GradedTestContract
from .gcs_service import get_gcs_service
from .points_display import format_points
from .returned_exam import (
    OVERLAY_KEY,
    current_cache_key,
    effective_stamp_position,
    gcs_object_path,
    render_returned_exam,
    scopes_for_render,
    summary_for_render,
)

logger = logging.getLogger(__name__)

class ReturnedExamUnavailable(Exception):
    """This exam cannot be produced, and the caller must NOT substitute one.

    Raised for a row that is not approved, carries no readable contract, or
    whose source scan is gone. Every one of those is a reason to omit the
    document and say so — never to ship a draft render or an older PDF in its
    place (§3.5a: degrade by omission, never by substitution).

    `reason` is a CODE, not prose: the single-test endpoint maps each cause to
    its own status and its own Hebrew sentence, and a caller that had to parse
    a message to do that would be one refactor away from mapping them wrong.
    """

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason


def _render_inputs(row: GradedTest, batch: GradingBatch | None):
    """Contract, stamp and criteria flag — the three things the key covers."""
    contract = GradedTestContract.model_validate(row.contract_json)
    include_criteria = bool(getattr(batch, "appendix_include_criteria", False))
    stamp = effective_stamp_position(
        (row.draft_json or {}).get(OVERLAY_KEY, {}).get("stamp_position"),
        getattr(batch, "stamp_position_default", None),
    )
    return contract, stamp, include_criteria


async def returned_exam_pdf(db, row: GradedTest, batch: GradingBatch | None) -> bytes:
    """The student's returned exam for one approved graded test.

    Serves the cached object when its key matches the CURRENT inputs, and
    renders + caches otherwise. Commits the new key.

    Raises `ReturnedExamUnavailable` when the exam cannot be produced. It never
    returns a document built from anything but the frozen contract.
    """
    if row.status != "approved" or not row.contract_json:
        raise ReturnedExamUnavailable("not_approved")

    try:
        contract, stamp, include_criteria = _render_inputs(row, batch)
        key = current_cache_key(contract, stamp, include_criteria)
    except Exception as exc:                                   # noqa: BLE001
        # An unreadable contract is a real problem, but the honest response is
        # to omit THIS exam rather than to guess at its contents.
        logger.warning("returned_exam_key_uncomputable graded_test_id=%s: %s",
                       row.id, exc)
        raise ReturnedExamUnavailable("contract_unreadable", str(exc)) from exc

    gcs = get_gcs_service()
    path = gcs_object_path(row.id, key)

    if row.returned_exam_key == key:
        try:
            return await run_in_threadpool(gcs.download_bytes, path)
        except Exception:                                      # noqa: BLE001
            # The row claims a render that is not in the bucket. Fall through
            # and rebuild: the key is a claim ABOUT the object, and the object
            # is the truth.
            logger.warning("returned_exam_cache_miss graded_test_id=%s path=%s",
                           row.id, path)

    transcription = await db.get(Transcription, row.transcription_id)
    if transcription is None:
        raise ReturnedExamUnavailable("scan_missing")
    source_pdf = await run_in_threadpool(gcs.download_bytes,
                                         transcription.gcs_object_path)

    pdf = await run_in_threadpool(
        render_returned_exam,
        source_pdf,
        row.student_name,
        scopes_for_render(contract, include_criteria),
        summary_for_render(contract),
        stamp,
        include_criteria,
        # [OD-2] the stamp carries her grade. From the CONTRACT — the frozen
        # number she signed — never re-summed from the rendered scopes.
        format_points(contract.total_score),
        format_points(contract.total_possible),
    )
    await run_in_threadpool(gcs.upload_bytes, pdf, path, "application/pdf")

    row.returned_exam_key = key
    await db.commit()
    logger.info("returned_exam_rendered graded_test_id=%s bytes=%d", row.id, len(pdf))
    return pdf
