"""
grader-v6 — the K2 / G-Z RESIDUAL, read two ways (owner rulings 2026-10-06 evening §7.3, §9). $0.

    python -m tests.grading_eval_suite.tools.v6_residual \\
        --run v5=<dir> --run v6_old=<dir> [--run v6_diag=<dir>] [--run v6_new=<dir>] \\
        [--plans old=archive:planner-v6.1] [--plans s55=recorded:claude-sonnet-5.5] \\
        [--plans opus=recorded:claude-opus-5.5] [--plans new=pinned] [--cells-from v6_old]

1. SPLIT BY FULL VALUE. Each run's K2 cells (GT-PARTIAL→AI-FULL) and G-Z cells
   (GT-PARTIAL→AI-ZERO), split by the cell's full value — the terminal's points, `< 2` and
   `≥ 2` (the AM-G19 line) — in cells AND in points (K2: AI − GT over-credited; G-Z: GT − AI
   lost). The cells are exactly the ones the kills count: the gate instrument's own row
   filter (`gates._included_rows` — invalid and model_fallback trials out, CONTESTED cells
   out). For reading the residual only; the kill is evaluated on cells, as ruled.

2. EXPRESSIBILITY OF A RUN'S CELLS. For the K2 and G-Z cells of `--cells-from`, whether each
   plan set can price the cell's GT award at all (§13.1, `reachable_awards_v6` — THE pricer
   over every option combination). A plan set is `pinned` (plans/v6/<exam>.plan.json),
   `archive:<tag>` (plans/v6/archive/<exam>.<tag>.plan.json), or `recorded:<model>` (that
   model's recording replayed offline, exactly as the tests replay it).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.agents.grader.plan_schemas import GradingPlanV6                         # noqa: E402
from app.agents.plan_compiler.stage1_v6 import compile_stage1_v6                 # noqa: E402
from tests.grading_eval_suite.fixtures import SUITE_DIR, load_bundle             # noqa: E402
from tests.grading_eval_suite.plan_v6_expressibility import reachable_awards_v6  # noqa: E402
from tests.grading_eval_suite.tools.gates import _cls, _included_rows           # noqa: E402

AM_G19_LINE = Decimal("2")
EXAM_FIXTURE = {"hobby_tvshow": "din_ezra", "bagrut_899371": "bagrut_899371.din_ezra"}
PLAN_DIR = SUITE_DIR / "plans" / "v6"


def _load(run_dir: Path):
    res = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    points, contested, exam_of = {}, {}, {}
    for fx in res["provenance"].get("fixtures", []):
        b = load_bundle(fx)
        exam_of[fx] = b.exam_id
        for tid, info in b.terminal_infos.items():
            points[(fx, tid)] = info.points
        for t in b.gt.terminals:
            if t.contested is not None:
                contested[(fx, t.terminal_id)] = t.contested
    return res, points, contested, exam_of


def cells(run_dir: Path) -> List[dict]:
    """Every K2 / G-Z cell of a run, with its full value and its points."""
    res, points, contested, exam_of = _load(run_dir)
    out = []
    for r in _included_rows(res["trials"], contested):
        possible = points[(r["fixture"], r["terminal_id"])]
        gt, ai = Decimal(r["gt_awarded"]), Decimal(r["ai_awarded"])
        key = (_cls(gt, possible), _cls(ai, possible))
        kind = {("PARTIAL", "FULL"): "K2", ("PARTIAL", "ZERO"): "GZ"}.get(key)
        if kind is None and key[0] != "PARTIAL":
            continue
        out.append({"kind": kind or "partial_other", "fixture": r["fixture"],
                    "exam": exam_of[r["fixture"]], "terminal_id": r["terminal_id"],
                    "trial": r.get("trial_index"), "possible": possible, "gt": gt, "ai": ai,
                    "band": "≥2" if possible >= AM_G19_LINE else "<2"})
    return out


def split_table(runs: Dict[str, Path]) -> List[str]:
    L = ["| run | band | GT-partial cells | K2 cells | K2 points over-credited | G-Z cells | G-Z points lost |",
         "|---|---|---|---|---|---|---|"]
    for label, d in runs.items():
        cs = cells(d)
        for band in ("<2", "≥2", "all"):
            sel = [c for c in cs if band == "all" or c["band"] == band]
            k2 = [c for c in sel if c["kind"] == "K2"]
            gz = [c for c in sel if c["kind"] == "GZ"]
            n = len(sel)
            L.append(f"| {label} | {band} | {n} | {len(k2)} ({_pct(len(k2), n)}) | "
                     f"{_fmt(sum((c['ai'] - c['gt'] for c in k2), Decimal(0)))} | "
                     f"{len(gz)} ({_pct(len(gz), n)}) | {_fmt(sum((c['gt'] - c['ai'] for c in gz), Decimal(0)))} |")
    return L


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}%" if b else "—"


def _fmt(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return "0" if s in ("-0", "0") else s


async def _replay(exam: str, model: str) -> GradingPlanV6:
    from tests.grading_eval_suite.tools.planner_report import _replay as replay
    rec = json.loads((PLAN_DIR / f"{exam}.{model}.recorded.json").read_text(encoding="utf-8"))
    _s1, _results, plan = await replay(exam, rec)
    return plan


def load_plans(spec: str) -> Dict[str, GradingPlanV6]:
    out = {}
    for exam in EXAM_FIXTURE:
        if spec == "pinned":
            p = PLAN_DIR / f"{exam}.plan.json"
        elif spec.startswith("archive:"):
            p = PLAN_DIR / "archive" / f"{exam}.{spec.split(':', 1)[1]}.plan.json"
        elif spec.startswith("recorded:"):
            out[exam] = asyncio.run(_replay(exam, spec.split(":", 1)[1]))
            continue
        elif spec.startswith("dir:"):                       # [Item C] e.g. dir:run11 → plans/v6/run11/
            p = PLAN_DIR / spec.split(":", 1)[1] / f"{exam}.plan.json"
        else:
            raise SystemExit(f"unknown plan spec {spec!r}")
        out[exam] = GradingPlanV6.model_validate_json(p.read_text(encoding="utf-8"))
    return out


def expressible_table(cell_rows: List[dict], plan_sets: Dict[str, Dict[str, GradingPlanV6]]) -> List[str]:
    precision = {}
    for exam, fx in EXAM_FIXTURE.items():
        b = load_bundle(fx, require_gt=False)
        precision[exam] = compile_stage1_v6(b.rubric_contract, exam_id=exam,
                                            rubric_contract_sha256="x").precision
    cache: Dict[Tuple[str, str, str], object] = {}

    def reach(label, exam, tid):
        k = (label, exam, tid)
        if k not in cache:
            cache[k] = reachable_awards_v6(plan_sets[label][exam], tid, precision[exam])
        return cache[k]

    L = ["| cells | n | " + " | ".join(f"expressible under `{l}`" for l in plan_sets) + " |",
         "|---|---|" + "---|" * len(plan_sets)]
    for kind in ("K2", "GZ"):
        sel = [c for c in cell_rows if c["kind"] == kind]
        row = [f"{'K2' if kind == 'K2' else 'G-Z'}", str(len(sel))]
        for label in plan_sets:
            ok = 0
            for c in sel:
                r = reach(label, c["exam"], c["terminal_id"])
                ok += r is None or c["gt"] in r
            row.append(f"{ok} ({_pct(ok, len(sel))})")
        L.append("| " + " | ".join(row) + " |")
    by_t = defaultdict(lambda: [0, 0])
    for c in cell_rows:
        if c["kind"] in ("K2", "GZ"):
            by_t[(c["exam"], c["terminal_id"], str(c["gt"]), c["possible"])][0 if c["kind"] == "K2" else 1] += 1
    L += ["", "| exam · terminal · GT award / full | K2 · G-Z cells | " +
          " | ".join(f"`{l}` can price it" for l in plan_sets) + " |",
          "|---|---|" + "---|" * len(plan_sets)]
    for (exam, tid, gt, possible), (k2, gz) in sorted(by_t.items(), key=lambda kv: -sum(kv[1])):
        marks = []
        for label in plan_sets:
            r = reach(label, exam, tid)
            marks.append("—" if r is None else ("✅" if Decimal(gt) in r else "❌"))
        L.append(f"| {exam} `{tid}` {gt}/{_fmt(possible)} | {k2} · {gz} | " + " | ".join(marks) + " |")
    return L


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="append", default=[], help="label=run_dir")
    ap.add_argument("--plans", action="append", default=[], help="label=pinned|archive:<tag>|recorded:<model>")
    ap.add_argument("--cells-from", default=None, help="the run label whose K2/G-Z cells are checked")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    runs = {k: Path(v) for k, v in (x.split("=", 1) for x in args.run)}
    L = ["### K2 and G-Z by full value (cells and points)", ""] + split_table(runs)
    if args.plans and args.cells_from:
        plan_sets = {k: load_plans(v) for k, v in (x.split("=", 1) for x in args.plans)}
        L += ["", f"### The K2 and G-Z cells of `{args.cells_from}`: can each plan price the GT award?", ""]
        L += expressible_table(cells(runs[args.cells_from]), plan_sets)
    text = "\n".join(L) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
