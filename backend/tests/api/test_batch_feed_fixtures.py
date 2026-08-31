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
