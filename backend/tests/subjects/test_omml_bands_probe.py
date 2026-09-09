"""The OMML + bands probe, pinned (execution plan §5 Phase 4a, and P-3).

The plan asked that the probe's band table become a pinned benchmark rather than "today's
coincidence". A provider result cannot be asserted from a test, so it is pinned in two halves:

  * DETERMINISTIC, here and now — the DOCX renders with its OMML equation intact
    (`omml_seen == omml_rendered`, P-3) and the band table present with 10 / 6 / 4.
  * RECORDED — the extraction that turned that table into three criteria at 10 / 6 / 4 is a real
    run, stored under `snapshots/2026-09-09_multisubject-probe/`, and this test asserts against
    the recorded draft so a change in the flattening rule shows up as a diff rather than as a
    memory.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from app.services.docx_v3.parser_render import render_docx_to_markdown_with_stats

HERE = Path(__file__).resolve().parents[1]           # backend/tests
PROBE = HERE / "rubric_eval_suite" / "fixtures" / "probes" / "omml_bands_probe.docx"
SNAPSHOT = HERE / "rubric_eval_suite" / "snapshots" / "2026-09-09_multisubject-probe"


# --- deterministic: the render, no provider -------------------------------------------------

def test_the_probe_renders_its_equation_and_its_band_table():
    md, stats = render_docx_to_markdown_with_stats(PROBE.read_bytes())
    # P-3: an equation is never silently dropped
    assert stats.omml_seen == 1
    assert stats.omml_rendered == stats.omml_seen, "an OMML equation was seen and not rendered"
    assert "חשבו את הגבול" in md
    # the ladder reaches the model as a table with its three top bands
    assert "10 / 5 / 0" in md and "6 / 3 / 0" in md and "4 / 2 / 0" in md
    for name in ("תוכן", "ארגון", "שפה"):
        assert name in md


# --- recorded: what the real extraction made of it ------------------------------------------

@pytest.mark.skipif(not (SNAPSHOT / "probe_summary.json").exists(),
                    reason="the recorded probe run is not in the tree")
def test_the_recorded_run_flattened_each_ladder_to_its_top_band():
    s = json.loads((SNAPSHOT / "probe_summary.json").read_text(encoding="utf-8"))
    # 3 criteria, not 9: one per ladder, each at the TOP band (D-3 beta path, P-12)
    assert s["criterion_points"] == ["10.0", "6.0", "4.0"]
    assert Decimal(s["total_points"]) == Decimal("20")
    assert s["compile"].startswith("OK total=20")
    assert s["question_types"] == ["short_answer"]      # never coding_task (the profile default)
    assert s["retry_count"] == 0
    assert (s.get("render") or {}).get("omml_seen") == (s.get("render") or {}).get("omml_rendered")
    # the ladder the teacher wrote is still legible on every criterion
    for _cid, _pts, description in s["criteria"]:
        assert "מלא" in description and "חלקי" in description and "חסר" in description
