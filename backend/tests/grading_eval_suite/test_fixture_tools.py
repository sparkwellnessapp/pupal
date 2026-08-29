"""
Fixture-pipeline tools guards [F0/F1/F4] — all in-memory, reading sibling GT
files read-only (the scope fence allows read + snapshot). Zero API calls.
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

SIBLING_TR = Path(__file__).resolve().parents[1] / "transcription_eval_suit"
SIBLING_RU = Path(__file__).resolve().parents[1] / "rubric_eval_suite"

# The grading suite keeps its OWN bare doc_ids; the sibling transcription corpus
# prefixes its fixtures with the exam ("hobby_tvshow.<student>", 2026-08-29), so the
# cross-suite read maps between the two namespaces here and nowhere else.
FIVE_DOCS = ["dan_basiuk", "din_ezra", "moran_aharon", "omer_gelber", "yonatan_basiuk"]
SIBLING_DOC = {d: f"hobby_tvshow.{d}" for d in FIVE_DOCS}


# ---------------------------------------------------------------------------
# F1 — draft-GT markdown -> TranscriptionContract, parity-guarded
# ---------------------------------------------------------------------------

def test_converter_parity_on_all_five_docs():
    """[F1] the converter must reproduce the sibling loader's answers
    byte-identically (keys and text) on every seed doc, or the pipeline aborts."""
    from tests.transcription_eval_suit.ground_truth import load_ground_truth
    from .tools.convert_transcription_gt import convert_gold_document

    for doc in FIVE_DOCS:
        p = SIBLING_TR / "draft_benchmarks" / f"{SIBLING_DOC[doc]}.md"
        gold = load_ground_truth(p)
        contract = convert_gold_document(gold)
        got = [(a.question_number, a.sub_question_id, a.answer_text)
               for a in contract.answers]
        want = [(a.question_number, a.sub_question_id, a.answer_text)
                for a in gold.answers]
        assert got == want, f"{doc}: converter diverges from the sibling loader"
        assert len(got) == len(set((q, s) for q, s, _ in got))   # unique keys


# ---------------------------------------------------------------------------
# F0 — hobby correction: original blocks, corrected compiles [R5/H1]
# ---------------------------------------------------------------------------

def test_original_hobby_gt_blocks_compilation():
    from app.services.contract_compiler import CompilationError
    from .tools.f0_hobby_correction import load_original, compile_response

    original = load_original()
    with pytest.raises(CompilationError) as exc:
        compile_response(original)
    msg = str(exc.value)
    assert "q2" in msg    # the two q2 sum shadows are the blockers


def test_corrected_hobby_compiles_clean_with_recorded_fix():
    """[R5/H1] the fix_proposal applied mechanically: c6 moves to a new ג,
    sums reconcile at every level, id renamed path-honestly [DL-5]."""
    from .tools.f0_hobby_correction import (
        apply_recorded_fix, compile_response, load_original)

    corrected = apply_recorded_fix(load_original())
    contract = compile_response(corrected)          # must NOT raise
    assert contract.total_points == Decimal("100")

    q2 = next(q for q in contract.questions if q.question_id == "q2")
    subs = {sq.sub_question_id: sq for sq in q2.sub_questions}
    assert set(subs) == {"א", "ב", "ג"}
    assert subs["ג"].points == Decimal("16")
    assert [c.criterion_id for c in subs["ג"].criteria] == ["q2.ג.c0"]   # [DL-5]
    # [DL-7 / H1-A1, ratified 2026-08-24]: a moved criterion renames its
    # CHILDREN with it — DL-5's own principle applied to the terminal level
    # the original proposal didn't know existed.
    gimel_children = [sc.sub_criterion_id for sc in (subs["ג"].criteria[0].sub_criteria or [])]
    assert gimel_children == ["q2.ג.c0.s0", "q2.ג.c0.s1", "q2.ג.c0.s2", "q2.ג.c0.s3"], gimel_children
    assert subs["ג"].criteria[0].points == Decimal("16")
    # ב no longer carries the mislabeled component and its sums reconcile
    assert sum(c.points for c in subs["ב"].criteria) == Decimal("29") == subs["ב"].points
    assert sum(sq.points for sq in q2.sub_questions) == q2.total_points == Decimal("60")
    # the stale error-description artifacts were dropped [DL-6]
    assert corrected.annotations == []
    assert corrected.pedagogical_mistakes == []


# ---------------------------------------------------------------------------
# F4 — GT skeleton: every terminal pre-populated, judgments empty
# ---------------------------------------------------------------------------

def test_gt_skeleton_prepopulates_all_terminals():
    from . import synth
    from .tools.build_gt_skeleton import build_skeleton

    bundle = synth.make_bundle()          # no GT needed
    sk = build_skeleton(bundle)
    ids = [t["terminal_id"] for t in sk["terminals"]]
    assert set(ids) == set(bundle.terminal_infos)
    assert all(t["awarded"] is None for t in sk["terminals"])       # owner fills
    assert all(t["evidence_exists"] is None for t in sk["terminals"])
    # [M1/H1-A2] skeletons emit the ruled v0 GT class: teacher_validated
    assert sk["blind"] is False and sk["gt_source"] == "teacher_validated"
    assert sk["proposed_by"] and sk["validated_by"] == "Noam"
    assert sk["fixture"] == "synthetic"
    # points shown as authoring aid, but NOT a FixtureGT field (stripped on load)
    assert all("points_possible" in t for t in sk["terminals"])


# ---------------------------------------------------------------------------
# Path-honesty structural guard [H1-A1 ruling, 2026-08-24] — closes the CLASS
# DL-7 was an instance of: every terminal id in every loaded fixture universe
# must be prefixed by its full ancestor chain (sub-criterion by its criterion
# id, criterion by its scope target). Would have caught DL-7 at birth.
# ---------------------------------------------------------------------------

FIXTURE_NAMES = FIVE_DOCS


def test_terminal_ids_are_path_honest_in_all_bundles():
    from .fixtures import load_bundle
    offenders = []
    for name in FIXTURE_NAMES:
        bundle = load_bundle(name, require_gt=False)
        for scope in bundle.gradable_test.scopes:
            target = (scope.question_id if scope.sub_question_id is None
                      else f"{scope.question_id}.{scope.sub_question_id}")
            for criterion in scope.criteria:
                if not criterion.criterion_id.startswith(target + "."):
                    offenders.append((name, target, criterion.criterion_id))
                for sc in (criterion.sub_criteria or []):
                    if not sc.sub_criterion_id.startswith(criterion.criterion_id + "."):
                        offenders.append((name, criterion.criterion_id, sc.sub_criterion_id))
    assert not offenders, f"path-dishonest ids (child not prefixed by parent): {offenders}"


def test_terminal_universe_unchanged_after_prior_context_seam():
    """[PR-G1 item 6] the seam is additive: all five bundles load, 38 terminals
    each (190 judgments), hash pins green — nothing the suite hashes moves."""
    from .fixtures import load_bundle
    total = 0
    for name in FIVE_DOCS:
        bundle = load_bundle(name, require_gt=False)
        assert len(bundle.terminal_infos) == 38, (name, len(bundle.terminal_infos))
        total += len(bundle.terminal_infos)
    assert total == 190


# ---------------------------------------------------------------------------
# H1-A2 (ratified 2026-08-25) — embedded ratified model solutions.
# Source of truth: benchmarks/contracts/_sources/model_solutions_transcription.md
# (owner-supplied teacher screenshots, transcribed by claude-fable-5, ratified
# by Noam; one in-review correction applied).
# ---------------------------------------------------------------------------

SOLUTION_KEYS = ["q1.א", "q1.ב", "q1.ג", "q2.א", "q2.ב", "q2.ג"]


def test_h1a2_all_six_example_solutions_embedded_byte_equal():
    """[H1-A2 item 1a] every sub-question's example_solution is non-empty and
    byte-equal to its ratified source block (fences stripped, no normalization)."""
    from .tools.f0_hobby_correction import (
        apply_recorded_fix, compile_response, load_original, load_model_solutions)
    solutions = load_model_solutions()
    assert set(solutions) == set(SOLUTION_KEYS)
    contract = compile_response(apply_recorded_fix(load_original()))
    fields = {}
    for q in contract.questions:
        for sq in q.sub_questions or []:
            fields[f"{q.question_id}.{sq.sub_question_id}"] = sq.example_solution
    for key in SOLUTION_KEYS:
        assert fields.get(key), f"{key}: example_solution empty"
        assert fields[key] == solutions[key], f"{key}: not byte-equal to the ratified block"
    # byte-fidelity spot pins — the exact hazards the ruling names (no
    # normalization, no reformatting):
    assert "int[101];      //" in fields["q2.ב"]            # the stray // kept
    assert "if (   sumRates[chl] > 0" in fields["q2.ב"]     # multiline if( formatting
    assert "internal class Hobby" in fields["q1.א"]          # internal kept
    assert "// מקדמים את המונה מס' העצמים המלאים" in fields["q1.ב"]  # Hebrew comment verbatim


def test_h1a2_q2_alef_is_constructor_then_updaterate():
    """[H1-A2 item 1b] q2.א = the constructor block + the UpdateRate block,
    concatenated in that order (images 3+4, one scope)."""
    from .tools.f0_hobby_correction import (
        apply_recorded_fix, compile_response, load_original, load_model_solutions)
    contract = compile_response(apply_recorded_fix(load_original()))
    q2 = next(q for q in contract.questions if q.question_id == "q2")
    alef = next(sq for sq in q2.sub_questions if sq.sub_question_id == "א")
    es = alef.example_solution or ""
    i_ctor = es.index("public TvShow(string name, int channel)")
    i_upd = es.index("public void UpdateRate(int numViewers)")
    assert i_ctor < i_upd
    assert es == load_model_solutions()["q2.א"]


# ---------------------------------------------------------------------------
# Phase-B closeout corpus pin (2026-08-26). The five GTs are ratified data;
# their totals are known-good through the REAL selection_scoring. This makes
# the closeout verification permanent: any silent GT edit moves a total and
# reds here. Re-anchor ONLY on an owner-ratified GT amendment (RUNLOG-entried),
# exactly like the byte pins — never to make a number pass.
# ---------------------------------------------------------------------------

CORPUS_TOTALS = {"din_ezra": "55.5", "dan_basiuk": "84.0", "omer_gelber": "89",
                 "moran_aharon": "92", "yonatan_basiuk": "92.5"}


def test_corpus_totals_via_real_selection_scoring():
    from decimal import Decimal
    from app.services.selection_scoring import ScopeScore, score_with_selection
    from .fixtures import load_bundle
    universes = set()
    for name, expected in CORPUS_TOTALS.items():
        bundle = load_bundle(name, require_gt=True)     # all loader guards run here
        gt = bundle.gt
        assert len(gt.terminals) == 38, (name, len(gt.terminals))
        universes.add(frozenset(t.terminal_id for t in gt.terminals))
        by_scope = {}
        for t in gt.terminals:
            key = bundle.terminal_infos[t.terminal_id].scope_key
            by_scope[key] = by_scope.get(key, Decimal("0")) + t.awarded
        scoring = score_with_selection(
            [ScopeScore(q, s, a) for (q, s), a in by_scope.items()], bundle.rubric_contract)
        assert scoring.total_score == Decimal(expected), (name, str(scoring.total_score))
        assert scoring.total_possible == Decimal("100"), name
        # [M1] every corpus GT is the ratified v0 provenance class
        assert gt.gt_source == "teacher_validated" and gt.blind is False
        assert gt.proposed_by and gt.validated_by
    # one terminal-id universe across the whole corpus (same exam, same contract)
    assert len(universes) == 1, "corpus fixtures disagree on the terminal universe"
