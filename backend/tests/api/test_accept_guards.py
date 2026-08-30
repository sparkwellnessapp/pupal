"""
P0 accept-path guards (batch-redesign spec v2, items B1 + B2).

B1 — accept_clean recomputes the flag verdict SERVER-side per item, with the
same inputs get_batch uses (live roster + rubric selection groups): flagged
items are skipped {skipped_reason: "flagged"} and left untouched; already-
approved items are reported {skipped_reason: "already_approved"} instead of
silently continuing. "Clean" becomes a server-guaranteed property (OD1).

B2 — accept_one shares the PATCH /review full-snapshot key-multiset guard
(one function, one 422 detail constant): the approval write never validates
less than the overlay save.

Live-DB integration tests (TestClient against DATABASE_URL), following the
sync-engine helper pattern of test_transcription_review.py. Grading kickoff is
patched at the Cloud-Tasks seam — never call OpenAI or enqueue in tests.
"""
from unittest.mock import patch
from uuid import uuid4

import pytest
import sqlalchemy

from tests.api.test_batch_grading import _clean_draft, _draft_with_annotation
from tests.api.test_transcription_review import (
    _cleanup_batch,
    _db_row,
    _insert_batch_sync,
    _insert_transcription_sync,
    _sync_engine,
    _user_id,
)


# ---------------------------------------------------------------------------
# Local helpers
# ---------------------------------------------------------------------------

def _create_student(client, headers, name: str) -> str:
    resp = client.post(
        "/api/v0/classroom/students", json={"full_name": name}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _graded_test_count(tx_id: str) -> int:
    engine = _sync_engine()
    with engine.connect() as conn:
        n = conn.execute(
            sqlalchemy.text(
                "SELECT COUNT(*) FROM graded_tests WHERE transcription_id = :id"
            ),
            {"id": tx_id},
        ).scalar_one()
    engine.dispose()
    return int(n)


_ENQUEUE_SEAM = "app.api.v0.batch_grading.enqueue_grading_task_or_log"


# ---------------------------------------------------------------------------
# B1 — server-side clean enforcement in accept_clean
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_accept_clean_skips_flagged_item(client, user_a, headers_a, rubric_a):
    """Flagged + clean posted together → accepted 1, flagged skipped with
    reason "flagged", flagged row still 'transcribed', no GradedTest for it."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=2)

    clean_name = f"תלמידה נקייה {uuid4().hex[:6]}"
    tx_clean = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=clean_name).model_dump(mode="json"),
    )
    # vlm_unparseable annotation ⇒ "unparseable" reason ⇒ review_needed.
    tx_flagged = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _draft_with_annotation("vlm_unparseable").model_dump(mode="json"),
    )
    s_clean = _create_student(client, headers_a, clean_name)
    s_other = _create_student(client, headers_a, f"תלמיד אחר {uuid4().hex[:6]}")
    try:
        with patch(_ENQUEUE_SEAM):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": [
                    {"transcription_id": tx_clean, "student_id": s_clean},
                    {"transcription_id": tx_flagged, "student_id": s_other},
                ]},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["accepted"] == 1
        assert body["skipped"] == [
            {"transcription_id": tx_flagged, "skipped_reason": "flagged"}
        ]

        flagged_row = _db_row(tx_flagged)
        assert flagged_row.status == "transcribed"        # untouched
        assert flagged_row.contract_json is None
        assert _graded_test_count(tx_flagged) == 0

        clean_row = _db_row(tx_clean)
        assert clean_row.status == "approved"
        assert _graded_test_count(tx_clean) == 1
    finally:
        _cleanup_batch(batch_id, [tx_clean, tx_flagged])


@pytest.mark.integration
def test_accept_clean_reports_already_approved(client, user_a, headers_a, rubric_a):
    """An item approved earlier (via accept_one) is reported
    {skipped_reason: "already_approved"} — not silently dropped."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=1)

    name = f"תלמיד מאושר {uuid4().hex[:6]}"
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=name).model_dump(mode="json"),
    )
    s_id = _create_student(client, headers_a, name)
    try:
        with patch(_ENQUEUE_SEAM):
            one = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx}",
                json={"student_id": s_id, "answers": [
                    {"question_number": 1, "sub_question_id": None,
                     "answer_text": "public class Node { int val; }"},
                ]},
                headers=headers_a,
            )
            assert one.status_code == 200, one.text
            assert one.json()["accepted"] == 1

            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": [{"transcription_id": tx, "student_id": s_id}]},
                headers=headers_a,
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["accepted"] == 0
        assert body["skipped"] == [
            {"transcription_id": tx, "skipped_reason": "already_approved"}
        ]
        assert _graded_test_count(tx) == 1                # no duplicate
    finally:
        _cleanup_batch(batch_id, [tx])


@pytest.mark.integration
def test_accept_clean_repost_idempotent(client, user_a, headers_a, rubric_a):
    """Reposting the same accept_clean body → accepted 0, everything reported
    already_approved, no duplicate GradedTests."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=2)

    names = [f"תלמיד חוזר {uuid4().hex[:6]}" for _ in range(2)]
    tx_ids = [
        _insert_transcription_sync(
            user_id, rubric_id, batch_id,
            _clean_draft(student_name=n).model_dump(mode="json"),
        )
        for n in names
    ]
    s_ids = [_create_student(client, headers_a, n) for n in names]
    items = [
        {"transcription_id": t, "student_id": s} for t, s in zip(tx_ids, s_ids)
    ]
    try:
        with patch(_ENQUEUE_SEAM):
            first = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": items}, headers=headers_a,
            )
            second = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": items}, headers=headers_a,
            )
        assert first.status_code == 200, first.text
        assert first.json()["accepted"] == 2
        assert first.json()["skipped"] == []

        assert second.status_code == 200, second.text
        assert second.json()["accepted"] == 0
        assert second.json()["skipped"] == [
            {"transcription_id": t, "skipped_reason": "already_approved"}
            for t in tx_ids
        ]
        for t in tx_ids:
            assert _graded_test_count(t) == 1
    finally:
        _cleanup_batch(batch_id, tx_ids)


# ---------------------------------------------------------------------------
# B2 — accept_one shares the PATCH key-multiset guard
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_accept_one_rejects_key_mismatch_422(client, user_a, headers_a, rubric_a):
    """A body whose answer keys don't match the draft's → 422, row untouched,
    no GradedTest created."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=1)
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft().model_dump(mode="json"),          # draft keys: [(1, "")]
    )
    s_id = _create_student(client, headers_a, f"תלמיד מפתח {uuid4().hex[:6]}")
    try:
        with patch(_ENQUEUE_SEAM):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx}",
                json={"student_id": s_id, "answers": [
                    {"question_number": 2, "sub_question_id": None,
                     "answer_text": "wrong key"},
                ]},
                headers=headers_a,
            )
        assert resp.status_code == 422, resp.text
        from app.api.guards import ANSWER_KEY_MISMATCH_DETAIL
        assert resp.json()["detail"] == ANSWER_KEY_MISMATCH_DETAIL

        row = _db_row(tx)
        assert row.status == "transcribed"               # untouched
        assert row.contract_json is None
        assert _graded_test_count(tx) == 0
    finally:
        _cleanup_batch(batch_id, [tx])


@pytest.mark.integration
def test_accept_one_and_patch_share_guard(client, user_a, headers_a, rubric_a):
    """PATCH /review and accept_one reject the same mismatch with the SAME
    detail string — the shared constant, not a copy."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=1)
    tx = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft().model_dump(mode="json"),          # draft keys: [(1, "")]
    )
    s_id = _create_student(client, headers_a, f"תלמיד שומר {uuid4().hex[:6]}")
    bad_answers = [
        {"question_number": 2, "sub_question_id": None, "answer_text": "ghost"},
    ]
    try:
        patch_resp = client.patch(
            f"/api/v0/transcriptions/{tx}/review",
            json={"answers": bad_answers, "student_id": None},
            headers=headers_a,
        )
        with patch(_ENQUEUE_SEAM):
            accept_resp = client.post(
                f"/api/v0/batches/{batch_id}/accept/{tx}",
                json={"student_id": s_id, "answers": bad_answers},
                headers=headers_a,
            )
        assert patch_resp.status_code == 422, patch_resp.text
        assert accept_resp.status_code == 422, accept_resp.text

        from app.api.guards import ANSWER_KEY_MISMATCH_DETAIL
        assert patch_resp.json()["detail"] == ANSWER_KEY_MISMATCH_DETAIL
        assert accept_resp.json()["detail"] == ANSWER_KEY_MISMATCH_DETAIL
    finally:
        _cleanup_batch(batch_id, [tx])


# ---------------------------------------------------------------------------
# E2 (closeout) — a poisoned item must NAME itself.
#
# accept_clean is all-or-nothing by design (one commit). The hazard is not the
# rollback — it is a bulk action that fails with no indication WHICH row broke
# it, leaving the teacher to re-click forever while her optimistic dimming
# reverts. Transaction semantics are deliberately unchanged here; only the
# report is fixed. Per-item commits are backlogged.
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_accept_clean_failure_names_the_offending_transcription(
    client, user_a, headers_a, rubric_a
):
    """A mid-loop failure returns the offending transcription id + filename and
    an actionable Hebrew message, and NOTHING is accepted (the whole
    transaction rolls back — both halves asserted)."""
    user_id = _user_id(user_a)
    rubric_id = rubric_a["rubric_id"]
    batch_id = _insert_batch_sync(user_id, rubric_id, test_count=2)

    name_a = f"תלמידה א {uuid4().hex[:6]}"
    name_b = f"תלמידה ב {uuid4().hex[:6]}"
    tx_ok = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=name_a).model_dump(mode="json"),
    )
    tx_poison = _insert_transcription_sync(
        user_id, rubric_id, batch_id,
        _clean_draft(student_name=name_b).model_dump(mode="json"),
    )
    s_ok = _create_student(client, headers_a, name_a)
    # BOTH students must exist: otherwise the poison item is flagged
    # `student_unassigned` and B1's skip absorbs it BEFORE the failure path —
    # the system defending itself, and the first version of this test proving
    # it. To exercise the halt we need a genuinely CLEAN item that then fails.
    _create_student(client, headers_a, name_b)
    try:
        # The poison: a student_id that does not exist. get_owned_or_404 raises
        # a bare 404 whose message names the STUDENT, never the transcription —
        # which is exactly the un-actionable shape this test pins closed.
        ghost_student = str(uuid4())
        with patch(_ENQUEUE_SEAM):
            resp = client.post(
                f"/api/v0/batches/{batch_id}/accept_clean",
                json={"items": [
                    {"transcription_id": tx_ok, "student_id": s_ok},
                    {"transcription_id": tx_poison, "student_id": ghost_student},
                ]},
                headers=headers_a,
            )

        assert resp.status_code == 404, resp.text
        detail = resp.json()["detail"]
        # (1) the offending item is NAMED — id and the filename she recognises
        assert detail["error"] == "accept_clean_failed"
        assert detail["transcription_id"] == tx_poison
        assert detail["filename"]
        assert detail["reason"]                      # the underlying cause survives
        # (2) the client-facing string is Hebrew, actionable, and names the file
        assert detail["accepted"] == 0
        assert detail["filename"] in detail["message_he"]
        assert "אף מבחן לא אושר" in detail["message_he"]

        # (3) all-or-nothing held: the GOOD item was rolled back too, so the
        # response's "accepted: 0" is the truth and not a hopeful guess.
        assert _db_row(tx_ok).status == "transcribed"
        assert _graded_test_count(tx_ok) == 0
        assert _db_row(tx_poison).status == "transcribed"
    finally:
        _cleanup_batch(batch_id, [tx_ok, tx_poison])
