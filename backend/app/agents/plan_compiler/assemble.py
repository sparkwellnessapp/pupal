"""
PLAN COMPILER v2 — Stage 3: PlanSkeleton (+ wording) → GradingPlan (PR §6).

Two entry points:

  assemble_placeholder_plan(skeleton)
      A0's plan: every slot's `source_span` stands in for `description_he`
      (a placeholder, never verifier-ready — it exists so the ALGEBRA can be
      measured against the GTs with zero spend). `rubric_quote` is the same
      span, so V9 grounds by construction wherever the span is verbatim.

  assemble_plan(skeleton, wording)
      The real thing: `wording[slot_id] = (description_he, rubric_quote,
      equivalence_note)` from the segmenter (P6). Points, kinds, amounts,
      counts and groups come ONLY from the skeleton — a wording entry cannot
      change a number (design law, PR §1).

Provenance: `plan_version = "<exam>/compiled-<sha256[:12]>"` where the hash is
over the plan's own JSON with the version field blanked, so the identifier is a
function of the artefact and two identical compilations share it.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple

from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan

from .skeleton import PlanSkeleton, Slot

Wording = Dict[str, Tuple[str, Optional[str], Optional[str]]]

PLACEHOLDER_REMAINDER_HE = "שאר הדרישה שבסעיף"     # a Case-2 remainder slot has no span of its own

# The placeholder description must be POINT-BLIND (validator V10) even though it
# is only a stand-in: A0 measures the algebra under the real validator, and a
# plan that fails V10 is not a plan. Same vocabulary as the validator's
# `_POINT_TEXT`, applied as a stripper.
_POINT_FRAGMENT = re.compile(
    r"\(?\s*\d+(?:[.,]\d+)?\s*(?:נק['׳]?|נקודות|נקודה|כ[\"״]א)\s*\)?"
    r"|(?:נק['׳]?|נקודות|נקודה)\s*\d+(?:[.,]\d+)?"
    r"|להוריד\s+\d+(?:[.,]\d+)?")


def point_blind(text: str) -> str:
    return re.sub(r"\s+", " ", _POINT_FRAGMENT.sub(" ", text)).strip(" ,;:-–")


def _check(slot: Slot, description_he: str, rubric_quote: Optional[str],
           equivalence_note: Optional[str]) -> PlanCheck:
    return PlanCheck(
        check_id=slot.slot_id,
        description_he=description_he,
        kind=slot.kind,
        points=slot.points,
        tariff_amount=slot.tariff_amount,
        partial_fraction=slot.partial_fraction,
        equivalence_note=equivalence_note or None,
        charge_group=slot.charge_group,
        rubric_quote=rubric_quote or None,
        unit_count=slot.unit_count,
    )


def _plan(skeleton: PlanSkeleton, checks_by_terminal: Dict[str, List[PlanCheck]], *,
          segmenter_prompt_version: Optional[str], segmenter_model: Optional[str],
          router_model: Optional[str]) -> GradingPlan:
    terminals = [TerminalPlan(terminal_id=t.terminal_id, points_possible=t.points_possible,
                              checks=checks_by_terminal[t.terminal_id])
                 for t in skeleton.terminals]
    draft = GradingPlan(plan_version="", exam_id=skeleton.exam_id,
                        rubric_contract_sha256=skeleton.rubric_contract_sha256,
                        terminals=terminals, compiler_version=skeleton.compiler_version,
                        segmenter_prompt_version=segmenter_prompt_version,
                        segmenter_model=segmenter_model, router_model=router_model)
    digest = hashlib.sha256(json.dumps(draft.model_dump(mode="json"), ensure_ascii=False,
                                       sort_keys=True).encode("utf-8")).hexdigest()
    return draft.model_copy(update={"plan_version": f"{skeleton.exam_id}/compiled-{digest[:12]}"})


def assemble_placeholder_plan(skeleton: PlanSkeleton) -> GradingPlan:
    """description_he ← the slot's marker-free summary (a tariff's is the
    requirement it guards, per PR §4 — «the requirement whose absence fires the
    tariff»); rubric_quote ← the verbatim span. Never verifier-ready; enough
    for V1–V12 and the expressibility guard."""
    by: Dict[str, List[PlanCheck]] = {}
    for t in skeleton.terminals:
        checks = []
        for s in t.slots:
            if s.kind == "tariff":
                desc = s.anchor_span or point_blind(s.summary or s.source_span)
            else:
                desc = s.summary or point_blind(s.source_span)
            if "case2_remainder" in s.flags:
                desc = PLACEHOLDER_REMAINDER_HE
            desc = point_blind(desc) or PLACEHOLDER_REMAINDER_HE
            quote = s.source_span or t.text.strip() or None
            # V9 (refined, R-1): a quote under 10 tight characters grounds only
            # as a WHOLE corpus line — «void», «אתחול» are pieces of a line. Cite
            # the criterion's own line instead; the slot's span is still the
            # segmenter's input, this is only what the validator sees.
            if quote and len(re.sub(r"\s+", "", quote)) < 10:
                quote = t.text.strip().split("\n")[0].strip() or quote
            checks.append(_check(s, desc, quote, None))
        by[t.terminal_id] = checks
    return _plan(skeleton, by, segmenter_prompt_version=None, segmenter_model=None,
                 router_model=None)


def assemble_plan(skeleton: PlanSkeleton, wording: Wording, *,
                  segmenter_prompt_version: str, segmenter_model: str,
                  router_model: Optional[str] = None) -> GradingPlan:
    """Every slot must have wording; a missing entry is a caller bug, not a
    fallback — the segmenter substitutes the span ITSELF on failure (PR §4),
    so an absent key means a stage was skipped."""
    by: Dict[str, List[PlanCheck]] = {}
    for t in skeleton.terminals:
        checks = []
        for s in t.slots:
            if s.slot_id not in wording:
                raise KeyError(f"no wording for {s.slot_id}")
            d, q, e = wording[s.slot_id]
            checks.append(_check(s, d, q, e))
        by[t.terminal_id] = checks
    return _plan(skeleton, by, segmenter_prompt_version=segmenter_prompt_version,
                 segmenter_model=segmenter_model, router_model=router_model)
