"""Prompt-rendering regression tests. Zero mocks; runs in `pytest -q`.

The transcription prompt is versioned provenance (a result is a function of
fixtures + config + PROMPT_VERSION + model). These tests pin the t1.2 identity-
exclusion policy: the student's name/class/ID must be excluded, WITHOUT
collateral damage to the `שאלה {n}` / `א.` section markers that page/answer
attribution depends on.
"""
from .prompts import P1_SYSTEM, TRANSCRIPTION_PROMPT_VERSION


def test_prompt_version_is_t1_4_tables():
    # t1.3/t1.3b (crossed-out whole-block reinforcement) were trialed and
    # REVERTED 2026-07-10 — see prompts.py note + RUNLOG. t1.4-tables (2026-08-29)
    # pins the hand-drawn-table shape; the version is provenance, so it moves
    # whenever the text the model sees moves.
    assert TRANSCRIPTION_PROMPT_VERSION == "t1.4-tables"


def test_p1_pins_the_hand_drawn_table_shape():
    """t1.4 — the table shape is pinned, and pinned in the ONE way that agrees
    with the scorer and the review surface (PLAN_multi_rubric_fixtures.md D9).

    Each assertion is a measured failure mode, not a style preference:
      * a `[TABLE]` caption injects fabricated `[`/`]` structural tokens,
      * a `|---|` separator injects fabricated `--` (decrement) operators,
      * `||` is BOTH the logical-OR operator on the critical-token metric AND a
        code-token that makes the review surface refuse to render the grid,
      * a skipped blank cell shifts every later value under the wrong header.
    """
    assert "one table row per line" in P1_SYSTEM
    assert "SAME number of cells" in P1_SYSTEM
    assert "never skip it" in P1_SYSTEM
    assert "wrong column" in P1_SYSTEM          # the reason, not just the rule
    assert "never `||`" in P1_SYSTEM
    assert "Do NOT add a header-separator" in P1_SYSTEM
    assert "| x | i | arr[i] | ret |" in P1_SYSTEM   # the worked example renders


def test_p1_table_rule_does_not_contradict_the_plain_text_rule():
    """The prompt still forbids markdown, so the table rows MUST be carved out
    explicitly — two absolute rules that appear to conflict is how you get
    inconsistent output."""
    assert "PLAIN TEXT only" in P1_SYSTEM
    assert "are the ONE exception" in P1_SYSTEM
    assert "not markdown" in P1_SYSTEM


def test_p1_table_rule_forbids_inventing_tables():
    """Precision bias: only ink the student drew as a grid becomes a table, and
    code containing `|` (`if (a || b)`) is never reformatted."""
    assert "never reformat ordinary" in P1_SYSTEM
    assert "code that happens to contain" in P1_SYSTEM


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
