"""
The 488-judgment expressibility guard (PR_plan_compiler_v2.md §6/§9) — standing.

Recompiles BOTH exams from their committed contracts (zero spend, pure) and
pins what A0 measured (`app/agents/plan_gen/A0_REPORT.md`):

  * the real validator accepts both placeholder plans with ZERO errors;
  * hobby 190 + bagrut 298 = 488 attempted judgments (R-2 reader);
  * every miss, by (fixture, terminal, award, class) — a NEW miss or a miss
    that changes class is a compiler regression; a miss that disappears is
    progress and must be re-pinned deliberately, with the reason;
  * the committed `plans/compiled/*.plan.json` are byte-identical to a fresh
    assembly (the artefact never drifts from the compiler that made it).

GT immutable (R-2/R-3 are the owner's). No bar moves here: the pinned sets ARE
the measurement, and the PR's bars are judged in the report, not softened in a
test.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal

import pytest

from app.agents.grader.plan_validator import validate_plan
from app.agents.plan_compiler import compile_contract
from app.agents.plan_compiler.assemble import assemble_placeholder_plan
from app.agents.plan_compiler.stage0 import contract_scopes, terminals_of
from app.agents.plan_gen.prompt import scope_corpus

from .fixtures import SUITE_DIR, load_bundle, read_gt_judgments
from .plan_expressibility import reachable_awards
from .tools.compile_plan import classify, discover_exams

COMPILED = SUITE_DIR / "plans" / "compiled"

# (fixture, terminal, award, class) — A0 2026-09-05, plan-compiler/v2.0
PINNED_MISSES = {
    "hobby_tvshow": {
        ("dan_basiuk", "q1.א.c1", "3.5", "routed"),
        ("dan_basiuk", "q2.א.c1", "9", "routed"),
        ("din_ezra", "q1.א.c1", "3", "routed"),
        ("din_ezra", "q2.א.c0", "4", "routed"),
        ("din_ezra", "q2.א.c1", "8", "routed"),
        ("yonatan_basiuk", "q2.ב.c4.s2", "1.5", "ruling"),
    },
    "bagrut_899371": {
        ("bagrut_899371.din_ezra", "q3.ב.c6", "2.5", "decomposition"),
        ("bagrut_899371.itay_kraft", "q6.c4", "0.5", "granularity-floor"),
        ("bagrut_899371.noam_breinshtein", "q3.ב.c5", "2.5", "decomposition"),
        ("bagrut_899371.noam_breinshtein", "q3.ב.c6", "2.5", "decomposition"),
        ("bagrut_899371.noam_breinshtein", "q6.c5", "1", "routed"),
        ("bagrut_899371.raz_cohen", "q1.ב.2.c1", "1.5", "granularity-ladder"),
        ("bagrut_899371.raz_cohen", "q3.ב.c4", "1", "routed"),
        ("bagrut_899371.raz_cohen", "q3.ב.c6", "2", "decomposition"),
        ("bagrut_899371.raz_cohen", "q6.c5", "1", "routed"),
        ("bagrut_899371.raz_cohen", "q6.c8", "3", "routed"),
        ("bagrut_899371.roni_ben_ezra", "q3.ב.c6", "2", "decomposition"),
        ("bagrut_899371.yael_kogan", "q2.ב.c5", "0.5", "granularity-floor"),
        ("bagrut_899371.yael_kogan", "q3.ב.c6", "2", "decomposition"),
        ("bagrut_899371.yahli_cohen", "q3.ב.c6", "2.5", "decomposition"),
    },
}
PINNED_TOTALS = {"hobby_tvshow": 190, "bagrut_899371": 298}


def _compile(exam, fixtures):
    b0 = load_bundle(fixtures[0], require_gt=False)
    manifest = json.loads((SUITE_DIR / "fixtures" / f"{fixtures[0]}.json").read_text(encoding="utf-8"))
    sha = hashlib.sha256((SUITE_DIR / manifest["rubric_contract"]).read_bytes()).hexdigest()
    skeleton = compile_contract(b0.rubric_contract, exam_id=exam, rubric_contract_sha256=sha)
    return b0.rubric_contract, skeleton, assemble_placeholder_plan(skeleton)


@pytest.fixture(scope="module")
def compiled():
    return {exam: _compile(exam, fx) for exam, fx in discover_exams().items()}


def test_both_exams_are_discovered():
    assert set(discover_exams()) == {"hobby_tvshow", "bagrut_899371"}


@pytest.mark.parametrize("exam", ["hobby_tvshow", "bagrut_899371"])
def test_the_real_validator_accepts_the_compiled_plan(compiled, exam):
    contract, _skeleton, plan = compiled[exam]
    points, scopes, corpora = {}, {}, {}
    for key, q, sub in contract_scopes(contract):
        lbl = f"{key[0]}.{key[1]}" if key[1] else key[0]
        corpora[lbl] = scope_corpus(q, sub)
        for tid, pts in terminals_of(sub or q):
            points[tid] = pts
            scopes[tid] = lbl
    errors = validate_plan(plan, contract_terminal_points=points, terminal_scopes=scopes,
                           precision=Decimal(str(contract.numeric_policy.precision)),
                           scope_corpora=corpora)
    assert errors == [], errors


@pytest.mark.parametrize("exam", ["hobby_tvshow", "bagrut_899371"])
def test_every_attempted_judgment_is_reachable_except_the_pinned_misses(compiled, exam):
    contract, skeleton, plan = compiled[exam]
    precision = Decimal(str(contract.numeric_policy.precision))
    hand_path = SUITE_DIR / "plans" / f"{exam}.plan.json"
    ruling = set()
    if hand_path.exists():
        from app.agents.grader.plan_schemas import GradingPlan
        hand = GradingPlan.model_validate_json(hand_path.read_text(encoding="utf-8"))
        ruling = {t.terminal_id for t in hand.terminals if any(c.source == "ruling" for c in t.checks)}
    by_tid = {t.terminal_id: t for t in skeleton.terminals}
    plan_by = {t.terminal_id: t for t in plan.terminals}
    total, misses = 0, set()
    for name in discover_exams()[exam]:
        _b, judgments = read_gt_judgments(name)
        for tid, award in judgments:
            total += 1
            reach = reachable_awards(plan_by[tid], precision)
            if award not in reach:
                misses.add((name, tid, str(award), classify(by_tid[tid], award, reach, ruling)))
    assert total == PINNED_TOTALS[exam]
    new = misses - PINNED_MISSES[exam]
    gone = PINNED_MISSES[exam] - misses
    assert not new, f"NEW misses (regression): {sorted(new)}"
    assert not gone, f"misses no longer occur — re-pin deliberately: {sorted(gone)}"


def test_488_judgments_in_total():
    assert sum(PINNED_TOTALS.values()) == 488


@pytest.mark.parametrize("exam", ["hobby_tvshow", "bagrut_899371"])
def test_the_committed_artefact_is_what_the_compiler_makes(compiled, exam):
    _c, _s, plan = compiled[exam]
    committed = json.loads((COMPILED / f"{exam}.plan.json").read_text(encoding="utf-8"))
    assert committed == plan.model_dump(mode="json")
    assert committed["compiler_version"] == "plan-compiler/v2.0"
    assert committed["plan_version"].startswith(f"{exam}/compiled-")
