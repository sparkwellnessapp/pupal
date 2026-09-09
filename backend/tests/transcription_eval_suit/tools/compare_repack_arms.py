#!/usr/bin/env python
"""
Stage E — read the p1_only arms and say, per document, whether the re-encoded
corpus reads worse than the original.

IT REPORTS; IT DOES NOT DECIDE. The ship gate is `check_goal.sh` at k>=5 and it
is untouched. This exists so a diagnostic run can be read honestly instead of by
squinting at two summary files.

VALIDITY BEFORE ACCURACY — the suite's own rule (§17.1), and the reason this
tool was rewritten once already. A record with a parse failure or coverage < 1.0
did not read the document WORSE; it did not read it at all. Averaging it into an
accuracy mean is a category error that produces a number nobody should act on:
ONE `MAX_TOKENS` truncation on a 6-page document drags its mean from 0.94 to
0.67, which reads as catastrophic quality loss when the real event is a
truncated JSON response. So invalid records are counted and named separately,
excluded from the ratio, and they decide the verdict on their own — an arm that
produces any invalid record has already failed, because check_goal.sh refuses a
run with one.

The accuracy rule is the 2026-08-19 attempt's, reused so two runs stay
comparable: a document regresses if its mean strict ratio falls more than 0.005
below the champion's, and any critical-token recall floor that drops at all is
named, because those are the tokens a wrong character turns into a wrong grade.

ONE DIFFERENCE FROM 2026-08-19, stated because it matters. That was a TRUE
paired A/B — one render, encoded both ways, so only compression differed. Here
the variants were re-RENDERED by Chromium at 200 DPI and then encoded, so this
measures the re-render AND the re-encode together. That is the right comparison
for the product question, because it is exactly what Stage F would ship, but a
regression here does not isolate which half caused it.

Usage:  python -m tests.transcription_eval_suit.tools.compare_repack_arms
        python -m tests.transcription_eval_suit.tools.compare_repack_arms --min-repeats 5
"""
from __future__ import annotations

import json
import pathlib
import statistics
import sys

# Windows consoles default to cp1252; a UnicodeEncodeError mid-report would
# truncate the only readable summary of a run that cost real money.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SUITE = pathlib.Path(__file__).resolve().parents[1]
RESULTS = SUITE / "results"

#: A document may not lose more than this much mean strict ratio (2026-08-19).
RATIO_TOLERANCE = 0.005

CRITICAL = ("operator_recall", "structural_recall", "method_call_recall")


def _load(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


#: The champion arm: stock config, stock corpus.
CHAMPION = ("v0", "pdfs")


def _latest_by_arm(min_repeats: int = 0) -> dict[tuple[str, str], pathlib.Path]:
    """Newest p1_only run per ARM, where an arm is (config_name, pdf_dir).

    Keyed on BOTH because the two experiments this tool serves vary different
    things: the client-repack arms hold the config still and swap the corpus,
    while the wire-format arm holds the corpus still and swaps the config. One
    key would silently collapse one of them into the champion.

    Globs EVERY run dir and filters on the recorded `mode`, not on the folder
    name: the runner names results `{timestamp}_{config}` with no mode in it, so
    a `*_p1_only` glob silently matches only historical runs and reports "no
    champion found" right after a run that just cost real money.

    `min_repeats` lets a k>=5 comparison ignore the earlier k=3 diagnostics
    rather than mixing two evidence standards in one table.
    """
    found: dict[tuple[str, str], pathlib.Path] = {}
    for d in sorted(RESULTS.glob("*"), reverse=True):
        f = d / "results.json"
        if not f.is_file():
            continue
        try:
            data = _load(f)
        except Exception:
            continue
        if data.get("mode") != "p1_only":
            continue
        if data.get("repeats", 0) < min_repeats:
            continue
        key = (data.get("config_name", "?"), data.get("pdf_dir", "pdfs"))
        found.setdefault(key, f)                           # desc => newest first
    return found


def _is_valid(record: dict) -> bool:
    return record["parse_failures"] == 0 and record["p1"]["coverage"] >= 1.0


def _per_doc(data: dict) -> dict[str, dict]:
    """doc_id -> accuracy over VALID records, plus the validity facts."""
    out: dict[str, dict] = {}
    by_doc: dict[str, list[dict]] = {}
    for r in data.get("records", []):
        by_doc.setdefault(r["doc_id"], []).append(r)

    for doc, recs in by_doc.items():
        valid = [r for r in recs if _is_valid(r)]
        ratios = [r["p1"]["doc_ratio_strict"] for r in valid]
        reasons: list[str] = []
        for r in recs:
            if not _is_valid(r):
                reasons += r.get("parse_failure_finish_reasons") or ["coverage<1"]
        out[doc] = {
            "n": len(recs),
            "n_valid": len(valid),
            "invalid_reasons": sorted(set(reasons)),
            "ratio": statistics.fmean(ratios) if ratios else float("nan"),
            "crit": {
                k: (statistics.fmean([r["p1"]["critical"].get(k, 0.0) for r in valid])
                    if valid else 0.0)
                for k in CRITICAL
            },
            "cost": statistics.fmean([r["cost_usd"] for r in recs]),
            "latency": statistics.fmean([r["latency_ms"] for r in recs]),
        }
    return out


def _mean(arm: dict, key: str) -> float:
    return statistics.fmean([a[key] for a in arm.values()])


def main() -> int:
    min_repeats = 0
    if "--min-repeats" in sys.argv:
        min_repeats = int(sys.argv[sys.argv.index("--min-repeats") + 1])
    arms = _latest_by_arm(min_repeats)
    if CHAMPION not in arms:
        print(f"no champion {CHAMPION} p1_only run found"
              + (f" with repeats>={min_repeats}" if min_repeats else ""),
              file=sys.stderr)
        return 2

    champ_data = _load(arms[CHAMPION])
    champ = _per_doc(champ_data)
    print(f"champion : {arms[CHAMPION].parent.name}  "
          f"({champ_data['repeats']} repeats, {len(champ)} docs)")
    if champ_data["repeats"] < 5:
        print(f"  k={champ_data['repeats']} - DIAGNOSTIC ONLY. The ship gate is "
              f"check_goal.sh at k>=5; this cannot authorise a change.")
    bad_champ = [d for d, a in champ.items() if a["n_valid"] < a["n"]]
    if bad_champ:
        print(f"  NOTE: the champion itself had invalid records ({', '.join(bad_champ)})")
    print(f"  baseline: cost/doc ${_mean(champ, 'cost'):.4f}  "
          f"latency {_mean(champ, 'latency') / 1000:.0f}s")
    print()

    verdicts: dict[str, str] = {}
    for key in sorted(k for k in arms if k != CHAMPION):
        arm = _per_doc(_load(arms[key]))
        # An arm sharing NO documents with the champion is a historical run from
        # before the fixture ids changed (B-30f added the exam prefix). Comparing
        # it prints five MISSING rows and a confident "NOT PROMISING" about a run
        # that was never in this experiment.
        if not (set(arm) & set(champ)):
            continue
        label = key[0] if key[1] == "pdfs" else f"{key[0]} + {key[1]}"
        print(f"-- {label}  ({arms[key].parent.name}) " + "-" * 24)
        print(f"{'doc':<30}{'champ':>8}{'variant':>9}{'delta':>9}{'valid':>8}  verdict")

        regressed: list[str] = []
        floor_drops: list[tuple[str, list[str]]] = []
        invalid: list[tuple[str, int, list[str]]] = []

        for doc in sorted(champ):
            if doc not in arm:
                print(f"{doc:<30}{champ[doc]['ratio']:8.4f}{'-':>9}{'-':>9}{'-':>8}  MISSING")
                regressed.append(doc)
                continue
            a = arm[doc]
            c, v = champ[doc]["ratio"], a["ratio"]
            delta = v - c
            is_invalid = a["n_valid"] < a["n"]
            is_regressed = delta < -RATIO_TOLERANCE
            drops = [k for k in CRITICAL
                     if a["crit"][k] < champ[doc]["crit"][k] - 1e-9]
            if is_invalid:
                invalid.append((doc, a["n"] - a["n_valid"], a["invalid_reasons"]))
            if is_regressed:
                regressed.append(doc)
            if drops:
                floor_drops.append((doc, drops))
            mark = ("INVALID" if is_invalid else
                    "REGRESSED" if is_regressed else
                    "floor-drop" if drops else "ok")
            valid_col = f"{a['n_valid']}/{a['n']}"
            print(f"{doc:<30}{c:8.4f}{v:9.4f}{delta:+9.4f}{valid_col:>8}  {mark}")

        print(f"  cost/doc ${_mean(champ, 'cost'):.4f} -> ${_mean(arm, 'cost'):.4f}"
              f"   latency {_mean(champ, 'latency') / 1000:.0f}s"
              f" -> {_mean(arm, 'latency') / 1000:.0f}s")
        for doc, n, reasons in invalid:
            print(f"  INVALID  {doc}: {n} of {arm[doc]['n']} repeats "
                  f"({', '.join(reasons)}) - excluded from the ratio above")
        for doc, ks in floor_drops:
            print("  floor drop  " + doc + ": " + ", ".join(
                f"{k} {champ[doc]['crit'][k]:.4f}->{arm[doc]['crit'][k]:.4f}"
                for k in ks))

        verdict = ("NOT PROMISING (invalid records)" if invalid else
                   "NOT PROMISING" if regressed else
                   "PROMISING (floors moved)" if floor_drops else
                   "PROMISING")
        verdicts[key] = verdict
        print(f"  -> {verdict}"
              + (f" - regressed: {', '.join(regressed)}" if regressed else ""))
        print()

    print("Summary")
    for k, v in verdicts.items():
        label = k[0] if k[1] == "pdfs" else f"{k[0]} + {k[1]}"
        print(f"  {label:<34} {v}")
    print()
    print("A 'PROMISING' arm has earned a k>=5 check_goal.sh run - nothing more.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
