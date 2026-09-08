"""CS byte-identity pins (multisubject execution plan §4.2).

Pinned 2026-09-08 at HEAD 4ee8a5b, BEFORE any prompt file was touched for the
multi-subject seam. Every constant below is the production prompt text as it
was measured by the eval suites; the pinned versions are the stamps those
measurements carry.

Rule: after the seam refactor, the `computer_science` assembly of each prompt
must equal its pin byte-for-byte. A mismatch is a STOP, never a re-pin — a
re-pinned sha silently moves a measured number (plan §4.2, "any mismatch is a
stop, not a re-pin").
"""
from __future__ import annotations

import hashlib

import pytest

PINS = {
    # constant                      version                 sha256 (pinned 2026-09-08)
    "EXTRACTION_SYSTEM_PROMPT": ("3.10.0-fixsource", "8443840a3084931093f5bd44be76107415213aef766d3b4b05785799da116718"),
    "P1_SYSTEM":                ("t1.4-tables",      "b9a25bc5574020d44eb87c229d4ba06e651811c233a8dfb8590961095b51fefa"),
    "p2_system_prompt":         ("t1.4-tables",      "4c02e38f086322855e996e45161d2a934b8d225774601148759f6c70d919a0c8"),
    "P2_SPAN_SYSTEM":           ("t1.4-tables",      "b6356fa83357132dd4c4c05c89fb8afb0ea7cd0ca0f0e54da2c58f922d2c2fff"),
    "VERIFIER_SYSTEM_PROMPT":   ("grader-v5.4",      "840aa30b34d359059d51a46d64f9448d75cf9f62de07d3c9a19ef7da962fd4d5"),
    "GRADER_V3_SYSTEM_PROMPT":  ("grader-v3",        "6b01e08283e790a8f04e4ebff150f7d2e3e95cfb142d24ba7def2f378ac5e640"),
}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _current_texts() -> dict:
    """The CS text of every prompt, as production assembles it TODAY.

    Before the seam lands these are the module constants; after it they are the
    `computer_science` assembly. Both must hash to the same pin.
    """
    from app.services.docx_v3 import pipeline as ext
    from app.services.transcription.two_phase import prompts as tp
    from app.agents.grader import verifier_prompt as vp
    from app.agents.grader import prompt as v3
    try:
        # Post-seam: the registry assembles per profile. CS must be byte-identical.
        from app.subjects.registry import get_profile  # type: ignore
        cs = get_profile("computer_science")
        return {
            "EXTRACTION_SYSTEM_PROMPT": (ext.extraction_system_prompt(cs), ext.EXTRACTION_PROMPT_VERSION),
            "P1_SYSTEM": (tp.p1_system(cs), tp.TRANSCRIPTION_PROMPT_VERSION),
            "p2_system_prompt": (tp.p2_system_prompt(cs), tp.TRANSCRIPTION_PROMPT_VERSION),
            "P2_SPAN_SYSTEM": (tp.p2_span_system(cs), tp.TRANSCRIPTION_PROMPT_VERSION),
            "VERIFIER_SYSTEM_PROMPT": (vp.verifier_system_prompt(cs), vp.VERIFIER_PROMPT_VERSION),
            "GRADER_V3_SYSTEM_PROMPT": (v3.SYSTEM_PROMPT, v3.GRADING_PROMPT_VERSION),
        }
    except ImportError:
        return {
            "EXTRACTION_SYSTEM_PROMPT": (ext.EXTRACTION_SYSTEM_PROMPT, ext.EXTRACTION_PROMPT_VERSION),
            "P1_SYSTEM": (tp.P1_SYSTEM, tp.TRANSCRIPTION_PROMPT_VERSION),
            "p2_system_prompt": (tp.p2_system_prompt(), tp.TRANSCRIPTION_PROMPT_VERSION),
            "P2_SPAN_SYSTEM": (tp.P2_SPAN_SYSTEM, tp.TRANSCRIPTION_PROMPT_VERSION),
            "VERIFIER_SYSTEM_PROMPT": (vp.VERIFIER_SYSTEM_PROMPT, vp.VERIFIER_PROMPT_VERSION),
            "GRADER_V3_SYSTEM_PROMPT": (v3.SYSTEM_PROMPT, v3.GRADING_PROMPT_VERSION),
        }


@pytest.mark.parametrize("name", sorted(PINS))
def test_cs_prompt_is_byte_identical_to_its_pin(name: str) -> None:
    version, sha = PINS[name]
    text, current_version = _current_texts()[name]
    assert current_version == version, (
        f"{name}: version stamp moved {version!r} → {current_version!r}; the CS pin is the spec")
    assert _sha(text) == sha, (
        f"{name}: CS prompt text changed (sha {_sha(text)[:12]}… ≠ pin {sha[:12]}…). "
        "STOP — do not re-pin; the measured CS numbers ride on these bytes.")
