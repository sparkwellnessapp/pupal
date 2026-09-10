"""
ProviderScheduler — the ONE place concurrency, ordering, backoff, and retry live.
Shared by production and the eval harness so measured throughput is real.

Three locked properties:

1. PER-PROVIDER ADAPTIVE LIMITS. Each provider has its own limiter (this is
   what makes multi-provider routing a config change later). On a rate-limit
   error the effective concurrency halves (min 1); after `recovery_successes`
   consecutive successes it creeps back up by 1 toward the configured max.

2. DEPTH-FIRST DISPATCH. Waiters are dispatched in (doc_priority, submit_seq)
   order — all pending calls for document 1 go before document 2's first call.
   This single ordering rule IS the time-to-first-draft optimization.

3. RETRY POLICY: ONE retry, retryable kinds only (rate_limit/transient/timeout),
   jittered backoff. Content/parse/bad-request failures are never retried —
   they propagate and are recorded as outcomes (mirrors the grader's
   transient-only rule). SDK-internal retries are disabled in adapters, so the
   attempt count here is globally true.

queue_wait_ms is measured on every call: time between submit and dispatch.
At low provider tiers this is THE number that decides "buy a tier upgrade vs
build routing" — which is why it must come from the same scheduler prod uses.

Determinism for tests: time_fn / sleep_fn / rng are injectable.
"""
from __future__ import annotations

import asyncio
import heapq
import itertools
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable

from .vlm_provider import VLMCallError, VLMResponse

log = logging.getLogger("transcription.scheduler")


@dataclass(frozen=True)
class ProviderLimit:
    max_concurrent: int = 3            # conservative lowest-tier default (approved)
    recovery_successes: int = 5        # consecutive successes to creep limit back up
    backoff_base_s: float = 1.0        # retry backoff = base * (1 + jitter)
    backoff_jitter: float = 0.5


@dataclass(frozen=True)
class ScheduledResult:
    response: VLMResponse
    queue_wait_ms: float
    attempts: int


class _AdaptiveLimiter:
    """A semaphore whose capacity can shrink on 429s and recover on successes.

    Waiters are kept in a heap ordered by (priority, seq) — depth-first.
    Plain asyncio primitives can't do priority wake-ups, hence hand-rolled.
    """

    def __init__(self, limit: ProviderLimit):
        self.cfg = limit
        self.effective = limit.max_concurrent
        self.in_flight = 0
        self._waiters: list[tuple[int, int, asyncio.Future]] = []
        self._seq = itertools.count()
        self._success_streak = 0

    def _dispatch(self) -> None:
        while self._waiters and self.in_flight < self.effective:
            _, _, fut = heapq.heappop(self._waiters)
            if fut.cancelled():
                continue
            self.in_flight += 1
            fut.set_result(None)

    async def acquire(self, priority: int) -> None:
        if self.in_flight < self.effective and not self._waiters:
            self.in_flight += 1
            return
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        heapq.heappush(self._waiters, (priority, next(self._seq), fut))
        try:
            await fut
        except asyncio.CancelledError:
            # TWO different states hide behind one exception, and they need
            # OPPOSITE handling. This was latent until the optional-pass belts
            # (pipeline.optional_pass_budget_s) made cancellation reachable at
            # all; a leaked slot is permanent, instance-wide, and silent — the
            # effective concurrency just quietly drops and never comes back.
            #
            #   fut.cancelled()  -> we were still QUEUED. No slot was charged;
            #                       _dispatch skips cancelled waiters when it
            #                       pops them, so simply leave.
            #   not fut.cancelled() -> _dispatch already handed us the slot and
            #                       charged in_flight BEFORE this task was
            #                       cancelled (Task.cancel on a resolved future
            #                       sets _must_cancel and throws at resume). The
            #                       `finally: lim.release()` in `submit` has not
            #                       been entered yet, so nobody else will give
            #                       this slot back. We must.
            if not fut.cancelled():
                self.release()
            raise

    def release(self) -> None:
        self.in_flight -= 1
        self._dispatch()

    def on_rate_limit(self) -> None:
        self._success_streak = 0
        self.effective = max(1, self.effective // 2)

    def on_success(self) -> None:
        self._success_streak += 1
        if (self._success_streak >= self.cfg.recovery_successes
                and self.effective < self.cfg.max_concurrent):
            self.effective += 1
            self._success_streak = 0
            self._dispatch()


class ProviderScheduler:
    def __init__(
        self,
        limits: dict[str, ProviderLimit],
        *,
        time_fn: Callable[[], float] = time.monotonic,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
        rng: random.Random | None = None,
    ):
        self._limiters = {name: _AdaptiveLimiter(cfg) for name, cfg in limits.items()}
        self._time = time_fn
        self._sleep = sleep_fn
        self._rng = rng or random.Random()

    def limiter(self, provider_name: str) -> _AdaptiveLimiter:
        if provider_name not in self._limiters:
            self._limiters[provider_name] = _AdaptiveLimiter(ProviderLimit())
        return self._limiters[provider_name]

    async def submit(
        self,
        provider_name: str,
        doc_priority: int,
        call: Callable[[], Awaitable[VLMResponse]],
        *,
        doc_id: str = "",
    ) -> ScheduledResult:
        """Run `call` under the provider's limiter. One retry on retryable kinds.

        `doc_id` is DIAGNOSTIC AND LOAD-BEARING. On 2026-09-10 a single call
        spent 481s here (240s + backoff + 240s) and the only line it wrote named
        the PROVIDER — so filtering the logs by the document that was stuck
        could not find the 481 seconds that explained it. Every line below now
        carries the document."""
        lim = self.limiter(provider_name)
        tag = f"[{doc_id}] " if doc_id else ""
        submitted = self._time()
        await lim.acquire(doc_priority)
        queue_wait_ms = (self._time() - submitted) * 1000.0

        attempts = 0
        try:
            while True:
                attempts += 1
                log.debug("%s%s: calling provider (attempt %d, in_flight=%d/%d, "
                          "queue_wait=%.0fms)",
                          tag, provider_name, attempts, lim.in_flight,
                          lim.effective, queue_wait_ms)
                attempt_started = self._time()
                try:
                    response = await call()
                except VLMCallError as e:
                    # The COST of a failed attempt is logged here and nowhere
                    # else: the success-path timing line in
                    # `Pipeline._call_and_parse` is only reached when `submit`
                    # RETURNS, so before this a call that raised recorded how
                    # long it burned in no log at all.
                    failed_after_s = self._time() - attempt_started
                    if e.kind.value == "rate_limit":
                        lim.on_rate_limit()
                    if e.retryable and attempts == 1:
                        cfg = lim.cfg
                        backoff = cfg.backoff_base_s * (
                            1.0 + self._rng.random() * cfg.backoff_jitter
                        )
                        log.warning(
                            "%s%s: call failed (%s) after %.0fs; retrying once "
                            "after %.2fs", tag, provider_name, e.kind.value,
                            failed_after_s, backoff)
                        await self._sleep(backoff)
                        continue
                    log.warning(
                        "%s%s: call failed (%s) after %.0fs; not retrying "
                        "(attempt %d)", tag, provider_name, e.kind.value,
                        failed_after_s, attempts)
                    raise
                lim.on_success()
                return ScheduledResult(
                    response=response,
                    queue_wait_ms=queue_wait_ms,
                    attempts=attempts,
                )
        finally:
            lim.release()
