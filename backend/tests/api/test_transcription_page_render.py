"""
Phase 1.5 — the page proxy renders ONLY the requested page.

`render_pdf_page` (single-page bounded render via pdf_render) replaces the
render-everything-then-index implementation in
GET /api/v0/transcriptions/{id}/pages/{n}. Ruled tests (plan Δ9):
  * correct page returned for first / middle / last of a multi-page fixture
  * 1-based bounds validation unchanged (0 and page_count+1 → 404)
  * render equivalence vs. the previous full-render-then-index implementation

EQUIVALENCE MODE — decided by spike, per the Δ9 ruling: poppler proved
deterministic across the two call shapes on the fixture (identical PNG bytes
through image_to_base64 for first/middle/last at 150 DPI), so these tests
assert BYTE-equality, not pixel-equality.
"""
import base64

import pytest
import sqlalchemy
import uuid
from unittest.mock import patch

from app.config import settings
from app.schemas.transcription import TranscriptionDraft, TranscriptionDraftAnswer
from app.services.document_parser import image_to_base64
from app.services.handwriting_transcription_service import pdf_to_images, render_pdf_page


# ---------------------------------------------------------------------------
# Fixture PDF: 3 visually distinct pages
# ---------------------------------------------------------------------------

def _three_page_pdf() -> bytes:
    import fitz
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=200, height=280)
        page.insert_text((50, 100), f"PAGE {i + 1}", fontsize=30)
    return doc.tobytes()


THREE_PAGE_PDF = _three_page_pdf()


# ---------------------------------------------------------------------------
# Unit — render_pdf_page vs the previous implementation
# ---------------------------------------------------------------------------

def test_single_page_render_matches_full_render_first_middle_last():
    """Byte-equal to full-render-then-index for pages 1, 2, 3 (spike-decided)."""
    full = pdf_to_images(THREE_PAGE_PDF, 150)
    assert len(full) == 3
    for page_number in (1, 2, 3):
        single = render_pdf_page(THREE_PAGE_PDF, page_number, 150)
        assert image_to_base64(single) == image_to_base64(full[page_number - 1]), (
            f"page {page_number}: single-page render differs from full render"
        )


def test_single_page_render_returns_the_right_page():
    """Pages are visually distinct — page 1 must NOT equal full-render page 2."""
    full = pdf_to_images(THREE_PAGE_PDF, 150)
    assert render_pdf_page(THREE_PAGE_PDF, 1, 150).tobytes() != full[1].tobytes()


def test_single_page_render_out_of_range_raises():
    with pytest.raises(ValueError):
        render_pdf_page(THREE_PAGE_PDF, 4, 150)


# ---------------------------------------------------------------------------
# API — the proxy endpoint, both 404 guards intact
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def transcription_3p(client, user_a, rubric_a):
    """
    A 'transcribed' row whose draft claims page_count=4 over a REAL 3-page PDF:
    pages 1-3 render; page 4 passes the draft-range check but the renderer
    raises (the guard the full-render path had via len(images)); page 5 fails
    the draft-range check. Both 404 paths are thus separately observable.
    """
    draft = TranscriptionDraft(
        page_count=4,
        answers=[TranscriptionDraftAnswer(
            question_number=1, sub_question_id=None,
            answer_text="x", confidence=0.9, page_numbers=[1],
        )],
        annotations=[],
    )
    tx_id = str(uuid.uuid4())
    engine = sqlalchemy.create_engine(
        settings.database_url.replace("+asyncpg", "+psycopg2")
    )
    import json
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text(
                "INSERT INTO transcriptions "
                "(id, user_id, rubric_id, gcs_uri, gcs_bucket, gcs_object_path, "
                " filename, draft_json, status, created_at, updated_at) "
                "VALUES (:id, :uid, :rid, 'gs://stub/p.pdf', 'stub', 'p.pdf', "
                " 'p.pdf', CAST(:dj AS JSONB), 'transcribed', now(), now())"
            ),
            {"id": tx_id, "uid": user_a["user"]["id"],
             "rid": rubric_a["rubric_id"],
             "dj": json.dumps(draft.model_dump(mode="json"))},
        )
        conn.commit()
    yield tx_id
    with engine.connect() as conn:
        conn.execute(
            sqlalchemy.text("DELETE FROM transcriptions WHERE id = :id"), {"id": tx_id}
        )
        conn.commit()
    engine.dispose()


def _patch_gcs():
    m = patch("app.api.v0.transcription.get_gcs_service")
    return m


def _get_page(client, headers, tx_id, page_number):
    with _patch_gcs() as mock_gcs:
        mock_gcs.return_value.download_bytes.return_value = THREE_PAGE_PDF
        return client.get(
            f"/api/v0/transcriptions/{tx_id}/pages/{page_number}",
            headers=headers,
        )


def test_page_proxy_first_middle_last(client, headers_a, transcription_3p):
    """Each page returns 200 with the byte-exact single-page render."""
    expected = [
        image_to_base64(img) for img in pdf_to_images(THREE_PAGE_PDF, 150)
    ]
    for page_number in (1, 2, 3):
        resp = _get_page(client, headers_a, transcription_3p, page_number)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["page_number"] == page_number
        decoded = base64.b64decode(body["thumbnail_base64"])
        assert decoded[:4] == b"\x89PNG"
        assert body["thumbnail_base64"] == expected[page_number - 1], (
            f"page {page_number}: proxy payload differs from full-render baseline"
        )


def test_page_proxy_bounds_unchanged(client, headers_a, transcription_3p):
    """1-based draft-range validation: 0 and page_count+1 → 404 (pre-GCS)."""
    for bad in (0, 5):
        resp = _get_page(client, headers_a, transcription_3p, bad)
        assert resp.status_code == 404, f"page {bad}: {resp.status_code}"


def test_page_proxy_renderer_range_guard(client, headers_a, transcription_3p):
    """draft page_count exceeds the real PDF: page 4 passes the draft check,
    the renderer raises ValueError, and the proxy still answers 404."""
    resp = _get_page(client, headers_a, transcription_3p, 4)
    assert resp.status_code == 404, resp.text


# ---------------------------------------------------------------------------
# PR-G8 — page1-thumb-rendered-once-then-served-from-cache
# ---------------------------------------------------------------------------

def test_page1_thumb_downloaded_once_then_served_from_cache(
        client, headers_a, transcription_3p):
    """§1.5 puts a page-1 thumbnail on every batch card. Before this cache, each
    request downloaded the ENTIRE PDF from GCS and re-rendered it — so one
    dashboard load of thirty tests was thirty full-PDF downloads, on a school
    connection, and it would have surfaced during the pilot.

    Pins the thing that matters: GCS download count == 1 across 30 loads.
    """
    from app.services import page_cache
    page_cache.clear()

    downloads = {"n": 0}

    def _counting_download(_path):
        downloads["n"] += 1
        return THREE_PAGE_PDF

    with _patch_gcs() as mock_gcs:
        mock_gcs.return_value.download_bytes.side_effect = _counting_download
        first = client.get(
            f"/api/v0/transcriptions/{transcription_3p}/pages/1", headers=headers_a)
        assert first.status_code == 200
        thumb = first.json()["thumbnail_base64"]

        for _ in range(29):
            resp = client.get(
                f"/api/v0/transcriptions/{transcription_3p}/pages/1", headers=headers_a)
            assert resp.status_code == 200
            assert resp.json()["thumbnail_base64"] == thumb

    assert downloads["n"] == 1, (
        f"expected ONE GCS download across 30 card loads, got {downloads['n']}")
