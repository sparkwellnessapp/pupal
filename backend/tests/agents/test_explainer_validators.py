"""grader-v6 explainer — E-1..E-5 (PR_grader_v6_options.md §7.5). Pure, zero mocks.

  test_e1_coverage_drops_unknown_and_duplicates
  test_e2_length_bounds
  test_e3_forbidden_vocabulary_and_rule_ids
  test_e4_numbers_subset_of_payload
  test_e5_voice_markers
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.agents.explainer.copy import MACHINE_VOCABULARY, MAX_LINE, VOICE_MARKERS
from app.agents.explainer.payload import (CreditCheckInput, FaultCheckInput, ScopeExplainerInput,
                                          TerminalExplainerInput)
from app.agents.explainer.validators import (allowed_numbers, e2_length_ok, e3_vocabulary_ok,
                                             e4_numbers_ok, e5_voice_ok, normalize_line,
                                             numbers_in, validate_line, validate_scope)

D = Decimal


def _terminal(alias: str, tid: str, *, text: str = "עדכון התכונה דרך המתודה (4 נק')",
              awarded: str = "2", points: str = "4", quote: str = "SetValue(v + 1);",
              pointer: str = "", faults=()) -> TerminalExplainerInput:
    return TerminalExplainerInput(
        alias=alias, terminal_id=tid, teacher_text=text, points_possible=D(points),
        awarded=D(awarded),
        credit_checks=(CreditCheckInput(description_he="עדכון התכונה",
                                        selected_label_he="התכונה מעודכנת",
                                        selected_value=D("4"), evidence_quote=quote,
                                        absence_pointer_he=pointer),),
        fault_checks=tuple(faults), fallback_he="חסר: עדכון התכונה")


def _scope(*terminals, question: str = "כתבו פעולה שמעדכנת ערך", solution: str = "") -> ScopeExplainerInput:
    return ScopeExplainerInput(question_id="q1", sub_question_id="א", question_text=question,
                               example_solution=solution, terminals=tuple(terminals))


# ── E-1 ─────────────────────────────────────────────────────────────────────

def test_e1_coverage_drops_unknown_and_duplicates() -> None:
    inp = _scope(_terminal("t1", "q1.א.c0"), _terminal("t2", "q1.א.c1"))
    out = validate_scope([("t1", "התכונה עודכנה דרך SetValue, כנדרש."),
                          ("t9", "שורה לקריטריון שלא קיים"),          # an alias never issued
                          ("q1.א.c1", "שורה עם מזהה אמיתי"),          # a real id is not an alias
                          ("t1", "שורה שנייה לאותו קריטריון")],        # a duplicate: first wins
                         inp)
    v1, v2 = out.verdicts["q1.א.c0"], out.verdicts["q1.א.c1"]
    assert (v1.text_he, v1.failed_rules) == ("התכונה עודכנה דרך SetValue, כנדרש.", ())
    assert (v2.text_he, v2.failed_rules) == (None, ("E-1",))      # t2 got no line of its own
    tel = "\n".join(out.telemetry)
    assert "alias_dropped" in tel and "t9" in tel and "q1.א.c1" in tel   # telemetry names them
    assert "duplicate_line t1" in tel
    assert set(out.verdicts) == {"q1.א.c0", "q1.א.c1"}          # every terminal has a verdict


def test_e1_unknown_alias_drop_goes_through_the_closed_world_function(monkeypatch) -> None:
    """[AM-G17] the drop IS `strip_out_of_world`, called with no `rekey` (no CWV-6)."""
    import app.agents.explainer.validators as validators

    seen = {}
    real = validators.strip_out_of_world

    def spy(items, **kw):
        seen.update(kw)
        return real(items, **kw)

    monkeypatch.setattr(validators, "strip_out_of_world", spy)
    validate_scope([("t1", "שורה")], _scope(_terminal("t1", "q1.c0")))
    assert seen.get("rekey") is None and set(seen["known"]) == {"t1"}


# ── E-2 ─────────────────────────────────────────────────────────────────────

def test_e2_length_bounds() -> None:
    assert not e2_length_ok("")
    assert not e2_length_ok(normalize_line("   \n  "))
    assert e2_length_ok("א")
    assert e2_length_ok("א" * MAX_LINE)
    assert not e2_length_ok("א" * (MAX_LINE + 1))
    # trimmed and collapsed BEFORE counting: padding never fails a line, nor rescues one
    assert normalize_line("  שורה \n עם   רווחים  ") == "שורה עם רווחים"
    assert e2_length_ok(normalize_line("  " + "א" * MAX_LINE + "  "))
    inp = _scope(_terminal("t1", "q1.c0"))
    assert validate_line("א" * 201, inp, inp.terminals[0]) == ["E-2"]


# ── E-3 ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("term", MACHINE_VOCABULARY)
def test_e3_every_machine_term_is_refused(term: str) -> None:
    assert not e3_vocabulary_ok(f"הציון נקבע לפי ה{term} שנבחרה" if not term.isascii()
                                else f"the {term} decided it")


def test_e3_forbidden_vocabulary_and_rule_ids() -> None:
    for line in ("לפי PL-10 טעות בשם אינה נענשת", "ראו PB3", "כלל V-2 חל כאן", "E4 נכשל",
                 "בהתאם ל-INV-2", "לפי CW-3", "OD-12 קובע", "PRC-6", "X-11", "P-1",
                 "בPL-10 נקבע",                       # a Hebrew prefix glued to the id
                 "The CHECK failed", "two options", "שאלו את Vivi",
                 "הצ׳ק נכשל",                          # geresh U+05F3 for the apostrophe
                 "לפי המודלים"):                      # an inflected form still contains it
        assert not e3_vocabulary_ok(line), line
    for line in ("הלולאה עוצרת איבר אחד לפני הסוף.", "המשתנה P1x מוגדר", "checkbox נוסף לטופס",
                 "הפעולה IsCheckedOut מחזירה true"):
        assert e3_vocabulary_ok(line), line


def test_e3_subject_matter_is_not_machine_vocabulary() -> None:
    """A token that is the SUBJECT — in her text, the question, the solution or a quote —
    is not the machinery: a point P1, a velocity V2, a method Check, an essay about AI."""
    assert not e3_vocabulary_ok("הנקודה P1 חושבה נכון")
    assert e3_vocabulary_ok("הנקודה P1 חושבה נכון", "P1 = (2, 3)")
    assert e3_vocabulary_ok("המתודה Check מחזירה true", "public bool Check(int x)")
    assert not e3_vocabulary_ok("המתודה Check מחזירה true", "public bool Verify(int x)")
    assert e3_vocabulary_ok("החיבור על בינה מלאכותית עוסק בנושא", "כתבו חיבור על בינה מלאכותית")
    # the exemption is per token: P1 in the quote does not excuse a rule id beside it
    assert not e3_vocabulary_ok("הנקודה P1 נכונה לפי PL-9", "P1 = (2, 3)")


# ── E-4 ─────────────────────────────────────────────────────────────────────

def test_e4_numbers_subset_of_payload() -> None:
    t = _terminal("t1", "q1.c0", text="עדכון הערך ב-1 (4 נק'). גישה ישירה — יורדו 2 נק'.",
                  awarded="1.5", points="4", quote="SetValue(v + 7);",
                  pointer="הערך מעודכן ב-99",
                  faults=[FaultCheckInput(description_he="גישה ישירה",
                                          selected_label_he="העדכון בגישה ישירה",
                                          amount=D("-2.5"), charged=D("-2.5"), status="applied")])
    inp = _scope(t, question="עדכנו את הערך עד 40", solution="v = v + 1;")
    allowed = allowed_numbers(inp, t)
    for line in ("הציון 1.5 מתוך 4", "ירדו 2.5 נקודות", "ירדו 2.50 נקודות",   # 2.5 == 2.50
                 "הערך עולה ב-7", "עד 40", "ב-1", "ירדו −2.5"):              # sign ignored
        assert e4_numbers_ok(line, allowed), line
    for line in ("ירדו 3 נקודות",                       # invented
                 "הערך מעודכן ב-99",                   # only in the verifier's absence pointer
                 "הציון 1.4"):
        assert not e4_numbers_ok(line, allowed), line
    assert validate_line("ירדו 3 נקודות", inp, t) == ["E-4"]


def test_e4_number_parsing() -> None:
    assert numbers_in("1.50 ו-½ ו-2,5 ו-x2 ו-007") == [D("1.5"), D("0.5"), D("2.5"), D("2"), D("7")]
    assert e4_numbers_ok("ירדה ½ נקודה", [D("0.50")])
    assert e4_numbers_ok("אין מספרים כאן", [])
    # a count label is plan data: «5 מתוך 8 נכונים» may be echoed
    t = TerminalExplainerInput(
        alias="t1", terminal_id="q1.c0", teacher_text="מילוי הטבלה (3 נק')",
        points_possible=D("3"), awarded=D("2"),
        credit_checks=(CreditCheckInput(description_he="תאים", selected_label_he="5 מתוך 8 נכונים",
                                        selected_value=D("2")),),
        fallback_he="תאים: 5 מתוך 8 נכונים")
    assert e4_numbers_ok("5 מתוך 8 תאים נכונים", allowed_numbers(_scope(t), t))


# ── E-5 ─────────────────────────────────────────────────────────────────────

def test_e5_voice_markers() -> None:
    for marker in VOICE_MARKERS:
        assert not e5_voice_ok(f"לדעת {marker} הכול תקין"), marker
    # proclitics: «ו ה ש ב כ ל מ», up to three
    for line in ("ואני רואה שהלולאה נכונה", "כפי שבדקתי", "ושמצאתי בה טעות", "התשובה משלי",
                 "לתלמיד חסרה ההחזרה",                # the article absorbed after ל
                 "בתלמידה", "וכשהתלמיד כתב", "אֲנִי"):    # niqqud stripped
        assert not e5_voice_ok(line), line
    # never inside a longer word, never a different word
    for line in ("הפעולה השלישית מחזירה ערך", "התשובה משלימה את החסר", "מאניה היא שם",
                 "התלמידים", "הספירה נכונה"):
        assert e5_voice_ok(line), line
