"""
p2_replay.py — replay P2 ALONE, under a given config, on the P1 text a finished run
saved (code-symbol mission, 2026-09-30). P1 is held fixed (its saved pages;
`pages_after_relocation` when arrows moved text), so two replays of the same results
directory under two configs are paired BY INPUT and measure answer-splitting only.
Costs one P2 call per replay.

Each P2 output is scored with the suite's own scorer (gate, ratio, critical misses)
and with code_attribution's P2 (splitting) miss count. History: the first version
also scored a deterministic "section adoption" rule on the same outputs; that rule
was KILLED (RUNLOG 2026-09-30) and removed.

Usage (from backend/):
  python -m tests.transcription_eval_suit.p2_replay <results_dir> --config prod --repeats 3
  python -m tests.transcription_eval_suit.p2_replay <results_dir> --compare prod p2tb
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

from .code_attribution import attribute_record
from .runner import (
    SCORING_POLICY, RunPlan, _load_config, make_default_pipeline, resolve_fixtures,
)
from .scoring import gate_pass, score_document


def _score(answers, fx):
    s = score_document(answers, fx.draft_gold, profile=fx.profile, policy=SCORING_POLICY)
    ok, reasons = gate_pass(s)
    miss = sum(len(a.critical.missed_operators) + len(a.critical.missed_structural)
               + len(a.critical.missed_method_calls) for a in s.answers)
    return {"ratio": s.doc_ratio_strict, "gate": ok, "reasons": reasons, "crit_miss": miss}


def _key_str(k):
    return f"Q{k[0]}" + (f".{k[1]}" if k[1] else "")


async def replay(d: Path, config: str, repeats: int) -> list[dict]:
    cfg = _load_config(config)
    pipe = make_default_pipeline(cfg)
    res = json.loads((d / "results.json").read_text(encoding="utf-8"))
    docs = sorted({r["doc_id"] for r in res["records"]})
    fxs = {fx.doc_id: fx for fx in resolve_fixtures(
        RunPlan(config=cfg, config_name=config, fixtures=tuple(docs), mode="per_doc"))}
    rows = []
    for rec in res["records"]:
        doc, rep = rec["doc_id"], rec["repeat"]
        o = json.loads((d / "outputs" / f"{doc}__rep{rep}.json").read_text(encoding="utf-8"))
        pages = {int(k): v for k, v in (o.get("pages_after_relocation") or o["pages"]).items()}
        fx = fxs[doc]
        for k in range(repeats):
            run = await pipe.run_phase2(pages, fx.exam_spec, f"{doc}#r{rep}.{k}")
            sc = _score(dict(run.answers), fx)
            out = {"pages": {str(n): t for n, t in pages.items()},
                   "answers": {_key_str(kk): v for kk, v in run.answers.items()}}
            sc["p2_miss"] = sum(m["n"] for m in attribute_record(doc, out)["misses"]
                                if m["stage"] == "P2")
            rows.append({"doc": doc, "rep": rep, "k": k, "score": sc,
                         "cost": run.trace.total_cost_usd()})
            print(f"{doc[-26:]:26s} r{rep}.{k}  gate {int(sc['gate'])}  ratio {sc['ratio']:.4f}  "
                  f"crit-miss {sc['crit_miss']}  P2-miss {sc['p2_miss']}", flush=True)
    return rows


def summarize(rows: list[dict]) -> dict:
    by = defaultdict(list)
    for r in rows:
        by[r["doc"]].append(r["score"])
    return {d: {"gate": sum(s["gate"] for s in ss), "n": len(ss),
                "ratio": st.mean(s["ratio"] for s in ss),
                "crit": sum(s["crit_miss"] for s in ss), "p2": sum(s["p2_miss"] for s in ss)}
            for d, ss in by.items()}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("results_dir")
    ap.add_argument("--config", default="prod")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--compare", nargs=2, metavar=("BASE", "VARIANT"),
                    help="print a paired table from two saved replays (no API calls)")
    args = ap.parse_args()
    d = Path(args.results_dir)
    if args.compare:
        a, b = (summarize(json.loads((d / f"p2_replay_{c}.json").read_text(encoding="utf-8"))["rows"])
                for c in args.compare)
        print(f"{'document':34s} gate  ratio  crit-miss  P2-miss   ({args.compare[0]} -> {args.compare[1]})")
        for doc in sorted(a):
            x, y = a[doc], b[doc]
            print(f"{doc:34s} {x['gate']}/{x['n']}->{y['gate']}/{y['n']}  {x['ratio']:.4f}->{y['ratio']:.4f}"
                  f"  {x['crit']:3d}->{y['crit']:3d}  {x['p2']:3d}->{y['p2']:3d}")
        return
    rows = asyncio.run(replay(d, args.config, args.repeats))
    print(f"\nspend: ${sum(r['cost'] for r in rows):.3f} over {len(rows)} P2 calls")
    (d / f"p2_replay_{args.config}.json").write_text(
        json.dumps({"rows": rows}, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
