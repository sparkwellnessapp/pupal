-- 026: grading_plans — compiled GradingPlans, keyed by rubric contract hash
--      (PLAN COMPILER v2 production wiring, PLAN_production_wiring.md; owner rulings
--      W-1..W-4 and OD-W1..OD-W12, 2026-09-05/06)
--
-- WHY. grader-v5 grades against a GradingPlan — the rubric's algebra compiled
-- into discrete checks. Until now the only plan was a hand-ratified file bound
-- to ONE rubric id, so every other teacher's rubric was graded by v3. A plan is
-- a DERIVED artefact of a contract: built once per contract, hidden from the
-- teacher (W-3 — she never learns the concept), selected automatically (W-4).
--
-- KEYED BY CONTENT, NOT BY RUBRIC (W-1 / OD-W4). `contract_sha256` is the
-- sha256 of the canonical JSON of the contract with `contract_version` blanked,
-- so two compiles of identical content share one plan and spend nothing twice.
-- `rubric_id` and `contract_version` are provenance for the audit trail; the
-- rubric FK is SET NULL so a deleted rubric never deletes the plan that graded
-- its tests.
--
-- APPEND-ONLY (W-1). `plan_json` is written exactly once, by the
-- building → ready transition. A rebuild INSERTS a new row and marks the old
-- `ready` row `superseded` in the same transaction; `failed` and `superseded`
-- rows are kept as history. The partial unique index below is the rule "one
-- LIVE plan per contract" — the RGC-1 / extraction-jobs precedent: a race
-- between two writers is decided by the index, never by a read-then-write.
--
-- LIFECYCLE. queued → building → ready | failed. The CHECK states what each
-- status must carry; a firing CHECK means the writer is wrong (CLAUDE.md §0.5).
--   ready       plan_json, plan_version, built_at, wording_source present.
--               wording_source = 'segmented' (the two model stages ran) or
--               'placeholder' (the compiler's own spans — a provider outage or
--               an envelope overrun degraded the WORDING, never the algebra;
--               OD-W11). Either way the plan is valid and grading proceeds (W-2).
--   failed      only when the COMPILER itself cannot produce a plan (a
--               CompilerBug); error_message says so. The grade path then builds
--               on demand and, failing that, refuses loudly.
--   building    updated_at is the heartbeat clock (plan_job_liveness, 5-min TTL);
--               queued is clocked on created_at (90-min dispatch backstop).
--
-- Idempotent: re-running this whole file is always the answer (013 convention).

CREATE TABLE IF NOT EXISTS public.grading_plans (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rubric_id        UUID REFERENCES public.rubrics(id) ON DELETE SET NULL,
    contract_version TEXT NOT NULL,
    contract_sha256  TEXT NOT NULL,
    status           TEXT NOT NULL
                     CHECK (status IN ('queued', 'building', 'ready', 'failed', 'superseded')),
    plan_version     TEXT,
    plan_json        JSONB,
    skeleton_json    JSONB,
    compiler_version TEXT,
    segmenter_model  TEXT,
    router_model     TEXT,
    wording_source   TEXT CHECK (wording_source IN ('segmented', 'placeholder')),
    cost_usd         NUMERIC(10, 4) NOT NULL DEFAULT 0,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    built_at         TIMESTAMPTZ,
    CONSTRAINT grading_plans_status_consistency CHECK (
        (status = 'ready'
            AND plan_json IS NOT NULL AND plan_version IS NOT NULL
            AND built_at IS NOT NULL AND wording_source IS NOT NULL)
     OR (status = 'superseded' AND plan_json IS NOT NULL)
     OR (status = 'failed' AND error_message IS NOT NULL)
     OR (status IN ('queued', 'building'))
    )
);

-- One LIVE plan per contract. failed / superseded rows are history and coexist.
CREATE UNIQUE INDEX IF NOT EXISTS idx_grading_plans_one_live_per_contract
    ON public.grading_plans (contract_sha256)
    WHERE status IN ('queued', 'building', 'ready');

CREATE INDEX IF NOT EXISTS idx_grading_plans_rubric
    ON public.grading_plans (rubric_id, created_at DESC);

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('026', 'grading_plans — compiled GradingPlans keyed by contract hash (PLAN COMPILER v2, production wiring)')
ON CONFLICT DO NOTHING;
