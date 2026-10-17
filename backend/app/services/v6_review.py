"""
grader-v6 review — her overlay over a v6 draft (owner rulings 2026-10-17 §7, the MVC).

ONE place for what the read endpoint, PATCH /draft and approval all need:

  overlay_of(overrides)        the persisted overlay IS the pricer's own input
                               (`pricing_v6.PricingOverlay`), stored as JSON at
                               `GradedTestOverrides.v6`
  overlay_violations(...)      CW-3 extended to checks and options, plus the MVC's
                               limits (no typed per-check amount, no evidence dispute —
                               both v6.1), the terminal pin's bounds and grid
  merge_overlay(stored, patch) MERGE, never replace: a key in the patch sets or (null)
                               withdraws exactly that decision; everything else stays
  review(draft, overrides)     both prices (Vivi's alone, and with her overlay) and the
                               line she reads per credit terminal

THE LINE SHE READS. The explainer's line is written ONCE, at grade time (§7: no other
writer of that field). A criterion she edits — a decision on any of its checks, or its
grade set by hand — and any criterion whose award moved anyway (a group charge that
moved with her pin) shows the FALLBACK COMPOSER's line for the effective selection: no
LLM call, and never the model's words over a grade they no longer describe. The
composer itself says «the grade was set by hand» when she pinned it.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple

from pydantic import BaseModel, Field

from app.schemas.graded_test_draft_v6 import DraftV6Content, v6_content
from app.services.pricing_v6 import CheckDecision, PricedTest, PricingOverlay, price

ReasoningLine = Tuple[str, str]                 # (text_he, source)
_COMMENT_MAX = 2000


@dataclass(frozen=True)
class OverlayViolation:
    target_id: str
    kind: str
    message: str


# ── the patch a PATCH /draft carries for a v6 draft ───────────────────────────

class CheckPatchV6(BaseModel):
    """Her decision on one check. `option_id` None with a comment keeps Vivi's pick and
    adds her note; both None is the same as withdrawing the record."""
    model_config = {"extra": "forbid"}
    option_id: Optional[str] = None
    comment: Optional[str] = None


class OverlayPatchV6(BaseModel):
    """MERGE semantics: a key PRESENT sets (or, with null, withdraws) that decision;
    an absent key leaves hers untouched. `extra=forbid`: a misspelt field is a 422,
    never a silent no-op."""
    model_config = {"extra": "forbid"}
    checks: Dict[str, Optional[CheckPatchV6]] = Field(default_factory=dict)
    terminal_points: Dict[str, Optional[Decimal]] = Field(default_factory=dict)


# ── persistence ───────────────────────────────────────────────────────────────

def overlay_of(overrides) -> PricingOverlay:
    raw = getattr(overrides, "v6", None) if overrides is not None else None
    return PricingOverlay() if raw is None else PricingOverlay.model_validate(raw)


def overlay_doc(overlay: PricingOverlay) -> Dict:
    return overlay.model_dump(mode="json", exclude_defaults=True)


def merge_overlay(stored: PricingOverlay, patch: OverlayPatchV6) -> PricingOverlay:
    checks = dict(stored.checks)
    for cid, p in patch.checks.items():
        if p is None or (p.option_id is None and not (p.comment or "").strip()):
            checks.pop(cid, None)
        else:
            checks[cid] = CheckDecision(option_id=p.option_id,
                                        comment=(p.comment or "").strip() or None)
    pins = dict(stored.terminal_points)
    for tid, v in patch.terminal_points.items():
        if v is None:
            pins.pop(tid, None)
        else:
            pins[tid] = v
    return PricingOverlay(checks=checks, terminal_points=pins)


# ── CW-3, extended to checks and options ──────────────────────────────────────

def overlay_violations(content: DraftV6Content, overlay: PricingOverlay) -> List[OverlayViolation]:
    checks = {c.plan.check_id: c.plan for c in content.checks}
    possible = {t.terminal_id: t.points_possible for t in content.terminals}
    out: List[OverlayViolation] = []
    for cid, d in overlay.checks.items():
        plan = checks.get(cid)
        if plan is None:
            out.append(OverlayViolation(cid, "closed_world",
                                        f"'{cid}' is not a check of this graded test."))
            continue
        if d.option_id is not None and plan.option(d.option_id) is None:
            out.append(OverlayViolation(cid, "closed_world",
                                        f"'{d.option_id}' is not an option of check '{cid}'."))
        if d.amount is not None:
            out.append(OverlayViolation(cid, "not_supported",
                                        "a typed amount on a v6 check is not available yet (v6.1)."))
        if d.evidence_disputed:
            out.append(OverlayViolation(cid, "not_supported",
                                        "disputing evidence on a v6 check is not available yet (v6.1)."))
        if d.comment is not None and len(d.comment) > _COMMENT_MAX:
            out.append(OverlayViolation(cid, "too_long", f"a comment is at most {_COMMENT_MAX} characters."))
    for tid, v in overlay.terminal_points.items():
        p = possible.get(tid)
        if p is None:
            out.append(OverlayViolation(tid, "closed_world",
                                        f"'{tid}' is not a criterion of this graded test."))
            continue
        if v < 0 or v > p:
            out.append(OverlayViolation(tid, "out_of_bounds",
                                        f"לא ניתן להעניק {v} נקודות לקריטריון עם מקסימום {p} נקודות"))
        elif (v / content.precision) % 1 != 0:
            out.append(OverlayViolation(tid, "off_grid",
                                        f"{v} is not on this rubric's grid of {content.precision}."))
    return out


# ── what she sees ─────────────────────────────────────────────────────────────

def decided_check_ids(overlay: PricingOverlay) -> Set[str]:
    """Checks SHE decided (an option, not only a note)."""
    return {cid for cid, d in overlay.checks.items() if d.option_id is not None}


def touched_terminals(content: DraftV6Content, overlay: PricingOverlay) -> Set[str]:
    by_check = {c.plan.check_id: c.plan.priced_terminal_id for c in content.checks}
    return {by_check[cid] for cid in decided_check_ids(overlay) if cid in by_check} \
        | set(overlay.terminal_points)


def reasoning_lines(content: DraftV6Content, ai: PricedTest, final: PricedTest,
                    overlay: PricingOverlay) -> Dict[str, ReasoningLine]:
    from app.agents.explainer.fallback import compose_reasoning_he
    view = content.to_view()
    recorded = {x.terminal_id: (x.text_he, x.source) for x in content.explanations}
    ai_award = {t.terminal_id: t.awarded for t in ai.terminals}
    final_t = {t.terminal_id: t for t in final.terminals}
    touched = touched_terminals(content, overlay)
    out: Dict[str, ReasoningLine] = {}
    for tid in (x.terminal_id for x in content.terminals):          # plan order
        if tid not in recorded and tid not in touched:
            continue
        t = final_t.get(tid)
        if t is None:
            continue
        if tid in touched or t.awarded != ai_award.get(tid):
            source = "teacher_override" if (t.overridden or t.typed) else "fallback"
            out[tid] = (compose_reasoning_he(final, view, tid), source)
        elif tid in recorded:
            out[tid] = recorded[tid]
    return out


@dataclass
class ReviewV6:
    content: DraftV6Content
    overlay: PricingOverlay
    ai: PricedTest
    final: PricedTest
    lines: Dict[str, ReasoningLine]


def review(draft, overrides) -> Optional[ReviewV6]:
    """None for a v3/v5 draft. Raises on a stored overlay that no longer parses — a
    consuming path refuses (§3.5a)."""
    content = v6_content(draft)
    if content is None:
        return None
    overlay = overlay_of(overrides)
    view = content.to_view()
    ai, final = price(view), price(view, overlay)
    return ReviewV6(content, overlay, ai, final, reasoning_lines(content, ai, final, overlay))


def undecided_checks(content: DraftV6Content, ai: PricedTest, overlay: PricingOverlay) -> List[str]:
    """[OD-4, unchanged for v6] a check a call SHOULD have answered but did not — its
    scope was graded by the model or failed — blocks approval until she decides it. A
    blank answer's checks are not undecided: nothing was asked, and zero is the grade."""
    called = {(s.question_id, s.sub_question_id) for s in content.scopes if s.graded_by in ("llm", "failed")}
    scope_of = {t.terminal_id: (t.question_id, t.sub_question_id) for t in content.view_terminals}
    plans = {c.plan.check_id: c.plan for c in content.checks}
    decided = decided_check_ids(overlay)
    pinned = set(overlay.terminal_points)
    out = []
    for r in ai.checks:
        plan = plans[r.check_id]
        if plan.role == "note" or not r.missing:
            continue
        tid = plan.priced_terminal_id
        if scope_of.get(tid) in called and r.check_id not in decided and tid not in pinned:
            out.append(r.check_id)
    return out
