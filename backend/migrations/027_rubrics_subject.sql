-- 027 — rubrics.subject: THE durable subject key of a rubric (multisubject seam, D-10).
--
-- Ruled 2026-09-08 (vivi-multisubject-execution-plan.md §2 D-10):
--   * NOT NULL DEFAULT 'computer_science' — every existing row is a CS rubric.
--   * Backfilled from the contract's own `subject` field (falling back to the
--     draft's, then the default) so the column and the JSONB never disagree.
--   * NO CHECK constraint on the value set: the registry (app/subjects) validates
--     at the API boundary with a 422. A CHECK per new subject would make adding
--     Physics a migration, which fails CLAUDE.md §3.3's litmus test.
--   * Downstream rows (graded_tests, transcriptions, grading_batches, grading_plans)
--     get NO column — they reach the subject through the rubric FK / the contract.
--
-- Idempotent: safe to re-run in full.

ALTER TABLE public.rubrics
    ADD COLUMN IF NOT EXISTS subject TEXT NOT NULL DEFAULT 'computer_science';

UPDATE public.rubrics
   SET subject = COALESCE(
         NULLIF(contract_json->>'subject', ''),
         NULLIF(draft_json->>'subject', ''),
         'computer_science')
 WHERE subject = 'computer_science'
   AND COALESCE(NULLIF(contract_json->>'subject', ''), NULLIF(draft_json->>'subject', ''), 'computer_science')
       <> 'computer_science';

CREATE INDEX IF NOT EXISTS idx_rubrics_subject ON public.rubrics (subject);

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('027', 'rubrics.subject — the durable subject key (multisubject seam, D-10); backfilled from contract_json')
ON CONFLICT DO NOTHING;
