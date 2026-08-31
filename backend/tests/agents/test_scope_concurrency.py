"""
PR-G3(a) — the scope-concurrency lever.

`MAX_CONCURRENT_SCOPES` was a module constant of 5, so a 15-scope test ran three
serial waves and no dial existed to change that. This makes it configurable and
scope-aware, and pins the two properties that make it safe:

  * it never exceeds the scope count (a 3-scope test does not open 16 slots), and
  * the ETA's wave arithmetic reads the SAME number.

The second is not housekeeping. `eta.py` computed its wave count from the
constant AT IMPORT TIME; leaving that alone would make every quoted ETA a
figure derived from a concurrency the grader is no longer using — a wrong number
presented with full confidence, on the one screen the teacher plans her evening
around (§3.5a).
"""
from __future__ import annotations

import asyncio

import pytest


def test_concurrency_is_capped_by_the_scope_count():
    """A 3-scope test opening 16 slots is not wrong, it is just noise — but the
    ETA divides by this number, so an honest value matters."""
    from app.agents.grader.grader import effective_scope_concurrency

    assert effective_scope_concurrency(3) == 3
    assert effective_scope_concurrency(1) == 1


def test_concurrency_is_capped_by_the_configured_ceiling():
    from app.agents.grader.grader import effective_scope_concurrency
    from app.config import settings

    assert effective_scope_concurrency(20) == settings.grader_max_concurrent_scopes
    assert effective_scope_concurrency(10_000) == settings.grader_max_concurrent_scopes


def test_concurrency_is_never_zero():
    """`asyncio.Semaphore(0)` deadlocks forever. A scope count of zero is a
    degenerate rubric, not a reason to hang a worker until the liveness reaper
    notices thirty minutes later."""
    from app.agents.grader.grader import effective_scope_concurrency

    assert effective_scope_concurrency(0) == 1
    assert effective_scope_concurrency(-1) == 1


def test_ceiling_is_read_at_call_time_not_import_time(monkeypatch):
    """The kill criterion is «any rate-limit failure → revert to 5». That revert
    has to be an env change on a running service, so the value cannot be frozen
    into a module constant at import."""
    from app.agents.grader import grader
    from app.config import settings

    monkeypatch.setattr(settings, "grader_max_concurrent_scopes", 2)
    assert grader.effective_scope_concurrency(50) == 2

    monkeypatch.setattr(settings, "grader_max_concurrent_scopes", 9)
    assert grader.effective_scope_concurrency(50) == 9


def test_eta_wave_math_tracks_the_same_ceiling(monkeypatch):
    """The ETA and the grader must not disagree about how many waves a test is.

    A frozen `_PROFILE_WAVES` would keep quoting 5-wide arithmetic after the
    dial moved — the teacher would be told a number that no longer describes
    anything the system does.
    """
    from app.config import settings
    from app.services.eta import estimate_eta

    monkeypatch.setattr(settings, "grader_max_concurrent_scopes", 5)
    at_five = estimate_eta(profile_p50=120.0, scope_count=15, landed_durations=[])

    monkeypatch.setattr(settings, "grader_max_concurrent_scopes", 16)
    at_sixteen = estimate_eta(profile_p50=120.0, scope_count=15, landed_durations=[])

    assert at_five["seconds"] == 180, "15 scopes at 5-wide is three waves"
    assert at_sixteen["seconds"] < at_five["seconds"], (
        "a wider dial finishes sooner, and the ETA must say so")


@pytest.mark.parametrize("scope_count,expected_peak", [(3, 3), (12, 6)])
def test_grader_never_runs_more_scopes_at_once_than_the_effective_cap(
        scope_count, expected_peak, monkeypatch):
    """The behavioural half: observed peak concurrency, not just the arithmetic.

    A `min()` in a helper nobody calls would pass every test above and change
    nothing about what production does.
    """
    from app.agents.grader import grader
    from app.config import settings

    monkeypatch.setattr(settings, "grader_max_concurrent_scopes", 6)

    live = 0
    peak = 0

    async def _work():
        nonlocal live, peak
        live += 1
        peak = max(peak, live)
        await asyncio.sleep(0.01)
        live -= 1

    async def _run():
        sem = asyncio.Semaphore(grader.effective_scope_concurrency(scope_count))

        async def _bounded():
            async with sem:
                await _work()

        await asyncio.gather(*(_bounded() for _ in range(scope_count)))

    asyncio.run(_run())
    assert peak == expected_peak, f"peak concurrency was {peak}, expected {expected_peak}"
