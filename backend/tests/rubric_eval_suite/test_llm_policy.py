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
4. runner._config_env_overrides round-trip (full config, minimal config).

Run: PYTHONPATH=. python tests/rubric_eval_suite/tests/test_llm_policy.py
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

from app.services.docx_v3.pipeline import _llm_params, _call_meta_from_raw, _is_openai_reasoning
from tests.rubric_eval_suite.runner import _config_env_overrides
from tests.rubric_eval_suite.runner import score_only  # noqa: F401 (import sanity)


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
    from pathlib import Path
    from app.schemas.ontology_types import ExtractRubricResponse
    gt_path = sorted(Path("tests/rubric_eval_suite/benchmarks").glob("*.json"))[0]
    g = ExtractRubricResponse.model_validate_json(gt_path.read_text())
    for fr, should_be_valid in [("length", False), ("MAX_TOKENS", False),
                                ("max_tokens", False), ("stop", True),
                                ("end_turn", True), ("STOP", True)]:
        rs = score_only(g, g, "x", meta={"rubric_name": gt_path.stem, "finish_reason": fr})
        assert rs.valid is should_be_valid, (fr, rs.valid, rs.invalid_reason)
    print("  [ok] truncation guard: fires on length/MAX_TOKENS/max_tokens; passes stop/end_turn/STOP")


def test_config_env_round_trip():
    full = _config_env_overrides({"model": "gpt-5.5", "provider": "openai",
                                  "max_output_tokens": 32000, "reasoning_effort": "high"})
    assert full == {"EXTRACTION_LLM_MODEL": "gpt-5.5",
                    "EXTRACTION_LLM_PROVIDER": "openai",
                    "EXTRACTION_LLM_MAX_TOKENS": "32000",
                    "EXTRACTION_LLM_REASONING_EFFORT": "high"}
    # minimal config: absent knobs must NOT appear (never clobber ambient env with 'None')
    assert _config_env_overrides({"model": "gpt-4o", "reasoning_effort": None}) == {
        "EXTRACTION_LLM_MODEL": "gpt-4o"}
    print("  [ok] config→env mapping (full + minimal, no None-clobbering)")


# The legal reasoning_effort domain (None = knob absent, for non-reasoning providers).
# No shared enum exists — reasoning_effort is a passthrough str in _llm_params — so the
# set is named here, at the one place that shape-checks it.
_LEGAL_EFFORTS = {None, "minimal", "low", "medium", "high"}


def test_sweep_configs_load_and_pair_prices():
    import json
    from pathlib import Path
    # prices/provider/model ARE pinned — the split-brain guard; they are not sweep
    # variables. reasoning_effort is NOT pinned: it is a designated sweep variable whose
    # intent lives in the config diff + results.json provenance (one concept, one place).
    # Pinning its value here would duplicate that intent and red the battery on every
    # legitimate sweep, training reflexive test edits that erode the guard. Shape only:
    # key present, value in the legal set.
    expected = {"gpt-5.5": ("openai", 5.00, 30.00),
                "claude-sonnet-4-6": ("anthropic", 3.00, 15.00),
                "gemini-3.1-pro-preview": ("gemini", 2.00, 12.00)}
    for name, (prov, pin, pout) in expected.items():
        cfg = json.loads(Path(f"tests/rubric_eval_suite/configs/{name}.json").read_text())
        assert cfg["provider"] == prov and cfg["model"] == name
        assert (cfg["price_per_1m_input"], cfg["price_per_1m_output"]) == (pin, pout)
        assert "reasoning_effort" in cfg, f"{name}: reasoning_effort key absent"
        assert cfg["reasoning_effort"] in _LEGAL_EFFORTS, (name, cfg["reasoning_effort"])
        assert cfg["cost_ceiling"] == 2.00
        # the model/prices pairing lives in ONE artifact — the split-brain guard
        _llm_params(prov, cfg["model"], cfg.get("max_output_tokens"), cfg.get("reasoning_effort"))
    print("  [ok] three sweep configs load; prices/provider/model pinned, effort shape-valid")


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
    test_sweep_configs_load_and_pair_prices()
    test_construction_wiring_all_branches()
    print("ALL LLM-POLICY SELF-TESTS PASSED")
