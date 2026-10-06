"""grader-v6 explainer — the input and the user message (PR_grader_v6_options.md §7.3). Pure.

  test_explainer_payload_has_no_transcription_or_gt
  test_explainer_prefix_is_stable_across_students
  test_explainer_payload_ids_are_ascii_aliases
  test_explainer_skips_excluded_skipped_and_failed_scopes
  + the evidence rule, the charged-elsewhere / moved-by-pin pointers, teacher-decided
    terminals, and the recorded-payload round trip.
"""
from __future__ import annotations

import inspect
import json
import re
import typing
from decimal import Decimal

import pytest
from pydantic import BaseModel

from app.agents.explainer.fallback import compose_reasoning_he
from app.agents.explainer.payload import (ExplainerInputError, ScopeExplainerInput,
                                          build_scope_inputs, payload_from_dict, payload_to_dict)
from app.agents.explainer.prompt import STUDENT_SECTION_HEADER, render_scope_message
from app.agents.grader.payload_aliases import ALIAS_PATTERN
from app.agents.grader.plan_schemas import PartialFraction
from app.services.pricing_v6 import CheckDecision
from tests.agents.explainer_cases import XSel, make_content, materials, priced_of
from tests.services.pricing_v6_cases import binary, fault, ladder, note, overlay, term

D = Decimal
A0, A1, B0 = "q1.א.c0", "q1.א.c1", "q1.ב.c0"
TEXTS = {("q1", "א"): {A0: "עדכון התכונה value דרך SetValue (4 נק'). גישה ישירה — יורדו 2 נק'.",
                       A1: "סכימת איברי המערך בלולאה (2 נק')"},
         ("q1", "ב"): {B0: "הדפסת הסכום שחושב (3 נק')"}}
SOLUTION = "obj.SetValue(5);\nfor (int k = 0; k < n; k++)\n    sum += arr[k];"

# one student's whole answer; the verifier quoted only parts of it
ANSWER = ("obj.value = 5;\n"
          "for (int k = 0; k < n - 1; k++)\n"
          "    sum += arr[k];\n"
          "int secretLine = 42; // never quoted")


def _checks():
    c_upd = binary(f"{A0}.c1", A0, 4, desc="עדכון התכונה value",
                   full="התכונה value מעודכנת", absent="התכונה value אינה מעודכנת")
    f_dir = fault(f"{A0}.f1", A0, [("m1", 2, "העדכון בגישה ישירה במקום SetValue")],
                  requires=f"{A0}.c1", desc="גישה ישירה לתכונה")
    c_loop = ladder(f"{A1}.c1", A1, 2, [("הלולאה עוצרת איבר אחד לפני הסוף", PartialFraction.HALF)],
                    desc="סכימת איברי המערך")
    n_obs = note(f"{A1}.n1", A1, observed="שם המשתנה sum אינו מתאר את תפקידו")
    c_print = binary(f"{B0}.c1", B0, 3, desc="הדפסת הסכום")
    return c_upd, f_dir, c_loop, n_obs, c_print


def _student(kind: str):
    c_upd, f_dir, c_loop, n_obs, c_print = _checks()
    if kind == "dan":
        sels = [XSel(c_upd, "full", evidence="obj.value = 5;"),
                XSel(f_dir, "f1", evidence="obj.value = 5;"),
                XSel(c_loop, "p1", evidence="for (int k = 0; k < n - 1; k++)"),
                XSel(n_obs, "observed", evidence="sum += arr[k];"),
                XSel(c_print, "full", evidence="Console.WriteLine(sum);")]
    else:                                            # a different student, same rubric
        sels = [XSel(c_upd, "absent", quote=None, pointer="אין בתשובה עדכון של value"),
                XSel(f_dir, "none", quote=None),
                XSel(c_loop, "full", evidence="foreach (int x in arr) sum += x;"),
                XSel(n_obs, "none", quote=None),
                XSel(c_print, "absent", quote=None, pointer="הסכום מוחזר ולא מודפס")]
    terms = [term(A0, 4, sq="א"), term(A1, 2, sq="א"), term(B0, 3, sq="ב")]
    return make_content(terms, sels, notes={A1: ["לולאת foreach שקולה ללולאת for"]})


def _inputs(kind: str = "dan", ov=None):
    content = _student(kind)
    priced = priced_of(content, ov)
    return content, priced, build_scope_inputs(content, priced,
                                               materials(TEXTS, solution=SOLUTION))


# ── what never enters ─────────────────────────────────────────────────────────

_FORBIDDEN_FIELD = re.compile(r"transcri|ground|(^|_)gt($|_)|answer_text|student|"
                              r"check_id|option_id|plan_index|other_scope")


def _walk(model, seen=None):
    seen = set() if seen is None else seen
    if model in seen:
        return
    seen.add(model)
    for name, f in model.model_fields.items():
        yield model.__name__, name
        stack = [f.annotation]
        while stack:
            t = stack.pop()
            if isinstance(t, type) and issubclass(t, BaseModel):
                yield from _walk(t, seen)
            stack.extend(typing.get_args(t))


def test_explainer_payload_has_no_transcription_or_gt() -> None:
    # the TYPE has no field for student work, GT, another scope, a check or an option id
    fields = list(_walk(ScopeExplainerInput))
    assert {"evidence_quote", "absence_pointer_he", "teacher_text"} <= {n for _, n in fields}
    assert not [f for f in fields if _FORBIDDEN_FIELD.search(f[1])]
    # the builder takes no transcription: the priced draft and the rubric text only
    assert list(inspect.signature(build_scope_inputs).parameters) == ["content", "priced",
                                                                      "materials"]
    _content, _priced, inputs = _inputs()
    scope_a = next(i for i in inputs if i.sub_question_id == "א")
    message = render_scope_message(scope_a)
    blob = message + json.dumps(payload_to_dict(scope_a), ensure_ascii=False)
    assert "obj.value = 5;" in message                       # the verified quotes are there…
    assert "for (int k = 0; k < n - 1; k++)" in message
    assert "secretLine" not in blob and "42" not in blob     # …the rest of the answer is not
    assert TEXTS[("q1", "ב")][B0] not in blob                 # nor another scope's criterion
    assert "Console.WriteLine" not in blob                    # nor another scope's evidence


# ── the cached prefix ─────────────────────────────────────────────────────────

def test_explainer_prefix_is_stable_across_students() -> None:
    from app.agents.explainer.prompt import explainer_system_prompt
    from app.subjects import get_profile

    _c1, _p1, dan = _inputs("dan")
    _c2, _p2, noa = _inputs("noa")
    cs = get_profile("computer_science")
    assert explainer_system_prompt(cs) == explainer_system_prompt(cs)   # no per-call state
    for a, b in zip(dan, noa):
        ma, mb = render_scope_message(a), render_scope_message(b)
        head_a, tail_a = ma.split(STUDENT_SECTION_HEADER)
        head_b, tail_b = mb.split(STUDENT_SECTION_HEADER)
        assert head_a == head_b                     # question, solution, criteria, notes
        assert tail_a != tail_b                     # the students differ only after it
        for t in a.terminals:                       # everything per-batch sits in the head
            assert t.teacher_text in head_a and f"{t.alias} · points:" in head_a
        assert "לולאת foreach שקולה ללולאת for" in head_a or a.sub_question_id == "ב"


# ── AM-G17 ────────────────────────────────────────────────────────────────────

_ID_POSITION = re.compile(r"^--- (\S+) ·", re.M)


def test_explainer_payload_ids_are_ascii_aliases() -> None:
    content, _priced, inputs = _inputs()
    real_ids = {t.terminal_id for t in content.terminals} | {c.plan.check_id for c in content.checks}
    option_ids = {o.option_id for c in content.checks for o in c.plan.options}
    for inp in inputs:
        message = render_scope_message(inp)
        ids = _ID_POSITION.findall(message) + [
            a.strip() for a in re.search(r"Write one line for each of: (.*)\.$", message,
                                         re.M).group(1).split(",")]
        assert ids and all(ALIAS_PATTERN.match(i) for i in ids), ids
        assert not [r for r in real_ids if r in message]           # no q1.א.c0, no …c0.f1
        assert "q1" not in message and "א.c" not in message
        words = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", message))
        assert not (option_ids & words), option_ids & words        # full, absent, p1, f1, none…


def test_the_input_refuses_aliases_that_are_not_the_table() -> None:
    _c, _p, inputs = _inputs()
    d = payload_to_dict(inputs[0])
    d["terminals"][0]["alias"] = "t7"
    with pytest.raises(ValueError, match="AM-G17"):
        payload_from_dict(d)


# ── D-6: which scopes get a call ──────────────────────────────────────────────

def test_explainer_skips_excluded_skipped_and_failed_scopes() -> None:
    cs = [binary(f"q{i}.c0.c1", f"q{i}.c0", 2, desc=f"רכיב {i}") for i in range(1, 6)]
    terms = [term(f"q{i}.c0", 2, q=f"q{i}") for i in range(1, 6)]
    sels = [XSel(cs[0], "full", evidence="a"), XSel(cs[1], "absent", quote=None),
            XSel(cs[2], "absent", quote=None), XSel(cs[3], "absent", quote=None),
            XSel(cs[4], "full", evidence="b")]
    content = make_content(terms, sels, groups=[(["q4", "q5"], 1)],
                           graded_by={("q2", None): "skipped_no_answer", ("q3", None): "failed",
                                      ("q4", None): "excluded_by_selection"})
    priced = priced_of(content)
    assert {s.question_id: s.counted for s in priced.scopes}["q4"] is False
    texts = {(f"q{i}", None): {f"q{i}.c0": f"רכיב {i} (2 נק')"} for i in range(1, 6)}
    inputs = build_scope_inputs(content, priced, materials(texts))
    assert [i.question_id for i in inputs] == ["q1", "q5"]

    # an `llm` scope that does not count is excluded too (the PricedScope rule)
    content2 = make_content(terms, sels, groups=[(["q4", "q5"], 1)])
    inputs2 = build_scope_inputs(content2, priced_of(content2), materials(texts))
    assert [i.question_id for i in inputs2] == ["q1", "q2", "q3", "q5"]


# ── what the input says ──────────────────────────────────────────────────────

def test_the_input_carries_the_priced_selection() -> None:
    content, priced, inputs = _inputs("dan")
    a = next(i for i in inputs if i.sub_question_id == "א")
    t0, t1 = a.terminals
    assert (t0.alias, t0.terminal_id, t0.awarded, t0.points_possible) == ("t1", A0, D("2"), D("4"))
    (credit,) = t0.credit_checks
    assert (credit.selected_label_he, credit.selected_value, credit.evidence_quote) == \
        ("התכונה value מעודכנת", D("4"), "obj.value = 5;")
    (f,) = t0.fault_checks
    assert (f.selected_label_he, f.amount, f.charged, f.status) == \
        ("העדכון בגישה ישירה במקום SetValue", D("-2"), D("-2"), "applied")
    assert (t1.awarded, t1.credit_checks[0].selected_label_he) == \
        (D("1"), "הלולאה עוצרת איבר אחד לפני הסוף")
    assert t1.interpretation_notes_he == ("לולאת foreach שקולה ללולאת for",)
    assert a.observed_notes_he == ("שם המשתנה sum אינו מתאר את תפקידו",)
    assert a.example_solution == SOLUTION and a.question_text.startswith("שאלה")
    view = content.to_view()
    assert t0.fallback_he == compose_reasoning_he(priced, view, A0)       # recorded, not rendered
    assert t0.fallback_he not in render_scope_message(a)


def test_evidence_only_for_the_option_it_was_produced_for() -> None:
    """A gated pick (quote not verified) resolves to zero WITHOUT the claimed quote; a
    pick she replaced shows neither the model's quote nor its pointer."""
    c = binary("q1.c0.c1", "q1.c0", 2, desc="רכיב", full="קיים", absent="חסר")
    texts = {("q1", None): {"q1.c0": "רכיב (2 נק')"}}

    def credit_of(sel, ov=None):
        content = make_content([term("q1.c0", 2)], [sel])
        (inp,) = build_scope_inputs(content, priced_of(content, ov), materials(texts))
        return inp.terminals[0].credit_checks[0]

    gated = credit_of(XSel(c, "full", quote="not_found", evidence="המצאה"))
    assert (gated.selected_value, gated.selected_label_he, gated.evidence_quote) == (D("0"), "חסר", "")
    fuzzy = credit_of(XSel(c, "full", quote="fuzzy", evidence="קיים בערך"))
    assert fuzzy.evidence_quote == "קיים בערך"
    zero = credit_of(XSel(c, "absent", quote=None, pointer="יש משהו אחר"))
    assert (zero.absence_pointer_he, zero.evidence_quote) == ("יש משהו אחר", "")
    replaced = credit_of(XSel(c, "absent", quote=None, pointer="יש משהו אחר"),
                         overlay({"q1.c0.c1": CheckDecision(option_id="full")}))
    assert (replaced.selected_value, replaced.evidence_quote, replaced.absence_pointer_he) == \
        (D("2"), "", "")
    # the model's VERIFIED quote for «full» is not evidence for the partial she chose
    lad = ladder("q1.c0.c1", "q1.c0", 2, [("חלקי", PartialFraction.HALF)], desc="רכיב")
    lowered = credit_of(XSel(lad, "full", quote="exact", evidence="הקוד המלא"),
                        overlay({"q1.c0.c1": CheckDecision(option_id="p1")}))
    assert (lowered.selected_value, lowered.selected_label_he, lowered.evidence_quote) == \
        (D("1"), "חלקי", "")
    kept = credit_of(XSel(lad, "full", quote="exact", evidence="הקוד המלא"),
                     overlay({"q1.c0.c1": CheckDecision(option_id="full")}))
    assert kept.evidence_quote == "הקוד המלא"          # she confirmed the model's own pick


def test_superseded_and_moved_by_pin_carry_her_text_of_the_other_criterion() -> None:
    a, b = "q1.c0", "q1.c1"
    ca = binary(f"{a}.c1", a, 3, desc="רכיב א")
    cb = binary(f"{b}.c1", b, 3, desc="רכיב ב")
    fa = fault(f"{a}.f1", a, [("m1", 1, "חסר public")], group="g", desc="הרשאת גישה")
    fb = fault(f"{b}.f1", b, [("m2", 1, "חסר public")], group="g", desc="הרשאת גישה")
    sels = [XSel(ca, "full", evidence="x"), XSel(fa, "f1", evidence="x"),
            XSel(cb, "full", evidence="y"), XSel(fb, "f1", evidence="y")]
    texts = {("q1", None): {a: "הגדרת המחלקה (3 נק')", b: "הגדרת הבנאי (3 נק')"}}
    content = make_content([term(a, 3), term(b, 3)], sels)

    (inp,) = build_scope_inputs(content, priced_of(content), materials(texts))
    statuses = {t.terminal_id: t.fault_checks[0] for t in inp.terminals}
    assert statuses[a].status == "applied" and statuses[a].charged_elsewhere_he is None
    assert statuses[b].status == "superseded"
    assert statuses[b].charged_elsewhere_he == "הגדרת המחלקה (3 נק')"

    # she pins a's grade: the charge moves to b, and b's row names the criterion she pinned
    priced = priced_of(content, overlay(pins={a: 3}))
    (inp,) = build_scope_inputs(content, priced, materials(texts))
    assert [t.terminal_id for t in inp.terminals] == [b]       # a is hers: not explained
    moved = inp.terminals[0].fault_checks[0]
    assert (moved.status, moved.moved_by_pin, moved.pinned_criterion_he) == \
        ("applied", True, "הגדרת המחלקה (3 נק')")
    assert "moved here" in render_scope_message(inp)


def test_teacher_decided_terminals_are_not_in_the_input() -> None:
    _c, _p, inputs = _inputs("dan", overlay({f"{A1}.c1": CheckDecision(amount=D("1.5"))}))
    a = next(i for i in inputs if i.sub_question_id == "א")
    assert [t.terminal_id for t in a.terminals] == [A0]           # A1's amount was typed
    _c, _p, inputs = _inputs("dan", overlay(pins={B0: 1}))
    assert [i.sub_question_id for i in inputs] == ["א"]            # scope ב: nothing to explain


def test_missing_materials_are_an_input_error() -> None:
    content = _student("dan")
    priced = priced_of(content)
    with pytest.raises(ExplainerInputError):
        build_scope_inputs(content, priced, materials({("q1", "א"): TEXTS[("q1", "א")]}))
    broken = {("q1", "א"): {A0: TEXTS[("q1", "א")][A0]}, ("q1", "ב"): TEXTS[("q1", "ב")]}
    with pytest.raises(ExplainerInputError, match=A1):
        build_scope_inputs(content, priced, materials(broken))


def test_recorded_payload_round_trips_as_json() -> None:
    _c, _p, inputs = _inputs("dan")
    for inp in inputs:
        d = json.loads(json.dumps(payload_to_dict(inp), ensure_ascii=False))
        back = payload_from_dict(d)
        assert back == inp and render_scope_message(back) == render_scope_message(inp)
        assert d["payload_schema"] == "explainer-payload/v1"
