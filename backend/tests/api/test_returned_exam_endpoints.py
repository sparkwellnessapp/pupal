"""
PR-G9 — the returned-exam endpoints: per-batch settings, manifest, ZIP.

These are the three named tests that need real rows: the pure decision logic
they exercise lives in `app/services/returned_exam.py` and is tested with zero
mocks in `tests/services/test_returned_exam.py`. What is proved HERE is that
the endpoints are wired to that logic, under real auth and real ownership.
"""
from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest


# ---------------------------------------------------------------------------
# row helpers (same shape as test_batch_grading.py's)
# ---------------------------------------------------------------------------

@asynccontextmanager
async def _session():
    from app.database import AsyncSessionLocal, engine

    await engine.dispose(close=False)
    try:
        async with AsyncSessionLocal() as db:
            yield db
    finally:
        await engine.dispose(close=False)


async def _insert_batch(user_id: str, rubric_id: str) -> str:
    from app.models.grading import GradingBatch

    async with _session() as db:
        batch = GradingBatch(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            rubric_contract_version="test-v1", name="מבחן 1",
            status="in_progress", test_count=2,
            started_at=datetime.now(timezone.utc))
        db.add(batch)
        await db.commit()
        return str(batch.id)


async def _insert_transcription(user_id: str, rubric_id: str, batch_id: str) -> str:
    """`graded_tests.transcription_id` is NOT NULL — a grade without a scan it
    came from is not a thing this schema allows, and the test must not pretend
    otherwise."""
    from app.models.transcription import Transcription

    async with _session() as db:
        t = Transcription(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            batch_id=uuid.UUID(batch_id),
            gcs_uri="gs://test-bucket/x.pdf", gcs_bucket="test-bucket",
            gcs_object_path="tests/x.pdf", filename="x.pdf",
            draft_json={"student_name_suggestion": None, "page_count": 1,
                        "answers": [], "annotations": []},
            status="transcribed")
        db.add(t)
        await db.commit()
        return str(t.id)


async def _insert_graded_test(user_id, rubric_id, batch_id, student_id, *,
                              status, student_name, stamp_source=None,
                              returned_exam_key=None) -> str:
    """A graded test with just enough shape for these endpoints.

    `contract_json` stays None for non-approved rows — the CHECK constraint
    requires draft+contract+approved_at together, and this suite must not
    invent a row shape the database would refuse.
    """
    from app.models.grading import GradedTest

    # The overlay goes through the REAL schema and the REAL key. It used to be
    # hand-written under "overrides" — a key nothing writes — so this suite
    # passed while every stamp reader in production looked somewhere else. A
    # fixture the test constructs rather than the code under test validates
    # nothing, and that is exactly how the dead key shipped.
    from app.schemas.graded_test_draft import GradedTestOverrides, StampPosition
    from app.services.returned_exam import OVERLAY_KEY

    overlay = GradedTestOverrides(
        stamp_position=(None if stamp_source is None
                        else StampPosition(corner="tl", source=stamp_source)))
    draft = {
        "rubric_contract_version": "rc", "transcription_contract_version": "tc",
        "model_version": "m", "prompt_version": "p", "plan_version": None,
        "scope_outcomes": [], "llm_calls_count": 1, "grading_duration_ms": 1,
        "total_input_tokens": 1, "total_output_tokens": 1,
        OVERLAY_KEY: json.loads(overlay.model_dump_json()),
    }
    contract = None
    approved_at = None
    if status == "approved":
        contract = {
            "contract_version": str(uuid.uuid4()),
            "rubric_contract_version": "rc",
            "transcription_contract_version": "tc",
            "model_version": "m", "prompt_version": "p",
            "total_score": "0", "total_possible": "0",
            "percentage": "0", "scope_outcomes": [],
            "approved_at": datetime.now(timezone.utc).isoformat(),
        }
        approved_at = datetime.now(timezone.utc)

    transcription_id = await _insert_transcription(user_id, rubric_id, batch_id)
    async with _session() as db:
        row = GradedTest(
            user_id=uuid.UUID(user_id), rubric_id=uuid.UUID(rubric_id),
            batch_id=uuid.UUID(batch_id),
            transcription_id=uuid.UUID(transcription_id),
            student_id=uuid.UUID(student_id),
            rubric_contract_version="rc", status=status,
            student_name=student_name, draft_json=draft,
            contract_json=contract, approved_at=approved_at,
            returned_exam_key=returned_exam_key)
        db.add(row)
        await db.commit()
        return str(row.id)


# ---------------------------------------------------------------------------
# appendix-toggle-per-batch
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_appendix_toggle_is_per_batch_and_invalidates_cached_pdfs(
        client, headers_a, user_a, rubric_a, student_a):
    """The criteria toggle changes what the appendix SHOWS, so every cached PDF
    in the batch is now a document the teacher did not choose. The endpoint
    clears those keys and reports the count — silently serving the old page is
    the one outcome this feature cannot have."""
    import asyncio

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="approved",
        student_name="דן", returned_exam_key="stale-key-1"))
    asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="draft",
        student_name="דין", returned_exam_key=None))

    r = client.patch(f"/api/v0/batches/{batch_id}",
                     json={"appendix_include_criteria": True},
                     headers=headers_a)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["appendix_include_criteria"] is True
    assert body["invalidated_count"] == 1, (
        "the cached PDF rendered without criteria was left addressable")
    assert body["name"] == "מבחן 1", "the toggle clobbered the batch name"

    # idempotent: setting the same value again invalidates nothing
    again = client.patch(f"/api/v0/batches/{batch_id}",
                         json={"appendix_include_criteria": True},
                         headers=headers_a)
    assert again.json()["invalidated_count"] == 0, (
        "a no-op write re-rendered every exam in the batch")


# ---------------------------------------------------------------------------
# stamp-apply-to-batch-writes-default-not-manual-overrides
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_apply_stamp_to_batch_clears_auto_positions_but_not_manual(
        client, headers_a, user_a, rubric_a, student_a):
    """«Apply to all» writes the batch default and clears the picker's guesses.
    A position the teacher dragged herself is a decision, and the endpoint must
    not undo it — she would have no way to see that it happened."""
    import asyncio

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    auto_id = asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="draft",
        student_name="אוטומטי", stamp_source="auto"))
    manual_id = asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="draft",
        student_name="ידני", stamp_source="manual"))

    r = client.patch(
        f"/api/v0/batches/{batch_id}",
        json={"stamp_position_default": {"corner": "br", "source": "manual"}},
        headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.json()["stamp_position_default"]["corner"] == "br"
    assert r.json()["stamp_applied_count"] == 1, (
        "exactly one auto position should have been cleared")

    async def _positions():
        from app.models.grading import GradedTest
        async with _session() as db:
            out = {}
            for gid in (auto_id, manual_id):
                row = await db.get(GradedTest, uuid.UUID(gid))
                from app.services.returned_exam import OVERLAY_KEY
                out[gid] = (row.draft_json or {}).get(
                    OVERLAY_KEY, {}).get("stamp_position")
            return out

    positions = asyncio.run(_positions())
    assert positions[auto_id] is None, "the auto position was not cleared"
    assert positions[manual_id] is not None, (
        "«apply to all» erased the position the teacher placed herself")
    assert positions[manual_id]["corner"] == "tl"


# ---------------------------------------------------------------------------
# zip-approved-only-with-manifest
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_manifest_lists_approved_only_and_names_each_exclusion(
        client, headers_a, user_a, rubric_a, student_a):
    """The manifest is the contract for what the download contains. Exclusions
    are ENUMERATED — a teacher who downloads 1 of 3 must be able to see which
    two are missing and why, or she hands back a class set with holes in it."""
    import asyncio

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="draft",
        student_name="טיוטה"))
    asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="approved",
        student_name="מאושר ללא רינדור", returned_exam_key=None))

    r = client.get(f"/api/v0/batches/{batch_id}/returned-exams/manifest",
                   headers=headers_a)
    assert r.status_code == 200, r.text
    body = r.json()

    assert [i["student_name"] for i in body["excluded_not_approved"]] == ["טיוטה"]
    assert [i["student_name"] for i in body["excluded_stale"]] == \
        ["מאושר ללא רינדור"], "an unrendered exam was reported as downloadable"
    assert body["included"] == []

    # …and the ZIP refuses rather than shipping an empty archive that looks fine
    z = client.get(f"/api/v0/batches/{batch_id}/returned-exams.zip",
                   headers=headers_a)
    assert z.status_code == 404, (
        "an empty archive would read as «these students have no feedback»")


@pytest.mark.integration
def test_zip_contains_approved_current_exams_only(
        client, headers_a, user_a, rubric_a, student_a, monkeypatch):
    """The archive holds exactly what the manifest promised.

    The GCS read is faked (no bucket in tests); everything that decides WHICH
    exams go in — approval, key freshness, ownership — is the real code path.
    """
    import asyncio
    import zipfile
    from io import BytesIO

    from app.schemas.graded_test_contract import GradedTestContract
    from app.services import returned_exam as rex

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    fresh_id = asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="approved", student_name="דן בסיוק"))
    asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id,
        student_a["id"], status="draft", student_name="לא אושר"))

    # stamp the fresh row with the key the endpoint will compute for it
    async def _make_current():
        from app.models.grading import GradedTest
        async with _session() as db:
            row = await db.get(GradedTest, uuid.UUID(fresh_id))
            contract = GradedTestContract.model_validate(row.contract_json)
            row.returned_exam_key = rex.current_cache_key(contract, None, False)
            await db.commit()
            return row.returned_exam_key

    key = asyncio.run(_make_current())

    import app.api.v0.batch_grading as bg

    class _FakeGCS:
        def download_bytes(self, path):
            assert key in path, f"the ZIP asked for a path it did not key: {path}"
            return b"%PDF-1.4 fake"

    monkeypatch.setattr(bg, "get_gcs_service", lambda: _FakeGCS())

    manifest = client.get(
        f"/api/v0/batches/{batch_id}/returned-exams/manifest",
        headers=headers_a).json()
    assert [i["student_name"] for i in manifest["included"]] == ["דן בסיוק"]

    r = client.get(f"/api/v0/batches/{batch_id}/returned-exams.zip",
                   headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip"

    names = zipfile.ZipFile(BytesIO(r.content)).namelist()
    assert len(names) == 1, f"the archive holds more than the manifest promised: {names}"
    assert "דן בסיוק" in names[0] and names[0].endswith("_מוחזר.pdf")
    assert "לא אושר" not in " ".join(names), (
        "an unapproved test was handed to a student")


@pytest.mark.integration
def test_returned_exam_endpoints_are_owner_scoped(
        client, headers_b, user_a, rubric_a):
    """Cross-tenant reads are 404, not 403 (§9) — 403 leaks existence."""
    import asyncio

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    for path in (f"/api/v0/batches/{batch_id}/returned-exams/manifest",
                 f"/api/v0/batches/{batch_id}/returned-exams.zip"):
        assert client.get(path, headers=headers_b).status_code == 404, path
    assert client.patch(f"/api/v0/batches/{batch_id}",
                        json={"appendix_include_criteria": True},
                        headers=headers_b).status_code == 404
