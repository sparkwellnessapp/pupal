"""[grader-v6 MVC, owner rulings 2026-10-17 §7] the v6 review endpoints, end to end through
the app with real users and real Bearer tokens (§9: never fake the auth dependency):

  GET   /api/v0/grading/graded_test/{id}/v6        owner-scoped; another teacher's id → 404
  PATCH /api/v0/grading/graded_test/{id}/v6/draft  MERGE (A-3: stamp_position survives), gated
  POST  /api/v0/grading/graded_test/{id}/approve   the v6 branch: the one pricer, v6 frozen

The draft is a REAL v6 draft (the v6 grader on the scripted model), the rubric row carries
the hobby contract it was graded against."""
from __future__ import annotations

import asyncio
import uuid

import pytest

from tests.api.test_graded_test_approval import _delete_graded_test_row, _insert_draft_row
from tests.services.test_v6_review_mvc import _grade

BASE = "/api/v0/grading/graded_test"


async def _insert_rubric(user_id: str, contract) -> str:
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import Rubric
    async with _fresh_loop_session() as db:
        rid = uuid.uuid4()
        db.add(Rubric(id=rid, user_id=uuid.UUID(user_id), name="v6 hobby",
                      subject="computer_science", total_points=float(contract.total_points),
                      contract_json=contract.model_dump(mode="json"),
                      contract_version=str(contract.contract_version)))
        await db.commit()
        return str(rid)


async def _delete_rubric(rid: str) -> None:
    """The graded test is gone already; its stub transcription still names the rubric."""
    from sqlalchemy import delete
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import GradedTest, Rubric
    from app.models.transcription import Transcription
    async with _fresh_loop_session() as db:
        key = uuid.UUID(rid)
        await db.execute(delete(GradedTest).where(GradedTest.rubric_id == key))
        await db.execute(delete(Transcription).where(Transcription.rubric_id == key))
        await db.execute(delete(Rubric).where(Rubric.id == key))
        await db.commit()


async def _set_stamp(gid: str) -> None:
    from tests.api.test_batch_grading import _fresh_loop_session
    from app.models.grading import GradedTest
    async with _fresh_loop_session() as db:
        row = await db.get(GradedTest, uuid.UUID(gid))
        doc = dict(row.draft_json)
        doc["teacher_overrides"] = {**doc.get("teacher_overrides", {}),
                                    "stamp_position": {"corner": "tl", "source": "manual"}}
        row.draft_json = doc
        await db.commit()


@pytest.fixture(scope="module")
def v6_draft():
    return _grade()


@pytest.fixture
def v6_row(client, user_a, headers_a, v6_draft):
    draft, bundle = v6_draft
    rid = asyncio.run(_insert_rubric(user_a["user"]["id"], bundle.rubric_contract))
    gid = asyncio.run(_insert_draft_row(user_a["user"]["id"], rid, draft.model_dump(mode="json")))
    yield gid, headers_a, draft
    asyncio.run(_delete_graded_test_row(gid))
    asyncio.run(_delete_rubric(rid))


def _ladder(body):
    return next(c["plan"] for c in body["content"]["checks"]
                if c["plan"]["role"] == "credit" and len(c["plan"]["options"]) > 2)


def test_get_v6_is_the_review_model(client, v6_row):
    gid, headers, draft = v6_row
    r = client.get(f"{BASE}/{gid}/v6", headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["content"]["plan_hash"] == draft.v6["plan_hash"]
    assert body["priced"]["total_score"] == body["ai_total_score"]          # no decision yet
    assert body["lines"] and body["undecided_check_ids"] == []


def test_v6_endpoints_are_owner_scoped(client, v6_row, headers_b):
    gid, _h, _d = v6_row
    assert client.get(f"{BASE}/{gid}/v6", headers=headers_b).status_code == 404
    assert client.patch(f"{BASE}/{gid}/v6/draft", json={}, headers=headers_b).status_code == 404
    assert client.get(f"{BASE}/{gid}/v6").status_code in (401, 403)


def test_patch_merges_and_keeps_the_stamp(client, v6_row):
    gid, headers, _d = v6_row
    asyncio.run(_set_stamp(gid))
    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    credits = [c["plan"] for c in body["content"]["checks"] if c["plan"]["role"] == "credit"]
    a, b = credits[0], credits[1]
    r1 = client.patch(f"{BASE}/{gid}/v6/draft", headers=headers, json={
        "v6": {"checks": {a["check_id"]: {"option_id": a["options"][-1]["option_id"]}}}})
    assert r1.status_code == 200, r1.text
    r2 = client.patch(f"{BASE}/{gid}/v6/draft", headers=headers, json={
        "v6": {"checks": {b["check_id"]: {"comment": "הערה שלי"}}}})
    assert r2.status_code == 200, r2.text
    body = r2.json()                                    # the response body, not a draft
    assert body["overlay"]["checks"][a["check_id"]]["option_id"] == a["options"][-1]["option_id"]
    assert body["overlay"]["checks"][b["check_id"]]["comment"] == "הערה שלי"
    assert body["overrides"]["stamp_position"]["corner"] == "tl"            # A-3: merged, never replaced
    line = {x["terminal_id"]: x for x in body["lines"]}[a["priced_terminal_id"]]
    assert line["source"] in ("fallback", "teacher_override")              # her edit: no model line


def test_patch_refuses_an_option_outside_the_check(client, v6_row):
    gid, headers, _d = v6_row
    plan = _ladder(client.get(f"{BASE}/{gid}/v6", headers=headers).json())
    r = client.patch(f"{BASE}/{gid}/v6/draft", headers=headers,
                     json={"v6": {"checks": {plan["check_id"]: {"option_id": "nope"}}}})
    assert r.status_code == 422
    assert r.json()["detail"]["gate_violations"][0]["kind"] == "closed_world"


def test_approve_freezes_the_v6_contract(client, v6_row):
    gid, headers, draft = v6_row
    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    plan = _ladder(body)
    out = client.patch(f"{BASE}/{gid}/v6/draft", headers=headers, json={
        "v6": {"checks": {plan["check_id"]: {"option_id": plan["options"][1]["option_id"]}}}}).json()
    r = client.post(f"{BASE}/{gid}/approve", headers=headers,
                    json={"overrides": out["overrides"], "client_total": out["priced"]["total_score"]})
    assert r.status_code == 200, r.text
    contract = r.json()["contract"]
    assert contract["v6"]["plan_hash"] == draft.v6["plan_hash"]
    assert contract["total_score"] == out["priced"]["total_score"]
    frozen = {c["check_id"]: c for c in contract["v6"]["checks"]}
    assert frozen[plan["check_id"]]["effective_option_id"] == plan["options"][1]["option_id"]
    assert client.get(f"{BASE}/{gid}/v6", headers=headers).json()["status"] == "approved"


# ── feedback: stale after her decisions, rewritten from them ─────────────────

@pytest.fixture
def v6_row_with_feedback(client, user_a, headers_a, v6_draft):
    from app.agents.feedback.inputs import feedback_inputs
    from app.schemas.graded_test_draft import FeedbackBlock, FeedbackText
    draft, bundle = v6_draft
    draft = draft.model_copy(update={"feedback": FeedbackBlock(
        scopes={i.scope_id: FeedbackText(text="משוב מקורי", basis_hash=i.basis)
                for i in feedback_inputs(draft, None)},
        summary=FeedbackText(text="סיכום"), model_version="m", prompt_version="p")})
    rid = asyncio.run(_insert_rubric(user_a["user"]["id"], bundle.rubric_contract))
    gid = asyncio.run(_insert_draft_row(user_a["user"]["id"], rid, draft.model_dump(mode="json")))
    yield gid, headers_a, draft
    asyncio.run(_delete_graded_test_row(gid))
    asyncio.run(_delete_rubric(rid))


def _fake_feedback_model(monkeypatch, sent: list, text: str = "משוב חדש"):
    from app.agents.feedback.schemas import FeedbackResponse, ScopeFeedback
    from app.config import settings

    class _Runner:
        async def ainvoke(self, messages):
            sent.append(messages[-1].content)
            ids = [line.split(" ", 1)[1] for line in messages[-1].content.splitlines()
                   if line.startswith("סעיף ")]
            return FeedbackResponse(scopes=[ScopeFeedback(scope_id=s, text=text) for s in ids],
                                    summary="סיכום חדש")

    class _LLM:
        def with_structured_output(self, _schema, include_raw=False):
            return _Runner()

    monkeypatch.setattr(settings, "feedback_model_key", "fake-model", raising=False)
    monkeypatch.setattr("app.agents.feedback.runner.build_feedback_model", lambda: _LLM())


def _flip_ladder(client, gid, headers):
    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    plan = _ladder(body)
    vt = next(t for t in body["content"]["view_terminals"]
              if t["terminal_id"] == plan["priced_terminal_id"])
    scope = vt["question_id"] if not vt.get("sub_question_id") else f"{vt['question_id']}.{vt['sub_question_id']}"
    out = client.patch(f"{BASE}/{gid}/v6/draft", headers=headers, json={
        "v6": {"checks": {plan["check_id"]: {"option_id": plan["options"][1]["option_id"]}}}})
    assert out.status_code == 200, out.text
    return out.json(), scope, plan


def test_a_decision_makes_its_feedback_stale_and_a_rewrite_describes_it(client, v6_row_with_feedback,
                                                                       monkeypatch):
    gid, headers, _d = v6_row_with_feedback
    assert client.get(f"{BASE}/{gid}/v6", headers=headers).json()["stale_feedback_scope_ids"] == []
    out, scope, plan = _flip_ladder(client, gid, headers)
    assert out["stale_feedback_scope_ids"] == [scope]

    sent: list = []
    _fake_feedback_model(monkeypatch, sent)
    r = client.post(f"{BASE}/{gid}/feedback/regenerate", params={"target": scope}, headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == {"target": scope, "text": "משוב חדש", "offered_only": False, "stale": False}
    # ONE scope asked for, described under HER decision — never «no checks»
    assert len(sent) == 1 and sent[0].count("סעיף ") == 1
    assert f"[{plan['options'][1]['label_he']}] {plan['description_he']}" in sent[0]
    assert "אין בדיקות לסעיף זה" not in sent[0]

    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    assert body["stale_feedback_scope_ids"] == []
    assert body["feedback"]["scopes"][scope]["text"] == "משוב חדש"
    # her decision survived the rewrite's write
    assert body["overlay"]["checks"][plan["check_id"]]["option_id"] == plan["options"][1]["option_id"]


def test_a_rewrite_never_replaces_her_words(client, v6_row_with_feedback, monkeypatch):
    gid, headers, _d = v6_row_with_feedback
    _out, scope, _plan = _flip_ladder(client, gid, headers)
    assert client.patch(f"{BASE}/{gid}/v6/draft", headers=headers,
                        json={"feedback": {scope: "המשוב שלי"}}).status_code == 200
    _fake_feedback_model(monkeypatch, [])
    r = client.post(f"{BASE}/{gid}/feedback/regenerate", params={"target": scope}, headers=headers)
    assert r.status_code == 200 and r.json()["offered_only"] is True
    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    assert body["overrides"]["feedback"][scope] == "המשוב שלי"
    assert body["feedback"]["scopes"][scope]["text"] == "משוב מקורי"


def test_a_rewrite_of_the_summary_fills_a_scope_that_has_no_text(client, v6_row, monkeypatch):
    """Feedback failed at grade time (no block at all): «נסי שוב» on the summary
    writes the whole test, stamped, and nothing is stale afterwards."""
    gid, headers, _d = v6_row
    assert client.get(f"{BASE}/{gid}/v6", headers=headers).json()["feedback"] is None
    _fake_feedback_model(monkeypatch, [])
    r = client.post(f"{BASE}/{gid}/feedback/regenerate", params={"target": "summary"}, headers=headers)
    assert r.status_code == 200, r.text
    body = client.get(f"{BASE}/{gid}/v6", headers=headers).json()
    assert body["feedback"]["summary"]["text"] == "סיכום חדש"
    assert body["feedback"]["scopes"] and all(
        t["text"] == "משוב חדש" for t in body["feedback"]["scopes"].values())
    assert body["stale_feedback_scope_ids"] == []
