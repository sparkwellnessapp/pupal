"""
Runner: orchestrates render -> extract -> score -> report.

Modes:
  extract   : real pipeline. render(DOCX) -> LLM -> predicted draft_json; scored
              vs GT. render_audit runs INSIDE every extract trial (free) to attribute
              each missed criterion render_loss vs extraction_loss.
  score_only: re-score a cached predicted JSON against GT (no OpenAI). Used by the
              self-tests and for re-scoring a prior run after a scorer change.

Determinism: --repeats k. gpt-4o at temp 0 is NOT guaranteed deterministic, so every
change is evaluated k>=N pre/post and per-metric variance is reported. One change +
one metric + one kill criterion per run (see RUBRIC_EVAL_PLAYBOOK.md).

The pipeline import is LAZY (inside produce_predicted) so importing this module for
score_only does not pull langchain/openai.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple

from app.schemas.ontology_types import ExtractRubricResponse

from . import reporting
from .gates import apply_gate
from .schemas import StageTiming, SuiteResult
from .scoring import score_rubric
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")  # backend/.env

SUITE_DIR = Path(__file__).resolve().parent
PROMPT_VERSION_FALLBACK = "unknown"


def _load_config(name: str) -> dict:
    p = SUITE_DIR / "configs" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))


def _discover(suite_dir: Path) -> List[Tuple[str, Path, Path]]:
    """Match fixtures/<name>.docx to benchmarks/<name>.json by basename."""
    fixtures = {p.stem: p for p in (suite_dir / "fixtures").glob("*.docx")}
    out = []
    for name, gt_path in sorted((p.stem, p) for p in (suite_dir / "benchmarks").glob("*.json")):
        docx = fixtures.get(name)
        if docx is None:
            print(f"[warn] benchmark '{name}' has no fixtures/{name}.docx — skipping")
            continue
        out.append((name, docx, gt_path))
    return out


def _suite_hash(suite_dir: Path) -> str:
    """Content hash over the suite's .py sources + benchmarks, stamped into
    results.json provenance so a MIXED TREE announces itself on run one.

    The instrument is (scorer + reporter + schema + gates + runner) and the golden
    set (benchmarks); configs are DELIBERATELY excluded — the config is the A/B knob
    that is SUPPOSED to differ between runs, so hashing it would flip on every sweep
    and mean nothing. When two runs disagree, this hash separates 'the ruler changed'
    from 'the config changed'. It is the direct fix for how the pedagogical-field drift
    had to be reverse-engineered from missing keys: a shifted hash says so immediately."""
    h = hashlib.sha256()
    files = sorted([*suite_dir.rglob("*.py"), *(suite_dir / "benchmarks").glob("*.json")],
                   key=lambda p: p.relative_to(suite_dir).as_posix())
    for p in files:
        h.update(p.relative_to(suite_dir).as_posix().encode("utf-8") + b"\0")
        h.update(p.read_bytes() + b"\0")
    return h.hexdigest()[:16]


def _load_gt(path: Path) -> ExtractRubricResponse:
    return ExtractRubricResponse.model_validate_json(path.read_text(encoding="utf-8"))


def _run_coro_blocking(coro):
    """Run a coroutine to completion from sync code, whether or not an event loop is
    already running. asyncio.run() raises inside a running loop (Jupyter — where eval
    analysis routinely happens); in that case run in a fresh loop on a worker thread."""
    import asyncio
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(asyncio.run, coro).result()


def _config_env_overrides(config: dict) -> dict:
    """PURE mapping from eval-config fields to the pipeline's env knobs.
    Skips absent/None/empty fields so a minimal config (model only) works and
    a knobless config never clobbers unrelated ambient env values with 'None'."""
    mapping = {
        "model": "EXTRACTION_LLM_MODEL",
        "provider": "EXTRACTION_LLM_PROVIDER",
        "max_output_tokens": "EXTRACTION_LLM_MAX_TOKENS",
        "reasoning_effort": "EXTRACTION_LLM_REASONING_EFFORT",
    }
    return {env: str(config[key]) for key, env in mapping.items()
            if config.get(key) not in (None, "")}


def produce_predicted(docx_path: Path, config: dict) -> Tuple[Optional[ExtractRubricResponse], str, dict]:
    """
    Run the REAL pipeline. Returns (predicted | None, rendered_markdown, meta).

    Maps app/services/docx_v3/pipeline.py's ACTUAL API:
      * render_docx_to_markdown(file_bytes: bytes) -> str   (deterministic; the audit string)
      * extract_rubric_from_docx(file_bytes, extraction_config) -> ExtractionResult  [ASYNC]:
            .response : Optional[ExtractRubricResponse]      (the Draft)
            .metrics  : ExtractionMetrics — timing + retry_count + LLM provenance
                        (input_tokens/output_tokens accumulated across retries,
                        finish_reason of the last call, llm_model)
            .metadata : {pipeline_version, subject, retry_count}
    Both the entrypoint and the renderer take DOCX BYTES (not a path), and the
    entrypoint is async. Division of responsibility for cost: the PIPELINE measures
    tokens; this CONFIG owns the price table (price_per_1m_input/output — prices
    drift, so they live in exactly one reviewable place); the GATE judges the dollars.
    finish_reason feeds the scorer's truncation guard (a 'length' finish invalidates
    the record). Imports are LAZY so score_only stays openai-free.
    """
    import os
    from app.services.docx_v3 import pipeline
    from app.services.docx_v3 import parser_render
    from app.services.docx_v3.pipeline import ExtractionConfig

    file_bytes = Path(docx_path).read_bytes()
    # Render here for the scorer's render-audit. render_docx_to_markdown lives in
    # parser_render — pipeline imports it lazily, so it is NOT a pipeline attribute.
    # Render is deterministic, so this is the same text the extractor's Step 0 produced.
    rendered = parser_render.render_docx_to_markdown(file_bytes)

    # Drive the pipeline's env-configured model/provider/generation-knobs from the
    # eval config, restoring afterwards so two configs in one process cannot
    # contaminate each other. The config file is the experiment record: every
    # experimental variable (model, provider, max_output_tokens, reasoning_effort)
    # travels through it — never ambient environment.
    _env_map = {
        "model": "EXTRACTION_LLM_MODEL",
        "provider": "EXTRACTION_LLM_PROVIDER",
        "max_output_tokens": "EXTRACTION_LLM_MAX_TOKENS",
        "reasoning_effort": "EXTRACTION_LLM_REASONING_EFFORT",
    }
    _overrides = _config_env_overrides(config)
    _saved = {k: os.environ.get(k) for k in _env_map.values()}
    for k, v in _overrides.items():
        os.environ[k] = v

    # ADDITIVE latency instrument (Phase 0): capture per-step wall-clocks via the
    # pipeline's existing pure-data on_progress seam (injected, never imported; a
    # callback failure is swallowed by the pipeline and cannot alter extraction).
    # We ALSO wrap the whole call in a monotonic timer (wall_seconds) as an
    # independent cross-check of the pipeline's own time.time()-based
    # total_time_seconds — a material divergence is itself a measurement finding.
    import time as _time
    stage_events: list = []
    _last_elapsed = [0.0]

    def _on_progress(ev):
        el = getattr(ev, "elapsed_s", None)
        dt = None
        if el is not None:
            dt = round(el - _last_elapsed[0], 3)
            _last_elapsed[0] = el
        stage_events.append({
            "stage": getattr(ev, "stage", None),
            "attempt": getattr(ev, "attempt", None),
            "elapsed_s": el, "dt_s": dt,
            "input_tokens": getattr(ev, "input_tokens", None),
            "output_tokens": getattr(ev, "output_tokens", None),
        })

    try:
        ec = ExtractionConfig(
            subject=config.get("subject", "computer_science"),
            detect_pedagogical_mistakes=config.get("detect_pedagogical_mistakes", True),
        )
        _wall0 = _time.monotonic()
        result = _run_coro_blocking(
            pipeline.extract_rubric_from_docx(file_bytes, ec, on_progress=_on_progress))
        wall_seconds = _time.monotonic() - _wall0
    finally:
        for k, v in _saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    m = result.metrics
    cost_usd = None
    p_in, p_out = config.get("price_per_1m_input"), config.get("price_per_1m_output")
    if p_in is not None and p_out is not None and (m.input_tokens or m.output_tokens):
        cost_usd = (m.input_tokens * float(p_in) + m.output_tokens * float(p_out)) / 1e6

    meta = {
        "cost_usd": cost_usd,
        "finish_reason": m.finish_reason,
        "input_tokens": m.input_tokens,
        "output_tokens": m.output_tokens,
        "llm_seconds": m.llm_time_seconds,
        "render_seconds": m.render_time_seconds,
        "total_seconds": m.total_time_seconds,
        # ADDITIVE latency instrument (Phase 0): runner-side monotonic wall + the
        # per-step event trace from the on_progress seam.
        "wall_seconds": wall_seconds,
        "stage_events": stage_events,
        "retry_count": m.retry_count,
        "num_questions": m.num_questions,
        "num_criteria": m.num_criteria,
        "rendered_chars": m.rendered_chars,
        "model_version": m.llm_model or config.get("model"),
        # prompt_version is the PROMPT's identity, sourced from the code constant next to
        # the prompt text — NOT the pipeline_version (a code/tail version). Conflating them
        # (the old behavior) mislabeled a prompt-driven metric move as a pipeline change.
        "prompt_version": getattr(pipeline, "EXTRACTION_PROMPT_VERSION", PROMPT_VERSION_FALLBACK),
        # pipeline_version (code/tail identity) is stamped from the RUN, not the config:
        # suite_hash does NOT cover pipeline.py, so this stamp is the ONLY tree-drift
        # signal for pipeline-code changes (e.g. the 3.1.0 retry-policy change).
        "pipeline_version": result.metadata.get("pipeline_version"),
        # B4: pipeline warnings/errors + the render-annotation-loss audit (B1b).
        # The audit is suite-side instrumentation: text-based attribution is blind
        # to formatting loss, so a dropped color/highlight/strike channel must
        # self-announce here rather than be reverse-engineered from a bad run.
        "warnings": list(result.warnings) + parser_render.audit_annotation_channels(
            file_bytes, rendered),
        "errors": list(result.errors),
        "requires_review": result.requires_review,
        "num_pedagogical_mistakes": (
            len(result.response.pedagogical_mistakes) if result.response is not None else 0
        ),
    }
    predicted = result.response
    if predicted is None:
        meta["invalid_reason"] = "; ".join(result.errors) or "pipeline returned no .response"
    return predicted, rendered, meta


def run(config_name: str, mode: str, repeats: int, suite_dir: Path = SUITE_DIR,
        only: Optional[str] = None) -> SuiteResult:
    config = _load_config(config_name)
    cost_ceiling = float(config.get("cost_ceiling", 0.40))
    rubrics = _discover(suite_dir)
    # `--only` is a SCREENING-ONLY fixture filter (mission §4 Phase-4 2-fixture
    # subset). Default None ⇒ ALL fixtures (unchanged behaviour). It never mutates
    # the fixture set on disk; it only narrows which pairs this run scores. The
    # selected names are stamped into provenance.fixtures so a subset run
    # self-documents as non-full and can never be mistaken for a 5/5 result.
    if only:
        want = {s.strip() for s in only.split(",") if s.strip()}
        rubrics = [r for r in rubrics if r[0] in want]
        missing = want - {r[0] for r in rubrics}
        if missing:
            raise SystemExit(f"--only names no such fixture(s): {sorted(missing)}")
        print(f"[only] SCREENING SUBSET — {sorted(r[0] for r in rubrics)} (NON-PROMOTABLE)")
    if not rubrics:
        raise SystemExit("no (fixture, benchmark) pairs found")

    # Out-dir is created BEFORE the loop so per-trial artifacts (B5) land as they
    # arrive — a crashed suite run still leaves every completed trial's prediction
    # on disk (the same worst-doc discipline as per-trial isolation).
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = suite_dir / "results" / f"{ts}_{config_name}"
    pred_dir = out_dir / "predictions"
    pred_dir.mkdir(parents=True, exist_ok=True)

    per_rubric = []
    model_v = prompt_v = pipeline_v = None
    for name, docx, gt_path in rubrics:
        gt = _load_gt(gt_path)
        for k in range(repeats):
            if mode == "extract":
                # Per-trial isolation (worst-doc discipline): one doc's transport
                # error or pipeline crash becomes an INVALID record — visible in the
                # report, failing the gate — never a lost suite run. Losing the run
                # would destroy the very worst-doc signal the crash represents.
                try:
                    predicted, rendered, meta = produce_predicted(docx, config)
                except Exception as e:
                    predicted, rendered = None, ""
                    meta = {"invalid_reason": f"pipeline exception: {type(e).__name__}: {e}"}
                    print(f"[error] {name} repeat {k}: {meta['invalid_reason']}")
            else:
                raise SystemExit(f"runner.run does not support mode={mode}; use score_only(...) for cached preds")
            meta["repeat_index"] = k
            meta["rubric_name"] = name
            # B5: persist the predicted Draft + the render verbatim. Twice a conclusion
            # had to be INFERRED because predictions vanished (the Tier-B invisibility;
            # the A4 answer-key-cleaning hypothesis) — scores are not evidence about
            # WHAT the model said, only how it scored. Draft JSON diffs directly
            # against GT (same type); the render (repeat-invariant: deterministic)
            # grounds render-vs-GT questions per run without chasing markdowns/.
            if predicted is not None:
                (pred_dir / f"{name}_r{k}.json").write_text(
                    predicted.model_dump_json(indent=2), encoding="utf-8")
            if k == 0 and rendered:
                (pred_dir / f"{name}_render.md").write_text(rendered, encoding="utf-8")
            rs = score_rubric(predicted, gt, rendered, meta=meta)
            apply_gate(rs, cost_ceiling)
            # ADDITIVE latency instrument (Phase 0): the scorer is IMMUTABLE and
            # never sets these; the runner attaches t_doc + decomposition AFTER
            # scoring so results.json carries latency with zero change to scoring
            # or gate semantics. Absent on an exception record (meta lacks the keys
            # ⇒ .get returns None), which is the honest "no timing for a crash".
            rs.total_seconds = meta.get("total_seconds")
            rs.render_seconds = meta.get("render_seconds")
            rs.wall_seconds = meta.get("wall_seconds")
            rs.input_tokens = meta.get("input_tokens")
            rs.output_tokens = meta.get("output_tokens")
            rs.stage_timings = [
                StageTiming(
                    stage=e.get("stage"), attempt=e.get("attempt"),
                    elapsed_s=e.get("elapsed_s"), dt_s=e.get("dt_s"),
                    input_tokens=e.get("input_tokens"), output_tokens=e.get("output_tokens"),
                )
                for e in (meta.get("stage_events") or [])
            ]
            per_rubric.append(rs)
            model_v = model_v or rs.model_version
            prompt_v = prompt_v or rs.prompt_version
            pipeline_v = pipeline_v or meta.get("pipeline_version")

    provenance = {
        "config": config_name, "mode": mode, "repeats": repeats,
        "fixtures": [n for n, _, _ in rubrics],
        "prompt_version": prompt_v, "model_version": model_v,
        # Stamped from the actual run (config value is a legacy fallback only) —
        # the sole drift signal for pipeline-code changes, which suite_hash misses.
        "pipeline_version": pipeline_v or config.get("pipeline_version"),
        "suite_hash": _suite_hash(suite_dir),
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
        "cost_ceiling": cost_ceiling,
    }
    suite = SuiteResult(provenance=provenance, per_rubric=per_rubric)
    suite.aggregates = reporting.aggregate(per_rubric)

    reporting.write_all(suite, out_dir)
    print(f"[done] {suite.aggregates['gate_pass_count']}/{len(per_rubric)} pass → {out_dir}")
    return suite


def score_only(
    predicted: Optional[ExtractRubricResponse],
    gt: ExtractRubricResponse,
    rendered_markdown: str,
    *,
    cost_ceiling: float = 0.40,
    meta: Optional[dict] = None,
):
    """Score a single (predicted, gt) pair without the pipeline. For tests / re-scoring."""
    rs = score_rubric(predicted, gt, rendered_markdown, meta=meta or {})
    apply_gate(rs, cost_ceiling)
    return rs


def main():
    ap = argparse.ArgumentParser(description="Rubric extraction eval suite")
    ap.add_argument("--config", default="default")
    ap.add_argument("--mode", default="extract", choices=["extract"])
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--only", default=None,
                    help="SCREENING ONLY: comma-separated fixture names to run a "
                         "subset (NON-PROMOTABLE). Omit for all fixtures.")
    args = ap.parse_args()
    run(args.config, args.mode, args.repeats, only=args.only)


if __name__ == "__main__":
    main()