"""
Runner — orchestrates grade | score_only over the fixture manifests [§3/§7].

grade      : REAL GraderAgent against compiled contracts (the authoritative
             surface; ~$0.03 and ~5s/test expected). k>=5 is authoritative;
             k=1 is PROVISIONAL in every artifact it touches [§3].
score_only : re-score the cached drafts of a prior run for $0 — the mode used
             for ALL instrument debugging [§3].
--scopes   : diagnostic subset of one fixture; totals suppressed; PROVISIONAL.

Trial validity policy [§7]:
  * per-trial wall bound (default 300 s) — the SUT has no timeout of its own
    (G-3, PR-7's territory; this mission only SURVIVES it, never fixes it).
  * exactly ONE re-run per trial, on retryable transport failure only —
    wall-bound hits count as transport hangs [DL-3]. No other retry layer is
    added around the agent (the standing rule; the SDK already hides retries).
  * parse failures are DETERMINISTIC model behavior: scored, never re-run [R6].

Provenance [§9]: suite_hash (instrument + snapshots + shared registry — D3),
model_key + registry_as_of + models block (cross-suite join keys),
GRADING_PROMPT_VERSION, config, k, mode.

The D6 model seam LANDED with the grader-v5 mission (V5-A, 2026-08-28): every
grade-mode agent is constructed through llm_factory from the registry spec, and
DL-4's guarantee got STRONGER — after every trial the runner asserts
draft.model_version == spec.model_id, i.e. what actually ran, not what the env
intended. Config keys (all beyond model_key optional):
  architecture  "v3" (GraderAgent, default) | "v5" (PlanVerifyGrader)
  plan          v5 only, REQUIRED there: suite-relative path to the ratified
                GradingPlan JSON; validated against the fixture's contract and
                hash-pinned before any spend
  sc_n          v5 only: SC-3 self-consistency call count (odd; default 1)
  params        {"reasoning_effort": ...} — seam params for the factory
"""
from __future__ import annotations

import argparse
import asyncio
import os
import datetime as _dt
import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

from app.agents.grader.prompt import GRADING_PROMPT_VERSION, effective_prompt_version
from app.schemas.graded_test_draft import GradedTestDraft
from app.services.transcription.two_phase.instrument import cost_usd
from app.services.transcription.vlm_provider import Usage
from tests.eval_common.models_registry import AS_OF as REGISTRY_AS_OF, ModelSpec
from tests.eval_common.models_registry import MODELS as _REGISTRY_MODELS
from tests.eval_common.models_registry import spec as model_spec

from . import reporting
from .fixtures import (
    SUITE_DIR,
    FixtureBundle,
    assert_blind_sequencing,
    load_bundle,
)
from .schemas import SuiteResult, TrialScore
from .scoring import _classify_failed_scopes, score_trial

load_dotenv(Path(__file__).resolve().parents[2] / ".env")   # backend/.env

RESULTS_DIR = SUITE_DIR / "results"
TRIAL_WALL_S = 300.0        # [§7] per-trial wall bound
_LEGACY_CONFIG_KEYS = ("model", "provider", "price_per_1m_input", "price_per_1m_output")


# ---------------------------------------------------------------------------
# Config [P14: config = experiment record; registry-era discipline]
# ---------------------------------------------------------------------------

def _load_config(name: str, *, suite_dir: Path = SUITE_DIR) -> dict:
    p = suite_dir / "configs" / f"{name}.json"
    config = json.loads(p.read_text(encoding="utf-8"))
    _validate_config(name, config)
    return config


def _validate_config(name: str, config: dict) -> None:
    """The config rules, PURE — so they can be tested without writing a file.

    A config is an experiment record [P14], so every rule here refuses rather
    than repairs: a run that silently corrected its own config would produce a
    record of something that did not happen."""
    legacy = [k for k in _LEGACY_CONFIG_KEYS if k in config]
    if legacy:
        raise SystemExit(
            f"config '{name}' carries legacy identity/price keys {legacy}: identity "
            f"and prices are registry-owned — use 'model_key' "
            f"(tests/eval_common/models_registry.py).")
    if not config.get("model_key"):
        raise SystemExit(f"config '{name}' has no 'model_key' — required.")
    arch = config.get("architecture", "v3")
    if arch not in ("v3", "v5"):
        raise SystemExit(f"config '{name}': architecture must be v3|v5, got {arch!r}.")
    # [two-exam harness] v5 needs a plan; it may name ONE ('plan', the legacy
    # single-exam key) or a MAP ('plans', exam_id -> path). Both, and neither,
    # are refused: two ways to answer one question is how a run silently grades
    # under the plan nobody meant (§0.4).
    if arch == "v5" and not (config.get("plan") or config.get("plans")):
        raise SystemExit(
            f"config '{name}': architecture v5 requires 'plan' (single exam) "
            f"or 'plans' (a map of exam_id -> plan path).")
    if config.get("plan") and config.get("plans"):
        raise SystemExit(
            f"config '{name}': names BOTH 'plan' and 'plans'. Pick one — with "
            f"both, which plan grades a fixture depends on resolution order "
            f"rather than on intent.")
    if arch != "v5" and (config.get("plan") or config.get("plans")
                         or config.get("sc_n")):
        raise SystemExit(f"config '{name}': 'plan'/'plans'/'sc_n' are v5-only keys.")
    casc = config.get("cascade")
    if casc is not None:
        if arch != "v5":
            raise SystemExit(f"config '{name}': cascade requires architecture v5.")
        if not casc.get("base_model_key"):
            raise SystemExit(f"config '{name}': cascade.base_model_key required.")


def _assert_draft_stamp(draft: Optional[GradedTestDraft], spec: ModelSpec) -> None:
    """[DL-4 successor, seam era] provenance may never claim a model the SUT
    didn't run — now asserted against what ACTUALLY ran: the draft's own
    model_version stamp, per trial, not the process env before the run.
    [COST_TRUTH] plus the PROVIDER-reported ids: every served model must be
    the requested one modulo the provider's date-suffix convention
    (gpt-4o -> gpt-4o-2024-08-06); anything else is a truth failure."""
    if draft is None:
        return
    if draft.cascade_usage is not None:
        # [cascade] the draft's own usage split names the allowed model set
        allowed = tuple(draft.cascade_usage.keys())
        if spec.model_id not in allowed:
            raise SystemExit(
                f"cascade stamp mismatch: champion {spec.model_id!r} not in the "
                f"draft's tier set {allowed!r}.")
        for served in draft.served_models or []:
            if not any(served.startswith(m) or m.startswith(served)
                       for m in allowed):
                raise SystemExit(
                    f"COST_TRUTH: cascade served {served!r} outside its tier "
                    f"set {allowed!r}.")
        return
    if draft.model_version != spec.model_id:
        raise SystemExit(
            f"model stamp mismatch: config resolves to model_id={spec.model_id!r} "
            f"but the draft was graded by {draft.model_version!r} — the seam "
            f"wiring is broken; provenance may never claim a model the SUT "
            f"didn't run.")
    for served in draft.served_models or []:
        if not (served.startswith(spec.model_id) or spec.model_id.startswith(served)):
            raise SystemExit(
                f"COST_TRUTH: provider served {served!r} for a request pinned to "
                f"{spec.model_id!r} — halt before spend accrues to the wrong "
                f"card; verify the registry model_id.")


# ---------------------------------------------------------------------------
# Provenance [§9]
# ---------------------------------------------------------------------------

def _hashed_paths() -> List[Path]:
    """[D3] the instrument + snapshots + the shared registry. Configs are
    DELIBERATELY excluded (the A/B knob — sibling precedent)."""
    paths = sorted(SUITE_DIR.glob("*.py"))
    paths += sorted((SUITE_DIR / "tools").glob("*.py")) if (SUITE_DIR / "tools").exists() else []
    for sub in ("benchmarks", "fixtures", "plans"):
        d = SUITE_DIR / sub
        if d.exists():
            paths += sorted(p for p in d.rglob("*") if p.is_file())
    registry = SUITE_DIR.parents[0] / "eval_common" / "models_registry.py"
    paths.append(registry)
    # [two-exam harness] Every artifact a fixture manifest REFERENCES, wherever
    # it lives. The globs above assume exam 1's layout (benchmarks/…); exam 2
    # landed its contract and transcriptions at the suite root, so they were
    # outside the instrument hash entirely — the exam-2 contract could change
    # and suite_hash would not move, which is the one thing it exists to
    # prevent, failing silently.
    #
    # Resolved from the manifests rather than by adding another glob, so this is
    # the CLASS fix: a third exam dropping files somewhere new is covered by
    # construction, and layout goes back to being a matter of taste.
    paths += _manifest_referenced_paths()
    return sorted(set(paths))


_MANIFEST_ARTIFACT_KEYS = ("rubric_contract", "transcription_contract", "gt")


def _manifest_referenced_paths() -> List[Path]:
    """Files named by any `fixtures/*.json`. Missing ones are SKIPPED, not
    fatal: a manifest legitimately points at a GT the owner has not authored
    yet, and hashing the instrument is not the place to enforce R1."""
    out: List[Path] = []
    manifest_dir = SUITE_DIR / "fixtures"
    if not manifest_dir.exists():
        return out
    for manifest_path in sorted(manifest_dir.glob("*.json")):
        try:
            data = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        for key in _MANIFEST_ARTIFACT_KEYS:
            ref = data.get(key)
            if isinstance(ref, str) and ref.strip():
                candidate = SUITE_DIR / ref.strip()
                if candidate.is_file():
                    out.append(candidate)
    return out


# [sut_hash, owner ruling 2026-08-27] suite_hash pins the INSTRUMENT; this pins
# the SYSTEM UNDER TEST. Two runs are comparable only if the grader-path code is
# byte-identical — previously an assumption, now a recorded fact stamped in every
# results.json. Deliberately DISJOINT from _hashed_paths(): the instrument can
# change without the SUT changing and vice versa, and a single combined hash
# would make a C2<->E7 comparison unverifiable.
_BACKEND_ROOT = SUITE_DIR.parents[1]
_SUT_RELPATHS = (
    "app/agents/grader/grader.py",
    "app/agents/grader/prompt.py",
    "app/agents/grader/schemas.py",
    "app/agents/grader/validator.py",
    "app/agents/grader/plan_schemas.py",
    "app/agents/grader/plan_validator.py",
    "app/agents/grader/pricer.py",
    "app/agents/grader/verifier_prompt.py",
    "app/agents/grader/grader_v5.py",
    "app/agents/grader/grader_cascade.py",
    "app/agents/grader/llm_factory.py",
    "app/services/gradable_compiler.py",
    "app/services/selection_scoring.py",
    "app/schemas/graded_test_draft.py",
    "app/schemas/gradable.py",
    "app/schemas/ontology_types.py",
)


def _sut_paths() -> List[Path]:
    return [_BACKEND_ROOT / rel for rel in _SUT_RELPATHS]


def _sut_hash() -> str:
    """sha256 over exactly the grader-path file set, computed at run time."""
    h = hashlib.sha256()
    for p in _sut_paths():
        h.update(p.relative_to(_BACKEND_ROOT).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _suite_hash() -> str:
    h = hashlib.sha256()
    for p in _hashed_paths():
        h.update(p.as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _apply_prior_context_flag(config: dict) -> bool:
    """[PR-G1 item 4] config key prior_context (default false) -> the env flag
    the prompt layer reads. Set explicitly BOTH ways so a stale ambient value
    can never leak into a run; returns the effective state for provenance."""
    on = bool(config.get("prior_context", False))
    if on:
        os.environ["GRADER_PRIOR_CONTEXT_ENABLED"] = "1"
    else:
        os.environ.pop("GRADER_PRIOR_CONTEXT_ENABLED", None)
    return on


def _effective_prompt_version_for(config: dict) -> str:
    if config.get("architecture") == "v5":
        from app.agents.grader.verifier_prompt import VERIFIER_PROMPT_VERSION
        return VERIFIER_PROMPT_VERSION
    return effective_prompt_version()


def _provenance(config_name: str, config: dict, spec: ModelSpec, *,
                mode: str, k: int, fixtures: List[str],
                scopes: Optional[List[str]],
                gt_sources: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    import dataclasses
    prov = {
        "config": config_name, "mode": mode, "k": k, "fixtures": fixtures,
        "scopes": scopes,
        "model_key": spec.key, "model_version": spec.model_id,
        "registry_as_of": REGISTRY_AS_OF,
        "models": {spec.key: {"model_id": spec.model_id, "provider": spec.provider,
                              "tier": spec.tier,
                              "price": dataclasses.asdict(spec.price)}},
        # [PR-G1 item 4] stamped version is a pure function of code + flag;
        # [2026-08-28 flashlite-screen fix] v5 runs report the VERIFIER prompt —
        # the run-level field must agree with what the drafts stamp
        "prompt_version": _effective_prompt_version_for(config),
        "prior_context": bool(config.get("prior_context", False)),
        # [M1] gt_source surfaced per fixture in results.json
        "gt_sources": gt_sources or {},
        "suite_hash": _suite_hash(),
        # [2026-08-27] proof of the CODE this run measured (grader path only)
        "sut_hash": _sut_hash(),
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "cost_ceiling": config.get("cost_ceiling"),
        "trial_wall_s": TRIAL_WALL_S,
    }
    prov["architecture"] = config.get("architecture", "v3")
    prov["params"] = config.get("params") or {}
    if config.get("architecture") == "v5":
        prov["sc_n"] = int(config.get("sc_n", 1))
        # The config as written. `prov["plans"]` (added after the fixtures are
        # known) is what says which plan actually graded which exam.
        prov["plan"] = config.get("plan")
        if config.get("plans"):
            prov["plan_map"] = config["plans"]
    if k == 1:
        prov["PROVISIONAL"] = "k=1 — provisional in every artifact it touches"
    elif k < 5:
        # [mission §1.4] k=3 results are SCREENING and never justify adoption
        prov["SCREENING"] = f"k={k} < 5 — screening tier; adoption needs k=5"
    return prov


# ---------------------------------------------------------------------------
# Grade mode
# ---------------------------------------------------------------------------

def _load_plan(config: dict, bundle: FixtureBundle, suite_dir: Path):
    """Load + validate the v5 GradingPlan for this bundle. Refuses (loud, before
    any spend) on: validator errors, or a plan pinned to different contract
    bytes than the fixture's snapshot [D5 discipline extended to plans].

    [two-exam harness] The plan is resolved BY THE FIXTURE'S exam_id, not from a
    single run-level key. The contract-hash pin below is what made a two-exam run
    impossible rather than wrong before this — a hobby plan meeting a bagrut
    fixture stopped the run loudly. This lifts that correct refusal into a
    correct resolution; the refusal stays exactly where it was.

    Returns (plan, plan_sha256, resolved)."""
    from app.agents.grader.plan_schemas import GradingPlan
    from app.agents.grader.plan_validator import validate_plan
    from .exam_resolution import ExamResolutionError, resolve_plan
    resolved = resolve_plan(bundle.exam_id, config,
                            fixture=bundle.name, suite_dir=suite_dir)
    if resolved is None:
        raise SystemExit(
            f"{bundle.name}: architecture v5 requires a plan, and the config "
            f"names neither 'plans' (by exam_id) nor 'plan'.")
    plan_path = resolved.path
    plan = GradingPlan.model_validate_json(plan_path.read_text(encoding="utf-8"))
    if bundle.rubric_contract_hash and             plan.rubric_contract_sha256 != bundle.rubric_contract_hash:
        raise SystemExit(
            f"plan {plan.plan_version!r} is pinned to contract sha "
            f"{plan.rubric_contract_sha256[:12]}… but fixture {bundle.name!r} "
            f"snapshots {str(bundle.rubric_contract_hash)[:12]}… — re-ratify the "
            f"plan against the current contract (owner decision, never silent).")
    errs = validate_plan(
        plan,
        contract_terminal_points={tid: info.points
                                  for tid, info in bundle.terminal_infos.items()},
        terminal_scopes={tid: (info.question_id if info.sub_question_id is None
                               else f"{info.question_id}.{info.sub_question_id}")
                         for tid, info in bundle.terminal_infos.items()},
        precision=bundle.rubric_contract.numeric_policy.precision)
    if errs:
        raise SystemExit(f"plan {plan.plan_version!r} failed validation against "
                         f"{bundle.name!r}:\n  " + "\n  ".join(errs))
    # [owner H-4 item 3, 2026-08-28] the expressibility guard is PRE-SPEND:
    # a plan that cannot express the fixture's ratified GT awards never grades.
    if bundle.gt is not None:
        from .plan_expressibility import expressibility_errors
        errs = expressibility_errors(
            plan, bundle.gt, bundle.terminal_infos,
            bundle.rubric_contract.numeric_policy.precision)
        if errs:
            raise SystemExit(
                f"plan {plan.plan_version!r} cannot express {bundle.name!r}'s "
                f"GT:\n  " + "\n  ".join(errs))
    return plan, resolved.sha256, resolved


def _plans_provenance(config: dict, bundles: List[FixtureBundle],
                      suite_dir: Path) -> Dict[str, Any]:
    """One entry per DISTINCT exam actually graded in this run, keyed by exam_id.

    Keyed by exam rather than by fixture because the plan is a property of the
    exam: five fixtures on one exam produce one entry, not five copies of it.
    The legacy single-plan path has no exam_id, so it keys as "<unscoped>" —
    named rather than blank, so a reader can tell "one exam, unlabelled" from
    "the field was never populated"."""
    out: Dict[str, Any] = {}
    for bundle in bundles:
        plan, plan_sha, resolved = _load_plan(config, bundle, suite_dir)
        key = resolved.exam_id or "<unscoped>"
        entry = {"plan": resolved.ref, "plan_version": plan.plan_version,
                 "plan_sha256": plan_sha,
                 "fixtures": []}
        out.setdefault(key, entry)["fixtures"].append(bundle.name)
    for entry in out.values():
        entry["fixtures"].sort()
    return out


def build_agent(bundle: FixtureBundle, agent_factory=None, *,
                config: Optional[dict] = None, spec: Optional[ModelSpec] = None,
                suite_dir: Path = SUITE_DIR):
    """Construct the agent with the CONTRACT's numeric policy — mirrors
    production grading_runner. agent_factory is the test seam (unchanged
    contract: called with numeric_policy only). With config+spec, construction
    goes through the D6 llm_factory seam: the registry spec decides the model,
    config decides architecture (v3 GraderAgent | v5 PlanVerifyGrader) and
    params."""
    if agent_factory is not None:
        return agent_factory(numeric_policy=bundle.rubric_contract.numeric_policy)
    policy = bundle.rubric_contract.numeric_policy
    if config is None or spec is None:
        from app.agents.grader.grader import GraderAgent   # lazy: pulls langchain
        return GraderAgent(numeric_policy=policy)
    from app.agents.grader.llm_factory import build_chat_model   # lazy
    params = config.get("params") or {}
    llm = build_chat_model(spec.provider, spec.model_id,
                           reasoning_effort=params.get("reasoning_effort"),
                           max_output_tokens=params.get("max_output_tokens"),
                           thinking_budget=params.get("thinking_budget"))
    if config.get("architecture", "v3") == "v5":
        plan, _sha, _resolved = _load_plan(config, bundle, suite_dir)
        casc = config.get("cascade")
        if casc:
            from app.agents.grader.grader_cascade import CascadeGrader   # lazy
            base_spec = model_spec(casc["base_model_key"])
            base_params = casc.get("base_params") or {}
            base_llm = build_chat_model(
                base_spec.provider, base_spec.model_id,
                reasoning_effort=base_params.get("reasoning_effort"),
                thinking_budget=base_params.get("thinking_budget"))
            return CascadeGrader(
                plan, policy, base_llm=base_llm, champion_llm=llm,
                base_model_version=base_spec.model_id,
                champion_model_version=spec.model_id,
                conf_threshold=float(casc.get("conf_threshold", 0.80)))
        from app.agents.grader.grader_v5 import PlanVerifyGrader   # lazy
        return PlanVerifyGrader(plan, policy, llm=llm,
                                model_version=spec.model_id,
                                sc_n=int(config.get("sc_n", 1)))
    from app.agents.grader.grader import GraderAgent
    return GraderAgent(numeric_policy=policy, llm=llm,
                       model_version=spec.model_id)


def _filter_scopes(bundle: FixtureBundle, scope_targets: List[str]):
    """--scopes: keep only the named scopes (full-path 'q2.א' / 'q1' targets)."""
    want = set(scope_targets)
    keep = [s for s in bundle.gradable_test.scopes
            if (s.question_id if s.sub_question_id is None
                else f"{s.question_id}.{s.sub_question_id}") in want]
    if not keep:
        raise SystemExit(f"--scopes matched nothing; known: "
                         f"{[(s.question_id, s.sub_question_id) for s in bundle.gradable_test.scopes]}")
    filtered = bundle.gradable_test.model_copy(update={"scopes": keep})
    return filtered, {(s.question_id, s.sub_question_id) for s in keep}


async def grade_fixture_trials(agent, bundle: FixtureBundle, *, k: int,
                               wall_s: float, cost_ceiling: float,
                               price, drafts_dir: Optional[Path],
                               gradable=None,
                               ) -> List[Tuple[Optional[GradedTestDraft], dict]]:
    """k trials of one fixture. Returns [(draft|None, meta)] — meta carries
    latency/rerun/invalid facts for scoring. Wall + ONE transport re-run [D7]."""
    gradable = gradable or bundle.gradable_test
    out: List[Tuple[Optional[GradedTestDraft], dict]] = []
    for r in range(k):
        meta = {"trial_index": r, "latency_s": None, "invalid_reason": None,
                "rerun_count": 0, "rerun_reason": None}
        draft: Optional[GradedTestDraft] = None
        for attempt in (1, 2):
            t0 = time.monotonic()
            try:
                draft = await asyncio.wait_for(agent.grade(gradable), timeout=wall_s)
                meta["latency_s"] = round(time.monotonic() - t0, 2)
            except asyncio.TimeoutError:
                draft = None
                meta["latency_s"] = round(time.monotonic() - t0, 2)
                # [DL-3] a wall hit IS the transport failure mode of a SUT with
                # no timeout (G-3) — retryable, once.
                if attempt == 1:
                    meta["rerun_count"], meta["rerun_reason"] = 1, "wall bound hit"
                    continue
                meta["invalid_reason"] = (f"wall bound {wall_s}s hit twice — "
                                          f"trial invalid [§7]")
                break
            # transport-classified failed scopes => retryable once [D7];
            # parse failures are deterministic and scored, never re-run [R6]
            _, transport = _classify_failed_scopes(draft)
            if transport and attempt == 1:
                meta["rerun_count"] = 1
                meta["rerun_reason"] = f"transport failure in {transport}"
                continue
            break
        if drafts_dir is not None and draft is not None:
            (drafts_dir / f"{bundle.name}_r{r}.json").write_text(
                draft.model_dump_json(indent=1), encoding="utf-8")
            (drafts_dir / f"{bundle.name}_r{r}.meta.json").write_text(
                json.dumps(meta, ensure_ascii=False), encoding="utf-8")
        out.append((draft, meta))
    return out


def _score_pair(draft: Optional[GradedTestDraft], meta: dict,
                bundle: FixtureBundle, *, cost_ceiling: float, price,
                provisional: bool, scope_filter=None) -> TrialScore:
    if draft is None:
        # a wall-invalid trial still gets a (invalid) row — counted, excluded
        empty = TrialScore(fixture=bundle.name, trial_index=meta["trial_index"],
                           valid=False, invalid_reason=meta["invalid_reason"],
                           provisional=provisional,
                           rerun_count=meta["rerun_count"],
                           rerun_reason=meta["rerun_reason"],
                           latency_s=meta["latency_s"])
        return empty
    cost = None
    per_scope_cost: Dict[str, float] = {}
    if draft.cascade_usage is not None:
        # [COST_TRUTH, cascade] price each tier by its OWN registry card
        cost = 0.0
        for model_id, u in draft.cascade_usage.items():
            tier_spec = next((m for m in _REGISTRY_MODELS.values()
                              if m.model_id == model_id), None)
            if tier_spec is None:
                raise SystemExit(f"cascade tier {model_id!r} has no registry card")
            cost += cost_usd(Usage(input_tokens=u.get("input", 0),
                                   output_tokens=u.get("output", 0),
                                   cached_input_tokens=u.get("cached") or None),
                             tier_spec.price)
    elif price is not None:
        cost = cost_usd(Usage(input_tokens=draft.total_input_tokens,
                              output_tokens=draft.total_output_tokens,
                              cached_input_tokens=draft.total_cached_input_tokens),
                        price)
        for o in draft.scope_outcomes:
            target = o.question_id if o.sub_question_id is None else f"{o.question_id}.{o.sub_question_id}"
            per_scope_cost[target] = cost_usd(
                Usage(input_tokens=o.input_tokens, output_tokens=o.output_tokens), price)
    ts = score_trial(
        draft, bundle, trial_index=meta["trial_index"],
        cost_usd_value=cost, cost_ceiling=cost_ceiling,
        latency_s=meta["latency_s"], provisional=provisional,
        scope_filter=scope_filter, per_scope_cost=per_scope_cost,
        rerun_count=meta["rerun_count"], rerun_reason=meta["rerun_reason"],
        invalid_reason=meta["invalid_reason"])
    ts.cached_input_tokens = draft.total_cached_input_tokens   # [mission §1.3]
    return ts


def run_grade(config_name: str, fixture_names: List[str], *, k: int,
              scopes: Optional[List[str]] = None, agent_factory=None,
              suite_dir: Path = SUITE_DIR) -> Path:
    config = _load_config(config_name, suite_dir=suite_dir)
    spec = model_spec(config["model_key"])
    _apply_prior_context_flag(config)                           # [PR-G1 item 4]
    cost_ceiling = float(config.get("cost_ceiling", 0.10))      # [§6 Tier-1]
    provisional = (k == 1) or bool(scopes)

    results_dir = suite_dir / "results"
    bundles: List[FixtureBundle] = []
    for name in fixture_names:
        b = load_bundle(name, suite_dir=suite_dir, require_gt=True)   # [R1]
        assert_blind_sequencing(name, b.gt, results_dir)               # [R1]
        bundles.append(b)

    ts_name = time.strftime("%Y%m%d-%H%M%S")
    out_dir = results_dir / f"{ts_name}_{config_name}"
    drafts_dir = out_dir / "drafts"
    drafts_dir.mkdir(parents=True, exist_ok=True)

    # [two-exam harness] PRE-SPEND GATE. Resolve and validate EVERY fixture's
    # plan before the first API call — plan pin, validator, and the
    # expressibility guard, for all exams.
    #
    # This ordering is load-bearing and the second exam is what made it so. With
    # one exam, "pre-spend" was true for free: the only plan was validated
    # before the only fixture graded. With two, resolving inside the loop means
    # a missing or unroutable exam-2 plan is discovered only when exam 2's turn
    # comes — after every exam-1 fixture has already been paid for. Same guard,
    # same words in the docstring, silently worth less.
    plans_prov = (_plans_provenance(config, bundles, suite_dir)
                  if config.get("architecture") == "v5" and bundles else None)

    trials: List[TrialScore] = []
    drafts_by_fixture: Dict[str, Dict[int, GradedTestDraft]] = {}
    for bundle in bundles:
        gradable, scope_filter = (None, None)
        if scopes:
            gradable, scope_filter = _filter_scopes(bundle, scopes)
        agent = build_agent(bundle, agent_factory=agent_factory,
                            config=config if agent_factory is None else None,
                            spec=spec if agent_factory is None else None,
                            suite_dir=suite_dir)
        pairs = asyncio.run(grade_fixture_trials(
            agent, bundle, k=k, wall_s=TRIAL_WALL_S, cost_ceiling=cost_ceiling,
            price=spec.price, drafts_dir=drafts_dir, gradable=gradable))
        for draft, meta in pairs:
            if agent_factory is None:
                _assert_draft_stamp(draft, spec)     # [DL-4 successor] per trial
            trials.append(_score_pair(draft, meta, bundle,
                                      cost_ceiling=cost_ceiling, price=spec.price,
                                      provisional=provisional,
                                      scope_filter=scope_filter))
            if draft is not None:
                drafts_by_fixture.setdefault(bundle.name, {})[meta["trial_index"]] = draft
        print(f"[grade] {bundle.name}: {k} trial(s) done")

    prov = _provenance(config_name, config, spec, mode="grade", k=k,
                       fixtures=[b.name for b in bundles], scopes=scopes,
                       gt_sources={b.name: b.gt.gt_source for b in bundles})
    served_all = sorted({m for by_r in drafts_by_fixture.values()
                         for d in by_r.values() for m in (d.served_models or [])})
    # [COST_TRUTH] absence is surfaced, never silently equated with the request
    prov["served_models"] = served_all or ["<unreported-by-provider>"]
    if plans_prov is not None:
        # Recorded for EVERY exam in the run. This used to read bundles[0],
        # which on a two-exam corpus records one plan and silently implies it
        # graded all of them — provenance that is wrong is worse than provenance
        # that is absent, because it is quotable.
        prov["plans"] = plans_prov
        # The single-exam keys keep their exact former values when one plan
        # resolved, so a hobby run's provenance is unchanged.
        if len(prov["plans"]) == 1:
            only = next(iter(prov["plans"].values()))
            prov["plan_version"] = only["plan_version"]
            prov["plan_sha256"] = only["plan_sha256"]
    suite = SuiteResult(provenance=prov, trials=trials)
    suite.aggregates = reporting.aggregate(trials, k=k)
    reporting.write_results(suite, out_dir)
    reporting.write_summary(suite, out_dir)
    for bundle in bundles:
        reporting.write_fixture_report(
            bundle.name, [t for t in trials if t.fixture == bundle.name],
            drafts_by_fixture.get(bundle.name, {}), out_dir)
    print(f"[done] {suite.aggregates.get('tier1_pass_count', 0)}/"
          f"{suite.aggregates.get('n_valid', 0)} valid trials pass Tier-1 -> {out_dir}")
    print(f"[spend] run total ${suite.aggregates.get('run_cost_usd_total', 0.0)} "
          f"-> RUNLOG ledger")
    return out_dir


# ---------------------------------------------------------------------------
# score_only mode — $0 re-scoring of cached drafts [§3]
# ---------------------------------------------------------------------------

def run_score_only(config_name: str, run_dir: Path, *,
                   suite_dir: Path = SUITE_DIR) -> Path:
    config = _load_config(config_name, suite_dir=suite_dir)
    spec = model_spec(config["model_key"])
    _apply_prior_context_flag(config)                           # [PR-G1 item 4]
    cost_ceiling = float(config.get("cost_ceiling", 0.10))
    drafts_dir = Path(run_dir) / "drafts"
    if not drafts_dir.exists():
        raise SystemExit(f"score_only: no drafts/ under {run_dir}")

    by_fixture: Dict[str, List[Tuple[int, GradedTestDraft, dict]]] = {}
    for p in sorted(drafts_dir.glob("*_r*.json")):
        if p.name.endswith(".meta.json"):
            continue
        stem = p.stem                       # <fixture>_r<i>
        fixture, _, ridx = stem.rpartition("_r")
        meta_p = drafts_dir / f"{stem}.meta.json"
        meta = (json.loads(meta_p.read_text(encoding="utf-8"))
                if meta_p.exists() else {"trial_index": int(ridx), "latency_s": None,
                                         "invalid_reason": None, "rerun_count": 0,
                                         "rerun_reason": None})
        draft = GradedTestDraft.model_validate_json(p.read_text(encoding="utf-8"))
        by_fixture.setdefault(fixture, []).append((int(ridx), draft, meta))

    trials: List[TrialScore] = []
    drafts_by_fixture: Dict[str, Dict[int, GradedTestDraft]] = {}
    gt_sources: Dict[str, str] = {}   # was defined AFTER first use — latent NameError
    k = max((len(v) for v in by_fixture.values()), default=0)
    for fixture, rows in sorted(by_fixture.items()):
        bundle = load_bundle(fixture, suite_dir=suite_dir, require_gt=True)   # [R1]
        assert_blind_sequencing(fixture, bundle.gt, suite_dir / "results")     # [R1]
        gt_sources[fixture] = bundle.gt.gt_source                              # [M1]
        for ridx, draft, meta in sorted(rows):
            meta = {**meta, "trial_index": ridx}
            trials.append(_score_pair(draft, meta, bundle,
                                      cost_ceiling=cost_ceiling, price=spec.price,
                                      provisional=(len(rows) == 1)))
            drafts_by_fixture.setdefault(fixture, {})[ridx] = draft

    ts_name = time.strftime("%Y%m%d-%H%M%S")
    out_dir = suite_dir / "results" / f"{ts_name}_{config_name}_rescore"
    prov = _provenance(config_name, config, spec, mode="score_only", k=k,
                       fixtures=sorted(by_fixture), scopes=None,
                       gt_sources=gt_sources)
    prov["rescored_run"] = str(run_dir)
    suite = SuiteResult(provenance=prov, trials=trials)
    suite.aggregates = reporting.aggregate(trials, k=k)
    reporting.write_results(suite, out_dir)
    reporting.write_summary(suite, out_dir)
    for fixture in sorted(by_fixture):
        reporting.write_fixture_report(
            fixture, [t for t in trials if t.fixture == fixture],
            drafts_by_fixture.get(fixture, {}), out_dir)
    print(f"[done] score_only rescore of {run_dir} -> {out_dir}")
    return out_dir


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description="Grading eval runner")
    ap.add_argument("--config", default="gpt-4o")
    ap.add_argument("--mode", default="grade", choices=["grade", "score_only"])
    ap.add_argument("--fixtures", default="",
                    help="comma-separated fixture names; default = all manifests")
    ap.add_argument("--repeats", "-k", type=int, default=5,
                    help="trials per fixture; k=1 is PROVISIONAL [§3]")
    ap.add_argument("--scopes", default="",
                    help="diagnostic subset: comma-separated scope targets (q1, q2.א)")
    ap.add_argument("--score-run", default="",
                    help="score_only: path to the run dir holding drafts/")
    args = ap.parse_args()

    if args.fixtures:
        fixtures = [f.strip() for f in args.fixtures.split(",") if f.strip()]
    else:
        fixtures = sorted(p.stem for p in (SUITE_DIR / "fixtures").glob("*.json"))
    if not fixtures and args.mode == "grade":
        raise SystemExit("no fixture manifests found under fixtures/")
    scopes = [s.strip() for s in args.scopes.split(",") if s.strip()] or None

    if args.mode == "grade":
        run_grade(args.config, fixtures, k=args.repeats, scopes=scopes)
    else:
        if not args.score_run:
            raise SystemExit("score_only requires --score-run <results/run_dir>")
        run_score_only(args.config, Path(args.score_run))


if __name__ == "__main__":
    main()
