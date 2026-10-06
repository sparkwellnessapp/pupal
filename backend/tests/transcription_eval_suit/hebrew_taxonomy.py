"""
hebrew_taxonomy.py — pre-classify every Hebrew difference between P1 output and
raw GT (MISSION §4.6). Read-only over run artifacts; a reading aid, not a metric.

The mechanical classes are assigned here; the two that need judgment are left for
a human read of the diff, and the output says so rather than guessing them:
  (a) letter confusion   — a word replaced by one within edit distance 2
  (b) dropped/added word — an insertion or deletion in the word alignment
  (c) ORDER              — a replaced block holding the same words (or letters),
                           reordered: the classic VLM bidi failure
  (d) normalization      — the model "fixed" the student   } judged from the
  (e) suspected GT error — the GT, not the model, is wrong } printed context

Usage: python -m tests.transcription_eval_suit.hebrew_taxonomy <results_dir> [...]
"""
from __future__ import annotations

import difflib
import json
import sys
from collections import Counter
from pathlib import Path

from .diag_hebrew import hebrew_words, is_hebrew, strip_marker_lines
from .ground_truth import load_page_ground_truth

SUITE = Path(__file__).parent


def _lev(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def classify(gold_words: list[str], pred_words: list[str]) -> list[dict]:
    out = []
    sm = difflib.SequenceMatcher(None, gold_words, pred_words, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        g, p = gold_words[i1:i2], pred_words[j1:j2]
        if tag == "equal":
            continue
        if tag in ("delete", "insert"):
            out.append({"class": "b", "gold": g, "pred": p})
            continue
        if Counter(g) == Counter(p) or Counter("".join(g)) == Counter("".join(p)):
            out.append({"class": "c", "gold": g, "pred": p})
            continue
        if len(g) == len(p):
            for gw, pw in zip(g, p):
                if gw == pw:
                    continue
                cls = "a" if _lev(gw, pw) <= 2 else "b"
                out.append({"class": cls, "gold": [gw], "pred": [pw]})
            continue
        out.append({"class": "b", "gold": g, "pred": p})
    return out


def reversed_lines(gold_text: str, pred_text: str, min_run: int = 4) -> list[str]:
    """Class (c) at LINE level: a predicted Hebrew line whose words, REVERSED, share
    a run of >= `min_run` consecutive words with the gold, at least twice the run
    the forward order shares. The word-level alignment in `classify` cannot see
    this — a reversed sentence shreds into several replace/insert hunks (noam p7
    did exactly that, with one misread word inside it, so an exact match misses)."""
    g = hebrew_words(gold_text)

    def run(w: list[str]) -> int:
        sm = difflib.SequenceMatcher(None, g, w, autojunk=False)
        return sm.find_longest_match(0, len(g), 0, len(w)).size

    out = []
    for line in pred_text.splitlines():
        w = hebrew_words(line)
        if len(w) < min_run:
            continue
        r = run(list(reversed(w)))
        if r >= min_run and r >= 2 * run(w):
            out.append(line.strip())
    return out


def main(dirs: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    totals: Counter = Counter()
    for d in dirs:
        data = json.loads((Path(d) / "results.json").read_text(encoding="utf-8"))
        seen = set()
        for rec in data["records"]:
            doc = rec["doc_id"]
            if doc in seen:
                continue                      # first repeat only; the read is per error
            seen.add(doc)
            src = Path(d) / "outputs" / f"{doc}__rep0.json"   # runner._write_outputs
            if not src.exists():
                continue
            outputs = json.loads(src.read_text(encoding="utf-8"))
            gold = load_page_ground_truth(SUITE / "raw_benchmarks" / f"{doc}.md").as_dict()
            for n, gtext in gold.items():
                ptext = outputs["pages"].get(str(n), "")
                # the prose view: section-marker lines are not Hebrew text
                errs = classify(hebrew_words(strip_marker_lines(gtext)),
                                hebrew_words(strip_marker_lines(ptext)))
                for ln in reversed_lines(strip_marker_lines(gtext), strip_marker_lines(ptext)):
                    totals["c_line"] += 1
                    print(f"{doc} p{n} (c, whole line reversed): pred={ln!r}")
                for e in errs:
                    totals[e["class"]] += 1
                    print(f"{doc} p{n} ({e['class']}): gold={' '.join(e['gold'])!r} "
                          f"pred={' '.join(e['pred'])!r}")
    print("\nTOTALS (mechanical classes only; (d)/(e) need the diff read):", dict(totals))


if __name__ == "__main__":
    main(sys.argv[1:])
