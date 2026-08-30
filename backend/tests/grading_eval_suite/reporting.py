"""
Reporting [§9]: results.json (machine, stable), summary.md (worst test FIRST),
report_<fixture>.md (the full terminal table — the artifact the PLAYBOOK's
read-two-by-hand rule consumes).

Statistics honesty [§6 standing rules]: worst-test over mean, always; every
rate at n<10 fixtures is PROVISIONAL and stamped so; k=1 is PROVISIONAL;
calibration is n-flagged below 50 terminals.
"""
from __future__ import annotations

import json
import statistics
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.schemas.graded_test_draft import GradedTestDraft

from .schemas import SuiteResult, TrialScore

CALIBRATION_MIN_N = 50
PROVISIONAL_MIN_FIXTURES = 10        # gate ratification needs n>=10 across >=2 exams [§4]


def aggregate(trials: List[TrialScore], *, k: int) -> Dict[str, Any]:
    valid = [t for t in trials if t.valid and not t.diagnostic_subset]
    fixtures = sorted({t.fixture for t in trials})
    agg: Dict[str, Any] = {
        "n_trials": len(trials),
        "n_valid": len(valid),
        "n_invalid": len(trials) - len([t for t in trials if t.valid]),
        "invalid_reasons": [t.invalid_reason for t in trials if not t.valid],
        "n_fixtures": len(fixtures),
        "k": k,
    }
    # PROVISIONAL stamping [§6]: n<10 fixtures => every rate is provisional; k=1 too.
    reasons = []
    if len(fixtures) < PROVISIONAL_MIN_FIXTURES:
        reasons.append(f"n_fixtures={len(fixtures)}<{PROVISIONAL_MIN_FIXTURES} "
                       f"(single-exam seed set — see ONBOARDING gap register)")
    if k < 5:
        reasons.append(f"k={k}<5 (authoritative tier is k>=5)")
    agg["provisional"] = bool(reasons)
    agg["provisional_reasons"] = reasons

    # Tier 1
    agg["tier1_pass_count"] = sum(1 for t in valid if t.tier1_pass)
    taxonomy: Dict[str, int] = {}
    for t in valid:
        for f in t.tier1_failures:
            tag = f.split("]")[0].strip("[")
            taxonomy[tag] = taxonomy.get(tag, 0) + 1
    agg["tier1_failure_taxonomy"] = taxonomy

    if not valid:
        return agg

    # Per-fixture blocks + worst test [worst-over-mean, always]
    per_fixture: Dict[str, Any] = {}
    by_terminal_all: Dict[Any, List[Decimal]] = {}   # (fixture, terminal) -> awards across k
    for fx in fixtures:
        recs = [t for t in valid if t.fixture == fx]
        if not recs:
            per_fixture[fx] = {"n_valid": 0}
            continue
        tds = [abs(Decimal(t.total_delta)) for t in recs if t.total_delta is not None]
        maes = [t.mae for t in recs if t.mae is not None]
        wpr = [t.within_precision_rate for t in recs if t.within_precision_rate is not None]
        burdens = [t.edit_burden for t in recs if t.edit_burden is not None]
        ai_totals = [Decimal(t.ai_total) for t in recs if t.ai_total is not None]
        # repeat stability [Tier-3]: per-terminal award spread across trials
        by_terminal: Dict[str, List[Decimal]] = {}
        for t in recs:
            for row in t.terminals:
                by_terminal.setdefault(row.terminal_id, []).append(Decimal(row.ai_awarded))
        for _tid, _v in by_terminal.items():
            by_terminal_all[(fx, _tid)] = _v
        spreads = {tid: max(v) - min(v) for tid, v in by_terminal.items() if len(v) > 1}
        worst_spread = max(spreads.values()) if spreads else Decimal("0")
        per_fixture[fx] = {
            "n_valid": len(recs),
            "total_abs_delta_median": float(statistics.median(tds)) if tds else None,
            "total_abs_delta_max": float(max(tds)) if tds else None,
            "mae_mean": round(statistics.mean(maes), 4) if maes else None,
            "within_precision_rate_mean": round(statistics.mean(wpr), 4) if wpr else None,
            "shippable_rate": (sum(1 for t in recs if t.shippable) / len(recs))
                              if any(t.shippable is not None for t in recs) else None,
            "edit_burden_median": statistics.median(burdens) if burdens else None,
            "ai_total_spread": float(max(ai_totals) - min(ai_totals)) if len(ai_totals) > 1 else 0.0,
            "terminal_award_spread_max": float(worst_spread),
            "unstable_terminals": sorted(
                [tid for tid, s in spreads.items() if s > 0])[:10],
            "tier1_failures": sum(len(t.tier1_failures) for t in recs),
            "compensating_errors": sum(1 for t in recs if t.compensating_error),
            "boundary_flip_trials": sum(1 for t in recs if t.boundary_flips),
            # [item 6] Tier-3 per-fixture counts (unique terminals, not per trial)
            "c1_table_terminals": len({row.terminal_id for t in recs for row in t.terminals
                                       if row.gt_note and "[C1-TABLE]" in row.gt_note}),
            "ungradable_terminals": len({row.terminal_id for t in recs for row in t.terminals
                                         if row.ungradable_scope}),
        }
    agg["per_fixture"] = per_fixture
    with_delta = [(fx, b) for fx, b in per_fixture.items()
                  if b.get("total_abs_delta_median") is not None]
    if with_delta:
        worst = max(with_delta, key=lambda kv: kv[1]["total_abs_delta_median"])
        agg["worst_test"] = {"fixture": worst[0],
                             "total_abs_delta_median": worst[1]["total_abs_delta_median"]}

    # Pooled Tier-2 rates (UNGATED-WATCHED). [C-2, ratified 2026-08-24]:
    # ungradable-scope terminals are excluded from agreement math AND from the
    # calibration input (their 'correct' would be measured against a best-guess
    # GT — noise by construction; the C-2 exclusion logic extends to it).
    all_terms = [row for t in valid for row in t.terminals
                 if not row.excluded_by_selection and not row.ungradable_scope]
    if all_terms:
        agg["terminal_within_precision_rate"] = round(
            sum(r.within_precision for r in all_terms) / len(all_terms), 4)
        agg["terminal_exact_rate"] = round(
            sum(r.exact for r in all_terms) / len(all_terms), 4)
        agg["terminal_mae"] = round(
            float(sum(Decimal(r.abs_delta) for r in all_terms) / len(all_terms)), 4)
    ship = [t for t in valid if t.shippable is not None]
    if ship:
        agg["shippable_grade_rate"] = round(sum(t.shippable for t in ship) / len(ship), 4)
        # [GA-3, mission §2] STRICT shippable: |total Δ| <= 1.0 AND no
        # compensating_error — the cancellation ruling made executable.
        agg["strict_shippable_rate"] = round(
            sum(1 for t in ship if t.shippable and not t.compensating_error)
            / len(ship), 4)
    # [GA-6, mission §2] corpus edit_burden per test — median and max
    burdens_all = [t.edit_burden for t in valid if t.edit_burden is not None]
    if burdens_all:
        agg["edit_burden"] = {"median": statistics.median(burdens_all),
                              "max": max(burdens_all)}
    agg["boundary_flip_rate"] = round(
        sum(1 for t in valid if t.boundary_flips) / len(valid), 4)
    agg["compensating_error_count"] = sum(1 for t in valid if t.compensating_error)
    agg["exclusion_mismatch_count"] = sum(1 for t in valid if t.exclusion_mismatch)

    # Tier 3: parse-failure rate [R6 escalation] over ALL trials (incl. invalid —
    # a parse failure inside an invalid trial still happened)
    llm_scopes = sum(t.graded_by_counts.get("llm", 0) + len(t.parse_failed_scopes)
                     for t in trials)
    parse_fails = sum(len(t.parse_failed_scopes) for t in trials)
    agg["parse_failure_rate"] = round(parse_fails / llm_scopes, 4) if llm_scopes else 0.0

    # [owner ruling 2026-08-27, E7-record correction b] Instability in BOTH
    # measures, every run. "How many terminals move" and "how far the test total
    # moves" are different properties, and reporting only the first hid a real
    # regression: E7's terminal-count instability improved (37.4% -> 30.0%) while
    # dan's per-test spread went 3.25 -> 14.00, crossing two grade boundaries on
    # identical input. Never report one without the other.
    spreads = {fx: b["ai_total_spread"] for fx, b in per_fixture.items()
               if b.get("ai_total_spread") is not None}
    moving = sum(1 for v in by_terminal_all.values() if len(set(v)) > 1) if by_terminal_all else 0
    n_terms = len(by_terminal_all) if by_terminal_all else 0
    agg["instability"] = {
        # measure 1 — HOW MANY terminals move across k
        "terminals_moving": moving,
        "terminals_total": n_terms,
        "terminals_moving_pct": round(100 * moving / n_terms, 1) if n_terms else 0.0,
        # measure 2 — HOW FAR the test total moves (the one E7 omitted)
        "per_fixture_ai_total_spread": spreads,
        "max_ai_total_spread": max(spreads.values()) if spreads else 0.0,
        "worst_spread_fixture": (max(spreads.items(), key=lambda kv: kv[1])[0]
                                 if spreads else None),
    }
    agg["parse_failure_escalation"] = parse_fails > 0     # [R6] bucket before any sweep

    # Calibration (reliability bins + ECE), n-flagged [Tier-3]
    conf_rows = [(r.ai_confidence, r.within_precision) for r in all_terms]
    if conf_rows:
        bins: List[Dict[str, Any]] = []
        ece = 0.0
        n = len(conf_rows)
        for i in range(10):
            lo, hi = i / 10, (i + 1) / 10
            inb = [(c, ok) for c, ok in conf_rows
                   if (lo <= c < hi) or (i == 9 and c == 1.0)]
            if not inb:
                continue
            acc = sum(ok for _, ok in inb) / len(inb)
            mean_conf = sum(c for c, _ in inb) / len(inb)
            bins.append({"bin": f"[{lo:.1f},{hi:.1f})", "n": len(inb),
                         "mean_confidence": round(mean_conf, 3),
                         "accuracy": round(acc, 3)})
            ece += (len(inb) / n) * abs(acc - mean_conf)
        agg["calibration"] = {
            "n_terminals": n,
            "ece": round(ece, 4),
            "n_flagged": n < CALIBRATION_MIN_N,
            "bins": bins,
        }

    # Cost / latency
    costs = [t.cost_usd for t in valid if t.cost_usd is not None]
    lats = [t.latency_s for t in valid if t.latency_s is not None]
    if costs:
        agg["cost_usd"] = {"mean": round(statistics.mean(costs), 4),
                           "max": round(max(costs), 4)}
        agg["run_cost_usd_total"] = round(sum(costs), 4)   # the ledger line [§1.6]
    thinks = [t.thinking_tokens for t in valid if t.thinking_tokens is not None]
    if thinks:
        # [item 2b] adaptive-thinking visibility; a SUBSET of output tokens.
        agg["thinking_tokens_total"] = sum(thinks)
        agg["thinking_tokens_per_test"] = round(sum(thinks) / len(thinks), 1)
    if lats:
        agg["latency_s"] = {"median": round(statistics.median(lats), 2),
                            "max": round(max(lats), 2)}
    agg["rerun_count_total"] = sum(t.rerun_count for t in trials)
    return agg


# ---------------------------------------------------------------------------
# Writers
# ---------------------------------------------------------------------------

def write_results(suite: SuiteResult, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "results.json"
    p.write_text(json.dumps(suite.to_dict(), ensure_ascii=False, indent=1),
                 encoding="utf-8")
    return p


def write_summary(suite: SuiteResult, out_dir: Path) -> Path:
    a, prov = suite.aggregates, suite.provenance
    L: List[str] = ["# Grading Eval Suite — Summary", ""]
    if a.get("provisional"):
        L.append("> **PROVISIONAL** — " + "; ".join(a.get("provisional_reasons", [])))
        L.append("")
    L.append(f"- config: `{prov.get('config')}`  mode: `{prov.get('mode')}`  "
             f"k: {prov.get('k')}  fixtures: {', '.join(prov.get('fixtures', []))}")
    L.append(f"- model_key: `{prov.get('model_key')}`  model_version: "
             f"`{prov.get('model_version')}`  prompt_version: `{prov.get('prompt_version')}`")
    L.append(f"- registry_as_of: `{prov.get('registry_as_of')}`  suite_hash: "
             f"`{prov.get('suite_hash')}`  **sut_hash: `{prov.get('sut_hash')}`**  "
             f"timestamp: {prov.get('timestamp')}")
    L.append(f"- prior_context: {prov.get('prior_context')}  "        # [PR-G1]
             f"gt_sources: {prov.get('gt_sources')}")                 # [M1]
    L.append("")
    L.append(f"**Validity:** {a.get('n_valid')}/{a.get('n_trials')} trials valid"
             + (f" — invalid: {a.get('invalid_reasons')}" if a.get("n_invalid") else ""))
    L.append(f"**Tier-1:** {a.get('tier1_pass_count', 0)}/{a.get('n_valid', 0)} "
             f"valid trials pass"
             + (f" — taxonomy: {a.get('tier1_failure_taxonomy')}"
                if a.get("tier1_failure_taxonomy") else ""))
    if a.get("worst_test"):
        w = a["worst_test"]
        L.append(f"**Worst test (median |total Δ|): `{w['fixture']}` "
                 f"= {w['total_abs_delta_median']}** — read its report first.")
    L.append("")
    L.append("## Tier-2 (UNGATED-WATCHED)")
    for key in ("terminal_within_precision_rate", "terminal_exact_rate", "terminal_mae",
                "shippable_grade_rate", "boundary_flip_rate",
                "compensating_error_count", "exclusion_mismatch_count"):
        if key in a:
            L.append(f"- {key}: {a[key]}")
    L.append("")
    L.append("## Tier-3 diagnostics")
    L.append(f"- parse_failure_rate: {a.get('parse_failure_rate')}"
             + ("  **[R6 ESCALATION: rate > 0 — bucket affected fixtures before "
                "any model comparison]**" if a.get("parse_failure_escalation") else ""))
    if a.get("calibration"):
        c = a["calibration"]
        L.append(f"- calibration: ECE={c['ece']} over n={c['n_terminals']} terminals"
                 + ("  (n-FLAGGED: below the 50-terminal bar)" if c["n_flagged"] else ""))
    if a.get("cost_usd"):
        L.append(f"- cost/trial: mean ${a['cost_usd']['mean']}  max ${a['cost_usd']['max']}")
    if a.get("latency_s"):
        L.append(f"- latency: median {a['latency_s']['median']}s  max {a['latency_s']['max']}s")
    L.append(f"- re-runs (transport/wall, D7): {a.get('rerun_count_total', 0)}")
    inst = a.get("instability")
    if inst:
        # BOTH measures, always [owner ruling 2026-08-27]
        L.append(f"- instability: **{inst['terminals_moving_pct']}%** of terminals move "
                 f"({inst['terminals_moving']}/{inst['terminals_total']}) · "
                 f"**max per-test total spread {inst['max_ai_total_spread']}** "
                 f"(worst: `{inst['worst_spread_fixture']}`) — "
                 f"how many AND how far; never report one alone")
    L.append("")
    L.append("## Per-fixture")
    for fx, b in (a.get("per_fixture") or {}).items():
        L.append(f"- `{fx}`: " + json.dumps(b, ensure_ascii=False))
    p = out_dir / "summary.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p


def write_fixture_report(fixture: str, trials: List[TrialScore],
                         drafts: Dict[int, GradedTestDraft], out_dir: Path) -> Path:
    """The manual-review companion: per-trial terminal table
    gold | awarded | Δ | quote_status | confidence | reasoning(He) [§9]."""
    L: List[str] = [f"# {fixture} — terminal-level report", ""]
    for t in sorted(trials, key=lambda x: x.trial_index):
        L.append(f"## trial r{t.trial_index}"
                 + ("  **INVALID: " + (t.invalid_reason or "") + "**" if not t.valid else "")
                 + ("  [PROVISIONAL]" if t.provisional else ""))
        L.append(f"- tier1: {'PASS' if t.tier1_pass else 'FAIL ' + str(t.tier1_failures)}")
        if t.total_delta is not None:
            L.append(f"- totals: gt {t.gt_total} / ai {t.ai_total} / possible "
                     f"{t.total_possible}  (Δ={t.total_delta}, shippable={t.shippable}, "
                     f"flips={t.boundary_flips}, compensating={t.compensating_error})")
        n_ungr = sum(1 for row in t.terminals if row.ungradable_scope)
        if n_ungr:
            # [C-2] totals-inclusion mark: best-guess awards live inside the
            # totals but outside every agreement metric
            L.append(f"- **total includes {n_ungr} ungradable-scope terminal"
                     f"{'s' if n_ungr != 1 else ''}** (C-2: excluded from all "
                     f"agreement metrics)")
        # reasoning text lives in the persisted draft, not results.json
        reasoning: Dict[str, str] = {}
        draft = drafts.get(t.trial_index)
        if draft is not None:
            for outcome in draft.scope_outcomes:
                for co in outcome.criterion_outcomes:
                    if co.sub_criterion_outcomes:
                        for so in co.sub_criterion_outcomes:
                            reasoning[so.sub_criterion_id] = so.reasoning
                    else:
                        reasoning[co.criterion_id] = co.reasoning
        L.append("")
        L.append("| terminal | gold | ai | Δ | quote | conf | flags | gt note | reasoning |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for row in t.terminals:
            r = (reasoning.get(row.terminal_id, "") or "").replace("|", "\\|")
            excl = " (EXCLUDED)" if row.excluded_by_selection else ""
            if row.ungradable_scope:
                excl += " (UNGRADABLE)"                       # [C-2] visible to the ritual
            note = (row.gt_note or "-").replace("|", "\\|")   # [item 6] [C1-TABLE] visible
            L.append(f"| {row.terminal_id}{excl} | {row.gt_awarded} | {row.ai_awarded} "
                     f"| {row.delta} | {row.quote_status or '-'} | "
                     f"{row.ai_confidence:.2f} | {','.join(row.ai_flags) or '-'} | "
                     f"{note} | {r} |")
        L.append("")
    p = out_dir / f"report_{fixture}.md"
    p.write_text("\n".join(L) + "\n", encoding="utf-8")
    return p
