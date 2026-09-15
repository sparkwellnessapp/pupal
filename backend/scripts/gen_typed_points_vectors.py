"""
[OD-R2] Pricer-parity vectors for TYPED amounts — `pricing_vectors_typed.json`.

`gen_grade_review_fixtures.py` emits the AI-only vectors from an eval run
(`--from-run`), which this repo cannot replay on demand. The typed-amount
vectors need no run: they are the SAME published drafts with an overlay laid
over them, priced by the real pricer. So they live in their own file, derived
from the committed `draft_*.json`, and `tests/fixtures/test_grade_review_fixtures.py`
regenerates them in memory and fails on any diff — the same
fixtures-regenerate-clean discipline, one file further along.

Two overlay shapes per terminal, whenever the terminal can carry them (a
tariff is never typed — owner ruling 2026-09-13, a deduction is yes/no):

  typed_credit    her amount on the first required/counted check, at half its
                  points snapped to the grid (a partially_met the verdict
                  vocabulary could not have expressed, e.g. 1.5 of 3)
  terminal_pin    her amount on the criterion row, at half the possible points
                  snapped to the grid — the checks beneath are not priced

The frontend mirror (`lib/pricing.test.ts`) must reproduce every vector
byte-for-byte, exactly as it does the AI-only set.

    python scripts/gen_typed_points_vectors.py            # write
    python scripts/gen_typed_points_vectors.py --check    # fail on any diff
"""
from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

FIX = BACKEND / "tests" / "fixtures" / "grade_review"
OUT = FIX / "pricing_vectors_typed.json"
CONTRACT = (BACKEND / "tests" / "grading_eval_suite" / "benchmarks" / "contracts"
            / "hobby_tvshow_corrected.contract.json")
STUDENTS = ("dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk")


def _half_on_grid(amount: Decimal, precision: Decimal) -> Decimal:
    """Half of `amount`, snapped DOWN to the grid — never above the ceiling."""
    half = amount / 2
    return (half / precision).to_integral_value(rounding="ROUND_FLOOR") * precision


def _check_json(c: dict) -> dict:
    return {"check_id": c["check_id"], "kind": c["kind"], "points": c["points"],
            "tariff": c.get("tariff"), "partial_fraction": c["partial_fraction"],
            "verdict": c["verdict"], "quote_status": c.get("quote_status"),
            "charge_group": c.get("charge_group"),
            "unit_count": c.get("unit_count"), "units_correct": c.get("units_correct")}


def vectors_from_drafts(drafts: dict, precision: Decimal) -> list:
    from app.schemas.graded_test_draft import (
        Check, GradedTestOverrides, TeacherOverride, TerminalPointsOverride)
    from app.services.pricing import (
        apply_overlay, price_scope_checks, typed_maximum, typed_points_of,
        verdict_for_amount)

    vectors = []
    for student in STUDENTS:
        d = drafts[student]
        for scope in d.get("scope_outcomes") or []:
            for crit in scope.get("criterion_outcomes") or []:
                for leaf in (crit.get("sub_criterion_outcomes") or [crit]):
                    tid = leaf.get("sub_criterion_id") or leaf.get("criterion_id")
                    raw_checks = leaf.get("checks") or []
                    if not raw_checks:
                        continue
                    checks = [Check.model_validate(c) for c in raw_checks]
                    possible = Decimal(leaf["points_possible"])

                    def emit(case: str, overrides: GradedTestOverrides) -> None:
                        eff, touched = apply_overlay(checks, overrides.overrides_for(tid))
                        pin = overrides.terminal_point(tid)
                        priced = price_scope_checks(
                            [(tid, possible, eff)], precision,
                            overridden_check_ids=touched,
                            typed_check_points=typed_points_of(overrides.overrides_for(tid)),
                            terminal_points={tid: pin} if pin is not None else None)
                        vectors.append({
                            "case": f"{student}:{tid}:{case}",
                            "student": student,
                            "terminal_id": tid,
                            "points_possible": leaf["points_possible"],
                            "checks": [_check_json(c) for c in raw_checks],
                            "overlay": overrides.model_dump(
                                mode="json", exclude={"feedback", "stamp_position"},
                                exclude_none=True),
                            "expected_points_awarded": str(priced[tid]),
                        })

                    credit = next((c for c in checks
                                   if c.kind in ("required", "counted") and c.points > 0), None)
                    if credit is not None:
                        amount = _half_on_grid(typed_maximum(credit), precision)
                        emit("typed_credit", GradedTestOverrides(terminals={tid: [
                            TeacherOverride(
                                check_id=credit.check_id, points_awarded=amount,
                                verdict=verdict_for_amount(amount, typed_maximum(credit)),
                                decided_at="2026-09-13T00:00:00+00:00")]}))

                    if possible > 0:
                        emit("terminal_pin", GradedTestOverrides(terminal_points={
                            tid: TerminalPointsOverride(
                                points_awarded=_half_on_grid(possible, precision),
                                decided_at="2026-09-13T00:00:00+00:00")}))
    return vectors


def load_inputs():
    drafts = {s: json.loads((FIX / f"draft_{s}.json").read_text(encoding="utf-8"))
              for s in STUDENTS}
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    return drafts, Decimal(str(contract["numeric_policy"]["precision"]))


def render(vectors: list) -> str:
    return json.dumps(vectors, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="regenerate and fail on any diff (fixtures-regenerate-clean)")
    args = ap.parse_args()

    drafts, precision = load_inputs()
    text = render(vectors_from_drafts(drafts, precision))
    current = OUT.read_text(encoding="utf-8") if OUT.exists() else None
    if args.check:
        if current != text:
            raise SystemExit(f"{OUT.name} is stale — rerun without --check")
        print(f"{OUT.name}: clean")
        return
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(BACKEND)} ({text.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
