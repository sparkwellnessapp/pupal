"""
plan/v6 — deterministic ids, option values and hashes (PR_grader_v6_options.md
§3.2, §3.3, §3.5). Pure: no I/O, no model, no clock.

D-LAW-2: the model never emits a number. Every value here is computed by code
from the teacher's own figures (points, marker amounts, bands) and from the
closed fraction enum the planner chose.

[AM-G4, owner 2026-09-27] ONE rounding rule for every value builder, new and
legacy: `snap_half_up` = ROUND_HALF_UP onto the grid. It replaces the spec's
original `floor_to_grid` and matches the rounding v5 already applied to its
terminal totals, so a legacy count prices exactly as v5 priced it.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal
from typing import Dict, Iterable, List, Sequence, Tuple, Union

from app.agents.grader.plan_schemas import (
    CheckOption,
    PartialFraction,
    PlanCheckV6,
    TerminalPlanV6,
)

# ── copy (labels code writes itself; everything else is the teacher's or the planner's)
ABSENT_LEVEL_LABEL = "לא נמצאה תשובה"          # §3.3: `levels` absent option
FALLBACK_FULL_LABEL = "קיים ותקין"              # §5.6 deterministic fallback
FALLBACK_ABSENT_LABEL = "לא נמצא"
FAULT_NONE_LABEL = "ללא הטעות הזו"
NOTE_NONE_LABEL = "לא רלוונטי"


def count_label(k: int, n: int) -> str:
    return f"{k} מתוך {n} נכונים"


FRACTION_VALUE: Dict[PartialFraction, Decimal] = {
    PartialFraction.QUARTER: Decimal("0.25"),
    PartialFraction.HALF: Decimal("0.5"),
    PartialFraction.THREE_QUARTERS: Decimal("0.75"),
}

MAX_COUNT_UNITS = 40          # §3.3: N+1 ≤ 41; beyond it, STOP and report
_ROLE_PREFIX = {"credit": "c", "fault": "f", "note": "n"}


# ═══════════════════════════════════════════════════════════════════════════
# §3.2 ids
# ═══════════════════════════════════════════════════════════════════════════

def check_id(priced_terminal_id: str, role: str, n: int) -> str:
    """`{terminal}.c{n}` credit · `.f{n}` fault · `.n{n}` note; n is 1-based in
    plan order within the terminal."""
    if role not in _ROLE_PREFIX:
        raise ValueError(f"unknown check role {role!r}")
    if n < 1:
        raise ValueError(f"check ordinal is 1-based, got {n}")
    return f"{priced_terminal_id}.{_ROLE_PREFIX[role]}{n}"


# ═══════════════════════════════════════════════════════════════════════════
# §3.3 values
# ═══════════════════════════════════════════════════════════════════════════

def snap_half_up(x: Decimal, grid: Decimal) -> Decimal:
    """[AM-G4] The one rounding rule: ROUND_HALF_UP onto the grid."""
    return (x / grid).to_integral_value(rounding=ROUND_HALF_UP) * grid


def credit_binary_options(max_value: Decimal, full_label: str,
                          absent_label: str) -> List[CheckOption]:
    return [CheckOption(option_id="full", label_he=full_label, value=max_value),
            CheckOption(option_id="absent", label_he=absent_label, value=Decimal("0"))]


def credit_ladder_options(max_value: Decimal, full_label: str,
                          partials: Sequence[Tuple[str, PartialFraction]],
                          absent_label: str, grid: Decimal
                          ) -> Tuple[List[CheckOption], List[str]]:
    """(options, collapsed labels). A partial is dropped — and reported as
    `partial_collapsed` telemetry — when its snapped value is 0, equals the
    max, or duplicates an option already kept (§3.3, rule unchanged by AM-G4).
    Kept partials are ordered by descending value and numbered p1, p2, …"""
    kept: List[Tuple[Decimal, str]] = []
    seen = {max_value, Decimal("0")}
    collapsed: List[str] = []
    for label, fraction in partials:
        v = snap_half_up(max_value * FRACTION_VALUE[PartialFraction(fraction)], grid)
        if v in seen:
            collapsed.append(label)
            continue
        seen.add(v)
        kept.append((v, label))
    kept.sort(key=lambda p: p[0], reverse=True)
    options = [CheckOption(option_id="full", label_he=full_label, value=max_value)]
    options += [CheckOption(option_id=f"p{i + 1}", label_he=label, value=v)
                for i, (v, label) in enumerate(kept)]
    options.append(CheckOption(option_id="absent", label_he=absent_label, value=Decimal("0")))
    return options, collapsed


def levels_options(bands: Sequence[Tuple[str, Decimal]],
                   absent_label: str = ABSENT_LEVEL_LABEL) -> List[CheckOption]:
    """One option per C8-lite band, in band order (Q-7), `L1…Lk`; an `absent`
    option (0) is added ONLY when no band is 0."""
    options = [CheckOption(option_id=f"L{i + 1}", label_he=label, value=Decimal(value))
               for i, (label, value) in enumerate(bands)]
    if all(Decimal(v) != 0 for _, v in bands):
        options.append(CheckOption(option_id="absent", label_he=absent_label, value=Decimal("0")))
    return options


def count_options(points_possible: Decimal, n: int, grid: Decimal) -> List[CheckOption]:
    """R-E Case 1: `n{N}…n0`, value(n_k) = snap_half_up(P·k/N) [AM-G4];
    value(n_N) is exactly P and value(n0) is 0. Neighbouring counts may share
    a value — count is exempt from V12's uniqueness clause."""
    if n < 1:
        raise ValueError(f"count needs N >= 1, got {n}")
    if n > MAX_COUNT_UNITS:
        raise ValueError(f"count N={n} > {MAX_COUNT_UNITS}: STOP and report (§3.3)")
    options = []
    for k in range(n, -1, -1):
        if k == n:
            v = points_possible
        elif k == 0:
            v = Decimal("0")
        else:
            v = snap_half_up(points_possible * Decimal(k) / Decimal(n), grid)
        options.append(CheckOption(option_id=f"n{k}", label_he=count_label(k, n), value=v))
    return options


MarkerSpec = Tuple[str, Union[Decimal, Sequence[Decimal]], str]


def fault_option_value(amounts: Union[Decimal, Iterable[Decimal]]) -> Decimal:
    """`−marker.amount`, verbatim; for a merged set, `−min(amounts)` — the
    lenient amount (P-6, OD-G4)."""
    if isinstance(amounts, Decimal):
        return -amounts
    return -min(Decimal(a) for a in amounts)


def fault_options(markers: Sequence[MarkerSpec],
                  none_label: str = FAULT_NONE_LABEL) -> List[CheckOption]:
    """`none` (0) first, then `f1…fm` in the markers' textual order. Each marker
    spec is (marker_id, amount | amounts-of-a-merged-set, label)."""
    options = [CheckOption(option_id="none", label_he=none_label, value=Decimal("0"))]
    for i, (marker_id, amounts, label) in enumerate(markers):
        options.append(CheckOption(option_id=f"f{i + 1}", label_he=label,
                                   value=fault_option_value(amounts), marker_id=marker_id))
    return options


def note_options(observed_label: str, none_label: str = NOTE_NONE_LABEL) -> List[CheckOption]:
    """[Q-10] `none` / `observed`, both 0 — a note never moves points."""
    return [CheckOption(option_id="none", label_he=none_label, value=Decimal("0")),
            CheckOption(option_id="observed", label_he=observed_label, value=Decimal("0"))]


def even_split(points: Decimal, n: int, grid: Decimal) -> List[Decimal]:
    """A split terminal shares its points evenly on the grid; the residual goes
    +1 grid unit to the first components in textual order (OD-9). This is a
    partition of the teacher's number, not a rounding of a value, so AM-G4's
    half-up rule does not apply."""
    if n < 1:
        raise ValueError(f"split needs n >= 1, got {n}")
    base = (points / n / grid).to_integral_value(rounding=ROUND_DOWN) * grid
    residual_units = int((points - base * n) / grid)
    return [base + (grid if i < residual_units else Decimal("0")) for i in range(n)]


# ═══════════════════════════════════════════════════════════════════════════
# §3.5 hashing
# ═══════════════════════════════════════════════════════════════════════════

def canonical_decimal(d: Decimal) -> str:
    """One spelling per value: `4.00` → "4", `0.50` → "0.5", no exponent."""
    s = format(Decimal(d).normalize(), "f")
    return "0" if s in ("-0", "0") else s


def _canon(o):
    if isinstance(o, Decimal):
        return canonical_decimal(o)
    if isinstance(o, str):
        return unicodedata.normalize("NFC", o)
    if isinstance(o, dict):
        return {unicodedata.normalize("NFC", str(k)): _canon(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_canon(v) for v in o]
    return o


def canonical_json(obj) -> str:
    """Keys sorted, Decimals normalized, strings NFC, UTF-8, no whitespace."""
    return json.dumps(_canon(obj), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _terminal_doc(t: TerminalPlanV6) -> dict:
    return {"terminal_id": t.terminal_id, "points_possible": t.points_possible,
            "interpretation_notes_he": list(t.interpretation_notes_he)}


def _check_doc(c: PlanCheckV6) -> dict:
    # Built from attributes, not model_dump: the models' serializers turn
    # Decimals into their literal spelling, and "4" vs "4.00" must not move
    # the hash.
    return {"check_id": c.check_id, "role": c.role, "shape": c.shape,
            "description_he": c.description_he, "source_span": c.source_span,
            "options": [{"option_id": o.option_id, "label_he": o.label_he,
                         "value": o.value, "marker_id": o.marker_id} for o in c.options],
            "requires": c.requires, "charge_group": c.charge_group,
            "priced_terminal_id": c.priced_terminal_id,
            "equivalence_note_he": c.equivalence_note_he,
            "evidence_required": c.evidence_required, "origin": c.origin}


def plan_hash(terminals: Sequence[TerminalPlanV6], checks: Sequence[PlanCheckV6]) -> str:
    """sha256 of the canonical JSON of terminals + checks (§3.5). Same inputs →
    same hash; a Decimal's spelling and a string's Unicode form never move it."""
    doc = {"terminals": [_terminal_doc(t) for t in terminals],
           "checks": [_check_doc(c) for c in checks]}
    return hashlib.sha256(canonical_json(doc).encode("utf-8")).hexdigest()


def config_hash(*, compiler_version: str, planner_model: str, planner_prompt_version: str,
                pack_id: str, pack_version: str) -> str:
    """sha256 of every input that decides a plan other than the contract (§3.5)."""
    doc = {"compiler_version": compiler_version, "planner_model": planner_model,
           "planner_prompt_version": planner_prompt_version,
           "pack_id": pack_id, "pack_version": pack_version}
    return hashlib.sha256(canonical_json(doc).encode("utf-8")).hexdigest()
