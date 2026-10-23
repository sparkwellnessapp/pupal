"""
scan-service API (PR_in_house_scanning.md §10 "scan-service API"), with an
in-memory storage fake — no GCP.
"""
import re

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from scan import SCAN_PIPELINE_VERSION
from scan.api import app
from scan.storage import ObjectMissing, set_storage
from tests.synth import on_desk, text_page, to_jpeg

DESK = [(450, 60), (1140, 90), (1170, 1080), (420, 1060)]


class FakeStorage:
    def __init__(self):
        self.objects: dict[str, tuple[bytes, str]] = {}

    def read(self, uri):
        if uri not in self.objects:
            raise ObjectMissing(uri)
        return self.objects[uri][0]

    def write(self, uri, data, content_type):
        self.objects[uri] = (data, content_type)


@pytest.fixture
def store():
    s = FakeStorage()
    set_storage(s)
    yield s
    set_storage(None)


@pytest.fixture
def client(store):
    return TestClient(app)


def _page_on_desk(store, uri="gs://b/captures/s/raw-1"):
    store.write(uri, to_jpeg(on_desk(text_page(), DESK)), "image/jpeg")
    return uri


def _snapshot(uri, corners=None, rotation=0, page_id="p1"):
    return {"page_id": page_id, "raw_gcs_uri": uri, "content_type": "image/jpeg",
            "corners": corners or [[0, 0], [1, 0], [1, 1], [0, 1]], "rotation": rotation}


def test_analyze_finds_the_page_writes_a_preview_and_reports_quality(client, store):
    raw = _page_on_desk(store)
    r = client.post("/analyze", json={"raw_uri": raw, "preview_uri_out": "gs://b/captures/s/preview-1.jpg"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["image_w"], body["image_h"]) == (1600, 1200)
    assert body["corners_source"] == "auto_contour"
    assert store.objects["gs://b/captures/s/preview-1.jpg"][1] == "image/jpeg"
    assert body["quality"]["verdict"] in ("ok", "warn")


def test_analyze_with_no_detectable_page_returns_the_full_frame_scn5(client, store):
    rng = np.random.default_rng(5)
    noise = cv2.GaussianBlur(np.clip(rng.normal(128, 30, (900, 1200, 3)), 0, 255).astype(np.uint8),
                             (21, 21), 0)
    store.write("gs://b/raw", to_jpeg(noise), "image/jpeg")
    body = client.post("/analyze", json={"raw_uri": "gs://b/raw", "preview_uri_out": "gs://b/p.jpg"}).json()
    assert body["corners_source"] == "full_frame"
    assert body["corners"] == [[0, 0], [1, 0], [1, 1], [0, 1]]
    assert "edges_not_found" in body["quality"]["reasons"]


def test_analyze_missing_raw_is_404_and_undecodable_is_422(client, store):
    assert client.post("/analyze", json={"raw_uri": "gs://b/none", "preview_uri_out": "gs://b/p"}).status_code == 404
    store.write("gs://b/junk", b"not an image", "image/jpeg")
    r = client.post("/analyze", json={"raw_uri": "gs://b/junk", "preview_uri_out": "gs://b/p"})
    assert (r.status_code, r.json()["code"]) == (422, "undecodable")


def test_compile_refuses_a_missing_raw_with_422_and_writes_nothing_scn11(client, store):
    raw = _page_on_desk(store)
    r = client.post("/compile", json={
        "pages_snapshot": [_snapshot(raw), _snapshot("gs://b/captures/s/raw-gone", page_id="p2")],
        "scan_pipeline_version": SCAN_PIPELINE_VERSION, "out_uri": "gs://b/captures/s/v.pdf"})
    assert r.status_code == 422
    assert r.json() == {"code": "raw_missing", "page_id": "p2"}
    assert "gs://b/captures/s/v.pdf" not in store.objects               # never a partial PDF


def test_compile_twice_to_the_same_uri_writes_the_same_bytes_scn4(client, store):
    raw = _page_on_desk(store)
    corners = (np.array(DESK, float) / [1600, 1200]).tolist()
    req = {"pages_snapshot": [_snapshot(raw, corners, 90), _snapshot(raw, page_id="p2")],
           "scan_pipeline_version": SCAN_PIPELINE_VERSION, "out_uri": "gs://b/captures/s/v.pdf"}
    first = client.post("/compile", json=req)
    a = store.objects["gs://b/captures/s/v.pdf"][0]
    second = client.post("/compile", json=req)
    b = store.objects["gs://b/captures/s/v.pdf"][0]
    assert first.status_code == second.status_code == 200
    assert first.json()["page_count"] == 2
    assert a == b


def test_compile_produces_a4_pages_with_no_name_in_the_metadata(client, store):
    raw = _page_on_desk(store)
    corners = (np.array(DESK, float) / [1600, 1200]).tolist()
    client.post("/compile", json={
        "pages_snapshot": [_snapshot(raw, corners)], "scan_pipeline_version": SCAN_PIPELINE_VERSION,
        "out_uri": "gs://b/v.pdf"})
    pdf = store.objects["gs://b/v.pdf"][0]
    (box,) = re.findall(rb"/MediaBox\s*\[\s*([\d.\s]+)\]", pdf)
    w, h = [float(x) for x in box.split()][2:]
    assert abs(w - 595.3) < 1.0 and abs(h - 841.9) < 1.0                # A4 in points
    assert b"/Title (exam)" in pdf and b"/Producer (Vivi)" in pdf
    assert b"/CreationDate" not in pdf                                    # nodate → deterministic
    # No trailer /ID: pikepdf's is clock-derived, so it differs across seconds
    # (two compiles inside one second agree, which is how it hid).
    assert b"/ID" not in pdf


def test_compile_refuses_a_pipeline_version_it_did_not_produce_409(client, store):
    raw = _page_on_desk(store)
    r = client.post("/compile", json={"pages_snapshot": [_snapshot(raw)],
                                      "scan_pipeline_version": "scan-v0.9", "out_uri": "gs://b/v.pdf"})
    assert r.status_code == 409
    assert r.json()["code"] == "pipeline_version_mismatch"


def test_render_writes_an_enhanced_jpeg(client, store):
    raw = _page_on_desk(store)
    r = client.post("/render", json={"raw_uri": raw, "corners": [[0, 0], [1, 0], [1, 1], [0, 1]],
                                     "rotation": 0, "long_side": 1600, "out_uri": "gs://b/n.jpg"})
    assert r.status_code == 200
    assert max(r.json()["width"], r.json()["height"]) == 1600
    assert store.objects["gs://b/n.jpg"][0][:2] == b"\xff\xd8"


def test_healthz_names_the_pipeline_version(client):
    assert client.get("/healthz").json()["scan_pipeline_version"] == SCAN_PIPELINE_VERSION
