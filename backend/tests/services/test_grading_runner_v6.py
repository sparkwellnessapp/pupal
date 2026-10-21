"""[grader-v6 MVC, owner rulings 2026-10-17 §7/§9] `run_grading` under GRADER_ARCHITECTURE=v6,
end to end against the test DB, with the model calls injected (no provider):

  * the v6 plan builds LAZILY at the first grade, under the v6 key of the plan cache, and
    a second test of the same rubric reuses it (no second build);
  * the draft lands `draft` with its v6 block, the explanation line written at grading time
    (here the fallback composer's: no explainer configured), and `plan_hash` pinned;
  * the cost counts the verifier (D-7) on its own card.
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import delete, select

from app.config import settings
from app.database import get_db_context
from app.models.grading import GradedTest
from app.models.grading_plan import GradingPlanRecord
from tests.agents.test_grader_v6 import _Fake, _full
from tests.grading_eval_suite.fixtures import load_bundle


async def _seed(bundle, n_tests=2):
    from app.models.grading import Rubric
    from app.models.student import Student
    from app.models.transcription import Transcription
    from app.models.user import User
    ids = SimpleNamespace(user=uuid.uuid4(), rubric=uuid.uuid4(), student=uuid.uuid4(),
                          transcriptions=[], graded=[])
    tag = uuid.uuid4().hex[:8]
    contract = bundle.rubric_contract
    async with get_db_context() as db:
        db.add(User(id=ids.user, email=f"v6_runner_{tag}@s2test.com", full_name="v6 Runner",
                    password_hash="x"))
        await db.flush()
        db.add(Rubric(id=ids.rubric, user_id=ids.user, name=f"v6-{tag}", subject="computer_science",
                      contract_version=str(contract.contract_version),
                      contract_json=contract.model_dump(mode="json")))
        db.add(Student(id=ids.student, user_id=ids.user, full_name=f"תלמידה {tag}"))
        await db.flush()
        for _ in range(n_tests):
            tid, gid = uuid.uuid4(), uuid.uuid4()
            path = f"transcriptions/{ids.user}/{tid}.pdf"
            db.add(Transcription(id=tid, user_id=ids.user, rubric_id=ids.rubric, student_id=ids.student,
                                 gcs_uri=f"gs://b/{path}", gcs_bucket="b", gcs_object_path=path,
                                 filename="v6.pdf", draft_json={"page_count": 1, "answers": [], "annotations": []},
                                 contract_json=bundle.transcription_contract.model_dump(mode="json"),
                                 approved_at=datetime.now(timezone.utc), status="approved"))
            await db.flush()
            db.add(GradedTest(id=gid, user_id=ids.user, rubric_id=ids.rubric, transcription_id=tid,
                              student_id=ids.student, rubric_contract_version=str(contract.contract_version),
                              student_name="x", status="pending"))
            ids.transcriptions.append(tid)
            ids.graded.append(gid)
        await db.commit()
    return ids


async def _teardown(ids, sha):
    from sqlalchemy import text
    async with get_db_context() as db:
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.contract_sha256 == sha))
        for gid in ids.graded:
            await db.execute(text("DELETE FROM graded_tests WHERE id = :id"), {"id": gid})
        for tid in ids.transcriptions:
            await db.execute(text("DELETE FROM transcriptions WHERE id = :id"), {"id": tid})
        for table, key in (("students", ids.student), ("rubrics", ids.rubric), ("users", ids.user)):
            await db.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": key})
        await db.commit()


@pytest.mark.db
def test_v6_grades_build_the_plan_once_and_land_pinned_drafts(monkeypatch):
    from app.services import grader_selection, plan_build_v6
    from app.services.grading_runner import run_grading
    from app.services.plan_store import contract_sha256
    bundle = load_bundle("din_ezra", require_gt=False)
    planner_calls = []

    async def planner_refused(system, user):                # every scope's output is refused → the
        from app.agents.planner.schemas import ScopePlanOutput   # fallback (content, not an outage)
        planner_calls.append(1)
        return ScopePlanOutput(terminals=[]), {}

    monkeypatch.setattr(settings, "grader_architecture", "v6")
    monkeypatch.setattr(settings, "v6_explainer_model", "")       # the fallback composer's lines
    monkeypatch.setattr(settings, "feedback_model_key", "")
    monkeypatch.setattr("app.agents.planner.planner_llm.build_planner_call",
                        lambda **kw: planner_refused)
    monkeypatch.setattr("app.agents.grader.llm_factory.build_chat_model",
                        lambda *a, **kw: _Fake(_full))
    sha = contract_sha256(bundle.rubric_contract.model_dump(mode="json"))
    ids = None

    async def scenario():
        nonlocal ids
        ids = await _seed(bundle)
        assert await run_grading(ids.graded[0])
        first_calls = len(planner_calls)
        assert first_calls > 0                                     # built in place, at the first grade
        assert await run_grading(ids.graded[1])
        assert len(planner_calls) == first_calls                   # the second grade reused it
        async with get_db_context() as db:
            rows = (await db.execute(select(GradingPlanRecord).where(
                GradingPlanRecord.contract_sha256 == sha))).scalars().all()
            v6_rows = [r for r in rows if r.config_hash != "v5"]
            assert len(v6_rows) == 1 and v6_rows[0].status == "ready"
            assert v6_rows[0].wording_source == "placeholder"     # every scope fell back
            for gid in ids.graded:
                gt = await db.get(GradedTest, gid)
                assert gt.status == "draft", gt.error_message
                assert gt.plan_hash == v6_rows[0].plan_hash
                assert gt.draft_json["v6"]["plan_hash"] == gt.plan_hash
                assert gt.draft_json["v6"]["explanations"]          # written at grading time
                assert gt.total_cost_usd is not None and gt.total_cost_usd > 0
    try:
        asyncio.run(scenario())
    finally:
        if ids is not None:
            asyncio.run(_teardown(ids, sha))
