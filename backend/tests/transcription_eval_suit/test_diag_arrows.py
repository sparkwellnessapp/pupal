"""Self-tests for the arrow diagnostic. GT cases applied to GT pages must place
100% with zero false relocations; the known failure shapes must score exactly."""
from app.services.transcription.two_phase.relocation import Instruction, relocate

from .diag_arrows import score_arrows

PAGE = "if (n == 1)\nreturn;\n|| m == 2\nint y = 0;\n{\nbody;\n}"
CASES = [
    {"id": "f#01", "fixture": "f", "kind": "insertion", "marker": "arrow",
     "source": {"page": 1, "text": "|| m == 2"},
     "target": {"page": 1, "after": "if (n == 1", "before": ")\nreturn;"}},
    {"id": "f#02", "fixture": "f", "kind": "attachment", "marker": "arrow",
     "source": {"page": 1, "text": "int y = 0;"},
     "target": {"page": 1, "line": "body;"}},
    {"id": "f#03", "fixture": "f", "kind": "decoy", "marker": "arrow",
     "page": 1, "near": "{\nbody;"},
]


def _inst(c):
    s, t = c["source"], c["target"]
    return Instruction(id=c["id"], kind=c["kind"], source_page=s["page"],
                       target_page=t["page"], source_text=s["text"],
                       after=t.get("after"), before=t.get("before"), line=t.get("line"))


def test_gold_cases_on_gold_pages_place_everything():
    live = [c for c in CASES if c["kind"] != "decoy"]
    res = relocate({1: PAGE}, [_inst(c) for c in live])
    assert not res.rejected
    s = score_arrows(CASES, list(res.applied), {1: PAGE})
    assert (s["cases"], s["placed"], s["missed"], s["false_relocations"]) == (2, 2, 0, 0)
    assert s["placement_rate"] == 1.0


def test_no_relocation_at_all_misses_every_case():
    s = score_arrows(CASES, [], {1: PAGE})
    assert (s["placed"], s["missed"], s["false_relocations"]) == (0, 2, 0)


def test_a_relocation_matching_no_case_is_false_and_names_its_decoy():
    """An INSERTION of text the owner recorded as an ATTACHMENT, landing right
    at the decoy mark: it corresponds to no case, and it names the decoy."""
    rogue = Instruction(id="p#1", kind="insertion", source_page=1, target_page=1,
                        source_text="int y = 0;", after="{", before="body;")
    res = relocate({1: PAGE}, [rogue])
    assert res.applied
    s = score_arrows(CASES, list(res.applied), {1: PAGE})
    assert s["false_relocations"] == 1 and s["false_on_decoy"] == 1
    assert s["false"][0]["decoy"] == "f#03"


def test_right_text_wrong_place_is_misplaced_not_placed():
    wrong = Instruction(id="p#1", kind="insertion", source_page=1, target_page=1,
                        source_text="|| m == 2", after="{", before="body;")
    res = relocate({1: PAGE}, [wrong])
    s = score_arrows(CASES, list(res.applied), {1: PAGE})
    assert (s["placed"], s["misplaced"], s["false_relocations"]) == (0, 1, 0)


def test_a_misread_moved_text_still_corresponds_to_its_case():
    """The model's reading of the moved ink differs from the GT by a misread
    letter: that is perception, and placement must still be credited.
    (Realistic length: yonatan #01's fragment is ~30 characters.)"""
    gold = '|| (answer=="n") || (answer==\'N\')'
    misread = '|| (answer=="n") || (anwer==\'N\')'
    page = "if (n == 1)\nreturn;\n" + misread + "\n{\nbody;\n}"
    cases = [{"id": "f#01", "kind": "insertion", "source": {"page": 1, "text": gold},
              "target": {"page": 1, "after": "if (n == 1", "before": ")\nreturn;"}}]
    inst = Instruction(id="p#1", kind="insertion", source_page=1, target_page=1,
                       source_text=misread, after="if (n == 1", before=")\nreturn;")
    res = relocate({1: page}, [inst])
    s = score_arrows(cases, list(res.applied), {1: page})
    assert s["placed"] == 1 and s["false_relocations"] == 0


def test_a_different_short_fragment_does_not_correspond():
    """The other side of the tolerance: a genuinely different short piece of ink
    is NOT credited to the case."""
    s_gold = {"id": "f#01", "kind": "insertion", "source": {"page": 1, "text": "|| m == 2"},
              "target": {"page": 1, "after": "if (n == 1", "before": ")\nreturn;"}}
    page = "if (n == 1)\nreturn;\n&& q > 7\n{\nbody;\n}"
    inst = Instruction(id="p#1", kind="insertion", source_page=1, target_page=1,
                       source_text="&& q > 7", after="if (n == 1", before=")\nreturn;")
    res = relocate({1: page}, [inst])
    s = score_arrows([s_gold], list(res.applied), {1: page})
    assert s["placed"] == 0 and s["false_relocations"] == 1
