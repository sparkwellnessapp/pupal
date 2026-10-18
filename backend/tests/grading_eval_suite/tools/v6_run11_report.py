"""
grader-v6 Item C (owner rulings 2026-10-18 §3e) — run 11 against run 10, PER FROZEN CLASS, plus
every NEW failing cell. $0, no model.

    python -m tests.grading_eval_suite.tools.v6_run11_report <run10_dir> <run11_dir> [--out FILE]

  * Per class of `docs/plans/v6_run11_k2_frozen.json` (split · verifier-miss · plan-wording ·
    other): the run-10 K2 cells, and for each (fixture, criterion) whether run 11 still fails it
    as K2 in ANY trial (still failing) or in none (fixed). Matched on (fixture, criterion), not
    on the trial index: run 10 had k=3, run 11 has k=2.
  * NEW failing cells: every run-11 K1 (GT zero, AI not zero), K2 (GT partial → AI full) or G-Z
    (GT partial → AI zero) cell whose (fixture, criterion) did NOT fail the same way in run 10 —
    with the checks behind it (the option the verifier chose and its quote).
Contested cells are excluded exactly as the gates exclude them (`gates._included_rows`).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.schemas.graded_test_draft import GradedTestDraft                      # noqa: E402
from app.schemas.graded_test_draft_v6 import v6_content                        # noqa: E402
from tests.grading_eval_suite.tools.gates import _cls, _included_rows          # noqa: E402
from tests.grading_eval_suite.tools.v6_residual import _load                   # noqa: E402

FROZEN = BACKEND.parent / "docs" / "plans" / "v6_run11_k2_frozen.json"
CLASSES = ("split", "verifier-miss", "plan-wording", "other")


def failing(run_dir: Path) -> Dict[Tuple[str, str], Dict[str, List[dict]]]:
    """(fixture, terminal) → kind → the failing trial rows. Kinds: K1 · K2 · GZ."""
    res, points, contested, _exam = _load(run_dir)
    out: Dict[Tuple[str, str], Dict[str, List[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in _included_rows(res["trials"], contested):
        possible = points[(r["fixture"], r["terminal_id"])]
        gt, ai = Decimal(r["gt_awarded"]), Decimal(r["ai_awarded"])
        gc, ac = _cls(gt, possible), _cls(ai, possible)
        kind = ("K1" if gc == "ZERO" and ac != "ZERO" else
                "K2" if (gc, ac) == ("PARTIAL", "FULL") else
                "GZ" if (gc, ac) == ("PARTIAL", "ZERO") else None)
        if kind:
            out[(r["fixture"], r["terminal_id"])][kind].append(
                {"trial": r.get("trial_index"), "gt": gt, "ai": ai, "possible": possible})
    return out


def _checks(run_dir: Path, fixture: str, trial, terminal: str) -> List[str]:
    p = run_dir / "drafts" / f"{fixture}_r{trial}.json"
    if not p.exists():
        return ["(draft not found)"]
    content = v6_content(GradedTestDraft.model_validate_json(p.read_text(encoding="utf-8")))
    lines = []
    for rec in content.checks:
        if rec.plan.priced_terminal_id != terminal:
            continue
        opt = rec.plan.option(rec.model_option_id) if rec.model_option_id else None
        label = opt.label_he if opt else "(no verdict)"
        quote = rec.evidence_quote or rec.absence_pointer_he or ""
        lines.append(f"{rec.plan.role} · {rec.plan.description_he[:70]} → **{label[:110]}**"
                     + (f" · «{quote[:140]}»" if quote else ""))
    return lines


def render(run10: Path, run11: Path) -> str:
    frozen = json.loads(FROZEN.read_text(encoding="utf-8"))["cells"]
    f10, f11 = failing(run10), failing(run11)
    L = [f"### Run 11 against run 10's frozen K2 classes (run 10 `{run10.name}` · run 11 `{run11.name}`)", "",
         "| class | run-10 cells | criteria (fixture · terminal) | fixed | still failing (K2 in any run-11 trial) |",
         "|---|---|---|---|---|"]
    detail = []
    for cls in CLASSES:
        cells = [c for c in frozen if c["class"] == cls]
        units = sorted({(c["fixture"], c["terminal_id"]) for c in cells})
        still = [u for u in units if f11.get(u, {}).get("K2")]
        L.append(f"| {cls} | {len(cells)} | {len(units)} | {len(units) - len(still)} | {len(still)} |")
        for u in units:
            n10 = sum(1 for c in cells if (c["fixture"], c["terminal_id"]) == u)
            n11 = len(f11.get(u, {}).get("K2", []))
            detail.append(f"| {cls} | {u[0]} · `{u[1]}` | {n10} | {n11} | {'still failing' if n11 else 'fixed'} |")
    L += ["", "| class | fixture · terminal | run-10 K2 trials | run-11 K2 trials | |", "|---|---|---|---|---|"] + detail
    new = []
    for u, kinds in sorted(f11.items()):
        for kind, rows in kinds.items():
            if f10.get(u, {}).get(kind):
                continue
            for r in rows:
                new.append((kind, u, r))
    L += ["", f"### NEW failing cells in run 11 (not failing the same way in run 10): {len(new)}", ""]
    for kind, (fx, tid), r in sorted(new, key=lambda x: (x[0], x[1], x[2]["trial"] or 0)):
        L.append(f"- **{kind}** · {fx} r{r['trial']} · `{tid}` · GT {r['gt']} / AI {r['ai']} of {r['possible']}")
        L += [f"  - {line}" for line in _checks(run11, fx, r["trial"], tid)]
    return "\n".join(L) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run10")
    ap.add_argument("run11")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    text = render(Path(a.run10), Path(a.run11))
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
