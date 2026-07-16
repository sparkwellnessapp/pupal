-- Migration: Add grading_sessions table for TestGrader Agent
-- Created: 2026-02-03
-- Purpose: Store grading session state for server-side persistence (survives browser close)

-- ============================================================================
-- GRADING SESSIONS TABLE
-- ============================================================================
-- Stores the state of ongoing and completed grading sessions.
-- Supports real-time progress tracking and session recovery.

CREATE TABLE IF NOT EXISTS grading_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- === REFERENCES ===
    teacher_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rubric_id UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    
    -- === CONTRACT REFERENCE (INV-A6: ContractVersionLock) ===
    contract_version VARCHAR(50) NOT NULL,
    
    -- === STUDENT INFO ===
    student_name VARCHAR(255) NOT NULL,
    filename VARCHAR(500),
    student_answer_document_id UUID,  -- Future: FK to student_answer_documents
    
    -- === SESSION STATE ===
    status VARCHAR(20) NOT NULL DEFAULT 'initialized' CHECK (
        status IN ('initialized', 'grading', 'completed', 'failed')
    ),
    
    -- === PROGRESS TRACKING ===
    total_questions INTEGER NOT NULL DEFAULT 0,
    total_criteria INTEGER NOT NULL DEFAULT 0,
    completed_criteria INTEGER NOT NULL DEFAULT 0,
    current_question_idx INTEGER NOT NULL DEFAULT 0,
    current_criterion_idx INTEGER NOT NULL DEFAULT 0,
    
    -- === STATE SNAPSHOT (for recovery) ===
    -- Stores serialized GradingAgentState for session recovery
    state_snapshot JSONB,
    
    -- === RESULTS ===
    graded_test_draft_id UUID,  -- FK to graded_tests when complete
    graded_test_draft_json JSONB,  -- Full GradedTestDraft for immediate access
    
    -- === ERROR HANDLING ===
    error_message TEXT,
    warnings JSONB DEFAULT '[]',
    skipped_criteria JSONB DEFAULT '[]',
    
    -- === QUALITY SIGNALS ===
    flagged_outcomes JSONB DEFAULT '[]',
    total_rules_evaluated INTEGER NOT NULL DEFAULT 0,
    rules_with_valid_quotes INTEGER NOT NULL DEFAULT 0,
    rules_flagged_for_review INTEGER NOT NULL DEFAULT 0,
    
    -- === TIMING & OBSERVABILITY ===
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    llm_calls_count INTEGER NOT NULL DEFAULT 0,
    total_llm_latency_ms INTEGER NOT NULL DEFAULT 0,
    
    -- === AUDIT ===
    model_version VARCHAR(50) DEFAULT 'test_grader_agent_v1.0'
);

-- ============================================================================
-- INDEXES
-- ============================================================================

-- For querying sessions by teacher
CREATE INDEX IF NOT EXISTS idx_grading_sessions_teacher_id 
    ON grading_sessions(teacher_id);

-- For querying sessions by rubric
CREATE INDEX IF NOT EXISTS idx_grading_sessions_rubric_id 
    ON grading_sessions(rubric_id);

-- For finding in-progress sessions
CREATE INDEX IF NOT EXISTS idx_grading_sessions_status 
    ON grading_sessions(status);

-- For progress tracking queries
CREATE INDEX IF NOT EXISTS idx_grading_sessions_created_at 
    ON grading_sessions(created_at DESC);

-- For finding sessions by contract version (batch consistency)
CREATE INDEX IF NOT EXISTS idx_grading_sessions_contract_version 
    ON grading_sessions(contract_version);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_grading_sessions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_grading_sessions_updated_at ON grading_sessions;
CREATE TRIGGER trigger_update_grading_sessions_updated_at
    BEFORE UPDATE ON grading_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_grading_sessions_updated_at();

-- ============================================================================
-- GRADING BATCHES TABLE (Optional, for batch grading)
-- ============================================================================
-- Groups multiple grading sessions for batch processing

CREATE TABLE IF NOT EXISTS grading_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- === REFERENCES ===
    teacher_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rubric_id UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    
    -- === CONTRACT REFERENCE (INV-A6) ===
    contract_version VARCHAR(50) NOT NULL,
    
    -- === BATCH INFO ===
    name VARCHAR(255),
    class_id VARCHAR(100),  -- Future: FK to classes
    
    -- === STATUS ===
    status VARCHAR(30) NOT NULL DEFAULT 'created' CHECK (
        status IN ('created', 'in_progress', 'completed', 'partially_completed', 'failed')
    ),
    
    -- === PROGRESS ===
    total_sessions INTEGER NOT NULL DEFAULT 0,
    completed_sessions INTEGER NOT NULL DEFAULT 0,
    failed_sessions INTEGER NOT NULL DEFAULT 0,
    
    -- === TIMING ===
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Link sessions to batches
ALTER TABLE grading_sessions 
    ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES grading_batches(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_grading_sessions_batch_id 
    ON grading_sessions(batch_id);

-- ============================================================================
-- VERIFICATION QUERIES
-- ============================================================================

-- Check table structure
SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_name = 'grading_sessions'
ORDER BY ordinal_position;

-- Check indexes
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE tablename IN ('grading_sessions', 'grading_batches');

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE grading_sessions IS 
    'Stores state for TestGrader Agent sessions, enabling server-side persistence and progress tracking';

COMMENT ON COLUMN grading_sessions.contract_version IS 
    'Immutable reference to the GradingRubricContract version used (INV-A6: ContractVersionLock)';

COMMENT ON COLUMN grading_sessions.state_snapshot IS 
    'Serialized GradingAgentState for session recovery after browser close';

COMMENT ON COLUMN grading_sessions.graded_test_draft_json IS 
    'Full GradedTestDraft stored for immediate access without joining graded_tests';

COMMENT ON TABLE grading_batches IS 
    'Groups grading sessions for batch processing, ensuring consistent contract_version';

