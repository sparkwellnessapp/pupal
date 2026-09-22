"""
The purge's two routes, with real auth and real rows (PR §12, §14, §15).

  GET    /api/v0/classroom/students/{id}/purge-preview   the plan, summarised; never writes
  DELETE /api/v0/classroom/students/{id}                 409 on a blocker; else purge + verify,
                                                         200 with the report (M-B4)

  PRV-4  OwnerOnly          another teacher's student is 404, and nothing is touched
  PRV-5  NoDeleteMidGrade   409 {"detail": "grading_in_progress", "count": n}
  PRV-7  VerifiedAfter      the DELETE body is the verify report
  §5.4   the interim 409 `student_has_data` is GONE

The storage client is the one dependency faked (`get_purge_storage`) — the
auth dependency never is (CLAUDE.md §9).

RED until the preview route, the purge, and migration 032 exist.
"""
from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.services.erasure.fakes import FakeStorage
from tests.services.erasure.seed import (
    BUCKET,
    add_graded_blocker,
    add_student,
    drop_graph,
    row_counts,
    seed_graph,
)

STUDENT = "/api/v0/classroom/students/{id}"
PREVIEW = STUDENT + "/purge-preview"


@pytest.fixture
def world(user_a):
    """A graph owned by the session's `user_a`, a bucket holding its objects,
    and the purge's storage dependency pointed at that bucket."""
    from app.main import app
    from app.services.erasure import GuardedStorage, get_purge_storage

    g = asyncio.run(seed_graph(user_id=uuid.UUID(user_a["user"]["id"])))
    store = FakeStorage(g.objects)
    app.dependency_overrides[get_purge_storage] = (
        lambda: GuardedStorage(store, known_buckets=frozenset({BUCKET})))
    try:
        yield g, store
    finally:
        app.dependency_overrides.pop(get_purge_storage, None)
        asyncio.run(drop_graph(g))


def test_the_preview_is_the_plan_summarised_and_never_writes(client, headers_a, world):
    g, store = world
    before = asyncio.run(row_counts(g))

    resp = client.get(PREVIEW.format(id=g.student_id), headers=headers_a)
    assert resp.status_code == 200, resp.text
    body = resp.json()

    rows = g.expected_rows()
    assert body["case"] == "signed_tests"
    assert body["signed_tests_count"] == 2              # chains alpha (r1) and beta
    assert body["blockers"] == 0
    assert body["counts"] == {t: len(ids) for t, ids in rows.items() if t != "students"}
    objects = g.expected_objects()
    assert body["objects"] == {
        family: sum(1 for (_, n) in objects if n.startswith(family + "/"))
        for family in ("transcriptions", "thumbs", "returned_exams")}
    assert asyncio.run(row_counts(g)) == before
    assert store.delete_calls() == []


def test_the_preview_names_the_dialog_case(client, headers_a, world):
    """PR §15: signed tests / data but no signed test / nothing attributable."""
    g, _ = world
    drafts = asyncio.run(add_student(g, draft_only=True))
    bare = asyncio.run(add_student(g))

    for sid, case in ((drafts, "data_only"), (bare, "nothing")):
        resp = client.get(PREVIEW.format(id=sid), headers=headers_a)
        assert resp.status_code == 200, resp.text
        assert (resp.json()["case"], resp.json()["signed_tests_count"]) == (case, 0)


def test_the_preview_of_another_teachers_student_is_404(client, headers_b, world):
    g, store = world
    resp = client.get(PREVIEW.format(id=g.student_id), headers=headers_b)
    assert resp.status_code == 404
    assert store.calls == []


def test_delete_purges_and_answers_200_with_the_verify_report(client, headers_a, world):
    g, store = world
    resp = client.delete(STUDENT.format(id=g.student_id), headers=headers_a)
    assert resp.status_code == 200, resp.text

    report = resp.json()["verify"]
    assert report["clean"] is True
    assert all(n == 0 for n in report["rows_remaining"].values())
    assert report["objects_remaining"] == 0
    assert report["soft_deleted_count"] == len(g.expected_objects())
    assert report["restorable_until"]
    after = asyncio.run(row_counts(g))
    assert after["students"] == 1                       # the control student
    assert set(store.delete_calls()) == g.expected_objects()


def test_delete_of_another_teachers_student_is_404_and_touches_nothing(client, headers_b, world):
    g, store = world
    before = asyncio.run(row_counts(g))
    resp = client.delete(STUDENT.format(id=g.student_id), headers=headers_b)
    assert resp.status_code == 404
    assert asyncio.run(row_counts(g)) == before
    assert store.calls == []


def test_delete_during_grading_is_409_and_touches_nothing(client, headers_a, world):
    g, store = world
    asyncio.run(add_graded_blocker(g, "grading"))
    store.live |= g.objects
    before = asyncio.run(row_counts(g))

    resp = client.delete(STUDENT.format(id=g.student_id), headers=headers_a)
    assert resp.status_code == 409
    assert resp.json() == {"detail": "grading_in_progress", "count": 1}
    assert asyncio.run(row_counts(g)) == before
    assert store.delete_calls() == []


def test_the_interim_student_has_data_409_is_gone(client, headers_a, world):
    """§5.4 was the interim; the purge replaces it. A student with only a draft
    is purged, not refused."""
    g, _ = world
    drafts = asyncio.run(add_student(g, draft_only=True))

    resp = client.delete(STUDENT.format(id=drafts), headers=headers_a)
    assert resp.status_code == 200, resp.text
    assert resp.json()["verify"]["clean"] is True


def test_a_student_with_nothing_attributable_is_deleted(client, headers_a, world):
    g, _ = world
    bare = asyncio.run(add_student(g))

    resp = client.delete(STUDENT.format(id=bare), headers=headers_a)
    assert resp.status_code == 200, resp.text
    assert client.get(PREVIEW.format(id=bare), headers=headers_a).status_code == 404
