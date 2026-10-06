"""
rescore.py — re-score a finished run's SAVED outputs against the ground truth as
it stands NOW. Read-only over the model's outputs; no API calls.

Why it exists: the ground truth is the owner's and moves while runs are in flight
(2026-09-27: the bagrut tick spelling changed from `v` to `✓` mid-screen). A run
scores each document when that document finishes, so arms of one comparison could
be judged by different rulers. Rescoring every arm from its outputs puts them
back on one ruler. Cost, latency, tokens and validity are copied from the
original record untouched — only accuracy and diagnostics are recomputed.

Usage (from backend/):
    python -m tests.transcription_eval_suit.rescore <results_dir> [...]
writes <results_dir>/results_rescored.json (same shape as results.json);
`mission_report --rescored` reads it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from . import diagnostics as diag
from .exam_resolution import resolve_exam
from .ground_truth import load_ground_truth, load_page_ground_truth
from .runner import SCORING_POLICY, SUITE_DIR, Fixture, _ser_e2e, _ser_p1
from .scoring import score_document, score_page_document


def _key(s: str) -> tuple[int, str | None]:
    """Inverse of runner._write_outputs' "Q1.א" spelling."""
    q, _, sub = s[1:].partition(".")
    return int(q), (sub or None)


def rescore_dir(d: Path) -> Path:
    res = json.loads((d / "results.json").read_text(encoding="utf-8"))
    out_records = []
    for rec in res["records"]:
        doc, rep = rec["doc_id"], rec["repeat"]
        src = d / "outputs" / f"{doc}__rep{rep}.json"
        if not src.exists():
            out_records.append(dict(rec, rescored=False))
            continue
        o = json.loads(src.read_text(encoding="utf-8"))
        raw = load_page_ground_truth(SUITE_DIR / "raw_benchmarks" / f"{doc}.md")
        draft_p = SUITE_DIR / "draft_benchmarks" / f"{doc}.md"
        draft = load_ground_truth(draft_p) if draft_p.exists() else None
        # the runner's own profile resolution (default profile when no exam)
        profile = Fixture(doc_id=doc, pdf_path=None, raw_gold=raw, draft_gold=draft,
                          exam=resolve_exam(doc, fallback_spec_path=None)).profile
        pages = {int(k): v for k, v in o.get("pages", {}).items()}
        answers = {_key(k): v for k, v in o.get("answers", {}).items()}
        new = dict(rec, rescored=True)
        if rec.get("p1") is not None:
            new["p1"] = _ser_p1(score_page_document(pages, raw, profile=profile,
                                                    policy=SCORING_POLICY))
        if rec.get("e2e") is not None and draft is not None:
            new["e2e"] = _ser_e2e(score_document(answers, draft, profile=profile,
                                                 policy=SCORING_POLICY))
        new["diag"] = diag.compute(
            doc, raw_gold=raw, draft_gold=draft,
            pages=pages if rec.get("p1") is not None else None,
            answers=answers if rec.get("e2e") is not None else None,
            relocations=(), pages_before_relocation=None,
        )
        # The ARROW metric needs the run's own relocation records, which outputs do
        # not carry — so it is NOT recomputed: the run-time block is kept verbatim
        # (valid as long as insertion_cases.json did not change during the run).
        if (rec.get("diag") or {}).get("arrows") is not None:
            new["diag"]["arrows"] = rec["diag"]["arrows"]
        out_records.append(new)
    res["records"] = out_records
    dst = d / "results_rescored.json"
    dst.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return dst


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    for a in sys.argv[1:]:
        p = rescore_dir(Path(a))
        n = sum(1 for r in json.loads(p.read_text(encoding="utf-8"))["records"] if r.get("rescored"))
        print(f"{p}: {n} records rescored")
