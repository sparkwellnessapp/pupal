"""
The §1.7 batch-feed fixtures must stay a true description of the endpoint.

A fixture the frontend builds against is a contract. If it can drift from the
wire type it describes, the disagreement surfaces at integration — the most
expensive place to find it — and the fixture will have been lying the whole
time. So these are GENERATED from the models (`scripts/gen_batch_feed_fixtures.py`)
and this test re-validates them against those same models.

If this fails after a schema change: regenerate, and read the diff. That diff is
the frontend's breaking-change notice.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "grade_review"
STATES = ("landing", "running", "done", "complete")


@pytest.mark.parametrize("state", STATES)
def test_fixture_validates_against_the_live_wire_type(state):
    from app.schemas.batch import BatchDetailResponse

    path = FIXTURES / f"batch_feed_{state}.json"
    assert path.is_file(), f"{path.name} is missing — run scripts/gen_batch_feed_fixtures.py"
    BatchDetailResponse.model_validate(json.loads(io.open(path, encoding="utf-8").read()))


@pytest.mark.parametrize("state", STATES)
def test_fixture_is_byte_identical_to_a_fresh_generation(state):
    """Regenerating must be a no-op. A hand-edit here is how a fixture starts
    describing a shape the backend never returns."""
    from scripts.gen_batch_feed_fixtures import STATES as BUILT

    fresh = json.dumps(BUILT[state].model_dump(mode="json"),
                       ensure_ascii=False, indent=2) + "\n"
    on_disk = io.open(FIXTURES / f"batch_feed_{state}.json", encoding="utf-8").read()
    assert on_disk == fresh, (
        f"batch_feed_{state}.json was hand-edited or the schema moved — "
        f"run scripts/gen_batch_feed_fixtures.py and read the diff")


def test_the_states_cover_what_the_dashboard_must_render():
    """Each fixture exists to pin one thing the UI has to get right.

    `running` carries a null look_count on purpose — a draft that will not
    parse gets NO number rather than a reassuring 0 (§3.5a), and the client has
    to render that honestly instead of as "nothing to check".
    """
    from app.schemas.batch import BatchDetailResponse

    def load(state):
        return BatchDetailResponse.model_validate(
            json.loads(io.open(FIXTURES / f"batch_feed_{state}.json",
                               encoding="utf-8").read()))

    landing = load("landing")
    assert landing.eta.kind == "first_landing" and landing.eta.seconds
    assert all(i.total_awarded is None for i in landing.graded_tests)

    running = load("running")
    assert running.eta.kind == "remaining"
    assert any(i.look_count is None for i in running.graded_tests), (
        "the unparseable-draft case is what stops the client showing a "
        "reassuring 0 for a test it cannot assess")
    assert any(i.look_count for i in running.graded_tests)

    done = load("done")
    assert done.eta.kind == "unknown", "no profile ⇒ «עוד רגע», never a number"
    assert any(i.opened_at and i.status == "draft" for i in done.graded_tests)

    complete = load("complete")
    assert any(i.status == "failed" for i in complete.graded_tests), (
        "a batch completes with its hole visible, not as 4 of 4")


# ---------------------------------------------------------------------------
# PLAN_page1_image_route phase 1b — page1_image_url on the feed
# ---------------------------------------------------------------------------

def test_page1_image_url_present_on_every_graded_item():
    """The Pile's thumbnail is the field; a fixture missing it would let F1
    build a grid against a payload the backend does not send."""
    from app.schemas.batch import BatchDetailResponse

    for state in STATES:
        feed = BatchDetailResponse.model_validate(
            json.loads(io.open(FIXTURES / f"batch_feed_{state}.json",
                               encoding="utf-8").read()))
        with_url = [i for i in feed.graded_tests if i.page1_image_url]
        assert with_url, f"{state}: no item carries a page-1 thumbnail url"
        for item in with_url:
            assert item.page1_image_url.startswith("/api/v0/transcriptions/"), (
                f"{state}: {item.page1_image_url} is not the relative seam path")
            assert "/pages/1/image?v=" in item.page1_image_url


def test_page1_image_url_omitted_when_there_is_no_page_1():
    """§3.5a — degrade by OMISSION. A url known to 404 renders a broken-image
    glyph, which reads as "this test is damaged" rather than "no preview".

    The omission sits on a `grading` item deliberately: it is INDEPENDENT of
    status, and carrying it on the failed one would teach the client a
    correlation that does not exist.
    """
    from app.schemas.batch import BatchDetailResponse

    feed = BatchDetailResponse.model_validate(
        json.loads(io.open(FIXTURES / "batch_feed_landing.json",
                           encoding="utf-8").read()))
    omitted = [i for i in feed.graded_tests if i.page1_image_url is None]
    assert len(omitted) == 1, (
        "the no-page-1 case is what stops the client rendering a broken image "
        "for a test that simply has no preview")
    assert omitted[0].status != "failed", (
        "the omission must not be correlated with failure in the fixture set")


def test_page1_image_url_carries_the_live_variant_token():
    """⟨C1⟩ the url pins the render settings, because the route answers with a
    year of `immutable`. If the fixtures spelled the token out by hand they
    would keep describing a url the backend stopped issuing after a settings
    change; minting it means the change shows up here as a diff."""
    from app.schemas.batch import BatchDetailResponse
    from app.services.thumbnail import current_variant

    token = current_variant().token
    feed = BatchDetailResponse.model_validate(
        json.loads(io.open(FIXTURES / "batch_feed_running.json",
                           encoding="utf-8").read()))
    for item in feed.graded_tests:
        if item.page1_image_url:
            assert item.page1_image_url.endswith(f"?v={token}"), (
                f"{item.page1_image_url} does not carry the live variant {token}")


def test_the_thumbnail_url_addresses_the_transcription_not_the_graded_test():
    """A regrade extends the chain with a NEW graded test over the SAME
    transcription. Addressing the thumbnail by graded_test_id would 404 on
    every revision — and would be a route that does not exist at all."""
    from app.schemas.batch import BatchDetailResponse

    feed = BatchDetailResponse.model_validate(
        json.loads(io.open(FIXTURES / "batch_feed_done.json",
                           encoding="utf-8").read()))
    for item in feed.graded_tests:
        if item.page1_image_url:
            assert str(item.graded_test_id) not in item.page1_image_url, (
                "the url is built from the graded_test_id, which the page route "
                "cannot resolve")
