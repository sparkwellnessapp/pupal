-- 036 — in-house scanning: the capture domain (PR_in_house_scanning.md §4–§5,
--       as amended by the Step 0 rulings of 2026-10-23).
--
-- WHAT. A teacher (or her students, via one link per batch) photographs exam
-- pages; Vivi flattens them and assembles ONE PDF per student. The PDF is the
-- boundary (OD-S9): from the moment a version is saved it is an ordinary
-- `transcription_jobs` row, and everything downstream is unchanged.
--
--   capture_links        one per batch (R6). The token is never stored: it is
--                        HMAC(secret, link id, generation) (OD-4), recomputed
--                        to re-show the QR; only sha256(token) is kept, for
--                        lookup. Rotation bumps `token_generation`.
--                        NO class_id column: the link's class IS the batch's
--                        (`grading_batches.class_id`, written only at batch
--                        create, or by link create when the batch had none).
--   capture_handoffs     the teacher's desktop→phone handoff (D2, OD-5): a
--                        one-time token exchanged for a batch-scoped session.
--                        Opaque random tokens, sha256 at rest (auth_nonces).
--   capture_submissions  the DRAFT: one student's pages + student assignment.
--   capture_pages        the draft's pages (corners, rotation, order).
--   capture_versions     the CONTRACT: a frozen snapshot of the ordered pages
--                        taken at save (SCN-2). There is NO status machine
--                        here (OD-1): compiling is step 0 of the transcription
--                        job the save creates, so the job IS the version's
--                        lifecycle (queued/running/completed/failed, LIV-1
--                        liveness, the per-document retry).
--   transcription_jobs   + capture_version_id (the ONE link from a version to
--                        its job — SCN-4: a version yields one job, the job's
--                        object path is deterministic, so compiling twice
--                        writes the same object) and + withdrawn_at (OD-2:
--                        set in the same transaction that supersedes or
--                        discards; every batch read filters on it).
--
-- RULES THIS FILE FOLLOWS. Statuses are text + CHECK (the codebase has not
-- used CREATE TYPE … AS ENUM since 001). Every foreign key is NO ACTION
-- (032/AM-B1: a delete out of the student graph happens only when the purge
-- spells it out). A submission's student is its teacher's student (032/AM-B4
-- tenant FK). Every new table enables RLS here (SEC-1; no policies — the
-- backend role owns the tables and bypasses RLS).
--
-- Idempotent: IF NOT EXISTS everywhere; constraints added by ALTER are
-- dropped IF EXISTS first. One transaction: all of it, or none of it.

BEGIN;

-- ---------------------------------------------------------------------------
-- capture_links
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.capture_links (
    id                uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id          uuid        NOT NULL REFERENCES public.grading_batches(id),
    user_id           uuid        NOT NULL REFERENCES public.users(id),
    token_hash        bytea       NOT NULL,
    token_generation  integer     NOT NULL DEFAULT 1,
    exam_date         date        NOT NULL,          -- an Asia/Jerusalem calendar date
    closed_at         timestamptz NULL,              -- non-null = closed early (R5)
    created_at        timestamptz NOT NULL DEFAULT now(),
    updated_at        timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT capture_links_one_per_batch UNIQUE (batch_id),          -- R6
    CONSTRAINT capture_links_token_hash_key UNIQUE (token_hash),
    CONSTRAINT capture_links_generation_positive CHECK (token_generation >= 1)
);
ALTER TABLE public.capture_links ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- capture_handoffs (D2 / OD-5)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.capture_handoffs (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid        NOT NULL REFERENCES public.users(id),
    batch_id            uuid        NOT NULL REFERENCES public.grading_batches(id),
    handoff_hash        bytea       NOT NULL,
    handoff_expires_at  timestamptz NOT NULL,        -- 10 minutes, single use
    consumed_at         timestamptz NULL,
    session_hash        bytea       NULL,
    session_expires_at  timestamptz NULL,            -- 12 hours
    revoked_at          timestamptz NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT capture_handoffs_handoff_hash_key UNIQUE (handoff_hash),
    CONSTRAINT capture_handoffs_session_hash_key UNIQUE (session_hash),
    -- A session exists exactly when the one-time token was consumed.
    CONSTRAINT capture_handoffs_session_consistency CHECK (
        (consumed_at IS NULL) = (session_hash IS NULL)
        AND (session_hash IS NULL) = (session_expires_at IS NULL))
);
CREATE INDEX IF NOT EXISTS idx_capture_handoffs_batch
    ON public.capture_handoffs (batch_id);
ALTER TABLE public.capture_handoffs ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- capture_submissions — the Draft
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.capture_submissions (
    id                    uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_id              uuid        NOT NULL REFERENCES public.grading_batches(id),
    user_id               uuid        NOT NULL REFERENCES public.users(id),   -- owning teacher
    source                text        NOT NULL,
    link_id               uuid        NULL REFERENCES public.capture_links(id),
    device_secret_hash    bytea       NULL,                                   -- student_link only (D1)
    student_id            uuid        NULL REFERENCES public.students(id),
    student_state         text        NOT NULL DEFAULT 'unassigned',
    pending_student_name  text        NULL,                                   -- R1/D4: as typed
    conflict_note         text        NULL,                                   -- D1/D5/D6, a code
    status                text        NOT NULL DEFAULT 'draft',
    current_version_id    uuid        NULL,                                   -- FK below
    created_at            timestamptz NOT NULL DEFAULT now(),
    updated_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT capture_submissions_source_check
        CHECK (source IN ('student_link', 'teacher')),
    CONSTRAINT capture_submissions_student_state_check
        CHECK (student_state IN ('unassigned', 'confirmed', 'pending', 'conflict')),
    CONSTRAINT capture_submissions_status_check
        CHECK (status IN ('draft', 'saved', 'discarded')),
    CONSTRAINT capture_submissions_conflict_note_check
        CHECK (conflict_note IS NULL OR conflict_note IN
               ('duplicate_student', 'duplicate_pending_name', 'late_resubmission')),
    CONSTRAINT capture_source_link CHECK (
        (source = 'student_link') = (link_id IS NOT NULL AND device_secret_hash IS NOT NULL)),
    CONSTRAINT capture_student_consistency CHECK (
        (student_state = 'confirmed'  AND student_id IS NOT NULL) OR
        (student_state = 'pending'    AND student_id IS NULL AND pending_student_name IS NOT NULL) OR
        (student_state = 'conflict') OR
        (student_state = 'unassigned' AND student_id IS NULL)),
    -- SCN-8: a teacher-source submission is saved only with a confirmed student.
    CONSTRAINT capture_teacher_saved_confirmed CHECK (
        NOT (source = 'teacher' AND status = 'saved' AND student_state <> 'confirmed')),
    -- A saved submission has a current version (SCN-3).
    CONSTRAINT capture_saved_has_version CHECK (
        status <> 'saved' OR current_version_id IS NOT NULL),
    -- AM-B4: a submission's student is its teacher's student.
    CONSTRAINT capture_submissions_student_tenant_fkey
        FOREIGN KEY (student_id, user_id) REFERENCES public.students(id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_capture_submissions_batch_status
    ON public.capture_submissions (batch_id, status);
CREATE INDEX IF NOT EXISTS idx_capture_submissions_link_device
    ON public.capture_submissions (link_id, device_secret_hash);
CREATE INDEX IF NOT EXISTS idx_capture_submissions_student
    ON public.capture_submissions (student_id) WHERE student_id IS NOT NULL;
ALTER TABLE public.capture_submissions ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- capture_pages
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.capture_pages (
    id                  uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id       uuid        NOT NULL REFERENCES public.capture_submissions(id),
    raw_gcs_uri         text        NOT NULL,
    preview_gcs_uri     text        NULL,          -- EXIF-oriented, long side ≤1600, display only (SCN-11)
    content_type        text        NOT NULL,
    status              text        NOT NULL DEFAULT 'awaiting_upload',
    image_w             integer     NULL,          -- EXIF-oriented pixel size
    image_h             integer     NULL,
    corners             jsonb       NULL,          -- [[x,y]×4] normalized 0..1, TL,TR,BR,BL
    corners_source      text        NULL,
    -- The last ANALYSIS result, kept apart from `corners` so «איפוס» (reset to
    -- auto, §6.5) can restore it after a manual edit overwrote `corners`.
    auto_corners        jsonb       NULL,
    auto_corners_source text        NULL,
    detect_confidence   real        NULL,
    quality             jsonb       NULL,          -- {blur, short_side_px, glare_ratio, verdict, reasons[]}
    rotation            smallint    NOT NULL DEFAULT 0,
    position            integer     NOT NULL,
    deleted_at          timestamptz NULL,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT capture_pages_content_type_check
        CHECK (content_type IN ('image/jpeg', 'image/png', 'image/heic', 'image/heif')),
    CONSTRAINT capture_pages_status_check
        CHECK (status IN ('awaiting_upload', 'analyzed', 'analyze_failed')),
    CONSTRAINT capture_pages_corners_source_check
        CHECK (corners_source IS NULL OR corners_source IN
               ('auto_model', 'auto_contour', 'full_frame', 'manual')),
    CONSTRAINT capture_pages_auto_corners_source_check
        CHECK (auto_corners_source IS NULL OR auto_corners_source IN
               ('auto_model', 'auto_contour', 'full_frame')),
    CONSTRAINT capture_pages_rotation_check CHECK (rotation IN (0, 90, 180, 270)),
    -- An uploaded page has corners: analysis either succeeded (and then it
    -- also knows the oriented pixel size) or fell back to the full frame (D9 —
    -- scan-service never decoded it, so the size is honestly unknown). An
    -- awaiting page has neither yet.
    CONSTRAINT capture_pages_status_consistency CHECK (
        (status = 'awaiting_upload') OR
        (status = 'analyze_failed' AND corners IS NOT NULL AND corners_source IS NOT NULL) OR
        (status = 'analyzed' AND corners IS NOT NULL AND corners_source IS NOT NULL
         AND image_w IS NOT NULL AND image_h IS NOT NULL))
);
-- Positions are unique among LIVE pages only; reorder is two-phase in one
-- transaction (offset, then set).
CREATE UNIQUE INDEX IF NOT EXISTS capture_pages_position_uq
    ON public.capture_pages (submission_id, position) WHERE deleted_at IS NULL;
ALTER TABLE public.capture_pages ENABLE ROW LEVEL SECURITY;

-- ---------------------------------------------------------------------------
-- capture_versions — the Contract (SCN-2: never mutated after insert)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.capture_versions (
    id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    submission_id          uuid        NOT NULL REFERENCES public.capture_submissions(id),
    version_no             integer     NOT NULL,
    pages_snapshot         jsonb       NOT NULL,   -- [{page_id, raw_gcs_uri, content_type, corners, rotation}] in order
    scan_pipeline_version  text        NOT NULL,   -- e.g. 'scan-v1.0'
    created_at             timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT capture_versions_submission_version_key UNIQUE (submission_id, version_no),
    -- Target of the composite FK below: a submission's current version is ITS version.
    CONSTRAINT capture_versions_id_submission_key UNIQUE (id, submission_id),
    CONSTRAINT capture_versions_version_no_positive CHECK (version_no >= 1)
);
ALTER TABLE public.capture_versions ENABLE ROW LEVEL SECURITY;

ALTER TABLE public.capture_submissions
    DROP CONSTRAINT IF EXISTS capture_current_version_fk;
ALTER TABLE public.capture_submissions
    ADD CONSTRAINT capture_current_version_fk
    FOREIGN KEY (current_version_id, id) REFERENCES public.capture_versions(id, submission_id);

-- ---------------------------------------------------------------------------
-- transcription_jobs: the version → job link (SCN-4) and the hide flag (OD-2)
-- ---------------------------------------------------------------------------
ALTER TABLE public.transcription_jobs
    ADD COLUMN IF NOT EXISTS capture_version_id uuid NULL;
ALTER TABLE public.transcription_jobs
    ADD COLUMN IF NOT EXISTS withdrawn_at timestamptz NULL;

ALTER TABLE public.transcription_jobs
    DROP CONSTRAINT IF EXISTS transcription_jobs_capture_version_id_fkey;
ALTER TABLE public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_capture_version_id_fkey
    FOREIGN KEY (capture_version_id) REFERENCES public.capture_versions(id);

-- One job per version (SCN-4). A UNIQUE constraint, not a partial index:
-- NULLs are distinct, so every upload-sourced job (NULL) coexists.
ALTER TABLE public.transcription_jobs
    DROP CONSTRAINT IF EXISTS transcription_jobs_capture_version_id_key;
ALTER TABLE public.transcription_jobs
    ADD CONSTRAINT transcription_jobs_capture_version_id_key UNIQUE (capture_version_id);

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('036', 'in-house scanning: capture_links/handoffs/submissions/pages/versions + transcription_jobs.capture_version_id/withdrawn_at (OD-1/OD-2/OD-4/OD-5)')
ON CONFLICT DO NOTHING;

COMMIT;
