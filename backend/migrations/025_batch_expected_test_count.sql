-- 025: grading_batches.expected_test_count — the upload-stage in-flight fact
--      (UPLOAD_LATENCY_PLAN.md Stage A; owner rulings R9 + Defect D)
--
-- WHY. A batch cannot say "still uploading". B9 made intake create-then-append:
-- the batch row is created EMPTY and each landed file inserts its own job, so
-- the rollup's denominator is COUNT(jobs) — the files that ARRIVED. Mid-upload a
-- ten-file batch with one file in has a total of one, and if that one is
-- transcribed and approved, `_derive_batch_status` returns "completed" while
-- nine files are still climbing the wire.
--
-- This is latent today only because the teacher never sees a batch mid-upload —
-- the redirect waits for the last byte. Stage B removes that wait and exposes it
-- immediately, and it fails in the §3.5a shape that matters most: it does not
-- blur the number, it KEEPS COMPUTING and returns a confident wrong one.
--
-- The fix is the doctrine the jobs table already uses one stage downstream:
-- "in flight is a fact, never an inference over absence". The number of files
-- she selected is a fact known at create time. Record it; do not infer it.
--
-- NULLABLE, and NULL is not a defect — it is the LEGACY POPULATION:
--   * every batch created before this ships, and
--   * every batch created by a client that predates the frontend half
--     (the backend deploys before Vercel does).
-- For those rows the rollup arithmetic is bypassed entirely and the response is
-- byte-identical to today's. A NOT NULL DEFAULT 0 would have been worse than
-- useless: it would claim every historical batch declared zero files, which is
-- the same confident lie in the other direction.
--
-- NOT a second home for COUNT(jobs) (CLAUDE.md §0.4): this column is what she
-- DECLARED, the job rows are what ARRIVED, and the whole point is the gap
-- between them. `uploading = max(0, expected − COUNT(jobs))` is derived at read
-- time and never stored, exactly like `transcribing`.
--
-- The server NEVER lowers this value (R9). A file that will never land is
-- re-declared DOWN by the client (PATCH, refused below COUNT(jobs)), or — when
-- she is gone and nothing re-declares — reported after a TTL as `not_received`,
-- a read-time fact that writes nothing.
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

ALTER TABLE public.grading_batches
    ADD COLUMN IF NOT EXISTS expected_test_count INTEGER;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('025', 'grading_batches.expected_test_count — upload-stage in-flight fact (Stage A / R9)')
ON CONFLICT DO NOTHING;
