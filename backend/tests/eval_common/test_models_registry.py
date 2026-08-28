"""
Registry integrity — the COST_TRUTH unit test (owner-ordered, 2026-08-28).

The registry is the single price authority for BOTH eval suites; a malformed
card silently corrupts every cost number downstream. Structural rules only —
price VALUES are verified against provider pages at authoring time (the card
comments carry the dates), not re-fetched here.
"""
from __future__ import annotations

import json
from pathlib import Path

from tests.eval_common.models_registry import AS_OF, MODELS, spec

_KNOWN_PROVIDERS = {"openai", "anthropic", "gemini", "xai"}


def test_every_card_is_structurally_sound():
    assert AS_OF and len(AS_OF) == 10
    for key, m in MODELS.items():
        assert m.key == key, f"{key}: key/spec.key mismatch"
        assert m.provider in _KNOWN_PROVIDERS, f"{key}: provider {m.provider!r}"
        assert m.model_id, f"{key}: empty model_id"
        assert m.tier in ("cheap", "frontier"), f"{key}: tier {m.tier!r}"
        assert m.price.in_per_mtok > 0 and m.price.out_per_mtok > 0, key
        # output >= input holds for every completion model we buy; a flip is
        # almost always a transposed card
        assert m.price.out_per_mtok >= m.price.in_per_mtok, f"{key}: in/out transposed?"
        if m.price.cached_in_per_mtok is not None:
            assert 0 < m.price.cached_in_per_mtok <= m.price.in_per_mtok, (
                f"{key}: cached_in must be a discount on in")


def test_unknown_key_is_loud():
    try:
        spec("no-such-model")
    except KeyError as e:
        assert "no-such-model" in str(e)
    else:
        raise AssertionError("unknown key must raise")


def test_every_grading_config_resolves_to_a_card():
    suite = Path(__file__).resolve().parents[1] / "grading_eval_suite" / "configs"
    for p in sorted(suite.glob("*.json")):
        cfg = json.loads(p.read_text(encoding="utf-8"))
        m = spec(cfg["model_key"])          # KeyError = failure
        assert m.provider in _KNOWN_PROVIDERS
