"""Tests for the deterministic corrector and the false-fix referee. Pure, no API."""
from .corrector import CSHARP_KEYWORDS, Correction, correct_text
from .scoring import measure_corrections


SPEC = frozenset({"Hobby", "TvShow", "GetArrShows", "LowestRateChannel",
                  "hobbyName", "durationInMinutes"})


# --- tier "impossible": keyword targets only ----------------------------------------

def test_impossible_fixes_misspelled_keywords():
    r = correct_text("privaze int x; doble y;", policy="impossible")
    assert "private" in r.text and "double" in r.text
    kinds = {(c.original, c.corrected) for c in r.corrections}
    assert ("privaze", "private") in kinds and ("doble", "double") in kinds
    assert all(c.tier == "impossible" and c.target_kind == "keyword"
               for c in r.corrections)


def test_impossible_does_not_touch_keyword_casing():
    # While/Public/For are keywords case-insensitively -> known -> untouched.
    r = correct_text("While (x) Public For", policy="impossible")
    assert r.text == "While (x) Public For"
    assert r.corrections == ()


def test_impossible_leaves_valid_far_tokens():
    r = correct_text("int tmp = foo(bar);", policy="impossible")
    assert r.corrections == ()  # tmp/foo/bar near nothing


def test_impossible_does_not_correct_toward_spec():
    # Mobby is near spec 'Hobby' but NOT near any keyword -> impossible tier leaves it.
    r = correct_text("class Mobby {}", policy="impossible", spec_identifiers=SPEC)
    assert r.text == "class Mobby {}"
    assert r.corrections == ()


# --- tier "spec": adds spec-identifier targets (the risky tier) ---------------------

def test_spec_tier_corrects_spec_near_miss():
    r = correct_text("class Mobby {}", policy="spec", spec_identifiers=SPEC)
    assert r.text == "class Hobby {}"
    assert r.corrections[0].tier == "spec"
    assert r.corrections[0].target_kind == "spec_identifier"


def test_spec_tier_distance_2_caught_distance_3_flagged():
    # GetArrShow -> GetArrShows is dist 1; a dist-3 mangle is left (flagged by absence).
    r = correct_text("GetArrShow() GetXYZ()", policy="spec", spec_identifiers=SPEC)
    assert "GetArrShows()" in r.text
    assert "GetXYZ()" in r.text  # no unique target within 2


def test_protected_abbreviations_never_corrected():
    r = correct_text("CW(x); CR();", policy="spec", spec_identifiers=SPEC)
    assert r.text == "CW(x); CR();"
    assert r.corrections == ()


def test_uniqueness_ties_flag_not_guess():
    # two spec ids equidistant -> no unique target -> no correction
    spec = frozenset({"Catt", "Batt"})
    r = correct_text("Aatt", policy="spec", spec_identifiers=spec)
    assert r.text == "Aatt" and r.corrections == ()


# --- the false-fix referee ----------------------------------------------------------

def test_measure_counts_true_and_false_fixes():
    # gold says student wrote 'Mobby' (faithful error). Correcting to Hobby is a FALSE fix.
    false_scope = ("class Mobby {}", "class Mobby {}", "class Hobby {}",
                   (Correction("Mobby", "Hobby", "spec", "spec_identifier"),))
    # gold says 'Hobby'; pred misread 'Hoby'; correcting to Hobby is a TRUE fix.
    true_scope = ("class Hobby {}", "class Hoby {}", "class Hobby {}",
                  (Correction("Hoby", "Hobby", "spec", "spec_identifier"),))
    m = measure_corrections([false_scope, true_scope], n_fixtures=12)
    assert m.false_fix == 1 and m.true_fix == 1
    assert m.false_fix_rate == 0.5
    assert m.trustworthy is True
    assert m.by_tier["spec"]["false_fix"] == 1


def test_measure_trustworthiness_gate():
    m = measure_corrections([], n_fixtures=5)
    assert m.trustworthy is False
