"""
The regression gate — REAL API calls. Excluded from `pytest -q` by an
environment guard (CLAUDE.md forbids live LLM calls in the default suite):

    RUN_TRANSCRIPTION_EVAL=1 PYTHONPATH=. python -m pytest -q \\
        tests/transcription_eval_suit/test_eval_gate.py

Asserts the current run against the committed baseline snapshot
(baselines/<config>.json — commit one by copying a blessed results.json).
Gate clauses:
  - conjunctive accuracy gate passes on EVERY doc
  - cost_avg_per_doc <= $0.08 (locked ceiling)
  - latency median <= baseline median * (1 + LATENCY_TOL)
  - parse failures <= baseline
Flag-recall clauses activate only at n >= 10 fixtures (C1 honesty rule).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

SUITE_DIR = Path(__file__).parent
LATENCY_TOL = 0.25

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_TRANSCRIPTION_EVAL") != "1",
    reason="real-API eval gate; set RUN_TRANSCRIPTION_EVAL=1 to run",
)


def _fixtures_present() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in (SUITE_DIR / "raw_benchmarks").glob("*.md")))


@pytest.mark.parametrize("config_name", ["v0"])
def test_eval_gate(config_name: str):
    from .pipelines import PipelineConfig
    from .runner import COST_CEILING_USD, RunPlan, run_plan, _load_config

    fixtures = _fixtures_present()
    if not fixtures:
        pytest.skip("no fixtures on disk")

    plan = RunPlan(
        config=_load_config(config_name), config_name=config_name,
        fixtures=fixtures, repeats=3, mode="per_doc",
        exam_spec_path=os.environ.get("EXAM_SPEC", "exam_spec.json"),
    )
    out_dir = run_plan(plan)
    results = json.loads((out_dir / "results.json").read_text(encoding="utf-8"))
    agg = results["aggregates"]

    assert agg["accuracy_gate_pass_all_docs"], (
        f"accuracy gate failed; see {out_dir}/summary.md for named reasons"
    )
    assert agg["cost_gate_pass"], (
        f"cost ${agg['cost_avg_per_doc_usd']:.4f}/doc exceeds ${COST_CEILING_USD}"
    )

    baseline_path = SUITE_DIR / "baselines" / f"{config_name}.json"
    if baseline_path.exists():
        base = json.loads(baseline_path.read_text(encoding="utf-8"))
        b_agg = base["aggregates"]
        assert (agg["latency_ms"]["median"]
                <= b_agg["latency_ms"]["median"] * (1 + LATENCY_TOL)), "latency regression"
        assert agg["parse_failure_total"] <= b_agg["parse_failure_total"], (
            "parse-failure regression"
        )
    else:
        pytest.skip(f"no baseline committed at {baseline_path}; "
                    f"bless this run by copying results.json there")
