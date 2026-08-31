-- 021 — the returned exam's render key (PR-G9)
--
-- sha256 over every input that can change a pixel (contract version, stamp
-- position, criteria toggle, feedback hash, renderer version). The cached PDF
-- in GCS is named by it, so a mismatch is the DEFINITION of stale: the row's
-- key is compared against the freshly computed one on every read, and a stale
-- exam is omitted from the ZIP rather than handed to a student.
--
-- NULL = never rendered.
--
-- Idempotent: re-running this whole file is always the answer (migration-013
-- convention).

ALTER TABLE public.graded_tests
    ADD COLUMN IF NOT EXISTS returned_exam_key TEXT;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('021', 'graded_tests.returned_exam_key — returned-exam render cache (PR-G9)')
ON CONFLICT DO NOTHING;
