"""
PR-G6 — school on the teacher, and the override-attribution join.

The operating doc needs five keys per override: teacher, school, question
identity, criterion, student. Four already resolve by join today
(`graded_tests.user_id`, `transcriptions.student_id`, and
`rubric_id + question_id + criterion_id + check_id + plan_version`); only
`school` has no home — there is no school entity or column anywhere.

These tests are pure: they inspect the model and the query the helper builds.
No DB round trip, no mocks. `school` must be NULLABLE throughout — a first-time
teacher has not told us her school and must still be attributable on the other
four keys, or the analysis silently drops her rows.
"""
import pytest


def test_school_entity_exists_and_users_carry_a_nullable_fk():
    """The column is nullable BY DESIGN: onboarding is skippable (§G6), so
    attribution must survive its absence rather than exclude the teacher."""
    from app.models.school import School          # noqa: F401
    from app.models.user import User

    assert School.__tablename__ == "schools"
    for col in ("id", "name", "city", "created_at"):
        assert col in School.__table__.columns, f"schools.{col} missing"

    school_id = User.__table__.columns.get("school_id")
    assert school_id is not None, "users.school_id missing"
    assert school_id.nullable is True, (
        "users.school_id must be nullable — a teacher who skipped the "
        "one-field prompt still has four resolvable attribution keys")
    assert school_id.foreign_keys, "users.school_id must be a real FK to schools"


def test_override_attribution_joins_resolve():
    """All five keys resolve in ONE query, and the school join is an OUTER join
    so a school-less teacher's overrides are still returned."""
    from app.services.override_attribution import override_attribution_query

    q = override_attribution_query()
    cols = {c.key for c in q.selected_columns}

    for key in ("teacher_id", "school_id", "school_name", "student_id",
                "rubric_id", "question_id", "criterion_id", "check_id",
                "plan_version"):
        assert key in cols, f"attribution key {key!r} does not resolve: {sorted(cols)}"

    sql = str(q)
    assert "LEFT OUTER JOIN" in sql.upper(), (
        "the schools join must be OUTER — an INNER join silently drops every "
        "override by a teacher who has not set a school")


def test_school_match_is_normalized_exact_never_fuzzy():
    """Create-or-pick matches on a normalized-exact key (CLAUDE.md §7's
    conservative student-match precedent). Fuzzy matching would merge two real
    schools that differ by one character."""
    from app.services.override_attribution import normalize_school_name

    assert normalize_school_name("  מוסינזון  ") == normalize_school_name("מוסינזון")
    assert normalize_school_name("Kfar HaNoar") == normalize_school_name("kfar  hanoar")
    # near-misses must NOT collide
    assert normalize_school_name("מוסינזון") != normalize_school_name("מוסינזון ב")
