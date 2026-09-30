"""grader-v6 planner input + prompt (PR_grader_v6_options.md §5.2, §5.4). Pure: no DB, no provider.

  test_planner_payload_has_no_amounts_and_no_student_work
  test_few_shot_outputs_validate_and_use_only_their_own_ids
  + the masking rule, the input guards, and the prompt's shape.
"""
from __future__ import annotations

import dataclasses
import re
import typing
from decimal import Decimal

import pytest

from app.agents.grader.plan_schemas import DeductionMarker
from app.agents.planner.examples import FEW_SHOTS
from app.agents.planner.inputs import (AMOUNT_MASK, SPLIT_REFS, MarkerInput, NoteInput,
                                       PlannerInputError, ScopePlannerInput, SkeletonComponent,
                                       TerminalInput, mask_amount, mask_marker_amounts,
                                       marker_input)
from app.agents.planner.prompt import (PLANNER_PROMPT_VERSION, planner_system_prompt,
                                       render_scope_input)
from app.agents.planner.schemas import ScopePlanOutput
from app.subjects import get_profile, subject_keys

_NUMBER = re.compile(r"\d+(?:[.,]\d+)?|[.,]\d+|½")


def _numbers(text: str) -> set:
    return {Decimal("0.5") if t == "½" else Decimal(t.replace(",", "."))
            for t in _NUMBER.findall(text)}


# ── a synthetic scope whose teacher text states the amounts ──────────────────
_TEXT_1 = ("חישוב מהירות הרכב בקמ\"ש (7 נק'). שימוש בזמן בדקות במקום בשעות — יורדו 1.5 נק'. "
           "תוצאה ללא יחידות: -0.75.")
_TEXT_2 = "הסבר קצר של הקשר בין מהירות לדרך (4 נק'). על הסבר מעגלי להוריד ½ נקודה."
_MARKERS = (
    DeductionMarker(marker_id="m1", home_terminal_id="t1", amount=Decimal("1.5"),
                    polarity="deduct", text_span="שימוש בזמן בדקות במקום בשעות — יורדו 1.5 נק'",
                    candidate_anchors=["t1"]),
    DeductionMarker(marker_id="m2", home_terminal_id="t1", amount=Decimal("0.75"),
                    polarity="deduct", text_span="תוצאה ללא יחידות: -0.75",
                    candidate_anchors=["t1"]),
    DeductionMarker(marker_id="m3", home_terminal_id="t2", amount=Decimal("0.5"),
                    polarity="deduct", text_span="על הסבר מעגלי להוריד ½ נקודה",
                    candidate_anchors=["t2", "t1"]),
)


def _synthetic_scope() -> ScopePlannerInput:
    return ScopePlannerInput(
        scope_id="q9",
        question_text="רכב נסע 180 ק\"מ ב-3 שעות. חשבו את מהירותו והסבירו.",
        example_solution="v = 180 / 3 = 60 קמ\"ש",
        terminals=(
            TerminalInput("t1", Decimal("7"), mask_marker_amounts(_TEXT_1, _MARKERS),
                          components=(SkeletonComponent("k1", "חישוב מהירות הרכב בקמ\"ש",
                                                        "monolith"),)),
            TerminalInput("t2", Decimal("4"), mask_marker_amounts(_TEXT_2, _MARKERS),
                          components=(SkeletonComponent("k2", "הסבר קצר של הקשר בין מהירות לדרך",
                                                        "fixed"),)),
        ),
        notes=(NoteInput("t2", "ניסוח לא מדויק — לא להוריד, לכתוב הערה"),),
        markers=tuple(marker_input(m) for m in _MARKERS),
    )


_FORBIDDEN_FIELD = re.compile(
    r"amount|value|student|answer|transcri|ground|(^|_)gt($|_)|award|verdict|grade|score|evidence")


def _walk_fields(cls, seen=None):
    """Every (owner, field name) reachable from a dataclass, through Tuple/Optional."""
    seen = set() if seen is None else seen
    if cls in seen or not dataclasses.is_dataclass(cls):
        return
    seen.add(cls)
    hints = typing.get_type_hints(cls)
    for f in dataclasses.fields(cls):
        yield cls.__name__, f.name
        stack = [hints[f.name]]
        while stack:
            t = stack.pop()
            if dataclasses.is_dataclass(t):
                yield from _walk_fields(t, seen)
            stack.extend(typing.get_args(t))


def test_planner_payload_has_no_amounts_and_no_student_work() -> None:
    # the input TYPES have no field for an amount, student work, GT or another scope
    fields = list(_walk_fields(ScopePlannerInput))
    names = {n for _, n in fields}
    assert {"markers", "candidate_anchors", "teacher_text", "components"} <= names
    offenders = [(o, n) for o, n in fields if _FORBIDDEN_FIELD.search(n)]
    assert not offenders, offenders
    assert "amount" not in {f.name for f in dataclasses.fields(MarkerInput)}

    # the source states every amount; the rendered message states none of them
    amounts = {abs(m.amount) for m in _MARKERS}
    assert amounts <= _numbers(_TEXT_1 + _TEXT_2)                     # not vacuous
    user = render_scope_input(_synthetic_scope())
    assert not (_numbers(user) & amounts), sorted(_numbers(user) & amounts)
    assert user.count(AMOUNT_MASK) >= 2 * len(_MARKERS)                 # in her text AND in each span
    # her points and the task's own figures survive the mask
    assert {Decimal("7"), Decimal("4"), Decimal("180"), Decimal("60")} <= _numbers(user)
    assert "ניסוח לא מדויק — לא להוריד, לכתוב הערה" in user            # notes: read-only context


def test_mask_amount_masks_only_the_amount() -> None:
    assert mask_amount("יורדו 2 נק'", Decimal("2")) == f"יורדו {AMOUNT_MASK} נק'"
    assert mask_amount("(−2) ו-(-2)", Decimal("2")) == f"({AMOUNT_MASK}) ו-({AMOUNT_MASK})"
    assert mask_amount("12 ו-2.5 ו-20", Decimal("2")) == "12 ו-2.5 ו-20"   # digit boundaries
    assert mask_amount("להוריד ½", Decimal("0.5")) == f"להוריד {AMOUNT_MASK}"
    assert mask_amount("להוריד .5 או 0,5", Decimal("0.5")) == f"להוריד {AMOUNT_MASK} או {AMOUNT_MASK}"
    assert mask_amount("לא מורידים 2", None) == "לא מורידים 2"
    # outside a marker's span her figures stay: «(2 נק')» is points, not the amount
    m = DeductionMarker(marker_id="m", home_terminal_id="t", amount=Decimal("2"), polarity="deduct",
                        text_span="גישה ישירה — 2", candidate_anchors=["t"])
    assert mask_marker_amounts("עדכון (2 נק'). גישה ישירה — 2", [m]) == \
        f"עדכון (2 נק'). גישה ישירה — {AMOUNT_MASK}"


def test_input_guards_keep_the_closed_world() -> None:
    comp = (SkeletonComponent("k1", "x", "monolith"),)
    t1 = TerminalInput("t1", Decimal("2"), "x", components=comp)
    with pytest.raises(PlannerInputError):          # V18's precondition
        ScopePlannerInput("s", "q", None, (t1,),
                          markers=(MarkerInput("m1", "x", "deduct", "t1", ("t1", "t9")),))
    with pytest.raises(PlannerInputError):
        TerminalInput("t2", Decimal("2"), "x")                        # neither skeleton nor shape
    with pytest.raises(PlannerInputError):
        TerminalInput("t3", Decimal("2"), "x", components=(
            SkeletonComponent("k2", "x", "monolith"), SkeletonComponent("k3", "y", "fixed")))
    with pytest.raises(PlannerInputError):
        ScopePlannerInput("s", "q", None, (t1, t1))
    assert t1.component_refs == ("k1",) + SPLIT_REFS


def test_the_input_refuses_a_real_id() -> None:
    """[AM-G17] the model reads aliases only: a real id is refused at construction,
    so it cannot be rendered by accident."""
    real = TerminalInput("q1.א.c0", Decimal("2"), "x",
                         components=(SkeletonComponent("k1", "x", "monolith"),))
    with pytest.raises(PlannerInputError, match="AM-G17"):
        ScopePlannerInput("q1.א", "q", None, (real,))
    t1 = TerminalInput("t1", Decimal("2"), "x", components=(SkeletonComponent("k1", "x", "monolith"),))
    with pytest.raises(PlannerInputError, match="AM-G17"):
        ScopePlannerInput("q1.א", "q", None, (t1,),
                          markers=(MarkerInput("q1.א.c0.m1", "x", "deduct", "t1", ("t1",)),))


# ── the few-shots ────────────────────────────────────────────────────────────

def _closed_world_errors(inp: ScopePlannerInput, out: ScopePlanOutput) -> list:
    """The §5.3 closed-list and decomposition rules, as a plain checker (the production
    validators are the mapping step's; this proves the examples obey what they teach)."""
    errs = []
    markers = {m.marker_id: m for m in inp.markers}
    planned = {t.terminal_id: t for t in inp.planned_terminals}
    refs_out = {}
    if [t.terminal_id for t in out.terminals] != list(planned):
        errs.append(f"terminals {[t.terminal_id for t in out.terminals]} != planned {list(planned)}")
    for pt in out.terminals:
        t = planned.get(pt.terminal_id)
        if t is None:
            continue
        refs = [c.component_ref for c in pt.credits]
        refs_out[pt.terminal_id] = set(refs)
        n_partials = [len(c.partials) for c in pt.credits]
        if pt.decomposition == "as_compiled":
            ok = not t.is_monolith and refs == [c.component_id for c in t.components]
        elif pt.decomposition == "binary":
            ok = t.is_monolith and refs == [t.components[0].component_id] and n_partials == [0]
        elif pt.decomposition == "ladder":
            ok = t.is_monolith and refs == [t.components[0].component_id] and n_partials[0] in (1, 2)
        else:
            ok = t.is_monolith and 2 <= len(refs) <= 6 and refs == list(SPLIT_REFS[:len(refs)])
        if not ok:
            errs.append(f"{pt.terminal_id}: bad {pt.decomposition} {refs} {n_partials}")
        if any(n > 2 for n in n_partials) or len(pt.interpretation_notes_he) > 3:
            errs.append(f"{pt.terminal_id}: list limits")
        for c in pt.credits:
            corpus = " ".join([inp.question_text, inp.example_solution or "", t.teacher_text])
            if c.source_span not in corpus:
                errs.append(f"{pt.terminal_id}: source_span not verbatim: {c.source_span!r}")
    seen_options = []
    for f in out.faults:
        members = [o.marker_id for o in f.options]
        seen_options += members
        if not 1 <= len(members) <= 7 or any(m not in markers for m in members):
            errs.append(f"fault options {members}")
            continue
        if any(f.anchor_terminal_id not in markers[m].candidate_anchors for m in members):
            errs.append(f"anchor {f.anchor_terminal_id} not a candidate of every member")
        if f.requires_component_ref is not None and \
                f.requires_component_ref not in refs_out.get(f.anchor_terminal_id, set()):
            errs.append(f"requires {f.requires_component_ref} not a credit of {f.anchor_terminal_id}")
        if any(markers[m].polarity == "no_deduct" for m in members):
            errs.append("a no_deduct marker is a fault option")
    disp = {d.marker_id: d for d in out.dispositions}
    if sorted(d.marker_id for d in out.dispositions) != sorted(markers):
        errs.append("dispositions must cover every marker exactly once")
    for mid, d in disp.items():
        if d.disposition == "fault" and seen_options.count(mid) != 1:
            errs.append(f"{mid}: fault but not exactly one option")
        if d.disposition == "merged":
            target = d.merged_into_marker_id
            fault_of = {m: i for i, f in enumerate(out.faults) for m in (o.marker_id for o in f.options)}
            if target not in fault_of or mid in seen_options or not d.reason_he:
                errs.append(f"{mid}: bad merge into {target}")
        if d.disposition == "not_a_deduction" and (mid in seen_options or not d.reason_he):
            errs.append(f"{mid}: bad not_a_deduction")
    return errs


@pytest.mark.parametrize("i", range(len(FEW_SHOTS)))
def test_few_shot_outputs_validate_and_use_only_their_own_ids(i: int) -> None:
    ex = FEW_SHOTS[i]
    # the JSON the PROMPT shows (not merely the Python object) parses as the schema
    system = planner_system_prompt(get_profile("computer_science"))
    blocks = re.findall(r"<output>\n(.*?)\n</output>", system, flags=re.S)
    assert len(blocks) == len(FEW_SHOTS)
    parsed = ScopePlanOutput.model_validate_json(blocks[i])
    assert parsed == ex.output
    assert render_scope_input(ex.input) in system
    assert _closed_world_errors(ex.input, parsed) == []


def test_few_shots_cover_what_section_5_4_names() -> None:
    ladder, requires, tiers = FEW_SHOTS
    assert any(t.decomposition == "ladder" for t in ladder.output.terminals)
    assert any(f.requires_component_ref for f in requires.output.faults)
    assert any(len(f.options) >= 2 for f in tiers.output.faults)
    assert any(d.disposition == "merged" for d in tiers.output.dispositions)


# Fixture vocabulary (hobby_tvshow, employee_course_select1, csharp_plane_combine,
# foundations_cs, bagrut_899371): the examples must share none of it (§5.4).
_FIXTURE_WORDS = ("TvShow", "TvRate", "Hobby", "Hobbies", "SetPeople", "people", "Employee",
                  "Course", "Department", "Plane", "Combine", "IsValidArray", "Workshop",
                  "Schedule", "Basketball", "Dice", "Mirror", "Statistics", "Channel",
                  "תחביב", "ערוץ", "דירוג", "עובד", "קורס", "טבלת מעקב", "זוגיים")


def test_few_shots_are_domain_shifted() -> None:
    for ex in FEW_SHOTS:
        text = render_scope_input(ex.input) + ex.output.model_dump_json()
        hits = [w for w in _FIXTURE_WORDS if w in text]
        assert not hits, (ex.title, hits)


# ── the assembled prompt ─────────────────────────────────────────────────────

_RULE_ID = re.compile(r"\b(?:PL|PB|OD|AM|PRC|INV|CWV?|R|C|P|Q|V|X|E)-\d+|R-alpha|R-beta|charge-once"
                      r"|credit-once|\bP-A\b|\bA-6\b")


@pytest.mark.parametrize("key", subject_keys())
def test_planner_system_prompt_per_pack(key: str) -> None:
    p = get_profile(key)
    text = planner_system_prompt(p)
    for n in range(1, 11):
        assert f"\n{n}. " in text, f"rule {n} missing"
    assert p.planner_fragment.rstrip("\n") in text
    assert text.count("--- Example ") == 3
    assert ("PRECEDENTS OF THIS SUBJECT" in text) == bool(p.precedents)
    assert all(c.text_he in text for c in p.precedents)
    assert p.verifier_fragment not in text            # the verifier's rules are not the planner's
    # no rule id reaches the model: its Hebrew is the teacher's to read (CWV-5)
    assert not _RULE_ID.search(text), _RULE_ID.search(text).group(0)
    assert PLANNER_PROMPT_VERSION == "planner-v6.1"
    # REVIEW-2 (owner-approved 2026-09-30): the cross-criterion rule, verbatim
    assert " ".join(("A fault check lives on one criterion. The same mistake at two criteria is "
                     "two fault checks; code links them.").split()) in " ".join(text.split())


def test_render_preamble_names_every_closed_list() -> None:
    user = render_scope_input(_synthetic_scope())
    head = user.split("=== SCOPE")[0]
    for token in ("t1, t2", "t1: k1 [monolith]", "n6", "t2: k2 [fixed]",
                  "m1, m2, m3", "as_compiled | binary | ladder | split",
                  "QUARTER | HALF | THREE_QUARTERS", "fault | merged | not_a_deduction",
                  "Never output a number"):
        assert token in head, token
