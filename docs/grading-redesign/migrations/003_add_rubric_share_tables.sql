-- Migration: Add rubric share tokens and history tables
-- Run this SQL in Supabase SQL Editor
-- Created: 2026-01-14

-- =============================================================================
-- 1. rubric_share_tokens table
-- =============================================================================

CREATE TABLE IF NOT EXISTS rubric_share_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token VARCHAR(64) NOT NULL UNIQUE,
    
    -- Source rubric
    rubric_id UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    sender_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Recipient
    recipient_email VARCHAR(255) NOT NULL,
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    
    -- Generated PDF
    generated_pdf_gcs_path VARCHAR(500),
    
    -- Copied rubric after acceptance
    copied_rubric_id UUID REFERENCES rubrics(id) ON DELETE SET NULL
);

-- Index for token lookup (frequently queried)
CREATE INDEX IF NOT EXISTS idx_rubric_share_tokens_token ON rubric_share_tokens(token);

-- Index for finding shares by rubric
CREATE INDEX IF NOT EXISTS idx_rubric_share_tokens_rubric_id ON rubric_share_tokens(rubric_id);


-- =============================================================================
-- 2. rubric_share_history table
-- =============================================================================

CREATE TABLE IF NOT EXISTS rubric_share_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rubric_id UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    sender_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Recipient
    recipient_email VARCHAR(255) NOT NULL,
    
    -- Status timestamps
    shared_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    accepted_at TIMESTAMP WITH TIME ZONE,
    revoked_at TIMESTAMP WITH TIME ZONE,
    
    -- Link to token
    share_token_id UUID REFERENCES rubric_share_tokens(id) ON DELETE SET NULL
);

-- Index for rubric history lookup
CREATE INDEX IF NOT EXISTS idx_rubric_share_history_rubric_id ON rubric_share_history(rubric_id);


-- =============================================================================
-- Verification
-- =============================================================================

-- Check tables were created
SELECT 
    table_name 
FROM information_schema.tables 
WHERE table_schema = 'public' 
  AND table_name IN ('rubric_share_tokens', 'rubric_share_history');
