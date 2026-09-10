"""
The per-document transcription wall budget and the optional-pass transport
policy — zero-network, zero-mock (a scripted FakeProvider, no patching).

WHAT THIS PINS, and why each one exists (incident 2026-09-10):

Five documents were submitted together. Four landed in 47-78s; one took ~600s
and left one line in the logs — `strike_check page 2 vote 1 failed; casting no
ranges`, written 521.8s after the job was claimed. Subtracting a normal P1
leaves ~481s = 240s + backoff + 240s: the scheduler's one transport retry on
the GLOBAL `timeout_s`, spent by an OPTIONAL pass with a 7.8s median whose own
failure handling is «keep the page exactly as P1 produced it».

  «checker must never sink the doc» was implemented as "never RAISE".
  It was not implemented as "never DELAY".

So the tests below are, in order: the timeout SPLIT (essential vs optional),
the phase BELT (an optional pass may not delay without bound even when it
cannot raise), the SKIP (an unaffordable optional pass yields rather than
starting), and the ESSENTIAL refusal (P1/P2 exhaustion is a loud, retryable
failure, never a partial draft).
"""
from __future__ import annotations

import asyncio
import json

import pytest
from PIL import Image

from app.services.transcription.budget import Budget, BudgetExceeded
from app.services.transcription.providers.fake import FakeProvider
from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.instrument import PriceCard, Trace
from app.services.transcription.two_phase.pipeline import (
    AliasedModel,
    Pipeline,
    PipelineConfig,
)

_PRICE = PriceCard(in_per_mtok=1.0, out_per_mtok=1.0)


def _resolver(key: str) -> AliasedModel:
    return AliasedModel(key=key, provider=key, model_id=f"{key}-id",
                        price=_PRICE, supports_json_schema=True)


def _images(n: int = 2) -> list[Image.Image]:
    return [Image.new("RGB", (40, 60), "white") for _ in range(n)]


def _cfg(**over) -> PipelineConfig:
    base = dict(
        p1_model_key="p1",
        p1_pages_per_call=3,
        p1_strike_check_model_key="checker",
        p1_strike_check_votes=1,
        timeout_s=240.0,
        optional_pass_timeout_s=40.0,
        optional_pass_budget_s=120.0,
        image_max_px=64,
    )
    base.update(over)
    return PipelineConfig(**base)


def _scheduler() -> ProviderScheduler:
    return ProviderScheduler({
        "p1": ProviderLimit(max_concurrent=4),
        "checker": ProviderLimit(max_concurrent=4),
    })


def _p1_ok(pages: dict[int, str]) -> FakeProvider:
    return FakeProvider(name="p1", script=[FakeProvider.ok(json.dumps(
        {"pages": [{"page_number": n, "text": t} for n, t in pages.items()]}))])


def _checker(script) -> FakeProvider:
    return FakeProvider(name="checker", script=script)


def _pipeline(cfg, providers, *, budget: Budget | None = None) -> Pipeline:
    return Pipeline(cfg, providers, _scheduler(),
                    resolve_model=_resolver, budget=budget)


# ---------------------------------------------------------------------------
# The Budget itself
# ---------------------------------------------------------------------------

def test_unbounded_budget_never_constrains_anything():
    # `None` IS the eval path (PR-2's seam): the suite measures model behaviour,
    # not Cloud Run's request timeout, so check_goal.sh is untouched by
    # construction. If this ever starts clamping, the eval numbers move.
    b = Budget(None)
    assert b.bounded is False
    assert b.remaining_s() is None
    assert b.clamp(240.0) == 240.0
    assert b.can_start(10_000.0) is True
    b.require(10_000.0, "anything")          # must not raise


def test_clamp_never_lets_a_call_outlive_the_budget():
    clock = [1000.0]
    b = Budget(100.0, time_fn=lambda: clock[0])
    assert b.clamp(240.0) == 100.0           # budget is the ceiling
    clock[0] += 70.0
    assert b.clamp(240.0) == pytest.approx(30.0)
    assert b.clamp(5.0) == 5.0               # a shorter ask is left alone


def test_clamp_floors_at_one_second_rather_than_going_negative():
    clock = [0.0]
    b = Budget(10.0, time_fn=lambda: clock[0])
    clock[0] = 999.0
    # Essential phases call `require` first, so this is defence in depth — but
    # handing a provider a negative timeout would be a DIFFERENT bug than the
    # one we are trying to report.
    assert b.clamp(240.0) == 1.0


def test_require_names_the_phase_and_the_arithmetic():
    clock = [0.0]
    b = Budget(100.0, time_fn=lambda: clock[0])
    clock[0] = 90.0
    with pytest.raises(BudgetExceeded) as exc:
        b.require(240.0, "phase 2 (segmentation)")
    msg = str(exc.value)
    assert "phase 2 (segmentation)" in msg
    assert "90s" in msg and "100s" in msg


def test_started_at_lets_the_caller_anchor_the_clock_before_the_object_exists():
    # The job runner starts counting at its CAS claim so the GCS download and
    # the rubric read are INSIDE the budget rather than assumed away.
    clock = [500.0]
    b = Budget(100.0, time_fn=lambda: clock[0], started_at=460.0)
    assert b.elapsed_s() == pytest.approx(40.0)
    assert b.remaining_s() == pytest.approx(60.0)


# ---------------------------------------------------------------------------
# THE FIX: the per-phase timeout split
# ---------------------------------------------------------------------------

def test_strike_check_gets_the_optional_pass_timeout_and_p1_keeps_its_own():
    """THE regression pin for the incident.

    One global `timeout_s` reached every phase. It is calibrated in its own
    comment entirely for P1's multi-MB image uploads on weak links — and the
    strike check inherited it, giving a 7.8s-median call a 240s ceiling and,
    with the scheduler's retry, a ~481s worst case."""
    cfg = _cfg()
    providers = {
        "p1": _p1_ok({1: "line one\nline two", 2: "line three"}),
        "checker": _checker([FakeProvider.ok(json.dumps({"struck_line_ranges": []}))]),
    }
    pipe = _pipeline(cfg, providers)
    asyncio.run(pipe.perceive(_images(2), "doc.pdf", 0, Trace(doc_id="doc.pdf")))

    assert [c.timeout_s for c in providers["p1"].calls] == [240.0]
    checker_timeouts = [c.timeout_s for c in providers["checker"].calls]
    assert checker_timeouts, "the strike check must actually have run"
    assert all(t == 40.0 for t in checker_timeouts), checker_timeouts


def test_the_skip_guard_is_the_strong_one_and_the_clamps_sit_under_it():
    """A composition fact worth stating, because it is what makes the two
    clamps look dead when you go looking for them.

    `can_start(optional_pass_budget_s)` runs at PHASE ENTRY, and
    `optional_pass_budget_s` (120s) is deliberately >= `optional_pass_timeout_s`
    (40s). So whenever an optional pass is allowed to begin, the remaining
    budget already exceeds both its per-call timeout and its belt — and the
    clamps can only bind on time that elapses BETWEEN entry and dispatch (page
    encoding, or queueing behind the per-model concurrency cap).

    That ordering is the design: the guard should be what stops an unaffordable
    pass, and the clamps should be the floor under it, never the other way
    round. Invert the two constants and a pass could start work it is certain
    not to finish — which is the shape of the bug this module exists to kill.
    """
    cfg = _cfg()
    assert cfg.optional_pass_budget_s >= cfg.optional_pass_timeout_s

    from app.services.transcription.two_phase_engine import PROD_CONFIG
    assert PROD_CONFIG.optional_pass_budget_s >= PROD_CONFIG.optional_pass_timeout_s
    # ...and an optional pass must never be given more patience than an
    # essential one: that inversion is exactly the incident.
    assert PROD_CONFIG.optional_pass_timeout_s < PROD_CONFIG.timeout_s


# ---------------------------------------------------------------------------
# THE BELT: an optional pass may not DELAY without bound
# ---------------------------------------------------------------------------

def test_a_hanging_strike_check_returns_p1_text_instead_of_holding_the_document():
    """The pass already could not RAISE. It could still DELAY, and on
    2026-09-10 it delayed a teacher's document by ~8 minutes and then discarded
    its own result exactly as designed. Expiry lands on the same outcome the
    pass already defines: every page keeps P1's text."""
    gate = asyncio.Event()          # never set: the checker call hangs forever
    cfg = _cfg(optional_pass_budget_s=0.05)
    providers = {
        "p1": _p1_ok({1: "kept one\nkept two"}),
        "checker": FakeProvider(name="checker", gate=gate),
    }
    pipe = _pipeline(cfg, providers)

    pages = asyncio.run(
        pipe.perceive(_images(1), "hang.pdf", 0, Trace(doc_id="hang.pdf")))

    assert pages == {1: "kept one\nkept two"}


# ---------------------------------------------------------------------------
# THE SKIP: an unaffordable optional pass yields rather than starting
# ---------------------------------------------------------------------------

def test_strike_check_is_skipped_whole_when_the_budget_cannot_cover_it():
    clock = [0.0]
    cfg = _cfg()
    providers = {
        "p1": _p1_ok({1: "x\ny"}),
        "checker": _checker([FakeProvider.ok(json.dumps({"struck_line_ranges": []}))]),
    }
    budget = Budget(300.0, time_fn=lambda: clock[0])
    pipe = _pipeline(cfg, providers, budget=budget)

    async def drive():
        clock[0] = 250.0        # 50s left; the pass wants 120s of runway
        return await pipe._strike_check_pages(          # noqa: SLF001
            _images(1), {1: "x\ny"}, "s.pdf", 0, Trace(doc_id="s.pdf"))

    pages = asyncio.run(drive())
    assert pages == {1: "x\ny"}
    assert providers["checker"].calls == [], "an unaffordable pass must not dial out"


def test_readers_are_skipped_on_the_same_rule():
    clock = [0.0]
    cfg = _cfg(reader_model_keys=("reader",))
    providers = {
        "p1": _p1_ok({1: "x"}),
        "checker": _checker([FakeProvider.ok(json.dumps({"struck_line_ranges": []}))]),
        "reader": _p1_ok({1: "x"}),
    }
    budget = Budget(300.0, time_fn=lambda: clock[0])
    pipe = _pipeline(cfg, providers, budget=budget)
    pipe._sched = ProviderScheduler({                       # noqa: SLF001
        k: ProviderLimit(max_concurrent=4) for k in providers})

    async def drive():
        clock[0] = 250.0
        return await pipe.run_readers(_images(1), "r.pdf", doc_priority=0)

    reader_pages, _ = asyncio.run(drive())
    assert reader_pages == {}
    assert providers["reader"].calls == []


def test_readers_use_the_optional_pass_timeout_when_they_do_run():
    cfg = _cfg(reader_model_keys=("reader",), p1_strike_check_model_key="")
    providers = {
        "p1": _p1_ok({1: "x"}),
        "reader": _p1_ok({1: "x"}),
    }
    pipe = Pipeline(cfg, providers,
                    ProviderScheduler({k: ProviderLimit(max_concurrent=4)
                                       for k in providers}),
                    resolve_model=_resolver)
    asyncio.run(pipe.run_readers(_images(1), "r.pdf", doc_priority=0))
    assert [c.timeout_s for c in providers["reader"].calls] == [40.0]


# ---------------------------------------------------------------------------
# THE ESSENTIAL REFUSAL: loud and retryable, never a partial draft
# ---------------------------------------------------------------------------

def test_p1_refuses_to_start_when_the_budget_is_gone():
    clock = [0.0]
    cfg = _cfg()
    providers = {"p1": _p1_ok({1: "x"}), "checker": _checker([])}
    budget = Budget(100.0, time_fn=lambda: clock[0])
    pipe = _pipeline(cfg, providers, budget=budget)

    async def drive():
        clock[0] = 99.0          # 1s left — under the 30s essential floor
        return await pipe.perceive(_images(1), "p.pdf", 0, Trace(doc_id="p.pdf"))

    with pytest.raises(BudgetExceeded) as exc:
        asyncio.run(drive())
    assert "phase 1" in str(exc.value)
    assert providers["p1"].calls == []


def test_p2_refuses_to_start_when_the_budget_is_gone():
    # P1 text without segmentation is not a transcription anyone can grade, so
    # exhaustion here RAISES rather than shipping a partial draft: transcription
    # feeds grading, a CONSUMING path (CLAUDE.md 3.5a), and a partial draft
    # presented as complete would be a silent repair (FC).
    clock = [0.0]
    cfg = _cfg(p2_model_key="p2")
    providers = {"p1": _p1_ok({1: "x"}), "checker": _checker([]),
                 "p2": _p1_ok({1: "x"})}
    budget = Budget(100.0, time_fn=lambda: clock[0])
    pipe = Pipeline(cfg, providers,
                    ProviderScheduler({k: ProviderLimit(max_concurrent=4)
                                       for k in providers}),
                    resolve_model=_resolver, budget=budget)

    async def drive():
        clock[0] = 99.0          # 1s left — under the 30s essential floor
        return await pipe.run_phase2({1: "x"}, _EMPTY_SPEC, "p.pdf")

    with pytest.raises(BudgetExceeded) as exc:
        asyncio.run(drive())
    assert "phase 2" in str(exc.value)
    assert providers["p2"].calls == []


class _EmptySpec:
    """Minimal ExamSpec stand-in: run_phase2 must refuse BEFORE it is read."""

    def to_prompt_json(self):                    # pragma: no cover - never called
        raise AssertionError("the budget must refuse before the spec is touched")


_EMPTY_SPEC = _EmptySpec()
