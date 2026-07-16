-- Migration 009: S8 — add cost/token capture + grading lifecycle columns to graded_tests
--
-- Adds:
--   grading_started_at  — set when row enters 'grading'; supports stuck-row detection
--   total_input_tokens  — sum of per-scope LLM input tokens (from GradedTestDraft)
--   total_output_tokens — sum of per-scope LLM output tokens
--   total_cost_usd      — computed cost at grading time (input+output tokens × pricing constants)
--   prompt_version      — GRADING_PROMPT_VERSION constant stamped at grade time; enables
--                         eval-suite slicing by prompt version without parsing draft_json
--
-- All columns are nullable: existing pending rows are unaffected.

ALTER TABLE public.graded_tests
    ADD COLUMN grading_started_at  TIMESTAMPTZ,
    ADD COLUMN total_input_tokens  INTEGER,
    ADD COLUMN total_output_tokens INTEGER,
    ADD COLUMN total_cost_usd      NUMERIC(10, 4),
    ADD COLUMN prompt_version      VARCHAR(50);
