"""
The conjunctive gate. A rubric passes iff ALL criteria hold simultaneously —
partial improvement that masks a regression must not pass (the conjunctive-gate
discipline from the transcription suite).

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
    if rs.cost_usd is not None:
        need(rs.cost_usd <= cost_ceiling, f"cost={rs.cost_usd:.3f}>{cost_ceiling}")

    return (len(f) == 0), f


def apply_gate(rs: RubricScore, cost_ceiling: float) -> RubricScore:
    rs.gate_pass, rs.gate_failures = evaluate_gate(rs, cost_ceiling)
    return rs