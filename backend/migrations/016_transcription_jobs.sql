-- =============================================================================
-- Migration 016 — Cloud Tasks migration: transcription_jobs (batch fan-out)
-- =============================================================================
--
-- WHY THIS IS REQUIRED
-- --------------------
-- The batch transcription fan-out ran on FastAPI BackgroundTasks: PDF bytes
-- existed only in request memory, the transcriptions row appeared only AFTER
-- success, and prod Cloud Run (CPU throttled post-response, min-instances 0)
-- could kill the work silently at any moment. Everything downstream (the
-- migration-015 failure ledger, the Δ15 residue heuristic) was inference over
-- ABSENCE. This table makes each batch document a durable job:
--   * ONE row per PDF, created in the SAME COMMIT as the batch —
--     Σ jobs == grading_batches.test_count, always, so "in flight" is a fact,
--     never an inference; the phantom-item class dies structurally.
--   * source PDF persisted to GCS at intake → per-document retry WITHOUT
--     re-upload (the extraction-jobs precedent).
--   * execution = authenticated HTTP POST /internal/transcription-jobs/{id}/run
--     (Cloud Tasks; CPU guaranteed inside the request), CAS-claimed
--     (queued→running), heartbeat-alive (updated_at), LIV-1-reaped.
--
-- Lifecycle: queued → running → completed | failed; failed/expired → queued
-- only via the per-document retry endpoint. Queue runs maxAttempts=3
-- (owner-ratified deviation from the extraction ADR: the CAS makes duplicate
-- delivery a no-op; redelivery heals dispatch-level failures under batch
-- backlog, where a short queued-TTL cannot work). Staleness is COMPUTED
-- (LIV-1 dual deadlines), never stored.
--
-- transcription_id links the completed job to its transcriptions row (written
-- in the same commit as that INSERT). It is intentionally NOT part of the
-- status CHECK: the FK is ON DELETE SET NULL, and demanding NOT NULL for
-- 'completed' would make any later transcription deletion violate the CHECK
-- mid-cascade.
--
-- Idempotent: re-running this whole file is always the answer.
-- =============================================================================

CREATE TABLE IF NOT EXISTS public.transcription_jobs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                 UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    batch_id                UUID NOT NULL REFERENCES public.grading_batches(id) ON DELETE CASCADE,
    rubric_id               UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,
    status                  VARCHAR(20) NOT NULL DEFAULT 'queued',

    -- source document (durability: per-doc retry without re-upload)
    source_gcs_object_path  TEXT NOT NULL,
    source_filename         VARCHAR(500),
    doc_priority            INTEGER NOT NULL DEFAULT 0,

    -- outcome
    transcription_id        UUID REFERENCES public.transcriptions(id) ON DELETE SET NULL,
    error_message           TEXT,
    net_verdict             VARCHAR(30),
    attempt_count           INTEGER NOT NULL DEFAULT 0,

    -- lifecycle clocks (LIV-1: queued runs on created_at, running on updated_at)
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at              TIMESTAMPTZ,
    finished_at             TIMESTAMPTZ,
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT transcription_jobs_status_check
        CHECK (status IN ('queued', 'running', 'completed', 'failed')),
    -- Which fields each status REQUIRES/FORBIDS — mirror in write paths,
    -- don't fight it.
    CONSTRAINT transcription_jobs_status_consistency CHECK (
        (status IN ('queued', 'running') AND finished_at IS NULL AND error_message IS NULL)
        OR (status = 'completed' AND finished_at IS NOT NULL AND error_message IS NULL)
        OR (status = 'failed'    AND finished_at IS NOT NULL AND error_message IS NOT NULL)
    )
);

-- Rollup + reap reads are batch-scoped: (batch_id, status) serves both.
CREATE INDEX IF NOT EXISTS idx_transcription_jobs_batch_status
    ON public.transcription_jobs (batch_id, status);

-- Commit token — LAST statement, per the migration-013 convention.
INSERT INTO public.schema_migrations (version, note)
VALUES ('016', 'transcription_jobs — durable per-document batch transcription (Cloud Tasks migration)')
ON CONFLICT (version) DO NOTHING;
