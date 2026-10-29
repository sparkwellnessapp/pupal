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


def test_bet2_table_rows_variant_is_opt_in_and_lands_inside_the_table_rule():
    """MISSION Bet 2: behind a flag, because P1_SYSTEM is sha-pinned."""
    from app.services.transcription.two_phase.prompts import p1_system
    assert p1_system() == P1_SYSTEM
    v = p1_system(table_rows=True)
    assert "never break a line inside a row" in v and "check mark as `✓`" in v
    assert v.index("wrong column.") < v.index("A row is ONE line") < v.index("pipes must never touch")


def test_boxed_values_variant_is_opt_in_and_demands_certainty():
    """GT §5.2a rule 5, behind a flag (P1_SYSTEM is sha-pinned). The pinned wording
    (RUNLOG 2026-10-03) brackets only a number she is CERTAIN was framed as the final
    answer, and says outright that reading is unchanged — the clause that stopped the
    rule from changing other digits."""
    from app.services.transcription.two_phase.prompts import p1_system
    assert p1_system(boxed_values=False) == P1_SYSTEM
    v = p1_system(boxed_values=True)
    assert "`[74]`" in v and "CERTAIN" in v and "never changes HOW you read" in v
    assert v.index("Use `[?]`") < v.index("FINAL-ANSWER BOX") < v.index("Preserve line breaks")
    both = p1_system(table_rows=True, boxed_values=True)
    assert "FINAL-ANSWER BOX" in both and "never break a line inside a row" in both
