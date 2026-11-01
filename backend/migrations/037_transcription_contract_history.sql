-- 037 — a teacher's correction of one answer at the grading gate (SRG, owner rulings
--       2026-11-01, D1 = A).
--
-- WHAT. LCY-1 ("an approved transcription is read-only") becomes APPEND-ONLY. When she
-- corrects an answer while reviewing a grade, `services/scope_regrade.py` freezes a NEW
-- transcription contract (fresh contract_version), appends the contract it supersedes to
-- `transcriptions.contract_history`, and moves `contract_json` forward — in the same
-- transaction that extends the graded-test chain with the regraded draft, pinned to the
-- new version (VER-3). Nothing is overwritten: the history is the audit trail and the
-- original approved contract is its first entry.
--
--   contract_history  jsonb NULL — a list of {contract, superseded_at, superseded_by,
--                     reason, answer_key, graded_test_id}. NULL = never corrected (every
--                     existing row; no backfill — an absent history is the truth).
--
-- WHY A COLUMN, NOT A TABLE. The history is part of the transcription and dies with it:
-- a column goes with the row on purge (PII registry: DELETED_WITH_ROW) and needs no new
-- foreign key into the student graph, no erasure-plan step and no ordering rule.
--
-- No CHECK changes: `transcriptions_approval_consistency` constrains status/contract
-- presence, which a correction never touches.
--
-- Idempotent; one transaction: the column and its commit token, or neither.

BEGIN;

ALTER TABLE public.transcriptions ADD COLUMN IF NOT EXISTS contract_history jsonb NULL;

INSERT INTO public.schema_migrations (version, note)
VALUES ('037', 'transcriptions.contract_history — LCY-1 append-only for grading-gate answer corrections (SRG)')
ON CONFLICT DO NOTHING;

COMMIT;
