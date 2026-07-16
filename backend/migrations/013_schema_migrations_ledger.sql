-- =============================================================================
-- Migration 013 — schema_migrations ledger (the DDL arbiter)
-- =============================================================================
--
-- WHY THIS IS REQUIRED
-- --------------------
-- This schema had TWO DDL sources and no arbiter between them:
--
--   (1) SQL migrations in this directory  — the intended canon
--   (2) Base.metadata.create_all() at app startup (database.py init_db)
--
-- Nothing recorded which migrations had actually been applied, so "is the live
-- schema what the migrations say?" was answerable only by forensic probing.
-- It fired twice, for real, during the PR-1 deploy:
--
--   * Migration 011 was PARTIALLY applied. The file is two independent
--     statements — (a) transcriptions.batch_id, (b) grading_batches.test_count.
--     (a) landed; (b) did not. Production batch creation was broken and nobody
--     knew until a test tripped over it, weeks later.
--   * A NEW ORM model (rubric_extraction_jobs) got a BARE table auto-created by
--     create_all — no CHECKs, no partial unique index — because the app booted
--     before migration 012 was applied.
--
-- This migration adds source (1)'s ledger, and PR-1's follow-up disables source
-- (2) outside development. One canon, one arbiter.
--
-- THE COMMIT-TOKEN CONVENTION (this is the part that actually catches 011)
-- -----------------------------------------------------------------------
-- A ledger that merely records "011 was run" would NOT have caught 011: whoever
-- ran statement (a) and stopped would have marked it applied anyway. So the
-- convention is:
--
--   *** EVERY migration file ends with its own INSERT INTO schema_migrations. ***
--
-- The version row is a COMMIT TOKEN, not a label. It is the LAST statement, so
-- it only lands if every statement before it landed. Partial application ⇒ no
-- token ⇒ the head stays behind ⇒ the boot-time check in database.py fires a
-- loud ERROR on the very first boot. This holds even when a file is run
-- statement-by-statement in a SQL console with no enclosing transaction —
-- which is exactly how 011 broke.
--
-- BACKFILL HONESTY
-- ----------------
-- Rows 001–012 are inserted retroactively. They are not an assumption: each
-- one's DDL artifacts were probed against this live database on 2026-07-13 and
-- confirmed present (and 007's DROPs confirmed absent). The ledger's forward
-- guarantee begins at 013; the backfill is a verified snapshot, not a promise.
-- =============================================================================

BEGIN;

CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version    VARCHAR(10) PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    note       TEXT
);

COMMENT ON TABLE public.schema_migrations IS
    'Applied-migration ledger. Each migration INSERTs its version as its LAST '
    'statement, so the row is a commit token: partial application leaves no row. '
    'Checked at boot against EXPECTED_MIGRATIONS in app/database.py.';

-- Backfill 001–012 — verified present in this database by direct DDL probe
-- (2026-07-13), not assumed. See "BACKFILL HONESTY" above.
INSERT INTO public.schema_migrations (version, note) VALUES
    ('001', 'backfilled 2026-07-13; verified: users, raw_rubrics present'),
    ('002', 'backfilled 2026-07-13; data-only (viviana user), no DDL artifact to probe'),
    ('003', 'backfilled 2026-07-13; verified: rubric_shares present'),
    ('004', 'backfilled 2026-07-13; verified: rubrics.draft_json, contract_json present'),
    ('005', 'backfilled 2026-07-13; superseded by 007 (grading_sessions dropped) — verified absent'),
    ('006', 'backfilled 2026-07-13; superseded by 007 (rubric_json dropped) — verified absent'),
    ('007', 'backfilled 2026-07-13; verified: grading_sessions + raw_graded_tests absent'),
    ('008', 'backfilled 2026-07-13; verified: transcriptions, students, classes, graded_tests present'),
    ('009', 'backfilled 2026-07-13; verified: graded_tests.total_cost_usd, prompt_version present'),
    ('010', 'backfilled 2026-07-13; verified: graded_tests.regraded_from_id present'),
    ('011', 'backfilled 2026-07-13; WAS PARTIALLY APPLIED — (b) grading_batches.test_count '
            'was missing in prod and completed idempotently on 2026-07-12. Both halves verified present.'),
    ('012', 'backfilled 2026-07-13; verified: rubric_extraction_jobs + both CHECKs + partial '
            'unique index + rubrics.extraction_job_id present (a bare create_all table was '
            'dropped and replaced by the real migration during the PR-1 deploy)')
ON CONFLICT (version) DO NOTHING;

-- This migration's own commit token — LAST statement, per the convention above.
INSERT INTO public.schema_migrations (version, note)
VALUES ('013', 'schema_migrations ledger + commit-token convention')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification (informational — do not run as part of migration):
--
--   SELECT version, applied_at FROM public.schema_migrations ORDER BY version;
--   -- expect: 001..013, thirteen rows
