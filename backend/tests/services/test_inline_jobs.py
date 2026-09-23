"""
Inline jobs are HELD until they finish, and the test harness can wait for them.

Two defects of the old `asyncio.create_task(runner(job_id))`, both about a task
nobody held:
  * the event loop keeps only a weak reference, so an un-held task can be
    garbage-collected mid-run (the asyncio documentation's own warning);
  * under test, a job one test started ran on into the next — the root cause
    of the roster statement-count flake (student-profile PR).
"""
from __future__ import annotations

import asyncio
from uuid import uuid4

from app.services import cloud_tasks_service as cts


def _kind(runner) -> cts.JobKind:
    return cts.JobKind(label="test_kind", internal_path="/internal/test/{job_id}/run",
                       queue=lambda: "q", execution_mode=lambda: "inline",
                       inline_runner=lambda: runner)


def _held(job_id) -> bool:
    return any(t.get_name() == f"test_kind:{job_id}" for t in cts._INLINE_TASKS)


async def test_an_inline_job_is_held_until_it_finishes_and_drain_waits_for_it():
    seen = []

    async def runner(job_id):
        await asyncio.sleep(0.05)
        seen.append(job_id)

    job = uuid4()
    await cts.enqueue_job(_kind(runner), job)
    assert _held(job) and seen == []

    assert await cts.drain_inline_jobs(timeout=5) == []
    assert seen == [job]
    assert not _held(job)                      # released once done


async def test_a_job_that_outlives_the_bound_is_cancelled_and_named():
    async def runner(job_id):
        await asyncio.sleep(30)

    job = uuid4()
    await cts.enqueue_job(_kind(runner), job)
    assert await cts.drain_inline_jobs(timeout=0.05) == [f"test_kind:{job}"]
    assert not _held(job)                      # cancelled AND unwound on return


async def test_a_failing_job_does_not_break_the_drain():
    """A runner owns its own failure handling (it writes a failed row); the
    drain only waits, and never re-raises a job's exception into a test."""
    async def runner(job_id):
        raise RuntimeError("boom")

    await cts.enqueue_job(_kind(runner), uuid4())
    assert await cts.drain_inline_jobs(timeout=5) == []


async def test_nothing_in_flight_is_an_immediate_no_op():
    assert await cts.drain_inline_jobs(timeout=0) == []
