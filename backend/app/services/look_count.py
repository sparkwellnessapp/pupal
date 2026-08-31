"""
look_count — how many things on this test need the teacher's eye (PR-G8, §1.5).

DETERMINISTIC markers only. This is a routing number, not a quality score: it
tells her where to look first on an evening with thirty papers, so it must be
reproducible from the draft alone and must never be a model's opinion about its
own confidence.

The markers (spec §1.5): evidence that did not validate (not_found / fuzzy),
bounds-clamped, closed-world, a skipped scope, a failed scope. Audit marks are
NOT counted — the consistency audit is deferred (ruling R-1) and counting a
surface that does not exist would inflate every card by nothing.

One look per DISTINCT marker. A scope carrying two different problems earns two
looks; the same problem seen twice earns one.
"""
from __future__ import annotations

from typing import Set, Tuple

# flags that mean "a human should check this", as opposed to the informational
# ones the pricer records for the eval suite
_LOOK_FLAGS = {
    "bounds_clamped", "closed_world_violation", "unverified_check",
    "evidence_unverified",
}
# v3-era drafts carry no checks, so their quote problems live only as flags.
# Counted ONLY for a leaf with no checks — a v5 leaf would otherwise be counted
# twice, once as a flag and once as the check's quote_status.
_V3_QUOTE_FLAGS = {"quote_not_found", "fuzzy_match"}
_UNVALIDATED = {"not_found", "fuzzy"}


def look_count(draft) -> int:
    """The number of distinct things to look at on this graded test."""
    seen: Set[Tuple[str, str]] = set()

    for scope in draft.scope_outcomes or []:
        scope_id = (scope.question_id if scope.sub_question_id is None
                    else f"{scope.question_id}.{scope.sub_question_id}")

        # An excluded scope was never owed. Counting it would send her hunting
        # for a problem that does not exist — the needs_eyes over-count lesson
        # (CLAUDE.md §3.5a).
        if scope.graded_by == "excluded_by_selection":
            continue
        if scope.graded_by in ("skipped_no_answer", "failed"):
            seen.add((scope_id, scope.graded_by))
            continue

        for criterion in scope.criterion_outcomes or []:
            for leaf in (criterion.sub_criterion_outcomes or [criterion]):
                terminal_id = (getattr(leaf, "sub_criterion_id", None)
                               or criterion.criterion_id)
                has_checks = bool(leaf.checks)
                for flag in (leaf.flags or []):
                    reason = getattr(flag.reason, "value", flag.reason)
                    if reason in _LOOK_FLAGS:
                        seen.add((terminal_id, reason))
                    elif reason in _V3_QUOTE_FLAGS and not has_checks:
                        seen.add((terminal_id, reason))
                for check in (leaf.checks or []):
                    # A `met` on a span that did not validate is INVENTED CREDIT
                    # and is invisible in the score — the points look ordinary.
                    # This is the case the number exists for.
                    if check.quote_status in _UNVALIDATED:
                        seen.add((check.check_id, check.quote_status))
    return len(seen)
