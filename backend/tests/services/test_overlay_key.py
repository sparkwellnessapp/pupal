"""
The overlay has ONE key, and no test may invent a second one.

WHY THESE ARE STRUCTURAL RATHER THAN BEHAVIOURAL. `GradedTestOverrides` is
persisted under `draft_json["teacher_overrides"]`, but every stamp READER used
`draft_json["overrides"]` — a key nothing has ever written. Two silent
consequences: a dragged stamp could never reach the student's PDF, and «apply to
all» could never clear anything, so `stamp_applied_count` reported a number that
was permanently and untruthfully 0.

It survived because the tests HAND-BUILT the wrong shape. A fixture constructed
by the test rather than by the code under test validates nothing — it validated
a key production never produces, and passed. So the guard cannot be another
behavioural test over a hand-made dict; it has to be a statement about the
source itself.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
APP = BACKEND / "app"
TESTS = BACKEND / "tests"


def test_overlay_writer_and_readers_agree_on_one_key():
    """The persisted key is what `GradedTestDraft` declares, and every reader
    reaches it through the one named constant."""
    from app.schemas.graded_test_draft import GradedTestDraft
    from app.services.returned_exam import OVERLAY_KEY

    assert OVERLAY_KEY in GradedTestDraft.model_fields, (
        f"{OVERLAY_KEY!r} is not a field of GradedTestDraft — the constant and "
        f"the schema have drifted")

    # and it is the field that actually carries the overlay
    field = GradedTestDraft.model_fields[OVERLAY_KEY]
    from app.schemas.graded_test_draft import GradedTestOverrides
    assert field.annotation in (GradedTestOverrides, type(None)) or \
        GradedTestOverrides.__name__ in str(field.annotation), str(field.annotation)


def test_no_source_file_reaches_the_overlay_by_a_literal_key():
    """`draft_json["overrides"]` / `.get("overrides")` must appear NOWHERE in
    app/. The literal is how the readers and the writer drifted apart; the
    constant is what stops them drifting again."""
    offenders = []
    pattern = re.compile(r"""(?:draft_json|row\.draft_json|\)\s*)\s*(?:\.get\(|\[)\s*["']overrides["']""")
    for path in sorted(APP.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(BACKEND)}:{i}: {line.strip()}")
    assert not offenders, (
        "a draft overlay is being read by the literal key 'overrides', which "
        "nothing writes:\n  " + "\n  ".join(offenders))


def _overlay_literal_sites(path: Path) -> list[str]:
    """Real CODE uses of the literal key — parsed, not grepped.

    An earlier version of this guard matched raw text and flagged its own
    docstring explaining the bug. A guard that fires on prose about itself
    teaches people to weaken it, so it parses instead: a dict key, a subscript,
    or a `.get("overrides")` argument, and nothing that is merely written down.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[str] = []

    def is_key(node) -> bool:
        return isinstance(node, ast.Constant) and node.value == "overrides"

    for node in ast.walk(tree):
        # {"overrides": ...}
        if isinstance(node, ast.Dict) and any(is_key(k) for k in node.keys):
            hits.append(f"{path.name}:{node.lineno}: dict literal keyed 'overrides'")
        # x["overrides"]
        elif isinstance(node, ast.Subscript) and is_key(node.slice):
            hits.append(f"{path.name}:{node.lineno}: subscript ['overrides']")
        # x.get("overrides")
        elif (isinstance(node, ast.Call)
              and isinstance(node.func, ast.Attribute) and node.func.attr == "get"
              and node.args and is_key(node.args[0])):
            hits.append(f"{path.name}:{node.lineno}: .get('overrides')")
    return hits


def test_no_test_hand_builds_a_draft_overlay():
    """A test that constructs `draft_json` with an "overrides" key is the bug,
    not the guard — that is precisely what let the dead key ship.

    NOTE the deliberate narrowness: `PATCH /draft`'s REQUEST BODY legitimately
    has a field called `overrides` (`body.overrides`), and `json={"overrides":
    ...}` is a request body, not a draft. Those are correct and are excluded —
    a guard that flagged them would be asking for the right code to be changed.
    """
    offenders: list[str] = []
    for path in sorted(TESTS.rglob("*.py")):
        if path.name == Path(__file__).name:
            continue
        text = path.read_text(encoding="utf-8")
        if "overrides" not in text:
            continue
        for hit in _overlay_literal_sites(path):
            line_no = int(hit.split(":")[1])
            line = text.splitlines()[line_no - 1]
            if "json=" in line or "body" in line:      # a request body
                continue
            offenders.append(f"{path.relative_to(BACKEND)}:{hit.split(':', 1)[1]}")
    assert not offenders, (
        "tests are hand-building a draft overlay under the key 'overrides'. "
        "Build it through GradedTestOverrides and persist it under OVERLAY_KEY, "
        "the way production does:\n  " + "\n  ".join(offenders))
