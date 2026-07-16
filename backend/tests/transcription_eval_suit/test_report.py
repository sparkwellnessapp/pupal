"""Report-rendering regression tests. Zero mocks; runs in `pytest -q`.

These pin the end-to-end observability the summary must expose: BOTH surfaces
(P1 perception and E2E after P2 segmentation), the P1→E2E ratio delta, and the
Phase-2 segmentation-health block (coverage / missed / extra keys / routing
notes) — so a high-fidelity P1 that collapses at E2E is never hidden again.
"""
from pathlib import Path
from types import SimpleNamespace

from .report import write_summary, write_doc_report


def _p1(ratio, cov=1.0, passed=False, reasons=None):
    return {"doc_ratio_strict": ratio, "doc_ratio_lenient": ratio, "coverage": cov,
            "missing_pages": [], "extra_pages": [], "critical": {},
            "pages": [], "gate": {"passed": passed, "reasons": reasons or []}}


def _e2e(ratio, cov, missed, extra, passed=False, reasons=None):
    return {"doc_ratio_strict": ratio, "doc_ratio_lenient": ratio, "coverage": cov,
            "missed_keys": missed, "extra_keys": extra, "critical": {},
            "answers": [], "gate": {"passed": passed, "reasons": reasons or []}}


def _results(records, *, worst, mode="per_doc"):
    return {
        "prompt_version": "t1.2", "registry_as_of": "2026-06-11",
        "config_name": "v0", "mode": mode,
        "models": {"m": {"model_id": "m", "tier": "frontier"}},
        "records": records,
        "aggregates": {
            "accuracy_gate_pass_all_docs": False, "cost_gate_pass": True,
            "cost_avg_per_doc_usd": 0.049, "parse_failure_total": 0,
            "flag_metrics_trustworthy": False, "n_fixtures": len(records),
            "worst_doc": worst,
            "latency_ms": {"median": 80000.0, "min": 70000.0, "max": 128000.0},
            "per_doc": {},  # unused by the new table (read from records)
        },
    }


def test_summary_exposes_both_surfaces_and_segmentation_tax(tmp_path):
    # omer: perfect P1, collapsed E2E — the case the old summary hid.
    records = [
        {"doc_id": "omer", "parse_failures": 0, "parse_failure_finish_reasons": [],
         "stage_ms": {"p1_call_max": 1.0, "p2_call": 1.0}, "spec_mismatches": [],
         "routing_notes": ["merged Q2.ג into Q2"],
         "p1": _p1(0.9838, passed=False, reasons=["method_call_recall 0.789 < 1.0"]),
         "e2e": _e2e(0.7149, 0.83, missed=[[2, "ג"]], extra=[[2, None]], passed=False,
                     reasons=["doc_ratio_strict 0.7149 < 0.98", "coverage 0.83 < 1.0"])},
    ]
    write_summary(tmp_path, _results(records, worst="omer"), cost_ceiling=0.08)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")

    # Both surfaces in the per-doc table, with the delta.
    assert "P1 ratio" in text and "E2E ratio" in text and "Δ P1→E2E" in text
    assert "0.9838" in text and "0.7149" in text
    assert "-0.2689" in text  # the segmentation tax for omer, made explicit
    # Phase-2 segmentation health surfaces coverage + the dropped sub-question.
    assert "Phase-2 segmentation health" in text
    assert "Q2.ג" in text                 # missed key, human-readable
    assert "Q2 (whole)" in text           # the stray whole-question bucket (extra)
    assert "merged Q2.ג into Q2" in text  # routing note surfaced
    assert "Segmentation tax" in text
    # Gate failures show the E2E surface (the old `seen` dedup hid it).
    assert "[E2E]" in text and "coverage 0.83 < 1.0" in text


def test_summary_p1_only_still_renders(tmp_path):
    records = [
        {"doc_id": "dan", "parse_failures": 0, "parse_failure_finish_reasons": [],
         "stage_ms": {"p1_call_max": 1.0}, "spec_mismatches": [], "routing_notes": [],
         "p1": _p1(0.94, passed=False, reasons=["doc_ratio_strict 0.94 < 0.98"]),
         "e2e": None},
    ]
    write_summary(tmp_path, _results(records, worst="dan", mode="p1_only"),
                  cost_ceiling=0.08)
    text = (tmp_path / "summary.md").read_text(encoding="utf-8")
    assert "Phase-2 segmentation health" not in text   # no P2 ran
    assert "P1 ratio" in text and "E2E ratio" not in text
    assert "[P1] doc_ratio_strict 0.94 < 0.98" in text


def test_doc_report_e2e_shows_coverage_and_routing(tmp_path):
    rec = {"doc_id": "omer", "parse_failures": 0, "parse_failure_finish_reasons": [],
           "stage_ms": {}, "spec_mismatches": [],
           "routing_notes": ["merged Q2.ג into Q2"],
           "p1": _p1(0.98, passed=True),
           "e2e": _e2e(0.71, 0.83, missed=[[2, "ג"]], extra=[[2, None]], passed=False,
                       reasons=["coverage 0.83 < 1.0"])}
    results = {"records": [rec]}
    write_doc_report(tmp_path, "omer", results, outputs={}, raw_gold=None, draft_gold=None)
    text = (tmp_path / "report_omer.md").read_text(encoding="utf-8")
    assert "Coverage 0.83" in text
    assert "missed Q2.ג" in text and "extra Q2 (whole)" in text
    assert "Routing notes" in text and "merged Q2.ג into Q2" in text
