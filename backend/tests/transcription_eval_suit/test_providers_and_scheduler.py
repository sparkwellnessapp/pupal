"""Tests for vlm_provider types, FakeProvider, ProviderScheduler, instrument.

Zero network. Scheduler tests use gated fakes and injected clocks/rng —
deterministic, no sleeps.
"""
import asyncio

import pytest

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import (
    ProviderLimit,
    ProviderScheduler,
    ScheduledResult,
)
from app.services.transcription.vlm_provider import (
    ErrorKind,
    Usage,
    VLMCallError,
    VLMProvider,
    VLMResponse,
)
from .instrument import PriceCard, StageTimer, Trace, cost_usd


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


# --- provider types ----------------------------------------------------------------

def test_fake_provider_satisfies_protocol():
    assert isinstance(FakeProvider(), VLMProvider)


def test_error_retryability():
    assert VLMCallError(ErrorKind.RATE_LIMIT, "x", provider="p").retryable
    assert VLMCallError(ErrorKind.TIMEOUT, "x", provider="p").retryable
    assert VLMCallError(ErrorKind.TRANSIENT, "x", provider="p").retryable
    assert not VLMCallError(ErrorKind.BAD_REQUEST, "x", provider="p").retryable
    assert not VLMCallError(ErrorKind.CONTENT_FILTER, "x", provider="p").retryable
    assert not VLMCallError(ErrorKind.AUTH, "x", provider="p").retryable


def test_fake_provider_records_phase_distinguishing_args():
    fake = FakeProvider()

    async def go():
        await fake.complete(system="s", user="u", images_b64=["img1", "img2"],
                            max_tokens=100)
        await fake.complete(system="s", user="u", max_tokens=100)  # phase-2 style

    _run(go())
    assert fake.calls[0].n_images == 2
    assert fake.calls[1].n_images == 0


# --- scheduler: retry policy ---------------------------------------------------------

def _sched(**limit_kw) -> ProviderScheduler:
    async def no_sleep(_s):  # collapse backoff in tests
        return None
    return ProviderScheduler(
        {"fake": ProviderLimit(**limit_kw)}, sleep_fn=no_sleep
    )


def test_retry_once_on_transient_then_success():
    fake = FakeProvider(script=[
        VLMCallError(ErrorKind.TRANSIENT, "boom", provider="fake"),
        FakeProvider.ok("recovered"),
    ])
    sched = _sched()

    async def go():
        return await sched.submit(
            "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
        )

    res: ScheduledResult = _run(go())
    assert res.response.text == "recovered"
    assert res.attempts == 2


def test_no_retry_on_bad_request():
    fake = FakeProvider(script=[
        VLMCallError(ErrorKind.BAD_REQUEST, "our bug", provider="fake"),
        FakeProvider.ok("should never be reached"),
    ])
    sched = _sched()

    async def go():
        return await sched.submit(
            "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
        )

    with pytest.raises(VLMCallError) as e:
        _run(go())
    assert e.value.kind == ErrorKind.BAD_REQUEST
    assert len(fake.calls) == 1  # exactly one attempt


def test_second_failure_propagates():
    fake = FakeProvider(script=[
        VLMCallError(ErrorKind.TIMEOUT, "t1", provider="fake"),
        VLMCallError(ErrorKind.TIMEOUT, "t2", provider="fake"),
    ])
    sched = _sched()

    async def go():
        return await sched.submit(
            "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
        )

    with pytest.raises(VLMCallError):
        _run(go())
    assert len(fake.calls) == 2  # one retry, then give up


# --- scheduler: concurrency + adaptive limit ----------------------------------------

def test_concurrency_limit_enforced_and_queue_wait_measured():
    async def go():
        gate = asyncio.Event()
        fake = FakeProvider(gate=gate)
        sched = ProviderScheduler({"fake": ProviderLimit(max_concurrent=2)})

        tasks = [
            asyncio.create_task(sched.submit(
                "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
            ))
            for _ in range(4)
        ]
        await asyncio.sleep(0)          # let tasks reach acquire
        lim = sched.limiter("fake")
        assert lim.in_flight == 2       # only 2 dispatched
        assert len(fake.calls) == 2     # third+fourth still queued
        gate.set()
        results = await asyncio.gather(*tasks)
        assert all(r.response.text == "ok" for r in results)
        assert len(fake.calls) == 4

    _run(go())


def test_rate_limit_halves_effective_concurrency_and_recovers():
    async def go():
        fake = FakeProvider(script=[
            VLMCallError(ErrorKind.RATE_LIMIT, "429", provider="fake"),
        ] + [FakeProvider.ok()] * 20)

        async def no_sleep(_s):
            return None

        sched = ProviderScheduler(
            {"fake": ProviderLimit(max_concurrent=4, recovery_successes=3)},
            sleep_fn=no_sleep,
        )
        lim = sched.limiter("fake")
        assert lim.effective == 4

        # First submit hits the 429 (then retries to success).
        await sched.submit(
            "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
        )
        assert lim.effective == 2  # halved by the 429

        # Successes creep it back up (+1 per `recovery_successes` streak).
        for _ in range(3):
            await sched.submit(
                "fake", 0, lambda: fake.complete(system="s", user="u", max_tokens=10)
            )
        assert lim.effective == 3

    _run(go())


def test_depth_first_dispatch_order():
    """Calls for doc 0 dispatch before doc 1's, regardless of submit order."""
    async def go():
        gate = asyncio.Event()
        fake = FakeProvider(gate=gate)
        sched = ProviderScheduler({"fake": ProviderLimit(max_concurrent=1)})
        order: list[str] = []

        async def call(tag: str):
            r = await sched.submit(
                "fake", int(tag[3]),  # "docN-..." -> N
                lambda: fake.complete(system="s", user=tag, max_tokens=10),
            )
            order.append(tag)
            return r

        # Occupy the single slot, then queue doc1 BEFORE doc0.
        first = asyncio.create_task(call("doc0-a"))
        await asyncio.sleep(0)
        later = [asyncio.create_task(call("doc1-a")),
                 asyncio.create_task(call("doc1-b")),
                 asyncio.create_task(call("doc0-b")),   # submitted last!
                 ]
        await asyncio.sleep(0)
        gate.set()
        await asyncio.gather(first, *later)
        # doc0-b jumps the queue ahead of both doc1 calls.
        assert order == ["doc0-a", "doc0-b", "doc1-a", "doc1-b"]

    _run(go())


# --- instrument ----------------------------------------------------------------------

def test_stage_timer_with_injected_clock():
    t = {"now": 0.0}

    def clock():
        return t["now"]

    trace = Trace(doc_id="d")
    timer = StageTimer(trace, time_fn=clock)
    with timer.span("p1_call"):
        t["now"] += 0.25
    with timer.span("p1_call"):
        t["now"] += 0.05
    with timer.span("merge"):
        t["now"] += 0.01
    assert trace.stage_ms("p1_call") == pytest.approx(300.0)
    assert trace.stage_ms("merge") == pytest.approx(10.0)


def test_cost_usd_with_and_without_cache_rate():
    usage = Usage(input_tokens=1_000_000, output_tokens=500_000,
                  cached_input_tokens=400_000)
    card = PriceCard(in_per_mtok=1.0, out_per_mtok=4.0, cached_in_per_mtok=0.1)
    # 600k uncached @ $1 + 400k cached @ $0.1 + 500k out @ $4
    assert cost_usd(usage, card) == pytest.approx(0.6 + 0.04 + 2.0)

    no_cache_card = PriceCard(in_per_mtok=1.0, out_per_mtok=4.0)
    # cached falls back to full input rate
    assert cost_usd(usage, no_cache_card) == pytest.approx(1.0 + 2.0)


# --- real adapters: import + construction only (no network in pytest -q) ------------

def test_real_adapters_import_and_construct():
    from app.services.transcription.providers.openai_provider import OpenAIProvider
    from app.services.transcription.providers.anthropic_provider import AnthropicProvider
    from app.services.transcription.providers.gemini_provider import GeminiProvider

    o = OpenAIProvider("gpt-test", api_key="k")
    a = AnthropicProvider("claude-test", api_key="k")
    g = GeminiProvider("gemini-test", api_key="k")
    assert isinstance(o, VLMProvider)
    assert isinstance(a, VLMProvider)
    assert isinstance(g, VLMProvider)
    assert (o.name, a.name, g.name) == ("openai", "anthropic", "gemini")


def test_models_registry():
    from .models_registry import MODELS, spec

    s = spec("claude-haiku-4.5")
    assert s.provider == "anthropic" and s.tier == "cheap"
    # every provider has a cheap and a frontier entry
    by_provider = {}
    for m in MODELS.values():
        by_provider.setdefault(m.provider, set()).add(m.tier)
    assert all(tiers == {"cheap", "frontier"} for tiers in by_provider.values())
    with pytest.raises(KeyError, match="Unknown model key"):
        spec("nope")
