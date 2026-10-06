"""grader-v6 explainer — the system prompt and its examples (PR_grader_v6_options.md §7.4, §8).
Pure: no DB, no provider.

  * the core states X-1..X-11 as numbered rules 1..11, subject-agnostic;
  * the pack's fragment and precedents (Hebrew text only) are appended; no rule id, no PB-*;
  * the three examples render through the real renderer, are domain-shifted, and every
    example line passes E-1..E-5 against its own input;
  * the CS assembly is sha-pinned (a change is deliberate: bump the version, log RUNLOG).
"""
from __future__ import annotations

import hashlib
import json
import re

import pytest

from app.agents.explainer.prompt import (EXAMPLES, EXPLAINER_CORE, EXPLAINER_PROMPT_VERSION,
                                         STUDENT_SECTION_HEADER, ScopeExplanations,
                                         explainer_system_prompt, render_scope_message)
from app.agents.explainer.validators import validate_scope
from app.subjects import get_profile, subject_keys

_RULE_ID = re.compile(r"\b(?:PL|PB|OD|AM|PRC|INV|CWV?|R|C|P|Q|V|X|E)-\d+|R-alpha|R-beta|charge-once"
                      r"|credit-once|\bP-A\b|\bA-6\b")


@pytest.mark.parametrize("key", subject_keys())
def test_explainer_system_prompt_per_pack(key: str) -> None:
    p = get_profile(key)
    text = explainer_system_prompt(p)
    for n in range(1, 12):
        assert f"\n{n}. " in text, f"rule {n} missing"
    assert p.explainer_fragment.rstrip("\n") in text
    assert ("PRINCIPLES OF THIS SUBJECT" in text) == bool(p.precedents)
    assert all(c.text_he in text for c in p.precedents)
    assert p.verifier_fragment not in text and p.planner_fragment not in text
    assert text.count("--- Example ") == 3
    assert not _RULE_ID.search(text), _RULE_ID.search(text).group(0)    # CWV-5 / E-3
    assert not re.search(r"\bPB-?\d+\b|PB-", text)                       # AM-G5
    assert explainer_system_prompt(p) == text                            # the cached prefix
    assert EXPLAINER_PROMPT_VERSION == "explainer-v1.0"


def test_the_core_is_subject_agnostic() -> None:
    """§3.3: the core knows no subject — CS lives in the CS pack's fragment."""
    for word in ("C#", "Java", "Python", "class ", "method", "compile", "algebra", "essay",
                 "computer", "programming"):
        assert word.lower() not in EXPLAINER_CORE.lower(), word


@pytest.mark.parametrize("i", range(len(EXAMPLES)))
def test_example_lines_pass_their_own_validators(i: int) -> None:
    ex = EXAMPLES[i]
    system = explainer_system_prompt(get_profile("computer_science"))
    blocks = re.findall(r"<output>\n(.*?)\n</output>", system, flags=re.S)
    assert len(blocks) == len(EXAMPLES)
    parsed = ScopeExplanations.model_validate_json(blocks[i])     # the JSON the prompt SHOWS
    assert parsed == ex.output
    assert render_scope_message(ex.input) in system
    checked = validate_scope([(ln.terminal_id, ln.text_he) for ln in parsed.lines], ex.input)
    assert {tid: v.failed_rules for tid, v in checked.verdicts.items()} == \
        {t.terminal_id: () for t in ex.input.terminals}
    assert checked.telemetry == []
    for ln in parsed.lines:
        assert len(ln.text_he.split()) <= 20 and len(ln.text_he) <= 200   # X-5's aim


def test_examples_cover_the_target_register_situations() -> None:
    """§7.4's five shapes, plus X-10's «already deducted elsewhere»."""
    terminals = [t for ex in EXAMPLES for t in ex.input.terminals]
    statuses = {f.status for t in terminals for f in t.fault_checks}
    assert {"applied", "inactive", "superseded"} <= statuses
    assert any(t.awarded == t.points_possible for t in terminals)          # full marks
    assert any(t.awarded == 0 for t in terminals)                          # a zero
    assert any(0 < c.selected_value < t.points_possible and not t.fault_checks
               for t in terminals for c in t.credit_checks)                # a partial
    assert any(c.absence_pointer_he for t in terminals for c in t.credit_checks)
    assert {ex.input.question_id for ex in EXAMPLES} == {"q2", "q4", "q6"}


# Fixture vocabulary (hobby_tvshow, employee_course_select1, csharp_plane_combine,
# foundations_cs, bagrut_899371): the examples share none of it (§7.4, as the planner's).
_FIXTURE_WORDS = ("TvShow", "TvRate", "Hobby", "Hobbies", "Mobby", "SetPeople", "people",
                  "Employee", "Course", "Department", "Plane", "Combine", "IsValidArray",
                  "Workshop", "Schedule", "Basketball", "Dice", "Mirror", "Statistics",
                  "Channel", "תחביב", "ערוץ", "דירוג", "עובד", "קורס", "טבלת מעקב", "זוגיים",
                  "מטוס", "קיבולת")


def test_examples_are_domain_shifted() -> None:
    text = "\n".join(render_scope_message(ex.input) + ex.output.model_dump_json()
                     for ex in EXAMPLES) + EXPLAINER_CORE
    hits = [w for w in _FIXTURE_WORDS if w in text]
    assert not hits, hits


def test_example_messages_split_at_the_student_section() -> None:
    for ex in EXAMPLES:
        head, tail = render_scope_message(ex.input).split(STUDENT_SECTION_HEADER)
        assert "grade:" not in head and "quoted from the answer" not in head
        assert all(t.teacher_text.strip() in head for t in ex.input.terminals)
        assert "Write one line for each of:" in tail


# ── the pin ──────────────────────────────────────────────────────────────────

PIN = ("explainer-v1.0/computer_science@v1",
       "d6e674734fa410d9ee6557652ca0effd043f8aa06e003b957a4bf68081e98c1f")


def test_cs_explainer_system_prompt_pinned() -> None:
    cs = get_profile("computer_science")
    version = f"{EXPLAINER_PROMPT_VERSION}/{cs.pack_id}@{cs.pack_version}"
    sha = hashlib.sha256(explainer_system_prompt(cs).encode("utf-8")).hexdigest()
    assert (version, sha) == PIN, (
        f"the CS explainer assembly moved ({version}, {sha}). A change is deliberate: bump "
        "EXPLAINER_PROMPT_VERSION, log it in RUNLOG, then re-pin.")


# ── §3.3 litmus ──────────────────────────────────────────────────────────────

def test_a_new_pack_explains_with_no_core_change(monkeypatch) -> None:
    from app.schemas import ontology_types
    from app.subjects import registry
    from tests.subjects import physics_test as pack

    monkeypatch.setitem(ontology_types.SUBJECT_PROFILES, pack.KEY, pack.ONTOLOGY)
    monkeypatch.setitem(registry._PROFILES, pack.KEY, registry._build(pack))
    text = explainer_system_prompt(get_profile(pack.KEY))
    assert pack.EXPLAINER_FRAGMENT.rstrip("\n") in text and "\n11. " in text
    json.dumps(text)                                  # a plain string, nothing pack-specific inside
