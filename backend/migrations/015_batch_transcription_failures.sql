-- ============================================================================
-- 015 — grading_batches.transcription_failures: the durable failure ledger
--
-- A batch document whose transcription failed previously left NO durable
-- record — the fan-out's containment logged and swallowed the exception, and
-- the rollup inferred "in flight" from test_count − transcription_rows.
-- Absence cannot distinguish in-flight from dead, so the dashboard reported
-- "N מבחנים עדיין בתהליך תמלול..." forever and the client polled forever
-- (observed 2026-08-12, batch 60ec5bf2: a COMPLETED pipeline lost to a GCS
-- upload stall left a phantom forever-transcribing item).
--
-- The column is a JSONB array of failure records appended ATOMICALLY
-- (jsonb || jsonb server-side, never read-modify-write) by the fan-out's
-- containment handler:
--   [{"filename": str|null, "error": str, "at": iso8601,
--     "net_verdict": str|null}, ...]
-- The rollup then computes: transcribing = test_count − rows − failures.
--
-- Idempotent: re-running this whole file is always the answer.
-- ============================================================================

ALTER TABLE public.grading_batches
    ADD COLUMN IF NOT EXISTS transcription_failures JSONB NOT NULL DEFAULT '[]'::jsonb;

-- Commit token — LAST statement, per the migration-013 convention.
INSERT INTO public.schema_migrations (version, note)
VALUES ('015', 'grading_batches.transcription_failures — durable per-document failure ledger')
ON CONFLICT (version) DO NOTHING;
