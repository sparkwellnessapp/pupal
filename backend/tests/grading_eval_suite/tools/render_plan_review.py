# -*- coding: utf-8 -*-
"""Render plans/hobby_tvshow.plan.json -> plans/hobby_tvshow_plan_review.md.
Re-run after any plan amendment (H-4 item 3 pairs it with the expressibility
guard: the guard verifies, this renders)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.agents.grader.plan_schemas import GradingPlan
from tests.grading_eval_suite.fixtures import load_bundle

SUITE = Path(__file__).resolve().parents[1]
KIND = {"required": "נדרש", "tariff": "ניכוי", "note_only": "הערה בלבד"}

HEADER = """# GradingPlan `{ver}` — RATIFIED (owner H-4, 2026-08-28, amendments A-1…A-6)

**plan_version:** `{ver}` · **contract pin:** `{pin}…` · **38 terminals ·
{n_checks} checks** ({kinds}) · validator: **CLEAN** · expressibility:
**190/190** (red-first vs v1 caught exactly the two ratified-unreachable cases;
the guard is now permanent — `plan_expressibility.py`, wired into `_load_plan`
pre-spend and `test_plan_expressibility.py`).

**Ratification record:** Q-1 as authored (comparison carries 3; usage-check
note_only — the 2+1 alternative makes five ratified GT 3s unreachable and
contradicts «לא להוריד, לכתוב הערה») · Q-2 as authored · Q-3 as authored except
A-1 · Q-4 both fields stay. Amendments: **A-1** q1.א.c1 → 1+1+1+1 per-parameter
· **A-2** q2.ב.c4.s2 start-index tariff 0.5 + base-candidate equivalence ·
**A-3** q1.ב.c7 semantic-flag equivalence [PL-8] · **A-4** min-index idiom
equivalence on q2.ב.c4.s0/s4 [PL-3] · **A-5** cw/CR shorthand on q1.ב.c3 [PL-2]
· **A-6** wrong-math verdict semantics on q1.ג.c6/c7 (met + tariff, never
compounded). **v3 (H-2-review Ruling 1, 2026-08-29):** the PL-10/AUDIT-3
undeclared-target boundary on q1.א.c1.k2–k4 and the R-β per-access-site rule
on both getter tariffs — constitution transcriptions, owner text verbatim.

**v5 (FP2 rulings R-A/R-B/R-C, 2026-08-29):** the credit-once completion on
the PL-9 note («הזיכוי חד-פעמי, כשם שהחיוב חד-פעמי» — source: the GT's own
charge-once note); the q1.ג.c0 header split (0.5+0.5, the criterion's own two
components); the q2.א.c1 off-by-one tariff transcribing the GT's "Owner-ruled
−1" — which RETIRES the H-4 item-5 accepted ±0.5 (dan q2.א.c1 GT 9 is now on
the faithful path: structure met + tariff).

**How to read:** the verifier answers met/partially_met/not_met per check with a
verbatim span; the pricer converts (required met→100% · partially_met→50% ·
not_met→0 · tariff not_met→the amount, once per charge-group · note_only→
annotation). **The verifier never sees point values.** «מקור» cites the rubric
span each check derives from.
"""


def main() -> None:
    plan = GradingPlan.model_validate_json(
        (SUITE / "plans" / "hobby_tvshow.plan.json").read_text(encoding="utf-8"))
    bundle = load_bundle("dan_basiuk", suite_dir=SUITE)
    scope_of = {t: (i.question_id if i.sub_question_id is None
                    else f"{i.question_id}.{i.sub_question_id}")
                for t, i in bundle.terminal_infos.items()}
    kinds: dict = {}
    for t in plan.terminals:
        for c in t.checks:
            kinds[c.kind] = kinds.get(c.kind, 0) + 1
    L = [HEADER.format(ver=plan.plan_version,
                       pin=plan.rubric_contract_sha256[:16],
                       n_checks=sum(kinds.values()),
                       kinds=" / ".join(f"{v} {k}" for k, v in sorted(kinds.items())))]
    cur = None
    for tp in plan.terminals:
        sc = scope_of[tp.terminal_id]
        if sc != cur:
            cur = sc
            L.append(f"\n## סעיף {sc}\n")
        L.append(f"### `{tp.terminal_id}` — {tp.points_possible} נק'")
        for c in tp.checks:
            extra = ""
            if c.kind == "tariff":
                extra = (f" · **ניכוי {c.tariff_amount}**"
                         + (f" · חיוב חד-פעמי בקבוצה `{c.charge_group}`"
                            if c.charge_group else ""))
            elif c.kind == "required":
                extra = f" · **{c.points} נק'**"
            L.append(f"- [{KIND[c.kind]}] `{c.check_id}`{extra}: {c.description_he}")
            if c.equivalence_note:
                L.append(f"  - שקילות: {c.equivalence_note}")
            if c.rubric_quote:
                L.append(f"  - מקור: «{c.rubric_quote}»")
        L.append("")
    out = SUITE / "plans" / "hobby_tvshow_plan_review.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"rendered {out} ({len(L)} blocks)")


if __name__ == "__main__":
    main()
