-- 033 — the purge's failure ledger (M-B2; PRV-3 ObjectsNeverSilentlyKept).
--
-- A student purge deletes her rows in one transaction and THEN her objects
-- (M-B1: synchronous, after commit — tens of objects). An object delete that
-- fails cannot roll the rows back: they are already gone, which is the point.
-- So each failure lands HERE, and in an ERROR log line, and never nowhere:
-- a place that is not a log to scrape, from which `retry_purge_failures`
-- (python -m app.scripts.retry_purge_failures) re-attempts every row and
-- clears it on success.
--
-- What a row holds: ids and an object path. Object paths in the three allowed
-- families are ids too (PRV-11), so the ledger carries no name and no filename
-- (OD-B4's rule, applied to a table).
--
-- `student_id` has NO foreign key, deliberately: the ledger row is written
-- AFTER the student row is deleted, and it must outlive it. `user_id` does:
-- a teacher's account cannot be deleted while objects of her students are
-- still waiting to be deleted (NO ACTION — the account-deletion follow-up will
-- call the erasure core, which drains this first).
--
-- One row per object: a second failure of the same object bumps `attempts`.

CREATE TABLE IF NOT EXISTS public.purge_failures (
    id              uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid        NOT NULL REFERENCES public.users(id),
    student_id      uuid        NOT NULL,
    bucket          text        NOT NULL,
    object_name     text        NOT NULL,
    error           text        NOT NULL,
    attempts        integer     NOT NULL DEFAULT 1,
    created_at      timestamptz NOT NULL DEFAULT now(),
    last_attempt_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_purge_failures_object
    ON public.purge_failures (bucket, object_name);

CREATE INDEX IF NOT EXISTS idx_purge_failures_student
    ON public.purge_failures (student_id);

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('033', 'purge_failures — the student purge''s ledger of object deletes that failed (M-B2, PRV-3)')
ON CONFLICT DO NOTHING;
