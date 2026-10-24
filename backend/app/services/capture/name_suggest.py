"""
The teacher page's name suggestion (§6.9; SCN-10, SCN-12; ruling OD-7).

After page 1 of a TEACHER-source submission is analyzed, the client asks for
a suggestion: scan-service renders page 1 flattened and cleaned (long side
1600), and the roster-aware reader in `transcription/identity.py` — the
identity pass's own crop and name-field rules, closed-world over the batch's
class roster — reads the name. Nothing is assigned: the response pre-fills
her picker, and her click is the assignment (OD-S2/OD-S4).

It never blocks and never raises past here: a render failure, a provider
outage, a timeout or a garbled answer is the same {null, null, low}.
Student-link submissions never reach it (SCN-10), and nothing it reads is
written into a transcription.
"""
from __future__ import annotations

import asyncio
import io
import logging
import time
from uuid import UUID

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import settings
from ...models.grading import GradingBatch
from ...schemas.capture import NameSuggestResponse, StudentRef
from ..transcription import identity
from . import paths
from .actors import CaptureError, TeacherActor
from .naming import class_roster
from .scan_client import get_scan_client
from .submissions import live_pages, load_submission

logger = logging.getLogger(__name__)

RENDER_LONG_SIDE = 1600
RENDER_TIMEOUT_S = 10.0


def _provider():
    """(provider, scheduler, key): the fast model on the SHARED provider set
    and scheduler when the engine already dispatches to it (it does — the
    strike check's key), so the per-model cap is one cap."""
    from ..transcription.two_phase_engine import _MODELS, _make_provider, _shared_infra

    key = settings.scan_name_model
    providers, _aliased, scheduler = _shared_infra()
    if key in providers:
        return providers[key], scheduler, key
    return _make_provider(_MODELS[key]), None, ""


async def suggest(db: AsyncSession, actor: TeacherActor, submission_id: UUID) -> NameSuggestResponse:
    sub = await load_submission(db, actor, submission_id)
    if sub.source != "teacher":                                            # SCN-10
        raise CaptureError(409, "not_teacher_source", "זיהוי שם זמין רק בצילום של המורה")
    pages = await live_pages(db, sub.id)
    first = pages[0] if pages else None
    if first is None or first.status != "analyzed":
        raise CaptureError(409, "page1_not_analyzed", "העמוד הראשון עוד לא מוכן")
    batch = await db.get(GradingBatch, sub.batch_id)
    roster = [(str(s.id), s.full_name)
              for s in await class_roster(db, batch.class_id, actor.user_id)]
    names = dict(roster)
    raw_uri, corners, rotation = first.raw_gcs_uri, first.corners, first.rotation
    render_path = paths.name_render_path(sub.id, first.id)
    await db.commit()                    # never hold a transaction across the calls

    started = time.monotonic()
    result = identity.NO_SUGGESTION
    try:
        await get_scan_client().render(raw_uri, corners, rotation, RENDER_LONG_SIDE,
                                       paths.gs_uri(settings.gcs_bucket_name, render_path),
                                       enhance=True, timeout_s=RENDER_TIMEOUT_S)
        from ..gcs_service import get_gcs_service
        jpeg = await asyncio.to_thread(get_gcs_service().download_bytes, render_path)
        image = Image.open(io.BytesIO(jpeg))
        provider, scheduler, key = _provider()
        result = await identity.suggest_from_roster(
            image, roster, provider, doc_id=str(sub.id),
            timeout_s=settings.scan_name_timeout_s, scheduler=scheduler, provider_key=key)
    except Exception as exc:                                       # never blocks (§6.9)
        logger.warning("capture_name_suggest_failed submission=%s error=%s",
                       sub.id, type(exc).__name__)
    # Ids and outcomes only — never the name read or the roster (OD-B4).
    logger.info("capture_name_suggest submission=%s model=%s prompt=%s read=%s matched=%s "
                "confidence=%s roster=%d ms=%d", sub.id, settings.scan_name_model,
                identity.NAME_PROMPT_VERSION, result.read_name is not None,
                result.student_id is not None, result.confidence, len(roster),
                int((time.monotonic() - started) * 1000))
    match = None
    if result.student_id is not None:
        match = StudentRef(student_id=UUID(result.student_id), display_name=names[result.student_id])
    return NameSuggestResponse(read_name=result.read_name, match=match,
                               confidence=result.confidence)
