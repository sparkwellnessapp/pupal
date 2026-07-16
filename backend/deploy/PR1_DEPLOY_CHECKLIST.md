# PR-1 deploy checklist — async rubric-extraction lifecycle

> Status: **EXECUTED 2026-07-12** (agent, on Noam's explicit authorization of
> owner credentials; secrets pre-created by Noam with rotated keys — old keys
> already revoked at execution time).
> Executed: Cloud Tasks + Service Usage APIs enabled · `extraction-task-invoker`
> SA + `rubric-extraction` queue (maxAttempts=1) · run.invoker / enqueuer /
> serviceAccountUser / 3× secretAccessor bindings · migration 012 applied
> (replacing a bare create_all-generated table — see the create_all footgun
> note below) · migration 011 completed idempotently (was PARTIALLY applied:
> transcriptions.batch_id existed, grading_batches.test_count did not — prod
> batch creation was broken until this) · deployed with timeout=900/1Gi/
> secretKeyRefs/model pin, then REDEPLOYED same-day with three first-use bug
> fixes caught by the integration tests (reserved LogRecord key 'filename';
> DetachedInstanceError on the ADR-3 reuse path; naive-utcnow defaults skewing
> heartbeat staleness).
>
> ⚠️ create_all footgun (recurred during this deploy): app startup runs
> Base.metadata.create_all (database.py init_db) — a NEW ORM model gets a bare
> table auto-created (no CHECKs, no partial indexes, no ALTERs on existing
> tables) the first time the app boots before the real migration is applied.
> Apply migrations BEFORE booting code that carries new models, and treat any
> ix_*-named index on a supposedly-migrated table as this failure's signature.
>
> ✅ STRUCTURALLY CLOSED by the PR-1 follow-up (migration 013) — see below.
>
> The commands below remain as the canonical re-runnable record.

## PR-1 follow-up — schema canon (migration 013). NOT YET APPLIED.

Closes the two DDL failures this deploy hit: the bare create_all table, and
migration 011's silent PARTIAL application. Code has landed; **the migration has
not been applied to any database yet.**

1. **Apply `migrations/013_schema_migrations_ledger.sql`** — creates the
   `schema_migrations` ledger and backfills 001–012. The backfill is verified,
   not assumed: every migration's DDL artifacts were probed against the live DB
   on 2026-07-13 and confirmed (incl. 007's DROPs). Apply it to **prod and every
   dev database**.
2. **Redeploy the backend** (any normal deploy picks up the code).

What changes at boot:

- `create_all` now runs **only** when `APP_ENV` is a dev env **AND** the target
  DB has no `schema_migrations` ledger. The ledger half is load-bearing: a dev
  `.env` routinely carries `APP_ENV=development` *and* the live `DATABASE_URL`
  (that is how the integration tests run), so an APP_ENV-only gate would still
  create_all **production** from a laptop. **Applying 013 to prod is what arms
  that guard** — do it even though prod already skips via APP_ENV.
- `verify_schema_head()` set-compares the ledger to `EXPECTED_MIGRATIONS` in
  `app/database.py` and logs `SCHEMA OK: migration head 013` or a loud
  `SCHEMA MISMATCH ... NOT APPLIED` **ERROR**. It never crashes — a deploy
  landing mid-migration-window must still boot so you can finish applying.
- ⚠️ **Until 013 is applied, prod will log `SCHEMA MISMATCH: schema_migrations
  ledger is MISSING` on every boot.** That is the alarm working as designed, not
  a new fault. It goes quiet the moment 013 lands.

The rule for every future migration: **end the file with its own commit token** —
`INSERT INTO public.schema_migrations (version, note) VALUES ('NNN', '...')
ON CONFLICT DO NOTHING;` as the LAST statement — and add the version to
`EXPECTED_MIGRATIONS`. The row only lands if every statement before it landed, so
a half-applied file leaves a gap the boot check sees. A ledger that merely
recorded "011 was run" would NOT have caught 011. `tests/test_schema_canon.py`
enforces both halves.
>
> Project: `gen-lang-client-0438328890` · Region: `europe-west1` ·
> Service: `gradervision-backend`

## Ordering (breaks if reordered)

1. **[Noam, D-3a] Create Secret Manager entries FIRST** (new keys, not the
   exposed ones): `openai-api-key`, `database-url`, `langchain-api-key`.
2. **[DB] Apply migration 012** to the database (`migrations/012_rubric_extraction_jobs.sql`).
   The ORM in this tree references `rubrics.extraction_job_id` — deploying (or
   even running `tests/models` / API integration tests) before 012 fails with
   UndefinedColumn.
3. **[D-1] Infra** — enable Cloud Tasks, create queue + invoker SA:
   ```bash
   gcloud services enable cloudtasks.googleapis.com

   gcloud iam service-accounts create extraction-task-invoker \
     --display-name="Cloud Tasks → gradervision-backend invoker"

   gcloud tasks queues create rubric-extraction \
     --location=europe-west1 \
     --max-attempts=1        # our retry story is heartbeat-staleness + explicit /retry

   gcloud run services add-iam-policy-binding gradervision-backend \
     --region=europe-west1 \
     --member="serviceAccount:extraction-task-invoker@gen-lang-client-0438328890.iam.gserviceaccount.com" \
     --role="roles/run.invoker"

   # The service's runtime SA must be able to enqueue + mint OIDC tokens:
   gcloud projects add-iam-policy-binding gen-lang-client-0438328890 \
     --member="serviceAccount:588558139818-compute@developer.gserviceaccount.com" \
     --role="roles/cloudtasks.enqueuer"
   gcloud iam service-accounts add-iam-policy-binding \
     extraction-task-invoker@gen-lang-client-0438328890.iam.gserviceaccount.com \
     --member="serviceAccount:588558139818-compute@developer.gserviceaccount.com" \
     --role="roles/iam.serviceAccountUser"
   ```
4. **[D-1 + D-2 + D-3b] Deploy the current tree** with raised timeout, more
   memory, secrets by reference (never plaintext env), and the pinned model:
   ```bash
   gcloud run deploy gradervision-backend \
     --source=vivi-codebase/backend \
     --region=europe-west1 \
     --timeout=900 \
     --memory=1Gi \
     --set-secrets="OPENAI_API_KEY=openai-api-key:latest,DATABASE_URL=database-url:latest,LANGCHAIN_API_KEY=langchain-api-key:latest" \
     --set-env-vars="APP_ENV=production,GOOGLE_CLOUD_PROJECT=gen-lang-client-0438328890,GCS_BUCKET_NAME=grader-vision-pdfs-0438328890,ALLOWED_ORIGINS=https://vivi-assistant.com;https://www.vivi-assistant.com,LANGCHAIN_TRACING_V2=true,LANGCHAIN_PROJECT=lang-projects,EXTRACTION_EXECUTION_MODE=cloud_tasks,CLOUD_TASKS_LOCATION=europe-west1,CLOUD_TASKS_QUEUE=rubric-extraction,CLOUD_TASKS_INVOKER_SA=extraction-task-invoker@gen-lang-client-0438328890.iam.gserviceaccount.com,SERVICE_BASE_URL=https://gradervision-backend-588558139818.europe-west1.run.app,EXTRACTION_LLM_PROVIDER=openai,EXTRACTION_LLM_MODEL=gpt-5.5,EXTRACTION_LLM_REASONING_EFFORT=medium,EXTRACTION_LLM_MAX_TOKENS=32000"
   ```
   Notes: `^;^`-style delimiter may be needed for ALLOWED_ORIGINS commas
   (`--set-env-vars=^|^ALLOWED_ORIGINS=a,b|KEY=...`). D-2 rationale: the 5/5
   eval gate was earned at gpt-5.5@medium/32k; the code default (gpt-4o) was
   never evaluated against prompt 3.3.1-tracehdr.
5. **[Noam, D-3c] Rotate AT cutover:** only after the new revision serves
   traffic, revoke the OLD OpenAI/LangSmith keys and change the DB password;
   update the Secret Manager versions if rotation produced new values. The old
   keys sat in plaintext env and were exposed to a read-only session — treat as
   compromised.

## Post-deploy verification

- `GET /health` → 200 on the new revision.
- Submit a real DOCX via the UI → 202 within ~2s; poll shows advancing stages;
  a 6+ minute doc completes with the browser closed mid-run.
- **The job table doubles as the deploy-verification artifact:** the first
  production job row must stamp `prompt_version = 3.3.1-tracehdr`,
  `pipeline_version = 3.2.0`, and
  `llm_config = {provider: openai, model: gpt-5.5, reasoning_effort: medium, max_tokens: 32000}`.
- Kill the serving instance mid-job → status shows `stale: true` within 15 min
  → `/retry` succeeds without re-upload.
- `pytest -q` (with 012 applied) — the 7 previously-failing
  `tests/models/test_s1_models.py` round-trips go green; the 12
  `tests/api/test_extraction_jobs.py` integration tests un-skip and pass.
