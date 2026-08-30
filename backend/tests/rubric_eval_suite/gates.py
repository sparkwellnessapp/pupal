"""
The conjunctive gate. A rubric passes iff ALL criteria hold simultaneously —
partial improvement that masks a regression must not pass (the conjunctive-gate
discipline from the transcription suite).

A fix a teacher can ACCEPT is part of the contract: `fix_effect_inconsistent`
fails a rubric whose proposed suggested_fix, once applied, leaves the rubric not
adding up. Added 2026-08-24 after a model shipped a fix that created the missing
sub-question correctly but left the source declaring points it no longer had —
the teacher accepts, and lands somewhere worse. pedagogical_match could not see it:
it compares mistakes by (kind, target) and never reads the payload.

DELIBERATELY NOT a gate criterion: point_sum_consistency. A teacher's rubric may
be genuinely inconsistent; the extractor's job is to reproduce it faithfully and
flag it (annotation_match), not to 'fix' it. Gating on consistency would punish
correct extraction of a flawed source — the rubric analog of the rejected Policy 1.
"""
from __future__ import annotations

from typing import List, Tuple

from .schemas import RubricScore


def evaluate_gate(rs: RubricScore, cost_ceiling: float) -> Tuple[bool, List[str]]:
    f: List[str] = []

    if not rs.valid:
        # an invalid (truncated / unparseable) extraction cannot pass and is excluded
        # from accuracy aggregates upstream; it fails the gate outright.
        return False, [f"invalid: {rs.invalid_reason}"]

    def need(cond: bool, label: str):
        if not cond:
            f.append(label)

    need(rs.question_recall >= 1.0, f"question_recall={rs.question_recall:.3f}<1")
    need(rs.question_precision >= 1.0, f"question_precision={rs.question_precision:.3f}<1")
    need(rs.subquestion_structure_match >= 1.0, f"subquestion_structure_match={rs.subquestion_structure_match:.3f}<1")
    need(rs.criterion_recall >= 1.0, f"criterion_recall={rs.criterion_recall:.3f}<1")
    need(rs.criterion_precision >= 1.0, f"criterion_precision={rs.criterion_precision:.3f}<1")
    need(rs.subcriterion_recall >= 1.0, f"subcriterion_recall={rs.subcriterion_recall:.3f}<1")
    need(rs.subcriterion_precision >= 1.0, f"subcriterion_precision={rs.subcriterion_precision:.3f}<1")
    need(rs.point_exactness >= 1.0, f"point_exactness={rs.point_exactness:.3f}<1")
    need(rs.total_points_correct, "total_points_incorrect")
    need(rs.selection_match, "selection_mismatch")
    need(rs.example_solution_fidelity >= 1.0, f"example_solution_fidelity={rs.example_solution_fidelity:.3f}<1")
    need(rs.annotation_match, "annotation_mismatch")
    need(rs.pedagogical_match, "pedagogical_mismatch")
    # FIX-EFFECT (2026-08-24, owner-approved). `is False` on purpose: None means
    # VACUOUS (the prediction proposed no fix) and must SKIP, exactly like the cost
    # check below when cost_usd is None. Armed only after measuring it over all 301
    # cached predictions: 229 vacuous / 51 reconcile / 21 broken, and every broken
    # one belongs to a config already rejected or to the pre-fix state of this
    # defect. The shipped configuration scores 0 broken.
    # It is a SIBLING of pedagogical_match, never folded into it: that one compares
    # a mistake SET against GT, this one asks whether the fix a mistake carries
    # actually reconciles the rubric. Merging them would make a failure ambiguous
    # about which half broke.
    # FIX-EFFECT (armed 2026-08-24, owner ruling "Option A"). `is False` on purpose:
    # None means VACUOUS (the prediction proposed no fix) and must SKIP, exactly like
    # the cost check below when cost_usd is None.
    # A fix is judged BY WHAT IT CLAIMS (scoring.py::fix_effect_check): a move-bearing
    # plan claims root-cause resolution and is held to its ancestors; a pure set_points
    # plan is a minimal local correction and is held only to the node it targets.
    # Measured over all 301 cached predictions before arming: 229 vacuous / 55
    # reconcile / 17 broken, and the SHIPPED configuration scores ZERO broken while
    # the same config before the Tier-B fix scores 3/3 broken.
    # SIBLING of pedagogical_match, never folded into it: that one compares a mistake
    # SET against GT, this one asks whether the fix a mistake carries actually
    # reconciles. Merged, a failure would not say which half broke.
    if rs.fix_effect_consistent is False:
        detail = rs.fix_effect_violations[0] if rs.fix_effect_violations else ""
        f.append(f"fix_effect_inconsistent: {detail}" if detail else "fix_effect_inconsistent")

    if rs.cost_usd is not None:
        need(rs.cost_usd <= cost_ceiling, f"cost={rs.cost_usd:.3f}>{cost_ceiling}")

    return (len(f) == 0), f


def apply_gate(rs: RubricScore, cost_ceiling: float) -> RubricScore:
    rs.gate_pass, rs.gate_failures = evaluate_gate(rs, cost_ceiling)
    return rs