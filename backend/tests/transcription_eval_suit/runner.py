"""
runner.py — orchestrates eval runs and emits the results artifact.

Modes:
  per_doc — full pipeline per fixture (PDF -> P1 -> P2), scores BOTH surfaces.
  p1_only — Phase 1 only (PDF -> pages). No exam spec, no draft GT needed.
  p2_only — Phase 2 isolation: GOLD pages -> P2. No PDF, no images, near-free.
  batch   — fixtures replicated+shuffled to batch_size, run concurrently with
            depth-first doc priorities; measures time-to-first/last + p95 (the
            only mode where a p95 is honest — C2).

Statistics honesty: per-doc latency reports median/min/max only. Accuracy:
mean+std over repeats, per doc, plus the WORST doc (the mean is forbidden as
the only aggregate). temp 0; first record of the run is marked cold.

Artifacts per run, under results/<timestamp>_<config_name>/:
  results.json — stable schema, the regression-gate input
  summary.md   — the human read (gate verdicts with named reasons, worst doc,
                 stage table, cost vs the $0.05–0.08 ceiling)
  report_<doc>.md — manual-review companion (report.py)
"""
from __future__ import annotations

import argparse
import asyncio
import dataclasses
import json
import logging
import os
import random
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

from app.services.transcription.scheduler import ProviderLimit, ProviderScheduler
from app.services.transcription.two_phase.trust import run_with_trust

from .critical_tokens import JAVA_BAGRUT
from .flag_metrics import score_flags
from .ground_truth import (
    GoldDocument,
    GoldPageDocument,
    load_ground_truth,
    load_page_ground_truth,
)
from .instrument import Trace
from .models_registry import AS_OF, spec as model_spec
from .parsing import ExamSpec, load_exam_spec, spec_from_rubric_draft
from .pipelines import Pipeline, PipelineConfig, build_pipeline
from .prompts import TRANSCRIPTION_PROMPT_VERSION
from .report import write_doc_report, write_summary
from .scoring import (
    DocumentScore,
    PageDocumentScore,
    ScoringPolicy,
    gate_pass,
    measure_corrections,
    score_document,
    score_page_document,
)

SUITE_DIR = Path(__file__).parent
COST_CEILING_USD = 0.08          # per-document average (locked success criterion)
# Trust-layer configs (reader_model_keys set) run under a separate, explicitly
# authorized envelope (Noam, 2026-07-08: up to $0.10/doc while the layer proves
# itself; cost optimization — reader image_max_px — comes after). The $0.08
# accuracy-gate ceiling above is UNCHANGED for v0 configs.
TRUST_COST_CEILING_USD = 0.10
FLAG_TRUST_MIN_FIXTURES = 10     # flag metrics are noise below this (C1)

# The scoring semantics this run uses. Stamped into results.json ("scoring") so
# every artifact states which scorer produced it. case_insensitive_keywords is
# ON by default (Change B): see RUNLOG 2026-06-25 — this BREAKS comparability of
# method_call_recall with any baseline scored case-sensitively.
SCORING_POLICY = ScoringPolicy()

load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # backend/.env

log = logging.getLogger("eval.runner")


def _configure_logging() -> None:
    """Live progress to stderr. EVAL_LOG_LEVEL=DEBUG surfaces the scheduler's
    per-call boundary; provider-SDK transport noise is pinned to WARNING so the
    pipeline's own progress lines stay readable."""
    level = getattr(logging, os.environ.get("EVAL_LOG_LEVEL", "INFO").upper(),
                    logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    for noisy in ("httpx", "httpcore", "openai", "anthropic",
                  "google", "google_genai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("transcription.scheduler").setLevel(level)

@dataclass(frozen=True)
class RunPlan:
    config: PipelineConfig
    config_name: str
    fixtures: tuple[str, ...]
    repeats: int = 3
    mode: str = "per_doc"            # per_doc | p1_only | p2_only | batch
    batch_size: int = 25
    exam_spec_path: str | None = None


@dataclass
class Fixture:
    doc_id: str
    pdf_path: Path | None
    raw_gold: GoldPageDocument | None
    draft_gold: GoldDocument | None


@dataclass
class RunRecord:
    doc_id: str
    repeat: int
    cold: bool
    latency_ms: float
    cost_usd: float
    parse_failures: int
    queue_wait_ms_total: float
    stage_ms: dict
    parse_failure_finish_reasons: list = field(default_factory=list)
    p1: dict | None = None           # serialized PageDocumentScore + gate
    e2e: dict | None = None          # serialized DocumentScore + gate
    spec_mismatches: list = field(default_factory=list)
    routing_notes: list = field(default_factory=list)   # P2's self-reported re-routing
    trust: dict | None = None        # trust-layer flag metrics (reader configs only)


# --- fixture resolution -----------------------------------------------------------

def _find_pdf(doc_id: str) -> Path | None:
    pdf_dir = SUITE_DIR / "pdfs"
    if not pdf_dir.exists():
        return None
    for p in pdf_dir.glob("*.pdf"):
        if p.stem.lower() == doc_id.lower():
            return p
    return None


def resolve_fixtures(doc_ids: tuple[str, ...], mode: str) -> list[Fixture]:
    fixtures: list[Fixture] = []
    for doc_id in doc_ids:
        raw_p = SUITE_DIR / "raw_benchmarks" / f"{doc_id}.md"
        draft_p = SUITE_DIR / "draft_benchmarks" / f"{doc_id}.md"
        fx = Fixture(
            doc_id=doc_id,
            pdf_path=_find_pdf(doc_id),
            raw_gold=load_page_ground_truth(raw_p) if raw_p.exists() else None,
            draft_gold=load_ground_truth(draft_p) if draft_p.exists() else None,
        )
        if mode in ("per_doc", "p1_only", "batch") and fx.pdf_path is None:
            raise FileNotFoundError(f"{doc_id}: no PDF in pdfs/ (required for {mode}).")
        if mode in ("per_doc", "p1_only", "batch") and fx.raw_gold is None:
            raise FileNotFoundError(f"{doc_id}: no raw_benchmarks GT (required for {mode}).")
        if mode in ("per_doc", "p2_only", "batch") and fx.draft_gold is None:
            raise FileNotFoundError(f"{doc_id}: no draft_benchmarks GT (required for {mode}).")
        if mode == "p2_only" and fx.raw_gold is None:
            raise FileNotFoundError(f"{doc_id}: p2_only needs raw GT as gold input.")
        fixtures.append(fx)
    return fixtures


def load_spec(plan: RunPlan) -> ExamSpec | None:
    if plan.mode == "p1_only" and plan.exam_spec_path is None:
        return None  # no spec needed; correction secondary metric simply absent
    if plan.exam_spec_path is None:
        raise ValueError(f"mode={plan.mode} requires --exam-spec.")
    p = Path(plan.exam_spec_path)
    if not p.is_absolute():
        p = SUITE_DIR / p
    try:
        return load_exam_spec(p)
    except (ValueError, KeyError):
        # KeyError: a rubric draft_json lacks the canonical "number" key, so the
        # strict loader trips before the fallback could run. Both shapes drop in.
        return spec_from_rubric_draft(p)   # tolerate a rubric draft_json drop-in


# --- scoring serialization ---------------------------------------------------------

def _ser_e2e(s: DocumentScore) -> dict:
    passed, reasons = gate_pass(s)
    return {
        "doc_ratio_strict": s.doc_ratio_strict,
        "doc_ratio_lenient": s.doc_ratio_lenient,
        "coverage": s.coverage,
        "missed_keys": [list(k) for k in s.missed_keys],
        "extra_keys": [list(k) for k in s.extra_keys],
        "critical": dataclasses.asdict(s.critical),
        "answers": [
            {"key": list(a.key), "ratio_strict": a.ratio_strict,
             "is_error": a.is_error,
             "missed": {
                 "operators": list(a.critical.missed_operators),
                 "structural": list(a.critical.missed_structural),
                 "method_calls": list(a.critical.missed_method_calls),
                 "abbreviations": list(a.critical.abbreviations_altered),
             }}
            for a in s.answers
        ],
        "gate": {"passed": passed, "reasons": reasons},
    }


def _ser_p1(s: PageDocumentScore) -> dict:
    passed, reasons = gate_pass(s)
    return {
        "doc_ratio_strict": s.doc_ratio_strict,
        "doc_ratio_lenient": s.doc_ratio_lenient,
        "coverage": s.coverage,
        "missing_pages": list(s.missing_pages),
        "extra_pages": list(s.extra_pages),
        "critical": dataclasses.asdict(s.critical),
        "pages": [
            {"page": p.page_number, "ratio_strict": p.ratio_strict,
             "is_error": p.is_error}
            for p in s.pages
        ],
        "gate": {"passed": passed, "reasons": reasons},
    }


# --- execution ----------------------------------------------------------------------

async def _run_one(
    pipeline: Pipeline, fx: Fixture, exam_spec: ExamSpec | None,
    mode: str, doc_priority: int,
) -> tuple[RunRecord, object | None, object | None, dict]:
    t0 = time.monotonic()
    p1_score = e2e_score = None
    mismatches: list = []
    routing_notes: list = []
    corr_scopes: list = []
    trust_block: dict | None = None
    outputs: dict = {"pages": {}, "answers": {}}
    if mode == "p2_only":
        run = await pipeline.run_phase2(
            fx.raw_gold.as_dict(), exam_spec, fx.doc_id, doc_priority=doc_priority
        )
        trace = run.trace
        scored_answers = run.corrected_answers or run.answers
        e2e_score = score_document(scored_answers, fx.draft_gold, profile=JAVA_BAGRUT, policy=SCORING_POLICY)
        mismatches = [dataclasses.asdict(m) for m in run.spec_mismatches]
        routing_notes = list(run.routing_notes)
        outputs = {"pages": dict(run.pages), "answers": dict(scored_answers)}
        corr_scopes = _correction_scopes(run, fx.draft_gold)
    elif mode == "p1_only":
        pages, trace = await pipeline.run_phase1(
            fx.pdf_path.read_bytes(), fx.doc_id, doc_priority=doc_priority
        )
        p1_score = score_page_document(pages, fx.raw_gold, profile=JAVA_BAGRUT, policy=SCORING_POLICY)
        outputs = {"pages": dict(pages), "answers": {}}
    else:  # per_doc / batch
        trust_run = None
        if pipeline.cfg.reader_model_keys:
            trust_run = await run_with_trust(
                pipeline, fx.pdf_path.read_bytes(), fx.doc_id, exam_spec,
                doc_priority=doc_priority,
            )
            run = trust_run.run
        else:
            run = await pipeline.run(
                fx.pdf_path.read_bytes(), fx.doc_id, exam_spec, doc_priority=doc_priority
            )
        trace = run.trace
        scored_answers = run.corrected_answers or run.answers
        p1_score = score_page_document(run.pages, fx.raw_gold, profile=JAVA_BAGRUT, policy=SCORING_POLICY)
        e2e_score = score_document(scored_answers, fx.draft_gold, profile=JAVA_BAGRUT, policy=SCORING_POLICY)
        mismatches = [dataclasses.asdict(m) for m in run.spec_mismatches]
        routing_notes = list(run.routing_notes)
        outputs = {"pages": dict(run.pages), "answers": dict(scored_answers)}
        corr_scopes = _correction_scopes(run, fx.draft_gold)
        if trust_run is not None:
            flag_score = score_flags(
                fx.doc_id, run.pages, fx.raw_gold,
                trust_run.flags, trust_run.lint,
            )
            outputs["flags"] = [dataclasses.asdict(f) for f in trust_run.flags]
            outputs["attributions"] = {
                k: {"pages": a.pages, "confidence": a.confidence}
                for k, a in trust_run.attributions.items()
            }
            trust_block = flag_score.as_dict()

    latency_ms = (time.monotonic() - t0) * 1000.0
    stage_ms: dict[str, float] = {}
    for span in trace.spans:
        stage_ms[span.stage] = stage_ms.get(span.stage, 0.0) + span.ms
    p1_times = [c.total_ms for c in trace.calls if c.phase == "p1"]
    stage_ms["p1_call_sum"] = sum(p1_times)
    stage_ms["p1_call_max"] = max(p1_times, default=0.0)  # ~wall (chunks concurrent)
    stage_ms["p2_call"] = sum(c.total_ms for c in trace.calls if c.phase == "p2")

    rec = RunRecord(
        doc_id=fx.doc_id, repeat=-1, cold=False,
        latency_ms=latency_ms,
        cost_usd=trace.total_cost_usd(),
        parse_failures=sum(1 for c in trace.calls if not c.parse_ok),
        parse_failure_finish_reasons=[
            str(c.finish_reason) for c in trace.calls if not c.parse_ok
        ],
        queue_wait_ms_total=sum(c.queue_wait_ms for c in trace.calls),
        stage_ms=stage_ms,
        p1=_ser_p1(p1_score) if p1_score else None,
        e2e=_ser_e2e(e2e_score) if e2e_score else None,
        spec_mismatches=mismatches,
        routing_notes=routing_notes,
        trust=trust_block,
    )
    return rec, p1_score, e2e_score, outputs, corr_scopes


def _correction_scopes(run, draft_gold) -> list:
    """Per-answer (gold, raw_pred, corrected_pred, corrections) tuples for the
    correction-safety referee. Only answers that were actually corrected, keyed
    so the corrected token can be checked against the faithful GT token set."""
    from .keys import normalize_key
    gold_map = {normalize_key(a.key): a.answer_text for a in draft_gold.answers}
    raw = run.answers
    corrected = run.corrected_answers or run.answers
    per_key_corr: dict = {}
    for c in run.corrections:
        per_key_corr.setdefault(None, [])  # placeholder; corrections carry their own key
    # corrections were recorded with their answer Key in SpecMismatch; rebuild per-key
    by_key: dict = {}
    for m in run.spec_mismatches:
        by_key.setdefault(m.key, []).append(m)
    scopes = []
    for k, corr_list in by_key.items():
        # reconstruct Correction-shaped objects for the measurer
        from .corrector import Correction
        cs = tuple(Correction(m.original, m.suggested, m.reason.split("->")[0],
                              m.reason.split("->")[-1]) for m in corr_list)
        scopes.append((gold_map.get(k, ""), raw.get(k, ""), corrected.get(k, ""), cs))
    return scopes


async def _run_one_resilient(pipeline, fx, exam_spec, mode, prio,
                             attempts: int = 3):
    """Doc-level retry for TRANSPORT failures only.

    The scheduler already retries each call once; a VLMCallError that still
    escapes (network flap outlasting that retry) used to kill the entire RUN
    mid-k=5 (observed twice on 2026-07-09: multi-vendor timeout storms). A
    retryable transport error now re-runs the document after a backoff.
    Content/parse failures are NEVER retried here — they are recorded metrics
    (D2), and non-retryable errors (auth/bad_request) still propagate loudly."""
    from app.services.transcription.vlm_provider import VLMCallError
    for attempt in range(1, attempts + 1):
        try:
            return await _run_one(pipeline, fx, exam_spec, mode, prio)
        except VLMCallError as e:
            if not e.retryable or attempt == attempts:
                raise
            wait = 15 * attempt
            log.warning("[%s] transport failure (%s) — re-running doc in %ds "
                        "(attempt %d/%d)", fx.doc_id, e.kind.value, wait,
                        attempt, attempts)
            await asyncio.sleep(wait)


async def execute(plan: RunPlan, pipeline: Pipeline) -> tuple[dict, dict]:
    fixtures = resolve_fixtures(plan.fixtures, plan.mode)
    exam_spec = load_spec(plan)
    records: list[RunRecord] = []
    doc_scores: dict[str, list] = {fx.doc_id: [] for fx in fixtures}
    first_outputs: dict[str, dict] = {}
    all_corr_scopes: list = []
    batch_metrics: dict = {}

    if plan.mode == "batch":
        rng = random.Random(42)
        instances = [fixtures[i % len(fixtures)] for i in range(plan.batch_size)]
        rng.shuffle(instances)
        t_batch = time.monotonic()
        completion_times: list[float] = []

        async def run_instance(i: int, fx: Fixture):
            rec, _, e2e, outs, cscopes = await _run_one_resilient(pipeline, fx, exam_spec, "per_doc", i)
            completion_times.append(time.monotonic() - t_batch)
            rec.repeat = i
            records.append(rec)
            first_outputs.setdefault(fx.doc_id, outs)
            all_corr_scopes.extend(cscopes)
            if e2e is not None:
                doc_scores[fx.doc_id].append(e2e)

        await asyncio.gather(*[run_instance(i, fx) for i, fx in enumerate(instances)])
        lat = sorted(r.latency_ms for r in records)
        batch_metrics = {
            "batch_size": plan.batch_size,
            "time_to_first_draft_s": min(completion_times),
            "time_to_last_draft_s": max(completion_times),
            "docs_per_min": plan.batch_size / (max(completion_times) / 60.0),
            "latency_p95_ms": lat[max(0, int(len(lat) * 0.95) - 1)],
            "queue_wait_ms_mean": statistics.mean(r.queue_wait_ms_total for r in records),
        }
    else:
        first = True
        for repeat in range(plan.repeats):
            for fx in fixtures:
                log.info("=== %s | repeat %d/%d | mode=%s ===",
                         fx.doc_id, repeat + 1, plan.repeats, plan.mode)
                t_fx = time.monotonic()
                rec, p1s, e2es, outs, cscopes = await _run_one_resilient(pipeline, fx, exam_spec, plan.mode, 0)
                log.info("=== %s done in %.1fs (cost=$%.4f, parse_failures=%d) ===",
                         fx.doc_id, time.monotonic() - t_fx, rec.cost_usd,
                         rec.parse_failures)
                rec.repeat, rec.cold = repeat, first
                first = False
                records.append(rec)
                first_outputs.setdefault(fx.doc_id, outs)
                all_corr_scopes.extend(cscopes)
                score = e2es if e2es is not None else p1s
                if score is not None:
                    doc_scores[fx.doc_id].append(score)

    # --- aggregates (honest at small n) ---
    def ratios(scores: list) -> list[float]:
        return [s.doc_ratio_strict for s in scores]

    per_doc = {}
    for doc_id, scores in doc_scores.items():
        if not scores:
            continue
        rs = ratios(scores)
        gates = [gate_pass(s)[0] for s in scores]
        per_doc[doc_id] = {
            "ratio_strict_mean": statistics.mean(rs),
            "ratio_strict_std": statistics.stdev(rs) if len(rs) > 1 else 0.0,
            "gate_pass_all": all(gates),
        }
    worst_doc = min(per_doc, key=lambda d: per_doc[d]["ratio_strict_mean"]) if per_doc else None

    warm = [r for r in records if not r.cold] or records
    lat = sorted(r.latency_ms for r in warm)
    cost_avg = statistics.mean(r.cost_usd for r in records) if records else 0.0
    aggregates = {
        "per_doc": per_doc,
        "worst_doc": worst_doc,
        "latency_ms": {"median": statistics.median(lat), "min": lat[0], "max": lat[-1]},
        "cost_avg_per_doc_usd": cost_avg,
        "cost_gate_pass": cost_avg <= COST_CEILING_USD,
        "parse_failure_total": sum(r.parse_failures for r in records),
        "accuracy_gate_pass_all_docs": all(d["gate_pass_all"] for d in per_doc.values()) if per_doc else False,
        "n_fixtures": len(fixtures),
        "flag_metrics_trustworthy": len(fixtures) >= FLAG_TRUST_MIN_FIXTURES,
        **({"batch": batch_metrics} if batch_metrics else {}),
    }

    # Trust-layer aggregate (only when the config names reader models).
    trust_recs = [r.trust for r in records if r.trust]
    if trust_recs:
        def _tot(key: str) -> int:
            return sum(t[key] for t in trust_recs)
        n_rec = len(trust_recs)
        labels, crit = _tot("n_labels"), _tot("n_labels_critical")
        flags_total = _tot("n_flags")
        aggregates["trust"] = {
            "reader_model_keys": list(plan.config.reader_model_keys),
            "error_recall": _tot("covered") / labels if labels else 1.0,
            "critical_recall": (_tot("covered_critical") / crit) if crit else 1.0,
            "critical_recall_high": (_tot("covered_critical_high") / crit)
                                    if crit else 1.0,
            "precision_high": (_tot("true_flags_high")
                               / sum(t["flags_by_severity"]["high"] for t in trust_recs)
                               if sum(t["flags_by_severity"]["high"] for t in trust_recs)
                               else 1.0),
            "flags_per_doc": flags_total / n_rec,
            "high_per_doc": sum(t["flags_by_severity"]["high"] for t in trust_recs) / n_rec,
            "medium_per_doc": sum(t["flags_by_severity"]["medium"] for t in trust_recs) / n_rec,
            "info_per_doc": sum(t["flags_by_severity"]["info"] for t in trust_recs) / n_rec,
            "lint_per_doc": _tot("lint_findings") / n_rec,
            "missed_critical_total": sum(len(t["missed_critical"]) for t in trust_recs),
            # The trust config's authorized cost envelope (Noam, 2026-07-08):
            # up to $0.10/doc while the layer proves itself; the $0.08 accuracy
            # cost gate above is unchanged and still stamped for v0 configs.
            "cost_ceiling_usd": TRUST_COST_CEILING_USD,
            "cost_gate_pass": cost_avg <= TRUST_COST_CEILING_USD,
        }

    # Correction-safety referee (only meaningful when a policy is on).
    if all_corr_scopes and plan.config.correction_policy != "off":
        cm = measure_corrections(all_corr_scopes, n_fixtures=len(fixtures))
        aggregates["correction"] = {
            "policy": plan.config.correction_policy,
            "n_corrections": cm.n_corrections,
            "true_fix": cm.true_fix,
            "false_fix": cm.false_fix,
            "neutral": cm.neutral,
            "false_fix_rate": cm.false_fix_rate,
            "ratio_delta": cm.ratio_delta,
            "by_tier": cm.by_tier,
            "trustworthy": cm.trustworthy,
        }

    return ({
        "prompt_version": TRANSCRIPTION_PROMPT_VERSION,
        "registry_as_of": AS_OF,
        "config_name": plan.config_name,
        "config": dataclasses.asdict(plan.config),
        "scoring": dataclasses.asdict(SCORING_POLICY),  # which scorer semantics produced this
        "mode": plan.mode,
        "repeats": plan.repeats,
        "models": {
            k: {"model_id": model_spec(k).model_id, "tier": model_spec(k).tier}
            for k in {plan.config.p1_model_key, plan.config.p2_model_key} if k
        },
        "records": [dataclasses.asdict(r) for r in records],
        "aggregates": aggregates,
    }, first_outputs)


# --- entry points -------------------------------------------------------------------

def make_default_pipeline(cfg: PipelineConfig) -> Pipeline:
    """Real providers + a fresh scheduler.

    Adapter instances are registered PER MODEL KEY (aliased), never per vendor:
    adapters pin model_id at construction, so a vendor-keyed dict with two
    same-vendor models (gemini-pro baseline + flash-lite reader) silently
    routes both through whichever instance was written last."""
    from app.services.transcription.providers.anthropic_provider import AnthropicProvider
    from app.services.transcription.providers.gemini_provider import GeminiProvider
    from app.services.transcription.providers.openai_provider import OpenAIProvider
    from app.services.transcription.two_phase.pipeline import alias

    adapter_cls = {"openai": OpenAIProvider, "anthropic": AnthropicProvider,
                   "gemini": GeminiProvider}
    providers = {}
    aliased = {}
    for key in {cfg.p1_model_key, cfg.p2_model_key, *cfg.reader_model_keys}:
        if not key:
            continue
        ms = model_spec(key)
        log.info("model %s -> %s adapter, model_id=%s (%s tier)",
                 key, ms.provider, ms.model_id, ms.tier)
        providers[key] = adapter_cls[ms.provider](ms.model_id)
        aliased[key] = alias(ms)
    scheduler = ProviderScheduler({key: ProviderLimit() for key in providers})
    return Pipeline(cfg, providers, scheduler,
                    resolve_model=lambda k: aliased[k])


def run_plan(plan: RunPlan, pipeline: Pipeline | None = None) -> Path:
    pipeline = pipeline or make_default_pipeline(plan.config)
    results, first_outputs = asyncio.run(execute(plan, pipeline))

    out_dir = SUITE_DIR / "results" / f"{time.strftime('%Y%m%d_%H%M%S')}_{plan.config_name}"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    write_summary(out_dir, results, cost_ceiling=COST_CEILING_USD)
    fixtures = resolve_fixtures(plan.fixtures, plan.mode)
    for fx in fixtures:
        write_doc_report(
            out_dir, fx.doc_id, results,
            outputs=first_outputs.get(fx.doc_id, {}),
            raw_gold=fx.raw_gold, draft_gold=fx.draft_gold,
        )
    return out_dir


def _load_config(name: str) -> PipelineConfig:
    p = SUITE_DIR / "configs" / f"{name}.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    return PipelineConfig(**data)


def main() -> None:
    _configure_logging()
    ap = argparse.ArgumentParser(description="Transcription eval runner (REAL API calls).")
    ap.add_argument("--config", required=True, help="config name under configs/ (e.g. v0)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--mode", default="per_doc",
                    choices=["per_doc", "p1_only", "p2_only", "batch"])
    ap.add_argument("--fixtures", default="",
                    help="comma-separated doc_ids; default = all in raw_benchmarks/")
    ap.add_argument("--exam-spec", default=None,
                    help="exam spec JSON (canonical or rubric draft_json), relative to suite dir")
    ap.add_argument("--batch-size", type=int, default=25)
    args = ap.parse_args()

    if args.fixtures:
        fixtures = tuple(f.strip() for f in args.fixtures.split(",") if f.strip())
    else:
        fixtures = tuple(sorted(
            p.stem for p in (SUITE_DIR / "raw_benchmarks").glob("*.md")
        ))

    plan = RunPlan(
        config=_load_config(args.config), config_name=args.config,
        fixtures=fixtures, repeats=args.repeats, mode=args.mode,
        batch_size=args.batch_size, exam_spec_path=args.exam_spec,
    )
    log.info("config=%s mode=%s repeats=%d fixtures=[%s]",
             args.config, args.mode, args.repeats, ", ".join(fixtures))
    out = run_plan(plan)
    print(f"Run complete -> {out}")


if __name__ == "__main__":
    main()
