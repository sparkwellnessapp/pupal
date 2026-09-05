"""
A1 / A2 — the SPEND stages of PLAN COMPILER v2 (PR §7), under hard envelopes.

    python tests/grading_eval_suite/tools/segment_plan.py --stage both --dry-run
    python tests/grading_eval_suite/tools/segment_plan.py --exam hobby_tvshow --stage route \\
           --envelope-usd 1.0 --confirm-spend
    python tests/grading_eval_suite/tools/segment_plan.py --stage segment --envelope-usd 2.0 --confirm-spend

Stage 2b (route, Sonnet 5) runs BEFORE Stage 2 (segment, Haiku 4.5) so routed
components get wording too. `--dry-run` builds every message, prints sizes and
a conservative cost ESTIMATE, and calls nothing. A real run needs
`--confirm-spend` and stops itself the moment the envelope is reached.

A0 gates all spend (PR §7): this tool refuses a real run while the compiled
A0 artefacts are missing, and prints the A0 verdict line it found so the
operator sees what they are spending on.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import statistics
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE.parents[1]))

from app.agents.grader.plan_validator import validate_plan                         # noqa: E402
from app.agents.plan_compiler import compile_contract                              # noqa: E402
from app.agents.plan_compiler.assemble import assemble_plan                        # noqa: E402
from app.agents.plan_compiler.route import (ROUTER_MODEL_KEY, ROUTER_PROMPT_VERSION,  # noqa: E402
                                            build_router_message, route_monoliths)
from app.agents.plan_compiler.segment import (SEGMENTER_MODEL_KEY,                 # noqa: E402
                                              SEGMENTER_PROMPT_VERSION,
                                              build_segmenter_message,
                                              segment_skeleton, substitute)
from app.agents.plan_compiler.stage0 import contract_scopes, scope_label, terminals_of  # noqa: E402
from app.agents.plan_gen.prompt import scope_corpus                                # noqa: E402
from app.services.transcription.two_phase.instrument import cost_usd               # noqa: E402
from app.services.transcription.vlm_provider import Usage                          # noqa: E402
from tests.eval_common.models_registry import spec                                 # noqa: E402
from tests.grading_eval_suite.fixtures import load_bundle, read_gt_judgments       # noqa: E402
from tests.grading_eval_suite.plan_expressibility import reachable_awards          # noqa: E402
from tests.grading_eval_suite.tools.compile_plan import discover_exams             # noqa: E402

OUT_DIR = SUITE / "plans" / "compiled"
RUNLOG = SUITE / "RUNLOG.md"
A0_REPORT = SUITE.parents[1] / "app" / "agents" / "plan_gen" / "A0_REPORT.md"

# Conservative token estimate for Hebrew-heavy text on a Claude tokenizer
# (~30% more tokens than older models; ≈1 token per 2.5 chars), output ≈ 60% of
# input for the segmenter (it echoes every span), ≈ 25% for the router.
CHARS_PER_TOKEN = 2.5


def _scope_maps(contract):
    corpora, solutions, questions = {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = scope_label(key)
        corpora[lbl] = scope_corpus(q, sub)
        node = sub or q
        sol = next((getattr(n, "example_solution", None) for n in (node, q)
                    if (getattr(n, "example_solution", None) or "").strip()), None)
        if sol:
            solutions[lbl] = sol
        qt = " ".join(s for s in (getattr(q, "question_text", None), getattr(sub, "text", None) if sub else None)
                      if isinstance(s, str) and s.strip())
        questions[lbl] = qt
    return corpora, solutions, questions


def _cost_fn(model_key: str):
    card = spec(model_key).price

    def fn(in_tok: int, out_tok: int, cached: Optional[int]) -> float:
        return cost_usd(Usage(input_tokens=in_tok, output_tokens=out_tok,
                              cached_input_tokens=cached), card)
    return fn


def _estimate(messages: List[str], system_chars: int, model_key: str, out_ratio: float) -> float:
    card = spec(model_key).price
    in_tok = sum((len(m) + system_chars) / CHARS_PER_TOKEN for m in messages)
    out_tok = in_tok * out_ratio
    return (in_tok * card.in_per_mtok + out_tok * card.out_per_mtok) / 1_000_000


def _compile(exam: str, fixtures: List[str]):
    b0 = load_bundle(fixtures[0], require_gt=False)
    manifest = json.loads((SUITE / "fixtures" / f"{fixtures[0]}.json").read_text(encoding="utf-8"))
    sha = hashlib.sha256((SUITE / manifest["rubric_contract"]).read_bytes()).hexdigest()
    contract = b0.rubric_contract
    return contract, compile_contract(contract, exam_id=exam, rubric_contract_sha256=sha)


def _validate(plan, contract):
    points, scopes, corpora = {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = scope_label(key)
        corpora[lbl] = scope_corpus(q, sub)
        for tid, pts in terminals_of(sub or q):
            points[tid] = pts
            scopes[tid] = lbl
    return validate_plan(plan, contract_terminal_points=points, terminal_scopes=scopes,
                         precision=Decimal(str(contract.numeric_policy.precision)),
                         scope_corpora=corpora)


def _expressibility(plan, fixtures: List[str], precision: Decimal):
    by = {t.terminal_id: t for t in plan.terminals}
    total = ok = 0
    for name in fixtures:
        _b, judgments = read_gt_judgments(name)
        for tid, award in judgments:
            total += 1
            if award in reachable_awards(by[tid], precision):
                ok += 1
    return ok, total


async def run_exam(exam: str, fixtures: List[str], *, stage: str, dry_run: bool,
                   envelope_route: float, envelope_segment: float) -> dict:
    from app.agents.plan_compiler.segment import SEGMENTER_SYSTEM_PROMPT
    from app.agents.plan_compiler.route import ROUTER_SYSTEM_PROMPT

    contract, skeleton = _compile(exam, fixtures)
    precision = Decimal(str(contract.numeric_policy.precision))
    corpora, solutions, questions = _scope_maps(contract)
    out: Dict[str, object] = dict(exam=exam, stage=stage, dry_run=dry_run)

    # ── Stage 2b ──────────────────────────────────────────────────────────
    if stage in ("route", "both"):
        routed = [t for t in skeleton.terminals if t.routed]
        msgs = [build_router_message(t, questions.get(t.scope, ""), solutions.get(t.scope, ""))
                for t in routed]
        est = _estimate(msgs, len(ROUTER_SYSTEM_PROMPT), ROUTER_MODEL_KEY, 0.25)
        out["route_calls_planned"] = len(msgs)
        out["route_chars"] = [len(m) for m in msgs]
        out["route_estimate_usd"] = round(est, 4)
        print(f"  [route] {len(msgs)} monolith(s): {[t.terminal_id for t in routed]}")
        print(f"  [route] message chars {out['route_chars']} · estimate ≈ ${est:.3f} "
              f"(envelope ${envelope_route:.2f})")
        if not dry_run:
            if est > envelope_route:
                raise SystemExit(f"route estimate ${est:.3f} exceeds the envelope — refusing")
            from app.agents.grader.llm_factory import build_chat_model
            llm = build_chat_model("anthropic", spec(ROUTER_MODEL_KEY).model_id,
                                   max_output_tokens=2000, timeout_s=180)
            t0 = time.monotonic()
            rr = await route_monoliths(skeleton, llm, corpora=corpora, solutions=solutions,
                                       questions=questions, cost_fn=_cost_fn(ROUTER_MODEL_KEY),
                                       envelope_usd=envelope_route)
            skeleton = rr.skeleton
            out["route"] = dict(
                cost_usd=round(rr.cost_usd, 4), calls=len(rr.calls), failed=rr.failed,
                wall_s=round(time.monotonic() - t0, 1),
                components={c.terminal_id: list(c.components) for c in rr.calls if not c.errors},
                latency_s=[round(c.latency_s, 1) for c in rr.calls],
                flags=[(f.code, f.terminal_id, f.detail) for f in rr.flags])
            print(f"  [route] ${rr.cost_usd:.4f} · {len(rr.calls)} calls · failed {rr.failed}")
            for c in rr.calls:
                if not c.errors:
                    print(f"     {c.terminal_id}: {list(c.components)}")

    # ── Stage 2 ───────────────────────────────────────────────────────────
    if stage in ("segment", "both"):
        by_scope: Dict[str, list] = {}
        for t in skeleton.terminals:
            by_scope.setdefault(t.scope, []).append(t)
        msgs = [build_segmenter_message(s, ts, solutions.get(s)) for s, ts in by_scope.items()]
        est = _estimate(msgs, len(SEGMENTER_SYSTEM_PROMPT), SEGMENTER_MODEL_KEY, 0.6)
        out["segment_calls_planned"] = len(msgs)
        out["segment_chars"] = [len(m) for m in msgs]
        out["segment_estimate_usd"] = round(est, 4)
        print(f"  [segment] {len(msgs)} scope call(s) · chars {out['segment_chars']} · "
              f"estimate ≈ ${est:.3f} (envelope ${envelope_segment:.2f})")
        if not dry_run:
            if est > envelope_segment:
                raise SystemExit(f"segment estimate ${est:.3f} exceeds the envelope — refusing")
            from app.agents.grader.llm_factory import build_chat_model
            llm = build_chat_model("anthropic", spec(SEGMENTER_MODEL_KEY).model_id,
                                   max_output_tokens=6000, timeout_s=120)
            t0 = time.monotonic()
            sr = await segment_skeleton(skeleton, llm, corpora=corpora, solutions=solutions,
                                        cost_fn=_cost_fn(SEGMENTER_MODEL_KEY),
                                        envelope_usd=envelope_segment)
            plan = assemble_plan(skeleton, sr.wording,
                                 segmenter_prompt_version=SEGMENTER_PROMPT_VERSION,
                                 segmenter_model=spec(SEGMENTER_MODEL_KEY).model_id,
                                 router_model=(spec(ROUTER_MODEL_KEY).model_id
                                               if stage == "both" else None))
            errors = _validate(plan, contract)
            ok, total = _expressibility(plan, fixtures, precision)
            slots = sum(len(t.slots) for t in skeleton.terminals)
            lat = [c.latency_s for c in sr.calls]
            out["segment"] = dict(
                cost_usd=round(sr.cost_usd, 4), calls=len(sr.calls),
                clean_first_try=sr.clean_first_try, retried=sum(1 for c in sr.calls if c.attempt == 2),
                slots=slots, substituted=sr.substituted, notes_dropped=sr.notes_dropped,
                validator_errors=errors, expressible=f"{ok}/{total}",
                wall_s=round(time.monotonic() - t0, 1),
                latency_p50_s=round(statistics.median(lat), 1) if lat else None,
                latency_max_s=round(max(lat), 1) if lat else None,
                plan_version=plan.plan_version,
                flags=[(f.code, f.terminal_id, f.detail) for f in sr.flags])
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            tag = "routed+segmented" if stage == "both" else "segmented"
            (OUT_DIR / f"{exam}.{tag}.plan.json").write_text(
                json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=1), encoding="utf-8")
            (OUT_DIR / f"{exam}.{tag}.wording.json").write_text(
                json.dumps({k: list(v) for k, v in sr.wording.items()}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            (OUT_DIR / f"{exam}.{tag}.run.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
            print(f"  [segment] ${sr.cost_usd:.4f} · {len(sr.calls)} calls · clean first try "
                  f"{sr.clean_first_try}/{len(by_scope)} · substituted {len(sr.substituted)}/{slots} · "
                  f"validator {len(errors)} · expressible {ok}/{total}")
    return out


def _runlog(results: List[dict]) -> None:
    lines = [f"\n## {time.strftime('%Y-%m-%d')} · PLAN COMPILER v2 · A1/A2 (spend stages)\n"]
    for r in results:
        lines.append(f"- **{r['exam']}** stage={r['stage']}")
        if "route" in r:
            rr = r["route"]
            lines.append(f"  - route (Sonnet 5): ${rr['cost_usd']} · {rr['calls']} calls · failed {rr['failed']} · "
                         f"wall {rr['wall_s']}s · components {rr['components']}")
        if "segment" in r:
            sr = r["segment"]
            lines.append(f"  - segment (Haiku 4.5): ${sr['cost_usd']} · {sr['calls']} calls · clean first try "
                         f"{sr['clean_first_try']} · retried {sr['retried']} · substituted "
                         f"{len(sr['substituted'])}/{sr['slots']} · notes dropped {len(sr['notes_dropped'])} · "
                         f"validator {len(sr['validator_errors'])} · expressible {sr['expressible']} · "
                         f"p50 {sr['latency_p50_s']}s max {sr['latency_max_s']}s · plan `{sr['plan_version']}`")
    RUNLOG.write_text(RUNLOG.read_text(encoding="utf-8").rstrip("\n") + "\n" + "\n".join(lines) + "\n",
                      encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--exam", default=None)
    ap.add_argument("--stage", choices=["route", "segment", "both"], default="both")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--confirm-spend", action="store_true")
    ap.add_argument("--envelope-route-usd", type=float, default=1.0)     # A2 ≤ $1 (PR §9)
    ap.add_argument("--envelope-segment-usd", type=float, default=2.0)   # A1 ≤ $2 (PR §9)
    args = ap.parse_args()
    if not args.dry_run and not args.confirm_spend:
        raise SystemExit("a real run spends money: pass --confirm-spend (or --dry-run)")
    if not args.dry_run:
        if not (OUT_DIR / "hobby_tvshow.plan.json").exists() or not A0_REPORT.exists():
            raise SystemExit("A0 gates all spend (PR §7): run tools/compile_plan.py first")
        verdicts = [l.strip() for l in A0_REPORT.read_text(encoding="utf-8").splitlines()
                    if "A0 verdict" in l]
        print("A0 verdicts on record:\n  " + "\n  ".join(verdicts))
    exams = discover_exams()
    todo = [args.exam] if args.exam else list(exams)
    results = []
    for exam in todo:
        print(f"\n===== {'DRY RUN' if args.dry_run else 'RUN'} · {exam} · stage {args.stage} =====")
        results.append(asyncio.run(run_exam(exam, exams[exam], stage=args.stage, dry_run=args.dry_run,
                                            envelope_route=args.envelope_route_usd,
                                            envelope_segment=args.envelope_segment_usd)))
    if not args.dry_run:
        _runlog(results)
        print(f"\nRUNLOG appended → {RUNLOG.relative_to(SUITE.parents[1])}")


if __name__ == "__main__":
    main()
