"""
ProviderScheduler under CANCELLATION — zero-network, deterministic (no sleeps,
no gates raced against the event loop).

WHY THIS FILE EXISTS. Nothing in this codebase cancelled a provider call until
the optional-pass belts landed (`PipelineConfig.optional_pass_budget_s`): a
hung strike check simply ran to its 240s timeout. The belt cancels it instead —
which is the point — and that made a latent slot leak in `_AdaptiveLimiter`
reachable for the first time.

THE LEAK. `submit` only enters its `try/finally: lim.release()` AFTER
`await lim.acquire(...)` returns. A waiter that `_dispatch` has already handed
a slot to (in_flight incremented, future resolved) but whose task is cancelled
before it resumes never reaches that `finally` — so the slot is charged and
never given back. It is permanent, instance-wide and silent: the effective
concurrency drops by one for the life of the process, with no error anywhere.
Two of those on a busy instance and every teacher's documents run half as wide
for no visible reason.

THE SUBTLETY is that the two cancellation states need OPPOSITE handling, and
one exception carries both: still QUEUED charged no slot, already DISPATCHED
charged one. The tests below drive the limiter directly, because the window
between "dispatched" and "resumed" is exactly one event-loop step and racing a
gate against it would make the pin flaky rather than deterministic.
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import (
    ProviderLimit,
    ProviderScheduler,
    _AdaptiveLimiter,
)


def _call(provider: FakeProvider):
    async def run():
        return await provider.complete(system="s", user="u", max_tokens=10)
    return run


def test_cancelling_a_dispatched_waiter_gives_its_slot_back():
    """The leak, pinned at the exact instant it happens.

    `release()` is synchronous: it decrements, then `_dispatch` immediately
    charges the slot to the popped waiter and resolves its future. Cancelling
    before the next loop step catches the waiter dispatched-but-not-resumed —
    the one window where nobody would give the slot back."""
    async def scenario():
        lim = _AdaptiveLimiter(ProviderLimit(max_concurrent=1))
        await lim.acquire(0)                     # A takes the only slot
        assert lim.in_flight == 1

        waiter = asyncio.ensure_future(lim.acquire(0))   # B queues
        await asyncio.sleep(0)
        assert lim.in_flight == 1

        lim.release()          # -> _dispatch hands B the slot, resolves its future
        assert lim.in_flight == 1, "the slot was handed to B, not freed"
        waiter.cancel()        # ...and B is cancelled before it ever resumes
        with pytest.raises(asyncio.CancelledError):
            await waiter

        assert lim.in_flight == 0, (
            "a cancelled-after-dispatch waiter leaked its concurrency slot")

    asyncio.run(scenario())


def test_cancelling_a_still_queued_waiter_charges_nothing():
    """The other state, and it must NOT double-release: this waiter never held
    a slot, so giving one back would drive in_flight negative and hand the
    provider MORE concurrency than its limit allows."""
    async def scenario():
        lim = _AdaptiveLimiter(ProviderLimit(max_concurrent=1))
        await lim.acquire(0)
        waiter = asyncio.ensure_future(lim.acquire(0))
        await asyncio.sleep(0)

        waiter.cancel()                          # still queued: nothing released
        with pytest.raises(asyncio.CancelledError):
            await waiter
        assert lim.in_flight == 1, "the queued waiter never held a slot"

        lim.release()
        assert lim.in_flight == 0

    asyncio.run(scenario())


def test_a_cancelled_waiter_does_not_swallow_the_slot_owed_to_the_next_one():
    """The consequence, end to end: after the cancellation the limiter must
    still admit work at its full width. Under the leak this went to zero and
    stayed there."""
    async def scenario():
        lim = _AdaptiveLimiter(ProviderLimit(max_concurrent=2))
        await lim.acquire(0)
        await lim.acquire(0)
        doomed = [asyncio.ensure_future(lim.acquire(0)) for _ in range(2)]
        await asyncio.sleep(0)

        lim.release()
        lim.release()
        for d in doomed:
            d.cancel()
        await asyncio.gather(*doomed, return_exceptions=True)
        assert lim.in_flight == 0

        # Full width, immediately, with no waiting.
        await lim.acquire(0)
        await lim.acquire(0)
        assert lim.in_flight == 2

    asyncio.run(scenario())


def test_a_cancelled_belt_leaves_the_scheduler_usable_for_the_next_document():
    """The same property through the public seam: after a phase belt cancels a
    hung call, the NEXT document must get the provider at full width."""
    async def scenario():
        never = asyncio.Event()
        hung = FakeProvider(name="p", gate=never)
        sched = ProviderScheduler({"p": ProviderLimit(max_concurrent=1)})

        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(sched.submit("p", 0, _call(hung)), timeout=0.01)

        healthy = FakeProvider(name="p")
        res = await asyncio.wait_for(
            sched.submit("p", 0, _call(healthy)), timeout=1.0)
        assert res.response.text == "ok"
        assert sched.limiter("p").in_flight == 0

    asyncio.run(scenario())


def test_submit_carries_the_doc_id_into_its_failure_lines(caplog):
    """Observability, and it is not cosmetic: on 2026-09-10 a single call spent
    481s here and the only line it wrote named the PROVIDER, so filtering the
    logs by the document that was stuck could not find the seconds that
    explained it."""
    from app.services.transcription.vlm_provider import ErrorKind, VLMCallError

    async def scenario():
        provider = FakeProvider(
            name="p",
            script=[VLMCallError(ErrorKind.TIMEOUT, "boom", provider="p")])
        sched = ProviderScheduler({"p": ProviderLimit(max_concurrent=1)},
                                  sleep_fn=lambda _s: asyncio.sleep(0))
        with pytest.raises(VLMCallError):
            await sched.submit("p", 0, _call(provider), doc_id="stuck.pdf")

    with caplog.at_level("WARNING", logger="transcription.scheduler"):
        asyncio.run(scenario())

    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "stuck.pdf" in text, "the retry/failure lines must name the document"
    assert "after" in text, "the COST of the failed attempt must be recorded"
