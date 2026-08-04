-- ============================================================================
-- 014 — transcriptions.review_json: the teacher review overlay
--        (batch transcription review, Phase 1)
--
-- The teacher's persisted working copy of a transcription review: a FULL
-- answer snapshot + the chosen student, saved while the transcription is
-- still in status='transcribed'. Application rules (enforced in the PATCH
-- /api/v0/transcriptions/{id}/review endpoint, not by DDL):
--   * writable only while status='transcribed' (409 otherwise);
--   * nulled inside the same UPDATE that performs the
--     'transcribed'→'approved' transition — part of the transition write,
--     never a mutation of an approved row, so LCY-1 is untouched;
--   * a non-null review_json excludes the row from accept_clean's bulk set
--     (teacher-touched ⇒ not "clean").
-- The chosen student lives INSIDE this JSON: transcriptions_approval_consistency
-- forbids writing the student_id COLUMN before approval.
--
-- Idempotent: re-running this whole file is always the answer.
-- ============================================================================

ALTER TABLE public.transcriptions
    ADD COLUMN IF NOT EXISTS review_json JSONB;

-- Commit token — LAST statement, per the migration-013 convention.
INSERT INTO public.schema_migrations (version, note)
VALUES ('014', 'transcriptions.review_json — teacher review overlay (batch review Phase 1)')
ON CONFLICT (version) DO NOTHING;
