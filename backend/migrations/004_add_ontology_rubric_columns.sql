-- =============================================================================
-- Migration: Add Ontology Rubric Columns for Two-Artifact Architecture
-- Run this SQL in Supabase SQL Editor
-- Created: 2026-02-02
-- 
-- This migration adds support for the ontology-based grading system:
-- - draft_json: Teacher-editable ExtractRubricResponse
-- - contract_json: Frozen GradingRubricContract for grading
-- - Version tracking and compilation metadata
-- - Immutable backup for safe migration rollback
-- =============================================================================

-- =============================================================================
-- 1. Add new columns to rubrics table
-- =============================================================================

-- The teacher-editable draft (ExtractRubricResponse serialized)
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS draft_json JSONB;

COMMENT ON COLUMN rubrics.draft_json IS 
    'Teacher-editable ExtractRubricResponse from ontology_types. Teachers review and edit this before compilation.';

-- The compiled contract (GradingRubricContract serialized)
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS contract_json JSONB;

COMMENT ON COLUMN rubrics.contract_json IS 
    'Frozen GradingRubricContract used by grading agent. Immutable after compilation. Closed-world semantics.';

-- Contract version for reproducibility (INV: given version, grading is deterministic)
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS contract_version VARCHAR(50);

COMMENT ON COLUMN rubrics.contract_version IS 
    'UUID version of the compiled contract. Increments on each successful compilation.';

-- Timestamp of last successful compilation
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS last_compiled_at TIMESTAMPTZ;

COMMENT ON COLUMN rubrics.last_compiled_at IS 
    'When the contract was last compiled. NULL if never compiled.';

-- Flag indicating draft was edited after last compilation
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS needs_recompilation BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN rubrics.needs_recompilation IS 
    'TRUE if draft_json was edited after last compilation. Blocks grading until recompiled.';

-- List of warning annotation IDs that teacher acknowledged
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS acknowledged_warnings JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN rubrics.acknowledged_warnings IS 
    'Array of warning annotation IDs that teacher acknowledged during compilation.';

-- Counter for observability: track compilation attempts
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS compilation_attempts INTEGER DEFAULT 0;

COMMENT ON COLUMN rubrics.compilation_attempts IS 
    'Number of compilation attempts. High values (>3) indicate UX or validation issues.';

-- Immutable backup for rollback safety during migration
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS legacy_rubric_json_backup JSONB;

COMMENT ON COLUMN rubrics.legacy_rubric_json_backup IS 
    'Immutable copy of original rubric_json before ontology migration. Used for rollback if needed.';


-- =============================================================================
-- 2. Create index on contract_version for efficient version lookups
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_rubrics_contract_version 
ON rubrics(contract_version) 
WHERE contract_version IS NOT NULL;


-- =============================================================================
-- 3. Create index for finding rubrics needing recompilation (for admin tools)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_rubrics_needs_recompilation 
ON rubrics(needs_recompilation) 
WHERE needs_recompilation = TRUE;


-- =============================================================================
-- 4. Create index for finding rubrics with high compilation attempts (observability)
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_rubrics_compilation_attempts 
ON rubrics(compilation_attempts) 
WHERE compilation_attempts > 3;


-- =============================================================================
-- Verification
-- =============================================================================

-- Verify columns were added
SELECT 
    column_name, 
    data_type, 
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_schema = 'public' 
  AND table_name = 'rubrics'
  AND column_name IN (
    'draft_json', 
    'contract_json', 
    'contract_version', 
    'last_compiled_at', 
    'needs_recompilation', 
    'acknowledged_warnings',
    'compilation_attempts',
    'legacy_rubric_json_backup'
  )
ORDER BY ordinal_position;

-- Show counts (should all be 0 initially for new columns with default values)
SELECT 
    COUNT(*) AS total_rubrics,
    COUNT(draft_json) AS has_draft,
    COUNT(contract_json) AS has_contract,
    COUNT(legacy_rubric_json_backup) AS has_backup,
    SUM(CASE WHEN needs_recompilation THEN 1 ELSE 0 END) AS needs_recompilation_count
FROM rubrics;


-- =============================================================================
-- DONE! 
-- 
-- Next steps after running this migration:
-- 1. Run the Python migration script to populate draft_json from rubric_json
-- 2. Verify backups were created
-- 3. Test compilation on a few rubrics
-- =============================================================================

