"""Shared-registry invariants — the statements true for ANY consumer.

Suite-specific statements live in the suites' own tests (e.g. the
transcription seed-set assertion in test_providers_and_scheduler.py, the
rubric sweep-config pins in test_llm_policy.py). This file guards the
registry itself plus the one cross-suite property the whole design exists
for: every model key any config names resolves, with zero API calls.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.eval_common.models_registry import AS_OF, MODELS, spec

TESTS_DIR = Path(__file__).resolve().parents[1]


def test_keys_are_self_consistent():
    # A dict key that disagrees with its spec.key would silently break the
    # config -> CallRecord/results vocabulary the key exists to unify.
    for k, m in MODELS.items():
        assert m.key == k, f"registry key {k!r} != spec.key {m.key!r}"


def test_unknown_key_fails_loudly():
    with pytest.raises(KeyError, match="Unknown model key"):
        spec("nope")


def test_prices_positive():
    for m in MODELS.values():
        assert m.price.in_per_mtok > 0 and m.price.out_per_mtok > 0, m.key


@pytest.mark.xfail(
    reason="D5 (PLAN_model_registry_normalization.md): claude-sonnet-4-6 "
           "carries cached_in=3.75 > in=3.00 — the shape of a cache WRITE "
           "rate applied to reads; awaiting owner price verification. Remove "
           "this marker when the card is corrected or the rate is confirmed.",
    strict=False,
)
def test_cached_rate_not_above_uncached():
    for m in MODELS.values():
        if m.price.cached_in_per_mtok is not None:
            assert m.price.cached_in_per_mtok <= m.price.in_per_mtok, m.key


def _config_model_keys() -> list[tuple[str, str]]:
    """(config filename, model key) for every key named by EITHER suite."""
    named: list[tuple[str, str]] = []
    for p in sorted((TESTS_DIR / "transcription_eval_suit" / "configs").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        for k in (d.get("p1_model_key"), d.get("p2_model_key"),
                  d.get("p1_strike_check_model_key"),
                  *(d.get("reader_model_keys") or [])):
            if k:
                named.append((p.name, k))
    for p in sorted((TESTS_DIR / "rubric_eval_suite" / "configs").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("model_key"):
            named.append((p.name, d["model_key"]))
    # grading eval suite (2026-08-24, mission §2: registered in the same PR as
    # its first config) — same model_key-only schema as the rubric suite
    for p in sorted((TESTS_DIR / "grading_eval_suite" / "configs").glob("*.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if d.get("model_key"):
            named.append((p.name, d["model_key"]))
    return named


def test_every_config_key_of_both_suites_resolves():
    """The dry-resolve gate: a typo'd or stale key in ANY config of EITHER
    suite fails here, offline — never as a provider 4xx mid-run (this caught
    v0_p2_correct_spec.json's stale 'gpt-5.4-nano' on day one)."""
    named = _config_model_keys()
    assert named, "found no config model keys — did the config dirs move?"
    bad = [(cfg, k) for cfg, k in named if k not in MODELS]
    assert not bad, f"configs name unknown model keys: {bad}"


def test_transcription_shim_reexports_same_objects():
    # The shim must alias, never fork: same objects, not equal copies.
    from tests.transcription_eval_suit import models_registry as shim
    assert shim.MODELS is MODELS
    assert shim.spec is spec
    assert shim.AS_OF == AS_OF
