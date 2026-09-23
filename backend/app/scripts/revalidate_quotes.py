"""
Re-run the quote check on OPEN drafts and re-price what it changes.

    python -m app.scripts.revalidate_quotes            # dry run: report only
    python -m app.scripts.revalidate_quotes --apply    # write the healed drafts

WHY THIS EXISTS (2026-09-15). The quote validator used to slide a fixed-width
window across the answer in coarse steps, and a genuine, correctly-cited span
could score under the 0.85 bar purely because of WHERE the window landed. The
pricer then refused the credit the model had given — the invented-credit
guard doing its job on a false input — and a criterion the student earned
priced at 0 (graded_test a0cd07ff, q2.א: 0 of 5). The validator is now an
exact alignment (`validator._coverage_score`); this script applies the new
check to drafts graded under the old one, so those rows heal without the
teacher having to notice and re-decide them.

WHAT IT TOUCHES, AND ONLY THAT
  * rows in status `draft` — approved and failed rows are immutable (LCY-2),
    pending/grading rows are not graded yet;
  * scopes graded by the LLM, checks of kind required/counted whose stored
    `quote_status` is `not_found` and whose quote now verifies (a status can
    only IMPROVE here: exact/fuzzy are never re-opened);
  * for a terminal that changed: its `points_awarded` (re-priced through the
    ONE pricer, `services.pricing`, scope-wide so charge groups still dedup),
    its `evidence_unverified` flag/annotation for that check (removed), a
    `fuzzy_match` flag (added when the new status is fuzzy), the
    `bounds_clamped` flag (recomputed from raw vs awarded), and the reasoning
    line the grade-time pricer wrote («✗ … ראיה לא אומתה» → the verdict's mark);
  * the criterion / scope sums and the row's total_score / percentage through
    `score_with_selection`, exactly as `grading_runner` derives them.

The AI's verdicts, quotes and confidences are never modified. Teacher
overrides are never read or written. The feedback text is left alone: its
staleness is keyed to the verdict vector, which does not change here.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
from decimal import Decimal
from typing import Dict, List, Tuple

from sqlalchemy import select

from app.agents.grader.validator import quote_match_status
from app.database import AsyncSessionLocal, engine
from app.models.grading import GradedTest, Rubric
from app.schemas.graded_test_draft import GradedTestDraft
from app.schemas.ontology_types import GradingRubricContract, QuoteValidationStatus
from app.services.pricing import price_scope_checks_detailed
from app.services.selection_scoring import ScopeScore, score_with_selection

logger = logging.getLogger("revalidate_quotes")

_MARK = {"met": "✓", "partially_met": "◐", "not_met": "✗"}


def _leaves(scope):
    for crit in scope.criterion_outcomes:
        for leaf in (crit.sub_criterion_outcomes or [crit]):
            tid = getattr(leaf, "sub_criterion_id", None) or crit.criterion_id
            yield crit, leaf, tid


def _heal_draft(draft: GradedTestDraft, contract: GradingRubricContract) -> Tuple[GradedTestDraft, List[str]]:
    """Return (healed draft, human-readable change log). Pure."""
    precision = contract.numeric_policy.precision
    log: List[str] = []
    new_scopes = []
    annotations = list(draft.annotations)

    for scope in draft.scope_outcomes:
        if scope.graded_by != "llm":
            new_scopes.append(scope)
            continue
        answer = scope.student_answer.text if scope.student_answer else ""
        changed_checks: Dict[str, Tuple[str, str]] = {}   # check_id -> (old, new)

        # 1. re-check every refused span
        rechecked = {}
        for _crit, leaf, tid in _leaves(scope):
            if not leaf.checks:
                continue
            new_checks = []
            for c in leaf.checks:
                if (c.kind in ("required", "counted") and c.quote
                        and c.quote_status == "not_found"):
                    status = quote_match_status(c.quote, answer)
                    if status is not None and status != QuoteValidationStatus.NOT_FOUND:
                        changed_checks[c.check_id] = ("not_found", status.value)
                        c = c.model_copy(update={"quote_status": status.value})
                new_checks.append(c)
            rechecked[tid] = new_checks
        if not changed_checks:
            new_scopes.append(scope)
            continue

        # 2. re-price the whole scope through the one pricer (charge groups dedup scope-wide)
        terminals = [(tid, leaf.points_possible, rechecked[tid])
                     for _c, leaf, tid in _leaves(scope) if leaf.checks]
        prices = price_scope_checks_detailed(terminals, precision)

        # 3. rebuild the leaves: points, flags, reasoning
        def heal_leaf(leaf, tid):
            if not leaf.checks:
                return leaf
            checks = rechecked[tid]
            price = prices[tid]
            flags = list(leaf.flags or [])
            reasoning = leaf.reasoning or ""
            for c in checks:
                if c.check_id not in changed_checks:
                    continue
                flags = [f for f in flags if not (
                    f.reason == "evidence_unverified" and f"check {c.check_id}:" in (f.message or ""))]
                if c.quote_status == "fuzzy":
                    from app.schemas.ontology_types import FlaggedOutcome, FlagReason
                    flags.append(FlaggedOutcome(
                        criterion_id=tid, reason=FlagReason.FUZZY_MATCH,
                        message=f"check {c.check_id}: fuzzy-matched evidence"))
                old_line = f"✗ {c.text} — ראיה לא אומתה"
                if old_line in reasoning:
                    reasoning = reasoning.replace(old_line, f"{_MARK[c.verdict]} {c.text}", 1)
            # the clamp flag follows the new raw/awarded pair
            flags = [f for f in flags if f.reason != "bounds_clamped"]
            if price.raw != price.awarded:
                from app.schemas.ontology_types import FlaggedOutcome, FlagReason
                flags.append(FlaggedOutcome(
                    criterion_id=tid, reason=FlagReason.BOUNDS_CLAMPED,
                    message=f"pricer clamped/snapped: {price.raw} → {price.awarded}"))
            if price.awarded != leaf.points_awarded:
                log.append(f"  {tid}: {leaf.points_awarded} → {price.awarded}")
            return leaf.model_copy(update={
                "checks": checks, "points_awarded": price.awarded,
                "flags": flags, "reasoning": reasoning})

        new_crits = []
        for crit in scope.criterion_outcomes:
            if crit.sub_criterion_outcomes:
                subs = [heal_leaf(s, s.sub_criterion_id) for s in crit.sub_criterion_outcomes]
                new_crits.append(crit.model_copy(update={
                    "sub_criterion_outcomes": subs,
                    "points_awarded": sum((s.points_awarded for s in subs), Decimal("0"))}))
            else:
                new_crits.append(heal_leaf(crit, crit.criterion_id))
        scope_awarded = sum((c.points_awarded for c in new_crits), Decimal("0"))
        new_scopes.append(scope.model_copy(update={
            "criterion_outcomes": new_crits, "points_awarded": scope_awarded}))

        # 4. the annotation the grade-time pricer wrote for each refused check
        annotations = [a for a in annotations if not (
            a.annotation_type == "evidence_unverified"
            and (a.metadata or {}).get("check_id") in changed_checks)]
        for cid, (old, new) in changed_checks.items():
            log.append(f"  check {cid}: {old} → {new}")

    healed = draft.model_copy(update={"scope_outcomes": new_scopes, "annotations": annotations})
    return healed, log


async def main(apply: bool) -> None:
    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(GradedTest).where(GradedTest.status == "draft", GradedTest.draft_json.isnot(None))
        )).scalars().all()
        print(f"open drafts: {len(rows)}")
        healed_rows = 0
        for row in rows:
            draft = GradedTestDraft.model_validate(row.draft_json)
            if not draft.plan_version:
                continue                                   # v3-era: no checks to re-check
            rubric = await db.get(Rubric, row.rubric_id)
            if rubric is None or rubric.contract_json is None:
                print(f"{row.id}: rubric contract missing — skipped")
                continue
            contract = GradingRubricContract.model_validate(rubric.contract_json)
            healed, log = _heal_draft(draft, contract)
            if not log:
                continue
            healed_rows += 1
            scoring = score_with_selection(
                [ScopeScore(question_id=so.question_id, sub_question_id=so.sub_question_id,
                            awarded=so.points_awarded) for so in healed.scope_outcomes],
                contract)
            healed = healed.model_copy(update={"scope_outcomes": [
                so.model_copy(update={"graded_by": "excluded_by_selection"})
                if so.graded_by in ("llm", "excluded_by_selection")
                and not scoring.is_counted((so.question_id, so.sub_question_id))
                else (so.model_copy(update={"graded_by": "llm"})
                      if so.graded_by == "excluded_by_selection" else so)
                for so in healed.scope_outcomes]})
            total = scoring.total_score
            possible = scoring.total_possible
            pct = (total / possible * 100).quantize(Decimal("0.01")) if possible > 0 else Decimal("0")
            # the id only, never the student's name (OD-B4)
            print(f"{row.id}: total {row.total_score} → {total}")
            for line in log:
                print(line)
            if apply:
                row.draft_json = healed.model_dump(mode="json")
                row.total_score = total
                row.total_possible = possible
                row.percentage = pct
        if apply:
            await db.commit()
            print(f"applied to {healed_rows} row(s)")
        else:
            print(f"dry run — {healed_rows} row(s) would change; rerun with --apply")
    await engine.dispose()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write the healed drafts")
    args = ap.parse_args()
    asyncio.run(main(args.apply))
