"""
diagnostics.py — the glue that runs the three additive diagnostics (Hebrew,
tables, arrows) over one document's outputs, for the runner (MISSION §4.3).

NOTHING HERE FEEDS THE GATE. `gate_pass`, `check_goal.sh` and every number they
read are untouched; these are reported beside them. If a diagnostic should become
a gate, that is a proposal to surface (the rejected-Policy-1 precedent).
"""
from __future__ import annotations

from app.services.transcription.two_phase.relocation import Relocation, relocate

from .diag_arrows import score_arrows
from .diag_hebrew import score_units
from .diag_tables import TableScore, score_tables
from .insertion_cases import Case, cases_for
from .keys import normalize_key


def _tables(gold: dict, pred: dict) -> dict:
    total = TableScore()
    for k, g in gold.items():
        total.add(score_tables(g, pred.get(k, ""), where=str(k)))
    return total.as_dict()


def _answers_by_key(gold_doc, answers: dict) -> tuple[dict, dict]:
    gold = {normalize_key(a.key): a.answer_text for a in gold_doc.answers}
    pred: dict = {}
    for k, v in answers.items():
        nk = normalize_key(k)
        pred[nk] = (pred[nk] + "\n" + v) if nk in pred else v
    return gold, pred


def token_totals(trace) -> dict:
    """Per-phase token and cost totals, from the calls the trace recorded. This is
    what the Bet-1 cost pre-screen reprices, so it must count EVERY call —
    including a parse re-request and any optional pass."""
    out: dict = {}
    for c in trace.calls:
        t = out.setdefault(c.phase, {"calls": 0, "in": 0, "cached_in": 0,
                                     "out": 0, "reasoning": 0, "cost_usd": 0.0})
        t["calls"] += 1
        t["in"] += c.usage.input_tokens
        t["cached_in"] += c.usage.cached_input_tokens or 0
        t["out"] += c.usage.output_tokens
        t["reasoning"] += getattr(c.usage, "reasoning_tokens", None) or 0
        t["cost_usd"] += c.cost_usd
    return out


def gold_relocation(fixture: str, raw_pages: dict[int, str]):
    """§4.4 — the owner's cases applied to the GOLD pages, so P2 in `p2_only` is
    measured on the student's INTENDED order, exactly as it is measured on gold
    pages today. Decoys carry no instruction. Returns (pages, result)."""
    live = [c for c in cases_for(fixture) if c.kind in ("insertion", "attachment")]
    res = relocate(raw_pages, [c.instruction() for c in live])
    return res.pages, res


def compute(fixture: str, *, raw_gold=None, draft_gold=None,
            pages: dict | None = None, answers: dict | None = None,
            relocations: tuple[Relocation, ...] = (),
            pages_before_relocation: dict | None = None) -> dict:
    """All three diagnostics for one document. `pages` is P1's output (physical
    placement, scored against raw GT); `answers` is the e2e output (scored
    against draft GT); `relocations` are the pipeline's own records, whose
    offsets live in `pages_before_relocation`."""
    d: dict = {}
    if pages is not None and raw_gold is not None:
        gold_pages = raw_gold.as_dict()
        d["hebrew_p1"] = score_units(gold_pages, pages)
        d["hebrew_p1_prose"] = score_units(gold_pages, pages, markers=False)
        d["tables_p1"] = _tables(gold_pages, pages)
    if answers is not None and draft_gold is not None:
        g, p = _answers_by_key(draft_gold, answers)
        d["hebrew_e2e"] = score_units(g, p)
        d["hebrew_e2e_prose"] = score_units(g, p, markers=False)
        d["tables_e2e"] = _tables(g, p)
    raw_cases = [c.raw for c in cases_for(fixture)]
    if raw_cases:
        d["arrows"] = score_arrows(raw_cases, list(relocations),
                                   pages_before_relocation or pages or {})
    return d
