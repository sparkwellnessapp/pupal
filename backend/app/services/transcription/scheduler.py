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

3. RETRY POLICY — kind-aware, still ONE layer (2026-09-30, owner-approved):
   * rate_limit (a 429 — the provider's shared pool is momentarily busy; it
     fails in ~2s and costs nothing): up to `rate_limit_max_attempts` (4)
     attempts, EXPONENTIAL backoff with jitter (~1-1.5s, 2-3s, 4-6s, capped).
     Google's own guidance for Vertex 429s; one quick retry landed in the same
     busy moment (eval 2026-09-28: 34 of 118 429s still failed after it).
   * transient / timeout (a SLOW failure — it already burned a full deadline):
     still ONE retry, because every extra attempt costs another deadline and
     the document's wall budget is built on this count. Its wait is WIDER and
     fully jittered (2-5s): when several pages of one document fail at the same
     moment (noam, 2026-09-30: four strike-check 504s in one second) a fixed
     ~1.2s wait retried them in lockstep into the same congestion (production:
     3 of 21 such retries succeeded).
   Content/parse/bad-request failures are never retried — they propagate and
   are recorded as outcomes (mirrors the grader's transient-only rule).
   SDK-internal retries are disabled in adapters, so the attempt count here is
   globally true.

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
    backoff_base_s: float = 1.0        # 429 backoff n = base * 2**(n-1) * (1 + jitter)
    backoff_jitter: float = 0.5
    backoff_cap_s: float = 20.0        # ceiling on any single 429 backoff
    rate_limit_max_attempts: int = 4   # a 429 fails fast: retry it up to 3 times
    slow_retry_wait_s: tuple[float, float] = (2.0, 5.0)   # transient/timeout: U(lo, hi)


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
        """Run `call` under the provider's limiter; retry per the kind-aware
        policy (module docstring, property 3).

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
                    cfg = lim.cfg
                    fast = e.kind.value == "rate_limit"
                    max_attempts = cfg.rate_limit_max_attempts if fast else 2
                    if e.retryable and attempts < max_attempts:
                        if fast:
                            backoff = min(cfg.backoff_cap_s,
                                          cfg.backoff_base_s * 2 ** (attempts - 1)) * (
                                1.0 + self._rng.random() * cfg.backoff_jitter)
                        else:
                            lo, hi = cfg.slow_retry_wait_s
                            backoff = lo + self._rng.random() * (hi - lo)
                        log.warning(
                            "%s%s: call failed (%s) after %.0fs; retrying "
                            "(attempt %d/%d) after %.2fs", tag, provider_name,
                            e.kind.value, failed_after_s, attempts + 1,
                            max_attempts, backoff)
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
