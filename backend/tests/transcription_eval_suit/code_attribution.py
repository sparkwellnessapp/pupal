"""
code_attribution.py — every gate-critical symbol miss, attributed to the stage that
lost it (code-symbol mission, 2026-09-30). Read-only over run artifacts; no API calls.

The gate fails a document on one missing operator / structural token / method call /
abbreviation. For each (record, answer, symbol) miss this decides WHO lost it:

  * P1 (reading) — the P1 text P2 received has FEWER copies of the symbol, in the
    region that holds this answer, than the gold answer does. (This bucket includes
    the strike check: crossed-out ink it failed to remove, or live ink it removed.)
  * P2 (splitting) — that region HAS the symbol; the answer P2 produced does not.
      - misrouted: the symbol sits in ANOTHER answer of the same document in excess
        of that answer's gold count;
      - dropped:   it sits in no answer.

HOW THE REGION IS FOUND. P2 answers by referencing LINES of P1's text (the spans
contract), so an answer is those lines verbatim. The gold answer is aligned to the
P1 text P2 received (`pages_after_relocation` when arrows moved text, else `pages`)
on whitespace-stripped characters; matched blocks >= MIN_BLOCK characters are mapped
back to P1 line numbers and the region is first..last matched line. The same lines
power the second output: the P1 lines in each answer's region that P2 left OUT of
that answer — the concrete target for any P2 fix.

Symbols come from the suite's own extractor and profile (the ruler, used as-is).
Usage (from backend/): python -m tests.transcription_eval_suit.code_attribution <results_dir> [...]
"""
from __future__ import annotations

import difflib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from .critical_tokens import extract_signature
from .exam_resolution import resolve_exam
from .ground_truth import load_ground_truth
from .keys import normalize_key
from .runner import SCORING_POLICY, SUITE_DIR, Fixture

MIN_BLOCK = 12


def symbols(text: str, profile) -> Counter:
    # the scorer's own folds (scoring._score_answer_critical), so a miss here is
    # exactly a miss the gate counts
    s = extract_signature(text, profile,
                          fold_keyword_case=SCORING_POLICY.case_insensitive_keywords,
                          fold_identifier_case=SCORING_POLICY.case_insensitive_method_calls)
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


def _stripped(text: str) -> tuple[str, list[int]]:
    chars, line_of = [], []
    for li, line in enumerate(text.split("\n")):
        for ch in line:
            if not ch.isspace():
                chars.append(ch)
                line_of.append(li)
    return "".join(chars), line_of


def region(gold: str, p1_text: str, p1_stripped=None) -> tuple[int, int] | None:
    """(first, last) P1 line index holding the gold answer's content, or None."""
    gs, _ = _stripped(gold)
    ts, line_of = p1_stripped or _stripped(p1_text)
    if not gs or not ts:
        return None
    sm = difflib.SequenceMatcher(None, gs, ts, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size >= MIN_BLOCK]
    if not blocks:
        return None
    return line_of[blocks[0].b], line_of[blocks[-1].b + blocks[-1].size - 1]


def _key(s: str):
    q, _, sub = s[1:].partition(".")
    return normalize_key((int(q), sub or None))


def _best_line(gline: str, cand: list[tuple[int, str]]) -> tuple[int, ...] | None:
    """The P1 line — or PAIR of consecutive lines, since P1 may wrap one written
    line in two (noam's Q1.א sentence) — that best matches a gold line
    (whitespace-blind), if any clears MIN_LINE_RATIO."""
    g = "".join(gline.split())
    best, best_r = None, MIN_LINE_RATIO
    for n, (j, t) in enumerate(cand):
        options = [((j,), t)]
        if n + 1 < len(cand) and cand[n + 1][0] == j + 1:
            options.append(((j, j + 1), t + cand[n + 1][1]))
        for idx, text in options:
            r = difflib.SequenceMatcher(None, g, text, autojunk=False).ratio()
            if r > best_r:
                best, best_r = idx, r
    return best


MIN_LINE_RATIO = 0.6
WINDOW = 12            # search the aligned region +- this many P1 lines


def attribute_record(doc: str, outputs: dict) -> dict:
    """LINE-LEVEL attribution (the first, region-count version over-credited P2:
    a region that over-spans into a neighbouring method borrows its symbols —
    dan Q3.ב's `DiceStatistics[arr]` → `(arr)` is a READING error it called P2).
    P2 answers are P1 lines verbatim (spans contract), so a miss is P2 ONLY when
    the P1 line matching the gold line HAS the symbol and is absent from the
    answer; every other shortfall is P1. Conservative toward P2 by design."""
    profile = Fixture(doc_id=doc, pdf_path=None, raw_gold=None, draft_gold=None,
                      exam=resolve_exam(doc, fallback_spec_path=None)).profile
    pages = outputs.get("pages_after_relocation") or outputs["pages"]
    p1_text = "\n".join(pages[k] for k in sorted(pages, key=int))
    p1_lines = p1_text.split("\n")
    p1_str = _stripped(p1_text)
    p1_norm = ["".join(x.split()) for x in p1_lines]
    gold = {normalize_key(a.key): a.answer_text for a in load_ground_truth(
        SUITE_DIR / "draft_benchmarks" / f"{doc}.md").answers}
    pred = {_key(k): v for k, v in outputs.get("answers", {}).items()}
    pred_lines = {k: {ln.strip() for ln in v.split("\n") if ln.strip()} for k, v in pred.items()}
    g_sym = {k: symbols(v, profile) for k, v in gold.items()}
    a_sym = {k: symbols(pred.get(k, ""), profile) for k in gold}
    gold_norm = {k: ["".join(x.split()) for x in v.split(chr(10)) if x.strip()] for k, v in gold.items()}
    out = {"misses": [], "omitted_lines": {}}
    for k, g in gold.items():
        missing = {sym: need - a_sym[k][sym] for sym, need in g_sym[k].items()
                   if a_sym[k][sym] < need}
        if not missing:
            continue
        reg = region(g, p1_text, p1_str)
        lo, hi = ((max(0, reg[0] - WINDOW), min(len(p1_lines), reg[1] + WINDOW + 1))
                  if reg else (0, len(p1_lines)))
        cand = [(j, p1_norm[j]) for j in range(lo, hi) if p1_norm[j]]
        p2_short = Counter()
        where = defaultdict(set)
        for gl in g.split("\n"):
            if not gl.strip():
                continue
            gs = symbols(gl, profile)
            if not any(sym in missing for sym in gs):
                continue
            idx = _best_line(gl, cand)
            if idx is None:
                continue
            p1ls = [p1_lines[j].strip() for j in idx]
            if any(x in pred_lines.get(k, set()) for x in p1ls):
                continue                      # P2 kept the line: any shortfall is P1's
            p1l = " ".join(p1ls)
            # A line that sits in ANOTHER answer whose own gold holds the same line is
            # that answer's line, not a misroute — P1 simply read one copy fewer
            # (omer: `if(hobbies[i] != null)` is in both Q1.ב and Q1.ג; P1 read one).
            owner = [k2 for k2, ls in pred_lines.items() if k2 != k and any(x in ls for x in p1ls)]
            if owner and owner[0] in gold_norm and any(
                    difflib.SequenceMatcher(None, "".join(p1l.split()), gl2).ratio() >= 0.9
                    for gl2 in gold_norm[owner[0]]):
                continue
            ps = symbols(p1l, profile)
            for sym in gs:
                if sym in missing:
                    has = min(gs[sym], ps[sym])   # P1 read these; P2 left the line out
                    if has:
                        p2_short[sym] += has
                        others = [k2 for k2, ls in pred_lines.items()
                                  if k2 != k and any(x in ls for x in p1ls)]
                        where[sym].add(f"misrouted→{others[0]}" if others else "dropped")
            out["omitted_lines"].setdefault(k, []).append(p1l)
        for sym, miss_n in missing.items():
            n_p2 = min(miss_n, p2_short[sym])
            n_p1 = miss_n - n_p2
            if n_p1:
                out["misses"].append({"key": k, "sym": sym, "n": n_p1, "stage": "P1"})
            if n_p2:
                out["misses"].append({"key": k, "sym": sym, "n": n_p2, "stage": "P2",
                                      "how": sorted(where[sym])[0]})
    return out


def main(dirs: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    per_doc = defaultdict(Counter)
    p2_sites = defaultdict(Counter)
    n_rec = Counter()
    mismatch = []
    for d in dirs:
        # the rescored file when present: it was scored on the CURRENT answer key,
        # which is what this attribution reads (rescore.py)
        f_res = Path(d) / "results_rescored.json"
        f_res = f_res if f_res.exists() else Path(d) / "results.json"
        res = json.loads(f_res.read_text(encoding="utf-8"))
        for rec in res["records"]:
            doc, rep = rec["doc_id"], rec["repeat"]
            f = Path(d) / "outputs" / f"{doc}__rep{rep}.json"
            if not f.exists() or not rec.get("e2e"):
                continue
            n_rec[doc] += 1
            a = attribute_record(doc, json.loads(f.read_text(encoding="utf-8")))
            mine = sum(m["n"] for m in a["misses"] if m["sym"][0] != "abbreviation")
            theirs = sum(len(x["missed"].get(k, [])) for x in rec["e2e"]["answers"]
                         for k in ("operators", "structural", "method_calls"))
            if mine != theirs:
                mismatch.append((doc, rep, mine, theirs))
            for m in a["misses"]:
                per_doc[doc][m["stage"]] += m["n"]
                if m["stage"] == "P2":
                    p2_sites[doc][(m["key"], m["sym"], m["how"])] += m["n"]
    tot = Counter()
    print(f"{'document':34s} {'records':>7s} {'P1 (reading)':>13s} {'P2 (splitting)':>15s}")
    for doc in sorted(n_rec):
        c = per_doc[doc]; tot.update(c)
        print(f"{doc:34s} {n_rec[doc]:7d} {c['P1']:13d} {c['P2']:15d}")
    print(f"{'TOTAL':34s} {sum(n_rec.values()):7d} {tot['P1']:13d} {tot['P2']:15d}")
    print(f"validation vs the scorer's own miss lists: {len(mismatch)} record(s) disagree"
          + (f" — first: {mismatch[:4]}" if mismatch else " (exact agreement)"))
    print("\n## P2 (splitting) misses by site — (answer, symbol, how): count")
    for doc in sorted(p2_sites):
        print(f"\n{doc}")
        for (k, sym, how), n in p2_sites[doc].most_common():
            print(f"   {k}  {sym[0]:12s} {sym[1]!r:24s} {how:18s} ×{n}")


if __name__ == "__main__":
    main(sys.argv[1:])
