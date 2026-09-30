"""grader-v6 subject packs (PR_grader_v6_options.md §8; [Q-18], [AM-G5]). Pure: no DB, no provider.

  test_cs_pack_assembled_prompts_pinned       the CS planner system prompt + the CS verifier and
                                              explainer fragments, sha-pinned
  test_no_pb_rulings_in_any_prompt            [AM-G5] no PB-* (nor any class-4 ruling) in any prompt
  test_no_subject_literals_outside_packs      [Q-18] the v6 grading core names no subject
  test_new_pack_needs_no_core_change          the §3.3 litmus: `physics_test`, a test-only pack

The pins follow tests/subjects/test_prompt_identity.py's rule: a moved sha is a deliberate
change, logged in RUNLOG, with PLANNER_PROMPT_VERSION / PACK_VERSION bumped in the same
commit — never a silent re-pin.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from app.agents.plan_gen import constitution
from app.subjects import get_profile, subject_keys

BACKEND = Path(__file__).resolve().parents[2]

PINS = {
    # name                          version                          sha256
    "cs.planner_system_prompt": ("planner-v6.1/computer_science@v1", "ff72866c026aec6be256fe8fa4fd30d255339a8dbe95011436d1da5a2bdfd66b"),
    "cs.verifier_fragment":     ("computer_science@v1",              "305158a2c207b927504480b686487b233c2eb9b44ba45ea2549b637de39cfb8e"),
    "cs.explainer_fragment":    ("computer_science@v1",              "ea68000e0e3f5be372b056dad265e71c9bcc8b2d41c68226627ac18d3c59426b"),
}

AM_G5_PRECEDENTS = ("PL-1", "PL-2", "PL-3", "PL-9", "PL-10", "R-alpha", "R-beta",
                    "A-6", "charge-once", "credit-once", "P-A")


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── pins ─────────────────────────────────────────────────────────────────────

def _cs_texts() -> dict:
    from app.agents.planner.prompt import PLANNER_PROMPT_VERSION, planner_system_prompt

    cs = get_profile("computer_science")
    pack = f"{cs.pack_id}@{cs.pack_version}"
    return {
        "cs.planner_system_prompt": (planner_system_prompt(cs), f"{PLANNER_PROMPT_VERSION}/{pack}"),
        "cs.verifier_fragment": (cs.verifier_fragment, pack),
        "cs.explainer_fragment": (cs.explainer_fragment, pack),
    }


@pytest.mark.parametrize("name", sorted(PINS))
def test_cs_pack_assembled_prompts_pinned(name: str) -> None:
    version, sha = PINS[name]
    text, current_version = _cs_texts()[name]
    assert current_version == version, (
        f"{name}: version moved {version!r} → {current_version!r}; re-pin only with a RUNLOG entry")
    assert _sha(text) == sha, (
        f"{name}: text changed (sha {_sha(text)[:12]}… ≠ pin {sha[:12]}…). A change to the CS "
        "assembly is deliberate: bump the version, log it in RUNLOG, then re-pin.")


# ── AM-G5: what the CS pack is made of ───────────────────────────────────────

def test_cs_verifier_fragment_is_the_v5_text_verbatim() -> None:
    """[AM-G5] rules 3-5 + rule 6's PL-9 / R-1 / C-1 clauses, byte-for-byte from grader-v5.4."""
    from app.agents.grader.verifier_prompt import VERIFIER_SYSTEM_PROMPT, _CS_RULES_3_5
    from app.subjects.profiles.computer_science import verifier as cs

    assert cs.RULES_3_5 == _CS_RULES_3_5
    assert cs.RULES_3_5 in VERIFIER_SYSTEM_PROMPT
    assert cs.RULE_6_CLAUSES in VERIFIER_SYSTEM_PROMPT
    heads = [l.strip() for l in cs.RULE_6_CLAUSES.splitlines() if l.strip().startswith("- [")]
    assert [h.split("]")[0] + "]" for h in heads] == ["- [PL-9]", "- [PL-9 boundary, R-1]", "- [C-1, R-D]"]
    assert get_profile("computer_science").verifier_fragment == cs.RULES_3_5 + "\n" + cs.RULE_6_CLAUSES


def test_cs_precedents_are_the_am_g5_clauses_by_reference() -> None:
    cs = get_profile("computer_science")
    assert tuple(c.clause_id for c in cs.precedents) == AM_G5_PRECEDENTS
    everything = constitution.clauses_for("computer_science", include_constitution=True)
    for c in cs.precedents:          # the constitution's own objects — referenced, never copied
        assert any(c is k for k in everything), c.clause_id


def test_precedents_never_reach_the_verifier() -> None:
    for key in subject_keys():
        p = get_profile(key)
        for c in p.precedents:
            assert c.text_he not in p.verifier_fragment, (key, c.clause_id)


@pytest.mark.parametrize("cid", constitution.NEVER_GENERATED + ("PB-1", "nope"))
def test_constitution_select_refuses_class_4_and_unknown_ids(cid: str) -> None:
    with pytest.raises(ValueError):
        constitution.select(cid)


def test_non_cs_packs_are_present_and_short() -> None:
    for key in ("english", "mathematics"):
        p = get_profile(key)
        assert p.pack_id == key and p.pack_version
        assert p.precedents == ()                     # AM-G5 assigns the clauses to CS only
        for name in ("planner_fragment", "verifier_fragment", "explainer_fragment"):
            lines = [l for l in getattr(p, name).splitlines() if l.strip()]
            assert 0 < len(lines) <= 12, f"{key}.{name}: {len(lines)} lines"


# ── AM-G5: no PB-* ruling in any prompt, ever ────────────────────────────────

_RULING_TOKEN = re.compile(r"\bPB-?\d+\b|PB-")


def _every_prompt_text() -> dict:
    from app.agents.feedback.prompt import FEEDBACK_SYSTEM_PROMPT
    from app.agents.grader.prompt import SYSTEM_PROMPT as GRADER_V3_SYSTEM_PROMPT
    from app.agents.grader.verifier_prompt import verifier_system_prompt
    from app.agents.plan_compiler.route import ROUTER_SYSTEM_PROMPT
    from app.agents.plan_compiler.segment import SEGMENTER_SYSTEM_PROMPT
    from app.agents.planner.prompt import planner_system_prompt

    texts = {"feedback": FEEDBACK_SYSTEM_PROMPT, "grader_v3": GRADER_V3_SYSTEM_PROMPT,
             "router": ROUTER_SYSTEM_PROMPT, "segmenter": SEGMENTER_SYSTEM_PROMPT}
    for key in subject_keys():
        p = get_profile(key)
        texts[f"{key}.planner_system_prompt"] = planner_system_prompt(p)
        texts[f"{key}.v5_verifier_system_prompt"] = verifier_system_prompt(p)
        texts[f"{key}.planner_fragment"] = p.planner_fragment
        texts[f"{key}.verifier_fragment"] = p.verifier_fragment
        texts[f"{key}.explainer_fragment"] = p.explainer_fragment
        for c in p.precedents:
            texts[f"{key}.precedent.{c.clause_id}"] = f"{c.clause_id} {c.text_he}"
    return texts


def test_no_pb_rulings_in_any_prompt() -> None:
    texts = _every_prompt_text()
    assert len(texts) > 20
    for name, text in texts.items():
        assert not _RULING_TOKEN.search(text), f"{name}: carries a PB-* ruling token"
        for cid in constitution.NEVER_GENERATED:   # the other class-4 rulings, likewise
            assert cid not in text, f"{name}: carries the exam-specific ruling {cid!r}"


# ── Q-18: no subject literal in the v6 grading core ──────────────────────────

_SUBJECT_LITERAL = re.compile(r"""["'](?:computer_science|mathematics|english)["']|\bsubject\s*==""")

_V6_CORE_FILES = ("app/agents/grader/plan_values.py", "app/agents/grader/plan_validator_v6.py",
                  "app/services/pricing_v6.py")
_V6_CORE_DIRS = ("app/agents/explainer", "app/agents/planner")
_PLAN_SCHEMAS_V6_BANNER = "# plan/v6 — one building block for every check"


def _v6_core_sources() -> dict:
    out = {rel: (BACKEND / rel).read_text(encoding="utf-8") for rel in _V6_CORE_FILES}
    for d in _V6_CORE_DIRS:
        for f in sorted((BACKEND / d).glob("*.py")):
            out[f.relative_to(BACKEND).as_posix()] = f.read_text(encoding="utf-8")
    schemas = (BACKEND / "app/agents/grader/plan_schemas.py").read_text(encoding="utf-8")
    assert _PLAN_SCHEMAS_V6_BANNER in schemas, "the v6 section banner moved — re-anchor this test"
    out["plan_schemas.py (v6 section)"] = schemas[schemas.index(_PLAN_SCHEMAS_V6_BANNER):]
    return out


def test_no_subject_literals_outside_packs() -> None:
    sources = _v6_core_sources()
    assert any(k.startswith("app/agents/planner/") for k in sources)
    offenders = {name: m.group(0) for name, src in sources.items()
                 for m in [_SUBJECT_LITERAL.search(src)] if m}
    assert not offenders, f"subject literal in the v6 grading core: {offenders}"


def test_the_subject_literal_scan_can_fire() -> None:
    assert _SUBJECT_LITERAL.search('if subject == "x":')
    assert _SUBJECT_LITERAL.search("profile = get_profile('english')")
    assert not _SUBJECT_LITERAL.search("the English example")


# ── §3.3 litmus: a new pack needs no core change ─────────────────────────────

def test_new_pack_needs_no_core_change(monkeypatch) -> None:
    from decimal import Decimal

    from app.agents.planner.inputs import ScopePlannerInput, SkeletonComponent, TerminalInput
    from app.agents.planner.prompt import planner_system_prompt, render_scope_input
    from app.schemas import ontology_types
    from app.subjects import UnknownSubject, registry

    from . import physics_test as pack

    with pytest.raises(UnknownSubject):             # production never sees it
        get_profile(pack.KEY)

    monkeypatch.setitem(ontology_types.SUBJECT_PROFILES, pack.KEY, pack.ONTOLOGY)
    monkeypatch.setitem(registry._PROFILES, pack.KEY, registry._build(pack))

    profile = get_profile(pack.KEY)                  # the ONE lookup, unchanged
    assert (profile.pack_id, profile.pack_version) == ("physics_test", "v1")
    system = planner_system_prompt(profile)
    assert pack.PLANNER_FRAGMENT.rstrip("\n") in system
    assert all(c.text_he in system for c in profile.precedents)
    assert "10. CLOSED LISTS" in system and system.count("--- Example ") == 3

    scope = ScopePlannerInput(
        scope_id="q1", question_text="גוף נופל מגובה של 20 מטר. חשבו את זמן הנפילה.",
        example_solution="t = sqrt(2h / g) = 2 s",
        terminals=(TerminalInput("t1", Decimal("5"), "חישוב זמן הנפילה עם יחידות",
                                 components=(SkeletonComponent("k1", "חישוב זמן הנפילה",
                                                               "monolith"),)),))
    user = render_scope_input(scope)
    assert "terminal_id (plan each one): t1" in user and "t1: k1 [monolith]" in user

    # zero changes outside the pack folder: nothing in production knows this subject
    hits = [p.relative_to(BACKEND).as_posix() for p in (BACKEND / "app").rglob("*.py")
            if "physics_test" in p.read_text(encoding="utf-8")]
    assert hits == []
