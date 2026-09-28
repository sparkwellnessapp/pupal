-- 035 — the plan cache keys on (contract, config), and a graded test pins its plan
--       (grader-v6 §5.7, amendment AM-G6; owner re-numbered it 035 behind SEC-1's 034).
--
-- WHY. grading_plans (026) holds ONE live plan per contract hash, because until now
-- one planner existed. grader-v6 plans the same contract differently (a different
-- compiler, planner model, prompt and subject pack), and during rollout both kinds
-- must coexist for the same contract: a v5 grade keeps reading its v5 plan while v6
-- plans are built beside it. So the key becomes (contract_sha256, config_hash).
-- The contract half is unchanged — still the CONTENT hash with `contract_version`
-- blanked (OD-W4, `plan_store.contract_sha256`), so a recompile of unchanged
-- content still reuses its plan.
--
-- WHAT, statement by statement (idempotent — re-running the file is the answer):
--   1. grading_plans.config_hash — every input that decides a plan other than the
--      contract (§3.5). EVERY existing row is a v5 plan, so they all get ONE
--      constant v5 key: 'v5' (`plan_store.V5_CONFIG_HASH` — the only spelling in
--      Python, pinned equal to this file by tests/services/test_plan_cache.py).
--      The DEFAULT is set BEFORE the backfill and stays: a still-running pre-035
--      revision inserts without naming the column and must keep landing v5 rows
--      during the deploy window. A v6 key is a sha256 hex digest, so it can never
--      collide with the literal.
--   2. grading_plans.plan_hash — the sha256 of a v6 plan's terminals + checks (§3.5).
--      NULL on every v5 row (a v5 plan has no plan_hash) and never back-filled.
--   3. The live-row rule moves to the new key. The NEW index is created FIRST and
--      the old one dropped SECOND: the new rule is strictly weaker than the old
--      (every row set the old index admits, the new one admits too), so the two can
--      coexist and there is never a moment with no uniqueness at all.
--   4. graded_tests.plan_hash — the plan a v6 draft was graded against. NULLABLE and
--      never back-filled: NULL means "a v5 / pre-035 grade", and a guessed pin is
--      worse than a recorded absence (029's rule).
--
-- No table is created here, so SEC-1's ENABLE ROW LEVEL SECURITY rule has nothing
-- to cover; both tables already have RLS on (034).

BEGIN;

-- 1. config_hash: add, default, backfill, then NOT NULL (this order is safe even
--    when each statement autocommits: a row inserted between the ADD and the
--    DEFAULT is caught by the backfill).
ALTER TABLE public.grading_plans
    ADD COLUMN IF NOT EXISTS config_hash TEXT;

ALTER TABLE public.grading_plans
    ALTER COLUMN config_hash SET DEFAULT 'v5';

UPDATE public.grading_plans
    SET config_hash = 'v5'
    WHERE config_hash IS NULL;

ALTER TABLE public.grading_plans
    ALTER COLUMN config_hash SET NOT NULL;

-- 2. plan_hash on the plan row.
ALTER TABLE public.grading_plans
    ADD COLUMN IF NOT EXISTS plan_hash TEXT;

-- 3. One LIVE plan per (contract, config). failed / superseded rows stay history.
CREATE UNIQUE INDEX IF NOT EXISTS idx_grading_plans_one_live_per_contract_config
    ON public.grading_plans (contract_sha256, config_hash)
    WHERE status IN ('queued', 'building', 'ready');

DROP INDEX IF EXISTS public.idx_grading_plans_one_live_per_contract;

-- 4. The pin on the graded test.
ALTER TABLE public.graded_tests
    ADD COLUMN IF NOT EXISTS plan_hash TEXT;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('035', 'plan cache keyed by (contract_sha256, config_hash) + grading_plans.plan_hash + graded_tests.plan_hash (grader-v6 AM-G6)')
ON CONFLICT DO NOTHING;

COMMIT;
