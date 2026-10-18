"""
grader-v6 Item C (owner rulings 2026-10-18 §3c) — FREEZE run 10's K2 cells into their classes,
BEFORE any run-11 spend. $0, no model.

    python -m tests.grading_eval_suite.tools.v6_freeze_k2 <run10_dir>

Reads run 10's K2 cells (GT-PARTIAL → AI-FULL) with `v6_residual.cells` and classifies each by
(exam, terminal, GT award) exactly as `docs/EVAL_REPORT_v6.md` §6.2 read them:
  split          (11) — a 3-point criterion split into 1-point binaries: the GT value has no option
  verifier-miss  (21) — the GT value WAS an option; the verifier picked full
  plan-wording   (6)  — the plan's own label accepts what the teacher docked
  other          (6)  — a 1-point binary by rule (q2.ב.c5) and the A-5 unwritten-ruling cell
Refuses unless the counts are exactly the ruled 11 / 21 / 6 / 6 = 44. Writes
`docs/plans/v6_run11_k2_frozen.json` (the per-class report of run 11 reads it).
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from decimal import Decimal
from pathlib import Path

from tests.grading_eval_suite.tools.v6_residual import cells

BACKEND = Path(__file__).resolve().parents[3]
OUT = BACKEND.parent / "docs" / "plans" / "v6_run11_k2_frozen.json"

# (exam, terminal_id, GT award or None for "any") → class; the most specific match wins
RULES = [
    (("bagrut_899371", "q3.ב.c6", Decimal("2.5")), "split"),
    (("bagrut_899371", "q3.ב.c5", None), "split"),
    (("bagrut_899371", "q3.ב.c6", Decimal("2")), "verifier-miss"),
    (("bagrut_899371", "q6.c6", None), "verifier-miss"),
    (("bagrut_899371", "q6.c7", None), "verifier-miss"),
    (("bagrut_899371", "q6.c1", None), "verifier-miss"),
    (("hobby_tvshow", "q2.ב.c3.s0", None), "verifier-miss"),
    (("hobby_tvshow", "q2.ג.c0.s1", None), "verifier-miss"),
    (("hobby_tvshow", "q1.ב.c2", None), "verifier-miss"),
    (("bagrut_899371", "q3.א.c2", None), "plan-wording"),
    (("hobby_tvshow", "q2.ב.c4.s1", None), "plan-wording"),
    (("hobby_tvshow", "q2.ב.c5", None), "other"),
    (("hobby_tvshow", "q2.ב.c4.s2", None), "other"),
]
RULED = {"split": 11, "verifier-miss": 21, "plan-wording": 6, "other": 6}


def classify(c: dict) -> str:
    exam = "bagrut_899371" if c["exam"].startswith("bagrut") else "hobby_tvshow"
    for (e, tid, gt), cls in RULES:
        if e == exam and tid == c["terminal_id"] and (gt is None or Decimal(str(c["gt"])) == gt):
            return cls
    raise SystemExit(f"UNCLASSIFIED K2 cell: {c}")


def main() -> None:
    run_dir = Path(sys.argv[1])
    k2 = [c for c in cells(run_dir) if c["kind"] == "K2"]
    rows = []
    for c in k2:
        rows.append({"fixture": c["fixture"], "exam": c["exam"], "trial": c.get("trial"),
                     "terminal_id": c["terminal_id"], "gt": str(c["gt"]), "ai": str(c["ai"]),
                     "possible": str(c["possible"]), "class": classify(c)})
    got = Counter(r["class"] for r in rows)
    if dict(got) != RULED or len(rows) != 44:
        raise SystemExit(f"STOP: run 10's K2 cells classify as {dict(got)} ({len(rows)} cells), "
                         f"not the ruled {RULED} (44)")
    OUT.write_text(json.dumps({"_about": __doc__.strip().splitlines()[0], "run10": run_dir.name,
                               "counts": RULED, "cells": rows}, ensure_ascii=False, indent=1) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"froze {len(rows)} K2 cells {dict(got)} → {OUT}")


if __name__ == "__main__":
    main()
