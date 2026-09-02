"""
`_build_graded_feed` — the grading half of the batch feed (§1.5).

It had NO direct coverage before PLAN_page1_image_route: the fixtures pinned the
shape it emits, but nothing pinned the function that decides what goes in. These
drive it with plain row stand-ins — no DB, no provider, no mocks of either —
because everything it does is a pure function of the rows it is handed.

The page-1 thumbnail rules it enforces, and why each one is here:
  * the url addresses the TRANSCRIPTION, not the graded test (a regrade is a new
    graded test over the same transcription, so the other id would 404);
  * it is OMITTED, never guessed, when there is no page 1 (§3.5a);
  * it carries the live variant token, so a settings change mints a new url
    instead of leaving browsers on a year of `immutable` stale bytes (⟨C1⟩).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from app.api.v0.batch_grading import _build_graded_feed
from app.services.thumbnail import current_variant

NOW = datetime(2026, 8, 31, 18, 0, tzinfo=timezone.utc)


def _row(*, transcription_id=None, status="draft", landed=True, total="87.5"):
    tid = transcription_id or uuid4()
    return SimpleNamespace(
        id=uuid4(),
        transcription_id=tid,
        student_id=uuid4(),
        student_name="דן בסיוק",
        status=status,
        opened_at=None,
        total_score=None if total is None else Decimal(total),
        draft_json=None,                      # look_count degrades to None
        grading_started_at=NOW,
        draft_created_at=NOW + timedelta(seconds=61) if landed else None,
    )


def test_page1_image_url_present_on_every_graded_item():
    rows = [_row() for _ in range(3)]
    counts = {str(r.transcription_id): 4 for r in rows}

    items, _ = _build_graded_feed(rows, 6, counts)

    assert len(items) == 3
    for row, item in zip(rows, items):
        assert item.page1_image_url == (
            f"/api/v0/transcriptions/{row.transcription_id}/pages/1/image"
            f"?v={current_variant().token}")


def test_page1_image_url_omitted_when_there_is_no_page_1():
    """§3.5a — no url beats a url that 404s. Both the missing-key and the
    zero-pages spellings of "no page 1" must omit."""
    absent, zero, fine = _row(), _row(), _row()
    counts = {str(zero.transcription_id): 0, str(fine.transcription_id): 1}

    items, _ = _build_graded_feed([absent, zero, fine], 6, counts)

    assert items[0].page1_image_url is None, "unknown transcription got a url"
    assert items[1].page1_image_url is None, "a zero-page transcription got a url"
    assert items[2].page1_image_url is not None


def test_the_url_addresses_the_transcription_not_the_graded_test():
    """A regrade extends the chain: a NEW graded test over the SAME
    transcription. Two chain members must therefore produce the SAME url —
    addressing by graded_test_id would give two urls, both of which 404."""
    shared = uuid4()
    first, second = _row(transcription_id=shared), _row(transcription_id=shared)
    assert first.id != second.id

    items, _ = _build_graded_feed([first, second], 6, {str(shared): 3})

    assert items[0].page1_image_url == items[1].page1_image_url
    assert str(first.id) not in items[0].page1_image_url


def test_a_settings_change_mints_a_different_url():
    """⟨C1⟩ the whole reason the variant is in the url: change a render setting
    and the resource is NEW, rather than the old bytes being served for a year
    under `immutable` with no way to bust them."""
    from app.config import settings

    row = _row()
    counts = {str(row.transcription_id): 2}
    before = _build_graded_feed([row], 6, counts)[0][0].page1_image_url

    original = settings.page_thumb_width_px
    try:
        settings.page_thumb_width_px = original + 200
        after = _build_graded_feed([row], 6, counts)[0][0].page1_image_url
    finally:
        settings.page_thumb_width_px = original

    assert before != after, "a render-settings change reused the same url"
    assert str(original) in before and str(original + 200) in after


def test_page_counts_is_optional_so_the_feed_never_crashes_without_it():
    """Defensive, and deliberately so: the field is additive and the plan's
    rollback (§9) is "return None". A missing map must degrade to no urls, not
    to a 500 on the dashboard."""
    items, _ = _build_graded_feed([_row()], 6, None)
    assert items[0].page1_image_url is None


def test_the_rest_of_the_item_is_unchanged_by_the_new_field():
    """Guard against the field's arrival disturbing what was already there."""
    row = _row(status="approved", total="93.75")
    items, eta = _build_graded_feed([row], 6, {str(row.transcription_id): 1})
    item = items[0]

    assert item.graded_test_id == row.id
    assert item.student_name == "דן בסיוק"
    assert item.status == "approved"
    assert item.total_awarded == Decimal("93.75")
    assert item.look_count is None            # draft_json absent → degrade
    assert item.audit_touched == "none"
    assert item.returned_exam_state == "none"
    assert eta.kind in ("first_landing", "remaining", "unknown")
