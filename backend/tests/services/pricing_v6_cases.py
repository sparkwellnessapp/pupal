"""grader-v6 pricer cases — the ONE vocabulary for building pricer inputs.

Used by three consumers, so they cannot drift:
  * `tests/services/test_pricing_v6.py`          the worked examples (§4.5)
  * `tests/services/test_pricing_v6_properties.py` Hypothesis (draw = data.draw)
  * `scripts/gen_pricing_v6_vectors.py`         the committed parity vectors
                                                 (draw = a seeded PRNG)

`build_random_case(draw)` is written against a tiny `Draw` interface so the
SAME construction serves Hypothesis (structured shrinking) and a byte-stable
generator. Hypothesis's own example stream is not stable across library
versions, which a regenerate-clean test would turn into a failure on every
upgrade — hence a seeded PRNG for the committed vectors (A-2).
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from decimal import Decimal
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from app.agents.grader.plan_schemas import PartialFraction, PlanCheckV6
from app.agents.grader.plan_values import (
    count_options,
    credit_binary_options,
    credit_ladder_options,
    even_split,
    fault_options,
    levels_options,
    note_options,
)
from app.services.pricing_v6 import (
    CheckDecision,
    DraftV6View,
    PricingOverlay,
    SelectionGroupView,
    SelectionView,
    ViewCheck,
    ViewTerminal,
)

D = Decimal
GRID = D("0.25")


# ═══════════════════════════════════════════════════════════════════════════
# small builders (hand-written cases)
# ═══════════════════════════════════════════════════════════════════════════

def term(tid: str, p, q: str = "q1", sq: Optional[str] = None) -> ViewTerminal:
    return ViewTerminal(terminal_id=tid, question_id=q, sub_question_id=sq,
                        points_possible=D(str(p)))


def binary(cid: str, tid: str, maxv, desc: str = "רכיב", full: str = "קיים ותקין",
           absent: str = "לא נמצא") -> PlanCheckV6:
    return PlanCheckV6(check_id=cid, role="credit", shape="binary", description_he=desc,
                       source_span=desc, options=credit_binary_options(D(str(maxv)), full, absent),
                       priced_terminal_id=tid, origin="planner")


def ladder(cid: str, tid: str, maxv, partials: Sequence[Tuple[str, PartialFraction]],
           desc: str = "רכיב", grid: Decimal = GRID) -> PlanCheckV6:
    opts, _ = credit_ladder_options(D(str(maxv)), "מלא", list(partials), "לא נמצא", grid)
    return PlanCheckV6(check_id=cid, role="credit", shape="ladder", description_he=desc,
                       source_span=desc, options=opts, priced_terminal_id=tid, origin="planner")


def levels(cid: str, tid: str, bands: Sequence[Tuple[str, object]], desc: str = "רמה") -> PlanCheckV6:
    return PlanCheckV6(check_id=cid, role="credit", shape="levels", description_he=desc,
                       source_span=desc,
                       options=levels_options([(lab, D(str(v))) for lab, v in bands]),
                       priced_terminal_id=tid, origin="compiler")


def count(cid: str, tid: str, p, n: int, desc: str = "תאים", grid: Decimal = GRID) -> PlanCheckV6:
    return PlanCheckV6(check_id=cid, role="credit", shape="count", description_he=desc,
                       source_span=desc, options=count_options(D(str(p)), n, grid),
                       priced_terminal_id=tid, origin="compiler")


def fault(cid: str, tid: str, markers: Sequence[Tuple[str, object, str]],
          requires: Optional[str] = None, group: Optional[str] = None,
          evidence_required: bool = True, desc: str = "טעות") -> PlanCheckV6:
    return PlanCheckV6(check_id=cid, role="fault", shape="fault", description_he=desc,
                       source_span=desc,
                       options=fault_options([(m, D(str(a)), lab) for m, a, lab in markers],
                                             "ללא טעות"),
                       requires=requires, charge_group=group, priced_terminal_id=tid,
                       evidence_required=evidence_required, origin="planner")


def note(cid: str, tid: str, observed: str = "הערה לתלמיד") -> PlanCheckV6:
    return PlanCheckV6(check_id=cid, role="note", shape="note", description_he=observed,
                       source_span=observed, options=note_options(observed),
                       priced_terminal_id=tid, origin="compiler")


@dataclass(frozen=True)
class Sel:
    check: PlanCheckV6
    option_id: Optional[str]
    quote: Optional[str] = "exact"


def view(terminals: Sequence[ViewTerminal], sels: Sequence[Sel], *,
         grid: Decimal = GRID, groups: Sequence[Tuple[Sequence[str], int]] = (),
         total: Optional[Decimal] = None) -> DraftV6View:
    """Checks are given in PLAN ORDER; plan_index is their position."""
    q_order: List[str] = []
    q_points: Dict[str, Decimal] = {}
    for t in terminals:
        if t.question_id not in q_order:
            q_order.append(t.question_id)
        q_points[t.question_id] = q_points.get(t.question_id, D("0")) + t.points_possible
    if total is None:
        total = _achievable(q_order, q_points, groups)
    return DraftV6View(
        precision=grid,
        terminals=list(terminals),
        checks=[ViewCheck(plan=s.check, plan_index=i, model_option_id=s.option_id,
                          quote_status=(s.quote if s.option_id is not None else None))
                for i, s in enumerate(sels)],
        selection=SelectionView(
            total_points=total, question_order=q_order,
            groups=[SelectionGroupView(of_question_ids=list(ids), choose_k=k)
                    for ids, k in groups]),
    )


def _achievable(q_order, q_points, groups) -> Decimal:
    grouped = set()
    total = D("0")
    for ids, k in groups:
        pts = sorted((q_points.get(q, D("0")) for q in ids), reverse=True)
        total += sum(pts[:k], D("0"))
        grouped.update(ids)
    total += sum((q_points[q] for q in q_order if q not in grouped), D("0"))
    return total


def overlay(checks: Optional[Dict[str, CheckDecision]] = None,
            pins: Optional[Dict[str, object]] = None) -> PricingOverlay:
    return PricingOverlay(checks=dict(checks or {}),
                          terminal_points={k: D(str(v)) for k, v in (pins or {}).items()})


# ═══════════════════════════════════════════════════════════════════════════
# the E10 plan — the real bagrut q5.ב.c4 text (AM-G9)
# ═══════════════════════════════════════════════════════════════════════════

E10_TEXT = ("סעיף ב: בדיקת תנאי הקיבולת (קטן או שווה ל-40) ועדכון נכון של התכונה people "
            "בעזרת SetPeople ו-GetPeople הבדיקת הקיבולת עצמה 1 נקודה אם לא השתמשו בפעולה "
            "הפנימית להוריד 2, אם לא השתמשו באף אחת מהן להוריד 3 אם חישבו נכון את סה\"כ ולא "
            "עדכנו את התכונה (כמובן ע\"י setter) להוריד 2")
E10_TID = "q5.ב.c4"


def e10_checks() -> Tuple[PlanCheckV6, PlanCheckV6, PlanCheckV6]:
    """A hand-built plan of the shape the planner is required to produce
    (P-3 one owner per fault, P-4 severities are one check): capacity 1 +
    update 4, and ONE fault check whose three options are the three phrases.
    Phase 2 re-runs E10 on the RECORDED planner output (AM-G9)."""
    capacity = binary(f"{E10_TID}.c1", E10_TID, 1, desc="בדיקת תנאי הקיבולת (קטן או שווה ל-40)")
    update = binary(f"{E10_TID}.c2", E10_TID, 4, desc="עדכון התכונה people")
    tiers = fault(f"{E10_TID}.f1", E10_TID, [
        ("m1", 2, "העדכון נעשה בלי SetPeople"),
        ("m2", 3, "לא נעשה שימוש ב-SetPeople וגם לא ב-GetPeople"),
        ("m3", 2, "הסכום חושב נכון אך התכונה לא עודכנה דרך setter"),
    ], requires=f"{E10_TID}.c2", desc="אופן עדכון התכונה people")
    return capacity, update, tiers


# ═══════════════════════════════════════════════════════════════════════════
# random cases — one construction, two draw sources
# ═══════════════════════════════════════════════════════════════════════════

class Draw:
    """The minimal interface `build_random_case` needs."""
    def int(self, lo: int, hi: int) -> int: ...           # inclusive
    def bool(self, pct: int = 50) -> bool: ...
    def choice(self, seq: Sequence): ...


class PrngDraw(Draw):
    def __init__(self, seed: int) -> None:
        self._r = random.Random(seed)

    def int(self, lo: int, hi: int) -> int:
        return self._r.randint(lo, hi)

    def bool(self, pct: int = 50) -> bool:
        return self._r.randint(1, 100) <= pct

    def choice(self, seq: Sequence):
        return seq[self._r.randrange(len(seq))]


class HypothesisDraw(Draw):
    def __init__(self, data) -> None:
        from hypothesis import strategies as st
        self._d, self._st = data, st

    def int(self, lo: int, hi: int) -> int:
        return self._d.draw(self._st.integers(lo, hi))

    def bool(self, pct: int = 50) -> bool:
        return self._d.draw(self._st.integers(1, 100)) <= pct

    def choice(self, seq: Sequence):
        return seq[self._d.draw(self._st.integers(0, len(seq) - 1))]


_QUOTES = ("exact", "exact", "fuzzy", "not_found", None)
_FRACTIONS = (PartialFraction.QUARTER, PartialFraction.HALF, PartialFraction.THREE_QUARTERS)


def build_random_case(draw: Draw, *, max_questions: int = 3, max_subs: int = 2,
                      max_terminals: int = 3) -> Tuple[DraftV6View, PricingOverlay]:
    """A random, VALID pricer input (every plan would pass V12/V13/V15/V17).
    The size knobs let the committed vectors stay small while Hypothesis
    explores the rich default."""
    grid = draw.choice((D("0.25"), D("0.25"), D("0.5"), D("1")))
    terminals: List[ViewTerminal] = []
    sels: List[Sel] = []
    decisions: Dict[str, CheckDecision] = {}
    pins: Dict[str, Decimal] = {}
    groups_pool = ("g1", "g2")

    n_q = draw.int(1, max_questions)
    for qi in range(n_q):
        qid = f"q{qi + 1}"
        subs = [None] if draw.bool(50) else [chr(ord("א") + i) for i in range(draw.int(1, max_subs))]
        for sq in subs:
            for ti in range(draw.int(1, max_terminals)):
                tid = f"{qid}{'.' + sq if sq else ''}.c{ti}"
                p = grid * draw.int(1, 16)
                terminals.append(ViewTerminal(terminal_id=tid, question_id=qid,
                                              sub_question_id=sq, points_possible=p))
                parts = even_split(p, draw.int(1, 3), grid) if p >= grid * 3 else [p]
                credits: List[PlanCheckV6] = []
                for ci, part in enumerate(parts):
                    cid = f"{tid}.c{ci + 1}"
                    shape = draw.choice(("binary", "binary", "ladder", "count", "levels"))
                    if shape == "ladder":
                        chk = ladder(cid, tid, part,
                                     [(f"p{j}", draw.choice(_FRACTIONS)) for j in range(draw.int(1, 2))],
                                     grid=grid)
                    elif shape == "count":
                        chk = count(cid, tid, part, draw.int(2, 9), grid=grid)
                    elif shape == "levels":
                        n_units = int(part / grid)
                        cuts = sorted({draw.int(0, n_units - 1) for _ in range(draw.int(1, 3))},
                                      reverse=True)
                        bands = [("רמה 1", part)] + [(f"רמה {k + 2}", grid * c)
                                                      for k, c in enumerate(cuts)]
                        chk = levels(cid, tid, bands)
                    else:
                        chk = binary(cid, tid, part)
                    credits.append(chk)
                    sels.append(Sel(chk, _pick(draw, chk), draw.choice(_QUOTES)))
                for fi in range(draw.int(0, 2)):
                    cid = f"{tid}.f{fi + 1}"
                    markers = [(f"{cid}.m{k}", grid * draw.int(1, 12), f"דרגה {k}")
                               for k in range(draw.int(1, 3))]
                    chk = fault(cid, tid, markers,
                                requires=(draw.choice(credits).check_id
                                          if draw.bool(70) else None),
                                # V7: a charge group stays inside one scope, so its
                                # name is scope-local (the draws are unchanged)
                                group=(f"{qid}{'.' + sq if sq else ''}:{draw.choice(groups_pool)}"
                                       if draw.bool(30) else None),
                                evidence_required=draw.bool(85))
                    sels.append(Sel(chk, _pick(draw, chk), draw.choice(_QUOTES)))
                if draw.bool(15):
                    chk = note(f"{tid}.n1", tid)
                    sels.append(Sel(chk, _pick(draw, chk), draw.choice(_QUOTES)))
                if draw.bool(8):
                    pins[tid] = grid * draw.int(0, int(p / grid))

    for s in sels:
        if not draw.bool(15):
            continue
        c = s.check
        if c.role == "credit" and draw.bool(40):
            top = c.options[0].value
            decisions[c.check_id] = CheckDecision(amount=grid * draw.int(0, int(top / grid)))
        else:
            decisions[c.check_id] = CheckDecision(option_id=draw.choice(c.options).option_id)

    groups: List[Tuple[List[str], int]] = []
    q_ids = sorted({t.question_id for t in terminals})
    if len(q_ids) >= 2 and draw.bool(25):
        members = q_ids[: draw.int(2, len(q_ids))]
        groups.append((members, draw.int(1, len(members) - 1)))

    return view(terminals, sels, grid=grid, groups=groups), overlay(decisions, pins)


def _pick(draw: Draw, check: PlanCheckV6) -> Optional[str]:
    roll = draw.int(1, 100)
    if roll <= 5:
        return None                                   # the model said nothing
    if roll <= 7:
        return "zz_foreign"                           # an id not of this check
    return draw.choice(check.options).option_id


GenerateCase = Callable[[Draw], Tuple[DraftV6View, PricingOverlay]]
