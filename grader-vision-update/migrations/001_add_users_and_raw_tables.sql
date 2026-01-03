-- =============================================================================
-- Grader Vision: User Management System Migration
-- Run this SQL in Supabase SQL Editor
-- =============================================================================

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- =============================================================================
-- 1. Create subscription_status enum type
-- =============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'subscription_status') THEN
        CREATE TYPE subscription_status AS ENUM ('trial', 'active', 'expired', 'cancelled');
    END IF;
END $$;

-- =============================================================================
-- 2. Create users table
-- =============================================================================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255),
    google_id VARCHAR(255) UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    -- Subscription fields
    subscription_status subscription_status DEFAULT 'trial' NOT NULL,
    started_trial_at TIMESTAMPTZ DEFAULT NOW(),
    started_pro_at TIMESTAMPTZ,
    
    -- Tranzila integration
    tranzila_customer_id VARCHAR(255),
    tranzila_token VARCHAR(255),
    tranzila_transaction_id VARCHAR(255),
    card_mask VARCHAR(10),
    last_payment_at TIMESTAMPTZ,
    next_payment_at TIMESTAMPTZ
);

-- Create indexes on users
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_google_id ON users(google_id);

-- =============================================================================
-- 3. Create subject_matters table with seed data
-- =============================================================================
CREATE TABLE IF NOT EXISTS subject_matters (
    id SERIAL PRIMARY KEY,
    code VARCHAR(50) UNIQUE NOT NULL,
    name_en VARCHAR(100) NOT NULL,
    name_he VARCHAR(100) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Seed subject matters
INSERT INTO subject_matters (code, name_en, name_he) VALUES
    ('computer_science', 'Computer Science', 'מדעי המחשב'),
    ('mathematics', 'Mathematics', 'מתמטיקה'),
    ('physics', 'Physics', 'פיזיקה'),
    ('chemistry', 'Chemistry', 'כימיה'),
    ('biology', 'Biology', 'ביולוגיה'),
    ('history', 'History', 'היסטוריה'),
    ('english', 'English', 'אנגלית'),
    ('hebrew', 'Hebrew', 'עברית'),
    ('literature', 'Literature', 'ספרות'),
    ('civics', 'Civics', 'אזרחות'),
    ('geography', 'Geography', 'גאוגרפיה'),
    ('arabic', 'Arabic', 'ערבית'),
    ('french', 'French', 'צרפתית'),
    ('art', 'Art', 'אמנות'),
    ('music', 'Music', 'מוזיקה'),
    ('physical_education', 'Physical Education', 'חינוך גופני'),
    ('civics', 'Civics', 'אזרחות'),
    ('chemistry', 'Chemistry', 'כימיה'),
    ('literature', 'Literature', 'ספרות'),
    ('bible studies', 'Bible Studies', 'תנך'),
    ('hebrew', 'Hebrew', 'לשון')
ON CONFLICT (code) DO NOTHING;

-- =============================================================================
-- 4. Create user_subject_matters junction table
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_subject_matters (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    subject_matter_id INTEGER REFERENCES subject_matters(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, subject_matter_id)
);

-- =============================================================================
-- 5. Create raw_rubrics table
-- =============================================================================
CREATE TABLE IF NOT EXISTS raw_rubrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    rubric_json JSONB NOT NULL,
    name VARCHAR(255),
    description TEXT,
    total_points FLOAT8,
    
    -- Extraction metadata
    source_filename VARCHAR(255),
    extraction_model VARCHAR(100),
    extraction_duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_raw_rubrics_user_id ON raw_rubrics(user_id);

-- =============================================================================
-- 6. Create raw_graded_tests table
-- =============================================================================
CREATE TABLE IF NOT EXISTS raw_graded_tests (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rubric_id UUID REFERENCES rubrics(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    student_name VARCHAR(255) NOT NULL,
    filename VARCHAR(255),
    graded_json JSONB NOT NULL,
    total_score FLOAT8 NOT NULL,
    total_possible FLOAT8 NOT NULL,
    percentage FLOAT8 NOT NULL,
    student_answers_json JSONB,
    
    -- Grading metadata
    grading_model VARCHAR(100),
    grading_duration_ms INTEGER,
    transcription_model VARCHAR(100),
    transcription_duration_ms INTEGER
);

CREATE INDEX IF NOT EXISTS idx_raw_graded_tests_user_id ON raw_graded_tests(user_id);
CREATE INDEX IF NOT EXISTS idx_raw_graded_tests_rubric_id ON raw_graded_tests(rubric_id);

-- =============================================================================
-- 7. Create share_permission enum type
-- =============================================================================
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'share_permission') THEN
        CREATE TYPE share_permission AS ENUM ('view', 'edit');
    END IF;
END $$;

-- =============================================================================
-- 8. Create rubric_shares table
-- =============================================================================
CREATE TABLE IF NOT EXISTS rubric_shares (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    rubric_id UUID REFERENCES rubrics(id) ON DELETE CASCADE NOT NULL,
    owner_user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    shared_with_user_id UUID REFERENCES users(id) ON DELETE CASCADE NOT NULL,
    permission share_permission DEFAULT 'view' NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    
    UNIQUE (rubric_id, shared_with_user_id)
);

CREATE INDEX IF NOT EXISTS idx_rubric_shares_rubric_id ON rubric_shares(rubric_id);
CREATE INDEX IF NOT EXISTS idx_rubric_shares_owner ON rubric_shares(owner_user_id);
CREATE INDEX IF NOT EXISTS idx_rubric_shares_shared_with ON rubric_shares(shared_with_user_id);

-- =============================================================================
-- 9. Add columns to existing rubrics table
-- =============================================================================
ALTER TABLE rubrics 
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS raw_rubric_id UUID UNIQUE REFERENCES raw_rubrics(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_rubrics_user_id ON rubrics(user_id);

-- =============================================================================
-- 10. Add columns to existing graded_tests table
-- =============================================================================
ALTER TABLE graded_tests
ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES users(id) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS raw_graded_test_id UUID UNIQUE REFERENCES raw_graded_tests(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_graded_tests_user_id ON graded_tests(user_id);

-- =============================================================================
-- 11. Create admin user (password: Takicer123)
-- =============================================================================
-- Note: Hash generated with bcrypt (cost 12)
INSERT INTO users (id, email, password_hash, full_name, subscription_status, started_trial_at, started_pro_at)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'tapicer.business@gmail.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewKyNiAYMyzJ/IiC',
    'Admin',
    'active',
    NOW(),
    NOW()
)
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- 12. Assign existing records to admin user
-- =============================================================================
UPDATE rubrics 
SET user_id = 'a0000000-0000-0000-0000-000000000001' 
WHERE user_id IS NULL;

UPDATE graded_tests 
SET user_id = 'a0000000-0000-0000-0000-000000000001' 
WHERE user_id IS NULL;

-- =============================================================================
-- DONE! Verify by running:
-- SELECT * FROM users;
-- SELECT * FROM subject_matters;
-- =============================================================================
