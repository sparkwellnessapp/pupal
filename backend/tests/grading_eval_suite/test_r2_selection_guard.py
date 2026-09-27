"""
R-2's companion guard (owner-ruled 2026-09-05): unselected scopes never enter
any per-terminal denominator, and selection is derived from the TRANSCRIPTION,
never from the GT's zeros.

Why the derivation matters: R-2 fills every unselected terminal with
`awarded: "0"`. A scorer that read those zeros to decide what to exclude would
be reading its own answer key — and a genuine zero on a question the student
DID attempt would vanish from K1 along with them. The transcription says which
questions were sat; the GT says how well.
"""
from __future__ import annotations

import json

import pytest

from .fixtures import (SUITE_DIR, load_bundle, read_gt_judgments,
                       unattempted_questions, unattempted_scope_keys)

BAGRUT = [f"bagrut_899371.{s}" for s in
          ["din_ezra", "itay_kraft", "noam_breinshtein", "raz_cohen",
           "roni_ben_ezra", "yael_kogan", "yahli_cohen"]]
HOBBY = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk"]


def test_unselected_scopes_never_enter_any_denominator():
    """THE R-2 test: 298 scored cells across the seven bagrut GTs, not 403.

    61 terminals × 7 fixtures = 427; each student sat exactly 4 of 6 questions,
    so 15–22 terminals per fixture are unselected and must be absent from every
    per-terminal metric. The count is the one the owner authored (298)."""
    total = 0
    for name in BAGRUT:
        _bundle, judgments = read_gt_judgments(name)
        total += len(judgments)
    assert total == 298, f"{total} scored cells — unselected scopes leaked into a denominator"


def test_selection_is_derived_from_the_transcription_not_the_gt():
    """The unattempted set must equal the questions with empty answers in the
    TRANSCRIPTION — and it must agree with what the owner left unawarded, which
    is the independent check that the derivation is reading the right thing."""
    for name in BAGRUT:
        bundle = load_bundle(name, require_gt=False)
        skipped = unattempted_questions(bundle)
        assert len(skipped) == 2, f"{name}: expected 2 unselected of 6, got {sorted(skipped)}"

        manifest = json.loads((SUITE_DIR / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
        raw = json.loads((SUITE_DIR / manifest["gt"]).read_text(encoding="utf-8"))
        keys = unattempted_scope_keys(bundle)
        for t in raw["terminals"]:
            info = bundle.terminal_infos[t["terminal_id"]]
            on_skipped = info.scope_key in keys
            unawarded = t.get("awarded") in (None, "0", "0.0", 0)
            if on_skipped:
                assert unawarded, (
                    f"{name}: {t['terminal_id']} is on an unselected question but "
                    f"carries award {t['awarded']!r} — the derivation disagrees with the GT")
            elif t.get("awarded") is None:
                pytest.fail(f"{name}: {t['terminal_id']} is on an ATTEMPTED question "
                            f"and has no award — still being authored")


def test_a_null_on_an_attempted_scope_is_refused():
    from .fixtures import GTValidationError
    import tempfile, shutil, pathlib

    # copy the suite's manifest+GT shape into a temp root and blank one attempted award
    name = BAGRUT[0]
    bundle = load_bundle(name, require_gt=False)
    manifest = json.loads((SUITE_DIR / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
    raw = json.loads((SUITE_DIR / manifest["gt"]).read_text(encoding="utf-8"))
    skipped = unattempted_scope_keys(bundle)
    victim = next(t for t in raw["terminals"]
                  if bundle.terminal_infos[t["terminal_id"]].scope_key not in skipped)
    victim["awarded"] = None

    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        (tmp / "fixtures").mkdir()
        shutil.copy(SUITE_DIR / "fixtures" / f"{name}.json", tmp / "fixtures" / f"{name}.json")
        for key in ("rubric_contract", "transcription_contract"):
            src = SUITE_DIR / manifest[key]
            dst = tmp / manifest[key]
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src, dst)
        gt_dst = tmp / manifest["gt"]
        gt_dst.parent.mkdir(parents=True, exist_ok=True)
        gt_dst.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
        with pytest.raises(GTValidationError, match="ATTEMPTED"):
            read_gt_judgments(name, suite_dir=tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_hobby_has_no_unattempted_scopes_by_construction():
    """No selection groups ⇒ an empty answer is a real skip the grader must
    match ([T1-SKIP]), never a question the exam invited her to leave."""
    for name in HOBBY:
        assert unattempted_questions(load_bundle(name)) == set(), name


def test_the_row_flag_and_the_gates_exclude_unattempted():
    """The three consumers key on the same field: the scorer's Tier-2 set,
    reporting's aggregate, and gates._included_rows (K1's denominator)."""
    from .schemas import TerminalScore
    from .tools.gates import _included_rows

    assert "unattempted" in TerminalScore.__dataclass_fields__
    trial = {"valid": True, "diagnostic_subset": False, "fixture": "f",
             "terminals": [{"terminal_id": "a", "unattempted": True},
                           {"terminal_id": "b", "unattempted": False},
                           {"terminal_id": "c"}]}                      # an OLD row
    kept = {r["terminal_id"] for r in _included_rows([trial])}
    assert kept == {"b", "c"}, "an unattempted terminal reached K1's denominator"


# ---------------------------------------------------------------------------
# Track B 1b (owner ruling 2026-09-27): `FixtureGT.awarded` is Optional. A null
# award is an UNSELECTED question ("Question not selected (choose-4-of-6)"),
# and the scorer, the gates and the expressibility guard SKIP it — never score
# it as zero. The loader keeps the completion check: a null on an ATTEMPTED
# question is still an unfinished judgment, refused under require_gt=True.
# ---------------------------------------------------------------------------

from decimal import Decimal

from . import synth


def _unselected_q2_bundle(awards):
    """choose-1-of-{q1,q2} + mandatory q3; the student sat q1 and q3 only."""
    from .fixtures import assemble_bundle
    gt = synth.make_gt(awards, fixture="synthetic-selection")
    transcription = synth.make_transcription([(1, None, "answer to q one"),
                                              (3, None, "answer to q three")])
    return assemble_bundle("synthetic-selection", synth.make_selection_contract(),
                           transcription, gt=gt)


def test_every_bagrut_fixture_loads_with_its_gt():
    """The acceptance fact: all seven exam-2 fixtures load under require_gt=True,
    and every null the owner left is on a question the TRANSCRIPTION says the
    student did not sit."""
    nulls = scored = 0
    for name in BAGRUT:
        bundle = load_bundle(name, require_gt=True)
        assert bundle.gt is not None, name
        skipped = unattempted_scope_keys(bundle)
        for t in bundle.gt.terminals:
            on_skipped = bundle.terminal_infos[t.terminal_id].scope_key in skipped
            if t.awarded is None:
                assert on_skipped, f"{name}: null award on an attempted question {t.terminal_id}"
                nulls += 1
            else:
                scored += 1
    assert scored == 298, scored
    assert nulls == 61 * 7 - 298, nulls


def test_a_null_award_is_skipped_by_the_scorer_never_scored_as_zero():
    from .scoring import score_trial
    bundle = _unselected_q2_bundle({"q1.c0": "8", "q2.c0": None, "q3.c0": "5"})
    scopes = {s.question_id: s for s in bundle.gradable_test.scopes}
    draft = synth.make_draft(bundle, [
        synth.make_scope_outcome(scopes["q1"], {"q1.c0": ("6", 0.9, "answer to q one", None)}),
        synth.make_skip_outcome(scopes["q2"]),
        synth.make_scope_outcome(scopes["q3"], {"q3.c0": ("5", 0.9, "answer to q three", None)}),
    ])
    ts = score_trial(draft, bundle, trial_index=0, cost_usd_value=0.03, cost_ceiling=0.10)

    # no agreement row for the unselected terminal — not a zero, not a row at all
    assert {t.terminal_id for t in ts.terminals} == {"q1.c0", "q3.c0"}
    assert ts.mae == pytest.approx((2 + 0) / 2)
    # totals: the unselected question is excluded from the total, on the GT side
    # by construction and on the AI side by best-k — so the sets AGREE
    assert ts.gt_total == "13" and ts.ai_total == "11" and ts.total_possible == "15"
    assert ts.exclusion_mismatch is False
    assert ts.tier1_pass, ts.tier1_failures


def test_a_null_award_still_gates_fabrication():
    """Skipped from the ARITHMETIC, not from the behaviour tripwires: a positive
    award citing ink the student never wrote fires on an unselected scope exactly
    as it does on a best-k-excluded one (PLAYBOOK §4 Selection)."""
    from app.schemas.ontology_types import QuoteValidationStatus
    from .scoring import score_trial
    bundle = _unselected_q2_bundle({"q1.c0": "8", "q2.c0": None, "q3.c0": "5"})
    scopes = {s.question_id: s for s in bundle.gradable_test.scopes}
    draft = synth.make_draft(bundle, [
        synth.make_scope_outcome(scopes["q1"], {"q1.c0": ("8", 0.9, "answer to q one", None)}),
        synth.make_scope_outcome(scopes["q2"], {"q2.c0": (
            "4", 0.9, "an invented sentence nobody wrote", QuoteValidationStatus.NOT_FOUND)}),
        synth.make_scope_outcome(scopes["q3"], {"q3.c0": ("5", 0.9, "answer to q three", None)}),
    ])
    ts = score_trial(draft, bundle, trial_index=0, cost_usd_value=0.03, cost_ceiling=0.10)
    assert "q2.c0" not in {t.terminal_id for t in ts.terminals}
    assert any(f.startswith("[T1-FABRICATED]") and "q2.c0" in f for f in ts.tier1_failures)


def test_a_null_on_an_attempted_question_is_refused_at_load():
    """The completion check survives the Optional: q1 WAS sat, so a null there is
    a judgment the owner has not made yet."""
    from .fixtures import GTValidationError
    with pytest.raises(GTValidationError, match="ATTEMPTED"):
        _unselected_q2_bundle({"q1.c0": None, "q2.c0": None, "q3.c0": "5"})


def test_a_null_row_never_reaches_the_gates():
    from .tools.gates import cross_tab, kills
    trial = {"valid": True, "diagnostic_subset": False, "fixture": "f",
             "terminals": [{"terminal_id": "a", "gt_awarded": None, "ai_awarded": "1"},
                           {"terminal_id": "b", "gt_awarded": "0", "ai_awarded": "0"}]}
    points = {("f", "a"): Decimal("2"), ("f", "b"): Decimal("2")}
    assert cross_tab([trial], points) == {("ZERO", "ZERO"): 1}
    assert kills([trial], points, {})["K1"]["value"] == "1/1"


def test_expressibility_skips_an_unselected_question():
    from app.agents.grader.plan_schemas import GradingPlan, PlanCheck, TerminalPlan
    from .plan_expressibility import expressibility_errors
    bundle = _unselected_q2_bundle({"q1.c0": "8", "q2.c0": None, "q3.c0": "5"})
    plan = GradingPlan(
        plan_version="synthetic/v1", exam_id="synthetic", rubric_contract_sha256="0" * 64,
        terminals=[TerminalPlan(terminal_id=f"q{i}.c0", points_possible=Decimal(p),
                                checks=[PlanCheck(check_id=f"q{i}.c0.k1", description_he="x",
                                                  kind="required", points=Decimal(p))])
                   for i, p in ((1, "10"), (2, "10"), (3, "5"))])
    errs = expressibility_errors(plan, bundle.gt, bundle.terminal_infos, Decimal("0.25"))
    assert [e for e in errs if "q2.c0" in e] == []
    assert any("q1.c0" in e for e in errs)          # 8 of an all-or-nothing 10: a real miss
