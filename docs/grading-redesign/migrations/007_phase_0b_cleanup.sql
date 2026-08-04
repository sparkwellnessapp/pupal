-- =============================================================================
-- Migration 007 — Phase 0b cleanup teardown
-- =============================================================================
--
-- Purpose: Drop dead/phantom infrastructure as enumerated in
--          phase_0b_deletion_manifest.md §1.
--
-- Scope:
--   * Drops 3 tables: raw_graded_tests, graded_test_pdfs, grading_sessions
--   * Drops 3 columns from graded_tests: raw_graded_test_id, graded_json,
--     student_answers_json
--   * Drops 3 columns from grading_batches: total_sessions, completed_sessions,
--     failed_sessions
--   * Drops 2 columns from rubrics: legacy_rubric_json_backup, rubric_json
--
-- What this migration does NOT do:
--   * Does NOT create new tables or columns (those land in migration 008 / S1)
--   * Does NOT backfill or preserve data (pre-launch — no real users)
--   * Does NOT modify users, subject_matters, user_subject_matters,
--     rubric_shares, rubric_share_history, rubric_share_tokens, or the
--     remaining columns on rubrics / graded_tests / grading_batches
--
-- Ordering constraint:
--   This migration is designed to run AFTER the S0 application-code cleanup
--   PR is merged (the PR deletes every endpoint/service that reads from the
--   dropped columns and tables). Running it before S0 merges leaves live
--   endpoints reading from non-existent columns at request time — they will
--   return 500s until S0 lands.
--
--   Pre-launch this is acceptable. If running in parallel with S0, expect a
--   broken state for legacy endpoints (which are being deleted anyway).
--
-- Idempotency: every DROP uses IF EXISTS. Re-running is a no-op.
--
-- Atomicity: wrapped in a transaction. If any statement fails, none apply.
--
-- Rollback: there is no rollback. Pre-launch destruction is intentional. If
--          the migration fails partway, the transaction rolls back; if it
--          succeeds, the data is gone. The new shape lands in migration 008.
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. Drop dependent tables (children before parents where FKs exist)
-- -----------------------------------------------------------------------------

-- graded_test_pdfs depends on graded_tests and rubrics via FKs.
-- CASCADE removes the FK constraints automatically. Never-written phantom.
DROP TABLE IF EXISTS public.graded_test_pdfs CASCADE;

-- grading_sessions depends on users, rubrics, grading_batches via FKs.
-- The deprecated LangGraph TestGraderAgent's state-machine persistence.
-- Replaced by direct draft_json writes on graded_tests (lands in migration 008).
DROP TABLE IF EXISTS public.grading_sessions CASCADE;

-- raw_graded_tests is referenced by graded_tests.raw_graded_test_id.
-- CASCADE drops both the FK constraint on graded_tests and any other
-- dependencies. Phantom — zero writers anywhere in the codebase.
DROP TABLE IF EXISTS public.raw_graded_tests CASCADE;

-- -----------------------------------------------------------------------------
-- 2. Drop dead columns from surviving tables
-- -----------------------------------------------------------------------------

-- graded_tests: three columns removed.
-- * raw_graded_test_id — FK to dropped table (the FK itself is already gone
--   from the CASCADE above, but the column persists until explicitly dropped).
-- * graded_json — replaced by draft_json + contract_json (migration 008).
-- * student_answers_json — replaced by transcription_id FK to the new
--   transcriptions table (migration 008).
ALTER TABLE public.graded_tests
    DROP COLUMN IF EXISTS raw_graded_test_id,
    DROP COLUMN IF EXISTS graded_json,
    DROP COLUMN IF EXISTS student_answers_json;

-- grading_batches: three count columns removed. Counts are derived from
-- graded_tests GROUP BY status. Storing them was a maintenance burden where
-- the count and the underlying state could disagree.
ALTER TABLE public.grading_batches
    DROP COLUMN IF EXISTS total_sessions,
    DROP COLUMN IF EXISTS completed_sessions,
    DROP COLUMN IF EXISTS failed_sessions;

-- rubrics: two dead columns removed.
-- * legacy_rubric_json_backup — declared as rollback safety; never written,
--   never read.
-- * rubric_json — pre-ontology legacy column; superseded by draft_json and
--   contract_json which already exist (migrations 004, 006).
ALTER TABLE public.rubrics
    DROP COLUMN IF EXISTS legacy_rubric_json_backup,
    DROP COLUMN IF EXISTS rubric_json;

-- -----------------------------------------------------------------------------
-- 3. Verification queries (informational — do not run as part of migration)
-- -----------------------------------------------------------------------------
--
-- After running this migration, the following queries should all succeed and
-- return zero rows / "table does not exist":
--
--   SELECT to_regclass('public.raw_graded_tests');     -- expect NULL
--   SELECT to_regclass('public.graded_test_pdfs');     -- expect NULL
--   SELECT to_regclass('public.grading_sessions');     -- expect NULL
--
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'graded_tests'
--     AND column_name IN ('raw_graded_test_id', 'graded_json',
--                         'student_answers_json');     -- expect 0 rows
--
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'grading_batches'
--     AND column_name IN ('total_sessions', 'completed_sessions',
--                         'failed_sessions');          -- expect 0 rows
--
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'rubrics'
--     AND column_name IN ('legacy_rubric_json_backup', 'rubric_json');
--                                                     -- expect 0 rows

COMMIT;
