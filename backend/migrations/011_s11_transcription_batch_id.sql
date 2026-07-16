-- =============================================================================
-- Migration 011 — S11: batch support for transcriptions + test_count on batches
-- =============================================================================
--
-- WHY BOTH CHANGES ARE REQUIRED
-- ------------------------------
-- The S11 batch-grading design tracks two distinct batch associations:
--
-- (a) transcriptions.batch_id — needed so transcription roll-up counts
--     (transcribing / transcribed / approved) can be derived per batch during
--     the transcription-review phase, BEFORE any graded_tests rows exist.
--     Without this column, there is no way to associate transcriptions with
--     the batch that triggered them.
--
-- (b) grading_batches.test_count — the number of PDFs submitted at batch
--     creation time. Used to compute the "transcribing" count (in-flight
--     background tasks) as: max(0, test_count - COUNT(transcriptions)).
--     Without this, there is no way to show in-flight progress before
--     transcription rows appear.
--
-- NOTE: graded_tests.batch_id already exists (migration 008). Only
--       transcriptions needs a new column.
-- =============================================================================

-- (a) Add batch_id FK to transcriptions
ALTER TABLE public.transcriptions
    ADD COLUMN batch_id UUID
        REFERENCES public.grading_batches(id)
        ON DELETE SET NULL;

-- Index for roll-up queries: "all transcriptions for this batch"
CREATE INDEX idx_transcriptions_batch
    ON public.transcriptions (batch_id)
    WHERE batch_id IS NOT NULL;

-- (b) Add test_count to grading_batches (number of PDFs submitted at creation)
ALTER TABLE public.grading_batches
    ADD COLUMN test_count INTEGER NOT NULL DEFAULT 0;

-- Verification queries (informational — do not run as part of migration):
--
--   SELECT column_name, data_type, is_nullable
--   FROM information_schema.columns
--   WHERE table_name = 'transcriptions'
--     AND column_name = 'batch_id';
--   -- expect: uuid, YES
--
--   SELECT column_name, data_type
--   FROM information_schema.columns
--   WHERE table_name = 'grading_batches'
--     AND column_name = 'test_count';
--   -- expect: integer
