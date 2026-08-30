"""
Override attribution — the five keys, resolved in one query (PR-G6).

The operating doc needs, per teacher override: **teacher, school, question
identity, criterion, student**. Four of the five already existed as columns or
joins; `school` arrives with migration 018. This module is the single place that
knows how they compose, so the analysis query and the onboarding endpoint cannot
drift about what "the same school" means.

Two design points worth stating, because both are easy to get wrong later:

* **The schools join is an OUTER join.** `users.school_id` is nullable by design
  (skippable onboarding). An INNER join here would silently drop every override
  by a teacher who never answered the prompt — the rows would simply not appear,
  and nothing would say so.
* **Matching is normalized-exact, never fuzzy** — the conservative
  student-match precedent (CLAUDE.md §7). Two schools differing by one
  character are two schools. Fuzzy matching merges real institutions and there
  is no way to un-merge them afterwards.
"""
from __future__ import annotations

import re

from sqlalchemy import Select, func, literal_column, select

from app.models.grading import GradedTest
from app.models.school import School
from app.models.transcription import Transcription
from app.models.user import User

_WS = re.compile(r"\s+")


def normalize_school_name(name: str) -> str:
    """The normalized-exact key: trimmed, internal whitespace collapsed,
    case-folded. Mirrors migration 018's unique index expression exactly — if
    one changes the other must, or the DB and the app disagree about identity."""
    return _WS.sub(" ", (name or "").strip()).casefold()


def override_attribution_query() -> Select:
    """One SELECT resolving all five attribution keys per overridden terminal.

    Terminal ids are FULL PATHS by convention (`q2.ב.c4.s2`, CLAUDE.md §5), so
    the question id is the segment before the first dot — derived, not stored,
    which is why there is no question_id column to join on.

    `check_id` is read from the override object. It is NULL for v3-era overlays
    (which had no check level) and populated from PR-G5 onward; that NULL is
    honest missing data, not a defect to coalesce away.
    """
    overrides = func.jsonb_each(
        GradedTest.draft_json["teacher_overrides"]
    ).table_valued("key", "value").render_derived(name="ov", with_types=True).lateral()

    terminal_id = literal_column("ov.key")
    override_obj = literal_column("ov.value")

    return (
        select(
            GradedTest.id.label("graded_test_id"),
            GradedTest.user_id.label("teacher_id"),
            User.school_id.label("school_id"),
            School.name.label("school_name"),
            Transcription.student_id.label("student_id"),
            GradedTest.rubric_id.label("rubric_id"),
            func.split_part(terminal_id, ".", 1).label("question_id"),
            terminal_id.label("criterion_id"),
            # literal_column has no JSONB typing, so the extraction is written
            # as the SQL function rather than the [] operator.
            func.jsonb_extract_path_text(override_obj, "check_id").label("check_id"),
            GradedTest.draft_json["plan_version"].astext.label("plan_version"),
        )
        .select_from(GradedTest)
        .join(User, User.id == GradedTest.user_id)
        .join(Transcription, Transcription.id == GradedTest.transcription_id)
        .outerjoin(School, School.id == User.school_id)   # OUTER — see module doc
        .join(overrides, literal_column("true"))
    )
