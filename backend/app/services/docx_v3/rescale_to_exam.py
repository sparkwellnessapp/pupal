"""rescale_to_exam — the D-13 grid-snap post-pass (ruled by Noam, 2026-09-08).

# ALPHA-GAP A-3 (D-13): this WHOLE function is the gap — grid-snapped shares (33.5/33.25…); alpha normalizes per-question scale vs exam share, adds the cap rule and the chapter minimum, and retires this file.

The Math extractor records the teacher's weights EXACTLY as written, on a per-question
scale of 100 (F-1: "10%" stays in the description; the number becomes the points). The
rubric total is always the exam's real total (100) — never an invented denominator. This
pure function maps that draft onto the exam:

  (1) SHARES — the exam total is split across the k selected questions of a selection
      group on the 0.25 grid as evenly as possible, residual on the FIRST member
      (k=3 → 33.5, 33.25, 33.25; every member of the group gets a share from that
      pattern, so the achievable maximum is exactly 100 when the first question is chosen
      and 99.75 otherwise — INV-4 sums the k LARGEST member totals, so it holds).
      Questions in no group keep their printed points.
  (2) CRITERIA — every node's weights are scaled to its parent's share and snapped to the
      grid by LARGEST REMAINDER so Σ children == parent EXACTLY, top-down through
      sub-questions and criteria (INV-1/2/3 hold by construction, never by tolerance).
      Sub-criteria: same rule under their criterion.

Runs ONCE on a mathematics draft, after extraction and before the teacher sees it; other
profiles never enter it (the profile's `rescale_to_exam` flag decides, not a subject
branch). Idempotent: a draft already stamped `extraction_metadata["rescale_to_exam"]`
is returned unchanged. The teacher sees her original weight in every description and
overrides freely; the phase-gate report says exactly what was snapped (§9 item 3).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR
from typing import Dict, List, Optional, Sequence, Tuple

from app.schemas.ontology_types import (
    Criterion,
    ExtractRubricResponse,
    Question,
    SubCriterion,
    SubQuestion,
)

GRID = Decimal("0.25")
STAMP_KEY = "rescale_to_exam"
STAMP_VERSION = "rescale_to_exam/v1 (grid-snap, largest remainder)"


# ---------------------------------------------------------------------------
# Arithmetic primitives (pure, Decimal, deterministic)
# ---------------------------------------------------------------------------

def _units(value: Decimal, grid: Decimal) -> Decimal:
    return (value / grid)


def _canon(value: Decimal) -> Decimal:
    """Canonical Decimal: no trailing zeros, no exponent (`33.50` → `33.5`, `20.00` → `20`).
    The ontology serializes points with `str()`, so the representation is part of the wire."""
    return Decimal(format(value.normalize(), "f"))


def snap_shares(total: Decimal, k: int, grid: Decimal = GRID) -> List[Decimal]:
    """Split `total` into k grid values as evenly as possible; residual on the first.

    k=3, 100 → [33.5, 33.25, 33.25]; k=4 → [25, 25, 25, 25]; k=2 → [50, 50];
    k=5 → [20, 20, 20, 20, 20]."""
    if k <= 0:
        raise ValueError("k must be positive")
    total_units = _units(total, grid)
    base_units = (total_units / k).to_integral_value(rounding=ROUND_FLOOR)
    residual_units = total_units - base_units * k
    shares = [base_units * grid for _ in range(k)]
    shares[0] += residual_units * grid
    return [_canon(s) for s in shares]


def largest_remainder(weights: Sequence[Decimal], target: Decimal, grid: Decimal = GRID) -> List[Decimal]:
    """Scale `weights` proportionally so they sum to `target`, snapped to `grid`, by the
    largest-remainder method (Hamilton). Ties → the earlier index. Σ result == target
    exactly. Zero/empty weight vectors split `target` evenly."""
    n = len(weights)
    if n == 0:
        return []
    total_w = sum(weights, Decimal("0"))
    target_units = _units(target, grid)
    if target_units != target_units.to_integral_value():
        raise ValueError(f"target {target} is not on the {grid} grid")
    if total_w <= 0:
        raw = [target_units / n] * n
    else:
        raw = [target_units * w / total_w for w in weights]
    floors = [r.to_integral_value(rounding=ROUND_FLOOR) for r in raw]
    remaining = int(target_units - sum(floors, Decimal("0")))
    order = sorted(range(n), key=lambda i: (-(raw[i] - floors[i]), i))
    out = list(floors)
    for i in order[:max(0, remaining)]:
        out[i] += 1
    return [_canon(u * grid) for u in out]


# ---------------------------------------------------------------------------
# Tree rescale
# ---------------------------------------------------------------------------

def _rescale_criteria(criteria: List[Criterion], target: Decimal, grid: Decimal) -> List[Criterion]:
    if not criteria:
        return criteria
    pts = largest_remainder([c.points for c in criteria], target, grid)
    out: List[Criterion] = []
    for c, p in zip(criteria, pts):
        subs = c.sub_criteria
        if subs:
            sub_pts = largest_remainder([s.points for s in subs], p, grid)
            subs = [s.model_copy(update={"points": sp}) for s, sp in zip(subs, sub_pts)]
        out.append(c.model_copy(update={"points": p, "sub_criteria": subs}))
    return out


def _rescale_sub_question(sq: SubQuestion, target: Decimal, grid: Decimal) -> SubQuestion:
    if sq.sub_questions:
        child_pts = largest_remainder([c.points for c in sq.sub_questions], target, grid)
        children = [_rescale_sub_question(c, p, grid) for c, p in zip(sq.sub_questions, child_pts)]
        return sq.model_copy(update={"points": target, "sub_questions": children})
    return sq.model_copy(update={"points": target,
                                 "criteria": _rescale_criteria(sq.criteria, target, grid)})


def _rescale_question(q: Question, share: Decimal, grid: Decimal) -> Question:
    if q.sub_questions:
        child_pts = largest_remainder([c.points for c in q.sub_questions], share, grid)
        children = [_rescale_sub_question(c, p, grid) for c, p in zip(q.sub_questions, child_pts)]
        return q.model_copy(update={"total_points": share, "sub_questions": children})
    return q.model_copy(update={"total_points": share,
                                "criteria": _rescale_criteria(q.criteria, share, grid)})


def question_shares(response: ExtractRubricResponse, grid: Decimal = GRID) -> Dict[str, Decimal]:
    """Question id → its share of the exam total (step (1)).

    Grouped questions share the pool (exam total − mandatory printed points); with
    several groups the pool is split evenly between groups (residual on the first),
    then within each group by `snap_shares`. Mandatory questions keep printed points.
    """
    exam_total = Decimal(str(response.total_points))
    grouped = {qid for g in response.selection_groups for qid in g.of_question_ids}
    shares: Dict[str, Decimal] = {}
    mandatory_sum = Decimal("0")
    for q in response.questions:
        if q.question_id not in grouped:
            shares[q.question_id] = q.total_points
            mandatory_sum += q.total_points
    pool = exam_total - mandatory_sum
    groups = list(response.selection_groups)
    if groups:
        group_pools = snap_shares(pool, len(groups), grid) if pool > 0 else [Decimal("0")] * len(groups)
        for g, gp in zip(groups, group_pools):
            k = g.choose_k
            pattern = snap_shares(gp, k, grid)
            for i, qid in enumerate(g.of_question_ids):
                # every member gets a share from the k-pattern: the first member the
                # residual, the rest the base — so the k largest sum to the pool exactly
                shares[qid] = pattern[0] if i == 0 else pattern[-1]
    return shares


def rescale_to_exam(response: ExtractRubricResponse, *, grid: Decimal = GRID) -> ExtractRubricResponse:
    """The post-pass. Pure; returns a new response; idempotent via the metadata stamp."""
    meta = dict(response.extraction_metadata or {})
    if meta.get(STAMP_KEY):
        return response
    shares = question_shares(response, grid)
    questions = [_rescale_question(q, shares.get(q.question_id, q.total_points), grid)
                 for q in response.questions]
    # A rubric-level mismatch annotation from extraction ("Σ questions ≠ total") is now
    # false by construction; per-node annotations (a teacher's own weights not summing
    # to 100) stay — they are her error, faithfully kept, and the teacher resolves them.
    annotations = [a for a in response.annotations
                   if not (a.annotation_type == "rubric_mismatch" and a.target_id is None)]
    meta[STAMP_KEY] = {
        "version": STAMP_VERSION,
        "grid": str(grid),
        "exam_total": str(response.total_points),
        "shares": {qid: str(s) for qid, s in shares.items()},
    }
    return response.model_copy(update={
        "questions": questions,
        "annotations": annotations,
        "extraction_metadata": meta,
    })


def max_criterion_drift(before: ExtractRubricResponse, after: ExtractRubricResponse) -> Decimal:
    """P-11b diagnostic: the largest |snapped − exact| over every criterion, where
    exact = weight × share / Σ weights of its node. Pure; for reports and tests."""
    shares = (after.extraction_metadata or {}).get(STAMP_KEY, {}).get("shares", {})
    worst = Decimal("0")

    def walk(bnode_crits, anode_crits, node_total_exact: Decimal):
        nonlocal worst
        total_w = sum((c.points for c in bnode_crits), Decimal("0"))
        for bc, ac in zip(bnode_crits, anode_crits):
            exact = (node_total_exact * bc.points / total_w) if total_w > 0 else node_total_exact / len(bnode_crits)
            worst = max(worst, abs(ac.points - exact))

    def walk_sq(bsq, asq, exact_total: Decimal):
        if bsq.sub_questions:
            total_w = sum((c.points for c in bsq.sub_questions), Decimal("0"))
            for bc, ac in zip(bsq.sub_questions, asq.sub_questions):
                walk_sq(bc, ac, exact_total * bc.points / total_w if total_w > 0 else exact_total / len(bsq.sub_questions))
        else:
            walk(bsq.criteria, asq.criteria, exact_total)

    for bq, aq in zip(before.questions, after.questions):
        share = Decimal(shares.get(bq.question_id, str(aq.total_points)))
        if bq.sub_questions:
            total_w = sum((c.points for c in bq.sub_questions), Decimal("0"))
            for bc, ac in zip(bq.sub_questions, aq.sub_questions):
                walk_sq(bc, ac, share * bc.points / total_w if total_w > 0 else share / len(bq.sub_questions))
        else:
            walk(bq.criteria, aq.criteria, share)
    return worst
