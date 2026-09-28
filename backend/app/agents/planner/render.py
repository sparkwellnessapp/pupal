"""The G2 plan render (PR_grader_v6_options.md §12, Phase 2): a Markdown page per
rubric that an engineer reads at REVIEW-2 — never shown to a teacher (W-3).

Per teacher criterion (terminal):
  * the collapsed line a teacher would see — the criterion and its points, with
    the fallback composer's line for a fully earned answer and for an empty one;
  * the expanded checks: role, shape, description, every option with its value,
    `requires`, charge group, origin;
  * the interpretation notes;
  * the marker dispositions of its scope;
  * the V19 fault-leak candidates (telemetry, never an error).
"""
from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Sequence

from app.agents.grader.plan_schemas import GradingPlanV6, PlanCheckV6
from app.agents.grader.plan_validator_v6 import v19_fault_leak_candidates
from app.agents.plan_compiler.stage1_v6 import Stage1V6

from .planner import ScopePlanResult


def _fmt(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s


def _check_lines(c: PlanCheckV6) -> List[str]:
    head = (f"- **{c.check_id}** · {c.role} · {c.shape} · origin `{c.origin}`"
            + (f" · requires `{c.requires}`" if c.requires else "")
            + (f" · group `{c.charge_group}`" if c.charge_group else ""))
    lines = [head, f"  - {c.description_he}"]
    if c.equivalence_note_he:
        lines.append(f"  - שקילות: {c.equivalence_note_he}")
    for o in c.options:
        marker = f" ← `{o.marker_id}`" if o.marker_id else ""
        lines.append(f"  - `{o.option_id}` **{_fmt(o.value)}** — {o.label_he}{marker}")
    return lines


def render_plan_md(title: str, plan: GradingPlanV6, stage1: Stage1V6,
                   results: Sequence[ScopePlanResult]) -> str:
    by_scope = {r.scope: r for r in results}
    checks_by_t: Dict[str, List[PlanCheckV6]] = {}
    for c in plan.checks:
        checks_by_t.setdefault(c.priced_terminal_id, []).append(c)
    terminals = {t.terminal_id: t for t in plan.terminals}

    out = [f"# {title} — plan/v6 render", "",
           f"- plan_hash `{plan.plan_hash[:16]}…` · config_hash `{plan.config_hash[:16]}…` · "
           f"pack `{plan.subject_pack.pack_id}@{plan.subject_pack.pack_version}`",
           f"- stage 1 `{stage1.version}` · {len(plan.terminals)} criteria · {len(plan.checks)} checks",
           "- scope origins: " + ", ".join(f"{r.scope}={r.origin}" for r in results), ""]
    for scope in stage1.scopes:
        r = by_scope.get(scope.scope)
        out += [f"## {scope.scope} — {r.origin if r else '?'}", ""]
        if r and r.errors:
            out += ["> validator messages that sent this scope to repair/fallback:"]
            out += [f"> - {e}" for e in r.errors]
            out.append("")
        for t in scope.terminals:
            tp = terminals.get(t.terminal_id)
            cs = checks_by_t.get(t.terminal_id, [])
            credit_max = sum((c.options[0].value for c in cs if c.role == "credit"), Decimal("0"))
            out += [f"### {t.terminal_id} · {_fmt(t.points_possible)} נק׳ · {t.shape}"
                    + (" · fixed" if t.fixed else ""), "",
                    f"**Teacher's text:** {t.text.strip()}", "",
                    f"**Collapsed:** {len(cs)} checks · credit max {_fmt(credit_max)} / "
                    f"{_fmt(t.points_possible)}", ""]
            for c in cs:
                out += _check_lines(c)
            if tp and tp.interpretation_notes_he:
                out += ["", "**Interpretation notes:**"] + [f"- {n}" for n in tp.interpretation_notes_he]
            out.append("")
        if scope.markers:
            disp = {d.marker_id: d for d in (r.dispositions if r else [])}
            out += ["**Markers and dispositions:**", ""]
            for m in scope.markers:
                d = disp.get(m.marker_id)
                how = (f"{d.disposition}" + (f" → `{d.merged_into_marker_id}`" if d.merged_into_marker_id else "")
                       + (f" — {d.reason_he}" if d.reason_he else "")) if d else "—"
                out.append(f"- `{m.marker_id}` −{_fmt(m.amount)} · candidates {m.candidate_anchors}"
                           f" · {how} · «{m.text_span.strip()}»")
            out.append("")
        scope_checks = [c for c in plan.checks
                        if c.priced_terminal_id in {t.terminal_id for t in scope.terminals}]
        v19 = v19_fault_leak_candidates(scope_checks, list(scope.markers))
        if v19:
            out += ["**V19 candidates (telemetry):**"] + [
                f"- `{f}` requires `{req}` — shared tokens {toks}" for f, req, toks in v19] + [""]
        if r and r.telemetry:
            out += ["**Telemetry:**"] + [f"- {x}" for x in r.telemetry] + [""]
    return "\n".join(out) + "\n"
