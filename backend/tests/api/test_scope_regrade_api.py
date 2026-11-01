"""[SRG] POST /api/v0/grading/graded_test/{id}/answers/regrade, end to end through the app
with real users and real Bearer tokens (§9: never fake the auth dependency). Only the
MODEL is scripted: `build_grader_v6` is swapped for the v6 grader over test_grader_v6's
fake, so the pricer, the graft, the transaction and the chain are all the real ones.

The seeded world is one the endpoint would meet in production: the hobby rubric with its
contract version, the plan the draft was graded against in `grading_plans`, an APPROVED
transcription carrying the contract the draft was compiled from, and the draft row."""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

from tests.agents.test_grader_v6 import MODEL, _Fake

BASE = "/api/v0/grading/graded_test"


def _full(role, opts):
    return opts[0]


def _default(role, opts):
    return opts[-1] if role == "CREDIT" else opts[0]


def _hobby():
    from app.agents.grader.plan_schemas import GradingPlanV6
    from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle
    plan = GradingPlanV6.model_validate_json(
        (SUITE_DIR / "plans" / "v6" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    return plan, load_bundle("din_ezra", require_gt=False)


def _agent(plan, contract, pick=_full, fail_times=0):
    from app.agents.grader.grader_v6 import OptionsVerifyGrader
    from app.subjects import get_profile
    return OptionsVerifyGrader(plan, contract, llm=_Fake(pick, fail_times=fail_times),
                               model_version=MODEL, profile=get_profile("computer_science"))


async def _seed(user_id: str, draft, plan, bundle) -> dict:
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import GradedTest, Rubric
    from app.models.grading_plan import GradingPlanRecord
    from app.models.student import Student
    from app.models.transcription import Transcription
    rc, tc = bundle.rubric_contract, bundle.transcription_contract
    uid = uuid.UUID(user_id)
    ids = {k: uuid.uuid4() for k in ("rubric", "plan", "student", "transcription", "graded")}
    async with _fresh_loop_session() as db:
        db.add(Rubric(id=ids["rubric"], user_id=uid, name="srg hobby", subject="computer_science",
                      total_points=float(rc.total_points), contract_json=rc.model_dump(mode="json"),
                      contract_version=str(rc.contract_version)))
        db.add(GradingPlanRecord(id=ids["plan"], rubric_id=ids["rubric"],
                                 contract_version=str(rc.contract_version),
                                 contract_sha256=uuid.uuid4().hex, config_hash=uuid.uuid4().hex,
                                 # SUPERSEDED on purpose: SRG-3 grades with the plan the draft
                                 # was graded with, found by its hash, even after a rebuild
                                 plan_hash=plan.plan_hash, status="superseded",
                                 plan_json=plan.model_dump(mode="json")))
        db.add(Student(id=ids["student"], user_id=uid, full_name=f"SRG {uuid.uuid4().hex[:6]}"))
        await db.flush()
        db.add(Transcription(id=ids["transcription"], user_id=uid, rubric_id=ids["rubric"],
                             student_id=ids["student"], student_name="SRG", gcs_uri="gs://t/s.pdf",
                             gcs_bucket="t", gcs_object_path="s.pdf", filename="s.pdf",
                             draft_json={"stub": True}, contract_json=tc.model_dump(mode="json"),
                             approved_at=datetime.now(timezone.utc), status="approved"))
        await db.flush()
        db.add(GradedTest(id=ids["graded"], user_id=uid, rubric_id=ids["rubric"],
                          transcription_id=ids["transcription"], student_id=ids["student"],
                          rubric_contract_version=str(rc.contract_version),
                          transcription_contract_version=tc.contract_version,
                          plan_hash=plan.plan_hash, student_name="SRG", filename="s.pdf",
                          status="draft", draft_json=draft.model_dump(mode="json")))
        await db.commit()
    return {k: str(v) for k, v in ids.items()}


async def _cleanup(ids: dict) -> None:
    from sqlalchemy import delete
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import GradedTest, Rubric
    from app.models.grading_plan import GradingPlanRecord
    from app.models.student import Student
    from app.models.transcription import Transcription
    async with _fresh_loop_session() as db:
        rid = uuid.UUID(ids["rubric"])
        await db.execute(delete(GradedTest).where(GradedTest.rubric_id == rid))
        await db.execute(delete(Transcription).where(Transcription.rubric_id == rid))
        await db.execute(delete(GradingPlanRecord).where(GradingPlanRecord.id == uuid.UUID(ids["plan"])))
        await db.execute(delete(Student).where(Student.id == uuid.UUID(ids["student"])))
        await db.execute(delete(Rubric).where(Rubric.id == rid))
        await db.commit()


async def _read(ids: dict):
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import GradedTest
    from app.models.transcription import Transcription
    from sqlalchemy import select
    async with _fresh_loop_session() as db:
        rows = (await db.execute(select(GradedTest).where(
            GradedTest.rubric_id == uuid.UUID(ids["rubric"])))).scalars().all()
        t = await db.get(Transcription, uuid.UUID(ids["transcription"]))
        return ({str(r.id): (r.status, r.regraded_to_id, r.transcription_contract_version, r.plan_hash,
                             r.total_score, r.draft_json) for r in rows},
                t.contract_json, t.contract_history)


@pytest.fixture(scope="module")
def hobby():
    return _hobby()


@pytest.fixture
def world(client, user_a, headers_a, hobby, monkeypatch):
    plan, bundle = hobby
    calls = {"fail_times": 0, "pick": _default}

    def fake_builder(p, contract, *, gradable_test=None):
        return _agent(p, contract, pick=calls["pick"], fail_times=calls["fail_times"])

    import app.services.grader_selection as gs
    monkeypatch.setattr(gs, "build_grader_v6", fake_builder)
    draft = asyncio.run(_agent(plan, bundle.rubric_contract).grade(bundle.gradable_test))
    ids = asyncio.run(_seed(user_a["user"]["id"], draft, plan, bundle))
    target = next(s for s in bundle.gradable_test.scopes if s.student_answer_text)
    yield ids, headers_a, draft, target, calls
    asyncio.run(_cleanup(ids))


def _body(scope, text):
    return {"question_id": scope.question_id, "sub_question_id": scope.sub_question_id,
            "answer_text": text}


def test_a_correction_regrades_and_extends_the_chain(client, world):
    ids, headers, draft, target, _calls = world
    # her decision on the scope she is about to correct (D5: it goes) and a note (it stays)
    v6 = client.get(f"{BASE}/{ids['graded']}/v6", headers=headers).json()
    sid = target.question_id + (f".{target.sub_question_id}" if target.sub_question_id else "")
    tids = {t["terminal_id"] for t in v6["content"]["view_terminals"]
            if (t["question_id"], t["sub_question_id"]) == (target.question_id, target.sub_question_id)}
    check = next(c["plan"] for c in v6["content"]["checks"] if c["plan"]["priced_terminal_id"] in tids)
    r = client.patch(f"{BASE}/{ids['graded']}/v6/draft", headers=headers, json={"v6": {
        "checks": {check["check_id"]: {"option_id": check["options"][0]["option_id"]}},
        "terminal_comments": {check["priced_terminal_id"]: "הערה שלי"}}})
    assert r.status_code == 200, r.text

    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                    json=_body(target, "תשובה שתוקנה"))
    assert r.status_code == 200, r.text
    out = r.json()
    assert sid in out["regraded_scope_ids"] and out["transcription_corrected"] is True
    assert out["cleared_decisions"] == 1
    new_id = out["graded_test_id"]

    rows, contract, history = asyncio.run(_read(ids))
    assert set(rows) == {ids["graded"], new_id}
    old, new = rows[ids["graded"]], rows[new_id]
    assert str(old[1]) == new_id and old[0] == "draft"                     # superseded, kept
    assert new[0] == "draft" and new[1] is None and new[3] == old[3]      # the leaf, same plan
    assert new[2] == contract["contract_version"] != old[2]              # VER-3 moved with it
    assert len(history) == 1 and history[0]["contract"]["contract_version"] == old[2]
    so = next(s for s in new[5]["scope_outcomes"]
              if (s["question_id"], s["sub_question_id"]) == (target.question_id, target.sub_question_id))
    assert so["student_answer"]["text"] == "תשובה שתוקנה"
    assert so["student_answer"]["original_text"] == target.student_answer_text
    overlay = new[5]["teacher_overrides"]["v6"]
    assert check["check_id"] not in overlay.get("checks", {})            # D5: cleared
    assert overlay["terminal_comments"][check["priced_terminal_id"]] == "הערה שלי"   # kept

    got = client.get(f"{BASE}/{ids['graded']}", headers=headers).json()
    assert got["regraded_to_id"] == new_id


def test_the_superseded_draft_is_read_only(client, world):
    ids, headers, _d, target, _c = world
    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                    json=_body(target, "תיקון"))
    assert r.status_code == 200, r.text
    old = ids["graded"]
    for resp in (client.patch(f"{BASE}/{old}/v6/draft", headers=headers, json={}),
                 client.post(f"{BASE}/{old}/approve", headers=headers, json={"overrides": {}}),
                 client.post(f"{BASE}/{old}/answers/regrade", headers=headers,
                             json=_body(target, "שוב"))):
        assert resp.status_code == 409, resp.text
        assert resp.json()["detail"]["code"] == "superseded"
        assert resp.json()["detail"]["successor_id"] == r.json()["graded_test_id"]


def test_an_unchanged_answer_is_refused(client, world):
    ids, headers, _d, target, _c = world
    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                    json=_body(target, target.student_answer_text))
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unchanged"


def test_a_failed_regrade_writes_nothing(client, world):
    ids, headers, _d, target, calls = world
    calls["fail_times"] = 10 ** 6
    before = asyncio.run(_read(ids))
    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                    json=_body(target, "תיקון שייכשל"))
    assert r.status_code == 502 and r.json()["detail"]["code"] == "regrade_failed"
    after = asyncio.run(_read(ids))
    assert after[0].keys() == before[0].keys() and after[1] == before[1] and after[2] is None


def test_a_changed_rubric_is_refused(client, world):
    ids, headers, _d, target, _c = world

    async def bump():
        from tests.api.test_batch_grading import _fresh_loop_session
        from app.models.grading import Rubric
        async with _fresh_loop_session() as db:
            row = await db.get(Rubric, uuid.UUID(ids["rubric"]))
            row.contract_version = str(uuid.uuid4())
            await db.commit()
    asyncio.run(bump())
    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                    json=_body(target, "תיקון"))
    assert r.status_code == 409 and r.json()["detail"]["code"] == "rubric_changed"


def test_it_is_owner_scoped(client, world, headers_b):
    ids, _h, _d, target, _c = world
    r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers_b,
                    json=_body(target, "תיקון"))
    assert r.status_code == 404
    assert client.post(f"{BASE}/{ids['graded']}/answers/regrade",
                       json=_body(target, "תיקון")).status_code in (401, 403)


def test_a_failed_scope_can_be_retried_without_an_edit(client, user_a, headers_a, hobby, monkeypatch):
    """D10: the same text again is a retry — allowed on a FAILED scope, and the
    transcription does not move."""
    plan, bundle = hobby
    import app.services.grader_selection as gs
    monkeypatch.setattr(gs, "build_grader_v6",
                        lambda p, c, *, gradable_test=None: _agent(p, c, pick=_full))
    failed = asyncio.run(_agent(plan, bundle.rubric_contract, fail_times=10 ** 6)
                         .grade(bundle.gradable_test))
    ids = asyncio.run(_seed(user_a["user"]["id"], failed, plan, bundle))
    try:
        target = next(s for s in bundle.gradable_test.scopes if s.student_answer_text)
        r = client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers_a,
                        json=_body(target, target.student_answer_text))
        assert r.status_code == 200, r.text
        assert r.json()["transcription_corrected"] is False
        rows, contract, history = asyncio.run(_read(ids))
        assert history is None
        new = rows[r.json()["graded_test_id"]]
        assert new[2] == contract["contract_version"] == bundle.transcription_contract.contract_version
    finally:
        asyncio.run(_cleanup(ids))


def test_the_editor_opens_on_the_raw_answer_and_names_who_shares_it(client, world):
    ids, headers, _d, target, _c = world
    params = {"question_id": target.question_id}
    if target.sub_question_id:
        params["sub_question_id"] = target.sub_question_id
    r = client.get(f"{BASE}/{ids['graded']}/answers/source", headers=headers, params=params)
    assert r.status_code == 200, r.text
    body = r.json()
    sid = target.question_id + (f".{target.sub_question_id}" if target.sub_question_id else "")
    assert body["answer_text"] == target.student_answer_text and body["original_text"] is None
    assert sid in body["shared_scope_ids"] and body["has_figures"] is False
    # after a correction the editor opens on HER text, and knows the original
    assert client.post(f"{BASE}/{ids['graded']}/answers/regrade", headers=headers,
                       json=_body(target, "מתוקן")).status_code == 200
    again = client.get(f"{BASE}/{ids['graded']}/answers/source", headers=headers, params=params).json()
    assert again["answer_text"] == "מתוקן" and again["original_text"] == target.student_answer_text
