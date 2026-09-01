"""
V11 — deduction completeness (plan-gen/v2, owner ruling 2026-09-01).

The detector (`prompt.detect_deductions`) finds every deduction phrase in a
scope deterministically. V11 is the other half: the model must DISPOSE of every
one, and the disposition must be honoured by the checks it emitted.

Phase 0 measured why this is deterministic work. The generator read the concept
of the missed tariff — it emitted `charge_group="max_instead_of_min"` — and
still anchored it to the wrong sub-criterion at the wrong amount. Finding the
phrase, copying its number, and knowing whose text contains it are string and
lookup tasks. Only "which sub-criterion does this modify" is judgement, and V11
narrows even that to a bounded choice among named candidates.

Errors are strings tagged `V11:` so they feed the existing repair loop verbatim,
exactly like V1–V10.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Sequence


def validate_dispositions(markers: Sequence,
                          dispositions: Sequence,
                          terminals: Sequence) -> List[str]:
    """`markers` are DetectedDeduction, `terminals` are TerminalPlan."""
    errs: List[str] = []

    by_marker: Dict[str, list] = {}
    for d in dispositions:
        by_marker.setdefault(d.marker_id, []).append(d)

    checks_by_id = {c.check_id: (t, c) for t in terminals for c in t.checks}

    for marker in markers:
        got = by_marker.get(marker.marker_id, [])
        if not got:
            errs.append(f"V11: detected deduction [{marker.marker_id}] "
                        f"({marker.quote[:60]!r}) has NO disposition; every "
                        f"detected marker must be disposed of")
            continue
        if len(got) > 1:
            errs.append(f"V11: [{marker.marker_id}] has {len(got)} dispositions; "
                        f"exactly one is required")
            continue

        d = got[0]

        # A "do not deduct" phrase can never become a deduction.
        if marker.polarity == "no_deduct" and d.disposition == "tariff":
            errs.append(f"V11: [{marker.marker_id}] is a NO-DEDUCT phrase "
                        f"({marker.quote[:60]!r}) and may not be disposed as a "
                        f"tariff")
            continue

        if d.disposition == "not_a_deduction":
            if not (d.reason or "").strip():
                errs.append(f"V11: [{marker.marker_id}] disposed "
                            f"'not_a_deduction' with no reason")
            continue

        if not d.check_id:
            errs.append(f"V11: [{marker.marker_id}] disposed "
                        f"'{d.disposition}' with no check_id")
            continue

        found = checks_by_id.get(d.check_id)
        if found is None:
            errs.append(f"V11: [{marker.marker_id}] names check "
                        f"{d.check_id!r}, which does not exist")
            continue
        terminal, check = found

        if d.disposition == "tariff":
            if check.kind != "tariff":
                errs.append(f"V11: [{marker.marker_id}] disposed 'tariff' but "
                            f"{d.check_id} is kind={check.kind!r}")
            elif check.tariff_amount != marker.amount:
                # No rounding, no substitution — the teacher wrote a number.
                errs.append(f"V11: [{marker.marker_id}] detected amount "
                            f"{marker.amount} but {d.check_id} carries "
                            f"{check.tariff_amount}; copy the number the "
                            f"teacher wrote")
            if (marker.candidate_terminal_ids
                    and terminal.terminal_id not in marker.candidate_terminal_ids):
                errs.append(f"V11: [{marker.marker_id}] anchored to "
                            f"{terminal.terminal_id}, which is not among its "
                            f"candidates {list(marker.candidate_terminal_ids)}")
        elif d.disposition == "note_only":
            if check.kind != "note_only":
                errs.append(f"V11: [{marker.marker_id}] disposed 'note_only' "
                            f"but {d.check_id} is kind={check.kind!r}")

    unknown = set(by_marker) - {m.marker_id for m in markers}
    for marker_id in sorted(unknown):
        errs.append(f"V11: disposition names unknown marker {marker_id!r}")

    return errs


def escape_hatch_count(dispositions: Sequence) -> int:
    """WATCHED, not gated (owner, 2026-09-01).

    `not_a_deduction` is V11's only way out. It is legitimate — a rubric can
    mention a number that is not a grading rule — but inflation here is the
    signal that it is being used to dodge the rule rather than to describe the
    text, so it is counted and reported every run.
    """
    return sum(1 for d in dispositions if d.disposition == "not_a_deduction")
