"""The §3.3 relocation function — pure, so every rule is a zero-mock test.

A false relocation silently reorders what the grader reads; a missed one is
visible on the scan. So the REJECTION tests matter as much as the happy paths:
each one pins a way this function refuses to guess.
"""
from app.services.transcription.two_phase.relocation import (
    ATTACHMENT, INSERTION, Instruction, find_all, log_line, relocate,
)


def ins(id="c#01", page=1, tpage=None, **kw):
    return Instruction(id=id, kind=INSERTION, source_page=page,
                       target_page=tpage or page, **kw)


def att(id="c#02", page=1, tpage=None, **kw):
    return Instruction(id=id, kind=ATTACHMENT, source_page=page,
                       target_page=tpage or page, **kw)


# --- the happy paths ---------------------------------------------------------------

def test_insertion_between_lines_lands_as_its_own_lines():
    page = ("int y = 1;\n"
            "public void F()\n{\nreturn;\n}")
    r = relocate({1: page}, [ins(source_text="int y = 1;",
                                 after="{\n", before="return;")])
    assert not r.rejected
    assert r.pages[1] == "public void F()\n{\nint y = 1;\nreturn;\n}"
    assert r.applied[0].text == "int y = 1;"


def test_mid_line_insertion_on_the_same_line_as_its_source():
    """yonatan #01's shape: the fragment sits at the start of the if-line and
    belongs inside its condition. Same line is legal; overlap is not."""
    page = "|| x == 2 if (a == 1)\nreturn;"
    r = relocate({1: page}, [ins(source_text="|| x == 2",
                                 after="if (a == 1", before=")\nreturn;")])
    assert not r.rejected, r.rejected
    assert "".join(r.pages[1].split()) == "if(a==1||x==2)return;"


def test_attachment_hangs_at_the_line_end_with_internal_breaks_collapsed():
    page = ("string[] names = new string[count];\n"
            "for (int i = 0; i < n; i++)\n"
            "assuming the counter\narray is zeroed")
    r = relocate({1: page}, [att(source_text="assuming the counter\narray is zeroed",
                                 line="string[] names = new string[count];")])
    assert not r.rejected
    assert r.pages[1] == ("string[] names = new string[count]; "
                          "⟦assuming the counter array is zeroed⟧\n"
                          "for (int i = 0; i < n; i++)")
    assert r.applied[0].text == "assuming the counter array is zeroed"


def test_cross_page_insertion_uses_the_document_page_list():
    pages = {1: "{\nreturn x;\n}", 2: "int x = 5;\nother"}
    r = relocate(pages, [ins(page=2, tpage=1, source_text="int x = 5;",
                             after="{", before="return x;")])
    assert not r.rejected
    assert r.pages[1] == "{\nint x = 5;\nreturn x;\n}"
    assert r.pages[2] == "other"


def test_matching_is_blind_to_whitespace_and_nothing_else():
    """The owner's cases are authored as `int mechinaNum=0;` against raw
    `int mechinaNum = 0;` — the same equality the scorer applies."""
    page = "int  mechinaNum = 0;\n{\nint [] copy = new int[3];"
    r = relocate({1: page}, [ins(source_text="int mechinaNum=0;",
                                 after="{\n", before="int[] copy = new int[3];")])
    assert not r.rejected
    assert r.pages[1].startswith("{\nint  mechinaNum = 0;\nint [] copy")


def test_answer_start_and_answer_end_anchors():
    r = relocate({1: "A\nB\nMOVE"}, [ins(source_text="MOVE", after="", before="A")])
    assert r.pages[1] == "MOVE\nA\nB"
    r = relocate({1: "MOVE\nA\nB"}, [ins(source_text="MOVE", after="B", before="")])
    assert r.pages[1] == "A\nB\nMOVE"


def test_first_last_words_form_resolves_the_span_between_them():
    page = "keep\nint a = 1;\nint b = 2;\nint c = 3;\n{\nbody;"
    r = relocate({1: page}, [ins(source_first="int a", source_last="c = 3;",
                                 after="{", before="body;")])
    assert not r.rejected
    assert r.pages[1] == "keep\n{\nint a = 1;\nint b = 2;\nint c = 3;\nbody;"


def test_several_cases_on_one_page_keep_their_step1_offsets():
    page = "X1\nX2\nA\nB\nC"
    r = relocate({1: page}, [
        ins(id="c#01", source_text="X1", after="A", before="B"),
        ins(id="c#02", source_text="X2", after="B", before="C"),
    ])
    assert not r.rejected
    assert r.pages[1] == "A\nX1\nB\nX2\nC"


# --- the refusals (each is a guess this function will not make) ---------------------

def test_ambiguous_target_is_rejected_and_the_page_is_untouched():
    page = "{\nreturn;\n}\n{\nreturn;\n}\nMOVE"
    r = relocate({1: page}, [ins(source_text="MOVE", after="{", before="return;")])
    assert r.pages[1] == page
    assert not r.applied
    assert "2 times" in r.rejected[0].reason


def test_ambiguous_source_is_rejected():
    r = relocate({1: "a;\na;\n{\nb"}, [ins(source_text="a;", after="{", before="b")])
    assert r.rejected and not r.applied


def test_missing_source_is_rejected():
    r = relocate({1: "{\nb"}, [ins(source_text="nowhere", after="{", before="b")])
    assert "not found" in r.rejected[0].reason


def test_no_edit_distance_fuzz_ever():
    """One character off is a DIFFERENT text. A near-match relocation is the
    false relocation this module exists to never produce."""
    page = "int max = int.minValue;\n{\nbody;"
    r = relocate({1: page}, [ins(source_text="int max = int.minValou;",
                                 after="{", before="body;")])
    assert r.pages[1] == page and r.rejected


def test_source_overlapping_target_is_rejected():
    page = "{\nMOVE body;"
    r = relocate({1: page}, [ins(source_text="MOVE body", after="{", before="MOVE body;")])
    assert r.rejected and r.pages[1] == page


def test_text_already_in_place_is_rejected_not_duplicated():
    """itay_kraft #01's current GT: the source already sits between its anchors,
    so `after+before` is not contiguous and nothing moves."""
    page = "{\nint mechinaNum = 0;\nint[] copy;"
    r = relocate({1: page}, [ins(source_text="int mechinaNum=0;",
                                 after="{\n", before="int[] copy;")])
    assert r.rejected and r.pages[1] == page


def test_one_source_cutting_another_cases_anchor_rejects_both():
    """c#02's source IS c#01's `before` anchor: moving it would pull c#01's
    context out from under it, so neither moves."""
    page = "X1\nA\nB\n{\nC"
    r = relocate({1: page}, [
        ins(id="c#01", source_text="X1", after="A", before="B"),
        ins(id="c#02", source_text="B", after="{", before="C"),
    ])
    assert {x.id for x in r.rejected} == {"c#01", "c#02"}
    assert r.pages[1] == page


def test_two_insertions_at_the_same_point_reject_both():
    page = "X1\nX2\nA\nB"
    r = relocate({1: page}, [
        ins(id="c#01", source_text="X1", after="A", before="B"),
        ins(id="c#02", source_text="X2", after="A", before="B"),
    ])
    assert {x.id for x in r.rejected} == {"c#01", "c#02"}


def test_two_overlapping_cases_are_BOTH_rejected():
    page = "SRC\nA\nB"
    r = relocate({1: page}, [
        ins(id="c#01", source_text="SRC", after="A", before="B"),
        ins(id="c#02", source_text="SRC", after="A", before="B"),
    ])
    assert {x.id for x in r.rejected} == {"c#01", "c#02"}
    assert r.pages[1] == page


def test_attachment_needs_a_complete_line():
    """itay_katav #01's current GT: the target text shares its line with the
    inline note, so it is not a complete line and nothing is attached."""
    page = "* string[] names = new string[count]; // note\nx"
    r = relocate({1: page}, [att(source_text="note",
                                 line="* string[] names = new string[count];")])
    assert r.rejected and r.pages[1] == page


def test_ambiguous_first_words_is_rejected():
    page = "int a = 1;\nint a = 2;\n{\nb"
    r = relocate({1: page}, [ins(source_first="int a", source_last="2;",
                                 after="{", before="b")])
    assert r.rejected


def test_unknown_page_or_kind_is_rejected():
    assert relocate({1: "x"}, [ins(tpage=9, source_text="x", after="x", before="")]).rejected
    bad = Instruction(id="c#9", kind="decoy", source_page=1, target_page=1)
    assert relocate({1: "x"}, [bad]).rejected


# --- purity + the operational line ---------------------------------------------------

def test_input_pages_are_never_mutated():
    pages = {1: "SRC\nA\nB"}
    relocate(pages, [ins(source_text="SRC", after="A", before="B")])
    assert pages == {1: "SRC\nA\nB"}


def test_find_all_returns_original_offsets():
    text = "a  b\nc"
    [(s, e)] = find_all(text, "ab c")
    assert text[s:e] == "a  b\nc"


def test_log_line_carries_everything_in_the_message():
    r = relocate({1: "SRC\nA\nB"}, [ins(source_text="SRC", after="A", before="B"),
                                   ins(id="c#9", source_text="zzz", after="A", before="")])
    line = log_line("doc1", r)
    assert "doc=doc1 applied=1 rejected=1" in line
    assert "insertion:p1@" in line and "not found" in line
