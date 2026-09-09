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
  (2) CHILDREN — every node's WRITTEN weights are mapped onto the node's exam-scale
      points, top-down through sub-questions, criteria and sub-criteria:
        * weights that ADD UP (|Σ children − written total| ≤ WRITTEN_TOLERANCE; a node
          the teacher gave no total of its own takes Σ children as that total — the
          post-pass's arithmetic, never the model's) → LARGEST REMAINDER on the grid, so
          Σ children == parent EXACTLY (INV-1/2/3 hold by construction, never by tolerance);
        * weights that DO NOT add up (the 4-unit fixture's q4.ד: steps 15+3+6+5+5 = 34
          under a written 39; a question with no marking scheme at all: every part at 0)
          → each child is scaled by the SAME factor and snapped to the nearest grid value
          INDEPENDENTLY, so her gap survives in proportion; a `rubric_mismatch` WARNING
          names the node with the exam-scale and the written numbers, and INV-1/2/3 FIRE
          at compile until she resolves it. Faithful capture, never silent repair: the
          first version of this pass reconciled every node by construction, which would
          have erased exactly that teacher error on the real fixture.
      Nothing written → nothing invented: an all-zero weight vector stays at zero.

Runs ONCE on a mathematics draft, after extraction and before the teacher sees it; other
profiles never enter it (the profile's `rescale_to_exam` flag decides, not a subject
branch). Idempotent: a draft already stamped `extraction_metadata["rescale_to_exam"]`
is returned unchanged. The teacher sees her original weight in every description and
overrides freely; the phase-gate report says exactly what was snapped (§9 item 3).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_FLOOR, ROUND_HALF_UP
from typing import Dict, List, Sequence, Tuple

from app.schemas.ontology_types import (
    Annotation,
    AnnotationSeverity,
    Criterion,
    ExtractRubricResponse,
    Question,
    SubQuestion,
)

GRID = Decimal("0.25")
STAMP_KEY = "rescale_to_exam"
STAMP_VERSION = "rescale_to_exam/v2 (grid-snap, largest remainder; written mismatches preserved)"
# "Did the teacher's written weights add up?" — the extraction validator's own pre-save
# tolerance (pipeline._SUM_TOLERANCE = 0.5), held here by value because the pipeline
# imports this module.
WRITTEN_TOLERANCE = Decimal("0.5")
# F-1: a selection-group member's weights are written on a per-question scale of 100. Its
# printed total (33⅓ on the paper, or whatever the model copied) is REPLACED by its share,
# so the per-question scale — not that total — is what its children are checked against.
GROUP_MEMBER_SCALE = Decimal("100")

_ZERO = Decimal("0")

# (node path, exam-scale expected, exam-scale actual, written declared, written Σ children)
Mismatch = Tuple[str, Decimal, Decimal, Decimal, Decimal]


# ---------------------------------------------------------------------------
# Arithmetic primitives (pure, Decimal, deterministic)
# ---------------------------------------------------------------------------

def _units(value: Decimal, grid: Decimal) -> Decimal:
    return (value / grid)


def _canon(value: Decimal) -> Decimal:
    """Canonical Decimal: no trailing zeros, no exponent (`33.50` → `33.5`, `20.00` → `20`).
    The ontology serializes points with `str()`, so the representation is part of the wire."""
    return Decimal(format(value.normalize(), "f"))


def _snap_nearest(value: Decimal, grid: Decimal) -> Decimal:
    """The nearest grid value, half up — used only where a node's children are snapped
    INDEPENDENTLY (their written weights do not add up, so Σ must not be forced)."""
    return _canon((value / grid).to_integral_value(rounding=ROUND_HALF_UP) * grid)


def snap_shares(total: Decimal, k: int, grid: Decimal = GRID) -> List[Decimal]:
    """Split `total` into k grid values as evenly as possible; residual on the first.

    k=3, 100 → [33.5, 33.25, 33.25]; k=4 → [25, 25, 25, 25]; k=2 → [50, 50];
    k=5 → [20, 20, 20, 20, 20]."""
    if k <= 0:
        raise ValueError("k must be positive")
    total_units = _units(total, grid)
    if total_units != total_units.to_integral_value():
        # Refuse rather than emit off-grid shares. Observed on the real 4-unit run: a
        # draft whose achievable total came out 33.33 produced a 11.33 share, i.e. points
        # off the precision policy's own grid. `rescale_to_exam` snaps the exam total
        # before it ever gets here, so this guard is the backstop for direct callers.
        raise ValueError(f"total {total} is not on the {grid} grid")
    base_units = (total_units / k).to_integral_value(rounding=ROUND_FLOOR)
    residual_units = total_units - base_units * k
    shares = [base_units * grid for _ in range(k)]
    shares[0] += residual_units * grid
    return [_canon(s) for s in shares]


def largest_remainder(weights: Sequence[Decimal], target: Decimal, grid: Decimal = GRID) -> List[Decimal]:
    """Scale `weights` proportionally so they sum to `target`, snapped to `grid`, by the
    largest-remainder method (Hamilton). Ties → the earlier index. Σ result == target
    exactly. An all-zero (or empty) weight vector comes back as zeros: nothing was
    written, so nothing is invented — the caller surfaces the gap."""
    n = len(weights)
    if n == 0:
        return []
    total_w = sum(weights, _ZERO)
    target_units = _units(target, grid)
    if target_units != target_units.to_integral_value():
        raise ValueError(f"target {target} is not on the {grid} grid")
    if total_w <= 0:
        return [_canon(_ZERO)] * n
    raw = [target_units * w / total_w for w in weights]
    floors = [r.to_integral_value(rounding=ROUND_FLOOR) for r in raw]
    remaining = int(target_units - sum(floors, _ZERO))
    order = sorted(range(n), key=lambda i: (-(raw[i] - floors[i]), i))
    out = list(floors)
    for i in order[:max(0, remaining)]:
        out[i] += 1
    return [_canon(u * grid) for u in out]


def split_written(
    weights: Sequence[Decimal], declared: Decimal, target: Decimal, grid: Decimal = GRID,
    alt_declared: Decimal = _ZERO,
) -> Tuple[List[Decimal], bool]:
    """Map a node's WRITTEN child weights onto the node's exam-scale `target`.

    `declared` is the node's own written weight; 0 means the teacher wrote no total for
    it, and Σ children stands in. `alt_declared` is a second scale the weights may have
    been written on (a question: F-1's per-question 100, OR its printed total when she
    wrote plain points) — consistent with either counts. Returns (points, consistent):
      * consistent (|Σ weights − declared| ≤ WRITTEN_TOLERANCE) → largest remainder,
        Σ points == target exactly;
      * inconsistent → every child scaled by the SAME factor (target / declared) and
        snapped to the nearest grid value on its own, so the written gap survives in
        proportion and the compiler's INV-1/2/3 fire on this node until the teacher
        resolves it (FC: capture the error, never repair it)."""
    n = len(weights)
    if n == 0:
        return [], True
    written_sum = sum(weights, _ZERO)
    effective = declared if declared > 0 else written_sum
    for scale in (effective, alt_declared):
        if scale > 0 and abs(written_sum - scale) <= WRITTEN_TOLERANCE:
            return largest_remainder(weights, target, grid), True
    if effective <= 0:                      # nothing written above, nothing written below
        return [_canon(_ZERO)] * n, True
    return [_snap_nearest(w * target / effective, grid) for w in weights], False


# ---------------------------------------------------------------------------
# Tree rescale
# ---------------------------------------------------------------------------

def _record(path: str, target: Decimal, pts: Sequence[Decimal],
            declared: Decimal, written: Sequence[Decimal]) -> Mismatch:
    return (path, _canon(target), _canon(sum(pts, _ZERO)),
            _canon(declared), _canon(sum(written, _ZERO)))


def _child_path(parent: str, child_id: str) -> str:
    """Anchor path for a child (`q2.א`, `q2.א.1`). Drafts built by the pipeline carry
    bare ids; drafts built by hand may already carry the full path."""
    return child_id if child_id.startswith(parent + ".") else f"{parent}.{child_id}"


def _sq_weight(sq: SubQuestion) -> Decimal:
    """A sub-question's weight in its parent's split: what the teacher wrote for it, or —
    when she wrote no total for it — the sum of what she wrote inside it."""
    if sq.points > 0:
        return sq.points
    if sq.sub_questions:
        return sum((_sq_weight(c) for c in sq.sub_questions), _ZERO)
    return sum((c.points for c in sq.criteria), _ZERO)


def _rescale_criteria(
    criteria: List[Criterion], declared: Decimal, target: Decimal, grid: Decimal,
    path: str, out: List[Mismatch],
) -> List[Criterion]:
    if not criteria:
        return criteria
    written = [c.points for c in criteria]
    pts, ok = split_written(written, declared, target, grid)
    if not ok:
        out.append(_record(path, target, pts, declared, written))
    return _rescale_criteria_with(criteria, pts, grid, out)


def _rescale_criteria_with(
    criteria: List[Criterion], pts: List[Decimal], grid: Decimal, out: List[Mismatch],
) -> List[Criterion]:
    result: List[Criterion] = []
    for c, p in zip(criteria, pts):
        subs = c.sub_criteria
        if subs:
            sub_written = [s.points for s in subs]
            sub_pts, sub_ok = split_written(sub_written, c.points, p, grid)
            if not sub_ok:
                out.append(_record(c.criterion_id, p, sub_pts, c.points, sub_written))
            subs = [s.model_copy(update={"points": sp}) for s, sp in zip(subs, sub_pts)]
        result.append(c.model_copy(update={"points": p, "sub_criteria": subs}))
    return result


def _rescale_sub_question(
    sq: SubQuestion, target: Decimal, grid: Decimal, path: str, out: List[Mismatch],
) -> SubQuestion:
    if sq.sub_questions:
        written = [_sq_weight(c) for c in sq.sub_questions]
        pts, ok = split_written(written, sq.points, target, grid)
        if not ok:
            out.append(_record(path, target, pts, sq.points, written))
        children = [
            _rescale_sub_question(c, p, grid, _child_path(path, c.sub_question_id), out)
            for c, p in zip(sq.sub_questions, pts)
        ]
        return sq.model_copy(update={"points": target, "sub_questions": children})
    return sq.model_copy(update={
        "points": target,
        "criteria": _rescale_criteria(sq.criteria, sq.points, target, grid, path, out),
    })


def _rescale_question(
    q: Question, share: Decimal, grouped: bool, grid: Decimal, out: List[Mismatch],
) -> Question:
    path = q.question_id
    # F-1: weights live on a per-question scale of 100; a teacher who wrote plain points
    # (Σ == the printed total) is consistent too. A group member's printed total is
    # replaced by its share, so only the 100 scale applies there.
    declared = GROUP_MEMBER_SCALE
    alt = _ZERO if grouped else q.total_points
    if q.sub_questions:
        written = [_sq_weight(c) for c in q.sub_questions]
        pts, ok = split_written(written, declared, share, grid, alt_declared=alt)
        if not ok:
            out.append(_record(path, share, pts, declared, written))
        children = [
            _rescale_sub_question(c, p, grid, _child_path(path, c.sub_question_id), out)
            for c, p in zip(q.sub_questions, pts)
        ]
        return q.model_copy(update={"total_points": share, "sub_questions": children})
    if q.criteria:
        written = [c.points for c in q.criteria]
        pts, ok = split_written(written, declared, share, grid, alt_declared=alt)
        if not ok:
            out.append(_record(path, share, pts, declared, written))
        criteria = _rescale_criteria_with(q.criteria, pts, grid, out)
    else:
        criteria = q.criteria
    return q.model_copy(update={"total_points": share, "criteria": criteria})


def question_shares(response: ExtractRubricResponse, grid: Decimal = GRID) -> Dict[str, Decimal]:
    """Question id → its share of the exam total (step (1)).

    Grouped questions share the pool (exam total − mandatory printed points); with
    several groups the pool is split evenly between groups (residual on the first),
    then within each group by `snap_shares`. Mandatory questions keep printed points.
    """
    exam_total = _snap_nearest(Decimal(str(response.total_points)), grid)
    grouped = {qid for g in response.selection_groups for qid in g.of_question_ids}
    shares: Dict[str, Decimal] = {}
    mandatory_sum = _ZERO
    for q in response.questions:
        if q.question_id not in grouped:
            # snapped for the same reason the exam total is: every number this pass emits
            # must sit on the precision policy's grid
            snapped = _snap_nearest(q.total_points, grid)
            shares[q.question_id] = snapped
            mandatory_sum += snapped
    pool = exam_total - mandatory_sum
    groups = list(response.selection_groups)
    if groups:
        group_pools = snap_shares(pool, len(groups), grid) if pool > 0 else [_ZERO] * len(groups)
        for g, gp in zip(groups, group_pools):
            k = g.choose_k
            pattern = snap_shares(gp, k, grid)
            for i, qid in enumerate(g.of_question_ids):
                # every member gets a share from the k-pattern: the first member the
                # residual, the rest the base — so the k largest sum to the pool exactly
                shares[qid] = pattern[0] if i == 0 else pattern[-1]
    return shares


def _mismatch_annotation(m: Mismatch) -> Annotation:
    path, expected, actual, w_declared, w_sum = m
    return Annotation(
        annotation_type="rubric_mismatch",
        severity=AnnotationSeverity.WARNING,
        target_id=path,
        message=(
            f"{path}: children sum to {actual}, but the node carries {expected} points on the "
            f"exam scale (written: {w_sum} of {w_declared}). Copied as written — not reconciled."
        ),
        message_he=(
            f"{path}: סכום הרכיבים ({actual}) שונה מהניקוד של הסעיף ({expected}); "
            f"במסמך נכתב {w_sum} מתוך {w_declared}. הועתק כפי שנכתב — לא תוקן."
        ),
        expected=str(expected),
        actual=str(actual),
    )


def rescale_to_exam(response: ExtractRubricResponse, *, grid: Decimal = GRID) -> ExtractRubricResponse:
    """The post-pass. Pure; returns a new response; idempotent via the metadata stamp."""
    meta = dict(response.extraction_metadata or {})
    if meta.get(STAMP_KEY):
        return response
    # The exam total is the denominator every share is cut from, so it must sit on the
    # grid before anything is cut. A real total (100) is already there and this is a
    # no-op; a draft that arrived with 33.33 (observed) would otherwise hand the teacher
    # points off her own precision policy. The written value is kept in the stamp and,
    # when it differs, named in a WARNING — snapped, never silently.
    written_total = Decimal(str(response.total_points))
    exam_total = _snap_nearest(written_total, grid)
    shares = question_shares(response, grid)
    grouped = {qid for g in response.selection_groups for qid in g.of_question_ids}
    mismatches: List[Mismatch] = []
    questions = [
        _rescale_question(q, shares.get(q.question_id, q.total_points),
                          q.question_id in grouped, grid, mismatches)
        for q in response.questions
    ]
    # Extraction-time `rubric_mismatch` annotations spoke the per-question scale (and the
    # rubric-level one — Σ questions ≠ total — is false by construction now). They are
    # REPLACED by the post-pass's own, on the exam scale: one per node whose written
    # weights do not add up (its written numbers are quoted in the message, so the teacher
    # recognises her own page). Every other annotation type passes through untouched.
    annotations = [a for a in response.annotations if a.annotation_type != "rubric_mismatch"]
    annotations += [_mismatch_annotation(m) for m in mismatches]
    if exam_total != written_total:
        annotations.append(Annotation(
            annotation_type="rubric_mismatch",
            severity=AnnotationSeverity.WARNING,
            target_id=None,
            message=(
                f"The exam total {written_total} is not on the {grid} grade grid; the rubric "
                f"is scored out of {exam_total}. Change the total if that is not what you meant."
            ),
            message_he=(
                f"סך הניקוד במסמך ({written_total}) אינו על סקאלת ה-{grid}; המחוון מנוקד "
                f"מתוך {exam_total}. אם זו אינה הכוונה, שני את סך הניקוד."
            ),
            expected=str(exam_total), actual=str(written_total),
        ))
    meta[STAMP_KEY] = {
        "version": STAMP_VERSION,
        "grid": str(grid),
        "exam_total": str(exam_total),
        "exam_total_written": str(written_total),
        "shares": {qid: str(s) for qid, s in shares.items()},
        # nodes the teacher must resolve before the draft compiles (INV-1/2/3 fire there)
        "unresolved": [m[0] for m in mismatches],
    }
    return response.model_copy(update={
        "total_points": exam_total,
        "questions": questions,
        "annotations": annotations,
        "extraction_metadata": meta,
    })


def _exact_shares(weights: Sequence[Decimal], declared: Decimal, target: Decimal) -> List[Decimal]:
    """The UNSNAPPED allocation the post-pass aimed at, under the branch it actually took.

    This must mirror `split_written`, or the diagnostic measures the wrong thing: on a node whose
    written weights do NOT add up, the pass scales by the DECLARED weight (preserving her gap),
    while dividing by Σ weights would fold that deliberate, flagged gap into what is supposed to be
    a rounding measurement. Measured on the real 4-unit document the difference is the whole
    finding: 0.15 (rounding) versus 0.97 (rounding + her 34-under-a-declared-39)."""
    n = len(weights)
    if n == 0:
        return []
    written_sum = sum(weights, _ZERO)
    effective = declared if declared > 0 else written_sum
    consistent = effective > 0 and abs(written_sum - effective) <= WRITTEN_TOLERANCE
    denom = written_sum if consistent else effective
    if denom <= 0:
        return [_ZERO] * n
    return [target * w / denom for w in weights]


def max_criterion_drift(before: ExtractRubricResponse, after: ExtractRubricResponse) -> Decimal:
    """P-11b: the largest |snapped − exact| over every node the post-pass allocated, where `exact`
    is the unsnapped allocation IT aimed at (see `_exact_shares`). Pure; for reports and tests.

    What this is NOT: a measure of how far the teacher's own numbers are from adding up. That gap
    is deliberate, preserved, and reported as a `rubric_mismatch` annotation per node; folding it
    in here would make a rounding bound look violated by a teacher's arithmetic."""
    worst = _ZERO

    def walk(bnode, anode, is_question: bool) -> None:
        nonlocal worst
        target = anode.total_points if is_question else anode.points
        declared = GROUP_MEMBER_SCALE if is_question else (bnode.points if bnode.points > 0 else _ZERO)
        bkids = getattr(bnode, "sub_questions", None) or []
        if bkids:
            akids = anode.sub_questions
            exact = _exact_shares([_sq_weight(c) for c in bkids], declared, target)
            for bc, ac, e in zip(bkids, akids, exact):
                worst = max(worst, abs(ac.points - e))
                walk(bc, ac, is_question=False)
            return
        bcrits = bnode.criteria
        if not bcrits:
            return
        node_declared = declared if is_question else (bnode.points if bnode.points > 0 else _ZERO)
        exact = _exact_shares([c.points for c in bcrits], node_declared, target)
        for bc, ac, e in zip(bcrits, anode.criteria, exact):
            worst = max(worst, abs(ac.points - e))

    for bq, aq in zip(before.questions, after.questions):
        walk(bq, aq, is_question=True)
    return worst
