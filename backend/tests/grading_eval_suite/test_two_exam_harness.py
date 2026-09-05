"""
The two-exam harness — exam 2 is a DATA DROP, not a refactor.

The theory these falsify is *"the exam is a property of the run"*, which was
encoded as one `config["plan"]` per run and run-level provenance read off
`bundles[0]`. True while the corpus was one exam; false the moment a second one
existed. The exam is a property of the FIXTURE.

The acceptance test is `test_hobby_scores_are_byte_identical`: everything else
here can pass while the harness silently moves a hobby number, and that would be
the only failure this work cannot have.
"""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from .exam_resolution import (
    ExamResolutionError,
    ResolvedPlan,
    assert_gt_exam_id_agrees,
    manifest_exam_id,
    resolve_plan,
)
from .fixtures import SUITE_DIR, load_bundle

HOBBY = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk"]
BAGRUT = [f"bagrut_899371.{s}" for s in
          ["din_ezra", "itay_kraft", "noam_breinshtein", "raz_cohen",
           "roni_ben_ezra", "yael_kogan", "yahli_cohen"]]

HOBBY_PLAN = "plans/hobby_tvshow.plan.json"


# ---------------------------------------------------------------------------
# two-exam-corpus-loads
# ---------------------------------------------------------------------------

def test_two_exam_corpus_loads():
    """Both exams assemble in ONE process, each against its own contract.

    The two exams are structurally different — 6 scopes / 38 terminals vs
    13 / 61, and only one has selection groups — so a harness that had quietly
    kept a single-exam assumption would produce identical shapes here.
    """
    hobby = [load_bundle(n) for n in HOBBY]
    bagrut = [load_bundle(n, require_gt=False) for n in BAGRUT]

    assert {b.exam_id for b in hobby} == {"hobby_tvshow"}
    assert {b.exam_id for b in bagrut} == {"bagrut_899371"}

    hobby_shape = {(len(b.gradable_test.scopes), len(b.terminal_infos)) for b in hobby}
    bagrut_shape = {(len(b.gradable_test.scopes), len(b.terminal_infos)) for b in bagrut}
    assert len(hobby_shape) == 1 and len(bagrut_shape) == 1, (
        "fixtures of one exam must share a terminal universe")
    assert hobby_shape != bagrut_shape, (
        "the two exams produced the same shape — a single-exam assumption survived")

    # the contracts are genuinely different artifacts, not one reused
    assert len({b.rubric_contract_hash for b in hobby + bagrut}) == 2


def test_din_ezra_sat_both_exams_without_a_collision():
    """The name collision that forced exam-namespaced fixtures. `din_ezra`'s
    hobby GT is RATIFIED; an un-namespaced exam-2 drop would have overwritten it."""
    hobby = load_bundle("din_ezra")
    bagrut = load_bundle("bagrut_899371.din_ezra", require_gt=False)
    assert hobby.exam_id != bagrut.exam_id
    assert hobby.rubric_contract_hash != bagrut.rubric_contract_hash
    assert hobby.gt is not None, "the ratified hobby GT must still be there"


def test_every_fixture_declares_its_exam():
    """A fixture that cannot name its exam cannot be routed to a plan."""
    for name in HOBBY + BAGRUT:
        assert manifest_exam_id(name) is not None, f"{name}: no exam_id"


# ---------------------------------------------------------------------------
# plan-resolves-by-exam-id
# ---------------------------------------------------------------------------

def test_plan_resolves_by_exam_id():
    config = {"plans": {"hobby_tvshow": HOBBY_PLAN,
                        "bagrut_899371": "plans/bagrut_899371.plan.json"}}
    resolved = resolve_plan("hobby_tvshow", config, fixture="din_ezra")
    assert isinstance(resolved, ResolvedPlan)
    assert resolved.exam_id == "hobby_tvshow"
    assert resolved.ref == HOBBY_PLAN
    assert len(resolved.sha256) == 64


def test_the_run_level_plan_key_still_works_alone():
    """Back-compat is the whole reason a one-exam run is byte-identical: the 20
    existing configs carry `plan`, not `plans`, and must keep resolving."""
    resolved = resolve_plan("hobby_tvshow", {"plan": HOBBY_PLAN}, fixture="din_ezra")
    assert resolved.ref == HOBBY_PLAN
    # …and it resolves even for a fixture whose manifest predates exam_id
    assert resolve_plan(None, {"plan": HOBBY_PLAN}).ref == HOBBY_PLAN


def test_unknown_exam_id_refuses_before_any_spend():
    """Grading exam 2 under exam 1's plan is a silently wrong benchmark. The
    contract-hash pin would eventually catch it, but this refuses EARLIER and
    names the actual problem."""
    config = {"plans": {"hobby_tvshow": HOBBY_PLAN}}
    with pytest.raises(ExamResolutionError, match="no plan for exam_id"):
        resolve_plan("bagrut_899371", config, fixture="bagrut_899371.din_ezra")


def test_a_plan_map_with_an_unroutable_fixture_refuses():
    config = {"plans": {"hobby_tvshow": HOBBY_PLAN}}
    with pytest.raises(ExamResolutionError, match="declares no 'exam_id'"):
        resolve_plan(None, config, fixture="legacy")


def test_a_missing_plan_file_refuses_by_path():
    config = {"plans": {"ghost": "plans/does_not_exist.plan.json"}}
    with pytest.raises(ExamResolutionError, match="does not exist"):
        resolve_plan("ghost", config, fixture="x")


def test_no_plan_at_all_returns_none_for_the_caller_to_judge():
    """Only the caller knows whether the architecture requires a plan (v3 does
    not), so this reports absence rather than deciding."""
    assert resolve_plan("hobby_tvshow", {"model_key": "x"}) is None


def test_config_refuses_both_plan_and_plans():
    """Two ways to answer one question is how a run silently grades under the
    plan nobody meant."""
    from .runner import _validate_config
    with pytest.raises(SystemExit, match="BOTH 'plan' and 'plans'"):
        _validate_config("bad", {"model_key": "claude-sonnet-5", "architecture": "v5",
                                 "plan": HOBBY_PLAN, "plans": {"a": HOBBY_PLAN}})


def test_v5_accepts_a_plans_map_as_its_plan_source():
    from .runner import _validate_config
    _validate_config("ok", {"model_key": "claude-sonnet-5", "architecture": "v5",
                            "plans": {"hobby_tvshow": HOBBY_PLAN}})


# ---------------------------------------------------------------------------
# gt-exam-id-must-agree-with-the-manifest
# ---------------------------------------------------------------------------

def test_gt_exam_id_must_agree_with_the_manifest():
    """§0.4 — two sources of one fact are only safe when a disagreement is loud."""
    assert_gt_exam_id_agrees("f", "hobby_tvshow", "hobby_tvshow")   # agrees
    assert_gt_exam_id_agrees("f", "hobby_tvshow", None)             # GT silent: fine
    assert_gt_exam_id_agrees("f", None, "hobby_tvshow")             # legacy manifest
    with pytest.raises(ExamResolutionError, match="benchmark the wrong pairing"):
        assert_gt_exam_id_agrees("f", "hobby_tvshow", "bagrut_899371")


def test_a_gt_naming_the_wrong_exam_is_refused_at_load(tmp_path):
    """End to end through `load_bundle`, not just the pure helper."""
    from .fixtures import GTValidationError, assemble_bundle
    from .schemas import FixtureGT

    bundle = load_bundle("din_ezra")
    gt = bundle.gt.model_copy(update={"exam_id": "bagrut_899371"})
    with pytest.raises(ExamResolutionError):
        assemble_bundle("din_ezra", bundle.rubric_contract,
                        bundle.transcription_contract, gt,
                        exam_id="hobby_tvshow")


# ---------------------------------------------------------------------------
# expressibility-runs-per-exam
# ---------------------------------------------------------------------------

def test_expressibility_runs_per_exam():
    """The pre-spend guard must run against each fixture's OWN plan.

    Before this, run-level provenance called `_load_plan(config, bundles[0])` —
    so on a two-exam corpus the guard proved something about fixture zero and the
    record implied it covered them all.
    """
    from .runner import _load_plan

    config = {"architecture": "v5", "plans": {"hobby_tvshow": HOBBY_PLAN}}
    for name in HOBBY:
        bundle = load_bundle(name)
        plan, sha, resolved = _load_plan(config, bundle, SUITE_DIR)
        assert resolved.exam_id == "hobby_tvshow"
        assert plan.rubric_contract_sha256 == bundle.rubric_contract_hash, (
            "the D5 plan<->contract pin must hold per fixture")

    # …and a fixture whose exam the config does not map never reaches a spend
    bagrut = load_bundle("bagrut_899371.din_ezra", require_gt=False)
    with pytest.raises(ExamResolutionError):
        _load_plan(config, bagrut, SUITE_DIR)


def test_plans_provenance_covers_every_exam_not_just_the_first():
    """Provenance that is WRONG is worse than provenance that is absent, because
    it is quotable. This is the `bundles[0]` defect, pinned."""
    from .runner import _plans_provenance

    config = {"architecture": "v5", "plans": {"hobby_tvshow": HOBBY_PLAN}}
    bundles = [load_bundle(n) for n in HOBBY]
    prov = _plans_provenance(config, bundles, SUITE_DIR)

    assert set(prov) == {"hobby_tvshow"}, "keyed by exam, one entry per exam"
    entry = prov["hobby_tvshow"]
    assert entry["fixtures"] == sorted(HOBBY), "every fixture is accounted for"
    assert entry["plan"] == HOBBY_PLAN
    assert entry["plan_version"] and len(entry["plan_sha256"]) == 64


# ---------------------------------------------------------------------------
# selection-scoring-is-exercised-by-a-choose-k-exam
# ---------------------------------------------------------------------------

def test_selection_scoring_is_exercised_by_a_choose_k_exam():
    """`scoring.py` has always called the real `score_with_selection` and has a
    [T1-SELECTION] tripwire, but NO fixture could exercise it: hobby has no
    selection groups. Exam 2 is choose-4-of-6, so the path is live for the first
    time — and INV-4's achievable arithmetic is what must hold.
    """
    bundle = load_bundle("bagrut_899371.din_ezra", require_gt=False)
    contract = bundle.rubric_contract
    groups = contract.selection_groups
    assert groups, "exam 2 must carry its selection group or it proves nothing"

    group = groups[0]
    assert group.choose_k == 4 and len(group.of_question_ids) == 6

    # achievable == best-k, NOT the offered sum (the bug that halved every
    # selection-exam grade — selection_scoring.py's docstring)
    per = sorted((q.total_points for q in contract.questions
                  if q.question_id in group.of_question_ids), reverse=True)
    offered = sum(q.total_points for q in contract.questions)
    assert sum(per[:group.choose_k]) == contract.total_points
    assert offered > contract.total_points, (
        "a choose-k exam must offer more than it awards, or it is not one")


# ---------------------------------------------------------------------------
# THE ACCEPTANCE TEST — hobby-scores-are-byte-identical
# ---------------------------------------------------------------------------

_BASELINE_RUN = "20260830-205954_sonnet5-v5"


@pytest.mark.integration
def test_hobby_scores_are_byte_identical():
    """Re-score a PUBLISHED run through the new code and compare the `trials`
    array byte-for-byte with that run's own committed results.json.

    WHY THE TRIALS ARRAY AND NOT THE WHOLE FILE. Adding exam-2 files under
    `benchmarks/`, `plans/` and `fixtures/` changes `suite_hash` BY CONSTRUCTION
    — `_hashed_paths()` globs those directories whole — and that is correct: the
    instrument's corpus grew and `suite_hash` exists to say so. Pretending
    otherwise would be the lie. The scores are the thing that must not move, and
    they are where a silent corruption would live.
    """
    from app.schemas.graded_test_draft import GradedTestDraft
    from .scoring import score_trial

    run_dir = SUITE_DIR / "results" / _BASELINE_RUN
    if not run_dir.exists():
        pytest.skip(f"baseline run {_BASELINE_RUN} not present")
    baseline = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
    by_fixture = {t["fixture"]: t for t in baseline["trials"]}
    assert by_fixture, "baseline carries no trials"

    drafts_dir = run_dir / "drafts"
    for fixture, expected in sorted(by_fixture.items()):
        draft_path = drafts_dir / f"{fixture}_r{expected['trial_index']}.json"
        if not draft_path.exists():
            pytest.skip(f"cached draft missing for {fixture}")
        draft = GradedTestDraft.model_validate_json(
            draft_path.read_text(encoding="utf-8"))
        bundle = load_bundle(fixture)
        assert bundle.exam_id == "hobby_tvshow"

        # The run's OWN cost inputs — Tier-1 carries a cost-ceiling tripwire, so
        # re-scoring with different money would change the verdict for a reason
        # that has nothing to do with the harness.
        got = score_trial(
            draft, bundle,
            trial_index=expected["trial_index"],
            cost_usd_value=expected.get("cost_usd"),
            cost_ceiling=float(baseline["provenance"].get("cost_ceiling") or 0.15),
            latency_s=expected.get("latency_s"),
            provisional=expected.get("provisional", False),
            per_scope_cost=expected.get("per_scope_cost_usd") or None,
            rerun_count=expected.get("rerun_count", 0),
            rerun_reason=expected.get("rerun_reason"),
            invalid_reason=expected.get("invalid_reason"))
        got_d, exp_d = got.to_dict(), dict(expected)

        # [OD-16, R-2 2026-09-05] `unattempted` is an ADDITIVE row field the
        # published baseline predates. The baseline is normalised FORWARD (the
        # field it could not have had is added at its default) — never the
        # other way, which would let a real drift hide behind "extra field".
        # Hobby has no selection groups, so the only honest value is False.
        for row in exp_d.get("terminals", []):
            row.setdefault("unattempted", False)

        # Fields the RUN stamps (cost/latency/rerun bookkeeping), not the scorer.
        for key in ("cost_usd", "latency_s", "rerun_count", "rerun_reason",
                    "input_tokens", "output_tokens", "cached_input_tokens",
                    "per_scope_cost_usd", "provisional", "invalid_reason",
                    "valid"):
            got_d.pop(key, None)
            exp_d.pop(key, None)

        assert json.dumps(got_d, sort_keys=True, ensure_ascii=False) == \
               json.dumps(exp_d, sort_keys=True, ensure_ascii=False), (
            f"{fixture}: re-scoring the published run under the two-exam harness "
            f"produced a DIFFERENT score. The harness moved a hobby number — "
            f"that is the one failure this work cannot have.")


# ---------------------------------------------------------------------------
# Review findings — the two defects the SECOND exam introduced
# ---------------------------------------------------------------------------

def test_every_plan_is_resolved_before_the_first_spend():
    """R1. With ONE exam "pre-spend" was true for free: the only plan was
    validated before the only fixture graded. With TWO, resolving inside the
    grading loop means an unroutable exam-2 plan is found only when exam 2's
    turn comes — after every exam-1 fixture has already been paid for. Same
    guard, same docstring, silently worth less.

    Driven through `run_grade` with an agent_factory that RECORDS spend: a
    config that cannot route exam 2 must raise having graded nothing at all.
    """
    from .runner import _plans_provenance

    config = {"architecture": "v5", "plans": {"hobby_tvshow": HOBBY_PLAN}}
    bundles = [load_bundle(n) for n in HOBBY]
    bundles.append(load_bundle("bagrut_899371.din_ezra", require_gt=False))

    # the gate is a single call over ALL bundles, so it cannot half-succeed
    with pytest.raises(ExamResolutionError):
        _plans_provenance(config, bundles, SUITE_DIR)

    # and the runner calls it before the loop, not inside it
    import inspect
    from . import runner as runner_mod
    src = inspect.getsource(runner_mod.run_grade)
    gate = src.index("_plans_provenance(config, bundles, suite_dir)")
    loop = src.index("for bundle in bundles:\n        gradable, scope_filter")
    assert gate < loop, (
        "the pre-spend gate moved AFTER the grading loop — an unroutable plan "
        "would be discovered only once earlier fixtures had been paid for")


def test_suite_hash_covers_every_artifact_a_manifest_references():
    """R4. The globs assume exam 1's layout (`benchmarks/…`). Exam 2 landed its
    contract and transcriptions at the suite root, so they sat OUTSIDE the
    instrument hash: the exam-2 contract could change and `suite_hash` would not
    move — the one thing it exists to prevent, failing silently."""
    from .runner import _hashed_paths

    hashed = {p.resolve() for p in _hashed_paths()}
    for name in HOBBY + BAGRUT:
        manifest = json.loads(
            (SUITE_DIR / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
        for key in ("rubric_contract", "transcription_contract"):
            path = (SUITE_DIR / manifest[key]).resolve()
            assert path.is_file(), f"{name}: {key} missing at {path}"
            assert path in hashed, (
                f"{name}: {key} is outside suite_hash — it could change without "
                f"the instrument hash moving")


def test_suite_hash_moves_when_an_exam_2_artifact_changes(tmp_path):
    """The property above, demonstrated rather than asserted structurally."""
    from .runner import _hashed_paths, _suite_hash

    contract = SUITE_DIR / "compiled_rubric_bagrut.json"
    original = contract.read_bytes()
    before = _suite_hash()
    try:
        contract.write_bytes(original + b"\n")
        assert _suite_hash() != before, (
            "changing the exam-2 contract did not move suite_hash")
    finally:
        contract.write_bytes(original)
    assert _suite_hash() == before, "the restore did not round-trip"


def test_hashed_paths_are_deduplicated_and_ordered():
    """Manifest-referenced files overlap the globs; a duplicate would make the
    hash depend on how many manifests happen to name the same file."""
    from .runner import _hashed_paths

    paths = _hashed_paths()
    assert len(paths) == len(set(paths)), "duplicate paths in the instrument hash"
    assert paths == sorted(set(paths)), "hash input order is not deterministic"
