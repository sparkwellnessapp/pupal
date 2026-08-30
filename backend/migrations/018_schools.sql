-- 018: schools + users.school_id — override attribution (PR-G6)
--
-- The operating doc needs five keys per teacher override: teacher, school,
-- question identity, criterion, student. Four already resolve by join
-- (graded_tests.user_id, transcriptions.student_id, and
-- rubric_id + question_id + criterion_id + check_id + plan_version). School had
-- no home at all — this file is that home.
--
-- users.school_id is NULLABLE on purpose: the onboarding prompt is one field and
-- skippable, so a teacher who never answers must still be attributable on the
-- other four keys. A NOT NULL column here would either block signup or invent a
-- school, and inventing one is the failure mode the whole attribution exists to
-- avoid.
--
-- Matching is normalized-exact, never fuzzy (the conservative student-match
-- precedent): two schools differing by one character are two schools.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

CREATE TABLE IF NOT EXISTS public.schools (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        TEXT NOT NULL,
    city        TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Normalized-exact uniqueness: trimmed, case-folded, internal whitespace
-- collapsed. Expressed in the INDEX so the database enforces the same rule the
-- application's normalize_school_name() applies — one concept, one place.
CREATE UNIQUE INDEX IF NOT EXISTS idx_schools_normalized_name
    ON public.schools (lower(regexp_replace(btrim(name), '\s+', ' ', 'g')));

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS school_id UUID REFERENCES public.schools(id);

CREATE INDEX IF NOT EXISTS idx_users_school_id
    ON public.users (school_id)
    WHERE school_id IS NOT NULL;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('018', 'schools + users.school_id (nullable FK) + normalized-exact unique index — PR-G6 override attribution')
ON CONFLICT DO NOTHING;
