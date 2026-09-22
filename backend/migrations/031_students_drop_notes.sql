-- 031 — students.notes is retired (student-profile PR, Part A · OD-3 / M-A6).
--
-- The field was a free-text box visible only in the edit modal and on the
-- roster card; the profile makes the student a navigational anchor with NO
-- judgement attached (P1: discrete facts only), and a notes column is exactly
-- the place a judgement would accumulate. M-A6: drop the column when it holds
-- no data — verified on production 2026-09-19 (9 students, 0 non-null notes) —
-- otherwise keep it and only remove the reads/writes. It held nothing.
--
-- Idempotent: re-running the whole file is always the answer (CLAUDE.md §13).
ALTER TABLE public.students DROP COLUMN IF EXISTS notes;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('031', 'students.notes dropped: the profile is a ledger of facts, not a place for judgements (student-profile PR, OD-3/M-A6)')
ON CONFLICT DO NOTHING;
