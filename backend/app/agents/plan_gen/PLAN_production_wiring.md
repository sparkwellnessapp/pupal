# PLAN — grader-v5 in production with compiled plans ("pin now regardless")

**Owner instruction (2026-09-05):** pin production to grader-v5 with the new plan-generation
architecture, with rulings W-1..W-4 below. **Status:** DRAFT — awaiting rulings on OD-W1..OD-W12
and approval. **Governs:** `PR_plan_compiler_v2.md` §9's "no production wiring" fence is lifted by
this instruction; everything else in the PR stands.

The concern I raised and the owner reaffirmed over: no A3 number exists for this architecture,
and A1/A2 have never run. Recorded in `TRACKER_plan_compiler_v2.md`; this plan ships anyway,
with A3 scheduled after (§10).

---

## 0. Rulings received (the spec)

| # | Ruling | Consequence in this plan |
|---|---|---|
| W-1 | `grading_plans`, append-only, keyed by rubric contract hash, migration 026 | §3 DDL; a `ready` row's `plan_json` is never rewritten; a rebuild is a NEW row that supersedes |
| W-2 | Built at rubric compile; the substitution policy guarantees a plan even if the model misbehaves | §4: enqueue on every contract write; §5: the builder can never fail to produce a valid plan |
| W-3 | Teacher never sees it; auto-accept; the concept is hidden | No UI, no annotation, no review gate; H-4 ratification does not exist in production |
| W-4 | v5 selected ALWAYS — every rubric will have a plan; no live users yet | §6: `grader_kind_for` becomes "v5 unless the emergency rollback knob says v3"; the file-based pilot pin retires |

---

## 1. Deutsch form

**Data.** Production grades with grader-v3 (OpenAI) because grader-v5 needs a plan and only one
hand-ratified plan exists, bound by rubric id to an exam that is not in production. The compiler
now produces a valid plan for any contract in milliseconds; the two wording stages are built and
cost ≈ $0.10–0.30 per rubric.

**Theory under criticism.** "A plan is a ratified artefact per exam" (the plan-gen spec's H-4). It
made v5 unreachable for every teacher but one.

**Conjecture.** A plan is a *derived artefact of a contract*: built once per contract hash, stored
next to nothing the teacher edits, hidden, and selected automatically. Grading reads it the way it
reads the contract.

**Criticism.** Hard to vary: the store is keyed by exactly the thing the plan is a function of.
New contradictions: (i) the build is stochastic in wording and costs money — bounded by the
substitution policy and an envelope; (ii) the build takes 1–2 minutes and rubric compile is a
synchronous request — solved by the job substrate the codebase already has; (iii) a grade can
arrive before its plan is ready — §6.2 says what happens; (iv) accuracy is unmeasured — A3 is
scheduled, not skipped.

---

## 2. Architecture

```
teacher saves / updates / compiles a rubric  (3 write sites, one helper)
        │  commit → enqueue PLAN_BUILD job (Cloud Tasks; inline in dev)
        ▼
grading_plans row  queued → building → ready | failed        (CAS, heartbeat, liveness)
        │
        │  build = compile (pure) → route (Sonnet 5) → segment (Haiku 4.5) → assemble → validate
        │          any stage's failure → substitution → the plan is STILL ready (wording_source tells)
        ▼
grade job (run_grading) → plan for the rubric's contract hash:
        ready   → grader-v5 with it
        building→ wait (bounded) for the builder
        absent / failed / stale-building → build IN PLACE (CAS claims the row), then grade
```

One concept, one place: `app/services/plan_store.py` owns the row lifecycle and the contract hash;
`app/services/plan_build_runner.py` owns the build; `grader_selection.build_grader` stays the ONLY
place production decides which grader runs.

---

## 3. Migration 026 — `grading_plans`

```sql
CREATE TABLE IF NOT EXISTS public.grading_plans (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rubric_id        UUID REFERENCES public.rubrics(id) ON DELETE SET NULL,   -- provenance, not identity
    contract_version TEXT NOT NULL,          -- the UUID inside contract_json, for the audit trail
    contract_sha256  TEXT NOT NULL,          -- THE KEY (W-1): canonical-JSON hash, see OD-W4
    status           TEXT NOT NULL CHECK (status IN ('queued','building','ready','failed','superseded')),
    plan_version     TEXT,                   -- "<rubric_id>/compiled-<sha[:12]>"
    plan_json        JSONB,                  -- the frozen GradingPlan; NEVER rewritten
    skeleton_json    JSONB,                  -- flags + provenance for forensics (hidden from her)
    compiler_version TEXT,
    segmenter_model  TEXT,
    router_model     TEXT,
    wording_source   TEXT CHECK (wording_source IN ('segmented','placeholder')),
    cost_usd         NUMERIC(10,4) NOT NULL DEFAULT 0,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),   -- the building heartbeat clock
    built_at         TIMESTAMPTZ,
    CONSTRAINT grading_plans_status_consistency CHECK (
        (status = 'ready'  AND plan_json IS NOT NULL AND plan_version IS NOT NULL
                           AND built_at IS NOT NULL AND wording_source IS NOT NULL)
     OR (status = 'superseded' AND plan_json IS NOT NULL)
     OR (status = 'failed' AND error_message IS NOT NULL)
     OR (status IN ('queued','building'))
    )
);
-- one LIVE plan per contract (the RGC-1 / extraction-jobs precedent); failed and superseded rows stay
CREATE UNIQUE INDEX IF NOT EXISTS idx_grading_plans_one_live_per_contract
    ON public.grading_plans (contract_sha256) WHERE status IN ('queued','building','ready');
CREATE INDEX IF NOT EXISTS idx_grading_plans_rubric ON public.grading_plans (rubric_id, created_at DESC);
INSERT INTO public.schema_migrations (version, note) VALUES
  ('026', 'grading_plans — compiled GradingPlans keyed by contract hash (PLAN COMPILER v2, production)')
ON CONFLICT DO NOTHING;
```

Plus: `"026"` in `database.EXPECTED_MIGRATIONS`; the partial index in `EXPECTED_PARTIAL_INDEXES`
(the predicate is load-bearing — the 023 lesson); ORM `app/models/grading_plan.py`; the CHECK is
correct and a firing means the writer is wrong (§0.5).

**Append-only (W-1):** `plan_json` is written exactly once, by the `building → ready` transition.
A rebuild (OD-W11) inserts a new row and marks the old `ready` row `superseded` in the same
transaction. Lookup = the one row with `status = 'ready'` for the hash.

---

## 4. Build trigger — at rubric compile (W-2)

The three writers of `rubrics.contract_json` (`save_ontology_draft`, `update_rubric_draft`,
`compile_rubric` in `rubric_management_service.py`) are followed, in their ENDPOINTS after the
commit, by one helper `ensure_plan_for_contract(rubric)`:

1. hash the contract (§7); if a `ready`/`building`/`queued` row exists for the hash → nothing
   (a re-save of an unchanged rubric costs nothing — the hash is the point of W-1);
2. else INSERT `queued` (the partial unique index makes a race a no-op, like extraction submit);
3. commit, close the session, `enqueue_job(PLAN_BUILD_KIND, row.id)` — enqueue failure is logged,
   never propagated: the queued row is durable and the grade path builds on demand (§6.2).

Nothing about this reaches the response: the teacher's save is as fast as today (W-3).

`rubric_generator.py`'s five unauthenticated duplicate routes (B-28) do not get the helper — they
are unreachable by construction and retiring them is not this plan.

---

## 5. The build — `plan_build_runner.run_plan_build(row_id)`

Mirrors `rubric_extraction_runner` (CAS, short sessions, heartbeat) — a durable job, never a
BackgroundTask.

1. CAS `queued → building` (duplicate delivery = no-op, 200).
2. Load the rubric contract; **Stage 1** `compile_contract` (pure; `CompilerBug` → the row fails
   loudly — a compiler defect, not a rubric problem, and the grade path then falls back per §6.2).
3. **Stage 2b** `route_monoliths` (Sonnet 5, `ROUTE_MIN_POINTS` per OD-W5) — a terminal whose
   routing fails keeps its single check (already the module's policy).
4. **Stage 2** `segment_skeleton` (Haiku 4.5) — a slot whose wording fails twice gets its span
   substituted (already the module's policy).
5. **Assemble** with full provenance; run `validate_plan` against the contract (V1–V12 + V9 on the
   scope corpora). A validator error here is impossible on the honest path (the substitution text
   is the A0 text that passed); if it fires, fall back to the whole placeholder plan and record
   `wording_source='placeholder'`, `error_message` with the errors — the row is still `ready`.
6. Envelope per build `PLAN_BUILD_ENVELOPE_USD` (default 1.00; both eval exams ≈ $0.10–0.16):
   on `EnvelopeExceeded`, the slots not yet worded take the placeholder → still `ready`.
7. Provider outage / auth failure / timeout on either model → placeholder plan, `ready`,
   `wording_source='placeholder'`, `error_message` says why. **The row reaches `failed` only when
   the COMPILER cannot produce a plan** (a `CompilerBug`) — W-2's guarantee, made structural.
8. Heartbeat on `updated_at` every ~30 s while building; liveness rule (§8) reaps a dead builder.

Cost is accounted per call from the registry price cards (`cost_usd(Usage, PriceCard)`) and
written to the row. The build never logs the plan text (it is hidden, W-3) — only ids, counts,
cost and flags.

---

## 6. Grading — v5 always (W-4)

### 6.1 `grader_selection`
- `grader_kind_for(rubric_id)` → `"v5"` unless `GRADER_ARCHITECTURE=v3` (the emergency rollback
  knob; default flips to `v5`). `grader_model_key` / `grader_model_provider` stay the model pin
  (`claude-sonnet-5` / anthropic). `grader_plan_path` and `grader_plan_rubric_id` are RETIRED
  with `app/agents/grader/plans/` (OD-W7) — the store is the only source.
- `build_grader(...)` gains the plan as an argument (the runner resolves it): it still validates
  the plan against the compiled test before constructing the client (the second guard stays —
  a ready plan for a hash that no longer matches this contract is a wiring bug and must be loud).

### 6.2 `grading_runner._do_grade`, before step 5
`plan_store.resolve_plan_for_grade(contract_json)`:
- `ready` → use it.
- `building` with a fresh heartbeat → wait, polling, up to `PLAN_WAIT_S` (OD-W3) — the row budget
  is extended by the wait actually spent.
- absent / `failed` / `building` with a STALE heartbeat → **build in place** inside the grade
  job: INSERT `queued` (or CAS the stale row to `building` under this worker), run
  `run_plan_build` synchronously, then grade. The grading Cloud Task's 900 s deadline holds
  1–2 min of build plus a normal grade; `_row_budget_s` adds the measured build time.
- Whatever happened, the draft stamps `plan_version` (already a `GradedTestDraft` field) and the
  row's `wording_source` lands in the draft's provenance (a placeholder-worded grade must be
  distinguishable in the eval ledger even though she never sees it).

Two grades of the same never-graded rubric arriving together: the partial unique index lets
exactly one INSERT `queued`; the other sees `building`, waits, and uses the result.

---

## 7. Contract identity — the hash (OD-W4, needs ratification)

`plan_store.contract_sha256(contract_json: dict) -> str` =
`sha256(json.dumps(contract_json, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))`
over the JSONB as stored (i.e. `GradingRubricContract.model_dump(mode="json")`). This is the
canonicalisation rule OD-G1.4 declined to invent for the pilot; pinned by a test that hashes a
contract through two serialisation paths and demands one digest. Note: `contract_version` (a fresh
UUID per compile) is INSIDE the JSON, so two compiles of an identical draft produce different
hashes — see OD-W4 for the choice.

The eval suite keeps hashing contract FILE bytes; the two pins never meet.

---

## 8. Job substrate, liveness, internal route

- `cloud_tasks_service.PLAN_BUILD_KIND` — `internal_path="/internal/plan-jobs/{job_id}/run"`,
  queue per OD-W2, `execution_mode=jobs_execution_mode`, `inline_runner=run_plan_build`.
- `POST /internal/plan-jobs/{id}/run` in a new `app/api/v0/plan_jobs.py` (`verify_task_request`,
  always 200 after auth, `include_in_schema=False`) registered in `main.py` next to the other
  internal routers.
- `plan_job_liveness` = one `LivenessRule` instance: `queued` on `created_at` (90-min dispatch
  backstop, like grading), `building` on `updated_at` (heartbeat 30 s, TTL 5 min). Expiry →
  `failed` with a reason; the next grade builds on demand; startup sweep includes it.

---

## 9. Frontend — the `counted` mirror (OD-17, now in scope)

A compiled production plan can carry a `counted` check (any trace-table criterion). The
review surface's pricing mirror (`frontend/src/lib/pricing.ts`, `CheckKind`) and `CheckRow` know
`required | tariff | note_only` only, so a counted terminal would mis-mirror the pricer.
- `pricing.ts`: `counted` branch = `points × units_correct / unit_count`, snapped with the
  terminal, evidence-gated like `required`; `CheckKind` gains `'counted'`.
- `CheckRow`: render «k מתוך N» beside the verdict for a counted check (the teacher sees a grade
  breakdown, never the word "plan" — W-3 holds; checks were already visible under PR-G1).
- `pricing_vectors.json` gets one counted vector (12 × 15/17 → 10.5) so backend and frontend
  are pinned to the same arithmetic; `api-types.ts` regen (already in the working tree).

---

## 10. Measurement — A3 after the pin

The pin ships without A3 (owner's call, recorded). Immediately after deploy: run A1/A2 on the
two eval exams (≈ $0.25, envelopes as ratified), then A3 (both exams, k=3 on the pinned grader,
≈ $6 — envelope to confirm) and report against the same bars the 2026-08-31 verdict used. If the
compiled hobby plan grades WORSE than the hand plan on K1, that is a finding for a ruling, not a
silent revert.

---

## 11. Tests (zero provider calls)

- `tests/services/test_plan_store.py` — hash canonicalisation (two paths, one digest);
  queued/building/ready/superseded/failed transitions; the unique-live-row race; `superseded`
  on rebuild; the CHECK constraint firing on a bad write (Vivi-Test DB).
- `tests/services/test_plan_build_runner.py` — fake model: full build → `segmented`; segmenter
  outage → `placeholder` still `ready`; envelope exceeded → partial substitution; `CompilerBug`
  → `failed`; heartbeat advances; duplicate delivery no-op.
- `tests/services/test_grader_selection.py` — rewritten for W-4: v5 by default, v3 only under
  the rollback knob, the fit-guard retained; `tests/agents/test_grader_pin.py` updated.
- `tests/services/test_grading_runner.py` — resolve: ready / wait-then-ready / stale-building →
  build in place / failed → build in place; budget extension; `plan_version` + wording source
  stamped.
- `tests/api/test_rubric_plan_trigger.py` — each of the three write endpoints leaves exactly one
  `queued` row per new hash and none for an unchanged contract (inline mode, fake model).
- `tests/test_schema_canon.py` — 026 in the ledger, the partial index with its predicate.
- `tests/api/test_plan_jobs_internal.py` — auth rejection 403, 200 on no-op.
- Frontend: `pricing.test.ts` counted vector parity; `CheckRow` render test.

## 12. Deploy checklist (production is `gradervision-backend`, europe-west1)

1. Secret Manager `anthropic-api-key` → env `ANTHROPIC_API_KEY` (**absent today** — verified
   2026-09-05: the service has OPENAI/LANGCHAIN/DATABASE secrets only). Without it every v5 grade
   and every build fails to a placeholder/failed row.
2. Apply migration 026; boot log must say `SCHEMA OK`.
3. Env: `GRADER_ARCHITECTURE` unset (code default becomes v5) or `=v3` for rollback;
   `GRADER_MAX_CONCURRENT_SCOPES` per OD-W12; `PLAN_BUILD_ENVELOPE_USD` default.
4. Queue per OD-W2 (reuse `grading-jobs` needs no infra).
5. Smoke on the Vivi-Test DB first: save a rubric → row `ready` with cost; grade one test →
   draft with `plan_version`; then production.
6. Rollback = `GRADER_ARCHITECTURE=v3` (env flip, no data change); plan rows are inert under v3.

### 12.1 Runbook (verified against the live project 2026-09-06; names only were read)

```bash
P=gen-lang-client-0438328890; R=europe-west1; S=gradervision-backend

# 1. the secret (does NOT exist yet: secrets are database-url, langchain-api-key, openai-api-key)
printf '%s' "$ANTHROPIC_KEY" | gcloud secrets create anthropic-api-key --data-file=- --project $P
gcloud secrets add-iam-policy-binding anthropic-api-key --project $P \
  --member "serviceAccount:$(gcloud run services describe $S --region $R --project $P --format 'value(spec.template.spec.serviceAccountName)')" \
  --role roles/secretmanager.secretAccessor

# 2. the queue — mirrors grading-jobs (20 concurrent, maxAttempts 3, 10s min backoff, RUNNING)
gcloud tasks queues create plan-build-jobs --location $R --project $P \
  --max-concurrent-dispatches 20 --max-attempts 3 --min-backoff 10s

# 3. migration 026 on the PRODUCTION database (idempotent file; the ledger row lands last)
#    psql "$PROD_DATABASE_URL" -f backend/migrations/026_grading_plans.sql
#    then: python scripts/schema_attest.py  → must list 026 and idx_grading_plans_one_live_per_contract

# 4. deploy with the new env + secret (existing env preserved; GRADER_ARCHITECTURE defaults to v5 in code)
gcloud run deploy $S --source backend --project $P --region $R \
  --update-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest \
  --update-env-vars GRADER_MAX_CONCURRENT_SCOPES=8,CLOUD_TASKS_PLAN_BUILD_QUEUE=plan-build-jobs

# 5. smoke: boot log says "SCHEMA OK: migration head 026"; save a rubric as a test user →
#    a grading_plans row goes queued → building → ready (cost_usd > 0, wording_source = segmented);
#    grade one test → draft_json.plan_version starts with "<rubric_id>/compiled-", plan_wording_source = segmented.
# 6. rollback at any point: gcloud run services update $S --region $R --project $P --update-env-vars GRADER_ARCHITECTURE=v3
```

## 13. Phases

| Phase | Delivers | Gate |
|---|---|---|
| W0 | migration 026 + ORM + ledger/canon tests; `plan_store` (hash, lifecycle) | schema canon + store tests green on Vivi-Test |
| W1 | `plan_build_runner` (fake-model tested), job kind, internal route, liveness, compile-time trigger | services + api tests green; inline mode builds a real row from a fake model |
| W2 | `grader_selection` v5-always + retire the file pin; runner resolve/wait/build-in-place | selection + runner tests; `import app.main`; full backend batteries |
| W3 | frontend counted mirror + vectors + api-types | vitest + tsc |
| W4 | deploy (secret, migration, env), Vivi-Test smoke, production smoke on a test user | boot `SCHEMA OK`; one real grade lands with `plan_version` |
| W5 | A1/A2 then A3 on the eval exams; report | numbers on record |

Each phase: tests, then a code review pass, then the next (the standing protocol).

---

## 14. Open decisions — need your ruling (recommendation first)

- **OD-W1 · When the build runs.** *(a) Recommended:* enqueue at compile AND build in place at
  grade time when no ready plan exists — both paths, one runner. (b) Only at compile (a grade
  before the plan is ready must wait or fail). (c) Only on demand at first grade (adds 1–2 min to
  the first grade of every rubric, zero infra).
- **OD-W2 · Queue.** *Recommended:* reuse `grading-jobs` (maxConcurrentDispatches=20, 900 s
  deadline, maxAttempts=3 — the CAS makes redelivery a no-op). Alternative: a new
  `plan-build-jobs` queue (an infra step, a separate dial).
- **OD-W3 · A grade arriving while the plan is `building`.** *Recommended:* wait up to 240 s on
  a fresh heartbeat, then treat a stale builder as dead and build in place. Never fail the grade
  because the plan is late. Alternative: fail the row (retryable through the revision chain).
- **OD-W4 · The hash.** *Recommended:* canonical JSON of `contract_json` as in §7 — which means a
  recompile of an unchanged draft still gets a NEW plan (its `contract_version` UUID differs),
  ≈ $0.10–0.30 each. Alternative: hash the contract with `contract_version` blanked, so identical
  content reuses the plan (zero spend on re-saves) — costs one line and a documented exception.
- **OD-W5 · Routing threshold in production** (= OD-24). *Recommended:* `P ≥ 3`, the measured
  evidence (seven bagrut misses, both hobby hand-plan divergences). Alternative: keep 4 as
  ratified and accept coarser plans on 3-point criteria.
- **OD-W6 · Verifier prompt version under `counted`** (= OD-18). *Recommended:* stamp
  `grader-v5.4` — system prompt byte-identical to v5.3, the counted rule in the user message
  only when a counted check exists. For plans without counted checks the messages are identical
  to what was measured, so the 2026-08-31 numbers carry; the stamp tells the truth about what
  ran. Alternative: keep `grader-v5.3` and accept that one stamp now covers two message shapes.
- **OD-W7 · Retire the file-based pin.** *Recommended:* retire `grader_plan_path`,
  `grader_plan_rubric_id`, `app/agents/grader/plans/` and their tests; keep
  `GRADER_ARCHITECTURE` as the single rollback knob (default v5).
- **OD-W8 · Frontend counted mirror in this PR.** *Recommended:* yes (§9) — otherwise a counted
  terminal renders a wrong number on the review screen the day a teacher saves a trace-table
  rubric. Alternative: defer and refuse to compile `counted` in production until the mirror
  lands (a compiler knob — coarser plans on those terminals).
- **OD-W9 · Existing rubrics (6 in the census).** *Recommended:* nothing special — the first
  grade builds on demand (OD-W1a). Alternative: a one-off backfill script now (≈ $1.50), which
  I would write anyway as an operator tool.
- **OD-W10 · Per-build envelope.** *Recommended:* `$1.00` per rubric (10× the measured eval
  cost); overrun → placeholder for the rest, still `ready`, flagged.
- **OD-W11 · Placeholder-worded plans.** A provider outage yields a `ready` plan with
  `wording_source='placeholder'` — valid, coarser wording, grading proceeds (W-2). *Recommended:*
  no automatic rebuild in this PR; the next contract write builds fresh; an operator tool can
  rebuild and supersede. Alternative: a rebuild attempt on the next grade of that rubric.
- **OD-W12 · Anthropic concurrency.** The grader dial is 16 scopes; Sonnet 5's request rate on
  our tier is unmeasured in production. *Recommended:* ship `GRADER_MAX_CONCURRENT_SCOPES=8`
  and re-measure the latency profile (`eta.py`, `_row_budget_s` follow the dial).

Not decisions, just facts you should hold: the pin ships with **no A3 number**; the segmenter and
router have never run against a real model; the first real runs happen inside production builds
(W-2's substitution policy is what makes that safe); every plan row is hidden and append-only.
