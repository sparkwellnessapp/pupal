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
    # AN UNRENDERED EXAM IS INCLUDABLE. The download RENDERS it — the cache is
    # an optimisation, not a gate. This assertion is inverted from what it used
    # to be, and the old version was pinning the bug: the single-test preview
    # was the only writer of `returned_exam_key`, so every approved test in a
    # batch had a NULL key, every one was excluded, and the teacher was told
    # she had approved nothing.
    assert [i["student_name"] for i in body["included"]] == ["מאושר ללא רינדור"]
    assert body["excluded_unavailable"] == []

    # …and when NOTHING can actually be produced (no bucket in this test), the
    # ZIP refuses rather than streaming a valid, empty archive. That guard used
    # to come for free — a row was only included when its PDF already existed —
    # and had to become explicit once the ZIP started building them.
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

    # The ZIP now produces exams through `returned_exam_store`, so the fake has
    # to sit where the bytes are actually fetched. Patching batch_grading alone
    # silently stopped intercepting anything.
    import app.services.returned_exam_store as store

    class _FakeGCS:
        def download_bytes(self, path):
            assert key in path, f"the ZIP asked for a path it did not key: {path}"
            return b"%PDF-1.4 fake"

    monkeypatch.setattr(store, "get_gcs_service", lambda: _FakeGCS())

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


# ---------------------------------------------------------------------------
# OD-1 (owner-ruled 2026-09-04) — PATCH …/stamp_position
#
# The gap these close: §4.3 P3 lets the teacher drag the stamp on the
# returned-exam preview, which renders APPROVED tests only; the only endpoint
# that wrote stamp_position refused anything that was not a draft. The two
# status guards were disjoint, so the drag had nowhere to go.
#
# Every overlay below is written by the REAL ENDPOINT, never hand-built — the
# hand-built overlay is what let the dead key ship.
# ---------------------------------------------------------------------------

def _patch_stamp(client, headers, gid, payload):
    return client.patch(
        f"/api/v0/grading/graded_test/{gid}/stamp_position",
        json=payload, headers=headers)


def _stored_stamp(gid):
    """Read the position back out of the row, through the production key."""
    import asyncio as _asyncio
    from app.models.grading import GradedTest
    from app.services.returned_exam import OVERLAY_KEY

    async def _read():
        async with _session() as db:
            row = await db.get(GradedTest, uuid.UUID(gid))
            return ((row.draft_json or {}).get(OVERLAY_KEY, {}).get("stamp_position"),
                    row.returned_exam_key)

    return _asyncio.run(_read())


def _approved_test(user_a, rubric_a, student_a, *, status="approved",
                   returned_exam_key=None):
    import asyncio
    user_id, rubric_id = user_a["user"]["id"], rubric_a["rubric_id"]
    batch_id = asyncio.run(_insert_batch(user_id, rubric_id))
    gid = asyncio.run(_insert_graded_test(
        user_id, rubric_id, batch_id, student_a["id"],
        status=status, student_name="דן בסיוק",
        returned_exam_key=returned_exam_key))
    return batch_id, gid


@pytest.mark.integration
def test_stamp_set_on_an_approved_exam_reaches_the_pdf(
        client, headers_a, user_a, rubric_a, student_a):
    """THE definition of done: a position the teacher sets on an APPROVED exam
    round-trips into the render, through the real endpoint."""
    _batch, gid = _approved_test(user_a, rubric_a, student_a,
                                 returned_exam_key="stale-key-from-an-earlier-render")

    resp = _patch_stamp(client, headers_a, gid,
                        {"stamp_position": {"corner": "br", "source": "auto"}})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["stamp_position"]["corner"] == "br"
    # the SERVER decides `source` — a client-sent "auto" would make her own
    # placement erasable by a later «apply to all»
    assert body["stamp_position"]["source"] == "manual", (
        "the server trusted the client's `source`")
    assert body["returned_exam_state"] == "stale"

    stored, cache_key = _stored_stamp(gid)
    assert stored is not None and stored["corner"] == "br", (
        "the position did not persist under the key production reads")
    assert stored["source"] == "manual"
    assert cache_key is None, (
        "the cached render survived a stamp move — the next fetch would serve "
        "a page showing a position she moved away from")


@pytest.mark.integration
def test_the_stamp_endpoint_accepts_a_draft_row_too(
        client, headers_a, user_a, rubric_a, student_a):
    """A draft is the other legal state — she may place the stamp before
    signing, and P3 is reachable from the review screen as well."""
    _batch, gid = _approved_test(user_a, rubric_a, student_a, status="draft")
    resp = _patch_stamp(client, headers_a, gid,
                        {"stamp_position": {"corner": "tl"}})
    assert resp.status_code == 200, resp.text


@pytest.mark.integration
def test_a_null_position_clears_it_back_to_the_batch_default(
        client, headers_a, user_a, rubric_a, student_a):
    """Clearing is a real operation: it is how she undoes a drag and lets the
    test inherit whatever the batch default becomes."""
    _batch, gid = _approved_test(user_a, rubric_a, student_a)
    assert _patch_stamp(client, headers_a, gid,
                        {"stamp_position": {"corner": "br"}}).status_code == 200

    resp = _patch_stamp(client, headers_a, gid, {"stamp_position": None})
    assert resp.status_code == 200, resp.text
    assert resp.json()["stamp_position"] is None
    assert _stored_stamp(gid)[0] is None


@pytest.mark.integration
def test_the_stamp_endpoint_does_not_extend_the_revision_chain(
        client, headers_a, user_a, rubric_a, student_a):
    """Moving a stamp must not mint a version. Routing this through
    `manual_edit` would un-sign the exam for a cosmetic change — she would have
    to re-approve because she nudged a stamp."""
    import asyncio
    from app.models.grading import GradedTest

    _batch, gid = _approved_test(user_a, rubric_a, student_a)
    _patch_stamp(client, headers_a, gid, {"stamp_position": {"corner": "tr"}})

    async def _row():
        async with _session() as db:
            row = await db.get(GradedTest, uuid.UUID(gid))
            return row.status, row.regraded_to_id

    status, regraded_to = asyncio.run(_row())
    assert status == "approved", "the exam was un-signed by a stamp move"
    assert regraded_to is None, "a stamp move extended the chain"


@pytest.mark.integration
def test_the_stamp_endpoint_is_owner_scoped(
        client, headers_b, user_a, rubric_a, student_a):
    """404, never 403 — 403 leaks existence (§9)."""
    _batch, gid = _approved_test(user_a, rubric_a, student_a)
    resp = _patch_stamp(client, headers_b, gid,
                        {"stamp_position": {"corner": "tl"}})
    assert resp.status_code == 404, resp.status_code


# NOTE — there is deliberately NO test that a `failed` row is refused. The
# CHECK constraint `graded_tests_status_consistency` forbids a failed row from
# carrying draft_json at all, so such a row cannot be constructed to test
# against. The database is the guard there, and the endpoint's own
# `if not row.draft_json` covers the shape that reaches it.


# ---------------------------------------------------------------------------
# Phase A/B code review — the three things the first pass missed
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_stamp_state_is_none_when_there_was_no_render_to_invalidate(
        client, headers_a, user_a, rubric_a, student_a):
    """[review F-1] The endpoint used to answer "stale" unconditionally.

    On an exam nobody has rendered, that is a lie — and not a harmless one: the
    frontend drives P8's re-sign banner off this state, so it would ask her to
    re-sign something that was never rendered. `stale` means "a render exists
    and no longer matches"; with no key there is no render.
    """
    _batch, never = _approved_test(user_a, rubric_a, student_a,
                                   returned_exam_key=None)
    resp = _patch_stamp(client, headers_a, never,
                        {"stamp_position": {"corner": "tl"}})
    assert resp.status_code == 200, resp.text
    assert resp.json()["returned_exam_state"] == "none", (
        "an exam with no cached render was reported stale")

    _batch2, rendered = _approved_test(user_a, rubric_a, student_a,
                                       returned_exam_key="a-real-earlier-render")
    resp = _patch_stamp(client, headers_a, rendered,
                        {"stamp_position": {"corner": "tl"}})
    assert resp.json()["returned_exam_state"] == "stale", (
        "a cached render was invalidated without saying so")


@pytest.mark.integration
def test_stamp_set_on_an_approved_exam_reaches_the_batch_zip(
        client, headers_a, user_a, rubric_a, student_a):
    """[review F-2] The DoD's second half, which the first pass did not cover.

    The ZIP is the OTHER reader of the stamp (`batch_grading.py`), and it was
    reading the same dead key. This drives the real endpoint and then asserts
    the archive addresses the object keyed for HER position — if the ZIP still
    read `None`, it would ask GCS for a different path and the student would
    receive an exam stamped somewhere she did not put it.
    """
    import asyncio
    import zipfile
    from io import BytesIO

    from app.schemas.graded_test_contract import GradedTestContract
    from app.schemas.graded_test_draft import StampPosition
    from app.services import returned_exam as rex

    _batch, gid = _approved_test(user_a, rubric_a, student_a)
    batch_id = _batch

    # she drags the stamp — through the REAL endpoint
    assert _patch_stamp(client, headers_a, gid,
                        {"stamp_position": {"corner": "br"}}).status_code == 200

    # the key the ZIP must now compute: the contract PLUS her position
    async def _key_and_mark():
        from app.models.grading import GradedTest
        async with _session() as db:
            row = await db.get(GradedTest, uuid.UUID(gid))
            contract = GradedTestContract.model_validate(row.contract_json)
            stamped = rex.current_cache_key(
                contract,
                StampPosition(corner="br", source="manual").model_dump(mode="json"),
                False)
            unstamped = rex.current_cache_key(contract, None, False)
            row.returned_exam_key = stamped          # as a fresh render would
            await db.commit()
            return stamped, unstamped

    stamped_key, unstamped_key = asyncio.run(_key_and_mark())
    assert stamped_key != unstamped_key, (
        "the stamp is not in the cache key — this test proves nothing")

    import app.services.returned_exam_store as store

    asked = []

    class _FakeGCS:
        def download_bytes(self, path):
            asked.append(path)
            return b"%PDF-1.4 fake"

    bg_original = store.get_gcs_service
    store.get_gcs_service = lambda: _FakeGCS()
    try:
        r = client.get(f"/api/v0/batches/{batch_id}/returned-exams.zip", headers=headers_a)
        assert r.status_code == 200, r.text
        names = zipfile.ZipFile(BytesIO(r.content)).namelist()
        assert names, "the stamped exam was excluded from the archive"
    finally:
        store.get_gcs_service = bg_original

    assert asked, "the ZIP fetched nothing"
    assert any(stamped_key in p for p in asked), (
        f"the ZIP addressed {asked} — none carries the key for HER stamp "
        f"({stamped_key}). The archive is reading a stamp position she did not set.")


@pytest.mark.integration
def test_apply_to_all_reports_a_count_that_is_true(
        client, headers_a, user_a, rubric_a, student_a):
    """[review F-3] Finding B's SECOND half, which nothing covered.

    `stamp_applied_count` is not just a number on a response: `rename_batch`
    feeds it into `settings_changed`, which is what drops `returned_exam_key`.
    So while the key was dead the count was 0 AND «apply to all» never
    invalidated a single cached render — a batch-default change could leave
    already-rendered exams serving the old stamp forever.
    """
    import asyncio

    batch_id = asyncio.run(_insert_batch(user_a["user"]["id"], rubric_a["rubric_id"]))
    auto_id = asyncio.run(_insert_graded_test(
        user_a["user"]["id"], rubric_a["rubric_id"], batch_id, student_a["id"],
        status="approved", student_name="אוטומטי", stamp_source="auto",
        returned_exam_key="rendered-under-the-old-stamp"))

    r = client.patch(
        f"/api/v0/batches/{batch_id}",
        json={"stamp_position_default": {"corner": "br", "source": "manual"}},
        headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.json()["stamp_applied_count"] == 1, (
        "the count is back to reporting 0 — the overlay key is dead again")
    assert r.json()["invalidated_count"] >= 1, (
        "«apply to all» cleared a position but left the render cached under it")

    async def _key():
        from app.models.grading import GradedTest
        async with _session() as db:
            row = await db.get(GradedTest, uuid.UUID(auto_id))
            return row.returned_exam_key

    assert asyncio.run(_key()) is None, (
        "the exam still addresses a render made under the stamp that was just "
        "cleared — it would be served, and it would look entirely correct")
