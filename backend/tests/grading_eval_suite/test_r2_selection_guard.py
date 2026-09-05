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
