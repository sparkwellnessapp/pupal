-- 022: onboarding — gender, the completion stamp, and the multi-school junction.
--
-- users.school_id (018) REMAINS the PR-G6 override-attribution key and is set to
-- the teacher's FIRST school. user_schools is the full truth; the column is the
-- key. This is a denormalization, deliberately, like graded_tests.total_score:
-- one concept at two granularities, with ONE write path (PUT /users/me/schools)
-- keeping them in agreement. override_attribution.py is untouched by this file.
--
-- gender is TEXT + CHECK, not a PG enum: subscription_status is this schema's one
-- enum and it is declared create_type=False, i.e. the DDL owns it. A CHECK is
-- idempotent, visible in \d, and widens with an ALTER. 'unspecified' is a STORED
-- value, not NULL — "prefer not to say" is an ANSWER, and collapsing it into NULL
-- would make `onboarding_completed_at IS NOT NULL AND gender IS NULL` unreadable.
--
-- No completion backfill: every existing row SHOULD see onboarding once (owner
-- confirmed 2026-08-31 that the only live account is the test user). If that ever
-- changes, the exemption is one UPDATE — it is not here because it is not wanted.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS gender TEXT,
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

DO $migration_022$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'users_gender_valid'
    ) THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_gender_valid
            CHECK (gender IS NULL OR gender IN ('female', 'male', 'unspecified'));
    END IF;
END
$migration_022$;

-- The full truth: every school the teacher works at, IN HER ORDER.
--
-- `position` is not decoration. Position 0 IS the school users.school_id points
-- at, so an unordered junction would let a later read hand back a different
-- "first" school than the attribution key — and a teacher who re-submits the
-- list she was shown would silently move that key. A many-to-many has no
-- inherent order; this column is what makes "schools[0] is the key" true rather
-- than merely usual. (Caught by test_schools_first_is_the_attribution_key.)
CREATE TABLE IF NOT EXISTS public.user_schools (
    user_id    UUID NOT NULL REFERENCES public.users(id)   ON DELETE CASCADE,
    school_id  UUID NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
    position   INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, school_id)
);

-- For a database that already ran an earlier draft of this file.
ALTER TABLE public.user_schools
    ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;

-- The PK already indexes (user_id, ...) for the per-teacher read; this covers the
-- reverse direction (every teacher at a school) that attribution reporting wants.
CREATE INDEX IF NOT EXISTS idx_user_schools_school_id
    ON public.user_schools (school_id);

-- Backfill: a teacher who already answered the one-field 018 prompt keeps her
-- answer as a junction row, so the two surfaces never disagree at cutover.
-- position 0: the one school she had IS the attribution key, by definition.
INSERT INTO public.user_schools (user_id, school_id, position)
SELECT id, school_id, 0 FROM public.users WHERE school_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('022', 'users.gender + users.onboarding_completed_at + user_schools junction — onboarding')
ON CONFLICT DO NOTHING;
