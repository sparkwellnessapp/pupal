"""
F0 — the hobby_tvshow corrected-variant pipeline [R5/H1].

The sibling rubric GT (`../rubric_eval_suite/benchmarks/hobby_tvshow.json`)
faithfully captures a real teacher error (the FC worked example): the
PrintLowRatingChannel component was mislabeled onto sub-question ב, so ג was
never extracted, q2.ב sums 45 vs declared 29, and q2 sums 44 vs declared 60.
The GT's own `structural_mislabel` mistake records the mechanical fix.

This tool:
  1. proves the ORIGINAL blocks compilation (the error is real — INV-1 + INV-2);
  2. applies the RECORDED fix_proposal steps, byte-faithful to the GT:
       move_text     -> new sub-question ג with the recorded question text
       move_criterion-> q2.ב criteria[6] (PrintLowRatingChannel, 16 pts) moves to ג
       set_points    -> ג.points = 16
     plus two agent-surfaced consequences for the owner to ratify:
       [DL-5] the moved criterion's id is renamed q2.ב.c6 -> q2.ג.c0 (path-honest;
              GT terminals are authored against the corrected ids);
       [DL-6] the stale error-description artifacts (2 rubric_mismatch WARNINGs,
              2 point_sum_mismatch mistakes, the applied structural_mislabel) are
              dropped — they describe the pre-fix state; keeping them would force
              fake acknowledgments at compile.
  3. proves the CORRECTED variant compiles clean through the REAL ContractCompiler;
  4. stages the proposal for the owner: H1_CORRECTION_PROPOSAL.md + a staged
     contract under benchmarks/contracts/_proposed/ (NOT the ratified path).

Ratification [H1] is the OWNER's act: re-run with --ratify after approval to
move the snapshot to benchmarks/contracts/hobby_tvshow_corrected.contract.json
with provenance. GT authoring waits for that ratification [R5].

NOTE: contract_version is a fresh UUID per compile — the ratified snapshot is
frozen ONCE and hash-pinned by every GT [D5]; regenerating it breaks the pins
by design (rebuild_fixtures refuses without an explicit override).
"""
from __future__ import annotations

import copy
import io
import json
import sys
from pathlib import Path

from app.schemas.ontology_types import ExtractRubricResponse, GradingRubricContract
from app.services.contract_compiler import CompilationError, compile_rubric

SUITE_DIR = Path(__file__).resolve().parents[1]
SIBLING_GT = SUITE_DIR.parents[0] / "rubric_eval_suite" / "benchmarks" / "hobby_tvshow.json"
PROPOSED_DIR = SUITE_DIR / "benchmarks" / "contracts" / "_proposed"
RATIFIED_PATH = SUITE_DIR / "benchmarks" / "contracts" / "hobby_tvshow_corrected.contract.json"
PROPOSAL_DOC = SUITE_DIR / "H1_CORRECTION_PROPOSAL.md"


def load_original() -> ExtractRubricResponse:
    return ExtractRubricResponse.model_validate_json(
        SIBLING_GT.read_text(encoding="utf-8"))


def compile_response(resp: ExtractRubricResponse) -> GradingRubricContract:
    return compile_rubric(resp)


def _find_recorded_fix(data: dict) -> dict:
    for m in data.get("pedagogical_mistakes") or []:
        if m.get("kind") == "structural_mislabel" and m.get("suggested_fix"):
            return m["suggested_fix"]
    raise RuntimeError("hobby GT: recorded structural_mislabel fix not found")


def apply_recorded_fix(resp: ExtractRubricResponse) -> ExtractRubricResponse:
    """Apply the GT's own suggested_fix steps [R5], plus DL-5/DL-6."""
    data = copy.deepcopy(resp.model_dump(mode="json"))
    fix = _find_recorded_fix(data)
    steps = {s["op"]: s for s in fix["steps"]}
    move_text, move_crit, set_points = (steps["move_text"], steps["move_criterion"],
                                        steps["set_points"])
    assert move_crit["scope"] == "q2.ב" and move_crit["to_scope"] == "q2.ג"

    q2 = next(q for q in data["questions"] if q["question_id"] == "q2")
    sq_b = next(s for s in q2["sub_questions"] if s["sub_question_id"] == "ב")
    idx = move_crit["criterion_index"]
    moved = sq_b["criteria"].pop(idx)
    assert moved["criterion_id"] == "q2.ב.c6", moved["criterion_id"]
    # [DL-5] path-honest rename — surfaced in the H1 diff for ratification
    moved["criterion_id"] = "q2.ג.c0"
    moved["index"] = 0

    q2["sub_questions"].append({
        "sub_question_id": "ג",
        "index": len(q2["sub_questions"]),
        "points": set_points["value"],          # "16" per the recorded step
        "text": move_text["text"],              # the recorded ג question text
        "criteria": [moved],
    })

    # [DL-6] drop the artifacts that describe the pre-fix state
    data["annotations"] = []
    data["pedagogical_mistakes"] = []
    return ExtractRubricResponse.model_validate(data)


def build_proposal() -> dict:
    """The mechanical half of F0: proofs + staged artifacts. Returns a summary."""
    original = load_original()
    try:
        compile_response(original)
        original_block = "UNEXPECTED: original compiled clean (H1 premise broken!)"
        blocked = False
    except CompilationError as e:
        original_block = str(e)
        blocked = True

    corrected = apply_recorded_fix(load_original())
    contract = compile_response(corrected)       # raises if not clean

    PROPOSED_DIR.mkdir(parents=True, exist_ok=True)
    draft_p = PROPOSED_DIR / "hobby_tvshow_corrected.draft.json"
    contract_p = PROPOSED_DIR / "hobby_tvshow_corrected.contract.json"
    draft_p.write_text(corrected.model_dump_json(indent=1), encoding="utf-8")
    contract_p.write_text(contract.model_dump_json(indent=1), encoding="utf-8")

    q2 = next(q for q in contract.questions if q.question_id == "q2")
    subs = {sq.sub_question_id: sq for sq in q2.sub_questions}
    summary = {
        "original_blocked": blocked,
        "original_errors": original_block,
        "corrected_total_points": str(contract.total_points),
        "q2_subs": {k: str(v.points) for k, v in subs.items()},
        "gimel_criteria": [(c.criterion_id, str(c.points)) for c in subs["ג"].criteria],
        "bet_criteria_sum": str(sum(c.points for c in subs["ב"].criteria)),
        "staged_contract": str(contract_p),
        "staged_draft": str(draft_p),
    }
    return summary


def write_proposal_doc(summary: dict) -> Path:
    doc = f"""# H1 — hobby_tvshow corrected-rubric proposal [R5, awaiting OWNER ratification]

**Status:** STAGED — nothing under `benchmarks/contracts/` (ratified path) is written.
GT authoring [F5] waits for this ratification. Ratify by replying, then the agent
runs `python -m tests.grading_eval_suite.tools.f0_hobby_correction --ratify`.

## 1. The error is real — the ORIGINAL blocks compilation (proof)

```
{summary['original_errors']}
```

## 2. The fix applied — EXACTLY the GT's own recorded fix_proposal

| step | content |
|---|---|
| move_text | new sub-question **ג** created with the recorded question text (PrintLowRatingChannel task) |
| move_criterion | `q2.ב` criteria[6] — "פעולה חיצונית PrintLowRatingChannel", **16 pts** — moved to ג |
| set_points | ג.points = **16** |

**Agent-surfaced consequences requiring your ratification:**
- **[DL-5] id rename:** the moved criterion becomes `q2.ג.c0` (was `q2.ב.c6`) — ids
  stay path-honest; your GT judgments will be authored against `q2.ג.c0`.
- **[DL-6] stale diagnostics dropped:** the 2 `rubric_mismatch` WARNINGs + the 2
  `point_sum_mismatch` mistakes + the applied `structural_mislabel` are removed from
  the corrected draft (they describe the pre-fix state; keeping them would force
  fake warning-acknowledgments at compile).

## 3. The corrected variant compiles CLEAN (proof)

- total_points: **{summary['corrected_total_points']}** (= 100)
- q2 sub-questions: {summary['q2_subs']}  (15 + 29 + 16 = 60 = q2 declared)
- ב criteria sum: **{summary['bet_criteria_sum']}** (= 29 declared — INV-2 resolves)
- ג criteria: {summary['gimel_criteria']}

One teacher fix resolves all three shadows together — the FC worked example, closed.

## 4. Provenance to be stamped at ratification

`derived_from: ../rubric_eval_suite/benchmarks/hobby_tvshow.json` ·
`correction: structural_mislabel fix_proposal (recorded in the GT) applied verbatim + DL-5 id rename + DL-6 stale-diagnostic drop` ·
`ratified_by: Noam` · `date: <ratification date>`

Staged artifacts: `{summary['staged_contract']}` (+ the corrected draft beside it).
"""
    PROPOSAL_DOC.write_text(doc, encoding="utf-8")
    return PROPOSAL_DOC


def ratify() -> None:
    """[H1] Owner-approved: move the staged snapshot to the ratified path with
    provenance. Run ONLY after the owner's explicit ratification."""
    staged = PROPOSED_DIR / "hobby_tvshow_corrected.contract.json"
    if not staged.exists():
        raise SystemExit("nothing staged — run without --ratify first")
    if RATIFIED_PATH.exists():
        raise SystemExit(f"{RATIFIED_PATH} already exists — the ratified snapshot is "
                         f"frozen ONCE (GT hashes pin it, D5); refusing to overwrite")
    RATIFIED_PATH.parent.mkdir(parents=True, exist_ok=True)
    RATIFIED_PATH.write_bytes(staged.read_bytes())
    prov = {
        "derived_from": "../rubric_eval_suite/benchmarks/hobby_tvshow.json",
        "correction": ("structural_mislabel fix_proposal (recorded in the sibling GT) "
                       "applied verbatim; [DL-5] q2.ב.c6 -> q2.ג.c0; [DL-6] stale "
                       "pre-fix diagnostics dropped"),
        "ratified_by": "Noam",
        "date": __import__("time").strftime("%Y-%m-%d"),
        "staged_by_tool": "tools/f0_hobby_correction.py",
    }
    (RATIFIED_PATH.with_suffix(".provenance.json")).write_text(
        json.dumps(prov, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[H1] ratified snapshot written: {RATIFIED_PATH}")


def main() -> None:
    if "--ratify" in sys.argv:
        ratify()
        return
    summary = build_proposal()
    doc = write_proposal_doc(summary)
    print(f"[F0] original blocked: {summary['original_blocked']}")
    print(f"[F0] corrected compiles clean; total={summary['corrected_total_points']}")
    print(f"[F0] proposal staged -> {doc}")


if __name__ == "__main__":
    main()
