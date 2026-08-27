"""
Reporting guards [ruling item 6, 2026-08-24]: the fixture report displays GT
notes ([C1-TABLE] terminals must be visible to the read-by-hand ritual), and
Tier-3 per-fixture counts carry [C1-TABLE] terminals + ungradable-scope
terminals, with the totals-inclusion mark. Zero API calls.
"""
from __future__ import annotations

from app.schemas.ontology_types import FlaggedOutcome, FlagReason

from . import synth
from .reporting import aggregate, write_fixture_report
from .scoring import score_trial


def _trial():
    gt = synth.make_gt(synth.GT_PERFECT,
                       ungradable=[("q2", "א", "garbled_structure")])
    noted = gt.model_copy(update={"terminals": [
        t.model_copy(update={"note": "[C1-TABLE] columns collapsed; read by row"})
        if t.terminal_id == "q1.c0" else t
        for t in gt.terminals]})
    bundle = synth.make_bundle(noted)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    o1 = synth.draft_from_gt(bundle, noted).scope_outcomes[0]
    o2 = synth.make_scope_outcome(
        s["q2"], {"q2.א.c0": ("0", 0.3, None, None)},
        extra_flags=[FlaggedOutcome(question_id="q2", reason=FlagReason.LLM_UNCERTAINTY)])
    draft = synth.make_draft(bundle, [o1, o2])
    ts = score_trial(draft, bundle, trial_index=0, cost_usd_value=0.03,
                     cost_ceiling=0.10)
    return bundle, draft, ts


def test_fixture_report_displays_gt_note_and_totals_mark(tmp_path):
    bundle, draft, ts = _trial()
    p = write_fixture_report(bundle.name, [ts], {0: draft}, tmp_path)
    text = p.read_text(encoding="utf-8")
    assert "[C1-TABLE] columns collapsed" in text          # the note is VISIBLE
    assert "total includes 1 ungradable-scope terminal" in text   # C-2 mark


def test_aggregate_counts_c1_table_and_ungradable_terminals():
    _, _, ts = _trial()
    agg = aggregate([ts], k=1)
    block = agg["per_fixture"]["synthetic"]
    assert block["c1_table_terminals"] == 1
    assert block["ungradable_terminals"] == 1


# ---------------------------------------------------------------------------
# Owner ruling 2026-08-27 (E7-record correction b): instability must be reported
# in BOTH measures every run — how MANY terminals move, and how FAR the test
# total moves. E7 reported only the first (37.4% -> 30.0%, "improved") while
# dan's per-test spread went 3.25 -> 14.00, crossing two grade boundaries on
# identical input. One measure hid the other.
# ---------------------------------------------------------------------------

def test_aggregate_reports_both_instability_measures():
    from .reporting import aggregate
    from . import synth
    from .scoring import score_trial
    gt = synth.make_gt(synth.GT_PERFECT)
    bundle = synth.make_bundle(gt)
    s = {x.question_id: x for x in bundle.gradable_test.scopes}
    trials = []
    # two trials that differ ONLY in total (same count of moving terminals)
    for i, award in enumerate(("2", "0")):
        o1 = synth.make_scope_outcome(s["q1"], {
            "q1.c0": (award, 0.9, synth.ANSWER_Q1[:8], None),
            "q1.c1.s0": ("1", 0.9, synth.ANSWER_Q1[:8], None),
            "q1.c1.s1": ("2", 0.9, synth.ANSWER_Q1[:8], None)})
        o2 = synth.make_scope_outcome(s["q2"], {"q2.א.c0": ("4", 0.9, synth.ANSWER_Q2A[:8], None)})
        trials.append(score_trial(synth.make_draft(bundle, [o1, o2]), bundle,
                                  trial_index=i, cost_usd_value=0.03, cost_ceiling=0.10))
    agg = aggregate(trials, k=2)
    inst = agg["instability"]
    # measure 1: how many terminals move
    assert "terminals_moving_pct" in inst and inst["terminals_moving_pct"] > 0
    # measure 2: how FAR the test total moves — the one E7 omitted
    assert inst["max_ai_total_spread"] == 2.0, inst
    assert inst["worst_spread_fixture"] == "synthetic"
    assert inst["per_fixture_ai_total_spread"]["synthetic"] == 2.0
