"""
Reporting: results.json (machine, stable), summary.md (human headline + gate
table), report_<rubric>.md (per-scope GT|pred|diff for hand reading).

The report files exist to enforce the 'read the diffs by hand every run' rule —
the aggregate metric tells you IF something regressed; the per-scope report tells
you WHERE and suggests the next change.
"""
from __future__ import annotations

import json
import statistics
from pathlib import Path
from typing import List

from .schemas import RubricScore, SuiteResult

# Metrics aggregated worst-case (lower is worse) — worst-rubric over mean.
_WORST_MIN = [
    "question_recall", "question_precision", "subquestion_structure_match",
    "criterion_recall", "criterion_precision", "subcriterion_recall",
    "subcriterion_precision", "point_exactness", "example_solution_fidelity",
]

# Text-fidelity diagnostics (UNGATED — not gate_pass criteria). Optional-valued:
# None means the rubric has no GT text at that level, and such rubrics are
# excluded from the aggregate rather than counted as zeros.
_TEXT_DIAG = [
    "question_text_fidelity_min", "subquestion_text_fidelity_min",
    "text_line_recall_min",
]


def aggregate(per_rubric: List[RubricScore]) -> dict:
    valid = [r for r in per_rubric if r.valid]
    agg: dict = {
        "n_rubrics": len(per_rubric),
        "n_valid": len(valid),
        "n_invalid": len(per_rubric) - len(valid),
        "gate_pass_count": sum(1 for r in per_rubric if r.gate_pass),
        "worst_rubric": {},
        "mean": {},
    }
    if not valid:
        return agg
    for m in _WORST_MIN:
        vals = [(getattr(r, m), r.rubric_name) for r in valid]
        worst_val, worst_name = min(vals, key=lambda x: x[0])
        agg["worst_rubric"][m] = {"value": round(worst_val, 4), "rubric": worst_name}
        agg["mean"][m] = round(statistics.mean(v for v, _ in vals), 4)
    for m in _TEXT_DIAG:
        vals = [(getattr(r, m), r.rubric_name) for r in valid if getattr(r, m) is not None]
        if vals:
            worst_val, worst_name = min(vals, key=lambda x: x[0])
            agg["worst_rubric"][m] = {"value": round(worst_val, 4), "rubric": worst_name}
            agg["mean"][m] = round(statistics.mean(v for v, _ in vals), 4)
        else:
            agg["worst_rubric"][m] = {"value": None, "rubric": None}
            agg["mean"][m] = None
    # boolean gates: count failures + name them
    for m in ["total_points_correct", "selection_match", "annotation_match", "pedagogical_match", "point_sum_consistency"]:
        failed = [r.rubric_name for r in valid if not getattr(r, m)]
        agg[m + "_failures"] = failed
    costs = [r.cost_usd for r in valid if r.cost_usd is not None]
    if costs:
        agg["cost_usd"] = {"max": round(max(costs), 4), "mean": round(statistics.mean(costs), 4)}
    agg["render_loss_total"] = sum(r.render_loss_count for r in valid)
    agg["extraction_loss_total"] = sum(r.extraction_loss_count for r in valid)

    # ---- latency instrument (Phase 0 — ADDITIVE, UNGATED, WATCHED) -------------
    # Worst-case discipline (mean forbidden as a headline): per fixture we report
    # the MEDIAN and MAX t_doc over its valid trials; the headline is the max over
    # fixtures of the per-fixture median (the slowest document a teacher waits on),
    # and the tail is the max over fixtures of the per-fixture max.
    timed = [r for r in valid if r.total_seconds is not None]
    if timed:
        names = sorted({r.rubric_name for r in timed})
        per_fixture: dict = {}
        for name in names:
            recs = [r for r in timed if r.rubric_name == name]
            tot = [r.total_seconds for r in recs]
            rnd = [r.render_seconds for r in recs if r.render_seconds is not None]
            llm = [r.llm_seconds for r in recs if r.llm_seconds is not None]
            intok = [r.input_tokens for r in recs if r.input_tokens is not None]
            outtok = [r.output_tokens for r in recs if r.output_tokens is not None]
            retr = [r.retry_count for r in recs if r.retry_count is not None]
            # llm_seconds covers ONLY Step 1 (_extract_with_retry). The Step 2c Tier-B
            # adjudicator is a SEPARATE LLM call inside total_seconds but outside
            # llm_seconds — recover it from the pedagogical stage timings so it is NOT
            # mis-booked as local CPU overhead (adversarial-review finding, 2026-07-21).
            def _tier_b(r):
                return sum(st.dt_s for st in (r.stage_timings or [])
                           if st.stage == "pedagogical" and st.dt_s) or 0.0
            tierb = [_tier_b(r) for r in recs]
            local = [r.total_seconds - (r.render_seconds or 0.0) - (r.llm_seconds or 0.0) - _tier_b(r)
                     for r in recs]
            per_fixture[name] = {
                "n": len(recs),
                "t_doc_median": round(statistics.median(tot), 2),
                "t_doc_max": round(max(tot), 2),
                "render_median": round(statistics.median(rnd), 3) if rnd else None,
                "llm_median": round(statistics.median(llm), 2) if llm else None,
                "tier_b_median": round(statistics.median(tierb), 3),
                "local_overhead_median": round(statistics.median(local), 3),
                "in_tok_median": int(statistics.median(intok)) if intok else None,
                "out_tok_median": int(statistics.median(outtok)) if outtok else None,
                "retries_total": sum(retr) if retr else 0,
            }
        headline_fixture = max(per_fixture.items(), key=lambda kv: kv[1]["t_doc_median"])
        tail_fixture = max(per_fixture.items(), key=lambda kv: kv[1]["t_doc_max"])
        agg["latency"] = {
            "per_fixture": per_fixture,
            "headline_median_worst": headline_fixture[1]["t_doc_median"],
            "headline_fixture": headline_fixture[0],
            "tail_max_worst": tail_fixture[1]["t_doc_max"],
            "tail_fixture": tail_fixture[0],
        }
    return agg


def write_results(suite: SuiteResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "results.json"
    p.write_text(json.dumps(suite.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def write_summary(suite: SuiteResult, out_dir: Path) -> Path:
    a = suite.aggregates
    lines: List[str] = []
    lines.append("# Rubric Eval Suite — Summary\n")
    prov = suite.provenance
    lines.append(f"- config: `{prov.get('config')}`  mode: `{prov.get('mode')}`  "
                 f"repeats: {prov.get('repeats')}")
    lines.append(f"- prompt_version: `{prov.get('prompt_version')}`  "
                 f"model: `{prov.get('model_version')}`  pipeline: `{prov.get('pipeline_version')}`")
    lines.append(f"- suite_hash: `{prov.get('suite_hash')}`  "
                 f"timestamp: {prov.get('timestamp')}\n")

    lines.append(f"**Gate: {a.get('gate_pass_count', 0)} / {a.get('n_rubrics', 0)} rubrics pass.**  "
                 f"valid={a.get('n_valid')}  invalid={a.get('n_invalid')}\n")

    if a.get("worst_rubric"):
        lines.append("## Worst-rubric (headline; not the mean)\n")
        lines.append("| metric | worst value | rubric | mean |")
        lines.append("|---|---|---|---|")
        for m in _WORST_MIN:
            w = a["worst_rubric"].get(m, {})
            lines.append(f"| {m} | {w.get('value')} | {w.get('rubric')} | {a['mean'].get(m)} |")
        lines.append("")
        lines.append("### Text fidelity (UNGATED diagnostic — never a gate criterion)\n")
        lines.append("| metric | worst value | rubric | mean |")
        lines.append("|---|---|---|---|")
        for m in _TEXT_DIAG:
            w = a["worst_rubric"].get(m, {})
            lines.append(f"| {m} | {w.get('value')} | {w.get('rubric')} | {a['mean'].get(m)} |")
        lines.append("")

    lines.append("## Boolean gates (rubrics failing)\n")
    for m in ["total_points_correct", "selection_match", "annotation_match", "pedagogical_match"]:
        failed = a.get(m + "_failures", [])
        lines.append(f"- {m}: {'ALL PASS' if not failed else 'FAIL → ' + ', '.join(failed)}")
    cons = a.get("point_sum_consistency_failures", [])
    lines.append(f"- point_sum_consistency (health, NOT gated): "
                 f"{'all consistent' if not cons else 'inconsistent → ' + ', '.join(cons)}")
    lines.append("")

    infra = [(r.rubric_name, len(r.errors), len(r.warnings))
             for r in suite.per_rubric if r.errors or r.warnings]
    if infra:
        lines.append("## Infra warnings/errors (see per-rubric reports)\n")
        for name, ne, nw in infra:
            lines.append(f"- {name}: {ne} errors, {nw} warnings")
        lines.append("")

    lines.append("## Attribution (missed criteria)\n")
    lines.append(f"- render_loss total: {a.get('render_loss_total', 0)}  "
                 f"(content never reached the LLM → fix parser_render)")
    lines.append(f"- extraction_loss total: {a.get('extraction_loss_total', 0)}  "
                 f"(content in render, LLM dropped it → fix prompt/model)\n")

    if a.get("latency"):
        lat = a["latency"]
        lines.append("## Latency (ADDITIVE instrument — UNGATED, worst-case discipline)\n")
        lines.append(f"- **headline** `max-over-fixtures of t_doc_median` = "
                     f"**{lat['headline_median_worst']}s** ({lat['headline_fixture']})")
        lines.append(f"- **tail** `max-over-fixtures of t_doc_max` = "
                     f"**{lat['tail_max_worst']}s** ({lat['tail_fixture']})\n")
        lines.append("| fixture | n | t_doc median | t_doc max | render | step1_llm | tier_b | local | in_tok | out_tok | retries |")
        lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for name in sorted(lat["per_fixture"]):
            d = lat["per_fixture"][name]
            lines.append(f"| {name} | {d['n']} | {d['t_doc_median']} | {d['t_doc_max']} | "
                         f"{d['render_median']} | {d['llm_median']} | {d.get('tier_b_median')} | "
                         f"{d['local_overhead_median']} | "
                         f"{d['in_tok_median']} | {d['out_tok_median']} | {d['retries_total']} |")
        lines.append("")

    if a.get("cost_usd"):
        lines.append(f"## Cost\n- max ${a['cost_usd']['max']}  mean ${a['cost_usd']['mean']}\n")

    lines.append("## Per-rubric gate\n")
    lines.append("| rubric | gate | failures |")
    lines.append("|---|---|---|")
    for r in suite.per_rubric:
        fails = "; ".join(r.gate_failures) if r.gate_failures else "—"
        lines.append(f"| {r.rubric_name} | {'PASS' if r.gate_pass else 'FAIL'} | {fails} |")
    lines.append("")

    p = out_dir / "summary.md"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def write_rubric_report(rs: RubricScore, out_dir: Path) -> Path:
    L: List[str] = []
    L.append(f"# Report — {rs.rubric_name}\n")
    L.append(f"gate: **{'PASS' if rs.gate_pass else 'FAIL'}**  "
             f"valid={rs.valid}  repeat={rs.repeat_index}")
    if rs.gate_failures:
        L.append("failures: " + "; ".join(rs.gate_failures))
    if not rs.valid:
        L.append(f"\nINVALID: {rs.invalid_reason}")
        (out_dir / f"report_{rs.rubric_name}.md").write_text("\n".join(L), encoding="utf-8")
        return out_dir / f"report_{rs.rubric_name}.md"
    L.append("")

    L.append("## Headline metrics")
    L.append(f"- question recall/precision: {rs.question_recall:.3f} / {rs.question_precision:.3f}")
    L.append(f"- subquestion_structure_match: {rs.subquestion_structure_match:.3f}")
    L.append(f"- criterion recall/precision: {rs.criterion_recall:.3f} / {rs.criterion_precision:.3f}")
    L.append(f"- subcriterion recall/precision: {rs.subcriterion_recall:.3f} / {rs.subcriterion_precision:.3f}")
    L.append(f"- point_exactness: {rs.point_exactness:.3f}  total_points_correct: {rs.total_points_correct}")
    L.append(f"- selection_match: {rs.selection_match}  "
             f"achievable pred/gt: {rs.achievable_points_pred}/{rs.achievable_points_gt}")
    L.append(f"- example_solution_fidelity: {rs.example_solution_fidelity:.3f}")
    L.append(f"- annotation_match: {rs.annotation_match}")
    L.append(f"- pedagogical_match: {rs.pedagogical_match}")
    L.append(f"- point_sum_consistency (health): {rs.point_sum_consistency}")
    L.append(f"- attribution: render_loss={rs.render_loss_count}  extraction_loss={rs.extraction_loss_count}")
    if rs.cost_usd is not None:
        L.append(f"- cost ${rs.cost_usd}  llm_s {rs.llm_seconds}  retries {rs.retry_count}")
    L.append("")

    # ADDITIVE latency instrument (Phase 0): per-step decomposition for attribution.
    if rs.total_seconds is not None:
        L.append("## Latency (UNGATED instrument)")
        tier_b = sum(st.dt_s for st in (rs.stage_timings or [])
                     if st.stage == "pedagogical" and st.dt_s) or 0.0
        local = rs.total_seconds - (rs.render_seconds or 0.0) - (rs.llm_seconds or 0.0) - tier_b
        L.append(f"- t_doc(total)={rs.total_seconds:.2f}s  wall={rs.wall_seconds}  "
                 f"render={rs.render_seconds}  step1_llm={rs.llm_seconds}  "
                 f"tier_b={round(tier_b, 3)}s  local_overhead={local:.3f}s")
        L.append(f"- tokens in/out: {rs.input_tokens}/{rs.output_tokens}  "
                 f"finish_reason={rs.finish_reason}  retries={rs.retry_count}")
        if rs.stage_timings:
            L.append("- per-step (stage[attempt] dt_s @ elapsed_s):")
            for st in rs.stage_timings:
                att = f"[{st.attempt}]" if st.attempt is not None else ""
                L.append(f"  - {st.stage}{att}  dt={st.dt_s}s  @{st.elapsed_s}s")
        L.append("")

    # nodes WITH GT text (text_ratio is non-None exactly there)
    text_scopes = [s for s in rs.scopes if s.text_ratio is not None]
    if text_scopes:
        L.append("## Text fidelity (UNGATED diagnostic)")
        L.append(f"- question_text_fidelity_min: {rs.question_text_fidelity_min}  "
                 f"subquestion_text_fidelity_min: {rs.subquestion_text_fidelity_min}  "
                 f"text_line_recall_min: {rs.text_line_recall_min}")
        worst = min(text_scopes, key=lambda s: s.text_ratio)
        for s in text_scopes:
            tag = "  <<worst>>" if s is worst else ""
            L.append(f"- `{s.scope_id}` [{s.kind}] ratio={s.text_ratio}  "
                     f"line_recall={s.text_line_recall}{tag}")
        L.append("")

    if rs.errors or rs.warnings:
        L.append("## Infra warnings/errors (pipeline + render audit + transport)")
        for e in rs.errors:
            L.append(f"- ERROR: {e}")
        for w in rs.warnings:
            L.append(f"- WARN: {w}")
        L.append("")

    if rs.missing_annotations or rs.spurious_annotations:
        L.append("## Annotation diffs (faithful-teacher-error)")
        for a in rs.missing_annotations:
            L.append(f"- MISSING expected: {a.annotation_type} @ {a.target_id}")
        for a in rs.spurious_annotations:
            L.append(f"- SPURIOUS: {a.annotation_type} @ {a.target_id}")
        L.append("")
    if rs.missing_pedagogical or rs.spurious_pedagogical:
        L.append("## Pedagogical-mistake diffs (Step 2c)")
        for a in rs.missing_pedagogical:
            L.append(f"- MISSING expected: {a.annotation_type} @ {a.target_id}")
        for a in rs.spurious_pedagogical:
            L.append(f"- SPURIOUS: {a.annotation_type} @ {a.target_id}")
        L.append("")

    if rs.consistency_violations:
        L.append("## Point-sum inconsistencies (health only — may be a faithful teacher error)")
        for v in rs.consistency_violations:
            L.append(f"- {v}")
        L.append("")

    L.append("## Structure (per scope)")
    for s in rs.scopes:
        tag = "" if s.structure_status == "ok" else f"  <<{s.structure_status}>>"
        pe = "" if s.points_exact is None else ("" if s.points_exact else "  POINT-MISMATCH")
        sol = "" if s.solution_status in (None, "na") else f"  solution:{s.solution_status}"
        L.append(f"- `{s.scope_id}` [{s.kind}] pts gt/pred {s.points_gt}/{s.points_pred}{pe}{sol}{tag}")
    L.append("")

    if rs.missed_criteria:
        L.append("## Missed criteria (recall) — with attribution")
        for r in rs.missed_criteria:
            mg = "  [merge suspected]" if r.merge_suspected else ""
            L.append(f"- ({r.attribution}) {r.gt_points} pts — {r.gt_description}{mg}")
        L.append("")
    if rs.spurious_criteria:
        L.append("## Spurious criteria (precision / hallucination)")
        for r in rs.spurious_criteria:
            L.append(f"- {r.pred_points} pts — {r.pred_description}")
        L.append("")

    p = out_dir / f"report_{rs.rubric_name}.md"
    p.write_text("\n".join(L), encoding="utf-8")
    return p


def write_all(suite: SuiteResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_results(suite, out_dir)
    write_summary(suite, out_dir)
    for r in suite.per_rubric:
        write_rubric_report(r, out_dir)
    return out_dir