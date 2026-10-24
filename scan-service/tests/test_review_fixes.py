"""
The 2026-10-24 review's fixes, each pinned: the bounded decode (memory), the
orientation parity it re-implements, the border-hugging false detection, the
full frame's own aspect, and the typed errors the backend branches on.
"""
import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageOps

from scan import pipeline as P
from scan.api import app
from scan.storage import StorageForbidden, set_storage
from tests.synth import on_desk, text_page, to_jpeg
from tests.test_api import DESK, FakeStorage, _snapshot


def _gradient(w, h):
    y, x = np.mgrid[0:h, 0:w]
    return np.dstack([(x * 255 // max(1, w - 1)), (y * 255 // max(1, h - 1)),
                      ((x + y) % 256)]).astype(np.uint8)


@pytest.mark.parametrize("orientation", range(1, 9))
def test_bounded_decode_orients_exactly_as_pillow_does(orientation):
    rgb = _gradient(60, 40)
    exif = Image.Exif()
    exif[0x0112] = orientation
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, "PNG", exif=exif.tobytes())
    raw = buf.getvalue()
    with Image.open(io.BytesIO(raw)) as im:
        expected = np.asarray(ImageOps.exif_transpose(im).convert("RGB"))
    got = P.decode_bounded(raw)
    assert np.array_equal(got.rgb, expected)
    assert (got.orig_w, got.orig_h) == (expected.shape[1], expected.shape[0])


def test_a_large_jpeg_is_drafted_to_the_working_cap_and_keeps_its_original_size():
    big = np.full((6000, 8000, 3), 240, np.uint8)          # 48 MP
    big[2000:4000, 3000:5000] = 20
    d = P.decode_bounded(to_jpeg(big, 80))
    assert max(d.rgb.shape[:2]) <= P.MAX_DECODE_LONG_SIDE
    assert (d.orig_w, d.orig_h) == (8000, 6000)
    assert d.scale == pytest.approx(d.rgb.shape[1] / 8000)


def test_a_huge_non_jpeg_is_refused_not_decoded(monkeypatch):
    monkeypatch.setattr(P, "MAX_FULL_DECODE_PIXELS", 100)
    buf = io.BytesIO()
    Image.fromarray(_gradient(20, 20)).save(buf, "PNG")
    with pytest.raises(P.ImageTooLarge):
        P.decode_bounded(buf.getvalue())


def test_too_far_is_judged_in_the_photos_own_pixels():
    page = on_desk(text_page(), DESK)
    det = P.detect(page)
    native = P.assess(page, det).short_side_px
    assert P.assess(page, det, scale=0.5).short_side_px == pytest.approx(2 * native, abs=2)


def test_a_quad_tracing_the_frame_border_is_not_a_page():
    w, h = 1000, 750
    quad = np.array([[0, 1], [w - 1, 2], [w - 1, h - 1], [0, h - 2]], np.float64)
    assert P._hugs_border(quad, w, h)
    assert not P._hugs_border(np.array([[50, 40], [950, 40], [950, 700], [50, 700]], float), w, h)


def test_the_full_frame_keeps_the_photos_aspect_and_a_placed_page_snaps_to_a4():
    rgb = np.full((900, 1200, 3), 200, np.uint8)            # 4:3, 5.7% off A4
    full = P.flatten(rgb, [list(p) for p in P.FULL_FRAME], 1200)
    assert full.shape[:2] == (900, 1200)
    inset = P.flatten(rgb, [[0.01, 0.01], [0.99, 0.01], [0.99, 0.99], [0.01, 0.99]], 1200)
    assert inset.shape[1] / inset.shape[0] == pytest.approx(2 ** 0.5, rel=0.01)


def test_non_finite_or_degenerate_corners_are_invalid_params_not_a_bad_photo():
    rgb = np.zeros((100, 100, 3), np.uint8)
    with pytest.raises(P.InvalidParams):
        P.flatten(rgb, [[float("nan"), 0], [1, 0], [1, 1], [0, 1]], 200)
    with pytest.raises(P.InvalidParams):
        P.flatten(rgb, [[0.5, 0.5]] * 4, 200)


@pytest.fixture
def store():
    s = FakeStorage()
    set_storage(s)
    yield s
    set_storage(None)


def test_compile_names_bad_parameters_invalid_params(store):
    uri = "gs://b/captures/s/raw-1"
    store.write(uri, to_jpeg(on_desk(text_page(), DESK)), "image/jpeg")
    r = TestClient(app).post("/compile", json={
        "pages_snapshot": [_snapshot(uri, corners=[[0.5, 0.5]] * 4)],
        "scan_pipeline_version": app.version, "out_uri": "gs://b/captures/s/v.pdf"})
    assert r.status_code == 422 and r.json() == {"code": "invalid_params", "page_id": "p1"}


def test_a_rotation_that_is_not_a_quarter_turn_is_refused_at_the_door(store):
    r = TestClient(app).post("/compile", json={
        "pages_snapshot": [_snapshot("gs://b/captures/s/raw-1", rotation=45)],
        "scan_pipeline_version": app.version, "out_uri": "gs://b/captures/s/v.pdf"})
    assert r.status_code == 422


def test_a_storage_permission_error_is_a_permanent_403_not_a_retried_500(store):
    class Forbidden(FakeStorage):
        def read(self, uri):
            raise StorageForbidden("read")
    set_storage(Forbidden())
    r = TestClient(app).post("/analyze", json={"raw_uri": "gs://b/captures/s/raw-1",
                                               "preview_uri_out": "gs://b/captures/s/p.jpg"})
    assert r.status_code == 403 and r.json()["code"] == "storage_forbidden"
