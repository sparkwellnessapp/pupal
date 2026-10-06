"""
code_taxonomy.py — where the GATE's critical-token misses come from (recommendation #4,
2026-09-28). Read-only over run artifacts; a reading aid, not a metric.

The gate fails a document on ONE missing operator / structural token / method call /
abbreviation. This names every miss, how often it recurs across repeats, and which
stage lost it:
  * P1  — the token is already short in the P1 page text (perception): the extracted
          count over the doc's pages is below the raw GT's;
  * P2  — P1 had it, the answers do not (segmentation dropped or mis-routed it).
Counts come from the suite's own extractor (`critical_tokens.extract_signature`) with the
fixture's own profile — the ruler, used as-is.

Usage (from backend/): python -m tests.transcription_eval_suit.code_taxonomy <results_dir>
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .critical_tokens import extract_signature
from .exam_resolution import resolve_exam
from .ground_truth import load_page_ground_truth
from .runner import SUITE_DIR, Fixture


def _sig_counts(text: str, profile) -> Counter:
    s = extract_signature(text, profile)
    c = Counter()
    for k, v in s.operators.items():
        c[("operator", k)] += v
    for k, v in s.structural.items():
        c[("structural", k)] += v
    for k in s.method_calls:
        c[("method_call", k)] += 1
    for k, v in s.abbreviations.items():
        c[("abbreviation", k)] += v
    return c


KIND = {"operators": "operator", "structural": "structural",
        "method_calls": "method_call", "abbreviations": "abbreviation"}


def main(d: str) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    res = json.loads((Path(d) / "results.json").read_text(encoding="utf-8"))
    by_doc: dict[str, Counter] = defaultdict(Counter)
    stage: dict[tuple, Counter] = defaultdict(Counter)
    reps: dict[str, int] = Counter()
    for rec in res["records"]:
        doc, rep = rec["doc_id"], rec["repeat"]
        reps[doc] += 1
        out = Path(d) / "outputs" / f"{doc}__rep{rep}.json"
        if not out.exists() or not rec.get("e2e"):
            continue
        profile = Fixture(doc_id=doc, pdf_path=None, raw_gold=None, draft_gold=None,
                          exam=resolve_exam(doc, fallback_spec_path=None)).profile
        o = json.loads(out.read_text(encoding="utf-8"))
        raw = load_page_ground_truth(SUITE_DIR / "raw_benchmarks" / f"{doc}.md").as_dict()
        gold_c = _sig_counts("\n".join(raw.values()), profile)
        p1_c = _sig_counts("\n".join(o["pages"].values()), profile)
        for a in rec["e2e"]["answers"]:
            for kind, toks in a["missed"].items():
                for t in toks:
                    key = (KIND[kind], t)
                    by_doc[doc][key] += 1
                    where = "P1" if p1_c[key] < gold_c[key] else "P2"
                    stage[(doc, key)][where] += 1
    total = Counter()
    for doc in sorted(by_doc):
        print(f"\n## {doc}  (repeats: {reps[doc]})")
        for (kind, tok), n in by_doc[doc].most_common():
            st = stage[(doc, (kind, tok))]
            total[(kind, st.most_common(1)[0][0])] += n
            print(f"  {kind:12s} {tok!r:24s} missed {n}x   stage {dict(st)}")
    print("\n## TOTAL misses by (kind, stage):")
    for (kind, st), n in sorted(total.items(), key=lambda x: -x[1]):
        print(f"  {kind:12s} {st}: {n}")


if __name__ == "__main__":
    main(sys.argv[1])
