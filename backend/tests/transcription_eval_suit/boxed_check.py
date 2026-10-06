"""
boxed_check.py — the owner's condition for the boxed-answer rule (2026-09-30): the
rule may add `[..]` around a framed final answer, and must change NO OTHER NUMBER.
Read-only over run artifacts; no API calls.

Per page, the sequence of numbers the model wrote (brackets stripped) is aligned to
the answer key's; every substitution / drop / insertion is a NUMBER ERROR. Brackets
are counted separately: expected (the key's `[n]`), produced, correct, spurious.

Usage: python -m tests.transcription_eval_suit.boxed_check <results_dir> [...]
"""
from __future__ import annotations

import difflib
import json
import re
import sys
from collections import Counter
from pathlib import Path

from .ground_truth import load_page_ground_truth

SUITE = Path(__file__).parent
NUM = re.compile(r"(?<![\w.])\d+(?![\w])")
BOXED = re.compile(r"(?<![\w\])])(?<!\w )(?<!\] )(?<!\) )\[(\d+)\]")   # not an index / size: `arr[0]`, `new int [31]`


def numbers(text: str) -> list[str]:
    return NUM.findall(BOXED.sub(r"\1", text))


def check_page(gold: str, pred: str) -> dict:
    g, p = numbers(gold), numbers(pred)
    sm = difflib.SequenceMatcher(None, g, p, autojunk=False)
    errs = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag != "equal":
            errs.append((tag, g[i1:i2], p[j1:j2]))
    gb, pb = BOXED.findall(gold), BOXED.findall(pred)
    correct = sum((Counter(gb) & Counter(pb)).values())
    return {"num_errors": sum(max(len(a), len(b)) for _, a, b in errs), "detail": errs,
            "boxed_expected": len(gb), "boxed_produced": len(pb), "boxed_correct": correct,
            "boxed_spurious": len(pb) - correct}


def _errors(d: Path) -> dict[str, set]:
    """doc -> every (page, error) seen in any repeat of this run."""
    out: dict[str, set] = {}
    for f in sorted((d / "outputs").glob("*.json")):
        doc = f.name.split("__")[0]
        gold = load_page_ground_truth(SUITE / "raw_benchmarks" / f"{doc}.md").as_dict()
        pages = json.loads(f.read_text(encoding="utf-8"))["pages"]
        for n, gt in gold.items():
            for t, a, b in check_page(gt, pages.get(str(n), ""))["detail"]:
                out.setdefault(doc, set()).add((n, t, tuple(a), tuple(b)))
    return out


def main(dirs: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    control = None
    if dirs and dirs[0].startswith("--control="):
        control = _errors(Path(dirs[0].split("=", 1)[1]))
        dirs = dirs[1:]
    for d in dirs:
        if control is not None:
            mine = _errors(Path(d))
            new = {doc: sorted(e - control.get(doc, set())) for doc, e in mine.items()}
            n_new = sum(len(v) for v in new.values())
            print(f"\n== {d}\n  NUMBER ERRORS NOT SEEN IN ANY CONTROL RUN: {n_new}")
            for doc, v in new.items():
                for e in v:
                    print(f"     {doc}  p{e[0]} {e[1]} {list(e[2])} -> {list(e[3])}")
        tot = Counter()
        print(f"\n== {d}")
        for f in sorted((Path(d) / "outputs").glob("*.json")):
            doc = f.name.split("__")[0]
            gold = load_page_ground_truth(SUITE / "raw_benchmarks" / f"{doc}.md").as_dict()
            pages = json.loads(f.read_text(encoding="utf-8"))["pages"]
            row = Counter()
            details = []
            for n, gt in gold.items():
                r = check_page(gt, pages.get(str(n), ""))
                for k in ("num_errors", "boxed_expected", "boxed_produced", "boxed_correct", "boxed_spurious"):
                    row[k] += r[k]
                details += [f"p{n} {t} {a}->{b}" for t, a, b in r["detail"]]
            tot.update(row)
            print(f"  {f.name[:-5]:40s} number errors {row['num_errors']:3d} | brackets "
                  f"{row['boxed_correct']}/{row['boxed_expected']} correct, {row['boxed_spurious']} spurious"
                  f"   {'; '.join(details)[:150]}")
        print(f"  TOTAL number errors {tot['num_errors']} | brackets {tot['boxed_correct']}/"
              f"{tot['boxed_expected']} correct, {tot['boxed_spurious']} spurious")


if __name__ == "__main__":
    main(sys.argv[1:])
