-- =============================================================================
-- Migration 012 — PR-1: rubric extraction jobs (async lifecycle)
-- =============================================================================
--
-- WHY THIS IS REQUIRED
-- --------------------
-- Extraction is a 1–8 minute LLM job wired today as a synchronous HTTP request
-- on infra that kills requests at 300s and de-allocates CPU post-response.
-- This table makes extraction a durable, observable, resumable job:
--   * source doc persisted (GCS URI + sha256) → retry without re-upload
--   * result + pipeline warnings/errors/requires_review persisted (previously
--     computed and dropped at the endpoint)
--   * provenance persisted (prompt/pipeline/model/tokens/duration) — closes
--     the extraction-side provenance gap (grading already stamps these)
--   * ADR-3: one active job per (user, source-doc) — the RGC-1 one-leaf
--     precedent applied to jobs; submit is idempotent on conflict.
--
-- Lifecycle: queued → extracting → completed | failed; failed → queued only
-- via the retry endpoint (which also covers stale-extracting rows whose
-- heartbeat lapsed — the reaper-on-read for instances that died mid-job).
-- Staleness is COMPUTED from updated_at, never stored.
--
-- NOTE: rubrics' base DDL is unversioned (predates migration 001); the ALTER
-- below assumes the live base table.
-- =============================================================================

CREATE TABLE public.rubric_extraction_jobs (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    status           VARCHAR(20) NOT NULL DEFAULT 'queued',

    -- source document (durability: retry/re-extract without re-upload)
    source_gcs_uri   TEXT NOT NULL,
    source_filename  VARCHAR(255) NOT NULL,
    source_sha256    CHAR(64) NOT NULL,
    request_params   JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- result payload (ADR-2: lives on the job row, never auto-saved as a rubric)
    result_json      JSONB,
    warnings         JSONB NOT NULL DEFAULT '[]'::jsonb,
    errors           JSONB NOT NULL DEFAULT '[]'::jsonb,
    requires_review  BOOLEAN,

    -- provenance
    prompt_version   VARCHAR(50),
    pipeline_version VARCHAR(50),
    llm_model        VARCHAR(100),
    input_tokens     INTEGER,
    output_tokens    INTEGER,
    retry_count      INTEGER,
    finish_reason    VARCHAR(50),
    duration_ms      INTEGER,
    llm_config       JSONB,

    -- progress / lifecycle
    progress_stage   VARCHAR(30),
    progress_detail  TEXT,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),   -- heartbeat

    CONSTRAINT rubric_extraction_jobs_status_check
        CHECK (status IN ('queued', 'extracting', 'completed', 'failed')),
    CONSTRAINT rubric_extraction_jobs_status_consistency CHECK (
        (status = 'queued'     AND result_json IS NULL AND started_at IS NULL
                               AND finished_at IS NULL)
     OR (status = 'extracting' AND result_json IS NULL AND started_at IS NOT NULL
                               AND finished_at IS NULL)
     OR (status = 'completed'  AND result_json IS NOT NULL AND finished_at IS NOT NULL)
     OR (status = 'failed'     AND error_message IS NOT NULL AND finished_at IS NOT NULL)
    )
);

-- ADR-3: one ACTIVE job per (user, source doc). Submit is idempotent: an
-- IntegrityError here means "return the existing active job (reused:true)".
CREATE UNIQUE INDEX idx_extraction_jobs_one_active_per_source
    ON public.rubric_extraction_jobs (user_id, source_sha256)
    WHERE status IN ('queued', 'extracting');

CREATE INDEX idx_extraction_jobs_user_recent
    ON public.rubric_extraction_jobs (user_id, created_at DESC);

-- Provenance chain: rubric → job → (prompt, model, tokens, source doc)
ALTER TABLE public.rubrics
    ADD COLUMN extraction_job_id UUID
        REFERENCES public.rubric_extraction_jobs(id) ON DELETE SET NULL;

-- Verification queries (informational — do not run as part of migration):
--
--   SELECT conname FROM pg_constraint
--   WHERE conname IN ('rubric_extraction_jobs_status_check',
--                     'rubric_extraction_jobs_status_consistency');
--   -- expect: both rows
--
--   SELECT indexname FROM pg_indexes
--   WHERE tablename = 'rubric_extraction_jobs';
--   -- expect: pkey + idx_extraction_jobs_one_active_per_source
--   --         + idx_extraction_jobs_user_recent
--
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'rubrics' AND column_name = 'extraction_job_id';
--   -- expect: one row
