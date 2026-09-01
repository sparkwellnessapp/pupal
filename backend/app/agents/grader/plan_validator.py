"""
grader-v5 plan validator — pure, loud, total (MISSION_grader_v5_closed_loop §5 V5-A).

validate_plan(plan, contract_terminal_points, terminal_scopes, precision) -> [errors]

Every rule carries a stable tag so tests and the H-4 render can name the exact
violation. An empty list is the ONLY pass. No I/O, no LLM, no floats.

Rules:
  V1  per terminal: Σ required.points == points_possible EXACTLY.
  V2  every points / tariff_amount value sits on the precision grid.
  V3  kind shape: required ⇒ points>0, no tariff_amount, no charge_group;
      tariff ⇒ points==0, 0 < tariff_amount <= points_possible;
      note_only ⇒ points==0, no tariff_amount, no charge_group.
  V4  required: points * partial_fraction sits on the grid (the partial award
      must be representable — no snapping ambiguity on the honest path).
  V5  check_id globally unique; terminal_id unique.
  V6  totality vs the contract: plan terminals == contract terminals exactly,
      and points_possible matches per terminal.
  V7  a charge_group never spans scopes (verdicts arrive per scope; a cross-
      scope group could not be deduped deterministically).
  V8  partial_fraction strictly inside (0, 1).
  V9  rubric-quote grounding: a GENERATED check's rubric_quote must appear in
      the rubric contract's own text. Runs only when the corpus is supplied
      (the plan compiler always supplies it; the eval flow may not).
  V10 point-blindness: description_he may not state point values — the verifier
      is point-blind by design, and a number in the check text hands it the
      answer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional

import re
import unicodedata

from app.agents.grader.plan_schemas import GradingPlan

# V9 — CALIBRATED against the ratified hand plan (2026-09-01), not invented.
# A first-principles "verbatim span of the criterion text" rejected 46 of its 80
# checks. Three properties of real authoring had to be honoured:
#   · quotes are ELIDED   ("יצירת 2 מונה … + אתחולם")  → split on … and dashes
#   · the source has TYPOS ("countHobbiesאו", no space) → compare whitespace-free
#   · the corpus is the WHOLE contract, not one criterion — authors cite the
#     question spec and the example solution, which is where most of the
#     decomposition actually comes from
# At that calibration the hand plan grounds 73/80, and the ungrounded remainder
# is dominated by its `ruling`-sourced checks — which V9 exempts by design.
_QUOTE_SPLIT = re.compile(r"…|\.\.\.|—|–")
_MIN_FRAGMENT = 8          # shorter fragments match accidentally

# V10 — point-DENOTING text, never bare digits. "אתחול ב-0" (initialise to zero)
# is legitimate code talk; "להוריד 2 נקודות" is the answer key. A bare-digit
# rule flagged 24 of the hand plan's 80 checks, all false positives.
_POINT_TEXT = re.compile(r"(\d+(?:\.\d+)?\s*(?:נק|נקוד)|(?:נק|נקוד)\S*\s*\d|להוריד\s+\d)")


def _tight(text: str) -> str:
    """NFC, whitespace removed — so a missing space in the teacher's source
    cannot make an honest citation look hallucinated."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFC", text or ""))


def quote_is_grounded(quote: str, corpus_tight: str) -> bool:
    fragments = [_tight(f) for f in _QUOTE_SPLIT.split(quote or "")]
    fragments = [f for f in fragments if len(f) >= _MIN_FRAGMENT]
    return bool(fragments) and all(f in corpus_tight for f in fragments)


def _on_grid(v: Decimal, precision: Decimal) -> bool:
    return (v % precision) == 0


def validate_plan(plan: GradingPlan,
                  *,
                  contract_terminal_points: Dict[str, Decimal],
                  terminal_scopes: Dict[str, str],
                  precision: Decimal,
                  contract_corpus: Optional[str] = None) -> List[str]:
    errs: List[str] = []
    # V9 runs only with a corpus. Not a silent skip: the plan compiler always
    # passes one, and the eval suite's file flow does not need it because its
    # plan is owner-ratified rather than generated.
    corpus_tight = _tight(contract_corpus) if contract_corpus else None

    # V5 — uniqueness first (later rules assume addressability)
    seen_terminals: set = set()
    seen_checks: set = set()
    for tp in plan.terminals:
        if tp.terminal_id in seen_terminals:
            errs.append(f"V5: duplicate terminal {tp.terminal_id!r} in plan")
        seen_terminals.add(tp.terminal_id)
        for c in tp.checks:
            if c.check_id in seen_checks:
                errs.append(f"V5: duplicate check_id {c.check_id!r}")
            seen_checks.add(c.check_id)

    # V6 — totality vs contract
    missing = set(contract_terminal_points) - seen_terminals
    extra = seen_terminals - set(contract_terminal_points)
    for t in sorted(missing):
        errs.append(f"V6: contract terminal {t!r} has no plan")
    for t in sorted(extra):
        errs.append(f"V6: plan terminal {t!r} is not in the contract")

    group_scopes: Dict[str, set] = {}

    for tp in plan.terminals:
        tid = tp.terminal_id
        if tid in contract_terminal_points and \
                tp.points_possible != contract_terminal_points[tid]:
            errs.append(f"V6: {tid} points_possible {tp.points_possible} != "
                        f"contract {contract_terminal_points[tid]}")

        required_sum = Decimal("0")
        for c in tp.checks:
            # V10 — point-blindness (applies to every check, both layers)
            if _POINT_TEXT.search(c.description_he or ""):
                errs.append(f"V10: {c.check_id} description_he states a point "
                            f"value; the verifier is point-blind by design")
            # V9 — grounding, GENERATED checks only. A `ruling` check cites a
            # ruling, not rubric text, so grounding it is not merely wrong but
            # impossible.
            if corpus_tight is not None and c.source == "generated":
                if not quote_is_grounded(c.rubric_quote or "", corpus_tight):
                    errs.append(f"V9: {c.check_id} rubric_quote is not grounded "
                                f"in the rubric text — a generated check must "
                                f"cite the teacher, or be marked source='ruling'")
            # V2 — grid
            if not _on_grid(c.points, precision):
                errs.append(f"V2: {c.check_id} points {c.points} off the "
                            f"{precision} grid")
            if c.tariff_amount is not None and not _on_grid(c.tariff_amount, precision):
                errs.append(f"V2: {c.check_id} tariff_amount {c.tariff_amount} "
                            f"off the {precision} grid")

            # V3 — kind shape
            if c.kind == "required":
                required_sum += c.points
                if c.points <= 0:
                    errs.append(f"V3: required {c.check_id} must carry points > 0")
                if c.tariff_amount is not None:
                    errs.append(f"V3: required {c.check_id} carries a tariff_amount")
                if c.charge_group is not None:
                    errs.append(f"V3: required {c.check_id} carries a charge_group")
                # V8 + V4 — partial credit representability
                if not (Decimal("0") < c.partial_fraction < Decimal("1")):
                    errs.append(f"V8: {c.check_id} partial_fraction "
                                f"{c.partial_fraction} outside (0, 1)")
                elif not _on_grid(c.points * c.partial_fraction, precision):
                    errs.append(f"V4: {c.check_id} partial award "
                                f"{c.points * c.partial_fraction} off the grid — "
                                f"adjust points or partial_fraction")
            elif c.kind == "tariff":
                if c.points != 0:
                    errs.append(f"V3: tariff {c.check_id} must carry points == 0")
                if c.tariff_amount is None or c.tariff_amount <= 0:
                    errs.append(f"V3: tariff {c.check_id} needs tariff_amount > 0")
                elif c.tariff_amount > tp.points_possible:
                    errs.append(f"V3: {c.check_id} tariff_amount {c.tariff_amount} "
                                f"exceeds the terminal's points_possible "
                                f"{tp.points_possible} — a defect never costs more "
                                f"than the component it belongs to")
                if c.charge_group is not None and tid in terminal_scopes:
                    group_scopes.setdefault(c.charge_group, set()).add(
                        terminal_scopes[tid])
            else:  # note_only
                if c.points != 0:
                    errs.append(f"V3: note_only {c.check_id} must carry points == 0")
                if c.tariff_amount is not None:
                    errs.append(f"V3: note_only {c.check_id} carries a tariff_amount")
                if c.charge_group is not None:
                    errs.append(f"V3: note_only {c.check_id} carries a charge_group")

        # V1 — the sum law
        if required_sum != tp.points_possible:
            errs.append(f"V1: {tid} Σ required.points = {required_sum} != "
                        f"points_possible {tp.points_possible}")

    # V7 — charge groups stay inside one scope
    for group, scopes in sorted(group_scopes.items()):
        if len(scopes) > 1:
            errs.append(f"V7: charge_group {group!r} spans scopes "
                        f"{sorted(scopes)} — groups must stay inside one scope")

    return errs
