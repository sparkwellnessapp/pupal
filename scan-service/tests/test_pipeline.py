"""
The page pipeline, zero mocks (PR_in_house_scanning.md §10 "Pure").
"""
import io
import math

import cv2
import numpy as np
import pytest
from PIL import Image

from scan import pipeline as P
from tests.synth import A4_H, A4_W, on_desk, ssim, text_page, to_jpeg

# A page photographed from roughly overhead: tilted, mild perspective, on a
# 1600×1200 desk. Its measured quad is 1.33:1 — within D11's 12% of A4, as an
# overhead shot of an A4 sheet is. (A steep shot measures further from √2 and
# keeps its measured aspect — that is D11 working, see the A4 tests.)
DESK_CORNERS = [(450, 60), (1140, 90), (1170, 1080), (420, 1060)]


# ---------------------------------------------------------------------------
# corners
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("perm", [(0, 1, 2, 3), (2, 0, 3, 1), (3, 2, 1, 0), (1, 3, 0, 2)])
def test_order_corners_returns_tl_tr_br_bl_from_any_order(perm):
    quad = np.array(DESK_CORNERS, float)
    shuffled = quad[list(perm)]
    assert P.order_corners(shuffled).tolist() == quad.tolist()


def test_order_corners_handles_a_45_degree_square():
    """A diamond ties the sums: the angular fallback still yields 4 distinct
    corners, clockwise from the top-left-most."""
    diamond = [(50, 0), (100, 50), (50, 100), (0, 50)]
    ordered = P.order_corners(diamond[::-1])
    assert len({tuple(p) for p in ordered.tolist()}) == 4
    assert P.is_convex(ordered)


def test_convexity_rejects_a_bow_tie_and_accepts_a_quad():
    assert P.is_convex(np.array(DESK_CORNERS, float))
    bow_tie = np.array([DESK_CORNERS[0], DESK_CORNERS[2], DESK_CORNERS[1], DESK_CORNERS[3]], float)
    assert not P.is_convex(bow_tie)


# ---------------------------------------------------------------------------
# D11 — the A4 decision at the 12% boundary
# ---------------------------------------------------------------------------

def _rect(w, h):
    return np.array([[0, 0], [w, 0], [w, h], [0, h]], float)


@pytest.mark.parametrize("factor,forced", [
    (1.00, True), (1.119, True), (0.881, True),      # within 12% → exactly A4
    (1.121, False), (0.879, False),                  # outside → measured aspect kept
])
def test_a4_is_forced_only_within_twelve_percent(factor, forced):
    h = 1000 * math.sqrt(2) * factor
    w, out_h = P.output_size(_rect(1000, h), 2339)
    assert out_h == 2339
    expected = round(2339 / math.sqrt(2)) if forced else round(2339 / (h / 1000))
    assert w == expected


def test_a4_decision_holds_in_landscape_too():
    w, h = P.output_size(_rect(1000 * math.sqrt(2) * 1.05, 1000), 2339)
    assert (w, h) == (2339, round(2339 / math.sqrt(2)))


def test_a_non_a4_sheet_keeps_its_measured_aspect():
    """A strip torn off a page (2:1) and a square are never stretched to A4."""
    assert P.output_size(_rect(1000, 500), 2000) == (2000, 1000)
    assert P.output_size(_rect(1000, 1000), 2000) == (2000, 2000)


# ---------------------------------------------------------------------------
# flatten / rotate
# ---------------------------------------------------------------------------

def test_flatten_recovers_a_known_homography_ssim_at_least_0_9():
    page = text_page()
    photo = on_desk(page, DESK_CORNERS)
    h, w = photo.shape[:2]
    corners = (np.array(DESK_CORNERS, float) / [w, h]).tolist()
    flat = P.flatten(photo, corners, A4_H)
    assert flat.shape[:2] == (A4_H, round(A4_H / math.sqrt(2)))
    flat = cv2.resize(flat, (A4_W, A4_H), interpolation=cv2.INTER_AREA)
    score = ssim(cv2.cvtColor(flat, cv2.COLOR_RGB2GRAY), cv2.cvtColor(page, cv2.COLOR_RGB2GRAY))
    assert score >= 0.9, score


@pytest.mark.parametrize("rotation,k", [(0, 0), (90, -1), (180, -2), (270, -3)])
def test_rotation_is_an_exact_quarter_turn_clockwise(rotation, k):
    img = np.arange(2 * 3 * 3, dtype=np.uint8).reshape(2, 3, 3)
    out = P.rotate(img, rotation)
    assert np.array_equal(out, np.rot90(img, k=k))
    if rotation == 90:                                   # top-left goes to top-right
        assert np.array_equal(out[0, -1], img[0, 0])


def test_four_quarter_turns_are_the_identity():
    img = text_page(120, 170)
    out = img
    for _ in range(4):
        out = P.rotate(out, 90)
    assert np.array_equal(out, img)


def test_rotation_refuses_anything_but_a_quarter_turn():
    with pytest.raises(ValueError):
        P.rotate(text_page(10, 10), 45)


# ---------------------------------------------------------------------------
# illumination (scan-v1.0: no binarization)
# ---------------------------------------------------------------------------

def _shadowed_page():
    w, h = 800, 1100
    page = np.full((h, w, 3), 240, np.uint8)
    # A faint gray "pencil" stroke and a dark ink line.
    cv2.line(page, (100, 300), (700, 300), (205, 205, 205), 2)
    cv2.line(page, (100, 700), (700, 700), (30, 30, 30), 3)
    gradient = np.linspace(0.45, 1.0, w)[None, :, None]        # a shadow across the page
    return np.clip(page.astype(np.float64) * gradient, 0, 255).astype(np.uint8)


def _background_rows(img):
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY).astype(np.float64)
    return np.concatenate([gray[100:250], gray[350:650], gray[750:1000]])


def test_illumination_flattens_a_gradient_shadow_by_at_least_80_percent():
    shadowed = _shadowed_page()
    out = P.normalize_illumination(shadowed)
    before = _background_rows(shadowed).var()
    after = _background_rows(out).var()
    assert after <= 0.2 * before, (before, after)


def test_a_faint_pencil_stroke_survives_illumination():
    out = cv2.cvtColor(P.normalize_illumination(_shadowed_page()), cv2.COLOR_RGB2GRAY).astype(int)
    stroke = out[299:302, 150:650].mean()
    paper = out[260:280, 150:650].mean()
    assert paper - stroke >= 8, (paper, stroke)       # still visibly darker than the paper
    assert 0 < stroke < 255                           # gray, not thresholded to black/white


def test_illumination_keeps_ink_colour():
    """A red pen stroke stays red. (A SOLID area wider than the 15 px closing
    kernel — a highlighter block — is absorbed into the background estimate
    and lightened; its hue survives, its depth does not. Known scan-v1.0
    limit, for the §11 eval to judge on real pages.)"""
    page = np.full((400, 400, 3), 235, np.uint8)
    cv2.line(page, (60, 200), (340, 200), (200, 30, 30), 4)           # red ink
    out = P.normalize_illumination(page)
    r, g, b = out[200, 200].astype(int)
    assert r > g + 60 and r > b + 60, (r, g, b)


# ---------------------------------------------------------------------------
# quality — warns, never blocks
# ---------------------------------------------------------------------------

def test_a_blurred_copy_scores_below_threshold_and_the_sharp_copy_above():
    sharp = cv2.cvtColor(cv2.resize(text_page(), (849, 1200)), cv2.COLOR_RGB2GRAY)
    blurred = cv2.GaussianBlur(sharp, (0, 0), 6)
    assert P.laplacian_variance(sharp) > P.T_BLUR
    assert P.laplacian_variance(blurred) < P.T_BLUR


def test_quality_reasons_for_a_far_full_frame_shot():
    small = cv2.resize(text_page(), (600, 850))
    q = P.assess(small, P.Detection([list(c) for c in P.FULL_FRAME], "full_frame", 0.0))
    assert q.verdict == "warn"
    assert {"too_far", "edges_not_found"} <= set(q.reasons)


def test_glare_counts_only_large_bright_blobs():
    page = np.full((1000, 800, 3), 200, np.uint8)
    cv2.circle(page, (400, 500), 120, (255, 255, 255), -1)            # one big glare patch
    assert P.glare_ratio(page) > P.GLARE_RATIO_MAX
    speckle = np.full((1000, 800, 3), 200, np.uint8)
    speckle[::50, ::50] = 255                                          # tiny bright dots only
    assert P.glare_ratio(speckle) == 0.0


# ---------------------------------------------------------------------------
# detection — contour, else the full frame (SCN-5)
# ---------------------------------------------------------------------------

def test_contour_detection_finds_the_page_on_a_desk():
    photo = on_desk(text_page(), DESK_CORNERS)
    d = P.detect(photo)
    assert d.source == "auto_contour"
    h, w = photo.shape[:2]
    found = np.array(d.corners) * [w, h]
    assert np.abs(found - np.array(DESK_CORNERS)).max() < 25, found


def test_no_page_edges_means_the_full_frame_never_a_guess():
    rng = np.random.default_rng(3)
    noise = np.clip(rng.normal(128, 30, (900, 1200, 3)), 0, 255).astype(np.uint8)
    d = P.detect(cv2.GaussianBlur(noise, (21, 21), 0))
    assert d.source == "full_frame"
    assert d.corners == [list(c) for c in P.FULL_FRAME]


# ---------------------------------------------------------------------------
# decode — EXIF orientation is applied
# ---------------------------------------------------------------------------

def test_decode_applies_exif_orientation():
    img = Image.fromarray(np.zeros((100, 200, 3), np.uint8))          # landscape pixels
    exif = Image.Exif()
    exif[0x0112] = 6                                                  # rotate 90 CW to display
    buf = io.BytesIO()
    img.save(buf, "JPEG", exif=exif.tobytes())
    assert P.decode(buf.getvalue()).shape[:2] == (200, 100)


def test_render_is_deterministic():
    raw = to_jpeg(on_desk(text_page(), DESK_CORNERS))
    corners = (np.array(DESK_CORNERS, float) / [1600, 1200]).tolist()
    a = P.encode_jpeg(P.render_page(raw, corners, 90, 1200, enhance=True), 85)
    b = P.encode_jpeg(P.render_page(raw, corners, 90, 1200, enhance=True), 85)
    assert a == b
