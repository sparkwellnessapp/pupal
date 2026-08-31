-- 020 — returned-exam settings, per batch (PR-G9)
--
-- Two teacher decisions that belong to the BATCH, not to each test: whether the
-- appendix shows the criterion breakdown, and where the stamp sits by default.
-- Both feed the render cache key, so changing either invalidates every cached
-- PDF in the batch — the endpoint reports that count rather than silently
-- serving a page rendered under the old setting.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

ALTER TABLE public.grading_batches
    ADD COLUMN IF NOT EXISTS appendix_include_criteria BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE public.grading_batches
    ADD COLUMN IF NOT EXISTS stamp_position_default JSONB;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('020', 'grading_batches.appendix_include_criteria + stamp_position_default (PR-G9)')
ON CONFLICT DO NOTHING;
