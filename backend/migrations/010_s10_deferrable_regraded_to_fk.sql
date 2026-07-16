-- =============================================================================
-- Migration 010 — S10: make regraded_to_id FK DEFERRABLE INITIALLY DEFERRED
-- =============================================================================
--
-- WHY THIS IS REQUIRED
-- --------------------
-- S10 adds revision actions (regrade, manual_edit, retry) that extend the
-- graded-test revision chain within the same (transcription_id, rubric_id) pair.
--
-- Two constraints collide on the chain-insert transaction:
--
--   (a) idx_graded_tests_one_leaf_per_chain — partial UNIQUE INDEX on
--       (transcription_id, rubric_id) WHERE regraded_to_id IS NULL.
--       Partial unique indexes in Postgres are NEVER deferrable — they are
--       checked after every statement/flush.
--
--   (b) graded_tests_regraded_to_id_fkey — the FK from regraded_to_id to
--       graded_tests.id.  Currently non-deferrable (migration 008 inline REFERENCES).
--
-- Neither naive insert order works with both constraints immediate:
--   • INSERT R2 first → R1 and R2 both have regraded_to_id IS NULL at flush
--     → partial index rejects two leaves.
--   • UPDATE R1 first (R1.regraded_to_id = R2.id) → R2 doesn't exist yet
--     → FK violation.
--
-- Making (b) deferrable unlocks the correct ordering:
--   1. R1.regraded_to_id = r2_id  [flush]  → R1 exits partial index (0 leaves);
--                                             FK deferred → not checked yet
--   2. INSERT R2 (id=r2_id)       [flush]  → R2 sole leaf; R2→R1 FK immediate OK
--   3. COMMIT                              → deferred R1→R2 FK resolved; R2 exists
--
-- regraded_from_id stays IMMEDIATELY checked: R2→R1 is always satisfied because
-- R1 exists at the time R2 is inserted.
--
-- CONSTRAINT NAME
-- ---------------
-- Migration 008 defined the FK inline without an explicit name:
--   regraded_to_id UUID REFERENCES public.graded_tests(id) ON DELETE SET NULL
-- Postgres auto-generates the name: graded_tests_regraded_to_id_fkey
--
-- Verify before running:
--   SELECT constraint_name
--   FROM information_schema.table_constraints
--   WHERE table_name = 'graded_tests'
--     AND constraint_type = 'FOREIGN KEY';
--
-- If the name differs from graded_tests_regraded_to_id_fkey, update the
-- DROP CONSTRAINT line below accordingly.
-- =============================================================================

ALTER TABLE public.graded_tests
    DROP CONSTRAINT graded_tests_regraded_to_id_fkey,
    ADD CONSTRAINT graded_tests_regraded_to_id_fkey
        FOREIGN KEY (regraded_to_id)
        REFERENCES public.graded_tests(id)
        ON DELETE SET NULL
        DEFERRABLE INITIALLY DEFERRED;

-- Verification query (informational — do not run as part of migration):
--
--   SELECT constraint_name, is_deferrable, initially_deferred
--   FROM information_schema.table_constraints
--   WHERE table_name = 'graded_tests'
--     AND constraint_name = 'graded_tests_regraded_to_id_fkey';
--
-- Expected: is_deferrable = YES, initially_deferred = YES
