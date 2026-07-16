"""
Zero-mock tests for the pure trust-layer modules:
app/services/transcription/flagging.py and page_provenance.py.
"""
from app.services.transcription.flagging import (
    FlagSpan,
    anchor_flags,
    brace_lint,
    compute_flags,
    compute_page_flags,
    diff_spans,
    merge_adjacent,
    tokenize,
)
from app.services.transcription.page_provenance import (
    align_answer_to_pages,
    norm_line,
)


# --- tokenization ------------------------------------------------------------

def test_tokenize_multichar_operators_are_single_tokens():
    toks = tokenize("if(a != b && c <= d) x += 1;")
    assert "!=" in toks and "&&" in toks and "<=" in toks and "+=" in toks
    assert "=" not in toks  # no fragment leakage from multi-char ops


def test_tokenize_hebrew_runs_and_illegible_marker():
    toks = tokenize("// סופר כמה [?] פעמים")
    assert "סופר" in toks and "[?]" in toks


# --- disagreement flags -------------------------------------------------------

def test_identical_readers_produce_no_flags():
    page = "public class Hobby\n{\nint x = 0;\n}"
    assert compute_page_flags(1, page, [page, page]) == []


def test_operator_flip_is_flagged_with_alternative_and_vote_count():
    base = "if(hobbies[i] == null)\n{\ncount++;\n}"
    r1 = "if(hobbies[i] != null)\n{\ncount++;\n}"
    r2 = "if(hobbies[i] != null)\n{\ncount++;\n}"
    flags = compute_page_flags(1, base, [r1, r2])
    assert len(flags) == 1
    f = flags[0]
    assert f.base_text == "=="
    assert f.alternatives == ("!=",)
    assert f.n_readers == 2
    assert f.kind == "code"
    assert f.severity == "high"
    assert "hobbies[i]" in f.context_line


def test_single_reader_disagreement_is_medium_severity():
    base = "int count = 0;"
    flags = compute_page_flags(1, base, ["int count = 10;", "int count = 0;"])
    assert len(flags) == 1
    assert flags[0].n_readers == 1
    assert flags[0].severity == "medium"


def test_case_only_difference_is_not_flagged():
    # Identifier case is not graded (scorer Change C) -> case-only diff = noise.
    base = "CW(GetRate());"
    flags = compute_page_flags(1, base, ["cw(getrate());"])
    assert flags == []


def test_hebrew_comment_disagreement_is_info():
    base = "// סופר כמה פעמים\nint x = 0;"
    flags = compute_page_flags(1, base, ["// סופר כמה שעות\nint x = 0;"])
    assert len(flags) == 1
    assert flags[0].kind == "hebrew"
    assert flags[0].severity == "info"


def test_marker_only_disagreement_is_info():
    base = "שאלה 1\npublic class A"
    flags = compute_page_flags(1, base, ["א .\npublic class A"])
    assert len(flags) == 1
    assert flags[0].kind == "marker"
    assert flags[0].severity == "info"


def test_insertion_when_reader_sees_dropped_token():
    base = "int x = 1\nint y = 2;"          # baseline missed the ';' on line 1
    flags = compute_page_flags(1, base, ["int x = 1;\nint y = 2;"])
    assert len(flags) == 1
    assert flags[0].base_text == ""          # zero-width on baseline
    assert ";" in flags[0].alternatives[0]


def test_missing_reader_page_casts_no_votes():
    base_pages = {1: "int x = 1;", 2: "int y = 2;"}
    reader = {1: "int x = 1;"}  # reader lost page 2 entirely
    assert compute_flags(base_pages, [reader]) == []


def test_adjacent_spans_merge_into_one_review_stop():
    spans = [
        {"i1": 2, "i2": 3, "base": ["a"], "other": ["b"]},
        {"i1": 4, "i2": 5, "base": ["c"], "other": ["d"]},   # gap of 1 -> merge
        {"i1": 20, "i2": 21, "base": ["e"], "other": ["f"]},  # far -> separate
    ]
    merged = merge_adjacent(spans)
    assert len(merged) == 2
    assert (merged[0]["i1"], merged[0]["i2"]) == (2, 5)


def test_diff_spans_ranges_are_base_side():
    base = tokenize("a b c d")
    other = tokenize("a X c d")
    spans = diff_spans(base, other)
    assert spans == [{"i1": 1, "i2": 2, "base": ["b"], "other": ["X"]}]


# --- anchoring ----------------------------------------------------------------

def test_flags_anchor_into_the_answer_holding_their_line():
    base = "public bool Populate()\n{\nif(hobbies[i] == null)\n{\n}\n}"
    flags = compute_page_flags(2, base, [base.replace("==", "!=")])
    answers = {
        "q1.a": "public class Hobby\n{\n}",
        "q1.b": "public bool Populate()\n{\nif(hobbies[i] == null)\n{\n}\n}",
    }
    anchored = anchor_flags(flags, answers)
    assert anchored[0].anchor_key == "q1.b"
    assert anchored[0].anchor_similarity == 1.0


def test_unanchorable_flag_falls_back_to_page_level():
    flags = [FlagSpan(page=3, i1=0, i2=1, char_start=0, char_end=5,
                      base_text="שאלה 2", alternatives=("שאלה 3",),
                      n_readers=1, kind="marker", context_line="שאלה 2")]
    anchored = anchor_flags(flags, {"q1.a": "int x = 0;"})
    assert anchored[0].anchor_key is None


# --- lint ---------------------------------------------------------------------

def test_brace_lint_fires_only_on_imbalance():
    findings = brace_lint({
        "q1.a": "class A\n{\nint x;\n}",       # balanced
        "q1.b": "class B\n{\nvoid F()\n{\n}",  # missing one '}'
    })
    assert len(findings) == 1
    assert findings[0].answer_key == "q1.b"
    assert findings[0].balance == 1


# --- page provenance ------------------------------------------------------------

def test_align_answer_to_single_page():
    pages = {1: "public class Hobby\n{\nprivate string name;\n}",
             2: "public bool Populate()\n{\nreturn true;\n}"}
    att = align_answer_to_pages("public class Hobby\n{\nprivate string name;\n}",
                                pages)
    assert att.pages == [1]
    assert att.confidence > 0.95


def test_align_cross_page_answer_detects_both_pages():
    pages = {
        1: "public bool Populate()\n{\nint count = 0;\nfor(int i=0; i<n; i++)",
        2: "if(hobbies[i] == null)\n{\ncount++;\n}\nreturn count > 0;\n}",
        3: "public void Print()\n{\n}",
    }
    answer = ("public bool Populate()\n{\nint count = 0;\n"
              "for(int i=0; i<n; i++)\nif(hobbies[i] == null)\n{\ncount++;\n}\n"
              "return count > 0;\n}")
    att = align_answer_to_pages(answer, pages)
    assert set(att.pages) == {1, 2}


def test_align_is_robust_to_transcription_noise():
    pages = {1: "publik class Hoby\n{\nprivate string nme;\n}"}  # noisy page
    att = align_answer_to_pages("public class Hobby\n{\nprivate string name;\n}",
                                pages)
    assert att.pages == [1]


def test_norm_line_strips_whitespace_and_case():
    assert norm_line("  If (X ==  1) ") == "if(x==1)"


# --- R1: comment-content spans classify hebrew (info tier), not code ------------

def test_comment_drop_with_slashes_is_hebrew_kind():
    # baseline dropped an entire Hebrew comment: span = '' -> '/ / אם ספורטיבי'
    base = "countS++;\nint x = 1;"
    reader = "countS++;\n// אם ספורטיבי\nint x = 1;"
    flags = compute_page_flags(1, base, [reader])
    assert len(flags) == 1
    assert flags[0].kind == "hebrew"
    assert flags[0].severity == "info"


def test_hebrew_span_with_identifier_stays_code():
    # merged span carrying a real identifier misread (minn/min1) stays code
    base = "int minn = arr[0]; // ב"
    reader = "int min1 = arr[0]; // ג"
    flags = compute_page_flags(1, base, [reader])
    assert any(f.kind == "code" for f in flags)


def test_hebrew_span_with_strong_operator_stays_code():
    base = "// בדיקה\nif(x == y)"
    reader = "// בדיקה אם\nif(x != y)"
    flags = compute_page_flags(1, base, [reader])
    kinds = {f.base_text: f.kind for f in flags}
    assert kinds.get("==") == "code"
