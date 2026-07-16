"""Pure unit tests for the scoring engine. Zero mocks; runs in `pytest -q`.

Several tests deliberately ENCODE the design thesis: a high difflib ratio can
coexist with a grading-critical transcription error, which the critical-token
metric is there to catch.
"""
from .critical_tokens import JAVA_BAGRUT
from .ground_truth import parse_ground_truth
from .scoring import ERROR_THRESHOLD, score_document


def _gold(md: str):
    return parse_ground_truth(md, doc_id="t")


def test_perfect_match_scores_one():
    md = "=== Q1 ===\nif (x == 5) { return; }\n"
    gold = _gold(md)
    pred = {(1, None): "if (x == 5) { return; }"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.doc_ratio_strict == 1.0
    assert s.coverage == 1.0
    assert s.missed_keys == () and s.extra_keys == ()
    assert not any(a.is_error for a in s.answers)
    assert s.critical.operator_recall == 1.0
    assert s.critical.structural_recall == 1.0
    assert s.critical.method_call_recall == 1.0
    assert s.critical.abbreviations_altered == ()


def test_equality_operator_error_is_caught_by_critical_not_difflib():
    """THE core thesis: '==' -> '=' barely moves difflib but tanks operator recall."""
    gold = _gold("=== Q1 ===\nif (x == 5) { y = 1; }\n")
    pred = {(1, None): "if (x = 5) { y = 1; }"}   # student wrote ==, model dropped one
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.doc_ratio_strict > 0.9                # difflib is fooled
    assert s.critical.operator_recall < 1.0        # critical-token metric is not


def test_dropped_semicolon_caught_by_structural_recall():
    gold = _gold("=== Q1 ===\nint x = 5;\n")
    pred = {(1, None): "int x = 5"}                # missing ';'
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.structural_recall < 1.0


def test_call_without_parens_changes_method_calls():
    gold = _gold("=== Q1 ===\nfoo();\n")
    pred = {(1, None): "foo;"}                     # Bagrut: call without ()
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.method_call_recall < 1.0     # 'foo' no longer a detected call


def test_misread_method_name_caught():
    gold = _gold("=== Q1 ===\nx = GetRate();\n")
    pred = {(1, None): "x = GetRates();"}          # misread name
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.method_call_recall < 1.0


def test_abbreviation_expansion_flagged():
    """Model expanding CW -> Console.WriteLine erases a deduction and is flagged."""
    gold = _gold('=== Q1 ===\nCW("hi");\n')
    pred = {(1, None): 'Console.WriteLine("hi");'}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert "CW" in s.critical.abbreviations_altered


def test_line_comment_strip_is_layout_invariant():
    """A FAITHFUL transcription flattened onto one physical line (inline '//'
    comments, no newlines — legal model output, common under token pressure) must
    score the SAME critical-token recalls as its multi-line form.

    Regression for the bug where '//[^\\n]*' had no terminator: the first '//'
    swallowed the entire single-line answer, deleting every operator/bracket/
    method call after it and cratering recall (precision stayed 1.0 — the
    fingerprint of a decimated prediction signature, not a real miss).
    """
    gold = _gold(
        "=== Q1 ===\n"
        "int counterS = 0; // ספירת ספורט\n"
        "for (int i = 0; i < n; i++) { counterS++; }\n"
        "cw(getRate());\n"
    )
    flat = (
        "int counterS = 0; // ספירת ספורט for (int i = 0; i < n; i++) "
        "{ counterS++; } cw(getRate());"
    )                                              # SAME content, one physical line
    multi = (
        "int counterS = 0; // ספירת ספורט\n"
        "for (int i = 0; i < n; i++) { counterS++; }\n"
        "cw(getRate());"
    )                                              # SAME content, preserved newlines

    s_flat = score_document({(1, None): flat}, gold, profile=JAVA_BAGRUT)
    s_multi = score_document({(1, None): multi}, gold, profile=JAVA_BAGRUT)

    cf, cm = s_flat.critical, s_multi.critical
    # Layout must not change the grading-critical signal at all.
    assert cf.structural_recall == cm.structural_recall
    assert cf.operator_recall == cm.operator_recall
    assert cf.method_call_recall == cm.method_call_recall
    # And a faithful transcription must actually pass the recall floors.
    assert cf.structural_recall == 1.0
    assert cf.method_call_recall == 1.0   # 'for', 'cw', 'getRate' all still detected


def test_missing_answer_reduces_coverage():
    md = "=== Q1.א ===\na = 1;\n=== Q1.ב ===\nb = 2;\n"
    gold = _gold(md)
    pred = {(1, "א"): "a = 1;"}                    # Q1.ב missing entirely
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.coverage == 0.5
    assert s.missed_keys == ((1, "ב"),)
    assert s.doc_ratio_strict < 1.0               # missing content penalizes the doc


def test_extra_answer_recorded_as_segmentation_error():
    gold = _gold("=== Q1 ===\na = 1;\n")
    pred = {(1, None): "a = 1;", (9, None): "garbage = 0;"}  # hallucinated/mis-routed
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.extra_keys == ((9, None),)
    assert s.doc_ratio_strict < 1.0


def test_error_label_threshold():
    gold = _gold("=== Q1 ===\nthe quick brown fox jumps over the lazy dog\n")
    pred = {(1, None): "completely different content entirely unrelated"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    a = s.answers[0]
    assert a.ratio_strict < ERROR_THRESHOLD
    assert a.is_error is True


def test_strict_vs_lenient_illegible():
    gold = _gold("=== Q1 ===\nreturn value;\n")
    pred = {(1, None): "return v[?]lue;"}          # one illegible char
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.doc_ratio_lenient >= s.doc_ratio_strict  # lenient never worse


# --- review fixes: B2 (error label), B3 (no cancellation), B4 (keys), gate ------

from .keys import normalize_sub_id
from .scoring import GateConfig, gate_pass


def test_b4_latin_and_numeral_sub_ids_join_with_hebrew_gold():
    """Label-format mismatch must not count as segmentation error."""
    gold = _gold("=== Q1.א ===\nint x = 1;\n=== Q1.ב ===\nint y = 2;\n")
    pred = {(1, "a"): "int x = 1;", (1, "2"): "int y = 2;"}  # latin + numeral
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.coverage == 1.0
    assert s.missed_keys == () and s.extra_keys == ()


def test_b4_punctuation_stripped_from_sub_id():
    assert normalize_sub_id("א.") == "א"
    assert normalize_sub_id(" B) ") == "ב"
    assert normalize_sub_id(None) is None
    assert normalize_sub_id("ii") == "ii"  # out-of-vocab passes through stripped


def test_b3_no_cross_answer_cancellation():
    """A dropped ';' in Q1 must NOT be masked by a spurious ';' in Q2.

    Document-level multiset comparison would score recall 1.0 here (counts
    balance); per-answer scoring must catch the miss.
    """
    gold = _gold("=== Q1 ===\nint x = 1;\n=== Q2 ===\nint y = 2;\n")
    pred = {
        (1, None): "int x = 1",     # dropped ';'
        (2, None): "int y = 2;;",   # spurious extra ';'
    }
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    a1 = next(a for a in s.answers if a.key == (1, None))
    assert ";" in a1.critical.missed_structural        # the miss is localized
    assert a1.is_error                                  # and labels the answer
    assert s.critical.structural_recall < 1.0           # and survives aggregation


def test_b2_error_label_fires_on_critical_miss_despite_high_ratio():
    """The demo finding, pinned: '==' -> '=' in a long answer keeps ratio >= 0.98
    but MUST label the answer as an error (a flag firing here is a true positive)."""
    long_code = (
        "for(int i = 0; i < rates.GetArrShows().Length; i++)\n"
        "{\n"
        "    if (arrShows[i].GetIsOn() && arrShows[i].GetChl()==lowestRateChl)\n"
        "        CW(arrShows[i].GetName());\n"
        "}\n"
    )
    gold = _gold("=== Q1 ===\n" + long_code)
    pred = {(1, None): long_code.replace("GetChl()==", "GetChl()=", 1)}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    a = s.answers[0]
    assert a.ratio_strict >= ERROR_THRESHOLD   # difflib clause does NOT fire
    assert a.critical.has_miss                  # critical clause DOES
    assert a.is_error                           # disjunction labels it


def test_gate_is_conjunctive_difflib_alone_insufficient():
    """A document passing 0.98 difflib but carrying a critical miss FAILS the gate."""
    long_code = "if (x == 5) { y = longVariableNameHere + anotherLongName; }\n" * 4
    gold = _gold("=== Q1 ===\n" + long_code)
    pred = {(1, None): long_code.replace("==", "=", 1)}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.doc_ratio_strict >= 0.98           # would pass a naive gate
    passed, reasons = gate_pass(s)
    assert not passed                            # conjunctive gate rejects
    assert any("operator_recall" in r for r in reasons)


def test_gate_passes_perfect_document():
    gold = _gold("=== Q1 ===\nif (x == 5) { foo(); }\n")
    pred = {(1, None): "if (x == 5) { foo(); }"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    passed, reasons = gate_pass(s)
    assert passed and reasons == []


def test_gate_fails_on_incomplete_coverage():
    gold = _gold("=== Q1 ===\na = 1;\n=== Q2 ===\nb = 2;\n")
    pred = {(1, None): "a = 1;"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    passed, reasons = gate_pass(s)
    assert not passed
    assert any("coverage" in r for r in reasons)


def test_duplicate_canonical_pred_keys_concatenate_not_drop():
    """Two prediction fragments mapping to the same canonical key (e.g. 'א' and
    'a') concatenate — content is never silently dropped."""
    gold = _gold("=== Q1.א ===\nint x = 1;\nint y = 2;\n")
    pred = {(1, "א"): "int x = 1;", (1, "a"): "int y = 2;"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.coverage == 1.0
    assert s.answers[0].ratio_strict == 1.0


# --- Phase-1 (per-page) scoring ----------------------------------------------------

from .ground_truth import parse_page_ground_truth
from .scoring import score_page_document


def _pgold(md: str):
    return parse_page_ground_truth(md, doc_id="t")


def test_page_scoring_perfect_and_gate_compatible():
    gold = _pgold("=== PAGE 1 ===\nשאלה 1\nif (x == 5) { foo(); }\n")
    pred = {1: "שאלה 1\nif (x == 5) { foo(); }"}
    s = score_page_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.doc_ratio_strict == 1.0 and s.coverage == 1.0
    # gate_pass works on page scores via shared field names (duck-typed gate).
    passed, reasons = gate_pass(s)
    assert passed and reasons == []


def test_page_scoring_missing_page_fails_gate():
    gold = _pgold("=== PAGE 1 ===\na = 1;\n=== PAGE 2 ===\nb = 2;\n")
    pred = {1: "a = 1;"}
    s = score_page_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.missing_pages == (2,)
    assert s.coverage == 0.5
    passed, reasons = gate_pass(s)
    assert not passed and any("coverage" in r for r in reasons)


def test_page_scoring_critical_miss_localized_to_page():
    gold = _pgold("=== PAGE 1 ===\nint x = 1;\n=== PAGE 2 ===\nif (a == b) foo();\n")
    pred = {1: "int x = 1;", 2: "if (a = b) foo();"}     # == -> = on page 2
    s = score_page_document(pred, gold, profile=JAVA_BAGRUT)
    p2 = next(p for p in s.pages if p.page_number == 2)
    assert "==" in p2.critical.missed_operators
    assert p2.is_error
    p1 = next(p for p in s.pages if p.page_number == 1)
    assert not p1.is_error


def test_ratio_immune_to_autojunk_on_long_sequences():
    """Regression: difflib autojunk corrupted real-page ratios (0.88 -> 0.21).

    Build two >=200-char highly similar code-like strings; the correct ratio
    is ~0.99. With autojunk=True it collapses; the instrument must score high.
    """
    base = "for(inti=0;i<rates.length;i++){chlrates[i]+=arr[i].getrate();}" * 6
    gold = _gold("=== Q1 ===\n" + base)
    pred = {(1, None): base[:-1] + ")"}   # one-char difference
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert len(base) >= 200
    assert s.doc_ratio_strict > 0.95


def test_empty_page_prediction_counts_as_missing():
    """Degraded-empty page must fail coverage, not hide behind ratio 0.0."""
    gold = _pgold("=== PAGE 1 ===\na = 1;\n=== PAGE 2 ===\nb = 2;\n")
    pred = {1: "a = 1;", 2: "   \n  "}     # whitespace-only == empty
    s = score_page_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.missing_pages == (2,)
    assert s.coverage == 0.5
    passed, reasons = gate_pass(s)
    assert not passed and any("coverage" in r for r in reasons)


# --- grade-irrelevant casing: case folds that must NOT weaken grade-critical checks ---
# Change A folds abbreviation letter-case (the abbreviations_altered flag); Change B
# folds C# keyword letter-case in method_calls (named ScoringPolicy option, default ON).
# The load-bearing constraint, pinned below: each fold collapses ONLY letter case —
# an EXPANSION (CW->Console.WriteLine) and an identifier-content misread (GetRate->
# getRate) stay fully detected.

from .scoring import ScoringPolicy


def test_change_a_abbreviation_casefold_not_flagged_as_altered():
    """CW vs cw is the same abbreviation with different case — NOT 'altered'.

    Pinned BOTH directions so the fold is symmetric, not an artifact of which side
    happens to be upper-case.
    """
    gold = _gold('=== Q1 ===\nCW("hi"); CR();\n')
    s = score_document({(1, None): 'cw("hi"); cr();'}, gold, profile=JAVA_BAGRUT)
    assert s.critical.abbreviations_altered == ()

    gold_lc = _gold('=== Q1 ===\ncw("hi"); cr();\n')
    s_rev = score_document({(1, None): 'CW("hi"); CR();'}, gold_lc, profile=JAVA_BAGRUT)
    assert s_rev.critical.abbreviations_altered == ()


def test_change_a_abbreviation_expansion_still_flagged_under_casefold():
    """THE Change-A constraint: case-folding must NOT collapse an EXPANSION.

    CW -> Console.WriteLine removes the standalone abbreviation token entirely;
    that is a grade-relevant deduction-eraser and MUST still flag, even though
    case is now folded. Holds when the gold abbreviation is lower-case too —
    which the old case-sensitive matcher missed, so the fold strengthens this.
    """
    gold = _gold('=== Q1 ===\nCW("hi");\n')
    s = score_document({(1, None): 'Console.WriteLine("hi");'}, gold, profile=JAVA_BAGRUT)
    assert "CW" in s.critical.abbreviations_altered

    gold_lc = _gold('=== Q1 ===\ncw("hi");\n')
    s_lc = score_document({(1, None): 'Console.WriteLine("hi");'}, gold_lc, profile=JAVA_BAGRUT)
    assert "CW" in s_lc.critical.abbreviations_altered


def test_change_b_keyword_casefold_passes_method_call_recall():
    """For() vs for() is a grade-irrelevant keyword-case diff — recall stays 1.0
    under the default (ON) policy."""
    gold = _gold("=== Q1 ===\nFor (int i = 0; i < n; i++) { }\n")
    pred = {(1, None): "for (int i = 0; i < n; i++) { }"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.method_call_recall == 1.0
    assert s.critical.method_call_precision == 1.0


def test_change_b_policy_is_a_real_named_toggle():
    """The folds are explicit, named options — with BOTH off the prior case-SENSITIVE
    behavior is intact (For != for). (Change C also folds For/for as an identifier, so
    isolating the case-sensitive baseline now requires disabling it too.) These are the
    comparability breaks the RUNLOG marks."""
    gold = _gold("=== Q1 ===\nFor (int i = 0; i < n; i++) { }\n")
    pred = {(1, None): "for (int i = 0; i < n; i++) { }"}
    off = score_document(pred, gold, profile=JAVA_BAGRUT,
                         policy=ScoringPolicy(case_insensitive_keywords=False,
                                              case_insensitive_method_calls=False))
    assert off.critical.method_call_recall < 1.0
    assert ScoringPolicy().case_insensitive_keywords is True  # default ON


def test_change_b_keyword_casefold_does_not_mask_identifier_misread():
    """Change-B constraint, isolated: the KEYWORD fold alone does NOT fold an
    identifier's case. With Change C off, a real method name stays case-exact
    (GetRate -> getRate is a miss). (Under the DEFAULT policy Change C folds it —
    see test_change_c_* — per Noam's ruling that method-name case is not graded.)"""
    gold = _gold("=== Q1 ===\nx = GetRate();\n")
    pred = {(1, None): "x = getRate();"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT,
                       policy=ScoringPolicy(case_insensitive_method_calls=False))
    assert s.critical.method_call_recall < 1.0


def test_change_c_identifier_casefold_default_on():
    """Change C (Noam 2026-06-27, reversing the §8 identifier-case lock): method-name
    CASE is not graded, so the DEFAULT policy folds ALL method-call identifier case.
    GetRate/getRate, CW/cw, GetChl/Getchl all compare equal -> recall 1.0."""
    gold = _gold("=== Q1 ===\nx = GetRate(); CW(); y = GetChl();\n")
    pred = {(1, None): "x = getRate(); cw(); y = getchl();"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.method_call_recall == 1.0
    assert ScoringPolicy().case_insensitive_method_calls is True  # default ON


def test_change_c_identifier_casefold_does_not_mask_content_misread():
    """THE Change-C safety constraint: folding case must NOT collapse an identifier
    CONTENT misread. A letter add/drop (GetArrShows -> GetArrShow) stays a miss even
    under the default fold, so genuine perception errors still fail the gate."""
    gold = _gold("=== Q1 ===\nx = GetArrShows();\n")
    pred = {(1, None): "x = GetArrShow();"}
    s = score_document(pred, gold, profile=JAVA_BAGRUT)
    assert s.critical.method_call_recall < 1.0