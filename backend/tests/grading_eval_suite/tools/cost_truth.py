"""
COST_TRUTH ledger — the suite side of the owner-ordered reconciliation
(H-4 item 4, blocking Stage 1).

    python -m tests.grading_eval_suite.tools.cost_truth

Aggregates every results dir into per-(UTC day, model_key) token and dollar
totals, with the provider-REPORTED served models alongside the requested id.
This table is diffed against the provider dashboards (OpenAI usage view /
Anthropic console / GCP billing filtered by the eval request labels) after
each Stage — the protocol lives in COST_TRUTH.md.

Invalid trials are INCLUDED: the provider billed them whether or not the
instrument kept them, and a ledger that drops them cannot reconcile.
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

SUITE = Path(__file__).resolve().parents[1]


def collect(results_dir: Path) -> Dict[Tuple[str, str], dict]:
    rows: Dict[Tuple[str, str], dict] = defaultdict(
        lambda: {"input": 0, "cached": 0, "output": 0, "cost": 0.0,
                 "trials": 0, "served": set(), "runs": set()})
    for run in sorted(results_dir.iterdir()):
        rj = run / "results.json"
        if not rj.exists():
            continue
        res = json.loads(rj.read_text(encoding="utf-8"))
        prov = res.get("provenance", {})
        day = str(prov.get("timestamp", ""))[:10] or "????-??-??"
        key = (day, prov.get("model_key", "?"))
        r = rows[key]
        r["runs"].add(run.name)
        r["served"].update(prov.get("served_models", []))
        for t in res.get("trials", []):
            r["trials"] += 1
            r["input"] += t.get("input_tokens", 0) or 0
            r["cached"] += t.get("cached_input_tokens") or 0
            r["output"] += t.get("output_tokens", 0) or 0
            r["cost"] += t.get("cost_usd") or 0.0
    return rows


def render(rows: Dict[Tuple[str, str], dict]) -> str:
    L: List[str] = ["# COST_TRUTH ledger — suite-side token/dollar totals", ""]
    L.append("| UTC day | model_key | served (provider-reported) | trials | "
             "input tok | cached tok | output tok | $ computed | runs |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    total = 0.0
    for (day, mk), r in sorted(rows.items()):
        total += r["cost"]
        L.append(f"| {day} | {mk} | {', '.join(sorted(r['served'])) or '-'} | "
                 f"{r['trials']} | {r['input']:,} | {r['cached']:,} | "
                 f"{r['output']:,} | ${r['cost']:.4f} | {len(r['runs'])} |")
    L.append("")
    L.append(f"**Total computed spend: ${total:.4f}** — diff each row against "
             f"the provider dashboard for that UTC day before the next Stage.")
    return "\n".join(L)


def main() -> None:
    results = SUITE / "results"
    out = render(collect(results))
    (SUITE / "COST_TRUTH_LEDGER.md").write_text(out + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
