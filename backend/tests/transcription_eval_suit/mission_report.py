"""
mission_report.py — the per-dimension read of one or more results.json
(MISSION_transcription_accuracy §2/§4.3). Read-only over run artifacts.

For every dimension it reports the WORST document first (the mean is never the
only aggregate here), the per-exam split (a win on one exam only is suspect), and
the validity and cost/latency constraints (C2/C3/C4) beside the accuracy.

Usage (from backend/):
    python -m tests.transcription_eval_suit.mission_report <results_dir> [<results_dir> ...]
Several directories are pooled (e.g. k parallel k=1 runs of one config).
`--rescored` reads results_rescored.json (rescore.py) instead of results.json.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

COST_CEILING = 0.08          # runner.COST_CEILING_USD — the C2 line
LATENCY_P95_LINE_S = 240.0   # C3: half of budget.py's 480 s


def _load(dirs: list[str], rescored: bool = False) -> tuple[list[dict], dict]:
    recs, meta = [], {}
    for d in dirs:
        f = Path(d) / ("results_rescored.json" if rescored else "results.json")
        data = json.loads(f.read_text(encoding="utf-8"))
        meta = {k: data.get(k) for k in ("config_name", "mode", "prompt_version", "models")}
        meta.setdefault("failed_runs", [])
        meta["failed_runs"] = meta["failed_runs"] + list(data.get("failed_runs") or [])
        recs += data["records"]
    return recs, meta


def _exam(doc: str) -> str:
    return doc.split(".")[0]


def _pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = max(0, min(len(xs) - 1, int(round(q * (len(xs) - 1)))))
    return xs[k]


def summarize(dirs: list[str], rescored: bool = False) -> dict:
    recs, meta = _load(dirs, rescored)
    by_doc: dict[str, list[dict]] = defaultdict(list)
    for r in recs:
        by_doc[r["doc_id"]].append(r)

    doc_rows = {}
    for doc, rs in sorted(by_doc.items()):
        def mean_of(f):
            vals = [v for v in (f(r) for r in rs) if v is not None]
            return statistics.mean(vals) if vals else None

        def minv(f):
            vals = [v for v in (f(r) for r in rs) if v is not None]
            return min(vals) if vals else None

        d = lambda r, *k: _dig(r, *k)
        doc_rows[doc] = {
            "exam": _exam(doc), "n": len(rs),
            "p1_ratio": mean_of(lambda r: d(r, "p1", "doc_ratio_strict")),
            "e2e_ratio": mean_of(lambda r: d(r, "e2e", "doc_ratio_strict")),
            "p1_gate_rate": mean_of(lambda r: None if not r.get("p1") else float(r["p1"]["gate"]["passed"])),
            "e2e_gate_rate": mean_of(lambda r: None if not r.get("e2e") else float(r["e2e"]["gate"]["passed"])),
            "heb_p1": mean_of(lambda r: d(r, "diag", "hebrew_p1", "doc", "ratio")),
            "heb_p1_min": minv(lambda r: d(r, "diag", "hebrew_p1", "doc", "ratio")),
            "heb_p1_wer": mean_of(lambda r: d(r, "diag", "hebrew_p1", "doc", "wer")),
            "heb_e2e": mean_of(lambda r: d(r, "diag", "hebrew_e2e", "doc", "ratio")),
            # the PROSE view (whole section-marker lines out, diag_hebrew): the
            # Hebrew-TEXT dimension. None = the doc has no Hebrew prose at all.
            "heb_prose": mean_of(lambda r: d(r, "diag", "hebrew_p1_prose", "doc", "ratio")),
            "heb_prose_min": minv(lambda r: d(r, "diag", "hebrew_p1_prose", "doc", "ratio")),
            "heb_prose_wer": mean_of(lambda r: d(r, "diag", "hebrew_p1_prose", "doc", "wer")),
            "tbl_expected": mean_of(lambda r: d(r, "diag", "tables_p1", "expected")),
            "tbl_shape": mean_of(lambda r: _rate(d(r, "diag", "tables_p1", "shape_exact"),
                                                 d(r, "diag", "tables_p1", "expected"))),
            "tbl_cells_exact": sum(d(r, "diag", "tables_p1", "cells_exact") or 0 for r in rs),
            "tbl_cells_total": sum(d(r, "diag", "tables_p1", "cells_total") or 0 for r in rs),
            "arrow_placed": sum(d(r, "diag", "arrows", "placed") or 0 for r in rs),
            "arrow_cases": sum(d(r, "diag", "arrows", "cases") or 0 for r in rs),
            "arrow_false": sum(d(r, "diag", "arrows", "false_relocations") or 0 for r in rs),
            "cost": mean_of(lambda r: r.get("cost_usd")),
            "wall_s": [r["latency_ms"] / 1000 for r in rs],
            "parse_failures": sum(r.get("parse_failures", 0) for r in rs),
            "truncations": sum(1 for r in rs for f in r.get("parse_failure_finish_reasons", [])
                               if str(f).upper() in ("MAX_TOKENS", "LENGTH")),
        }
        row = doc_rows[doc]
        row["tbl_cells"] = (row["tbl_cells_exact"] / row["tbl_cells_total"]
                            if row["tbl_cells_total"] else None)
    # VALIDITY (2026-09-28): an optional pass that silently failed (a lost strike
    # check: timeouts / 429 / a dead local network) leaves a record that LOOKS like a
    # result. Count records whose strike check covered every nonempty page.
    from .ground_truth import load_page_ground_truth
    suite = Path(__file__).parent
    sc_total = sc_full = 0
    for r in recs:
        sc = (r.get("tokens") or {}).get("strike_check")
        if sc is None:
            continue
        sc_total += 1
        pages = sum(1 for t in load_page_ground_truth(
            suite / "raw_benchmarks" / f"{r['doc_id']}.md").as_dict().values() if t.strip())
        sc_full += sc.get("calls", 0) >= pages
    walls = [w for r in doc_rows.values() for w in r["wall_s"]]
    costs = [r["cost"] for r in doc_rows.values() if r["cost"] is not None]
    return {"meta": meta, "docs": doc_rows,
            "wall_p50": _pct(walls, 0.5), "wall_p95": _pct(walls, 0.95),
            "cost_avg": statistics.mean(costs) if costs else None,
            "n_records": len(recs), "strike_full": sc_full, "strike_total": sc_total}


def _dig(r, *keys):
    for k in keys:
        if not isinstance(r, dict) or k not in r:
            return None
        r = r[k]
    return r


def _rate(a, b):
    return None if not b else a / b


def _f(x, w=6, p=4):
    return "—".rjust(w) if x is None else f"{x:{w}.{p}f}"


def render(s: dict) -> str:
    m = s["meta"]
    out = [f"# {m.get('config_name')} · mode={m.get('mode')} · prompt={m.get('prompt_version')} "
           f"· records={s['n_records']}", ""]
    hdr = ("| doc | n | P1 ratio | E2E ratio | P1 gate | E2E gate | Heb prose P1 (min) | prose WER "
           "| Heb all P1 | Heb E2E | tbl shape | tbl cells | arrows placed/cases (false) | $/doc | parse/trunc |")
    out += [hdr, "|" + "---|" * 15]
    for doc, r in s["docs"].items():
        out.append(
            f"| {doc} | {r['n']} | {_f(r['p1_ratio'])} | {_f(r['e2e_ratio'])} "
            f"| {_f(r['p1_gate_rate'],4,2)} | {_f(r['e2e_gate_rate'],4,2)} "
            f"| {_f(r['heb_prose'])} ({_f(r['heb_prose_min'],4,3)}) | {_f(r['heb_prose_wer'],5,3)} "
            f"| {_f(r['heb_p1'])} | {_f(r['heb_e2e'])} | {_f(r['tbl_shape'],4,2)} | {_f(r['tbl_cells'],5,3)} "
            f"| {r['arrow_placed']}/{r['arrow_cases']} ({r['arrow_false']}) "
            f"| {_f(r['cost'],6,4)} | {r['parse_failures']}/{r['truncations']} |")
    out.append("")

    def worst(key, lower_is_worse=True):
        vals = [(d, r[key]) for d, r in s["docs"].items() if r[key] is not None]
        if not vals:
            return "—"
        d, v = (min if lower_is_worse else max)(vals, key=lambda t: t[1])
        return f"{d} = {v:.4f}"

    out.append("## Worst document per dimension")
    out.append(f"- P1 ratio: {worst('p1_ratio')}")
    out.append(f"- E2E ratio: {worst('e2e_ratio')}")
    out.append(f"- Hebrew prose P1 ratio: {worst('heb_prose')}   (per-run min: {worst('heb_prose_min')})")
    out.append(f"- Hebrew prose P1 WER: {worst('heb_prose_wer', lower_is_worse=False)}")
    out.append(f"- Hebrew all (incl. markers) P1: {worst('heb_p1')}")
    out.append(f"- Table cells: {worst('tbl_cells')}")
    out.append("")
    out.append("## Per exam")
    for exam in sorted({r["exam"] for r in s["docs"].values()}):
        rows = [r for r in s["docs"].values() if r["exam"] == exam]
        def m_(k):
            v = [r[k] for r in rows if r[k] is not None]
            return statistics.mean(v) if v else None
        out.append(f"- **{exam}** (n={len(rows)}): P1 {_f(m_('p1_ratio'))} · E2E {_f(m_('e2e_ratio'))} "
                   f"· E2E gate {_f(m_('e2e_gate_rate'),4,2)} · Heb prose P1 {_f(m_('heb_prose'))} "
                   f"· $/doc {_f(m_('cost'),6,4)}")
    out.append("")
    cells_ex = sum(r["tbl_cells_exact"] for r in s["docs"].values())
    cells_t = sum(r["tbl_cells_total"] for r in s["docs"].values())
    out.append("## Constraints")
    out.append(f"- C2 cost: avg ${s['cost_avg']:.4f}/doc vs ${COST_CEILING:.2f} "
               f"→ {'PASS' if s['cost_avg'] is not None and s['cost_avg'] <= COST_CEILING else 'FAIL'}")
    out.append(f"- C3 latency: p50 {s['wall_p50']:.0f}s · p95 {s['wall_p95']:.0f}s "
               f"(line {LATENCY_P95_LINE_S:.0f}s) → "
               f"{'PASS' if s['wall_p95'] <= LATENCY_P95_LINE_S else 'SURFACE'}")
    pf = sum(r["parse_failures"] for r in s["docs"].values())
    tr = sum(r["truncations"] for r in s["docs"].values())
    out.append(f"- C4 validity: parse failures {pf} · truncations {tr}")
    fr = s["meta"].get("failed_runs") or []
    if fr:
        out.append(f"- ⚠ FAILED document-runs (all retries exhausted, isolated): {len(fr)} — "
                   + ", ".join(f"{x['doc_id']}#{x['repeat']}({x['kind']})" for x in fr))
    if s.get("strike_total"):
        full, tot = s["strike_full"], s["strike_total"]
        out.append(f"- Strike-check coverage: {full}/{tot} records complete"
                   + ("" if full == tot else "  ⚠ DEGRADED records — not a clean measurement"))
    out.append(f"- Tables micro cell-exact: "
               f"{(cells_ex / cells_t) if cells_t else float('nan'):.4f} ({cells_ex}/{cells_t})")
    return "\n".join(out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    rescored = "--rescored" in args          # rescore.py output: one GT for all arms
    print(render(summarize([a for a in args if a != "--rescored"], rescored)))
