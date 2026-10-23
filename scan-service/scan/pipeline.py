"""
The page pipeline — PURE functions (PR_in_house_scanning.md §7.1, §7.4).

No I/O, no clock, no randomness: given (raw image bytes, corners, rotation,
SCAN_PIPELINE_VERSION) the output bytes are a function of the input. That is
what makes compiling a version twice yield the same PDF (SCN-4), and it is why
every step here is tested with zero mocks.

Coordinates: everything after `decode` is in the EXIF-ORIENTED image, and
corners travel normalized to [0, 1] in the order TL, TR, BR, BL.

Detection in scan-v1.0 is CONTOUR ONLY, then the full frame (SCN-5). The
DocAligner model the spec named was dropped from v1 by the spike's kill
criterion (2026-10-23): its ONNX graph has one output, the corner heatmaps,
and no document-presence score — so there was no confidence to gate a crop
on. `corners_source='auto_model'` stays in the vocabulary for a future,
eval-calibrated pipeline version.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Optional, Sequence

import cv2
import numpy as np
from PIL import Image, ImageOps
from pillow_heif import register_heif_opener

register_heif_opener()

# -- constants (every threshold here is to be CALIBRATED on real photos, §11) --
A4_ASPECT = math.sqrt(2.0)
A4_TOLERANCE = 0.12                 # D11
DETECT_LONG_SIDE = 1000             # contour detection runs on this downscale
MIN_QUAD_AREA_FRACTION = 0.20       # a "page" smaller than this is not trusted
CONTOUR_CONFIDENCE = 0.5            # §7.1 step 4
QUALITY_LONG_SIDE = 1200
T_BLUR = 60.0                       # Laplacian variance below this → blurry
MIN_SHORT_SIDE_PX = 1200            # the page's short side in ORIGINAL pixels
GLARE_V_MIN, GLARE_S_MAX = 250, 25
GLARE_BLOB_MIN_FRACTION = 0.002     # a glare blob counts above 0.2% of the page
GLARE_RATIO_MAX = 0.02
PREVIEW_LONG_SIDE = 1600
PREVIEW_QUALITY = 80
COMPILE_LONG_SIDE = 2339            # A4 long side at 200 DPI
COMPILE_DPI = 200
COMPILE_QUALITY = 85

FULL_FRAME = ((0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0))


# ---------------------------------------------------------------------------
# decode / encode
# ---------------------------------------------------------------------------

def decode(raw: bytes) -> np.ndarray:
    """Bytes (JPEG / PNG / HEIC / HEIF) → RGB uint8, EXIF orientation applied."""
    with Image.open(io.BytesIO(raw)) as im:
        im = ImageOps.exif_transpose(im)
        return np.asarray(im.convert("RGB"), dtype=np.uint8).copy()


def encode_jpeg(rgb: np.ndarray, quality: int) -> bytes:
    """Baseline JPEG, 4:2:0, no optimisation passes — byte-stable for a
    given array (img2pdf embeds these bytes as-is; no re-encode)."""
    out = io.BytesIO()
    Image.fromarray(rgb, "RGB").save(out, "JPEG", quality=quality, subsampling=2,
                                     optimize=False, progressive=False)
    return out.getvalue()


def resize_long_side(rgb: np.ndarray, long_side: int) -> np.ndarray:
    """Downscale only — a preview never upsamples."""
    h, w = rgb.shape[:2]
    scale = long_side / max(h, w)
    if scale >= 1.0:
        return rgb
    return cv2.resize(rgb, (max(1, round(w * scale)), max(1, round(h * scale))),
                      interpolation=cv2.INTER_AREA)


# ---------------------------------------------------------------------------
# corners
# ---------------------------------------------------------------------------

def order_corners(points: Sequence[Sequence[float]]) -> np.ndarray:
    """Four points in any order → TL, TR, BR, BL (the sum/diff method).
    TL has the smallest x+y, BR the largest; TR the smallest y−x, BL the largest."""
    pts = np.asarray(points, dtype=np.float64).reshape(4, 2)
    s = pts.sum(axis=1)
    d = pts[:, 1] - pts[:, 0]
    ordered = np.array([pts[np.argmin(s)], pts[np.argmin(d)],
                        pts[np.argmax(s)], pts[np.argmax(d)]])
    if len({tuple(p) for p in ordered.tolist()}) != 4:
        # Degenerate (e.g. a 45°-rotated square ties the sums): fall back to an
        # angular sort around the centroid, starting from the top-left-most.
        c = pts.mean(axis=0)
        angles = np.arctan2(pts[:, 1] - c[1], pts[:, 0] - c[0])
        ring = pts[np.argsort(angles)]           # clockwise in image coordinates
        start = int(np.argmin(ring.sum(axis=1)))
        ordered = np.roll(ring, -start, axis=0)
    return ordered


def normalize(points: np.ndarray, w: int, h: int) -> list[list[float]]:
    out = np.asarray(points, dtype=np.float64) / np.array([w, h], dtype=np.float64)
    return np.clip(out, 0.0, 1.0).round(6).tolist()


def denormalize(corners: Sequence[Sequence[float]], w: int, h: int) -> np.ndarray:
    return np.asarray(corners, dtype=np.float64).reshape(4, 2) * np.array([w, h], dtype=np.float64)


def polygon_area(points: np.ndarray) -> float:
    x, y = points[:, 0], points[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def is_convex(points: np.ndarray) -> bool:
    """Strictly convex and non-self-intersecting, in the given order."""
    signs = []
    for i in range(4):
        a, b, c = points[i], points[(i + 1) % 4], points[(i + 2) % 4]
        cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
        if abs(cross) < 1e-9:
            return False
        signs.append(cross > 0)
    return all(signs) or not any(signs)


def quad_size(points: np.ndarray) -> tuple[float, float]:
    """(width, height) of a TL,TR,BR,BL quad: the longer of each opposite pair."""
    tl, tr, br, bl = points
    width = max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl))
    height = max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr))
    return float(width), float(height)


# ---------------------------------------------------------------------------
# detection (§7.1 steps 4–6)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Detection:
    corners: list[list[float]]          # normalized, TL,TR,BR,BL
    source: str                         # 'auto_contour' | 'full_frame'
    confidence: float


def _auto_canny(gray: np.ndarray) -> np.ndarray:
    median = float(np.median(gray))
    lower = int(max(0, 0.66 * median))
    upper = int(min(255, 1.33 * median))
    return cv2.Canny(gray, lower, upper)


def detect_contour(rgb: np.ndarray) -> Optional[np.ndarray]:
    """The largest convex 4-gon covering ≥20% of the frame, in ORIGINAL pixel
    coordinates, ordered TL,TR,BR,BL — or None."""
    h, w = rgb.shape[:2]
    scale = min(1.0, DETECT_LONG_SIDE / max(h, w))
    small = cv2.resize(rgb, (max(1, round(w * scale)), max(1, round(h * scale))),
                       interpolation=cv2.INTER_AREA) if scale < 1.0 else rgb
    gray = cv2.cvtColor(small, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.dilate(_auto_canny(gray), np.ones((3, 3), np.uint8), iterations=1)
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    frame_area = float(small.shape[0] * small.shape[1])
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:10]:
        if cv2.contourArea(contour) < MIN_QUAD_AREA_FRACTION * frame_area:
            break                                   # sorted: nothing later is bigger
        approx = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if len(approx) != 4:
            continue
        quad = order_corners(approx.reshape(4, 2))
        if is_convex(quad) and polygon_area(quad) >= MIN_QUAD_AREA_FRACTION * frame_area:
            return quad / scale
    return None


def detect(rgb: np.ndarray) -> Detection:
    """Contour, else the full frame — never a crop on a guess (SCN-5)."""
    h, w = rgb.shape[:2]
    quad = detect_contour(rgb)
    if quad is not None:
        return Detection(normalize(quad, w, h), "auto_contour", CONTOUR_CONFIDENCE)
    return Detection([list(p) for p in FULL_FRAME], "full_frame", 0.0)


# ---------------------------------------------------------------------------
# flatten / rotate / illumination (§7.4)
# ---------------------------------------------------------------------------

def output_size(quad: np.ndarray, long_side: int) -> tuple[int, int]:
    """(width, height) of the flattened page. D11: within 12% of A4's aspect
    (either orientation) → exactly A4; otherwise the MEASURED aspect is kept,
    so a half sheet is never stretched into a whole one."""
    width, height = quad_size(quad)
    if width <= 0 or height <= 0:
        raise ValueError("degenerate quad")
    portrait = height >= width
    aspect = (height / width) if portrait else (width / height)
    if abs(aspect / A4_ASPECT - 1.0) <= A4_TOLERANCE:
        aspect = A4_ASPECT
    short = max(1, round(long_side / aspect))
    return (short, long_side) if portrait else (long_side, short)


def flatten(rgb: np.ndarray, corners: Sequence[Sequence[float]], long_side: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    quad = denormalize(corners, w, h).astype(np.float32)
    out_w, out_h = output_size(quad.astype(np.float64), long_side)
    target = np.array([[0, 0], [out_w - 1, 0], [out_w - 1, out_h - 1], [0, out_h - 1]],
                      dtype=np.float32)
    matrix = cv2.getPerspectiveTransform(quad, target)
    return cv2.warpPerspective(rgb, matrix, (out_w, out_h), flags=cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE)


def rotate(rgb: np.ndarray, rotation: int) -> np.ndarray:
    """Exact quarter turns CLOCKWISE (np.rot90 turns counter-clockwise, hence
    the negative k) — no interpolation."""
    if rotation not in (0, 90, 180, 270):
        raise ValueError(f"rotation must be a quarter turn, got {rotation}")
    return np.ascontiguousarray(np.rot90(rgb, k=-(rotation // 90)))


def normalize_illumination(rgb: np.ndarray) -> np.ndarray:
    """Even out shadows and lighting on the L channel only; a/b are kept, so
    red/blue ink and highlighted graphs keep their colour. NO binarization and
    NO sharpening in scan-v1.0 — a faint pencil stroke must survive. Any change
    here bumps SCAN_PIPELINE_VERSION."""
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB)
    lum, a, b = cv2.split(lab)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
    background = cv2.medianBlur(cv2.morphologyEx(lum, cv2.MORPH_CLOSE, kernel), 31)
    flat = np.clip(lum.astype(np.float32) / np.maximum(background.astype(np.float32), 1.0) * 235.0,
                   0.0, 255.0)
    # WHITE point only: the 99.5th percentile (the paper) → 255; black stays 0.
    # The spec's stretch also pinned the 1st percentile → 0, and that is wrong
    # on a SPARSE page: when ink covers under 1% of the pixels (one short
    # answer on a sheet), the 1st percentile IS paper, everything darker than
    # paper clips to black — a faint pencil stroke came out 0, i.e. binarized —
    # and paper noise was amplified (the shadow test reached 61%, not 80%).
    # Measured on the synthetic page in tests/test_pipeline.py, 2026-10-23.
    hi = float(np.percentile(flat, 99.5))
    if hi >= 1.0:
        flat = np.clip(flat * (255.0 / hi), 0.0, 255.0)
    lum2 = np.round(flat).astype(np.uint8)
    return cv2.cvtColor(cv2.merge((lum2, a, b)), cv2.COLOR_LAB2RGB)


def render_page(raw: bytes, corners, rotation: int, long_side: int, *, enhance: bool) -> np.ndarray:
    """§7.4 end to end: decode → flatten → rotate → (illumination)."""
    page = rotate(flatten(decode(raw), corners, long_side), rotation)
    return normalize_illumination(page) if enhance else page


# ---------------------------------------------------------------------------
# quality (§7.1 step 7) — warns, never blocks (D10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Quality:
    blur: float
    short_side_px: int
    glare_ratio: float
    verdict: str                        # 'ok' | 'warn'
    reasons: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {"blur": round(self.blur, 2), "short_side_px": self.short_side_px,
                "glare_ratio": round(self.glare_ratio, 5), "verdict": self.verdict,
                "reasons": list(self.reasons)}


def laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def glare_ratio(rgb: np.ndarray) -> float:
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    mask = ((hsv[:, :, 2] > GLARE_V_MIN) & (hsv[:, :, 1] < GLARE_S_MAX)).astype(np.uint8)
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    page = float(mask.size)
    big = sum(int(stats[i, cv2.CC_STAT_AREA]) for i in range(1, n)
              if stats[i, cv2.CC_STAT_AREA] > GLARE_BLOB_MIN_FRACTION * page)
    return big / page


def assess(rgb: np.ndarray, detection: Detection) -> Quality:
    h, w = rgb.shape[:2]
    quad = denormalize(detection.corners, w, h)
    flat = flatten(rgb, detection.corners, QUALITY_LONG_SIDE)
    blur = laplacian_variance(cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY))
    short_side = int(round(min(quad_size(quad))))
    glare = glare_ratio(flat)
    reasons = []
    if blur < T_BLUR:
        reasons.append("blurry")
    if short_side < MIN_SHORT_SIDE_PX:
        reasons.append("too_far")
    if glare > GLARE_RATIO_MAX:
        reasons.append("glare")
    if detection.source == "full_frame":
        reasons.append("edges_not_found")
    return Quality(blur, short_side, glare, "warn" if reasons else "ok", reasons)
