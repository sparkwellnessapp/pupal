"""
AM-B1's regression half: regrade, manual_edit and retry still extend a chain
once migration 032 makes every graded-test FK NO ACTION — and a whole chain
still deletes in ONE statement (census §1: statement-end checking is all a
chain delete needs; the regraded_to_id deferral stays for extend_chain's
insert order).

Each test first asserts that 032 is applied: under today's SET NULL these
flows already pass, and a pass there would prove nothing about NO ACTION.

RED until migration 032.
"""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from tests.api.test_revision_flows import _fetch_row, _insert_approved_row, _insert_failed_row
from tests.services.erasure.seed import session

SELF_FKS = ("graded_tests_regraded_from_id_fkey", "graded_tests_regraded_to_id_fkey")


async def _self_fk_rules() -> dict[str, tuple[str, str]]:
    async with session() as db:
        rows = (await db.execute(text("""
            SELECT tc.constraint_name, rc.delete_rule, tc.initially_deferred
              FROM information_schema.table_constraints tc
              JOIN information_schema.referential_constraints rc
                ON rc.constraint_name = tc.constraint_name AND rc.constraint_schema = tc.table_schema
             WHERE tc.constraint_name = ANY(:n)"""), {"n": list(SELF_FKS)})).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def _require_032() -> None:
    rules = asyncio.run(_self_fk_rules())
    assert rules == {
        "graded_tests_regraded_from_id_fkey": ("NO ACTION", "NO"),
        "graded_tests_regraded_to_id_fkey": ("NO ACTION", "YES"),
    }, f"migration 032 is not applied to this database: {rules}"


async def _chain_ids(transcription_id: str) -> list[str]:
    async with session() as db:
        return [str(r[0]) for r in (await db.execute(
            text("SELECT id FROM graded_tests WHERE transcription_id = :t"),
            {"t": uuid.UUID(transcription_id)})).all()]


async def _drop_chain(transcription_id: str) -> None:
    """The whole chain in ONE statement, then its scan and its student —
    explicit, in dependency order, never leaning on a cascade (census F)."""
    t = uuid.UUID(transcription_id)
    async with session() as db:
        student = (await db.execute(text("SELECT student_id FROM transcriptions WHERE id = :t"),
                                    {"t": t})).scalar_one_or_none()
        await db.execute(text("DELETE FROM graded_tests WHERE transcription_id = :t"), {"t": t})
        await db.execute(text("DELETE FROM transcriptions WHERE id = :t"), {"t": t})
        if student is not None:
            await db.execute(text("DELETE FROM students WHERE id = :s"), {"s": student})
        await db.commit()


def _assert_linked(r1_id: str, r2_id: str) -> None:
    r1, r2 = asyncio.run(_fetch_row(r1_id)), asyncio.run(_fetch_row(r2_id))
    assert r1["regraded_to_id"] == r2_id
    assert r2["regraded_from_id"] == r1_id
    assert r2["regraded_to_id"] is None


@pytest.fixture
def approved_chain(user_a, rubric_a, headers_a):
    gid, tid = asyncio.run(_insert_approved_row(
        user_a["user"]["id"], rubric_a["rubric_id"], rubric_contract_version="stale-version-032"))
    yield gid, tid, headers_a
    asyncio.run(_drop_chain(tid))


@pytest.fixture
def failed_chain(user_a, rubric_a, headers_a):
    gid, tid = asyncio.run(_insert_failed_row(user_a["user"]["id"], rubric_a["rubric_id"]))
    yield gid, tid, headers_a
    asyncio.run(_drop_chain(tid))


@pytest.mark.integration
def test_regrade_extends_the_chain_under_no_action(client, approved_chain):
    _require_032()
    gid, _, headers = approved_chain
    with patch("app.api.v0.grading.enqueue_grading_task_or_log", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/regrade", headers=headers)
    assert resp.status_code == 200, resp.text
    _assert_linked(gid, resp.json()["graded_test_id"])


@pytest.mark.integration
def test_manual_edit_extends_the_chain_under_no_action(client, approved_chain):
    _require_032()
    gid, _, headers = approved_chain
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200, resp.text
    _assert_linked(gid, resp.json()["graded_test_id"])


@pytest.mark.integration
def test_retry_extends_the_chain_under_no_action(client, failed_chain):
    _require_032()
    gid, _, headers = failed_chain
    with patch("app.api.v0.grading.enqueue_grading_task_or_log", new=AsyncMock()):
        resp = client.post(f"/api/v0/grading/graded_test/{gid}/retry", headers=headers)
    assert resp.status_code == 200, resp.text
    _assert_linked(gid, resp.json()["graded_test_id"])


@pytest.mark.integration
def test_a_whole_chain_deletes_in_one_statement_under_no_action(client, approved_chain):
    """R1 → R2 references run both ways (regraded_to_id deferred, regraded_from_id
    immediate). NO ACTION checks at statement end, so one statement deleting
    both succeeds whatever order the rows are visited in."""
    _require_032()
    gid, tid, headers = approved_chain
    resp = client.post(f"/api/v0/grading/graded_test/{gid}/manual_edit", headers=headers)
    assert resp.status_code == 200, resp.text
    assert len(asyncio.run(_chain_ids(tid))) == 2

    async def _delete_chain() -> None:
        async with session() as db:
            await db.execute(text("DELETE FROM graded_tests WHERE transcription_id = :t"),
                             {"t": uuid.UUID(tid)})
            await db.commit()
    asyncio.run(_delete_chain())
    assert asyncio.run(_chain_ids(tid)) == []
