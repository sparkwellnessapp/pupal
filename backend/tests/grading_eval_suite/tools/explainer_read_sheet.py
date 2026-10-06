"""
The owner's explainer read (PR_grader_v6_options.md §13.4; Oct 6 rulings §3.7d).

    python -m tests.grading_eval_suite.tools.explainer_read_sheet <v6_run_dir> <arm_b.json> \\
        [--seed 6] [--out docs/plans/v6_explainer_read_sheet.md]

40 CS credit terminals, stratified 10 full / 10 partial / 10 zero / 10 with a deduction
(a fault check priced there, applied or not), drawn with a fixed seed from trial r0 of
every fixture. Each terminal appears ONCE PER ARM — 80 items, shuffled, BLIND: the sheet
shows the criterion (her text), the grade, the quotes and the line, and three yes/no
questions (faithful · clear · concise). The arm of every item is written to a SEPARATE
key file (`<out>.key.json`), never on the sheet.

An arm ships iff faithful 40/40, clear ≥ 36, concise ≥ 36; among qualifying arms the
cheapest wins; if none qualifies, the fallback composer ships.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List

BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BACKEND))

from app.schemas.graded_test_draft import GradedTestDraft                      # noqa: E402
from app.schemas.graded_test_draft_v6 import v6_content                        # noqa: E402
from app.services.pricing_v6 import price                                      # noqa: E402
from tests.grading_eval_suite.fixtures import load_bundle                      # noqa: E402

STRATA = ("full", "partial", "zero", "deduction")
PER_STRATUM = 10


def line_key(fixture: str, trial: int, terminal_id: str) -> str:
    return f"{fixture}|r{trial}|{terminal_id}"


def _candidates(run_dir: Path) -> List[dict]:
    out = []
    for p in sorted((run_dir / "drafts").glob("*_r0.json")):
        fixture = p.stem.rsplit("_r", 1)[0]
        draft = GradedTestDraft.model_validate_json(p.read_text(encoding="utf-8"))
        content = v6_content(draft)
        if content is None:
            continue
        bundle = load_bundle(fixture, require_gt=False)
        texts = {}                               # her criterion text, per terminal
        for sc in bundle.gradable_test.scopes:
            for cr in sc.criteria:
                for leaf in (cr.sub_criteria or [cr]):
                    texts[getattr(leaf, "sub_criterion_id", None) or leaf.criterion_id] = leaf.description
        priced = price(content.to_view())
        lines = {e.terminal_id: e for e in content.explanations}
        graded = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by == "llm"}
        scope_of = {t.terminal_id: (t.question_id, t.sub_question_id) for t in content.view_terminals}
        possible = {t.terminal_id: t.points_possible for t in content.view_terminals}
        by_t: Dict[str, list] = {}
        for c in content.checks:
            by_t.setdefault(c.plan.priced_terminal_id, []).append(c)
        for t in priced.terminals:
            e = lines.get(t.terminal_id)
            if e is None or scope_of[t.terminal_id] not in graded:
                continue
            checks = by_t.get(t.terminal_id, [])
            if any(c.plan.role == "fault" for c in checks):
                stratum = "deduction"
            elif t.awarded == possible[t.terminal_id]:
                stratum = "full"
            elif t.awarded == 0:
                stratum = "zero"
            else:
                stratum = "partial"
            quotes = [c.evidence_quote for c in checks if c.evidence_quote]
            pointers = [c.absence_pointer_he for c in checks if c.absence_pointer_he]
            out.append({"key": line_key(fixture, 0, t.terminal_id), "stratum": stratum,
                        "criterion": texts.get(t.terminal_id, t.terminal_id),
                        "grade": f"{t.awarded} / {possible[t.terminal_id]}",
                        "quotes": quotes, "pointers": pointers, "arm_a": e.text_he,
                        "arm_a_source": e.source})
    return out


def build(run_dir: Path, arm_b: dict, seed: int) -> (str, dict):
    rng = random.Random(seed)
    cands = _candidates(run_dir)
    picked: List[dict] = []
    for s in STRATA:
        pool = [c for c in cands if c["stratum"] == s]
        rng.shuffle(pool)
        picked += pool[:PER_STRATUM]
    items = []
    for c in picked:
        items.append({**c, "arm": "A", "line": c["arm_a"]})
        b = (arm_b.get("lines") or {}).get(c["key"])
        if b is not None:
            items.append({**c, "arm": "B", "line": b["text_he"]})
    rng.shuffle(items)
    L = ["# Explainer read sheet (§13.4) — blind", "",
         f"{len(items)} lines ({len(picked)} terminals × 2 arms), shuffled. For each line answer "
         "three yes/no questions:",
         "- **Faithful** — says nothing the grade and the quotes don't support.",
         "- **Clear** — understood on the first read.",
         "- **Concise** — nothing extraneous.", ""]
    key = {}
    for i, it in enumerate(items, start=1):
        key[str(i)] = {"arm": it["arm"], "terminal": it["key"], "stratum": it["stratum"]}
        L += [f"### {i}", "", f"**הקריטריון:** {it['criterion']}", "",
              f"**ציון:** {it['grade']}", ""]
        if it["quotes"]:
            L += ["**ציטוטים:** " + " · ".join(f"«{q}»" for q in it["quotes"]), ""]
        if it["pointers"]:
            L += ["**מה אין:** " + " · ".join(it["pointers"]), ""]
        L += [f"> {it['line']}", "", "faithful ☐ yes ☐ no · clear ☐ yes ☐ no · concise ☐ yes ☐ no", ""]
    counts = {s: sum(1 for c in picked if c["stratum"] == s) for s in STRATA}
    L += ["---", f"Strata drawn (seed {seed}): {counts}. The arm key is in a separate file."]
    return "\n".join(L) + "\n", key


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("arm_b")
    ap.add_argument("--seed", type=int, default=6)
    ap.add_argument("--out", default=str(BACKEND.parent / "docs" / "plans" / "v6_explainer_read_sheet.md"))
    a = ap.parse_args()
    arm_b = json.loads(Path(a.arm_b).read_text(encoding="utf-8"))
    text, key = build(Path(a.run_dir), arm_b, a.seed)
    out = Path(a.out)
    out.write_text(text, encoding="utf-8")
    out.with_suffix(".key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {out} ({len(key)} items) and its key")


if __name__ == "__main__":
    main()
