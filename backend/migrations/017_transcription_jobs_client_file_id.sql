-- 017: transcription_jobs.client_file_id — append idempotency (B9, batch-redesign spec v2)
--
-- Intake v2 sends ONE file per request (the legacy every-PDF-in-one-multipart
-- create hit Cloud Run's 32MB request ceiling at ~5 scans). A network-ambiguous
-- append retry must return the EXISTING job, never duplicate a test — so the
-- client stamps every file with a generated UUID and the DB enforces
-- (batch_id, client_file_id) uniqueness. Composite because the same
-- client_file_id may legitimately recur across DIFFERENT batches; partial so
-- pre-017 rows (NULL) never collide.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

ALTER TABLE public.transcription_jobs
    ADD COLUMN IF NOT EXISTS client_file_id UUID;

CREATE UNIQUE INDEX IF NOT EXISTS idx_transcription_jobs_batch_client_file
    ON public.transcription_jobs (batch_id, client_file_id)
    WHERE client_file_id IS NOT NULL;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('017', 'transcription_jobs.client_file_id + (batch_id, client_file_id) partial unique index — B9 append idempotency')
ON CONFLICT DO NOTHING;
