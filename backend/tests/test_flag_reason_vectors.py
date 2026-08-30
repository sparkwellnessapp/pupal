"""
Cross-pinned flag-reason vocabulary (closeout/B1) — the PY half.

WHY THIS EXISTS (and why it is not the test the audit first asked for):
the audit hypothesised that "what counts as needs-eyes" is implemented a third
time in the frontend's `partitionItems`. It is not — that module CONSUMES the
server's `flag_verdict.review_needed` ("the server's word", per its own
docstring; B1 made clean a server-guaranteed property). So the predicate is
not forked and there is nothing to cross-pin there.

What IS mirrored across the language boundary is the REASON VOCABULARY:
  - the client owns the Hebrew label map (F3: a Latin enum must never render),
  - and the identity-vs-content split that decides whether a flagged item goes
    to the identity wave or the needs-eyes rows.
Both are hand-maintained tables keyed by strings this module emits. A reason
added here without a client label renders raw Latin to a teacher; added
without a classification, it silently defaults. That is the drift this pins.

The fixture is the single artifact; the TS twin reads the same file.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "flag_reason_vocabulary.json"
TRIAGE = Path(__file__).parents[1] / "app" / "services" / "batch_triage.py"


def _vocabulary() -> set[str]:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return {entry["reason"] for entry in data["reasons"]}


def test_fixture_is_wellformed() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    kinds = {entry["kind"] for entry in data["reasons"]}
    assert kinds <= {"identity", "content"}, "every reason is identity or content"
    reasons = [entry["reason"] for entry in data["reasons"]]
    assert len(reasons) == len(set(reasons)), "no duplicate reasons"


def test_triage_emits_nothing_outside_the_pinned_vocabulary() -> None:
    """Every `reasons.append("…")` literal in batch_triage must be pinned.

    Source-scanning rather than exhaustive input-driving is deliberate: it
    catches a NEW reason the moment it is written, including on code paths a
    behavioural test would need a bespoke fixture to reach.
    """
    source = TRIAGE.read_text(encoding="utf-8")
    emitted = set(re.findall(r'reasons\.append\(\s*"([a-z_]+)"', source))
    assert emitted, "the scan found no reasons — the emit pattern changed; fix this test"

    unpinned = emitted - _vocabulary()
    assert not unpinned, (
        f"batch_triage emits {sorted(unpinned)} but the cross-pinned vocabulary "
        f"does not carry them. Add each to tests/fixtures/flag_reason_vocabulary.json "
        f"WITH its identity/content kind, then add a Hebrew label to the frontend's "
        f"FLAG_REASON_LABELS — otherwise the chip renders a raw Latin enum (F3)."
    )


def test_vocabulary_carries_no_reason_the_server_cannot_emit() -> None:
    """The reverse direction: a stale entry is dead weight the client still
    ships labels for. Documented exceptions go here explicitly, never silently."""
    source = TRIAGE.read_text(encoding="utf-8")
    emitted = set(re.findall(r'reasons\.append\(\s*"([a-z_]+)"', source))
    stale = _vocabulary() - emitted
    assert not stale, (
        f"the vocabulary pins {sorted(stale)} which batch_triage never emits — "
        f"remove them, or document the emitter if it lives elsewhere."
    )
