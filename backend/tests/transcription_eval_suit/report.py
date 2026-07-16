"""
report.py — the human-facing artifacts.

write_summary: one-screen scoreboard. In a two-phase (end-to-end) run it shows
BOTH surfaces side by side — P1 (perception) and E2E (after P2 segmentation) —
plus the P1→E2E ratio delta (the "segmentation tax": how much P2 degraded a
good transcription) and a Phase-2 segmentation-health block (coverage, missed/
extra answer keys, routing notes). A high-fidelity P1 that collapses at E2E is a
P2 failure that must be visible, not hidden behind a single conflated ratio.

write_doc_report: the manual-review companion. Per answer/page: gold | prediction
unified diff on RAW text (case/whitespace visible to the eye even though the
difflib metric ignores them), ratios, named critical-token misses, the
is_error label, plus per-surface segmentation/coverage and routing notes.
Difflib is the proxy; your read is the metric this document serves.
"""
from __future__ import annotations

import difflib
import json
import statistics
from pathlib import Path

# Surfaces, in pipeline order. p1 = perception (image->pages); e2e = after P2
# segmentation (pages->answers, scored vs draft GT).
_SURFACES = (("p1", "P1"), ("e2e", "E2E"))


def _fmt_key(k) -> str:
    """A scoring key [q, sub] -> 'Q1.א', or 'Q2 (whole)' when sub is null (a
    whole-question bucket P2 produced instead of routing to a sub-question)."""
    q = k[0]
    sub = k[1] if len(k) > 1 else None
    if sub in (None, "", "None"):
        return f"Q{q} (whole)"
    return f"Q{q}.{sub}"


def _fmt_keys(keys) -> str:
    return ", ".join(_fmt_key(k) for k in keys) if keys else "—"


def write_summary(out_dir: Path, results: dict, *, cost_ceiling: float) -> None:
    agg = results["aggregates"]
    records = results["records"]
    has = {s: any(r.get(s) for r in records) for s, _ in _SURFACES}

    # Group records by doc, first-seen order; aggregate across repeats.
    by_doc: dict[str, list] = {}
    for r in records:
        by_doc.setdefault(r["doc_id"], []).append(r)

    def ratio_mean(recs, surface):
        v = [r[surface]["doc_ratio_strict"] for r in recs if r.get(surface)]
        return statistics.mean(v) if v else None

    def gate_all(recs, surface):
        g = [r[surface]["gate"]["passed"] for r in recs if r.get(surface)]
        return all(g) if g else None

    def first(recs, surface):
        return next((r[surface] for r in recs if r.get(surface)), None)

    lines: list[str] = []
    lines.append(f"# Eval summary — {results['config_name']} ({results['mode']})")
    lines.append("")
    lines.append(f"- prompt_version: `{results['prompt_version']}` · "
                 f"registry as of {results['registry_as_of']}")
    models = ", ".join(f"{k} ({v['model_id']}, {v['tier']})"
                       for k, v in results["models"].items())
    lines.append(f"- models: {models}")
    surfaces_run = " + ".join(label for s, label in _SURFACES if has[s]) or "—"
    lines.append(f"- surfaces scored: {surfaces_run}")
    scoring = results.get("scoring")
    if scoring is not None:
        cik = scoring.get("case_insensitive_keywords")
        note = " — ⚠ method_call_recall NOT comparable to case-sensitive baselines" if cik else ""
        lines.append(f"- scoring policy: case_insensitive_keywords=`{cik}`{note}")
    lines.append("")

    lines.append("## Gates")
    acc = "PASS" if agg["accuracy_gate_pass_all_docs"] else "FAIL"
    cost = "PASS" if agg["cost_gate_pass"] else "FAIL"
    lines.append(f"- Accuracy (conjunctive, all docs): **{acc}**")
    lines.append(f"- Cost: **{cost}** — avg ${agg['cost_avg_per_doc_usd']:.4f}/doc "
                 f"(ceiling ${cost_ceiling:.2f})")
    lines.append(f"- Parse failures: {agg['parse_failure_total']}")
    if agg["parse_failure_total"]:
        for rec in records:
            if rec["parse_failures"]:
                reasons = rec.get("parse_failure_finish_reasons", [])
                lines.append(f"  - {rec['doc_id']}: {rec['parse_failures']} "
                             f"(finish_reason: {reasons}) — 'length'/'MAX_TOKENS' "
                             f"= truncation, raise p1_max_tokens or shrink chunk")
    if not agg["flag_metrics_trustworthy"]:
        lines.append(f"- ⚠️ n={agg['n_fixtures']} fixtures: flag metrics are NOISE "
                     f"below n=10; conclusions provisional.")
    if "trust" in agg:
        t = agg["trust"]
        tcost = "PASS" if t["cost_gate_pass"] else "FAIL"
        lines.append(
            f"- Trust layer (readers: {', '.join(t['reader_model_keys'])}): "
            f"critical-error flag recall **{t['critical_recall']:.3f}** · "
            f"error recall {t['error_recall']:.3f} · "
            f"missed-critical {t['missed_critical_total']} · "
            f"flags/doc {t['flags_per_doc']:.1f} "
            f"(high {t['high_per_doc']:.1f} / med {t['medium_per_doc']:.1f} / "
            f"info {t['info_per_doc']:.1f}) · lint/doc {t['lint_per_doc']:.1f} · "
            f"trust-cost **{tcost}** (ceiling ${t['cost_ceiling_usd']:.2f})"
        )
    if "correction" in agg:
        c = agg["correction"]
        trust = "" if c["trustworthy"] else " ⚠️ UNDERPOWERED (n<10, needs included student-spec-errors)"
        lines.append(f"- Correction (`{c['policy']}`): {c['n_corrections']} applied · "
                     f"true-fix {c['true_fix']} · **false-fix {c['false_fix']}** "
                     f"(rate {c['false_fix_rate']:.3f}) · ratio_delta {c['ratio_delta']:+.4f}{trust}")
        lines.append(f"  - KILL CRITERION: any non-trivial false-fix against faithful GT "
                     f"kills `{c['policy']}`. Per-tier: {c['by_tier']}")
    lines.append("")

    # --- Per-document table (surface-aware) ---
    lines.append("## Per document")
    if has["p1"] and has["e2e"]:
        lines.append("| doc | P1 ratio | E2E ratio | Δ P1→E2E | E2E cov | P1 gate | E2E gate |")
        lines.append("|---|---|---|---|---|---|---|")
        for doc_id, recs in by_doc.items():
            p1r, e2r = ratio_mean(recs, "p1"), ratio_mean(recs, "e2e")
            delta = (e2r - p1r) if (p1r is not None and e2r is not None) else None
            cov = first(recs, "e2e")["coverage"]
            p1g = "✅" if gate_all(recs, "p1") else "❌"
            e2g = "✅" if gate_all(recs, "e2e") else "❌"
            worst = " ← **WORST**" if doc_id == agg.get("worst_doc") else ""
            dtxt = f"{delta:+.4f}" if delta is not None else "—"
            lines.append(f"| {doc_id} | {p1r:.4f} | {e2r:.4f} | {dtxt} | "
                         f"{cov:.2f} | {p1g} | {e2g}{worst} |")
    else:
        surface = "e2e" if has["e2e"] else "p1"
        label = "E2E" if has["e2e"] else "P1"
        lines.append(f"| doc | {label} ratio | {label} cov | gate |")
        lines.append("|---|---|---|---|")
        for doc_id, recs in by_doc.items():
            s = first(recs, surface)
            mark = "✅" if gate_all(recs, surface) else "❌"
            worst = " ← **WORST**" if doc_id == agg.get("worst_doc") else ""
            lines.append(f"| {doc_id} | {ratio_mean(recs, surface):.4f} | "
                         f"{s['coverage']:.2f} | {mark}{worst} |")
    lines.append("")

    # --- Phase-2 segmentation health (only meaningful when E2E ran) ---
    if has["e2e"]:
        lines.append("## Phase-2 segmentation health")
        lines.append("How P2 routed the verbatim pages into per-question answers "
                     "(coverage = matched answer keys / gold keys).")
        deltas: list[tuple[str, float]] = []
        for doc_id, recs in by_doc.items():
            e = first(recs, "e2e")
            if not e:
                continue
            p1r, e2r = ratio_mean(recs, "p1"), ratio_mean(recs, "e2e")
            if p1r is not None and e2r is not None:
                deltas.append((doc_id, e2r - p1r))
            notes = []
            for r in recs:
                notes.extend(r.get("routing_notes") or [])
            note_txt = ("; ".join(dict.fromkeys(notes))) if notes else "none"
            lines.append(
                f"- **{doc_id}**: coverage {e['coverage']:.2f}"
                f" · missed {_fmt_keys(e['missed_keys'])}"
                f" · extra {_fmt_keys(e['extra_keys'])}"
                f" · routing_notes: {note_txt}"
            )
        if has["p1"] and deltas:
            p1m = statistics.mean(v for d, v in
                                  [(d, ratio_mean(by_doc[d], "p1")) for d in by_doc]
                                  if v is not None)
            e2m = statistics.mean(v for d, v in
                                  [(d, ratio_mean(by_doc[d], "e2e")) for d in by_doc]
                                  if v is not None)
            worst_doc, worst_delta = min(deltas, key=lambda t: t[1])
            lines.append(
                f"- **Segmentation tax**: P1 mean {p1m:.4f} → E2E mean {e2m:.4f} "
                f"(Δ {e2m - p1m:+.4f}); worst tax {worst_doc} {worst_delta:+.4f} "
                f"(perfect P1 that collapses here = a P2 failure, not perception)."
            )
        lines.append("")

    # --- Gate failures, grouped by doc, BOTH surfaces labeled (no dedup) ---
    fail_blocks: list[str] = []
    for doc_id, recs in by_doc.items():
        doc_lines: list[str] = []
        for surface, label in _SURFACES:
            s = first(recs, surface)
            if s and not s["gate"]["passed"]:
                for reason in s["gate"]["reasons"]:
                    doc_lines.append(f"- [{label}] {reason}")
        if doc_lines:
            fail_blocks.append(f"### {doc_id}")
            fail_blocks.extend(doc_lines)
    if fail_blocks:
        lines.append("## Gate failures (named)")
        lines.extend(fail_blocks)
        lines.append("")

    lines.append("## Latency")
    lm = agg["latency_ms"]
    lines.append(f"- per-doc (warm): median {lm['median']:.0f} ms, "
                 f"min {lm['min']:.0f}, max {lm['max']:.0f}")
    if "batch" in agg:
        b = agg["batch"]
        lines.append(f"- batch (n={b['batch_size']}): first draft "
                     f"{b['time_to_first_draft_s']:.1f}s, last "
                     f"{b['time_to_last_draft_s']:.1f}s, "
                     f"{b['docs_per_min']:.1f} docs/min, p95 "
                     f"{b['latency_p95_ms']:.0f} ms, mean queue-wait "
                     f"{b['queue_wait_ms_mean']:.0f} ms")
    lines.append("")

    lines.append("## Stage breakdown (mean ms per doc)")
    stage_totals: dict[str, list[float]] = {}
    for rec in records:
        for stage, ms in rec["stage_ms"].items():
            stage_totals.setdefault(stage, []).append(ms)
    lines.append("| stage | mean ms |")
    lines.append("|---|---|")
    for stage in sorted(stage_totals):
        lines.append(f"| {stage} | {statistics.mean(stage_totals[stage]):.0f} |")

    (out_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def _diff_block(gold: str, pred: str) -> str:
    diff = difflib.unified_diff(
        gold.splitlines(), pred.splitlines(),
        fromfile="gold", tofile="pred", lineterm="",
    )
    body = "\n".join(diff)
    return body if body else "(identical)"


def write_doc_report(
    out_dir: Path, doc_id: str, results: dict, *,
    outputs: dict | None = None, raw_gold=None, draft_gold=None,
) -> None:
    """Manual companion from the FIRST run of this doc: gold | pred | diff.

    Diffs run on RAW text so case/whitespace differences are visible to the
    eye even though the difflib metric ignores them. This file contains
    student text — it lives under results/, which stays gitignored.
    """
    rec = next((r for r in results["records"] if r["doc_id"] == doc_id), None)
    if rec is None:
        return
    outputs = outputs or {}
    lines: list[str] = [f"# Manual review — {doc_id}", ""]

    if rec.get("spec_mismatches"):
        lines.append("## Spec mismatches (Phase 2)")
        for m in rec["spec_mismatches"]:
            lines.append(f"- `{m['original']}` → `{m['suggested']}` "
                         f"({_fmt_key(m['key'])}): {m['reason']}")
        lines.append("")

    for surface, title in (("e2e", "Per answer (end-to-end)"),
                           ("p1", "Per page (Phase 1)")):
        s = rec.get(surface)
        if not s:
            continue
        lines.append(f"## {title}")
        gate = "✅ PASS" if s["gate"]["passed"] else "❌ FAIL"
        lines.append(f"Gate: {gate}" + (
            "" if s["gate"]["passed"]
            else " — " + "; ".join(s["gate"]["reasons"])
        ))
        # Per-surface structural health: where did segmentation / coverage break?
        if surface == "e2e":
            lines.append(
                f"Coverage {s['coverage']:.2f} · missed {_fmt_keys(s['missed_keys'])}"
                f" · extra {_fmt_keys(s['extra_keys'])}"
            )
            notes = rec.get("routing_notes") or []
            if notes:
                lines.append("Routing notes (P2 self-reported):")
                for n in notes:
                    lines.append(f"  - {n}")
        else:
            mp = s.get("missing_pages") or []
            ep = s.get("extra_pages") or []
            lines.append(
                f"Coverage {s['coverage']:.2f} · missing_pages "
                f"{mp if mp else '—'} · extra_pages {ep if ep else '—'}"
            )
        lines.append("")
        items = s.get("answers") or [
            {"key": ["page", p["page"]], "ratio_strict": p["ratio_strict"],
             "is_error": p["is_error"], "missed": {}}
            for p in s.get("pages", [])
        ]
        gold_map = {}
        pred_map = {}
        if surface == "e2e" and draft_gold is not None:
            gold_map = {tuple(k): v for k, v in
                        ((a.key, a.answer_text) for a in draft_gold.answers)}
            pred_map = {tuple(k): v for k, v in
                        (outputs.get("answers") or {}).items()}
        elif surface == "p1" and raw_gold is not None:
            gold_map = {("page", p.page_number): p.text for p in raw_gold.pages}
            pred_map = {("page", n): t for n, t in
                        (outputs.get("pages") or {}).items()}

        for a in items:
            err = " ⚠️ ERROR" if a["is_error"] else ""
            is_page = a["key"][0] == "page"
            key = f"page {a['key'][1]}" if is_page else _fmt_key(a["key"])
            lines.append(f"### {key} — ratio {a['ratio_strict']:.4f}{err}")
            missed = a.get("missed", {})
            for kind, toks in missed.items():
                if toks:
                    lines.append(f"- missed {kind}: `{toks}`")
            gk = ("page", a["key"][1]) if is_page else (a["key"][0], a["key"][1])
            if gk in gold_map:
                lines.append("")
                lines.append("```diff")
                lines.append(_diff_block(gold_map[gk], pred_map.get(gk, "")))
                lines.append("```")
            lines.append("")
    (out_dir / f"report_{doc_id}.md").write_text("\n".join(lines), encoding="utf-8")


def compare_texts(gold: str, pred: str) -> str:
    """Ad-hoc gold|pred diff helper for notebook/REPL manual review."""
    return _diff_block(gold, pred)
