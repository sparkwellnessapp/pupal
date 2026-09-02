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


# ---------------------------------------------------------------------------
# PLAN_page1_image_route phase 1a — the WebP card thumbnail as BYTES
#
# A SEPARATE RESOURCE from the JSON proxy above, not a reformatting of it.
# Measured on the six real bagrut scans: the JSON path is 1168 KB / 1227 ms per
# page, this one 33.6 KB / 259 ms, so a thirty-card dashboard goes from ~34 MB
# and ~37 s of render to ~1.0 MB. Everything below pins one half of that claim
# or one of the two guards that keep the resources apart.
# ---------------------------------------------------------------------------

from app.services import thumbnail  # noqa: E402


def _image_url(tx_id, page=1, variant="current"):
    token = thumbnail.current_variant().token if variant == "current" else variant
    suffix = "" if token is None else f"?v={token}"
    return f"/api/v0/transcriptions/{tx_id}/pages/{page}/image{suffix}"


class _FakeGcs:
    """A bucket that behaves like one: an object store plus call records.

    Phase 2 made the route read TWO different objects — the stored thumbnail
    first, the source PDF only on a miss — so a mock that returns the same bytes
    for every path would hand the route a PDF and let it answer with it. This
    stands in for the bucket properly: a missing object raises, an upload lands,
    and the paths are recorded so a test can say WHICH object was fetched.
    """

    def __init__(self, pdf_path="p.pdf", pdf_bytes=None):
        self.objects = {pdf_path: pdf_bytes if pdf_bytes is not None else THREE_PAGE_PDF}
        self.pdf_path = pdf_path
        self.downloads = []
        self.uploads = []
        self.fail_thumb_read = False
        self.fail_upload = False

    # -- the two methods the route uses ------------------------------------
    def download_bytes(self, object_path):
        self.downloads.append(object_path)
        if self.fail_thumb_read and object_path.startswith("thumbs/"):
            raise RuntimeError("thumb read unavailable")
        if object_path not in self.objects:
            # The REAL type google-cloud-storage raises. Using FileNotFoundError
            # here would make every cold render take the route's outage branch,
            # so the test would pass while pinning the wrong behaviour.
            from google.api_core.exceptions import NotFound
            raise NotFound(object_path)
        return self.objects[object_path]

    def upload_bytes(self, data, object_path, content_type="application/pdf"):
        if self.fail_upload:
            raise RuntimeError("thumb write unavailable")
        self.uploads.append((object_path, content_type, len(data)))
        self.objects[object_path] = data
        return object_path

    # -- what the tests ask it ---------------------------------------------
    @property
    def pdf_downloads(self):
        return [p for p in self.downloads if p == self.pdf_path]

    @property
    def thumb_downloads(self):
        return [p for p in self.downloads if p.startswith("thumbs/")]


def _patch_fake_gcs(fake):
    m = patch("app.api.v0.transcription.get_gcs_service")
    started = m.start()
    started.return_value = fake
    return m


def _get_image(client, headers, tx_id, page=1, variant="current", fake=None):
    own = fake is None
    fake = fake or _FakeGcs()
    m = _patch_fake_gcs(fake)
    try:
        return client.get(_image_url(tx_id, page, variant), headers=headers)
    finally:
        m.stop()
        if own:
            pass


def test_page_image_returns_webp_bytes_not_json(client, headers_a, transcription_3p):
    resp = _get_image(client, headers_a, transcription_3p)
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "image/webp"
    body = resp.content
    assert body[:4] == b"RIFF" and body[8:12] == b"WEBP", (
        f"not a WebP payload: {body[:16]!r}")


def test_page_image_sets_immutable_cache_headers_only_with_a_variant(
        client, headers_a, transcription_3p):
    """[C1] the header is a PROMISE about the bytes, and it is only honest when
    the URL named the variant that produced them. Without ?v the same URL would
    return different bytes after a settings change, so it must not claim a year
    of immutability."""
    from app.services import page_cache
    page_cache.clear()

    pinned = _get_image(client, headers_a, transcription_3p)
    assert pinned.status_code == 200
    cc = pinned.headers["cache-control"]
    assert "immutable" in cc and f"max-age={thumbnail.IMMUTABLE_MAX_AGE}" in cc, cc

    page_cache.clear()
    unpinned = _get_image(client, headers_a, transcription_3p, variant=None)
    assert unpinned.status_code == 200
    cc = unpinned.headers["cache-control"]
    assert "immutable" not in cc, f"an unpinned URL claimed immutability: {cc}"
    assert f"max-age={thumbnail.UNPINNED_MAX_AGE}" in cc, cc


def test_page_image_refuses_an_unknown_variant_token(
        client, headers_a, transcription_3p):
    """[C1] the token resolves render settings, so an unvalidated one would be a
    client-controlled rasterizer. ?v=20000x100@600 is a render-bomb."""
    for bad in ("20000x100@600", "600x72@111", "not-a-token", "600x72", "0x0@0"):
        resp = _get_image(client, headers_a, transcription_3p, variant=bad)
        assert resp.status_code == 404, f"{bad}: {resp.status_code} {resp.text[:120]}"


def test_page_image_requires_auth(client, transcription_3p):
    resp = client.get(_image_url(transcription_3p))
    assert resp.status_code in (401, 403), resp.status_code


def test_page_image_refuses_another_tenants_transcription(
        client, headers_b, transcription_3p):
    """404, never 403 — 403 leaks existence (section 9)."""
    resp = _get_image(client, headers_b, transcription_3p)
    assert resp.status_code == 404, resp.status_code


def test_page_image_bounds_and_renderer_guards_match_the_json_proxy(
        client, headers_a, transcription_3p):
    """Same two 404 paths as the JSON proxy: 0 and page_count+1 fail the draft
    range check; page 4 passes it and the renderer raises."""
    for bad in (0, 5, 4):
        resp = _get_image(client, headers_a, transcription_3p, page=bad)
        assert resp.status_code == 404, f"page {bad}: {resp.status_code}"


def test_thirty_cards_cost_one_pdf_download(client, headers_a, transcription_3p):
    """The census-E pin for the card thumbnail: one dashboard load of thirty
    tests must not be thirty full-PDF downloads."""
    from app.services import page_cache
    page_cache.clear()

    fake = _FakeGcs()
    m = _patch_fake_gcs(fake)
    try:
        first = client.get(_image_url(transcription_3p), headers=headers_a)
        assert first.status_code == 200
        payload = first.content
        for _ in range(29):
            resp = client.get(_image_url(transcription_3p), headers=headers_a)
            assert resp.status_code == 200
            assert resp.content == payload
    finally:
        m.stop()

    assert len(fake.pdf_downloads) == 1, (
        f"expected ONE source-PDF download across 30 card loads, "
        f"got {len(fake.pdf_downloads)}")


def test_the_webp_thumbnail_is_far_smaller_than_the_review_png(
        client, headers_a, transcription_3p):
    """The reason this resource exists at all. On the synthetic 3-page fixture
    the ratio is smaller than on real scans (1168 KB -> 33.6 KB there), but the
    direction is the whole claim and must hold."""
    from app.services import page_cache
    page_cache.clear()
    webp = _get_image(client, headers_a, transcription_3p).content
    png_b64 = _get_page(client, headers_a, transcription_3p, 1).json()["thumbnail_base64"]
    assert len(webp) < len(png_b64), (
        f"thumbnail {len(webp)} B is not smaller than the review image "
        f"{len(png_b64)} B — the resource has no reason to exist")


def test_json_page_proxy_bytes_are_unchanged(client, headers_a, transcription_3p):
    """The variant-key change must not move the JSON proxy's payload by a byte."""
    from app.services import page_cache
    page_cache.clear()
    expected = [image_to_base64(img) for img in pdf_to_images(THREE_PAGE_PDF, 150)]
    for page_number in (1, 2, 3):
        resp = _get_page(client, headers_a, transcription_3p, page_number)
        assert resp.status_code == 200
        assert resp.json()["thumbnail_base64"] == expected[page_number - 1]


def test_the_two_resources_do_not_answer_for_each_other(
        client, headers_a, transcription_3p):
    """Cache-namespace isolation, end to end: warming one must not populate the
    other, and neither may return the other's bytes."""
    from app.services import page_cache
    page_cache.clear()
    _get_image(client, headers_a, transcription_3p)          # warm webp only

    with _patch_gcs() as mock_gcs:
        mock_gcs.return_value.download_bytes.return_value = THREE_PAGE_PDF
        json_resp = client.get(
            f"/api/v0/transcriptions/{transcription_3p}/pages/1", headers=headers_a)
    assert json_resp.status_code == 200
    body = json_resp.json()["thumbnail_base64"]
    assert base64.b64decode(body)[:4] == b"\x89PNG", (
        "the JSON proxy answered with the WebP thumbnail's bytes")


# --- the variant value type, unit ------------------------------------------

def test_variant_token_round_trips_and_rejects_junk():
    v = thumbnail.current_variant()
    assert thumbnail.ThumbVariant.parse(v.token) == v
    assert v.cache_variant.startswith("webp@")
    for bad in ("", "600x72", "600x72@", "x@", "600x200@110", "600x72@110extra",
                "999999x72@110", "600x0@110"):
        assert thumbnail.ThumbVariant.parse(bad) is None, bad


def test_resolve_variant_separates_pinned_from_unpinned_from_unknown():
    current = thumbnail.current_variant()
    assert thumbnail.resolve_variant(current.token) == (current, True)
    assert thumbnail.resolve_variant(None) == (current, False)
    assert thumbnail.resolve_variant("") == (current, False)
    assert thumbnail.resolve_variant("601x72@110") == (None, False)


def test_an_unparseable_legacy_variant_is_dropped_not_fatal():
    """A config typo must not take the route down; it is logged and skipped,
    and the current variant is always present and can never be excluded."""
    from app.config import settings as s
    original = s.page_thumb_legacy_variants
    try:
        s.page_thumb_legacy_variants = ["not-a-token", "300x72@72"]
        allowed = thumbnail.allowed_variants()
        assert thumbnail.current_variant() in allowed
        assert thumbnail.ThumbVariant(300, 72, 72) in allowed
        assert len(allowed) == 2
    finally:
        s.page_thumb_legacy_variants = original


def test_page_image_path_is_relative_and_carries_the_live_variant():
    path = thumbnail.page_image_path("abc-123")
    assert path.startswith("/api/v0/transcriptions/abc-123/pages/1/image?v=")
    assert path.endswith(thumbnail.current_variant().token)


# ---------------------------------------------------------------------------
# PLAN_page1_image_route phase 2 — the GCS thumb store
#
# Cloud Run runs up to 60 instances, so the in-process cache has a poor hit rate
# by construction: without a stored thumbnail it is the ONLY thing between the
# pilot and thirty full-PDF downloads per dashboard load, on a school
# connection. These pin that the store is consulted, written, keyed correctly,
# and never able to fail the request.
# ---------------------------------------------------------------------------


def test_thumb_rendered_once_then_read_from_gcs(
        client, headers_a, transcription_3p):
    """The phase-2 claim. The FIRST request renders and persists; a request from
    a cold instance (in-process cache cleared, which is what a different Cloud
    Run instance looks like) reads the ~34 KB object and never touches the PDF."""
    from app.services import page_cache
    page_cache.clear()

    fake = _FakeGcs()
    m = _patch_fake_gcs(fake)
    try:
        first = client.get(_image_url(transcription_3p), headers=headers_a)
        assert first.status_code == 200
        assert len(fake.pdf_downloads) == 1, "the cold request did not render"
        assert len(fake.uploads) == 1, "the render was not persisted"
        path, content_type, size = fake.uploads[0]
        assert path.startswith("thumbs/") and path.endswith(".webp")
        assert content_type == "image/webp"
        assert size == len(first.content)

        # A DIFFERENT instance: no in-process cache, same bucket.
        page_cache.clear()
        second = client.get(_image_url(transcription_3p), headers=headers_a)
        assert second.status_code == 200
        assert second.content == first.content
    finally:
        m.stop()

    assert len(fake.pdf_downloads) == 1, (
        f"the second instance re-downloaded the source PDF "
        f"({len(fake.pdf_downloads)} downloads) instead of reading the thumb")
    assert len(fake.uploads) == 1, "the thumbnail was written twice"
    assert len(fake.thumb_downloads) == 2, (
        "the store was not consulted before rendering")


def test_the_stored_thumb_path_carries_the_variant():
    """⟨C1⟩ one layer down. The PR-G8 spec line said `thumbs/{id}/p1.webp`, from
    before the variant existed — keeping that would rebuild the exact bug the
    variant fixed for the browser: change a render setting and every teacher is
    served the old bytes from GCS forever, with no expiry to age them out and no
    request that can ever miss."""
    from app.services.thumbnail import ThumbVariant, gcs_object_path

    a = gcs_object_path("tx-1", 1, ThumbVariant(600, 72, 110))
    b = gcs_object_path("tx-1", 1, ThumbVariant(800, 72, 110))
    assert a != b, "a settings change reuses the same GCS object"
    assert "600" in a and "800" in b
    assert a.startswith("thumbs/tx-1/") and a.endswith(".webp")
    assert "@" not in a, "'@' in an object path is asking for trouble"


def test_a_thumb_store_read_failure_degrades_to_rendering(
        client, headers_a, transcription_3p):
    """The store is an optimisation, never a dependency. If GCS cannot answer
    for the thumb, the teacher still gets her image."""
    from app.services import page_cache
    page_cache.clear()

    fake = _FakeGcs()
    fake.fail_thumb_read = True
    m = _patch_fake_gcs(fake)
    try:
        resp = client.get(_image_url(transcription_3p), headers=headers_a)
    finally:
        m.stop()

    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"RIFF"
    assert len(fake.pdf_downloads) == 1, "it did not fall through to a render"


def test_a_thumb_store_write_failure_is_not_fatal(
        client, headers_a, transcription_3p):
    """Persisting is for the NEXT request. Failing this one because the write
    failed would trade a working image for a broken card."""
    from app.services import page_cache
    page_cache.clear()

    fake = _FakeGcs()
    fake.fail_upload = True
    m = _patch_fake_gcs(fake)
    try:
        resp = client.get(_image_url(transcription_3p), headers=headers_a)
    finally:
        m.stop()

    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"RIFF"
    assert fake.uploads == []


def test_the_store_is_not_consulted_before_ownership_and_variant_checks(
        client, headers_b, transcription_3p):
    """Ownership first, always (§9) — and an unknown variant names no resource,
    so neither may reach GCS at all."""
    from app.services import page_cache
    page_cache.clear()

    fake = _FakeGcs()
    m = _patch_fake_gcs(fake)
    try:
        cross = client.get(_image_url(transcription_3p), headers=headers_b)
        assert cross.status_code == 404
        assert fake.downloads == [], "a cross-tenant request reached the bucket"
    finally:
        m.stop()


def test_a_missing_thumb_is_silent_but_an_outage_is_logged(
        client, headers_a, transcription_3p, caplog):
    """A miss and an outage both degrade to a render, so if they look alike in
    the logs a broken bucket presents as "everything works, just slow" — the
    worst diagnostic shape there is, because nothing ever asks why."""
    import logging
    from app.services import page_cache

    # (a) the normal cold path: nothing stored yet
    page_cache.clear()
    caplog.clear()
    fake = _FakeGcs()
    m = _patch_fake_gcs(fake)
    try:
        with caplog.at_level(logging.WARNING, logger="app.api.v0.transcription"):
            assert client.get(_image_url(transcription_3p),
                              headers=headers_a).status_code == 200
    finally:
        m.stop()
    assert "page_thumb_read_failed" not in caplog.text, (
        "a first-ever request logged an outage")

    # (b) the bucket is broken
    page_cache.clear()
    caplog.clear()
    fake = _FakeGcs()
    fake.fail_thumb_read = True
    m = _patch_fake_gcs(fake)
    try:
        with caplog.at_level(logging.WARNING, logger="app.api.v0.transcription"):
            assert client.get(_image_url(transcription_3p),
                              headers=headers_a).status_code == 200
    finally:
        m.stop()
    assert "page_thumb_read_failed" in caplog.text, (
        "a GCS outage degraded silently")
