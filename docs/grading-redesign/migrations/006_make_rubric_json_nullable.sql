-- =============================================================================
-- Migration: Make rubric_json nullable in rubrics table
-- Run this SQL in Supabase SQL Editor
-- Created: 2026-04-11
--
-- Root cause:
--   The rubrics table was originally created with rubric_json NOT NULL (legacy
--   format). The SQLAlchemy model was updated to nullable=True to support the
--   ontology two-artifact path (draft_json + contract_json), but this ALTER was
--   never applied to the database, causing every new ontology rubric save to
--   fail with:
--       null value in column "rubric_json" of relation "rubrics"
--       violates not-null constraint
--
-- Fix: drop the NOT NULL constraint so new ontology rubrics can be inserted
-- without a rubric_json value (they use draft_json + contract_json instead).
-- Existing legacy rubrics already have rubric_json populated and are unaffected.
-- =============================================================================

ALTER TABLE rubrics
    ALTER COLUMN rubric_json DROP NOT NULL;

-- =============================================================================
-- Verification
-- =============================================================================

-- Should show is_nullable = 'YES' for rubric_json
SELECT
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name   = 'rubrics'
  AND column_name  = 'rubric_json';
