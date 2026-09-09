-- 029 — pin the TRANSCRIPTION contract version on each graded test.
--
-- WHY. VER-2 already pins `rubric_contract_version` on this row, but the other
-- half of the grading input was identified only by `transcription_id`. So "what
-- did the grader actually consume?" was answerable for the rubric and merely
-- ASSUMED for the transcription — resting on LCY-1 (an approved transcription
-- is immutable and its review_json is nulled at approval) rather than on a
-- recorded fact.
--
-- The gap became load-bearing when the review surface stopped re-deriving the
-- student's answer client-side and started reading it as EVIDENCE of what was
-- graded. Evidence needs a provenance you can check, not one you infer from a
-- rule elsewhere in the system holding.
--
-- NULLABLE, deliberately and permanently. Every row written before this
-- migration has no pin and never will: back-filling one would INVENT the
-- provenance this column exists to record — asserting we know which contract
-- version was consumed when we do not. NULL means exactly "this row predates
-- the pin", and the read path treats it as unverified rather than as verified.
-- This is the same honesty the 023 note states for Ministry symbols: a value
-- that establishes identity is never adopted from a plausible match.
--
-- No index: nothing queries by it. It is provenance carried with the row and
-- read only when that row is already in hand.
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

ALTER TABLE public.graded_tests
    ADD COLUMN IF NOT EXISTS transcription_contract_version TEXT;

COMMENT ON COLUMN public.graded_tests.transcription_contract_version IS
    'The TranscriptionContract.contract_version consumed at grade time (029). '
    'NULL = the row predates the pin; never back-filled, because a guessed '
    'provenance is worse than a recorded absence.';

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('029', 'graded_tests.transcription_contract_version — pin the second half of the grading input (VER-2 symmetry)')
ON CONFLICT DO NOTHING;
