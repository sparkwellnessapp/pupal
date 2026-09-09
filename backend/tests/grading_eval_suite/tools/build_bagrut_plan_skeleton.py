"""
Plan skeleton for bagrut_899371 — the authoring aid for a hand-written plan.

Mirrors `hobby_tvshow.plan.json`'s shape with `checks: []` left for the owner,
plus three aids per terminal that turn work the machine can already do into
something she does not have to redo by hand:

  * **`_detected_deductions`** — the calibrated v2 detector (12/12 recall,
    14/14 precision on the reference plan) run over this exam. Every «...להוריד N»
    located, with its amount, its verbatim clause, and the terminals it could
    modify. Locating a deduction and copying its number is string work; only
    "which terminal does this modify" is judgement, and that is the one thing
    left to decide.
  * **`_re_case`** — which R-E reconciliation case the terminal falls into,
    with the stated components. An ANALYSIS, not an application: R-E's pricing
    policy is not implemented yet, so nothing here is applied to any number.
  * **`_stated_components`** — the point figures the criterion text itself
    names, so a mismatch against `points_possible` is visible while authoring
    rather than discovered by the validator afterwards.

Everything prefixed `_` is an authoring aid and is stripped before the file
becomes a `GradingPlan`. `checks` is the only field the owner fills.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from decimal import Decimal
from pathlib import Path

SUITE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SUITE.parents[1]))

from app.agents.plan_gen.prompt import detect_deductions          # noqa: E402
from app.schemas.ontology_types import GradingRubricContract      # noqa: E402

CONTRACT = SUITE / "compiled_rubric_bagrut.json"
OUT = SUITE / "plans" / "bagrut_899371.plan.skeleton.json"
EXAM_ID = "bagrut_899371"

TOTAL_CLAIM = re.compile(r"סה[\"״']?כ\s*(\d+(?:\.\d+)?)")
PER_EACH = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:נק['׳]?|נקודות)?\s*(?:כל|לכל)\s*(?:תא|אחד|רכיב)")
CELLS = re.compile(r"(\d+)\s*תאים")
INLINE_PTS = re.compile(r"(\d+(?:\.\d+)?)\s*נק(?:'|׳|ודות|ודה)")
UNSURE = re.compile(r"\(\s*או\s*\d+\s*\?\s*\)")


def classify(text: str, points: Decimal) -> dict:
    """Which R-E case this terminal presents. Analysis only — R-E's pricing is
    not implemented here and no number below is adjusted."""
    cells, each = CELLS.search(text), PER_EACH.search(text)
    inline = [Decimal(x) for x in INLINE_PTS.findall(text)]

    if cells and each:
        n = int(cells.group(1))
        per = Decimal(each.group(1).replace(",", "."))
        return {
            "_re_case": "case_1_uniform_units",
            "_units": n,
            "_stated_per_unit": str(per),
            "_stated_total": str(n * per),
            "_note": (f"{n} uniform units at {per} each = {n * per} vs "
                      f"points_possible {points}. R-E Case 1: emit ONE counted "
                      f"check with points={points}, unit_count={n}; per-unit is "
                      f"derived, and the stated per-unit is her rounding, not an "
                      f"error. NOTE: the `counted` kind is not implemented yet."),
        }
    if UNSURE.search(text):
        return {"_re_case": "case_4_teacher_indecision",
                "_note": "The rubric states two possible deductions. R-E Case 4: "
                         "default to the LENIENT end (smaller) and flag."}
    if len(inline) >= 2:
        total = sum(inline)
        if total > points:
            return {"_re_case": "case_3_over_allocation",
                    "_stated_components": [str(x) for x in inline],
                    "_stated_total": str(total),
                    "_note": (f"stated components sum to {total} > "
                              f"points_possible {points}. R-E Case 3: classes "
                              f"descending absorb WHOLE POINTS per member, never "
                              f"reaching the next class; residual breaks the "
                              f"largest class that can take it without inverting "
                              f"order, split evenly, and flags.")}
        if total < points:
            return {"_re_case": "case_2_partial_itemisation",
                    "_stated_components": [str(x) for x in inline],
                    "_stated_total": str(total),
                    "_note": (f"stated components sum to {total} < "
                              f"points_possible {points}. R-E Case 2: keep the "
                              f"stated values exactly and add ONE check carrying "
                              f"the remainder {points - total} for the "
                              f"unenumerated requirement.")}
        return {"_re_case": "clean_itemised",
                "_stated_components": [str(x) for x in inline]}
    if len(inline) == 1 and inline[0] != points:
        return {"_re_case": "case_2_partial_itemisation",
                "_stated_components": [str(inline[0])],
                "_stated_total": str(inline[0]),
                "_note": (f"one component stated ({inline[0]}) below "
                          f"points_possible {points}; the remainder "
                          f"{points - inline[0]} is unenumerated. R-E Case 2.")}
    for m in TOTAL_CLAIM.finditer(text):
        if Decimal(m.group(1)) != points:
            return {"_re_case": "text_total_disagrees",
                    "_note": (f"text states a total of {m.group(1)} but "
                              f"points_possible is {points}. points_possible is "
                              f"authoritative for the total (R-E principle).")}
    return {"_re_case": "clean"}


def main() -> None:
    contract = GradingRubricContract.model_validate(
        json.loads(CONTRACT.read_text(encoding="utf-8")))
    rubric_hash = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()

    # deductions are detected per SCOPE (V7: a charge_group never spans scopes)
    detected = {}
    scopes = []

    def walk(q, sub, path):
        kids = getattr(sub, "sub_questions", None) if sub else None
        if kids:
            for child in kids:
                walk(q, child, path + [child.sub_question_id])
        else:
            scopes.append((q, sub, ".".join([q.question_id] + path)))

    for q in contract.questions:
        if q.sub_questions:
            for sub in q.sub_questions:
                walk(q, sub, [sub.sub_question_id])
        else:
            scopes.append((q, None, q.question_id))

    for q, sub, label in scopes:
        detected[label] = detect_deductions(q, sub)

    terminals = []
    for q, sub, label in scopes:
        node = sub or q
        markers = detected[label]
        for crit in getattr(node, "criteria", []) or []:
            subs = getattr(crit, "sub_criteria", None) or []
            targets = ([(s.sub_criterion_id, s.points, s.description) for s in subs]
                       if subs else
                       [(crit.criterion_id, crit.points, crit.description)])
            for tid, pts, desc in targets:
                mine = [{
                    "marker_id": d.marker_id,
                    "amount": None if d.amount is None else str(d.amount),
                    "polarity": d.polarity,
                    "quote": d.quote,
                    "candidate_terminal_ids": list(d.candidate_terminal_ids),
                } for d in markers if tid in d.candidate_terminal_ids]
                entry = {
                    "terminal_id": tid,
                    "points_possible": str(pts),
                    "scope": label,
                    "description": desc,
                    "checks": [],                       # OWNER FILLS
                }
                entry.update(classify(desc or "", pts))
                if mine:
                    entry["_detected_deductions"] = mine
                terminals.append(entry)

    skeleton = {
        "plan_version": f"{EXAM_ID}/v0-skeleton",
        "exam_id": EXAM_ID,
        "rubric_contract_sha256": rubric_hash,
        "rubric_contract_version": contract.contract_version,
        "precision": str(contract.numeric_policy.precision),
        "_instructions": (
            "Fill `checks` per terminal. Each check: check_id "
            "(\"<terminal_id>.k<N>\" required / \".t<N>\" tariff / \".n<N>\" "
            "note_only), description_he (requirement-phrased so that 'met' means "
            "SATISFIED, and never stating points), kind, points, "
            "partial_fraction, optional equivalence_note / charge_group, and "
            "rubric_quote — a VERBATIM span of this scope's own text (V9; elide "
            "with … but never paraphrase). Per terminal, Σ required.points must "
            "equal points_possible EXACTLY, and every value must sit on the "
            "precision grid. Delete every key beginning with `_` when done; they "
            "are authoring aids, not plan fields."),
        "terminals": terminals,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(skeleton, ensure_ascii=False, indent=1),
                   encoding="utf-8")

    cases = {}
    for t in terminals:
        cases[t["_re_case"]] = cases.get(t["_re_case"], 0) + 1
    with_ded = sum(1 for t in terminals if t.get("_detected_deductions"))
    print(f"{OUT.relative_to(SUITE.parents[1])}")
    print(f"  terminals: {len(terminals)}  ·  with detected deductions: {with_ded}")
    for k, v in sorted(cases.items()):
        print(f"  {k:32s} {v}")


if __name__ == "__main__":
    main()
