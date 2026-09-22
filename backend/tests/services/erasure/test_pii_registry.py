"""
The PII registry — census row 2 as code (PR §16.1, census addition G).

Every column in `public` that the census patterns catch is CLASSIFIED in
`app.services.erasure.PII_REGISTRY`, and nothing in the registry names a column
that no longer exists. A new column matching a pattern fails this test until
someone decides what the purge does with it — that decision is the point.

Patterns: %name% (G: the one that catches `students.full_name`, literally
her name), %student_name%, %filename%, %gcs%, %object_path%, %_key, and every
jsonb column.

RED until the registry exists.
"""
from __future__ import annotations

from sqlalchemy import text

from tests.services.erasure.seed import session

CAUGHT = r"""
    SELECT c.table_name, c.column_name
      FROM information_schema.columns c
      JOIN information_schema.tables t
        ON t.table_schema = c.table_schema AND t.table_name = c.table_name
     WHERE c.table_schema = 'public' AND t.table_type = 'BASE TABLE'
       AND (c.column_name ILIKE '%name%'
            OR c.column_name ILIKE '%filename%'
            OR c.column_name ILIKE '%student_name%'
            OR c.column_name ILIKE '%gcs%'
            OR c.column_name ILIKE '%object_path%'
            OR c.column_name ILIKE '%\_key'
            OR c.data_type = 'jsonb')
"""


async def _caught() -> set[tuple[str, str]]:
    async with session() as db:
        return {(r[0], r[1]) for r in (await db.execute(text(CAUGHT))).all()}


async def test_every_caught_column_is_classified_and_every_entry_still_exists():
    from app.services.erasure import PII_REGISTRY

    caught, registered = await _caught(), set(PII_REGISTRY)
    assert sorted(caught - registered) == [], "unclassified — decide what the purge does with each"
    assert sorted(registered - caught) == [], "the registry names columns that no longer match"


def test_her_name_is_deleted_with_her_row():
    from app.services.erasure import PII_REGISTRY, Disposition

    assert PII_REGISTRY[("students", "full_name")] is Disposition.DELETED_WITH_ROW


def test_every_deleted_with_row_column_lives_in_a_table_the_plan_deletes_from():
    from app.services.erasure import COVERED_TABLES, PII_REGISTRY, Disposition

    stray = sorted(k for k, d in PII_REGISTRY.items()
                   if d in (Disposition.DELETED_WITH_ROW, Disposition.OBJECT_POINTER)
                   and k[0] not in COVERED_TABLES)
    assert stray == []


def test_the_only_in_place_scrub_is_the_batch_failure_ledger():
    """The batch is the teacher's and survives; only its dormant 015 ledger is
    scrubbed (census row 2; 0 entries in production)."""
    from app.services.erasure import PII_REGISTRY, Disposition

    assert sorted(k for k, d in PII_REGISTRY.items() if d is Disposition.SCRUBBED_IN_PLACE) == \
        [("grading_batches", "transcription_failures")]


def test_the_legacy_tables_are_asserted_empty_never_purged():
    """OD-B1, ruled: the purge does not reference them; verify_purged asserts
    they stay empty."""
    from app.services.erasure import PII_REGISTRY, Disposition

    legacy = {t for (t, _), d in PII_REGISTRY.items() if d is Disposition.LEGACY_ASSERTED_EMPTY}
    assert legacy == {"grading_sessions", "raw_graded_tests"}
