"""
scan-service HTTP surface (§7). Private on Cloud Run (--no-allow-unauthenticated;
invoker = the backend's service account), so authentication is Cloud Run's job
and nothing here re-checks a token.

Endpoints are plain `def`: the work is CPU-bound, and FastAPI runs sync
handlers in its threadpool, so one slow compile never stalls the event loop.

Errors carry a machine `code`, never a filename or a name (OD-B4): the
backend maps them (analyze → `analyze_failed` + full frame, D9; compile →
a failed, retryable transcription job, SCN-11).
"""
from __future__ import annotations

import logging
import time
from typing import Annotated, List, Literal

import cv2
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from PIL import Image, UnidentifiedImageError
from pydantic import AfterValidator, BaseModel, Field

from . import SCAN_PIPELINE_VERSION
from .assemble import assemble_pdf
from .pipeline import (
    COMPILE_LONG_SIDE, COMPILE_QUALITY, PREVIEW_LONG_SIDE, PREVIEW_QUALITY, ImageTooLarge,
    InvalidParams, assess, decode_bounded, detect, encode_jpeg, render_page, resize_long_side,
)
from .storage import ObjectMissing, StorageFailed, StorageForbidden, get_storage, split_gs_uri

logger = logging.getLogger("scan")
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                    level=logging.INFO)

# Pillow refuses above 2x this (its bomb check) and only WARNS between 1x and
# 2x. The real memory bound is pipeline.decode_bounded (JPEG drafted, other
# formats refused above 64 MP); this is the outer wall: 2 x 125 MP = 250 MP,
# above Samsung's 200 MP JPEG mode, which decodes at a quarter size.
Image.MAX_IMAGE_PIXELS = 125_000_000
# One OpenCV thread per request: Cloud Run concurrency (4) already runs
# requests in parallel, and 2 vCPU shared by 4 requests × N OpenCV threads is
# contention, not speed.
cv2.setNumThreads(1)

app = FastAPI(title="scan-service", version=SCAN_PIPELINE_VERSION)

Point = Annotated[List[float], Field(min_length=2, max_length=2)]
Corners = Annotated[List[Point], Field(min_length=4, max_length=4)]
Rotation = Literal[0, 90, 180, 270]


def _gs(uri: str) -> str:
    split_gs_uri(uri)                 # raises ValueError → a 422 at the door
    return uri


GsUri = Annotated[str, AfterValidator(_gs)]
# The decode/render failures that are the PHOTO's (a corrupt or oversized
# file) — distinct from the request's (InvalidParams) and storage's.
_UNDECODABLE = (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError)
# (ImageTooLarge is a ValueError; InvalidParams is too, and is caught FIRST.)


class AnalyzeRequest(BaseModel):
    raw_uri: GsUri
    preview_uri_out: GsUri


class QualityOut(BaseModel):
    blur: float
    short_side_px: int
    glare_ratio: float
    verdict: str
    reasons: List[str]


class AnalyzeResponse(BaseModel):
    image_w: int
    image_h: int
    corners: Corners
    corners_source: str
    confidence: float
    quality: QualityOut
    preview_uri: str


class RenderRequest(BaseModel):
    raw_uri: GsUri
    corners: Corners
    rotation: Rotation = 0
    long_side: int = Field(1600, ge=200, le=4000)
    out_uri: GsUri
    enhance: bool = True


class RenderResponse(BaseModel):
    out_uri: str
    width: int
    height: int


class SnapshotPage(BaseModel):
    page_id: str
    raw_gcs_uri: GsUri
    content_type: str
    corners: Corners
    rotation: Rotation


class CompileRequest(BaseModel):
    pages_snapshot: List[SnapshotPage] = Field(min_length=1)
    scan_pipeline_version: str
    out_uri: GsUri


class CompileResponse(BaseModel):
    pdf_uri: str
    page_count: int
    bytes: int


def _error(status: int, code: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"code": code, **extra})


@app.exception_handler(StorageForbidden)
def _forbidden(_request, exc: StorageForbidden):
    # Permanent (IAM): a 4xx, so the backend never retries it as transient.
    logger.error("storage_forbidden op=%s", exc.op)
    return _error(403, "storage_forbidden")


@app.exception_handler(StorageFailed)
def _storage_failed(_request, exc: StorageFailed):
    logger.warning("storage_error op=%s error=%s", exc.op, exc.kind)
    return _error(502, "storage_error")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "scan_pipeline_version": SCAN_PIPELINE_VERSION}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest):
    started = time.monotonic()
    storage = get_storage()
    try:
        raw = storage.read(body.raw_uri)
    except ObjectMissing:
        return _error(404, "raw_missing")
    try:
        decoded = decode_bounded(raw)
    except _UNDECODABLE:
        return _error(422, "undecodable")
    del raw
    rgb, w, h = decoded.rgb, decoded.orig_w, decoded.orig_h
    preview = encode_jpeg(resize_long_side(rgb, PREVIEW_LONG_SIDE), PREVIEW_QUALITY)
    storage.write(body.preview_uri_out, preview, "image/jpeg")
    detection = detect(rgb)
    quality = assess(rgb, detection, scale=decoded.scale)
    logger.info("analyze w=%d h=%d corners_source=%s confidence=%.2f verdict=%s reasons=%s ms=%d",
                w, h, detection.source, detection.confidence, quality.verdict,
                ",".join(quality.reasons) or "-", int((time.monotonic() - started) * 1000))
    return AnalyzeResponse(image_w=w, image_h=h, corners=detection.corners,
                           corners_source=detection.source, confidence=detection.confidence,
                           quality=QualityOut(**quality.as_dict()), preview_uri=body.preview_uri_out)


@app.post("/render", response_model=RenderResponse)
def render(body: RenderRequest):
    storage = get_storage()
    try:
        raw = storage.read(body.raw_uri)
    except ObjectMissing:
        return _error(404, "raw_missing")
    try:
        page = render_page(raw, body.corners, body.rotation, body.long_side, enhance=body.enhance)
    except InvalidParams:
        return _error(422, "invalid_params")
    except _UNDECODABLE:
        return _error(422, "undecodable")
    storage.write(body.out_uri, encode_jpeg(page, COMPILE_QUALITY), "image/jpeg")
    return RenderResponse(out_uri=body.out_uri, width=page.shape[1], height=page.shape[0])


@app.post("/compile", response_model=CompileResponse)
def compile_version(body: CompileRequest):
    """Every page re-rendered from its RAW photo and the frozen parameters —
    never from a preview (SCN-11). A missing raw refuses the whole version:
    no partial PDF exists, ever."""
    if body.scan_pipeline_version != SCAN_PIPELINE_VERSION:
        return _error(409, "pipeline_version_mismatch", expected=SCAN_PIPELINE_VERSION,
                      got=body.scan_pipeline_version)
    started = time.monotonic()
    storage = get_storage()
    jpegs: list[bytes] = []
    for page in body.pages_snapshot:
        try:
            raw = storage.read(page.raw_gcs_uri)
        except ObjectMissing:
            return _error(422, "raw_missing", page_id=page.page_id)
        try:
            rendered = render_page(raw, page.corners, page.rotation, COMPILE_LONG_SIDE, enhance=True)
        except InvalidParams:
            return _error(422, "invalid_params", page_id=page.page_id)
        except _UNDECODABLE:
            return _error(422, "undecodable", page_id=page.page_id)
        jpegs.append(encode_jpeg(rendered, COMPILE_QUALITY))
    pdf = assemble_pdf(jpegs)
    storage.write(body.out_uri, pdf, "application/pdf")
    logger.info("compile pages=%d bytes=%d ms=%d", len(jpegs), len(pdf),
                int((time.monotonic() - started) * 1000))
    return CompileResponse(pdf_uri=body.out_uri, page_count=len(jpegs), bytes=len(pdf))
