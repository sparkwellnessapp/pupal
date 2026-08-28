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
    if arch == "v5" and not config.get("plan"):
        raise SystemExit(f"config '{name}': architecture v5 requires 'plan'.")
    if arch != "v5" and (config.get("plan") or config.get("sc_n")):
        raise SystemExit(f"config '{name}': 'plan'/'sc_n' are v5-only keys.")
    return config


def _assert_draft_stamp(draft: Optional[GradedTestDraft], spec: ModelSpec) -> None:
    """[DL-4 successor, seam era] provenance may never claim a model the SUT
    didn't run — now asserted against what ACTUALLY ran: the draft's own
    model_version stamp, per trial, not the process env before the run."""
    if draft is not None and draft.model_version != spec.model_id:
        raise SystemExit(
            f"model stamp mismatch: config resolves to model_id={spec.model_id!r} "
            f"but the draft was graded by {draft.model_version!r} — the seam "
            f"wiring is broken; provenance may never claim a model the SUT "
            f"didn't run.")


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
    return paths


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
        # [PR-G1 item 4] stamped version is a pure function of code + flag
        "prompt_version": effective_prompt_version(),
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
        prov["plan"] = config.get("plan")
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
    Returns (plan, plan_sha256)."""
    from app.agents.grader.plan_schemas import GradingPlan
    from app.agents.grader.plan_validator import validate_plan
    plan_path = suite_dir / config["plan"]
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
    return plan, hashlib.sha256(plan_path.read_bytes()).hexdigest()


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
                           max_output_tokens=params.get("max_output_tokens"))
    if config.get("architecture", "v3") == "v5":
        from app.agents.grader.grader_v5 import PlanVerifyGrader   # lazy
        plan, _sha = _load_plan(config, bundle, suite_dir)
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
    if price is not None:
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
    if config.get("architecture") == "v5" and bundles:
        plan, plan_sha = _load_plan(config, bundles[0], suite_dir)
        prov["plan_version"] = plan.plan_version
        prov["plan_sha256"] = plan_sha
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
