-- =============================================================================
-- Add New User: Viviana Steiman
-- Run this in Supabase SQL Editor
-- =============================================================================

-- Create the new user
-- Email: vivianasteiman@yahoo.com
-- Password: NoamAluf (bcrypt hashed)
INSERT INTO users (id, email, password_hash, full_name, subscription_status, started_trial_at, started_pro_at)
VALUES (
    'b0000000-0000-0000-0000-000000000002',
    'vivianasteiman@yahoo.com',
    '$2b$12$8b4W9VI14Sagp9IWtbv2Gu1ErYZiC.IqptL1fAMcfjUt8gvdKf4km',
    'Viviana Tapicer',
    'active',
    NOW(),
    NOW()
)
ON CONFLICT (email) DO NOTHING;

-- Assign ALL existing rubrics to this user (in addition to admin)
-- This makes her a co-owner of existing rubrics
UPDATE rubrics 
SET user_id = 'b0000000-0000-0000-0000-000000000002' 
WHERE user_id IS NULL OR user_id = 'a0000000-0000-0000-0000-000000000001';

-- Assign ALL existing graded_tests to this user
UPDATE graded_tests 
SET user_id = 'b0000000-0000-0000-0000-000000000002' 
WHERE user_id IS NULL OR user_id = 'a0000000-0000-0000-0000-000000000001';

-- Verify the user was created
SELECT id, email, full_name, subscription_status, created_at FROM users;

-- Verify rubrics are assigned
SELECT id, name, user_id FROM rubrics LIMIT 10;
