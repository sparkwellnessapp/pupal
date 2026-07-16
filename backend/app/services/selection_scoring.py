"""
Selection-aware scoring — the SINGLE source of the grade denominator (PR-3).

WHY THIS MODULE EXISTS
----------------------
The final score was computed in TWO places, and both of them re-derived the
denominator by re-summing scopes:

    grading_runner            total_possible = Σ scope.points_possible
    graded_test_contract_compiler   total_possible = Σ scope.points_possible

On a "choose k of N" exam that is wrong, and wrong in the worst direction: it
divides by every question the exam OFFERED rather than the points the student
could actually EARN. A student who answers the 50-point question perfectly and
skips the other two — exactly as the exam instructs — scored 50/100 = 50%.
Their grade was halved for obeying the instructions.

Worse, fixing only the grading site would have been actively dangerous: the
approval gate would then freeze a DIFFERENT percentage than the teacher reviewed
and approved. So both sites now call this one function and NEITHER re-sums
anything.

THE RULES (R2)
--------------
* Denominator = `contract.total_points`, which the ContractCompiler set to the
  ACHIEVABLE total (Σ mandatory + Σ per-group top-k). Read, never recomputed.
* Per group, the student's BEST-k answered members count toward the numerator.
  Best-k is student-favorable and is the only orderable rule — "first k answered"
  is unknowable without reading order.
* Members beyond k are EXCLUDED: they contribute to neither numerator nor
  denominator, and they are NOT "given 0". On a choose-4-of-6 the two unchosen
  questions are not failures; they were never owed.
* If FEWER than k were answered, the empty slots simply fall inside the counted
  k and contribute 0 — that is the exam's own rule, and it falls out of best-k
  ranking for free (an unanswered scope scores 0 and still ranks into the top-k).
* Questions in no group are MANDATORY: always counted. An unanswered mandatory
  question keeps its zero — that semantics is correct for it.

EXCLUSION IS DERIVED STATE, NEVER AN INPUT
------------------------------------------
This function takes the CURRENT scores and returns the counted/excluded split.
It must be recomputed at every site, because a teacher override can change which
member is best-k: bump the 15-pointer's awarded points above the 50-pointer's and
group membership flips. Therefore:

    grading time  -> marks are PROVISIONAL (display/audit only)
    approval time -> recomputed from POST-override scores; THAT is authoritative
                     and is what gets frozen into the GradedTestContract.

Same function, different inputs. That is correctness, not drift. The
`graded_by="excluded_by_selection"` literal and `counted_in_total` flag are
RECORDS of this function's decision — the math never reads them back.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Dict, FrozenSet, List, Optional, Sequence, Tuple

from ..schemas.ontology_types import GradingRubricContract

# A scope is identified by (question_id, sub_question_id). sub_question_id is the
# full path within the question ("א", "א.2") or None for a direct-criteria question.
ScopeKey = Tuple[str, Optional[str]]


@dataclass(frozen=True)
class ScopeScore:
    """The minimum this module needs about one scope. Deliberately NOT a
    ScopeOutcome/ContractScopeOutcome: the two call sites hold different types
    (points_awarded vs final_points_awarded), and this keeps the helper pure and
    trivially testable."""
    question_id: str
    sub_question_id: Optional[str]
    awarded: Decimal

    @property
    def key(self) -> ScopeKey:
        return (self.question_id, self.sub_question_id)


@dataclass(frozen=True)
class SelectionScoring:
    total_score: Decimal
    total_possible: Decimal              # = contract.total_points (ACHIEVABLE)
    excluded: FrozenSet[ScopeKey]        # scopes that count toward neither total

    def is_counted(self, key: ScopeKey) -> bool:
        return key not in self.excluded


def score_with_selection(
    scopes: Sequence[ScopeScore],
    contract: GradingRubricContract,
) -> SelectionScoring:
    """Compute (numerator, denominator, excluded-scope set) from CURRENT scores.

    Non-selection contracts (no groups) reduce to today's arithmetic exactly:
    nothing is excluded, the numerator is Σ awarded, and the denominator is
    Σ q.total_points — which is what `Σ scope.points_possible` already equalled,
    by INV-1/INV-2. That equivalence is asserted in the tests.
    """
    # Question -> its scopes' awarded total (a question's score is the sum of its
    # scopes, whether it has one direct scope or many leaf scopes).
    by_question: Dict[str, Decimal] = {}
    scopes_of_question: Dict[str, List[ScopeKey]] = {}
    for s in scopes:
        by_question[s.question_id] = by_question.get(s.question_id, Decimal("0")) + s.awarded
        scopes_of_question.setdefault(s.question_id, []).append(s.key)

    excluded: set[ScopeKey] = set()

    # Fast path: no selection groups ⇒ nothing can be excluded. Kept explicit (rather
    # than falling out of the loop) so the overwhelmingly common non-selection rubric
    # never touches the ranking machinery at all.
    if not getattr(contract, "selection_groups", None):
        return SelectionScoring(
            total_score=sum((s.awarded for s in scopes), Decimal("0")),
            total_possible=contract.total_points,
            excluded=frozenset(),
        )

    # Deterministic tie-break: contract question order. Two members tying on awarded
    # points (very common — e.g. several unanswered questions all at 0) must resolve
    # the same way on every run, or the frozen marks would be non-reproducible.
    order: Dict[str, int] = {
        q.question_id: i for i, q in enumerate(contract.questions)
    }

    for group in contract.selection_groups:
        members = [qid for qid in group.of_question_ids if qid in scopes_of_question]
        if not members:
            continue
        ranked = sorted(
            members,
            key=lambda qid: (-by_question.get(qid, Decimal("0")), order.get(qid, 1_000_000)),
        )
        for qid in ranked[group.choose_k:]:          # everything past the best-k
            excluded.update(scopes_of_question[qid])

    total_score = sum(
        (s.awarded for s in scopes if s.key not in excluded), Decimal("0")
    )
    return SelectionScoring(
        total_score=total_score,
        # SINGLE SOURCE. Never Σ scope.points_possible — that re-derivation is the
        # exact bug this module exists to kill.
        total_possible=contract.total_points,
        excluded=frozenset(excluded),
    )
