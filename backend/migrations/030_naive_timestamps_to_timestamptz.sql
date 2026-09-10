-- 030 — the last ten NAIVE timestamp columns become TIMESTAMPTZ.
--
-- WHY. `grading_batches.created_at` is declared `DateTime(timezone=True)` on the
-- ORM and was `timestamp without time zone` in the database. The database wins,
-- so the driver handed back a NAIVE datetime and `.isoformat()` serialised it
-- with NO OFFSET:
--
--     "2026-09-09T20:10:32.431479"      <- no Z, no +00:00
--
-- ECMAScript parses a date-time string without an offset as LOCAL time. A
-- teacher in Israel (UTC+3 on IDT) therefore read a UTC instant as if it were
-- her own wall clock, and every duration computed from it was wrong by exactly
-- her offset. Observed live: the batch-completion hero read
-- «מהעלאה ועד אישור אחרון — 181 דקות» for a batch created 4 MINUTES earlier —
-- 180 minutes of phantom offset plus the one real minute.
--
-- This is the migration-022 lesson, arriving from the other direction: there the
-- ORM was naive and the column was TIMESTAMPTZ; here the ORM is aware and the
-- column was naive. Either way the two disagreed and the wire carried the lie.
--
-- WHY `AT TIME ZONE 'UTC'` IS THE CORRECT CONVERSION, and not a guess: every
-- writer of these columns stored UTC wall-clock — `datetime.utcnow()` on the
-- legacy tables, `datetime.now(timezone.utc)` on `grading_batches`. So the naive
-- values ARE UTC with the label rubbed off, and this puts the label back. It
-- does NOT shift any instant.
--
-- The three other tables (`grading_sessions`, `graded_test_pdfs`,
-- `raw_graded_tests`) have NO ORM model and no code reference — verified. They
-- are converted anyway so the invariant "every timestamp in this database is
-- TIMESTAMPTZ" becomes true rather than nearly true, which is the only form of
-- it worth writing down.
--
-- IDEMPOTENT, AND THE GUARD IS LOAD-BEARING. `ALTER ... TYPE timestamptz USING
-- col AT TIME ZONE 'UTC'` is NOT safe to re-run: applied to a column that is
-- ALREADY timestamptz, `AT TIME ZONE 'UTC'` converts the other way — it strips
-- the zone and yields a naive timestamp. A blind re-run would therefore UNDO
-- this migration. The DO block converts only columns still sitting at
-- `timestamp without time zone`, so re-running the whole file is a no-op.

DO $$
DECLARE
    target RECORD;
BEGIN
    FOR target IN
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        WHERE c.table_schema = 'public'
          AND c.data_type = 'timestamp without time zone'
          AND (c.table_name, c.column_name) IN (
              ('graded_test_pdfs', 'created_at'),
              ('grading_batches',  'created_at'),
              ('grading_batches',  'updated_at'),
              ('grading_batches',  'started_at'),
              ('grading_batches',  'completed_at'),
              ('grading_sessions', 'created_at'),
              ('grading_sessions', 'updated_at'),
              ('grading_sessions', 'started_at'),
              ('grading_sessions', 'completed_at'),
              ('raw_graded_tests', 'created_at')
          )
    LOOP
        EXECUTE format(
            'ALTER TABLE public.%I ALTER COLUMN %I TYPE timestamptz '
            'USING %I AT TIME ZONE ''UTC''',
            target.table_name, target.column_name, target.column_name
        );
        RAISE NOTICE '030: %.% -> timestamptz', target.table_name, target.column_name;
    END LOOP;
END $$;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('030', 'naive timestamp columns -> timestamptz (batch/session/pdf/raw): the wire was serialising UTC instants with no offset, so browsers parsed them as local time')
ON CONFLICT DO NOTHING;
