"""Prompt-rendering regression tests. Zero mocks; runs in `pytest -q`.

The transcription prompt is versioned provenance (a result is a function of
fixtures + config + PROMPT_VERSION + model). These tests pin the t1.2 identity-
exclusion policy: the student's name/class/ID must be excluded, WITHOUT
collateral damage to the `שאלה {n}` / `א.` section markers that page/answer
attribution depends on.
"""
from .prompts import P1_SYSTEM, TRANSCRIPTION_PROMPT_VERSION


def test_prompt_version_is_t1_2():
    # t1.3/t1.3b (crossed-out whole-block reinforcement) were trialed and
    # REVERTED 2026-07-10 — see prompts.py note + RUNLOG.
    assert TRANSCRIPTION_PROMPT_VERSION == "t1.2"


def test_p1_excludes_student_identity():
    """Policy 2: the identity-exclusion clause must render."""
    assert "EXCLUDE the student's identity" in P1_SYSTEM
    assert "must not be transcribed" in P1_SYSTEM
    # name / class / id are the three identity fields named
    assert "name" in P1_SYSTEM and "כיתה" in P1_SYSTEM and "ID" in P1_SYSTEM


def test_p1_keeps_section_markers():
    """The load-bearing guard: identity exclusion must NOT suppress the
    section markers, or page/answer attribution breaks."""
    assert "שאלה {n}" in P1_SYSTEM
    assert "`א.`" in P1_SYSTEM
    assert "distinct from the" in P1_SYSTEM  # the explicit 'not identity' clause


def test_p1_no_longer_includes_all_ink_verbatim():
    """The old over-inclusive line (which drove name transcription) is gone."""
    assert "Include ALL handwritten ink" not in P1_SYSTEM
