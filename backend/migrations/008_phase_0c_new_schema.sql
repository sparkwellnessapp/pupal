-- =============================================================================
-- Migration 008 — Phase 0c new schema
-- =============================================================================
--
-- Purpose: Implement the target schema specified in phase_0c_target_ddl.md.
--          Creates new tables and reshapes the surviving ones from Phase 0b.
--
-- Preflight: This migration assumes migration 007 (Phase 0b cleanup) has been
--            run successfully. Verify with:
--              SELECT to_regclass('public.raw_graded_tests');   -- expect NULL
--              SELECT to_regclass('public.graded_test_pdfs');   -- expect NULL
--              SELECT to_regclass('public.grading_sessions');   -- expect NULL
--            If any return non-NULL, run 007 first.
--
-- Scope:
--   New tables:
--     * students            — first-class learner identity, per-teacher scoped
--     * classes             — teacher-defined groupings
--     * class_memberships   — M:N join between students and classes
--     * transcriptions      — Draft/Contract artifact for student answers,
--                             with GCS PDF persistence
--
--   Reshaped tables:
--     * graded_tests        — dropped and recreated with new shape
--                             (transcription_id FK, revision chain, draft/contract
--                              pattern, denormalized score columns)
--     * grading_batches     — teacher_id renamed to user_id, class_id retyped
--                             to UUID FK on classes, status CHECK added
--
-- What this migration does NOT do:
--   * Does NOT drop any data (graded_tests and grading_batches are empty pre-launch)
--   * Does NOT touch users, rubrics (apart from FK relationships), subject_matters,
--     user_subject_matters, rubric_shares, rubric_share_history, rubric_share_tokens,
--     or raw_rubrics
--   * Does NOT enforce JSONB-internal invariants (CW-* and PTS-* — application layer)
--
-- Idempotency: every CREATE uses IF NOT EXISTS. The DROP TABLE for graded_tests
--              uses IF EXISTS. ALTER TABLE statements use IF EXISTS / IF NOT EXISTS
--              where supported by PostgreSQL.
--
-- Atomicity: wrapped in a transaction. If any statement fails, none apply.
--
-- Reference: phase_0c_target_ddl.md (the spec this migration implements)
-- =============================================================================

BEGIN;

-- -----------------------------------------------------------------------------
-- 1. New table: students
-- -----------------------------------------------------------------------------
-- First-class learner identity. Per Phase 0a §2.2.A and Phase 0c §1.
-- Per-teacher scoped — different teachers may each have a student named "יוסי כהן";
-- they are different students.

CREATE TABLE IF NOT EXISTS public.students (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    full_name   VARCHAR(255) NOT NULL,
    notes       TEXT,

    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT students_unique_name_per_user UNIQUE (user_id, full_name)
);

CREATE INDEX IF NOT EXISTS idx_students_user ON public.students (user_id);

COMMENT ON TABLE public.students IS
    'Persistent identity for a learner. Per-teacher scoped. Per Phase 0c §1.';

-- -----------------------------------------------------------------------------
-- 2. New table: classes
-- -----------------------------------------------------------------------------
-- Teacher-defined groupings of students. Per Phase 0a §2.2.B and Phase 0c §2.

CREATE TABLE IF NOT EXISTS public.classes (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    name                VARCHAR(255) NOT NULL,
    subject_matter_id   INTEGER REFERENCES public.subject_matters(id) ON DELETE SET NULL,
    school_year         VARCHAR(20),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT classes_unique_name_per_user UNIQUE (user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_classes_user ON public.classes (user_id);

COMMENT ON TABLE public.classes IS
    'Teacher-defined groupings of students. Per-teacher scoped. Per Phase 0c §2.';

-- -----------------------------------------------------------------------------
-- 3. New table: class_memberships
-- -----------------------------------------------------------------------------
-- M:N join table between students and classes. Per Phase 0a §2.2.B and Phase 0c §3.

CREATE TABLE IF NOT EXISTS public.class_memberships (
    class_id    UUID NOT NULL REFERENCES public.classes(id) ON DELETE CASCADE,
    student_id  UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (class_id, student_id)
);

CREATE INDEX IF NOT EXISTS idx_class_memberships_student
    ON public.class_memberships (student_id);

COMMENT ON TABLE public.class_memberships IS
    'M:N join between classes and students. Per Phase 0c §3.';

-- -----------------------------------------------------------------------------
-- 4. New table: transcriptions
-- -----------------------------------------------------------------------------
-- The transcription artifact — Draft + Contract for one student's handwritten
-- test, with PDF persistence to GCS. Per Phase 0a §2.1.A and Phase 0c §4.

CREATE TABLE IF NOT EXISTS public.transcriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rubric_id           UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,

    -- Nullable while status='transcribed'; required at 'approved' (per CHECK below).
    student_id          UUID REFERENCES public.students(id) ON DELETE CASCADE,
    student_name        VARCHAR(255),

    -- GCS PDF persistence (per Phase 0a OD2 + Phase 0c §4).
    gcs_uri             VARCHAR(500) NOT NULL,
    gcs_bucket          VARCHAR(255) NOT NULL,
    gcs_object_path     VARCHAR(500) NOT NULL,
    filename            VARCHAR(500),

    -- Draft side: VLM output. Pydantic model: TranscriptionDraft (defined in S4).
    -- Immutable from INSERT onward.
    draft_json          JSONB NOT NULL,

    -- Contract side: teacher-approved StudentAnswer set, frozen.
    -- Pydantic model: TranscriptionContract (defined in S4).
    -- contract_version lives INSIDE the JSONB (per Phase 0a RD-3 — no separate column).
    contract_json       JSONB,
    approved_at         TIMESTAMPTZ,

    status              VARCHAR(20) NOT NULL DEFAULT 'transcribed'
                        CHECK (status IN ('transcribed', 'approved')),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- LCY-1 enforcement: status and the approval fields are consistent.
    CONSTRAINT transcriptions_approval_consistency CHECK (
        (status = 'transcribed'
            AND contract_json IS NULL
            AND approved_at IS NULL
            AND student_id IS NULL)
        OR
        (status = 'approved'
            AND contract_json IS NOT NULL
            AND approved_at IS NOT NULL
            AND student_id IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_transcriptions_user_rubric
    ON public.transcriptions (user_id, rubric_id);

CREATE INDEX IF NOT EXISTS idx_transcriptions_user_student
    ON public.transcriptions (user_id, student_id)
    WHERE student_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_transcriptions_status
    ON public.transcriptions (status);

COMMENT ON TABLE public.transcriptions IS
    'Draft+Contract artifact for one student handwritten test. Per Phase 0c §4.';
COMMENT ON COLUMN public.transcriptions.draft_json IS
    'TranscriptionDraft Pydantic model. VLM output, immutable from INSERT onward.';
COMMENT ON COLUMN public.transcriptions.contract_json IS
    'TranscriptionContract Pydantic model. Teacher-approved answers. contract_version inside JSONB.';

-- -----------------------------------------------------------------------------
-- 5. Reshape: grading_batches
-- -----------------------------------------------------------------------------
-- Four changes:
--   (a) Rename teacher_id → user_id for consistency with the rest of the schema.
--   (b) Change ON DELETE behavior on user FK from SET NULL to CASCADE
--       (per Phase 0c §6 — per-teacher scoping invariant).
--   (c) Drop class_id (VARCHAR free-text) and re-add as UUID FK to classes.
--   (d) Add status CHECK constraint with the locked set of statuses.
--
-- Pre-launch: grading_batches is empty, so destructive column changes are safe.

-- (a) Rename teacher_id → user_id
ALTER TABLE public.grading_batches
    RENAME COLUMN teacher_id TO user_id;

-- (b) Replace the FK constraint with the new CASCADE rule.
--     The constraint name from the original migration is the Postgres-generated default.
ALTER TABLE public.grading_batches
    DROP CONSTRAINT IF EXISTS grading_batches_teacher_id_fkey;

ALTER TABLE public.grading_batches
    ADD CONSTRAINT grading_batches_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES public.users(id) ON DELETE CASCADE;

-- (c) Re-type class_id from VARCHAR to UUID FK on classes.
--     Drop the column entirely (empty pre-launch) and add a new one with the FK.
ALTER TABLE public.grading_batches
    DROP COLUMN IF EXISTS class_id;

ALTER TABLE public.grading_batches
    ADD COLUMN class_id UUID REFERENCES public.classes(id) ON DELETE SET NULL;

-- (d) Add status CHECK constraint (none existed before — status was free VARCHAR).
ALTER TABLE public.grading_batches
    DROP CONSTRAINT IF EXISTS grading_batches_status_check;

ALTER TABLE public.grading_batches
    ADD CONSTRAINT grading_batches_status_check
    CHECK (status IN ('pending', 'in_progress', 'completed',
                      'partially_completed', 'failed'));

-- (e) Make user_id NOT NULL (the old teacher_id was nullable due to SET NULL FK).
--     Pre-launch: no rows exist, so this is safe.
ALTER TABLE public.grading_batches
    ALTER COLUMN user_id SET NOT NULL;

-- New index for user-scoped queries
CREATE INDEX IF NOT EXISTS idx_grading_batches_user
    ON public.grading_batches (user_id);

COMMENT ON TABLE public.grading_batches IS
    'Teacher-defined groupings of grading operations. Counts derived from graded_tests. Per Phase 0c §6.';

-- -----------------------------------------------------------------------------
-- 6. Reshape: graded_tests
-- -----------------------------------------------------------------------------
-- Per Phase 0c §5, the table is fully rebuilt. Pre-launch the table is empty,
-- so DROP TABLE + CREATE TABLE is the simplest path. Nothing FKs into graded_tests
-- after migration 007 (graded_test_pdfs and grading_sessions are gone).

DROP TABLE IF EXISTS public.graded_tests CASCADE;

CREATE TABLE public.graded_tests (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rubric_id                UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,
    transcription_id         UUID NOT NULL REFERENCES public.transcriptions(id) ON DELETE CASCADE,
    student_id               UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    batch_id                 UUID REFERENCES public.grading_batches(id) ON DELETE SET NULL,

    -- Pinned at INSERT (per VER-2). Used to compute rubric_contract_stale at query
    -- time by joining to rubrics.contract_version.
    rubric_contract_version  VARCHAR(50) NOT NULL,

    -- Denormalized for list-view performance (per Phase 0c §9).
    student_name             VARCHAR(255) NOT NULL,
    filename                 VARCHAR(500),

    -- Draft side: agent outcomes + sparse teacher_overrides overlay.
    -- Pydantic model: GradedTestDraft (defined in S6/S8).
    -- NULL during 'pending' and 'grading'; populated from 'draft' onward.
    draft_json               JSONB,
    draft_created_at         TIMESTAMPTZ,

    -- Contract side: frozen, approved.
    -- Pydantic model: GradedTestContract (defined in S9).
    -- contract_version lives INSIDE the JSONB.
    contract_json            JSONB,
    approved_at              TIMESTAMPTZ,

    -- Revision chain. Self-referential FKs. ON DELETE SET NULL preserves the
    -- audit trail even if a chain neighbor is somehow deleted.
    regraded_from_id         UUID REFERENCES public.graded_tests(id) ON DELETE SET NULL,
    regraded_to_id           UUID REFERENCES public.graded_tests(id) ON DELETE SET NULL,

    -- Lifecycle. Five states: pending → grading → (draft → approved) | failed.
    status                   VARCHAR(20) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'grading', 'draft', 'approved', 'failed')),
    error_message            TEXT,

    -- Denormalized score for list views. Updated whenever draft_json changes.
    total_score              NUMERIC(10, 2),
    total_possible           NUMERIC(10, 2),
    percentage               NUMERIC(5, 2),

    -- Observability.
    llm_calls_count          INTEGER NOT NULL DEFAULT 0,
    grading_duration_ms      INTEGER NOT NULL DEFAULT 0,
    model_version            VARCHAR(50),

    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- LCY-2 + state-machine enforcement: status and the presence of draft/contract
    -- fields are consistent. See Phase 0c §5 for the full state machine.
    CONSTRAINT graded_tests_status_consistency CHECK (
        (status = 'pending'  AND draft_json IS NULL AND contract_json IS NULL)
        OR
        (status = 'grading'  AND draft_json IS NULL AND contract_json IS NULL)
        OR
        (status = 'draft'    AND draft_json IS NOT NULL AND contract_json IS NULL)
        OR
        (status = 'approved' AND draft_json IS NOT NULL AND contract_json IS NOT NULL AND approved_at IS NOT NULL)
        OR
        (status = 'failed'   AND error_message IS NOT NULL)
    )
);

-- RGC-1 enforcement: exactly one leaf (regraded_to_id IS NULL) per
-- (transcription_id, rubric_id) pair. Load-bearing constraint.
CREATE UNIQUE INDEX idx_graded_tests_one_leaf_per_chain
    ON public.graded_tests (transcription_id, rubric_id)
    WHERE regraded_to_id IS NULL;

-- Query indexes. Each one serves a named query pattern (per Phase 0c §5).
CREATE INDEX idx_graded_tests_user_rubric
    ON public.graded_tests (user_id, rubric_id);

CREATE INDEX idx_graded_tests_user_student
    ON public.graded_tests (user_id, student_id);

CREATE INDEX idx_graded_tests_batch
    ON public.graded_tests (batch_id) WHERE batch_id IS NOT NULL;

CREATE INDEX idx_graded_tests_transcription
    ON public.graded_tests (transcription_id);

CREATE INDEX idx_graded_tests_status
    ON public.graded_tests (status);

CREATE INDEX idx_graded_tests_regraded_from
    ON public.graded_tests (regraded_from_id) WHERE regraded_from_id IS NOT NULL;

COMMENT ON TABLE public.graded_tests IS
    'GradedTest Draft+Contract. Per (transcription, rubric version, grading pass) triple. Per Phase 0c §5.';
COMMENT ON COLUMN public.graded_tests.draft_json IS
    'GradedTestDraft Pydantic model. Agent outcomes + teacher_overrides overlay.';
COMMENT ON COLUMN public.graded_tests.contract_json IS
    'GradedTestContract Pydantic model. Frozen on approval. contract_version inside JSONB.';
COMMENT ON COLUMN public.graded_tests.regraded_from_id IS
    'Revision chain: the row this row replaces. NULL for first grade in a chain.';
COMMENT ON COLUMN public.graded_tests.regraded_to_id IS
    'Revision chain: the row that replaces this row. NULL for the current leaf.';

-- -----------------------------------------------------------------------------
-- 7. Verification queries (informational — do not run as part of migration)
-- -----------------------------------------------------------------------------
--
-- After running this migration, the following should all succeed:
--
--   SELECT to_regclass('public.students');           -- expect 'students'
--   SELECT to_regclass('public.classes');            -- expect 'classes'
--   SELECT to_regclass('public.class_memberships');  -- expect 'class_memberships'
--   SELECT to_regclass('public.transcriptions');     -- expect 'transcriptions'
--   SELECT to_regclass('public.graded_tests');       -- expect 'graded_tests'
--   SELECT to_regclass('public.grading_batches');    -- expect 'grading_batches'
--
--   -- Verify graded_tests has the new shape:
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'graded_tests'
--     AND column_name IN ('transcription_id', 'draft_json', 'contract_json',
--                         'regraded_from_id', 'regraded_to_id', 'rubric_contract_version');
--   -- expect 6 rows
--
--   -- Verify grading_batches has user_id (not teacher_id):
--   SELECT column_name FROM information_schema.columns
--   WHERE table_name = 'grading_batches' AND column_name IN ('user_id', 'teacher_id');
--   -- expect 1 row with 'user_id'
--
--   -- Verify the partial unique index exists:
--   SELECT indexname FROM pg_indexes
--   WHERE tablename = 'graded_tests' AND indexname = 'idx_graded_tests_one_leaf_per_chain';
--   -- expect 1 row
--
--   -- Verify CHECK constraints exist:
--   SELECT conname FROM pg_constraint
--   WHERE conname IN ('transcriptions_approval_consistency',
--                     'graded_tests_status_consistency',
--                     'grading_batches_status_check');
--   -- expect 3 rows
--
--   -- Verify class_id on grading_batches is now UUID (not VARCHAR):
--   SELECT data_type FROM information_schema.columns
--   WHERE table_name = 'grading_batches' AND column_name = 'class_id';
--   -- expect 'uuid'

COMMIT;
