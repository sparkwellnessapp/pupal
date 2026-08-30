"""
identity.py — the student-name identity pass (B-25 fix, 2026-08-12).

The two-phase P1 prompt deliberately EXCLUDES the student identity block from
its verbatim output (anti-contamination — identity must never leak into
graded content), which starved the downstream auto-match machinery:
student_name_suggestion was hard-coded None, every batch item flagged
student_unmatched, and bulk-accept was unreachable.

This module is the replacement channel, fully separate from the reading
pipeline: ONE cheap VLM call over a TOP-CROP of page 1 (the handwritten
name sits in the exam header), with the PDF filename as a fallback the model
may use only when it plausibly is a person's name (owner-specified priority).
Probe-validated 2026-08-12: 5/5 handwritten Hebrew names on the golden
fixtures + correct filename fallback + null on scanner junk.

Contract: best-effort HINT only. The output feeds student_name_suggestion →
the conservative normalized-EXACT roster match → the teacher-visible picker.
Any failure (render, provider, parse, timeout) returns None — the identity
pass can never sink or delay a transcription (it runs concurrently with the
pipeline and is bounded by its own timeout).
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging

from PIL import Image
from starlette.concurrency import run_in_threadpool

from ..handwriting_transcription_service import render_pdf_page
from .two_phase.parsing import parse_model_json
from .vlm_provider import VLMProvider

logger = logging.getLogger(__name__)

# The header region: the name is generally at the top of page 1 (observed in
# the top ~10%; 35% is generous headroom for position variance).
CROP_FRACTION = 0.35
RENDER_DPI = 200
# 60s, not 30 (2026-08-12): on a congested uplink even this ~300KB crop
# stalls mid-transfer — both attempts of both docs died at exactly 30s in the
# observed batch while slower-but-patient P1 calls landed. Same doctrine as
# the 240s P1 timeout: a slowly-succeeding upload must not be killed. On a
# healthy network the call returns in 5-10s, so the ceiling never bites.
CALL_TIMEOUT_S = 60.0
# Belt over everything: render + (queue + 2 call attempts + scheduler retry
# delay) + parse ≈ 2×60 + ~2 + queue. Identity is gathered WITH the pipeline,
# so this ceiling adds wall time only when the pipeline finished first while
# identity is still timing out — i.e. exactly when the network is bad and the
# pipeline was slow too.
TOTAL_TIMEOUT_S = 150.0

# ── Filename plausibility — the CODE half of B-25's fallback clause ──────────
# Live-E2E finding (2026-08-22): the fallback lived ONLY in the model prompt,
# so when the model call never happened (identity starved in the gemini lane
# behind P1 chunks: cap 5, chunks running 57-195s, identity's 150s total
# timeout expiring inside `lim.acquire`), files literally NAMED after the
# student (רז כהן.pdf) yielded no suggestion — 7/10 in the observed batch.
# This is the same judgment the prompt asks of the model, as code, applied
# only when the model path fails. CONSERVATIVE by the same logic as the
# roster match: a wrong pre-seed is worse than none.

_GENERIC_WORDS = frozenset({
    "סריקה", "מסמך", "עמוד", "קובץ", "מבחן", "בגרות", "מתכונת", "דוח",
    "ציונים", "כיתה", "שאלון", "טיוטה", "חדש", "קיץ", "חורף", "תשובות",
})


def plausible_name_from_filename(filename: str | None) -> str | None:
    """Hebrew-person-name plausibility for a PDF filename. Pure.

    Accepts 2-4 tokens of Hebrew letters (geresh/gershayim/hyphen allowed),
    after stripping the extension and mapping underscores to spaces. Rejects
    anything with digits/Latin, single tokens, >4 tokens, and generic
    document words — junk must yield None, never a guess.
    """
    import re
    if not filename:
        return None
    stem = re.sub(r"\.[A-Za-z0-9]{1,5}$", "", filename)
    stem = stem.replace("_", " ").strip()
    stem = re.sub(r"\s+", " ", stem)
    if not stem:
        return None
    if re.search(r"[0-9A-Za-z]", stem):
        return None
    tokens = stem.split(" ")
    if not (2 <= len(tokens) <= 4):
        return None
    token_re = re.compile(r"^[\u05d0-\u05ea][\u05d0-\u05ea'\u05f3\u05f4-]*$")
    for t in tokens:
        if len(t) < 2 or not token_re.match(t):
            return None
        if t in _GENERIC_WORDS:
            return None
    return stem


IDENTITY_SYSTEM = """\
You extract ONE thing from the top of a handwritten exam page: the STUDENT'S \
OWN handwritten name.
Rules:
- The name is usually written beside a printed label such as "שם התלמיד". \
Return the student's name only — NEVER the teacher's name (מורה), the class \
(כיתה), the school, a date, or a page number.
- Return the name exactly as written (Hebrew stays Hebrew). Do not invent, \
complete, or transliterate.
- If no legible handwritten student name is visible: consider the PDF \
filename given by the user. Return it (without extension/underscores) ONLY \
if it plausibly is a person's name — not scanner junk, dates, or generic \
words. Otherwise return null.
Output JSON only: {"student_name": string|null, "source": "handwriting"|"filename"|null}
"""

IDENTITY_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "student_name": {"type": ["string", "null"]},
        "source": {"type": ["string", "null"]},
    },
    "required": ["student_name", "source"],
    "additionalProperties": False,
}


def crop_top(image: Image.Image, fraction: float = CROP_FRACTION) -> Image.Image:
    """Top strip of the page — pure."""
    w, h = image.size
    return image.crop((0, 0, w, max(1, int(h * fraction))))


def _header_b64(pdf_bytes: bytes) -> str:
    img = render_pdf_page(pdf_bytes, 1, RENDER_DPI)
    buf = io.BytesIO()
    crop_top(img).convert("RGB").save(buf, format="PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


async def extract_student_name(
    pdf_bytes: bytes,
    filename: str | None,
    provider: VLMProvider,
    *,
    scheduler=None,
    provider_key: str = "",
    doc_priority: int = 0,
) -> str | None:
    """Best-effort student-name hint from page-1 header ink, else filename.

    Never raises; None on any failure or when no plausible name exists.

    When a ProviderScheduler is given, the call rides it under `provider_key`
    at `doc_priority` — sharing the global per-model concurrency cap with the
    P1 chunks (an ungoverned identity call was observed being starved to
    timeout by its own batch's upload burst, 2026-08-12) and inheriting the
    scheduler's transport retry (one concept, one place)."""
    try:
        return await asyncio.wait_for(
            _extract(pdf_bytes, filename, provider,
                     scheduler=scheduler, provider_key=provider_key,
                     doc_priority=doc_priority),
            timeout=TOTAL_TIMEOUT_S,
        )
    except Exception as exc:
        # B-25's fallback clause, in CODE: the model was asked to judge the
        # filename, but a starved/timed-out call never got to judge anything.
        fallback = plausible_name_from_filename(filename)
        if fallback is not None:
            logger.warning(
                "identity pass failed for %s — using filename fallback %r",
                filename, fallback)
            return fallback
        logger.warning("identity pass failed for %s — no name suggestion",
                       filename, exc_info=True)
        try:
            from ..net_diag import diagnose_transport_failure
            await diagnose_transport_failure(f"identity pass for {filename}", exc)
        except Exception:
            pass
        return None


async def _extract(
    pdf_bytes: bytes,
    filename: str | None,
    provider: VLMProvider,
    *,
    scheduler=None,
    provider_key: str = "",
    doc_priority: int = 0,
) -> str | None:
    header_b64 = await run_in_threadpool(_header_b64, pdf_bytes)

    def make_call():
        return provider.complete(
            system=IDENTITY_SYSTEM,
            user=(f'PDF filename: "{filename or "(unknown)"}". '
                  "Extract the student name per the rules."),
            images_b64=[header_b64],
            max_tokens=2000,
            json_schema=IDENTITY_SCHEMA,
            timeout_s=CALL_TIMEOUT_S,
        )

    if scheduler is not None:
        res = (await scheduler.submit(provider_key, doc_priority, make_call)
               ).response
    else:
        res = await make_call()
    ok, data = parse_model_json(res.text, required_keys=("student_name",))
    if not ok:
        # The model answered garbage — it never JUDGED the filename either.
        return plausible_name_from_filename(filename)
    name = data.get("student_name")
    if not isinstance(name, str) or not name.strip():
        # The MODEL returned null after seeing the header AND the filename —
        # that is a judgment ("no name, filename implausible"), not a
        # failure. Respect it; no code override.
        return None
    logger.info("identity pass: %r (source=%s) for %s",
                name.strip(), data.get("source"), filename)
    return name.strip()
