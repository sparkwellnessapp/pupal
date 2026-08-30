"""Self-tests for multi-provider model switching (no API calls, no provider
packages required — everything tested here is a pure function by design).

Covers:
1. _llm_params per-family constructor policy (the reasoning-family temperature
   omission is the load-bearing case: passing temperature=0 to gpt-5.x/o-series
   is an API error, silently absent from any unit test that mocks the LLM).
2. _call_meta_from_raw against faked metadata shapes of all three providers,
   including the legacy OpenAI token_usage fallback.
3. The scorer's truncation guard firing on every provider's truncation string
   and NOT firing on every provider's normal-stop string.
4. runner._config_env_overrides round-trip (registry-sourced identity + knobs).
5. Sweep configs resolve through the shared registry (2026-08-23 migration):
   identity/prices are registry-owned; the legacy split-brain keys stay gone;
   the shared cost formula reproduces the legacy formula on a real record.

Run: PYTHONPATH=. python tests/rubric_eval_suite/test_llm_policy.py
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from app.services.docx_v3.pipeline import _llm_params, _call_meta_from_raw, _is_openai_reasoning
from tests.rubric_eval_suite.runner import _config_env_overrides
from tests.rubric_eval_suite.runner import score_only  # noqa: F401 (import sanity)

SUITE_DIR = Path(__file__).resolve().parent


def test_param_policy_per_family():
    """EXACT-DICT equality is deliberate and must stay exact (never relax to subset
    matching): this pin is the tripwire that caught the reasoning_effort drift. PR-2
    adds `timeout` + `max_retries=0` to the bounded providers, so the EXPECTED VALUES
    change — the assertion style does not."""
    # T is the ruled default (360s); pin it explicitly so a silent default change fails here.
    T = 360.0
    BOUND = {"timeout": T, "max_retries": 0}   # bound + disabled-hidden-layer travel together

    # openai reasoning family: temperature MUST be absent; effort passes through
    p = _llm_params("openai", "gpt-5.5", 32000, "high")
    assert "temperature" not in p, "reasoning family rejects non-default temperature"
    assert p == {"max_tokens": 32000, "reasoning_effort": "high", **BOUND}
    # effort omitted when not set (don't send a null knob)
    p = _llm_params("openai", "o3", None, None)
    assert p == {"max_tokens": 32000, **BOUND}
    # family detection includes the cheap nano tier (also reasoning-family API)
    assert _is_openai_reasoning("gpt-5.4-nano-2026-03-17")
    # openai non-reasoning: original generation policy preserved, now bounded
    assert _llm_params("openai", "gpt-4o", None, None) == {
        "temperature": 0, "max_tokens": 12000, **BOUND}
    # reasoning_effort is meaningless for non-reasoning family — policy drops it
    assert "reasoning_effort" not in _llm_params("openai", "gpt-4o", None, "high")
    # anthropic: temperature pinned, api-required max_tokens defaulted, bounded
    assert _llm_params("anthropic", "claude-sonnet-4-6", None, None) == {
        "temperature": 0, "max_tokens": 16000, **BOUND}
    # gemini: provider-correct kwarg name — DELIBERATELY UNBOUNDED (branch is
    # undeployable: langchain_google_genai is not installed; bounding it is a
    # separate decision, not a PR-2 side effect)
    assert _llm_params("gemini", "gemini-3.1-pro-preview", 16000, None) == {
        "temperature": 0, "max_output_tokens": 16000}
    # xai (grok, OpenAI-compatible reasoning family): temperature omitted, bounded;
    # effort passes through only when explicitly set
    assert _llm_params("xai", "grok-4.6", None, None) == {"max_tokens": 32000, **BOUND}
    assert _llm_params("xai", "grok-4.6", 16000, "low") == {
        "max_tokens": 16000, "reasoning_effort": "low", **BOUND}
    # config override wins over family default
    assert _llm_params("openai", "gpt-5.5", 64000, None)["max_tokens"] == 64000
    # PR-2: the timeout is injectable (env-tunable at the caller); max_retries stays 0
    p = _llm_params("openai", "gpt-5.5", 32000, None, timeout_s=120.0)
    assert p == {"max_tokens": 32000, "timeout": 120.0, "max_retries": 0}
    print("  [ok] per-family constructor policy (reasoning temp omission, kwarg names, defaults, PR-2 bounds)")


def _fake(usage_metadata=None, response_metadata=None):
    return SimpleNamespace(usage_metadata=usage_metadata, response_metadata=response_metadata or {})


def test_provenance_shapes_all_providers():
    # openai modern: normalized usage_metadata + finish_reason
    m = _call_meta_from_raw(_fake({"input_tokens": 100, "output_tokens": 50},
                                  {"finish_reason": "stop"}), "gpt-5.5")
    assert (m["input_tokens"], m["output_tokens"], m["finish_reason"]) == (100, 50, "stop")
    # anthropic: stop_reason key
    m = _call_meta_from_raw(_fake({"input_tokens": 7, "output_tokens": 3},
                                  {"stop_reason": "end_turn"}), "claude-sonnet-4-6")
    assert m["finish_reason"] == "end_turn"
    # gemini: uppercase finish_reason
    m = _call_meta_from_raw(_fake({"input_tokens": 5, "output_tokens": 2},
                                  {"finish_reason": "MAX_TOKENS"}), "gemini-3.1-pro-preview")
    assert m["finish_reason"] == "MAX_TOKENS"
    # legacy openai fallback: no usage_metadata, token_usage shape
    m = _call_meta_from_raw(_fake(None, {"token_usage": {"prompt_tokens": 11, "completion_tokens": 4},
                                         "finish_reason": "length"}), "gpt-4o")
    assert (m["input_tokens"], m["output_tokens"], m["finish_reason"]) == (11, 4, "length")
    print("  [ok] provenance extraction across openai/anthropic/gemini metadata shapes")


def test_truncation_guard_per_provider():
    """The guard is scoring-side (case-insensitive vs {MAX_TOKENS, LENGTH}).
    Prove it fires on every provider's truncation string and passes every
    provider's normal stop — via score_only's validity path (GT vs GT with the
    finish_reason injected, so any invalidity is attributable to the guard alone)."""
    import json
    from app.schemas.ontology_types import ExtractRubricResponse
    gt_path = sorted((SUITE_DIR / "benchmarks").glob("*.json"))[0]
    g = ExtractRubricResponse.model_validate_json(gt_path.read_text(encoding="utf-8"))
    for fr, should_be_valid in [("length", False), ("MAX_TOKENS", False),
                                ("max_tokens", False), ("stop", True),
                                ("end_turn", True), ("STOP", True)]:
        rs = score_only(g, g, "x", meta={"rubric_name": gt_path.stem, "finish_reason": fr})
        assert rs.valid is should_be_valid, (fr, rs.valid, rs.invalid_reason)
    print("  [ok] truncation guard: fires on length/MAX_TOKENS/max_tokens; passes stop/end_turn/STOP")


def test_config_env_round_trip():
    from tests.eval_common.models_registry import spec
    # Identity ALWAYS comes from the registry spec — and it is the SDK
    # model_id, not the registry key (chatgpt-4o-mini -> gpt-4o-mini is the
    # proving pair: a key/id divergence must send the ID down the wire).
    s = spec("chatgpt-4o-mini")
    full = _config_env_overrides({"model_key": "chatgpt-4o-mini",
                                  "max_output_tokens": 32000,
                                  "reasoning_effort": "high"}, s)
    assert full == {"EXTRACTION_LLM_MODEL": "gpt-4o-mini",
                    "EXTRACTION_LLM_PROVIDER": "openai",
                    "EXTRACTION_LLM_MAX_TOKENS": "32000",
                    "EXTRACTION_LLM_REASONING_EFFORT": "high"}
    # minimal config: absent knobs must NOT appear (never clobber ambient env
    # with 'None') — but identity is ALWAYS present (F2: no ambient leakage)
    s2 = spec("gpt-4o")
    assert _config_env_overrides({"model_key": "gpt-4o", "reasoning_effort": None}, s2) == {
        "EXTRACTION_LLM_MODEL": "gpt-4o", "EXTRACTION_LLM_PROVIDER": "openai"}
    print("  [ok] config→env mapping (registry identity incl. key≠id, knobs, no None-clobbering)")


# The legal reasoning_effort domain (None = knob absent, for non-reasoning providers).
# No shared enum exists — reasoning_effort is a passthrough str in _llm_params — so the
# set is named here, at the one place that shape-checks it.
_LEGAL_EFFORTS = {None, "minimal", "low", "medium", "high"}


def test_sweep_configs_resolve_through_registry():
    import json
    from tests.eval_common.models_registry import spec
    # Identity/prices are REGISTRY-owned (2026-08-23): the config carries only
    # the key + knobs + this suite's economics. Pinning provider/prices HERE,
    # against the registry, keeps the split-brain guard — a price move must
    # happen in the registry (announced by registry_as_of + suite_hash), never
    # in a config. reasoning_effort stays NOT pinned: it is a designated sweep
    # variable whose intent lives in the config diff + results.json provenance
    # (one concept, one place). Pinning its value here would duplicate that
    # intent and red the battery on every legitimate sweep, training reflexive
    # test edits that erode the guard. Shape only: key present, value legal.
    # Ceilings pinned per config: gpt-5.5 at 1.00 (owner ruling 2026-08-23);
    # the non-openai sweeps keep the loose 2.00 pathology-detection ceiling.
    # The gpt-5.6 sweep (2026-08-23) pins its three per-model MEDIUM anchors
    # here; the -low/-high effort variants stay unpinned for the same reason
    # gpt-5.5-low is (effort is the designated sweep variable). sol is pinned
    # at the LIST card (5.00/30.00) — the registry note explains why the
    # promotional 4.00/20.00 is deliberately not what we cost against.
    expected = {"gpt-5.5": ("openai", 5.00, 30.00, 1.00),
                "gpt-5.6-luna": ("openai", 0.20, 1.20, 1.00),
                "gpt-5.6-terra": ("openai", 2.00, 12.00, 1.00),
                "gpt-5.6-sol": ("openai", 5.00, 30.00, 1.00),
                "claude-sonnet-4-6": ("anthropic", 3.00, 15.00, 2.00),
                "gemini-3.1-pro-preview": ("gemini", 2.00, 12.00, 2.00),
                "grok-4.6": ("xai", 2.00, 6.00, 2.00)}
    for name, (prov, pin, pout, ceiling) in expected.items():
        cfg = json.loads((SUITE_DIR / "configs" / f"{name}.json").read_text(encoding="utf-8"))
        assert cfg["model_key"] == name
        # the legacy split-brain keys must be gone AND stay gone (D6/D7)
        assert not ({"model", "provider", "price_per_1m_input", "price_per_1m_output",
                     "temperature", "pipeline_version"} & cfg.keys()), name
        s = spec(cfg["model_key"])
        assert s.provider == prov
        assert (s.price.in_per_mtok, s.price.out_per_mtok) == (pin, pout)
        assert cfg["cost_ceiling"] == ceiling, (name, cfg["cost_ceiling"])
        assert "reasoning_effort" in cfg, f"{name}: reasoning_effort key absent"
        assert cfg["reasoning_effort"] in _LEGAL_EFFORTS, (name, cfg["reasoning_effort"])
        # the (provider, model_id, knobs) triple constructs cleanly
        _llm_params(s.provider, s.model_id, cfg.get("max_output_tokens"), cfg.get("reasoning_effort"))
    print("  [ok] sweep configs resolve through the registry; prices/provider pinned there, effort shape-valid")


def test_cost_parity_with_legacy_formula():
    """Comparability receipt for the 2026-08-23 migration: with cached input
    absent/zero, the shared cost_usd (two_phase/instrument.py) is algebraically
    identical to the legacy config-scalar formula. Pinned on a REAL historical
    record — bagrut_899371 in results/20260726-144104_gpt-5.5 wrote
    cost_usd=0.50122 for in=18968/out=13546 at 5.00/30.00. The migration must
    not move a single historical cost number."""
    from app.services.transcription.two_phase.instrument import cost_usd
    from app.services.transcription.vlm_provider import Usage
    from tests.eval_common.models_registry import spec
    got = cost_usd(Usage(input_tokens=18968, output_tokens=13546,
                         cached_input_tokens=None), spec("gpt-5.5").price)
    assert abs(got - 0.50122) < 1e-9, got
    # and the cached path bills BELOW the uncached path (the F4 fix direction)
    cached = cost_usd(Usage(input_tokens=18968, output_tokens=13546,
                            cached_input_tokens=10000), spec("gpt-5.5").price)
    assert cached < got
    print("  [ok] shared cost_usd reproduces the legacy formula on a real record; cached path discounts")


def test_construction_wiring_all_branches():
    """Inject fake provider modules to verify the env -> _llm_params -> constructor
    chain end-to-end for all three branches (the packages aren't installed here;
    construction is lazy-imported, so fakes in sys.modules are sufficient)."""
    import os
    import types
    from app.services.docx_v3.pipeline import _get_llm

    captured = {}
    def make_fake(modname, clsname):
        mod = types.ModuleType(modname)
        def ctor(**kwargs): captured[clsname] = kwargs; return SimpleNamespace(kind=clsname, **kwargs)
        setattr(mod, clsname, ctor)
        sys.modules[modname] = mod
    make_fake("langchain_openai", "ChatOpenAI")
    make_fake("langchain_anthropic", "ChatAnthropic")
    make_fake("langchain_google_genai", "ChatGoogleGenerativeAI")
    saved = {k: os.environ.get(k) for k in
             ("EXTRACTION_LLM_MAX_TOKENS", "EXTRACTION_LLM_REASONING_EFFORT",
              "EXTRACTION_LLM_TIMEOUT_S")}
    # PR-2: the bound + the disabled hidden SDK layer. This is the ACCEPTANCE
    # assertion "no LLM client is constructed without an explicit timeout and
    # max_retries=0" — enforced at the constructor, where it cannot be evaded.
    BOUND = {"timeout": 360.0, "max_retries": 0}
    try:
        os.environ.pop("EXTRACTION_LLM_TIMEOUT_S", None)      # exercise the ruled default
        os.environ["EXTRACTION_LLM_MAX_TOKENS"] = "32000"
        os.environ["EXTRACTION_LLM_REASONING_EFFORT"] = "high"
        _get_llm("openai", "gpt-5.5")
        assert captured["ChatOpenAI"] == {"model": "gpt-5.5", "max_tokens": 32000,
                                          "reasoning_effort": "high", **BOUND}
        os.environ.pop("EXTRACTION_LLM_REASONING_EFFORT")
        os.environ["EXTRACTION_LLM_MAX_TOKENS"] = "16000"
        _get_llm("anthropic", "claude-sonnet-4-6")
        assert captured["ChatAnthropic"] == {"model": "claude-sonnet-4-6",
                                             "temperature": 0, "max_tokens": 16000, **BOUND}
        # gemini is DELIBERATELY unbounded (undeployable branch — see _llm_params)
        _get_llm("gemini", "gemini-3.1-pro-preview")
        assert captured["ChatGoogleGenerativeAI"] == {"model": "gemini-3.1-pro-preview",
                                                      "temperature": 0, "max_output_tokens": 16000}
        # no knobs in env -> family defaults apply (still bounded)
        os.environ.pop("EXTRACTION_LLM_MAX_TOKENS")
        _get_llm("openai", "gpt-4o")
        assert captured["ChatOpenAI"] == {"model": "gpt-4o", "temperature": 0,
                                          "max_tokens": 12000, **BOUND}
        # the timeout is env-tunable (the #1 knob to watch at the next k-run)
        os.environ["EXTRACTION_LLM_TIMEOUT_S"] = "120"
        _get_llm("openai", "gpt-4o")
        assert captured["ChatOpenAI"]["timeout"] == 120.0
        assert captured["ChatOpenAI"]["max_retries"] == 0, "the hidden SDK layer stays OFF"
        # xai: same ChatOpenAI client re-pointed at the x.ai endpoint with its own key
        os.environ.pop("EXTRACTION_LLM_TIMEOUT_S", None)
        saved_xai = os.environ.get("XAI_API_KEY")
        os.environ["XAI_API_KEY"] = "xai-test-key"
        try:
            _get_llm("xai", "grok-4.6")
            # streaming=True is LOAD-BEARING for xai (non-streaming hangs — see
            # pipeline._get_llm); stream_usage keeps token/cost accounting.
            assert captured["ChatOpenAI"] == {
                "model": "grok-4.6", "api_key": "xai-test-key",
                "base_url": "https://api.x.ai/v1", "streaming": True,
                "stream_usage": True, "max_tokens": 32000, **BOUND}
        finally:
            if saved_xai is None: os.environ.pop("XAI_API_KEY", None)
            else: os.environ["XAI_API_KEY"] = saved_xai
    finally:
        for k, v in saved.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        for m in ("langchain_openai", "langchain_anthropic", "langchain_google_genai"):
            sys.modules.pop(m, None)
    print("  [ok] construction wiring: env knobs -> params -> constructor, all branches BOUNDED")


if __name__ == "__main__":
    test_param_policy_per_family()
    test_provenance_shapes_all_providers()
    test_truncation_guard_per_provider()
    test_config_env_round_trip()
    test_sweep_configs_resolve_through_registry()
    test_cost_parity_with_legacy_formula()
    test_construction_wiring_all_branches()
    print("ALL LLM-POLICY SELF-TESTS PASSED")
