"""
identity.py — the student-name identity pass (plumbing; model behavior was
probe-validated live 2026-08-12: 5/5 handwritten Hebrew names + filename
fallback + null on scanner junk).

Pinned here: crop geometry, fence-tolerant parsing, the never-raises
isolation contract, and the null/blank handling. FakeProvider only — never
call a real VLM in tests.
"""
import asyncio
import json
from unittest.mock import patch

from PIL import Image

from app.services.transcription.identity import (
    CROP_FRACTION,
    IDENTITY_SCHEMA,
    crop_top,
    extract_student_name,
)
from app.services.transcription.providers.fake import FakeProvider


def _run(coro):
    return asyncio.run(coro)


def _patch_render():
    return patch(
        "app.services.transcription.identity.render_pdf_page",
        return_value=Image.new("RGB", (800, 1000), "white"),
    )


def _extract(provider):
    with _patch_render():
        return _run(extract_student_name(b"%PDF", "din_ezra.pdf", provider))


def test_crop_top_geometry():
    img = Image.new("RGB", (800, 1000), "white")
    c = crop_top(img)
    assert c.size == (800, int(1000 * CROP_FRACTION))
    assert crop_top(img, 0.5).size == (800, 500)


def test_happy_path_name_extracted_and_call_shape():
    fake = FakeProvider(script=[FakeProvider.ok(
        json.dumps({"student_name": "דין עזרא", "source": "handwriting"},
                   ensure_ascii=False))])
    assert _extract(fake) == "דין עזרא"
    call = fake.calls[0]
    assert call.n_images == 1                       # the header crop
    assert call.json_schema == IDENTITY_SCHEMA
    assert "din_ezra.pdf" in call.user              # filename fallback context


def test_fenced_json_is_tolerated():
    fake = FakeProvider(script=[FakeProvider.ok(
        '```json\n{"student_name": "דן בסיוק", "source": "handwriting"}\n```')])
    assert _extract(fake) == "דן בסיוק"


def test_null_and_blank_names_yield_none():
    for payload in ('{"student_name": null, "source": null}',
                    '{"student_name": "   ", "source": "filename"}',
                    'not json at all'):
        fake = FakeProvider(script=[FakeProvider.ok(payload)])
        assert _extract(fake) is None


def _extract_scheduled(provider):
    """Through a real ProviderScheduler — the production path (shared cap +
    scheduler-owned transport retry)."""
    from app.services.transcription.scheduler import (
        ProviderLimit, ProviderScheduler,
    )
    sched = ProviderScheduler({"eyes": ProviderLimit()})
    with _patch_render():
        return _run(extract_student_name(
            b"%PDF", "din_ezra.pdf", provider,
            scheduler=sched, provider_key="eyes", doc_priority=0))

def test_scheduler_path_transient_failure_retried_once_then_succeeds():
    from app.services.transcription.vlm_provider import ErrorKind, VLMCallError
    fake = FakeProvider(script=[
        VLMCallError(ErrorKind.TIMEOUT, "flap", provider="fake"),
        FakeProvider.ok('{"student_name": "דין עזרא", "source": "handwriting"}'),
    ])
    assert _extract_scheduled(fake) == "דין עזרא"
    assert len(fake.calls) == 2                     # the scheduler's one retry

def test_scheduler_path_provider_failure_never_raises():
    from app.services.transcription.vlm_provider import ErrorKind, VLMCallError
    fake = FakeProvider(script=[VLMCallError(
        ErrorKind.TRANSIENT, "boom", provider="fake")])
    assert _extract_scheduled(fake) is None         # isolation contract
    assert len(fake.calls) == 2                     # retried once, then gave up

def test_direct_path_failure_never_raises_and_never_retries():
    from app.services.transcription.vlm_provider import ErrorKind, VLMCallError
    fake = FakeProvider(script=[VLMCallError(
        ErrorKind.BAD_REQUEST, "our bug", provider="fake")])
    assert _extract(fake) is None
    assert len(fake.calls) == 1                     # no scheduler => no retry


def test_render_failure_never_raises():
    fake = FakeProvider()
    with patch("app.services.transcription.identity.render_pdf_page",
               side_effect=ValueError("no pages")):
        assert _run(extract_student_name(b"junk", "x.pdf", fake)) is None
    assert fake.calls == []                         # never reached the provider


def test_timeout_budget_covers_two_scheduler_attempts():
    # 2026-08-12: identity died at CALL_TIMEOUT=30s on a congested uplink
    # (both attempts, both docs) while patient P1 calls landed. The invariant
    # worth pinning is BUDGET COHERENCE, not the magic numbers: the total
    # ceiling must fit two full call attempts plus the scheduler's retry
    # delay and queue headroom, or the second attempt is theater.
    from app.services.transcription.identity import CALL_TIMEOUT_S, TOTAL_TIMEOUT_S
    assert CALL_TIMEOUT_S >= 60.0          # patience floor (weak-uplink doctrine)
    assert TOTAL_TIMEOUT_S >= 2 * CALL_TIMEOUT_S + 10.0
