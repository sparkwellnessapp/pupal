"""
grader-v5 deterministic pricer — verdicts in, points out. Pure, no I/O, no LLM.

price_scope(terminal_plans, assessed_verdicts, precision) -> {terminal_id: PricedTerminal}

The model NEVER emits a number (mission §3); every point on the graded test is
computed here, from the ratified plan and the model's verdicts. Rules (each
pinned by tests/agents/test_grader_v5_plan.py):

  earn      required met → points · partially_met → points × partial_fraction ·
            not_met → 0.
  evidence  met/partially_met on a REQUIRED check must carry a VERIFIED span
            (exact or fuzzy). Unverifiable ("" or not_found) ⇒ priced as
            not_met + EVIDENCE_UNVERIFIED flag + annotation — credit is refused
            LOUDLY, never granted on invented ink (the GA-1 property in code).
  missing   a check with no verdict ⇒ not_met + UNVERIFIED_CHECK flag (no credit
            without verification; conservative, review-first).
  tariff    verdicts are requirement-phrased: not_met = the defect IS present ⇒
            deduct tariff_amount. Once per charge_group across the scope
            (charge-once): first firing terminal in document order pays the MAX
            fired amount; later firings annotate `charge_group_dedup` and pay
            nothing. partially_met on a tariff is coerced to fired
            (TARIFF_COERCED flag) — tariffs are binary.
  note_only fired (not_met) ⇒ INFO annotation, NEVER points (the rubric's
            «לציין, לא להוריד» made structural).
  clamp     terminal award = clamp(earned − tariffs, 0, points_possible), then
            grid-snap ROUND_HALF_UP; any change flags BOUNDS_CLAMPED (belt and
            braces — the validator makes the honest path exact already).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional

from app.agents.grader.plan_schemas import PlanCheck, TerminalPlan
from app.schemas.graded_test_draft import Check, GradingAnnotation
from app.schemas.ontology_types import (
    AnnotationSeverity,
    AnswerQuotation,
    FlaggedOutcome,
    FlagReason,
    QuoteValidationStatus,
)

_VERDICT_MARK = {"met": "✓", "partially_met": "◐", "not_met": "✗"}


@dataclass(frozen=True)
class AssessedVerdict:
    """One model verdict AFTER deterministic quote validation (the v5 agent
    validates each evidence span against the student answer before pricing)."""
    check_id: str
    verdict: str                              # met | partially_met | not_met
    confidence: float
    basis_he: str
    quote_text: str
    quote_status: Optional[QuoteValidationStatus]   # None when quote_text == ""


@dataclass
class PricedTerminal:
    points_awarded: Decimal
    reasoning: str
    confidence: float
    # [PR-G1] the per-check record this class used to drop on the floor. The
    # verdicts were always here; only the carrying was missing.
    checks: List[Check] = field(default_factory=list)
    evidence_quotes: List[AnswerQuotation] = field(default_factory=list)
    flags: List[FlaggedOutcome] = field(default_factory=list)
    annotations: List[GradingAnnotation] = field(default_factory=list)


def _evidence_verified(av: AssessedVerdict) -> bool:
    return av.quote_status in (QuoteValidationStatus.EXACT, QuoteValidationStatus.FUZZY)


def _snap(value: Decimal, lo: Decimal, hi: Decimal, precision: Decimal) -> Decimal:
    clamped = max(lo, min(value, hi))
    return (clamped / precision).to_integral_value(rounding=ROUND_HALF_UP) * precision


def _tariff_fired(av: Optional[AssessedVerdict]) -> bool:
    return av is not None and av.verdict in ("not_met", "partially_met")


def price_scope(terminal_plans: List[TerminalPlan],
                assessed: Dict[str, AssessedVerdict],
                precision: Decimal) -> Dict[str, PricedTerminal]:
    # ── charge-once pre-pass: per group, the FIRST firing check (document
    # order) pays the MAX fired amount; every other firing member is deduped ──
    group_first_firing: Dict[str, str] = {}      # group -> check_id that pays
    group_amount: Dict[str, Decimal] = {}        # group -> max fired amount
    for tp in terminal_plans:
        for check in tp.checks:
            if check.kind != "tariff":
                continue
            group = check.charge_group or f"__solo__{check.check_id}"
            if _tariff_fired(assessed.get(check.check_id)):
                group_first_firing.setdefault(group, check.check_id)
                amount = check.tariff_amount or Decimal("0")
                if amount > group_amount.get(group, Decimal("0")):
                    group_amount[group] = amount

    out: Dict[str, PricedTerminal] = {}

    for tp in terminal_plans:
        earned = Decimal("0")
        deducted = Decimal("0")
        flags: List[FlaggedOutcome] = []
        annotations: List[GradingAnnotation] = []
        lines: List[str] = []
        confidences: List[float] = []
        quotes: List[AnswerQuotation] = []
        seen_spans: set = set()

        def _collect_quote(av: AssessedVerdict) -> None:
            if av.quote_text and _evidence_verified(av) and av.quote_text not in seen_spans:
                seen_spans.add(av.quote_text)
                quotes.append(AnswerQuotation(quote_text=av.quote_text,
                                              validation_status=av.quote_status))

        checks: List[Check] = []

        def _record(check: PlanCheck, av: Optional[AssessedVerdict]) -> None:
            """One Check per plan check, ALWAYS — including the no-verdict case.

            A check the model never answered is priced as no-credit, so the
            record says not_met at confidence 0 with the reason in basis_he.
            The terminal's UNVERIFIED_CHECK flag carries the fact that no
            verdict arrived; conflating the two into a fourth verdict value
            would expand the wire vocabulary without a ruling."""
            # The span the model CITED is kept even when it does not validate:
            # `quote_status` says whether it was found, and an invented-credit
            # case is exactly where the teacher needs to see WHAT was claimed.
            # §1.1: quote is None only when there is no evidence at all.
            checks.append(Check(
                check_id=check.check_id,
                text=check.description_he,
                kind=check.kind,
                points=check.points,
                tariff=check.tariff_amount,
                partial_fraction=check.partial_fraction,
                verdict=(av.verdict if av is not None else "not_met"),
                quote=(av.quote_text or None) if av is not None else None,
                quote_status=(av.quote_status.value
                              if av is not None and av.quote_status is not None else None),
                basis_he=(av.basis_he if av is not None
                          else "לא אומת על ידי המודל"),
                confidence=(max(0.0, min(1.0, av.confidence)) if av is not None else 0.0),
            ))

        for check in tp.checks:
            av = assessed.get(check.check_id)
            _record(check, av)

            # ── missing verdict: no credit without verification ────────────
            if av is None:
                confidences.append(0.0)
                flags.append(FlaggedOutcome(
                    criterion_id=tp.terminal_id, reason=FlagReason.UNVERIFIED_CHECK,
                    message=f"check {check.check_id} received no verdict"))
                annotations.append(GradingAnnotation(
                    severity=AnnotationSeverity.WARNING,
                    target_id=tp.terminal_id, annotation_type="unverified_check",
                    message=f"הבדיקה '{check.description_he}' לא אומתה על ידי המודל — לא ניתן זיכוי",
                    metadata={"check_id": check.check_id}))
                lines.append(f"✗ {check.description_he} — לא אומת")
                continue

            confidences.append(max(0.0, min(1.0, av.confidence)))
            verdict = av.verdict

            if check.kind == "required":
                # evidence gating: credit only on a verified span
                if verdict in ("met", "partially_met") and not _evidence_verified(av):
                    flags.append(FlaggedOutcome(
                        criterion_id=tp.terminal_id,
                        reason=FlagReason.EVIDENCE_UNVERIFIED,
                        message=f"check {check.check_id}: {verdict} on an "
                                f"unverifiable span — credit refused"))
                    annotations.append(GradingAnnotation(
                        severity=AnnotationSeverity.WARNING,
                        target_id=tp.terminal_id,
                        annotation_type="evidence_unverified",
                        message=f"הבדיקה '{check.description_he}' סומנה כמתקיימת אך "
                                f"הציטוט לא נמצא בתשובת התלמיד — לא ניתן זיכוי",
                        metadata={"check_id": check.check_id,
                                  "claimed_verdict": verdict,
                                  "quote_text": av.quote_text[:200]}))
                    lines.append(f"✗ {check.description_he} — ראיה לא אומתה")
                    continue
                if verdict == "met":
                    earned += check.points
                elif verdict == "partially_met":
                    earned += check.points * check.partial_fraction
                if _evidence_verified(av) and av.quote_status == QuoteValidationStatus.FUZZY:
                    flags.append(FlaggedOutcome(
                        criterion_id=tp.terminal_id, reason=FlagReason.FUZZY_MATCH,
                        message=f"check {check.check_id}: fuzzy-matched evidence"))
                _collect_quote(av)
                lines.append(f"{_VERDICT_MARK[verdict]} {check.description_he}"
                             + (f" — {av.basis_he}" if verdict != "met" and av.basis_he else ""))

            elif check.kind == "tariff":
                fired = verdict in ("not_met", "partially_met")
                if verdict == "partially_met":
                    flags.append(FlaggedOutcome(
                        criterion_id=tp.terminal_id, reason=FlagReason.TARIFF_COERCED,
                        message=f"check {check.check_id}: partially_met on a binary "
                                f"tariff — treated as fired"))
                    annotations.append(GradingAnnotation(
                        severity=AnnotationSeverity.INFO,
                        target_id=tp.terminal_id, annotation_type="tariff_coerced",
                        message=f"הבדיקה '{check.description_he}' סומנה כמתקיימת חלקית — "
                                f"הניכוי הוחל במלואו (בדיקת ניכוי היא בינארית)",
                        metadata={"check_id": check.check_id}))
                if fired:
                    group = check.charge_group or f"__solo__{check.check_id}"
                    if group_first_firing.get(group) == check.check_id:
                        amount = group_amount[group]        # MAX fired in group
                        deducted += amount
                        lines.append(f"✗ {check.description_he} — ניכוי {amount}"
                                     + (f" — {av.basis_he}" if av.basis_he else ""))
                    else:
                        annotations.append(GradingAnnotation(
                            severity=AnnotationSeverity.INFO,
                            target_id=tp.terminal_id,
                            annotation_type="charge_group_dedup",
                            message=f"הליקוי '{check.description_he}' כבר חויב "
                                    f"בסעיף אחר — לא נוכה שוב (חיוב חד-פעמי)",
                            metadata={"check_id": check.check_id,
                                      "charge_group": group}))
                        lines.append(f"✗ {check.description_he} — חויב פעם אחת בלבד")
                    _collect_quote(av)
                else:
                    lines.append(f"✓ {check.description_he}")

            else:  # note_only
                if verdict in ("not_met", "partially_met"):
                    annotations.append(GradingAnnotation(
                        severity=AnnotationSeverity.INFO,
                        target_id=tp.terminal_id, annotation_type="note_only",
                        message=f"לתשומת לב (ללא הורדת נקודות): {check.description_he}"
                                + (f" — {av.basis_he}" if av.basis_he else ""),
                        metadata={"check_id": check.check_id,
                                  "quote_text": av.quote_text[:200]}))
                    lines.append(f"◦ {check.description_he} — צוין, ללא ניכוי")
                    _collect_quote(av)
                else:
                    lines.append(f"✓ {check.description_he}")

        raw = earned - deducted
        final = _snap(raw, Decimal("0"), tp.points_possible, precision)
        if final != raw:
            flags.append(FlaggedOutcome(
                criterion_id=tp.terminal_id, reason=FlagReason.BOUNDS_CLAMPED,
                message=f"pricer clamped/snapped: {raw} → {final}"))

        out[tp.terminal_id] = PricedTerminal(
            checks=checks,
            points_awarded=final,
            reasoning="\n".join(lines),
            confidence=min(confidences) if confidences else 0.0,
            evidence_quotes=quotes,
            flags=flags,
            annotations=annotations,
        )
    return out
