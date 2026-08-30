"""
The rubric scorer: aligns a predicted ExtractRubricResponse against a GT
ExtractRubricResponse and produces a RubricScore.

Design pillars (locked):
  - Pred-vs-GT FIDELITY, not rubric-internal consistency. A faithfully reproduced
    teacher error PASSES (scored via annotation_match); 'fixing' it FAILS. So
    point_sum_consistency is reported as health, never gated.
  - Criterion matching is DESCRIPTION-PRIMARY (deviation from the B2 lock, flagged):
    a criterion is matched on description similarity >= tau; points then feed
    point_exactness. Requiring points-exact as a MATCH key would double-penalize a
    pure point error as recall+precision loss AND misattribute it. Matching on
    description and scoring points separately keeps the signals orthogonal. (Make
    this a config flag if you want the strict variant.)
  - Attribution: every MISSED GT criterion is classified render_loss vs
    extraction_loss from the rendered markdown — the p1/p2 split from one GT.
  - Ids and index are IGNORED in matching (the pipeline generates them; they shift
    when structure differs). Criteria match by description+points; sub-questions by
    harmonized label.

Pure module: imports only the ontology types + normalize + schemas + stdlib.
No pipeline import, so it is importable and testable without OpenAI/langchain.
"""
from __future__ import annotations

import re as _re
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

from app.schemas.ontology_types import (
    Criterion,
    ExtractRubricResponse,
    Question,
    SubCriterion,
    SubQuestion,
    compute_achievable_points,
)

from . import normalize as nz
from .schemas import (
    AnnotationCheck,
    CriterionMatchRecord,
    RubricScore,
    ScopeScore,
)

# ---- tunables (locked values; see RUBRIC_EVAL_PLAYBOOK.md) -------------------
TEXT_TAU = 0.85          # description / text fidelity match threshold
ATTRIB_TAU = 0.70        # render token-overlap threshold for attribution
MERGE_LOW = 0.55         # >= this (but < TEXT_TAU) on a missed GT criterion vs some
                         # predicted criterion => flag 'merge suspected'
POINT_EPS = Decimal("0")  # exact point matching (discrete 0.25 increments)
LINE_TAU = 0.85          # per-line match threshold for text_line_recall.
                         # PROVISIONAL/DIAGNOSTIC: not calibrated from any measured
                         # distribution; the gate threshold (if text is ever gated)
                         # is to be pre-registered from measured data, never guessed.


def _pts_eq(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= POINT_EPS


def _text_fidelity(pred: Optional[str], gt: Optional[str]) -> Optional[float]:
    """Question/sub-question text fidelity with explicit null semantics.

    GT text null   => None (comparison undefined: null means 'no task prose in
                     the document', which is not-comparable, never a zero wall).
    GT text present, predicted null => 0.0 (a real miss).
    Both present   => normalized similarity ratio.
    """
    if not nz.norm_text(gt):
        return None
    if not nz.norm_text(pred):
        return 0.0
    return round(nz.ratio(pred, gt), 4)


def _text_line_recall(pred: Optional[str], gt: Optional[str]) -> Optional[float]:
    """Fraction of GT text lines (normalized, non-empty) having >= 1 predicted
    line with ratio >= LINE_TAU. Same null semantics as _text_fidelity.

    Why a second number: `ratio` is length-weighted, so a silently dropped
    constraint line in a 1,500-char spec still scores ~0.93 — the doc-ratio
    blindspot documented in the transcription suite (its §4). Line recall is
    the omission detector; ratio is the fidelity detector. Two numbers, two
    failure classes.
    """
    gt_lines = [ln for ln in (gt or "").split("\n") if nz.norm_text(ln)]
    if not gt_lines:
        return None
    pred_lines = [ln for ln in (pred or "").split("\n") if nz.norm_text(ln)]
    if not pred_lines:
        return 0.0
    hits = sum(1 for g in gt_lines if any(nz.ratio(p, g) >= LINE_TAU for p in pred_lines))
    return round(hits / len(gt_lines), 4)


def _is_branch(node) -> bool:
    return bool(getattr(node, "sub_questions", None))


def _has_criteria(node) -> bool:
    return bool(getattr(node, "criteria", None))


# =============================================================================
# CRITERION ALIGNMENT (greedy, description-primary)
# =============================================================================

def _align_criteria(
    pred: List[Criterion],
    gt: List[Criterion],
    render_tokens,
) -> Tuple[List[CriterionMatchRecord], int, int]:
    """
    Greedy max-similarity matching. Returns (records, n_matched, n_gt).

    records contains one entry per matched pair, per missed GT criterion (with
    attribution), and per spurious predicted criterion.
    """
    pairs: List[Tuple[float, float, int, int]] = []
    for i, gc in enumerate(gt):
        for j, pc in enumerate(pred):
            r = nz.ratio(pc.description, gc.description)
            if r >= TEXT_TAU:
                # rank by ratio desc, then by point closeness (smaller gap first)
                gap = float(abs(pc.points - gc.points))
                pairs.append((r, -gap, i, j))
    pairs.sort(reverse=True)

    gt_used, pred_used = set(), set()
    records: List[CriterionMatchRecord] = []
    for r, _neg_gap, i, j in pairs:
        if i in gt_used or j in pred_used:
            continue
        gt_used.add(i)
        pred_used.add(j)
        gc, pc = gt[i], pred[j]
        records.append(CriterionMatchRecord(
            status="matched",
            gt_description=gc.description,
            pred_description=pc.description,
            gt_points=str(gc.points),
            pred_points=str(pc.points),
            text_ratio=round(r, 4),
            points_exact=_pts_eq(pc.points, gc.points),
        ))

    # missed GT criteria (recall) + attribution + merge heuristic
    for i, gc in enumerate(gt):
        if i in gt_used:
            continue
        merge = any(
            MERGE_LOW <= nz.ratio(pc.description, gc.description) < TEXT_TAU
            for pc in pred
        )
        attribution = (
            "extraction_loss"
            if nz.present_in_render(gc.description, render_tokens, ATTRIB_TAU)
            else "render_loss"
        )
        records.append(CriterionMatchRecord(
            status="missed",
            gt_description=gc.description,
            gt_points=str(gc.points),
            attribution=attribution,
            merge_suspected=merge,
        ))

    # spurious predicted criteria (precision / hallucination guard)
    for j, pc in enumerate(pred):
        if j in pred_used:
            continue
        records.append(CriterionMatchRecord(
            status="spurious",
            pred_description=pc.description,
            pred_points=str(pc.points),
        ))

    return records, len(gt_used), len(gt)


def _align_subcriteria(
    pred: Optional[List[SubCriterion]],
    gt: Optional[List[SubCriterion]],
    render_tokens,
) -> Tuple[List[CriterionMatchRecord], int, int]:
    p = list(pred or [])
    g = list(gt or [])
    # reuse the criterion aligner shape via duck-typed .description/.points
    return _align_criteria(p, g, render_tokens)  # type: ignore[arg-type]


# =============================================================================
# SUB-QUESTION TREE ALIGNMENT
# =============================================================================

def _index_children(nodes: List[SubQuestion]) -> Dict[Tuple[str, object], SubQuestion]:
    """Map each child to its harmonized label key for within-parent matching."""
    out: Dict[Tuple[str, object], SubQuestion] = {}
    for sq in nodes:
        out[nz.canon_subq_label(sq.sub_question_id)] = sq
    return out


def _walk_tree(
    pred_node,
    gt_node,
    scope_id: str,
    render_tokens,
    out: Dict[str, list],
):
    """
    Recursively align the sub-question subtree under a matched node.

    Accumulates into `out`:
      out['scopes']            : List[ScopeScore]
      out['crit_records']      : List[CriterionMatchRecord]
      out['sub_records']       : List[CriterionMatchRecord]
      out['struct_total']      : int  (# GT sub-question nodes seen)
      out['struct_total_pred'] : int  (# predicted sub-question nodes seen)
      out['struct_correct']    : int  (# GT nodes correctly present w/ matching kind)
      out['sol_total']/['sol_ok'] : example-solution fidelity tallies
      out['point_nodes']/['point_ok'] : point exactness tallies (all node levels)
    """
    gt_children = list(getattr(gt_node, "sub_questions", []) or [])
    pred_children = list(getattr(pred_node, "sub_questions", []) or [])
    out["struct_total"] += len(gt_children)
    out["struct_total_pred"] += len(pred_children)

    pred_idx = _index_children(pred_children)
    gt_idx = _index_children(gt_children)

    for key, gsq in gt_idx.items():
        kind = "sub_sub_question" if scope_id.count(".") >= 1 else "sub_question"
        child_scope = f"{scope_id}.{gsq.sub_question_id}"
        psq = pred_idx.get(key)
        if psq is None:
            out["scopes"].append(ScopeScore(
                scope_id=child_scope, kind=kind, structure_status="missing",
                # a missing node's predicted text is null: 0.0 when GT has text
                # (a real miss), None when GT has none (not-comparable)
                text_ratio=_text_fidelity(None, gsq.text),
                text_line_recall=_text_line_recall(None, gsq.text),
                points_gt=str(gsq.points),
            ))
            # missing node => its GT criteria are all missed (recall + attribution)
            recs, _m, _t = _align_criteria(list(gsq.criteria or []), list(gsq.all_criteria), render_tokens) \
                if False else _align_criteria([], list(gsq.all_criteria), render_tokens)
            out["crit_records"].extend(recs)
            continue

        # leaf-vs-branch classification (FP2 signal)
        gt_branch, pred_branch = _is_branch(gsq), _is_branch(psq)
        if gt_branch != pred_branch:
            status = "leaf_vs_branch"
        else:
            status = "ok"
            out["struct_correct"] += 1

        # points at this node
        p_exact = _pts_eq(psq.points, gsq.points)
        out["point_nodes"] += 1
        out["point_ok"] += int(p_exact)

        # example solution fidelity at this node (gate-blocking)
        sol_status, sol_ratio = _score_solution(psq.example_solution, gsq.example_solution, out)

        out["scopes"].append(ScopeScore(
            scope_id=child_scope, kind=kind, structure_status=status,
            text_ratio=_text_fidelity(psq.text, gsq.text),
            text_line_recall=_text_line_recall(psq.text, gsq.text),
            points_gt=str(gsq.points), points_pred=str(psq.points), points_exact=p_exact,
            solution_status=sol_status, solution_ratio=sol_ratio,
            criterion_matches=[],
        ))

        if gt_branch and pred_branch:
            _walk_tree(psq, gsq, child_scope, render_tokens, out)
        elif (not gt_branch) and (not pred_branch):
            recs, _m, _t = _align_criteria(list(psq.criteria or []), list(gsq.criteria or []), render_tokens)
            out["crit_records"].extend(recs)
            out["scopes"][-1].criterion_matches = recs
            # sub-criteria within matched criteria
            _score_matched_subcriteria(recs, psq, gsq, render_tokens, out)
        else:
            # kind mismatch: score the GT side's criteria as all missed
            recs, _m, _t = _align_criteria([], list(gsq.all_criteria), render_tokens)
            out["crit_records"].extend(recs)
            out["scopes"][-1].criterion_matches = recs

    # extra predicted sub-questions (precision on structure)
    for key, psq in pred_idx.items():
        if key not in gt_idx:
            out["scopes"].append(ScopeScore(
                scope_id=f"{scope_id}.{psq.sub_question_id}", kind="sub_question",
                structure_status="extra", points_pred=str(psq.points),
            ))
            # spurious predicted criteria under an invented node
            recs, _m, _t = _align_criteria(list(psq.all_criteria), [], render_tokens)
            out["crit_records"].extend(recs)


def _score_matched_subcriteria(crit_records, pred_node, gt_node, render_tokens, out):
    """For each matched criterion at a leaf scope, align its sub-criteria."""
    # pair matched criteria back to their objects by (description, points)
    pred_by_key = {(nz.norm_text(c.description), str(c.points)): c for c in (pred_node.criteria or [])}
    gt_by_key = {(nz.norm_text(c.description), str(c.points)): c for c in (gt_node.criteria or [])}
    for rec in crit_records:
        if rec.status != "matched":
            continue
        pc = pred_by_key.get((nz.norm_text(rec.pred_description), rec.pred_points))
        gc = gt_by_key.get((nz.norm_text(rec.gt_description), rec.gt_points))
        if pc is None or gc is None:
            continue
        sub_recs, _m, _t = _align_subcriteria(pc.sub_criteria, gc.sub_criteria, render_tokens)
        out["sub_records"].extend(sub_recs)


def _score_solution(pred_sol: Optional[str], gt_sol: Optional[str], out) -> Tuple[str, Optional[float]]:
    """
    Example-solution fidelity at one node. Gate-blocking.

    GT has solution  -> pred must have it with ratio >= TEXT_TAU   ('ok' else 'missing')
    GT has none      -> pred must have none                        ('ok' else 'spurious')
    """
    gt_has = bool(nz.norm_text(gt_sol))
    pred_has = bool(nz.norm_text(pred_sol))
    if not gt_has:
        if pred_has:
            out["sol_total"] += 1  # spurious counts against fidelity
            return "spurious", None
        return "na", None
    out["sol_total"] += 1
    r = nz.ratio(pred_sol, gt_sol)
    if pred_has and r >= TEXT_TAU:
        out["sol_ok"] += 1
        return "ok", round(r, 4)
    return "missing", round(r, 4) if pred_has else None


# =============================================================================
# CONSISTENCY (health, recursive) — NOT gated
# =============================================================================

def _check_consistency(node, scope_id: str, violations: List[str]):
    """Σ children.points == node.points at every node (INV-PS), reported only."""
    declared = getattr(node, "total_points", None)
    if declared is None:
        declared = getattr(node, "points", None)
    if _is_branch(node):
        s = sum((sq.points for sq in node.sub_questions), Decimal("0"))
        if declared is not None and abs(s - declared) > Decimal("0.01"):
            violations.append(f"{scope_id}: children sum {s} != node {declared}")
        for sq in node.sub_questions:
            _check_consistency(sq, f"{scope_id}.{sq.sub_question_id}", violations)
    elif _has_criteria(node):
        s = sum((c.points for c in node.criteria), Decimal("0"))
        if declared is not None and abs(s - declared) > Decimal("0.01"):
            violations.append(f"{scope_id}: criteria sum {s} != node {declared}")
        for c in node.criteria:
            if c.sub_criteria:
                ss = sum((x.points for x in c.sub_criteria), Decimal("0"))
                if abs(ss - c.points) > Decimal("0.01"):
                    violations.append(f"{scope_id}/{c.criterion_id}: sub sum {ss} != {c.points}")


# =============================================================================
# TOP-LEVEL SCORER
# =============================================================================


# -----------------------------------------------------------------------------
# FIX-EFFECT CHECK - "a proposed fix must leave the rubric adding up"
# -----------------------------------------------------------------------------
# WHY THIS EXISTS (2026-08-24): pedagogical_match set-compares mistakes by
# (kind, canonical target) ONLY, so a fix PAYLOAD could be wrong or incomplete and
# the fixture still passed. That blind spot survived a full 9-cell model sweep and
# was found by the owner running a rubric through the LIVE app: the model proposed
# "move the 16-point criterion to sub-question 3" and omitted the source-side
# set_points, so accepting it left the source declaring 45 against 29 of criteria
# and the question at 76 against a declared 60. The teacher accepts a proposed fix
# and lands somewhere WORSE than before she clicked.
#
# WHAT IS CHECKED: the EFFECT, never the syntax. Step ORDER legitimately varies
# between draws of one config, `description` is free prose, and `move_text.text` is
# a long verbatim quote - none of them are comparable. What IS comparable is the
# arithmetic: apply the steps' point semantics, then require every touched scope
# (and its ancestors) to add up.
#
# THE SEMANTICS BELOW MIRROR THE ONLY REAL APPLIER, frontend/src/utils/edit-steps.ts:
#   R1 set_points WITH criterion_index -> set that criterion, then cascade living
#      sums (leaf = sum of criteria, parent = sum of children).   [applySetPoints]
#   R2 set_points WITHOUT criterion_index -> set that scope's declared, no cascade.
#   R3 move_criterion -> remove+append the SAME criterion; NEITHER side's declared
#      points move. This asymmetry is the whole defect class. [applyMoveCriterion]
#   R4 post-pass: a target VIVIFIED by this fix (absent from the ORIGINAL tree) that
#      received criteria and no explicit set_points ends at the sum of what arrived.
#   R5 set_points scope="rubric" -> the rubric total; contractually the only step.
#   R6 post-pass (2026-08-24): a move SOURCE that was CONSISTENT before the move,
#      and is not left empty by it, ends at the sum of what REMAINS -- the
#      symmetric half of R4. Guards: a source already carrying the teacher's own
#      discrepancy is left alone (rewriting it would be silent repair), and an
#      emptied source is left alone (0 is a number she never wrote).
# They are cross-pinned against that file by tests/fixtures/edit_step_points_cases.json,
# read IN PLACE by BOTH this suite and frontend/src/utils/edit-steps.test.ts - the
# selection_expectation_cases.json precedent. If the applier ever starts repairing the
# SOURCE too (a live proposal), those vectors fail loudly here instead of this check
# silently demanding a step the app no longer needs.


class _FxNode:
    """Mutable points-only mirror of a question / sub-question."""
    __slots__ = ("nid", "declared", "criteria", "children", "is_question")

    def __init__(self, nid, declared, criteria, children, is_question=False):
        self.nid = nid
        self.declared = declared          # Decimal | None
        self.criteria = criteria          # List[Decimal]
        self.children = children          # List[_FxNode]
        self.is_question = is_question


def _fx_dec(v) -> Optional[Decimal]:
    if v is None:
        return None
    try:
        return Decimal(str(v))
    except Exception:
        return None


def _fx_build(predicted) -> List["_FxNode"]:
    def sub(sq) -> "_FxNode":
        return _FxNode(
            str(getattr(sq, "sub_question_id", "") or ""),
            _fx_dec(getattr(sq, "points", None)),
            [_fx_dec(getattr(c, "points", None)) or Decimal(0)
             for c in (getattr(sq, "criteria", None) or [])],
            [sub(k) for k in (getattr(sq, "sub_questions", None) or [])],
        )
    return [
        _FxNode(
            str(getattr(q, "question_id", "") or ""),
            _fx_dec(getattr(q, "total_points", None)),
            [_fx_dec(getattr(c, "points", None)) or Decimal(0)
             for c in (getattr(q, "criteria", None) or [])],
            [sub(sq) for sq in (getattr(q, "sub_questions", None) or [])],
            is_question=True,
        )
        for q in (getattr(predicted, "questions", None) or [])
    ]


def _fx_norm_qid(s: str) -> str:
    return (s or "").strip().lstrip("qQ")


def _fx_resolve(roots: List["_FxNode"], scope: str) -> Optional[List["_FxNode"]]:
    """Return the chain [question, ...subs] for a dotted scope, or None."""
    parts = [p for p in (scope or "").split(".") if p]
    if not parts:
        return None
    q = next((r for r in roots if _fx_norm_qid(r.nid) == _fx_norm_qid(parts[0])), None)
    if q is None:
        return None
    chain = [q]
    node = q
    for seg in parts[1:]:
        nxt = next((c for c in node.children if c.nid == seg), None)
        if nxt is None:
            return None
        chain.append(nxt)
        node = nxt
    return chain


def _fx_vivify(roots: List["_FxNode"], scope: str) -> Optional[List["_FxNode"]]:
    """Mirror resolveOrVivify: create ONLY the last segment, under an existing parent."""
    got = _fx_resolve(roots, scope)
    if got:
        return got
    parts = [p for p in (scope or "").split(".") if p]
    if len(parts) < 2:
        return None                      # a question is never vivified
    parent = _fx_resolve(roots, ".".join(parts[:-1]))
    if parent is None:
        return None
    fresh = _FxNode(parts[-1], Decimal(0), [], [])
    parent[-1].children.append(fresh)
    return parent + [fresh]


def _fx_cascade(node: "_FxNode") -> None:
    """recalculateParentsFromCriteria: leaf = sum criteria, parent = sum children.
    A QUESTION's declared total is never auto-touched (the codec's standing rule)."""
    for ch in node.children:
        _fx_cascade(ch)
    if node.is_question:
        return
    node.declared = (sum((c.declared or Decimal(0)) for c in node.children)
                     if node.children else sum(node.criteria))


def _fx_sum_children(n: "_FxNode") -> Optional[Decimal]:
    if n.children:
        if any(c.declared is None for c in n.children):
            return None
        return sum(c.declared for c in n.children)
    return sum(n.criteria) if n.criteria else None


def fx_simulate(predicted, steps, *, repair_source: bool = True):
    """Apply a fix's POINT semantics to a fresh tree and return (roots, touched,
    rubric_total, problems). THE one implementation of the semantics — both
    fix_effect_check and its tests observe this rather than re-deriving it, so a
    test can never accidentally pin a different applier than the check uses.

    repair_source=False disables R6 only, which is how fix_plan_complete asks
    "would this plan have reconciled WITHOUT the app compensating for it?".
    """
    roots = _fx_build(predicted)
    pristine = _fx_build(predicted)          # the ORIGINAL tree, for before-checks
    problems: List[str] = []
    touched, rubric_total, moved_from = set(), None, set()
    original_scopes = {sc for st in steps
                       for sc in (getattr(st, "scope", None), getattr(st, "to_scope", None))
                       if sc and sc != "rubric" and _fx_resolve(roots, sc)}

    for st in steps:
        op = getattr(st, "op", None)
        scope = getattr(st, "scope", None)
        to_scope = getattr(st, "to_scope", None)
        val = _fx_dec(getattr(st, "value", None))
        ci = getattr(st, "criterion_index", None)

        if op == "set_points" and scope == "rubric":                       # R5
            if len(steps) != 1:
                problems.append("set_points@rubric is not the only step")
                break
            rubric_total = val
            continue
        if op == "move_text":                                              # no points effect
            if to_scope:
                if _fx_vivify(roots, to_scope) is None:
                    problems.append(f"move_text target {to_scope!r} unresolvable")
                    break
                touched.add(to_scope)
            continue

        chain = _fx_resolve(roots, scope) if scope else None
        if chain is None:
            problems.append(f"{op} scope {scope!r} unresolvable")
            break
        node = chain[-1]
        touched.add(scope)

        if op == "set_points":
            if val is None:
                problems.append(f"set_points@{scope} has no value")
                break
            if ci is not None:                                             # R1
                if ci >= len(node.criteria):
                    problems.append(f"set_points@{scope} criterion_index {ci} out of range")
                    break
                node.criteria[ci] = val
                for r in roots:
                    _fx_cascade(r)
            else:                                                          # R2
                node.declared = val
        elif op == "move_criterion":                                       # R3
            if ci is None or ci >= len(node.criteria) or not to_scope:
                problems.append(f"move_criterion@{scope} index {ci} invalid")
                break
            dest = _fx_vivify(roots, to_scope)
            if dest is None:
                problems.append(f"move_criterion target {to_scope!r} unresolvable")
                break
            dest[-1].criteria.append(node.criteria.pop(ci))
            touched.add(to_scope)
            moved_from.add(scope)
        else:
            problems.append(f"unknown op {op!r}")
            break

    if problems:
        return roots, touched, rubric_total, problems

    explicit = {getattr(st, "scope", None) for st in steps
                if getattr(st, "op", None) == "set_points"
                and getattr(st, "criterion_index", None) is None}

    for sc in sorted(touched):                                             # R4 vivified TARGET
        if sc in explicit or sc in original_scopes:
            continue
        ch = _fx_resolve(roots, sc)
        if ch and len(ch) > 1:
            total = sum(ch[-1].criteria)
            if total > 0:
                ch[-1].declared = total

    if repair_source:                                                      # R6 move SOURCE
        for sc in sorted(moved_from):
            if sc in explicit:
                continue
            before = _fx_resolve(pristine, sc)
            if not before or len(before) < 2:                # question totals never auto-touched
                continue
            bnode = before[-1]
            if bnode.declared is None or bnode.declared != sum(bnode.criteria):
                continue                                     # guard 1: her discrepancy stays hers
            ch = _fx_resolve(roots, sc)
            if not ch or not ch[-1].criteria:
                continue                                     # guard 2: emptied => leave alone
            ch[-1].declared = sum(ch[-1].criteria)

    return roots, touched, rubric_total, problems


def fix_effect_check(predicted, *, repair_source: bool = True) -> Tuple[Optional[bool], List[str]]:
    """(consistent, violations). None = VACUOUS: no mistake carried a suggested_fix,
    so the criterion is skipped exactly as the cost check is when cost_usd is None."""
    mistakes = list(getattr(predicted, "pedagogical_mistakes", None) or [])
    pairs = [(m, getattr(m, "suggested_fix", None)) for m in mistakes]
    pairs = [(m, f) for m, f in pairs if f is not None and (getattr(f, "steps", None) or [])]
    if not pairs:
        return None, []

    violations: List[str] = []
    for m, fix in pairs:
        mid = getattr(m, "mistake_id", None) or getattr(m, "kind", "?")
        mid = getattr(mid, "value", mid)
        steps = list(getattr(fix, "steps", None) or [])
        roots, touched, rubric_total, problems = fx_simulate(
            predicted, steps, repair_source=repair_source)
        if problems:
            violations.extend(f"{mid}: {p}" for p in problems)
            continue

        # OPTION A (owner ruling 2026-08-24) — JUDGE A FIX BY WHAT IT CLAIMS.
        # A move-bearing plan claims ROOT-CAUSE resolution ("one fix settles all
        # shadows", Tier-B prompt principle 3): its promise includes the ancestors,
        # so they are checked. A pure set_points plan is a MINIMAL, LOCAL correction
        # -- Tier A's deterministic fallback, whose whole contract is that it
        # "INVENTS NOTHING" (_adjust_points_fix) -- and it never claimed to settle
        # anything above the node it targets. Holding it to ancestors punishes a
        # promise it did not make, and would demand it write a number the teacher
        # never wrote, which is the one thing FC forbids.
        # Discriminating on the STEPS, not on suggested_fix.operation: that label is
        # derived from exactly this predicate upstream and is documented as analytics
        # metadata the client never dispatches on. The steps are what get applied.
        structural = any(getattr(st, "op", None) in ("move_criterion", "move_text")
                         for st in steps)

        checked = set()
        for sc in sorted(touched):
            chain = _fx_resolve(roots, sc)
            if not chain:
                continue
            # structural => the scope AND its ancestors; local => only the node it targeted
            for node in (chain if structural else chain[-1:]):
                key = id(node)
                if key in checked:
                    continue
                checked.add(key)
                exp = _fx_sum_children(node)
                if exp is None or node.declared is None:
                    continue
                if node.declared != exp:
                    kind = "question" if node.is_question else "sub-question"
                    violations.append(
                        "{}: after the fix, {} {!r} declares {} but its {} sum to {}".format(
                            mid, kind, node.nid, node.declared,
                            "children" if node.children else "criteria", exp))
        if rubric_total is not None:
            tot = sum((r.declared for r in roots if r.declared is not None), Decimal(0))
            if rubric_total != tot:
                violations.append(
                    "{}: after the fix, rubric declares {} but questions sum to {}".format(
                        mid, rubric_total, tot))

    return (len(violations) == 0), violations


def score_rubric(
    predicted: Optional[ExtractRubricResponse],
    gt: ExtractRubricResponse,
    rendered_markdown: str,
    *,
    meta: Optional[dict] = None,
) -> RubricScore:
    meta = meta or {}
    rs = RubricScore(rubric_name=gt.rubric_name or meta.get("rubric_name", "unknown"),
                     valid=True)
    rs.cost_usd = meta.get("cost_usd")
    rs.llm_seconds = meta.get("llm_seconds")
    rs.retry_count = meta.get("retry_count")
    rs.finish_reason = meta.get("finish_reason")
    rs.model_version = meta.get("model_version")
    rs.prompt_version = meta.get("prompt_version")
    rs.repeat_index = meta.get("repeat_index", 0)
    rs.warnings = list(meta.get("warnings") or [])
    rs.errors = list(meta.get("errors") or [])

    # validity gate (validity before significance)
    if predicted is None:
        rs.valid = False
        rs.invalid_reason = meta.get("invalid_reason", "no predicted rubric (parse/transport failure)")
        return rs
    if rs.finish_reason and rs.finish_reason.upper() in {"MAX_TOKENS", "LENGTH"}:
        rs.valid = False
        rs.invalid_reason = f"truncated (finish_reason={rs.finish_reason})"
        return rs

    render_tokens = nz.render_token_set(rendered_markdown)

    # ---- questions: match by canonical question key (robust to id convention) ----
    pred_q = {nz.canon_q(q.question_id): q for q in predicted.questions}
    gt_q = {nz.canon_q(q.question_id): q for q in gt.questions}
    matched_qids = [qid for qid in gt_q if qid in pred_q]
    rs.question_recall = len(matched_qids) / len(gt_q) if gt_q else 1.0
    rs.question_precision = len(matched_qids) / len(pred_q) if pred_q else 1.0

    acc = {
        "scopes": [], "crit_records": [], "sub_records": [],
        "struct_total": 0, "struct_total_pred": 0, "struct_correct": 0,
        "sol_total": 0, "sol_ok": 0, "point_nodes": 0, "point_ok": 0,
    }

    total_points_ok = (_pts_eq(predicted.total_points, gt.total_points))
    rs.rubric_total_gt = str(gt.total_points)
    rs.rubric_total_pred = str(predicted.total_points)

    for qkey in matched_qids:
        pq, gq = pred_q[qkey], gt_q[qkey]
        qid = gq.question_id  # human-readable scope id for the report
        # question-level points
        q_exact = _pts_eq(pq.total_points, gq.total_points)
        acc["point_nodes"] += 1
        acc["point_ok"] += int(q_exact)
        total_points_ok = total_points_ok and q_exact
        # question-level example solution
        sol_status, sol_ratio = _score_solution(pq.example_solution, gq.example_solution, acc)
        acc["scopes"].append(ScopeScore(
            scope_id=qid, kind="question",
            structure_status=("ok" if _is_branch(pq) == _is_branch(gq) else "leaf_vs_branch"),
            text_ratio=_text_fidelity(pq.question_text, gq.question_text),
            text_line_recall=_text_line_recall(pq.question_text, gq.question_text),
            points_gt=str(gq.total_points), points_pred=str(pq.total_points), points_exact=q_exact,
            solution_status=sol_status, solution_ratio=sol_ratio,
        ))

        if _is_branch(gq) and _is_branch(pq):
            _walk_tree(pq, gq, qid, render_tokens, acc)
        elif (not _is_branch(gq)) and (not _is_branch(pq)):
            recs, _m, _t = _align_criteria(list(pq.criteria or []), list(gq.criteria or []), render_tokens)
            acc["crit_records"].extend(recs)
            acc["scopes"][-1].criterion_matches = recs
            _score_matched_subcriteria(recs, pq, gq, render_tokens, acc)
        else:
            # question kind mismatch (e.g. GT nested, pred flat) -> GT criteria all missed
            recs, _m, _t = _align_criteria(list(pq.all_criteria), list(gq.all_criteria), render_tokens)
            acc["crit_records"].extend(recs)
            acc["scopes"][-1].criterion_matches = recs

    # ---- structure match ---------------------------------------------------
    denom = max(acc["struct_total"], acc["struct_total_pred"])
    rs.subquestion_structure_match = (acc["struct_correct"] / denom) if denom else 1.0

    # ---- text fidelity (UNGATED diagnostic; NOT a gate_pass criterion) -----
    # Worst-node over nodes WITH GT text (a scope's text_ratio is non-None
    # exactly when GT text exists there — mean is forbidden, worst-node is the
    # headline discipline). None when the fixture has no GT text at a level.
    q_ratios = [s.text_ratio for s in acc["scopes"]
                if s.kind == "question" and s.text_ratio is not None]
    sq_ratios = [s.text_ratio for s in acc["scopes"]
                 if s.kind != "question" and s.text_ratio is not None]
    recalls = [s.text_line_recall for s in acc["scopes"] if s.text_line_recall is not None]
    rs.question_text_fidelity_min = min(q_ratios) if q_ratios else None
    rs.subquestion_text_fidelity_min = min(sq_ratios) if sq_ratios else None
    rs.text_line_recall_min = min(recalls) if recalls else None

    # ---- criterion recall/precision ----------------------------------------
    cr = acc["crit_records"]
    c_matched = sum(1 for r in cr if r.status == "matched")
    c_missed = sum(1 for r in cr if r.status == "missed")
    c_spurious = sum(1 for r in cr if r.status == "spurious")
    rs.criterion_recall = c_matched / (c_matched + c_missed) if (c_matched + c_missed) else 1.0
    rs.criterion_precision = c_matched / (c_matched + c_spurious) if (c_matched + c_spurious) else 1.0

    sr = acc["sub_records"]
    s_matched = sum(1 for r in sr if r.status == "matched")
    s_missed = sum(1 for r in sr if r.status == "missed")
    s_spurious = sum(1 for r in sr if r.status == "spurious")
    rs.subcriterion_recall = s_matched / (s_matched + s_missed) if (s_matched + s_missed) else 1.0
    rs.subcriterion_precision = s_matched / (s_matched + s_spurious) if (s_matched + s_spurious) else 1.0

    # ---- points ------------------------------------------------------------
    # fold every MATCHED criterion + sub-criterion's point exactness into the tally
    # (question and sub-question levels were tallied inline during the walk)
    for r in acc["crit_records"] + acc["sub_records"]:
        if r.status == "matched":
            acc["point_nodes"] += 1
            acc["point_ok"] += int(bool(r.points_exact))
    rs.point_exactness = (acc["point_ok"] / acc["point_nodes"]) if acc["point_nodes"] else 1.0

    # ---- selection (FP1) ---------------------------------------------------
    def _sel_key(groups):
        return {(g.choose_k, frozenset(nz.canon_q(q) for q in g.of_question_ids)) for g in groups}
    rs.selection_match = _sel_key(predicted.selection_groups) == _sel_key(gt.selection_groups)
    ach_pred = compute_achievable_points(predicted.questions, predicted.selection_groups)
    ach_gt = compute_achievable_points(gt.questions, gt.selection_groups)
    rs.achievable_points_pred = str(ach_pred)
    rs.achievable_points_gt = str(ach_gt)
    rs.achievable_points_correct = _pts_eq(ach_pred, ach_gt)
    rs.total_points_correct = total_points_ok and rs.achievable_points_correct

    # ---- example solution fidelity (gate-blocking) -------------------------
    rs.example_solution_fidelity = (acc["sol_ok"] / acc["sol_total"]) if acc["sol_total"] else 1.0

    # ---- annotations (faithful-teacher-error) ------------------------------
    def _ann_keys(r):
        return {(a.annotation_type, a.target_id) for a in r.annotations
                if a.annotation_type == "rubric_mismatch"}
    exp, got = _ann_keys(gt), _ann_keys(predicted)
    rs.expected_annotations = [AnnotationCheck(t, tid) for (t, tid) in sorted(exp, key=lambda x: str(x))]
    rs.missing_annotations = [AnnotationCheck(t, tid) for (t, tid) in sorted(exp - got, key=lambda x: str(x))]
    rs.spurious_annotations = [AnnotationCheck(t, tid) for (t, tid) in sorted(got - exp, key=lambda x: str(x))]
    rs.annotation_match = (not rs.missing_annotations) and (not rs.spurious_annotations)

    # ---- pedagogical mistakes (Step 2c falsifier) ---------------------------
    # Same set-comparison as annotations: {(kind, canonical_target)}. Target
    # canonicalization applies canon_q ONLY to pure question ids ('q2'/'2'/'שאלה 2'
    # all -> '2'); criterion-style ids pass through verbatim — canon_q concatenates
    # digits ('q1_sq_a_c2' -> 12) and would collide them. GTs with zero mistakes are
    # the detector's false-positive guard: predicting any mistake there fails.
    _pure_q = _re.compile(r"^(?:q|question[_ ]?|שאלה\s*)?\d+$")

    def _pm_target(tid) -> str:
        if not tid:
            return ""
        t = str(tid).strip()
        return str(nz.canon_q(t)) if _pure_q.match(t) else t

    def _pm_keys(r):
        out = set()
        for m in (getattr(r, "pedagogical_mistakes", None) or []):
            kind = m.kind.value if hasattr(m.kind, "value") else str(m.kind)
            out.add((kind, _pm_target(m.target_id)))
        return out

    p_exp, p_got = _pm_keys(gt), _pm_keys(predicted)
    rs.expected_pedagogical = [AnnotationCheck(k, t) for (k, t) in sorted(p_exp)]
    rs.missing_pedagogical = [AnnotationCheck(k, t) for (k, t) in sorted(p_exp - p_got)]
    rs.spurious_pedagogical = [AnnotationCheck(k, t) for (k, t) in sorted(p_got - p_exp)]
    rs.pedagogical_match = (not rs.missing_pedagogical) and (not rs.spurious_pedagogical)

    # ---- consistency (health only) -----------------------------------------
    violations: List[str] = []
    for q in predicted.questions:
        _check_consistency(q, q.question_id, violations)
    rs.point_sum_consistency = (len(violations) == 0)
    rs.consistency_violations = violations

    # ---- attribution counts ------------------------------------------------
    rs.render_loss_count = sum(1 for r in cr + sr if r.status == "missed" and r.attribution == "render_loss")
    rs.extraction_loss_count = sum(1 for r in cr + sr if r.status == "missed" and r.attribution == "extraction_loss")

    # ---- detail ------------------------------------------------------------
    rs.scopes = acc["scopes"]
    rs.missed_criteria = [r for r in cr + sr if r.status == "missed"]
    rs.spurious_criteria = [r for r in cr + sr if r.status == "spurious"]

    # fix-effect: does a proposed suggested_fix, once applied, still add up?
    rs.fix_effect_consistent, rs.fix_effect_violations = fix_effect_check(predicted)
    # UNGATED diagnostic: the app now repairs a move source, so a model that forgets
    # the source-side set_points can no longer hurt the teacher -- and would no longer
    # fail the gate above. This records whether the plan would have reconciled WITHOUT
    # that compensation, so model quality stays VISIBLE after being made harmless.
    rs.fix_plan_complete, _ = fix_effect_check(predicted, repair_source=False)
    return rs