-- 019: graded_tests.opened_at — first teacher open (PR-G8)
--
-- The moment the teacher first LOOKED at a graded test. Two consumers need it
-- and both need it to mean exactly that:
--   * the batch feed distinguishes "landed" from "landed and seen";
--   * the deferred consistency applier keys on it — a delta may be applied
--     SILENTLY to a draft she has never opened, but must be MARKED once she
--     has, because changing something under her after she read it is the one
--     thing that would make her stop trusting the surface.
--
-- Set ONCE, by the owner's own GET. Never by an admin read, never by a
-- background job, and never re-stamped: "when she first saw it" is not a
-- last-access timestamp.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

ALTER TABLE public.graded_tests
    ADD COLUMN IF NOT EXISTS opened_at TIMESTAMPTZ;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('019', 'graded_tests.opened_at — first teacher open (PR-G8)')
ON CONFLICT DO NOTHING;
