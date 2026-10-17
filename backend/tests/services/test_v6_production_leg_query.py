"""[grader-v6, owner rulings 2026-10-17 §10] the production-leg query the owner runs by
hand (`docs/plans/v6_production_leg_query.sql`), pinned against the schema it reads.

A query run once, by hand, against production has no other test: if a JSON path or a
column name in it is wrong, the first anyone hears of it is a NULL in the owner's paste.
So this seeds one approved v6 batch (a REAL v6 contract, compiled by the approval gate
from a real v6 draft, with one check re-picked and one criterion set to 0 over Vivi's
credit) and one approved v5 batch, runs the file verbatim and checks the numbers."""
from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path

import pytest
from sqlalchemy import text

from app.database import get_db_context
from app.schemas.graded_test_draft_v6 import v6_content
from app.services.graded_test_contract_compiler import compile_graded_test
from app.services.v6_review import CheckPatchV6, OverlayPatchV6, merge_overlay, overlay_of, review
from tests.services.test_v6_review_mvc import _grade, _with

QUERY = Path(__file__).resolve().parents[3] / "docs" / "plans" / "v6_production_leg_query.sql"
LONG_AGO = datetime(2020, 1, 1, tzinfo=timezone.utc)      # earliest v6 batch, whatever else is there


def _contracts():
    draft, bundle = _grade()
    content = v6_content(draft)
    ai = review(draft, draft.teacher_overrides).ai
    ladder = next(c.plan for c in content.checks if c.plan.role == "credit" and len(c.plan.options) > 2)
    credited = next(t.terminal_id for t in ai.terminals
                    if t.awarded > 0 and t.terminal_id != ladder.priced_terminal_id)
    v6_draft, overrides = _with(draft, merge_overlay(overlay_of(None), OverlayPatchV6(
        checks={ladder.check_id: CheckPatchV6(option_id=ladder.options[-1].option_id)},
        terminal_points={credited: D("0")})))
    v6 = compile_graded_test(v6_draft, overrides, bundle.rubric_contract)
    v5 = v6.model_dump(mode="json")
    v5.pop("v6")
    v5["prompt_version"] = "grader-v5.4"
    return bundle, v6_draft, v6, v5, ladder, credited


@pytest.mark.db
def test_the_production_leg_query_reads_what_it_claims():
    from app.models.grading import GradedTest, GradingBatch, Rubric
    from app.models.student import Student
    from app.models.transcription import Transcription
    from app.models.user import User
    bundle, v6_draft, v6, v5, ladder, credited = _contracts()
    contract = bundle.rubric_contract
    tag = uuid.uuid4().hex[:8]
    user, rubric, student = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    batches = {"v6": uuid.uuid4(), "v5": uuid.uuid4()}
    rows = []

    async def seed():
        async with get_db_context() as db:
            db.add(User(id=user, email=f"v6_leg_{tag}@v6leg.example", full_name="leg", password_hash="x"))
            await db.flush()
            db.add(Rubric(id=rubric, user_id=user, name=f"leg-{tag}", subject="computer_science",
                          contract_version=str(contract.contract_version),
                          contract_json=contract.model_dump(mode="json")))
            db.add(Student(id=student, user_id=user, full_name=f"תלמידה {tag}"))
            await db.flush()
            for arch, doc in (("v6", v6.model_dump(mode="json")), ("v5", v5)):
                db.add(GradingBatch(id=batches[arch], user_id=user, rubric_id=rubric,
                                    rubric_contract_version=str(contract.contract_version),
                                    status="completed", test_count=1, created_at=LONG_AGO))
                await db.flush()
                tid, gid = uuid.uuid4(), uuid.uuid4()
                path = f"transcriptions/{user}/{tid}.pdf"
                db.add(Transcription(id=tid, user_id=user, rubric_id=rubric, student_id=student,
                                     gcs_uri=f"gs://b/{path}", gcs_bucket="b", gcs_object_path=path,
                                     filename="leg.pdf", batch_id=batches[arch],
                                     draft_json={"page_count": 1, "answers": [], "annotations": []},
                                     contract_json=bundle.transcription_contract.model_dump(mode="json"),
                                     approved_at=LONG_AGO, status="approved"))
                await db.flush()
                db.add(GradedTest(id=gid, user_id=user, rubric_id=rubric, transcription_id=tid,
                                  student_id=student, batch_id=batches[arch], student_name="x",
                                  rubric_contract_version=str(contract.contract_version),
                                  status="approved", draft_json=v6_draft.model_dump(mode="json"),
                                  contract_json=doc, created_at=LONG_AGO,
                                  opened_at=LONG_AGO, approved_at=LONG_AGO + timedelta(minutes=30)))
                rows.append((gid, tid))
            await db.commit()

    async def run():
        async with get_db_context() as db:
            return (await db.execute(text(QUERY.read_text(encoding="utf-8")))).scalar_one()

    async def teardown():
        async with get_db_context() as db:
            for gid, tid in rows:
                await db.execute(text("DELETE FROM graded_tests WHERE id = :id"), {"id": gid})
                await db.execute(text("DELETE FROM transcriptions WHERE id = :id"), {"id": tid})
            for b in batches.values():
                await db.execute(text("DELETE FROM grading_batches WHERE id = :id"), {"id": b})
            for table, key in (("students", student), ("rubrics", rubric), ("users", user)):
                await db.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": key})
            await db.commit()

    try:
        asyncio.run(seed())
        out = json.loads(asyncio.run(run()))
    finally:
        asyncio.run(teardown())

    counted = [t for s in v6.scope_outcomes if s.counted_in_total for t in s.terminal_outcomes]
    changed = [t for t in counted if t.final_points_awarded != t.ai_points_awarded]
    assert out["first_v6_batch"] == str(batches["v6"])
    summary = {s["cohort"]: s for s in out["summary"]}
    mine = summary["v6_first_batch"]
    assert (mine["tests"], mine["criteria"], mine["criteria_overridden"]) == (1, len(counted), len(changed))
    k1 = {t.terminal_id for t in changed if t.ai_points_awarded > 0 and t.final_points_awarded == 0}
    assert credited in k1 and mine["k1_behaviour_overrides"] == len(k1)
    assert D(str(mine["median_min_to_sign"])) == D("30.0")
    assert summary["v5_batches"]["tests"] >= 1                           # the seeded v5 batch counts
    overrides = {o["criterion"]: o for o in out["v6_overrides"]}
    assert set(overrides) == {t.terminal_id for t in changed}
    assert {o["criterion"] for o in out["v6_overrides"][:len(k1)]} == k1  # K1 rows first
    assert all(overrides[t]["k1_behaviour"] is True for t in k1)
    re_picked = overrides.get(ladder.priced_terminal_id)
    if re_picked is not None:                                             # the re-pick moved the grade
        assert re_picked["checks_changed"][0]["check"] == ladder.check_id
