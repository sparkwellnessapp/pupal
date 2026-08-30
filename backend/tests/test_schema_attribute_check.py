"""
Constraint-ATTRIBUTE schema check (P1 follow-up, owner-sanctioned 2026-08-17).

The version ledger proves a migration RAN once — not that its DDL survived.
Discovered live: `graded_tests_regraded_to_id_fkey` was silently non-deferrable
on the dev DB while the ledger listed 010, breaking the whole revision feature.
`verify_schema_head` now also verifies declared constraint attributes so this
half-applied class can't hide behind a green version check again.
"""
import pytest

from app.database import (
    EXPECTED_CONSTRAINT_ATTRIBUTES,
    EXPECTED_PARTIAL_INDEXES,
    SCHEMA_CHECK_COVERAGE,
    _constraint_attribute_problems,
    _partial_index_problems,
)


# ---------------------------------------------------------------------------
# Pure comparator — zero mocks
# ---------------------------------------------------------------------------

_SPEC = {"graded_tests_regraded_to_id_fkey": (True, True, "010")}


def test_matching_attributes_produce_no_problems():
    rows = [("graded_tests_regraded_to_id_fkey", True, True)]
    assert _constraint_attribute_problems(rows, _SPEC) == []


def test_wrong_attributes_name_the_owning_migration():
    rows = [("graded_tests_regraded_to_id_fkey", False, False)]
    problems = _constraint_attribute_problems(rows, _SPEC)
    assert len(problems) == 1
    assert "graded_tests_regraded_to_id_fkey" in problems[0]
    assert "010" in problems[0]
    assert "half-applied" in problems[0]


def test_missing_constraint_is_a_problem():
    problems = _constraint_attribute_problems([], _SPEC)
    assert len(problems) == 1
    assert "MISSING" in problems[0]
    assert "010" in problems[0]


def test_extra_db_rows_are_ignored():
    rows = [
        ("graded_tests_regraded_to_id_fkey", True, True),
        ("some_other_constraint", False, False),
    ]
    assert _constraint_attribute_problems(rows, _SPEC) == []


def test_default_spec_covers_the_010_constraint():
    assert "graded_tests_regraded_to_id_fkey" in EXPECTED_CONSTRAINT_ATTRIBUTES
    deferrable, deferred, migration = (
        EXPECTED_CONSTRAINT_ATTRIBUTES["graded_tests_regraded_to_id_fkey"]
    )
    assert (deferrable, deferred, migration) == (True, True, "010")


# ---------------------------------------------------------------------------
# Integration — the live DB (repaired 2026-08-17) must pass the check
# ---------------------------------------------------------------------------

@pytest.mark.integration
def test_live_db_constraint_attributes_pass():
    import sqlalchemy
    from app.config import settings

    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    engine = sqlalchemy.create_engine(sync_url)
    with engine.connect() as conn:
        rows = [
            (r[0], bool(r[1]), bool(r[2]))
            for r in conn.execute(sqlalchemy.text(
                "SELECT conname, condeferrable, condeferred FROM pg_constraint "
                "WHERE conname = 'graded_tests_regraded_to_id_fkey'"
            )).fetchall()
        ]
    engine.dispose()
    assert _constraint_attribute_problems(rows) == []


# ---------------------------------------------------------------------------
# Partial-index comparator (closeout/A2) — the second reader. Partial unique
# indexes live in pg_index, so the constraint reader above is STRUCTURALLY
# blind to them; 017's index is B9's idempotency guarantee.
# ---------------------------------------------------------------------------

_IDX_SPEC = {
    "idx_transcription_jobs_batch_client_file": (
        "where (client_file_id is not null)", "017",
    ),
}
_REAL_DEF = (
    "CREATE UNIQUE INDEX idx_transcription_jobs_batch_client_file ON "
    "public.transcription_jobs USING btree (batch_id, client_file_id) "
    "WHERE (client_file_id IS NOT NULL)"
)


def test_present_index_with_its_predicate_is_clean():
    assert _partial_index_problems([
        ("idx_transcription_jobs_batch_client_file", _REAL_DEF)
    ], _IDX_SPEC) == []


def test_missing_index_names_the_owning_migration():
    problems = _partial_index_problems([], _IDX_SPEC)
    assert len(problems) == 1
    assert "MISSING" in problems[0]
    assert "017" in problems[0]


def test_index_recreated_WITHOUT_its_predicate_is_caught():
    """The dangerous shape: the name is present, so a presence-only check
    passes, while the uniqueness guarantee silently covers every row —
    including the pre-017 NULLs it was written to exclude."""
    stripped = _REAL_DEF.replace(" WHERE (client_file_id IS NOT NULL)", "")
    problems = _partial_index_problems([
        ("idx_transcription_jobs_batch_client_file", stripped)
    ], _IDX_SPEC)
    assert len(problems) == 1
    assert "lacks" in problems[0]
    assert "017" in problems[0]


def test_predicate_match_is_case_insensitive():
    """pg_indexes renders SQL in its own case; the expectation table is
    hand-written. A case mismatch must not read as a lost predicate."""
    assert _partial_index_problems([
        ("idx_transcription_jobs_batch_client_file", _REAL_DEF.upper())
    ], _IDX_SPEC) == []


def test_every_expected_index_name_is_nonempty_and_unique():
    names = list(EXPECTED_PARTIAL_INDEXES)
    assert names, "the index expectation table must not be empty"
    assert len(names) == len(set(names))
    for name, (fragment, migration) in EXPECTED_PARTIAL_INDEXES.items():
        assert name.strip() and fragment.strip() and migration.strip()


def test_coverage_is_stated_not_implied():
    """Owner ruling (closeout/A2): the checker's blind spots are documented
    rather than discovered. If a reader is added, this string changes with it."""
    assert "NOT covered" in SCHEMA_CHECK_COVERAGE
    for uncovered in ("CHECK expressions", "triggers", "RLS"):
        assert uncovered in SCHEMA_CHECK_COVERAGE
