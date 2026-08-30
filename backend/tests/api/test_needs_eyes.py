"""
needs_eyes (Ruling 1; ZC-1 v2 2026-08-23) — the SERVER half of the rule.

RECORD CORRECTION: the Ruling-1 log entry claimed a backend test asserted
needs_eyes; none existed (grep-verified 2026-08-23). This file closes that
gap AND pins the v2 semantics in one move.

The rule (twin: `isIdentityPending` in frontend/src/utils/zone-assignment.ts;
change one, change the other):
  - touched (review_json set)                      → needs eyes (Δ1)
  - flagged beyond `student_unassigned`            → needs eyes
  - IDENTITY-PENDING (untouched, ONLY flag is the
    extracted new name)                            → NOT needs eyes; home=clean
ZC-1 sum, server-side: transcribed = needs_eyes + clean-side.
"""
from unittest.mock import patch
from uuid import uuid4

import pytest

from tests.api.test_batch_grading import _clean_draft, _draft_with_annotation
from tests.api.test_transcription_review import (
    _cleanup_batch,
    _insert_batch_sync,
    _insert_transcription_sync,
    _user_id,
)


@pytest.mark.integration
def test_needs_eyes_excludes_identity_pending_and_both_endpoints_agree(
    client, user_a, headers_a, rubric_a
):
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=3)

    matched_name = f"תלמידה קיימת {uuid4().hex[:6]}"
    # (a) content-flagged → needs eyes
    tx_flagged = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _draft_with_annotation("vlm_unparseable").model_dump(mode="json"),
    )
    # (b) identity-pending: clean content, extracted NEW name, no roster row
    tx_pending = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=f"תלמיד חדש {uuid4().hex[:6]}").model_dump(mode="json"),
    )
    # (c) clean + matched (student exists)
    tx_clean = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=matched_name).model_dump(mode="json"),
    )
    resp = client.post("/api/v0/classroom/students",
                       json={"full_name": matched_name}, headers=headers_a)
    assert resp.status_code == 201, resp.text

    try:
        detail = client.get(f"/api/v0/batches/{batch_id}", headers=headers_a)
        assert detail.status_code == 200, detail.text
        rollup = detail.json()["rollup"]

        # v2: ONLY the content-flagged item needs her eyes. The pending item
        # is clean-side (its name rides the wave); the matched item is clean.
        assert rollup["needs_eyes"] == 1
        assert rollup["transcribed"] == 3
        # ZC-1 sum, server-side: transcribed = needs_eyes + clean-side.
        assert rollup["transcribed"] - rollup["needs_eyes"] == 2

        # The item-level verdicts stay HONEST (the wave needs the reason):
        items = {i["filename"]: i for i in detail.json()["transcriptions"]}
        by_id = {i["transcription_id"]: i for i in detail.json()["transcriptions"]}
        pending_item = by_id[tx_pending]
        assert pending_item["flag_verdict"]["review_needed"] is True
        assert pending_item["flag_verdict"]["reasons"] == ["student_unassigned"]

        # Endpoint agreement: the LIST reports the same number (one rule,
        # both endpoints — Ruling 1's original condition, now actually pinned).
        listing = client.get("/api/v0/batches", headers=headers_a)
        assert listing.status_code == 200
        row = next(b for b in listing.json() if b["id"] == str(batch_id))
        assert row["rollup"]["needs_eyes"] == 1
        assert row["rollup"]["transcribed"] == 3
    finally:
        _cleanup_batch(batch_id, [tx_flagged, tx_pending, tx_clean])
