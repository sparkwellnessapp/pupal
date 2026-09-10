"""
Configuration settings for Test Grader AI.
Loads settings from environment variables and .env file.
"""
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings
from typing import List, Optional


_SECRET_NAME_PARTS = ("api_key", "secret", "token", "password",
                      "credentials_json", "database_url", "service_account")


def _is_secret_name(name: str) -> bool:
    """Secret-shaped by NAME. `*_file` is excluded — those are paths."""
    if name.endswith("_file"):
        return False
    return any(part in name for part in _SECRET_NAME_PARTS)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI settings
    openai_api_key: SecretStr
    openai_model: str = "gpt-4o"  # For text grading

    # [PR-G2] Per-scope wall for a grading LLM attempt. The production
    # GraderAgent used to construct ChatOpenAI with NO timeout, which makes
    # LangChain pass timeout=None explicitly -> httpx Timeout(None) -> no
    # bound at all, and a `grading` row with no exit. Matches
    # llm_factory.GRADER_LLM_TIMEOUT_S so the seam-constructed and default
    # paths are bounded alike.
    grader_llm_timeout_s: float = 240.0
    # Slack added to the row-level budget on top of timeout x waves, to
    # cover compile + assembly + one GA-3 retry landing in the last wave.
    grader_row_grace_s: float = 120.0

    # Disable SQLAlchemy connection pooling (NullPool). TEST-ONLY knob,
    # default OFF: production keeps its QueuePool. Pooled asyncpg
    # connections outlive a test and stay registered with the Windows
    # proactor, so the app lifespan's loop-close hangs on an orphaned op at
    # session teardown — every test passes and the process never exits.
    db_disable_pooling: bool = False

    # [PR-G1(a), the owed R-4 pilot-bridge seam] Which grader production
    # runs. DARK AND DEFAULT-OFF: with these unset the selection is the
    # historical v3 path byte-for-byte, so landing the seam cannot move
    # production behaviour — flipping them does, deliberately.
    # The ratified pin (EVAL_REPORT §9.3, k=5 confirmed, k=2 re-verified
    # 2026-08-31): gemini-3.1-pro + plan hobby_tvshow/v3 + grader-v5.1.
    # ─── OWNER VERDICT 2026-08-31: the production grader is SONNET-5. ───────
    # Supersedes the gemini-3.1-pro pin. Measured basis (RUNLOG 2026-08-31):
    #   · gemini-3.1-pro failed T1-COST on 10/10 trials at $0.3823 — 2.5x the
    #     $0.15 ceiling — and graded at p50 79.3 s.
    #   · claude-sonnet-5 grades the same corpus 3.4x faster (p50 23.0 s at
    #     16-wide) for 42% of the cost ($0.1569), accuracy comparable
    #     (within-precision 0.861 vs 0.895, MAE 0.116 vs 0.111).
    #
    # THE VERDICT ACCEPTS A KNOWN KILL, deliberately and on the record: Sonnet-5
    # fails K1 at 45/48. All three firings are the SAME cell —
    # din/q2.ב.c4.s2 — which the gemini champion also leaks on 1/3 of draws
    # under the same grader-v5.3, and which the RUNLOG attributes to the
    # plan/prompt surface rather than to the vendor. It is carried to fixture
    # expansion. The bar was NOT moved to accommodate this; the failure is
    # accepted with its name attached.
    #
    # The prompt half of the pin is in code, not here: VERIFIER_PROMPT_VERSION
    # = "grader-v5.4" (OD-W6: v5.3's system prompt byte-identical plus the
    # conditional `counted` rule), guarded by tests/agents/test_grader_pin.py.
    #
    # LIVE (owner instruction 2026-09-05/06, PLAN_production_wiring.md, W-4):
    # grader-v5 for EVERY rubric. Every compiled rubric gets a compiled
    # GradingPlan (grading_plans, built at compile time or in place at the
    # first grade), so the pilot-era file+rubric-id binding is retired. The
    # only knob left is the EMERGENCY ROLLBACK: GRADER_ARCHITECTURE=v3 sends
    # every grade down the historical v3 path with no data change.
    grader_architecture: str = "v5"                    # v5 | v3 (rollback only)
    grader_model_key: Optional[str] = "claude-sonnet-5"
    grader_model_provider: str = "anthropic"            # openai | anthropic | gemini

    # [PR-G4] Feedback model — a SEPARATE dial from the grader (OD10/OD-B3).
    # Feedback is prose and cheaper; tying it to the grading pin would make
    # every grading-model decision a feedback decision too. Unset = no
    # feedback generated, which is a state the wire and the UI both carry.
    # OD-B3 CLOSED by measurement + owner ruling (2026-08-31): Sonnet 5.
    # gemini-3.1-pro was both too expensive and too rate-limited. Measured on
    # the five fixtures, k=2: gender-neutral lint 10/10 clean, $0.0564/test
    # (vs gemini-3.1-pro's $0.48-0.63 and the $0.15 OD10 ceiling), p50 44.8s.
    feedback_model_provider: str = "anthropic"
    feedback_model_key: Optional[str] = "claude-sonnet-5"

    # [PR-G3] How many scopes of ONE test may be in flight at once. Was a
    # hardcoded 5, which made a 15-scope test three serial waves with no dial.
    #
    # THE KILL CRITERION IS AN ENV CHANGE: any rate-limit failure under this
    # value → set it back to 5 and record. That is why it lives here and is
    # read at CALL time, never frozen into a module constant at import.
    #
    # It is bounded by the PROVIDER's request rate, not by our appetite: a
    # provider at 25 RPM cannot absorb 16 concurrent calls from a single test,
    # let alone twenty tests dispatching at once. Raising this without checking
    # the pinned provider's quota buys 429s, not speed.
    grader_max_concurrent_scopes: int = 16

    # [PR-G8] measured p50 seconds per TEST, per model key, from the eval
    # table. Absent model ⇒ the ETA reports `unknown` and the client says
    # «עוד רגע» rather than a number nothing supports.
    # MEASURED 2026-08-31 (PR-G3(b)). Seconds per TEST as the batch feed counts
    # them: `draft_created_at - grading_started_at`, which spans grading AND
    # feedback, because attach_feedback runs inside the grading run before the
    # draft lands. Composed from two separately-measured halves:
    #   grading  p50 23.0 s  (sonnet5-v5, 16-wide, k=2 x 5 fixtures)
    # + feedback p50 44.8 s  (claude-sonnet-5, k=2 x 5 fixtures, OD-B3)
    #   = ~68 s
    # PROVISIONAL: measured on a laptop with no queue depth, on 6-scope
    # fixtures. The moment one test lands, the ETA switches to this batch's own
    # observed p90 and stops using this number at all — which bounds the damage
    # to the first card of a batch.
    latency_profile: dict = {"claude-sonnet-5": 68.0}
    openai_vision_model: str = "gpt-4o"  # For vision/transcription tasks
    
    # Google Cloud settings
    google_cloud_project: str
    pubsub_topic_name: str = "gmail-test-grader"
    
    # Gmail settings (optional - only for legacy email-based grading)
    gmail_credentials_file: str = "config/gmail_credentials.json"
    gmail_token_file: str = "config/token.json"
    teacher_email: Optional[str] = None  # Only needed for email-based grading
    
    # Application settings.
    # Unset/unknown ⇒ production (fail closed): every consumer of this value
    # grants something in development that must not be granted in production.
    app_env: str = "production"
    api_host: str = "0.0.0.0"
    api_port: int = 8080
    log_level: str = "INFO"
    sql_echo: bool = False  # SQL_ECHO=true to log every statement (very noisy)
    
    # CORS settings (comma-separated list of allowed origins)
    # IMPORTANT: CORS origins must be scheme://host:port only - NO paths!
    #
    # The DEFAULT is production-safe: no dev origins (closeout, owner-ruled).
    # A production API that trusts http://localhost:3000 with credentials lets
    # anything running on a teacher's own machine at that port make
    # credentialed calls against her session — narrow, but real, and free to
    # drop. Dev origins belong in the developer's .env (which overrides this),
    # never in the shipped default.
    allowed_origins: str = "https://vivi-assistant.com,https://www.vivi-assistant.com"
    
    # Grading settings
    confidence_threshold: float = 0.7
    max_concurrent_jobs: int = 3
    max_tokens_per_request: int = 4000
    temp_file_retention_hours: int = 1
    
    # Vision processing settings
    vision_dpi: int = 150  # DPI for PDF to image conversion
    vision_max_image_size: int = 1500  # Max dimension for images sent to VLM
    
    # PDF rasterizer backend (2026-08-19). "pymupdf" is in-process and ~18x
    # faster than "poppler" (pdf2image), which spawns a subprocess per call and
    # pipes every page through PPM/PNG. The backends are NOT pixel-identical, so
    # pymupdf became the default only after a k=5 transcription-eval
    # non-inferiority run. Poppler stays installed in the image and reachable
    # here: reverting production is this one env var, no redeploy.
    pdf_renderer: str = "pymupdf"

    # --- Page-1 thumbnail (PR-G8, PLAN_page1_image_route) --------------------
    # MEASURED on the six real bagrut scans, p50 of 3 runs each: the JSON page
    # proxy's PNG-base64 is 1168 KB / 1227 ms; this variant is 33.6 KB / 259 ms
    # — ~35x fewer bytes, ~4.7x less render. render_dpi > the output width is
    # SUPERSAMPLING for sharpness, not resolution: rendering at 110 and LANCZOS
    # -ing down to 600 beats rendering at 72 directly for ~2 KB and ~36 ms.
    #
    # ⚠ These three ARE the cache identity. The URL the feed mints carries them
    # as a variant token (`600x72@110`), so changing any one of them mints a NEW
    # resource rather than serving stale bytes under a year-long `immutable`
    # header. That is the whole point — do not "simplify" the token away.
    page_thumb_width_px: int = 600
    page_thumb_quality: int = 72
    page_thumb_render_dpi: int = 110
    # Retired variants to keep serving deliberately (e.g. through a deploy
    # window). Empty by default: a token not in the allow-set is a 404, which is
    # what stops `?v=20000x100@600` being a render-bomb.
    page_thumb_legacy_variants: List[str] = []

    # Page-render cache budget, in BYTES. It used to be an entry count (256) on
    # the strength of a docstring claiming "a rendered page is tens of KB";
    # measured, a review page is 1168 KB p50 / 1870 KB max, so that cap was
    # ~300 MB (worst case ~480 MB) in a 2 GiB container whose concurrency was
    # already cut 5->4 on an OOM measurement. Entries were never the memory
    # bound; bytes are.
    page_cache_max_bytes: int = 64 * 1024 * 1024

    # Parallel transcription settings
    parallel_transcription_enabled: bool = True  # Feature flag for async parallel processing
    max_parallel_pages: int = 3  # Max concurrent VLM calls (reduced to avoid overwhelming API)
    vlm_timeout_seconds: int = 90  # Per-call timeout for VLM requests (increased for vision)
    vlm_max_retries: int = 2  # Number of retry attempts before degraded fallback
    vlm_retry_backoff_base: int = 3  # Exponential backoff base: 3s, 9s

    # Transcription VLM provider settings (S4)
    transcription_vlm_provider: str = "openai"
    transcription_vlm_model: str = "gpt-4o"
    transcription_debug_dump: bool = False  # gate debug file writes in production

    # Transcription engine selector.
    #   "legacy"    — HandwritingTranscriptionService (S4 architecture; default)
    #   "two_phase" — P1 perception + P2 segmentation (the eval-suite-validated
    #                 pipeline; see app/services/transcription/two_phase/ +
    #                 two_phase_engine.py). Cross-reader trust layer retired in
    #                 production 2026-08-07 (see two_phase_engine docstring).
    #                 Requires GEMINI_API_KEY + OPENAI_API_KEY.
    transcription_engine: str = "legacy"

    # S11 batch concurrency: since the Cloud Tasks migration the in-process
    # semaphore is GONE — batch-wide concurrency is governed by the queues'
    # maxConcurrentDispatches (see the deploy checklist: 5 per queue) plus the
    # per-process provider scheduler cap. No dead knob left behind
    # (batch_max_concurrent_tests was removed with the semaphore).

    # S11: Logprob span-min thresholds for vlm_low_logprob flagging.
    # logprob scale: 0.0 = certain, -∞ = impossible. -2.0 ≈ 13.5% token probability.
    # Calibration guesses — E2 will tune from real teacher corrections.
    logprob_span_threshold: float = -2.0   # any sliding window below this → flag
    logprob_span_window: int = 5           # sliding-window width in tokens

    # S11: Per-answer VLM confidence threshold for flagging.
    # Shadows the older confidence_threshold; used specifically by batch triage.
    transcription_confidence_threshold: float = 0.8

    # PR-1: async rubric-extraction job lifecycle.
    # Execution substrate for extraction jobs (ADR-1):
    #   "cloud_tasks" — enqueue a Cloud Tasks HTTP task targeting
    #                   /internal/extraction-jobs/{id}/run; extraction runs
    #                   INSIDE that request so CPU is guaranteed (prod default).
    #   "inline"      — asyncio.create_task in-process. LOCAL DEV ONLY: under
    #                   prod Cloud Run config (CPU throttled post-response,
    #                   min-instances 0) an in-process background task is
    #                   throttled/killed after the response returns.
    extraction_execution_mode: str = "cloud_tasks"
    # Heartbeat TTL: an 'extracting' job whose updated_at is older than this is
    # reported stale (instance died mid-job) and becomes retryable.
    extraction_heartbeat_ttl_minutes: int = 15
    # LIV-1: how long a job may sit 'queued' before we declare the dispatch lost.
    # 'queued' has NO heartbeat — nothing about the row changes while it waits —
    # so without this deadline a lost dispatch is unfalsifiable and traps the
    # teacher forever. Cloud Tasks pickup is normally sub-second; 5 minutes
    # tolerates a cold start or a briefly backed-up queue.
    extraction_dispatch_ttl_minutes: int = 5
    # Cloud Tasks queue + OIDC identity for the task → /internal call.
    cloud_tasks_location: str = "europe-west1"
    cloud_tasks_queue: str = "rubric-extraction"
    cloud_tasks_invoker_sa: Optional[str] = None
    # Base URL of THIS service (Cloud Run URL) — target for enqueued tasks.
    service_base_url: Optional[str] = None
    # Shared-secret fallback auth for /internal/extraction-jobs/{id}/run
    # (inline/dev mode, where no OIDC token exists).
    internal_task_token: Optional[SecretStr] = None
    # Max accepted rubric DOCX upload size.
    extraction_max_upload_mb: int = 15
    # Max accepted per-file batch scan size (B9 intake v2 — per-file appends;
    # 20MB covers the largest observed scan ~10.2MB with headroom while
    # staying far under Cloud Run's 32MB request ceiling).
    batch_max_upload_file_mb: int = 20

    # Cloud Tasks migration — batch transcription + grading job kinds.
    # Execution mode for the NEW kinds; None ⇒ falls back to
    # extraction_execution_mode, so existing dev (.env inline) and prod
    # (cloud_tasks) environments need ZERO new configuration.
    jobs_execution_mode: Optional[str] = None
    # Separate queues per kind — rate/concurrency tune independently.
    # Owner-ratified deviation from the extraction ADR: these queues run
    # maxAttempts=3 (the DB CAS claim makes duplicate delivery a no-op;
    # redelivery heals dispatch-level failures under batch backlog).
    cloud_tasks_transcription_queue: str = "transcription-jobs"
    cloud_tasks_grading_queue: str = "grading-jobs"
    # [PLAN COMPILER v2 production wiring, OD-W2] plan builds ride their own
    # queue so a burst of rubric saves never delays a grade.
    cloud_tasks_plan_build_queue: str = "plan-build-jobs"
    # Transcription-job liveness (LIV-1 arms):
    #   running — heartbeat sidecar touches updated_at every ~60s; 5 min of
    #   silence is PROVABLY dead, not slow.
    transcription_job_heartbeat_ttl_minutes: int = 5
    #   queued — under batch backlog a doc legitimately waits behind
    #   maxConcurrentDispatches, and Cloud Tasks' own redelivery (maxAttempts=3)
    #   covers dispatch flakes — so this is a generous absolute backstop, not
    #   the extraction-style 5-minute dispatch window.
    transcription_job_dispatch_ttl_minutes: int = 90
    #: LIV-1 ABSOLUTE cap for a 'running' transcription job, in minutes
    #: (owner-ruled 20, 2026-09-10). Clocked on `started_at`, which the worker
    #: writes ONCE at its CAS claim and never touches again - unlike
    #: `updated_at`, which the heartbeat refreshes, so a hung-but-alive worker
    #: can hold a row past every heartbeat deadline forever.
    #:
    #: 20 minutes can only ever catch corpses: the document's own wall budget is
    #: 480s and Cloud Run kills the owning request at 900s, so no LEGITIMATE run
    #: can still be running at 20 minutes. It is the backstop for the case the
    #: budget cannot cover - a coroutine orphaned past its request, still
    #: heartbeating, which no in-process check can reach.
    transcription_job_absolute_ttl_minutes: int = 20
    # Grading liveness over graded_tests rows (no in-run heartbeat; updated_at
    # is written at the pending→grading claim): TTL must exceed the task's
    # 900s dispatch deadline, after which a killed worker can write nothing.
    grading_job_running_ttl_minutes: int = 30
    grading_job_dispatch_ttl_minutes: int = 90

    # ── PLAN COMPILER v2 — production plan builds (PLAN_production_wiring.md) ──
    # Every rubric gets a compiled GradingPlan at compile time (W-2), built by
    # a durable job; a grade that finds none builds in place (OD-W1).
    plan_build_envelope_usd: float = 1.0          # OD-W10: per-rubric spend cap; overrun → placeholder wording
    plan_route_min_points: int = 3                # OD-W5 / OD-24: monoliths at P ≥ 3 with a solution route
    plan_wait_s: float = 240.0                    # OD-W3: how long a grade waits on a LIVE builder
    plan_build_heartbeat_ttl_minutes: int = 5     # building rows lapse after this without a heartbeat
    plan_build_dispatch_ttl_minutes: int = 90     # queued rows never claimed → failed (backstop)
    # Upload-declaration backstop (migration 025, ruling R9). NOT a LIV-1 arm:
    # there is no row to reap — the files it describes never reached us, so
    # nothing can be marked failed. It is a READ-TIME fact only: a batch whose
    # declared count still exceeds its job count, and which has received no
    # append for this long, reports the difference as `not_received` instead of
    # an eternal `uploading`. 90 minutes matches the transcription DISPATCH
    # backstop for the same reason it was chosen there — a slow uplink under a
    # 30-file batch makes a long wait honest, and declaring her files dead while
    # they are still climbing would be the confident lie in the other direction.
    upload_declaration_ttl_minutes: int = 90

    # Extraction LLM pin for the docx_v3 pipeline. Read from env/.env (Pydantic maps
    # EXTRACTION_LLM_MODEL etc. case-insensitively); default = the eval-validated
    # production pin (D-2), NOT the pipeline's gpt-4o code default. These are
    # bridged into os.environ after Settings() below, because the pipeline reads
    # os.environ directly (so the eval runner can override them per-run).
    #
    # D-2 FLIPPED 2026-08-24 (owner-ordered): gpt-5.5/medium -> gpt-5.6-terra/high.
    # Evidence (RUNLOG "VERDICT 2026-08-24"): same prompt (3.9.0-blockend), same
    # pipeline (3.6.2), same instrument (suite_hash 19607f69e6bc3432), k=3 all-5 —
    # IDENTICAL gate result 12/15 with identical pass sets, every terra draw clean
    # (0 spurious, 0 missed, example_solution 1.000, 0 retries), while headline
    # t_doc -17.4%, suite -18.7%, and $/doc -63.9%.
    # ⚠ THE MODEL AND THE PROMPT ARE A PACKAGE. terra-high scores 12/15 on prompt
    # 3.9.0 but only 10/15 on 3.7.0 (phantom point-label criteria -> false
    # rubric_mismatch alarms). NEVER ship this pin onto an image built before
    # EXTRACTION_PROMPT_VERSION 3.9.0-blockend. gpt-5.5 is unaffected by the prompt
    # (12/15 on both), which is what makes the model half a safe one-line rollback.
    # ROLLBACK: set these three back to openai / gpt-5.5 / medium (and, in prod, the
    # Cloud Run env vars of the same name, which OVERRIDE these defaults).
    extraction_llm_provider: str = "openai"
    extraction_llm_model: str = "gpt-5.6-terra"
    extraction_llm_reasoning_effort: Optional[str] = "high"
    # 32000 aligns this default with BOTH the deployed Cloud Run value and the
    # eval config the pin was validated at (was 38000 — a latent 3-way drift that
    # only surfaced if the env var were ever removed). Non-binding either way:
    # the largest single-call output observed on any fixture is ~18k.
    extraction_llm_max_tokens: int = 32000

    # PR-2: the extraction task's total wall budget, in seconds.
    # 840 = Cloud Run request timeout (900) − 60s reserve. The runner measures its
    # OWN pre-work (GCS download etc.) against a monotonic t0 and passes
    # `840 − elapsed` down as the pipeline deadline — pre-work is MEASURED, never
    # assumed away (its library bound is 120s, which a flat 60s reserve would not
    # have covered). Keep in lockstep with the Cloud Run --timeout and the Cloud
    # Tasks dispatchDeadline: budget < request timeout, always.
    extraction_task_budget_s: float = 840.0

    # The per-DOCUMENT transcription wall budget, in seconds (owner-ruled 480,
    # 2026-09-10). Same doctrine as `extraction_task_budget_s` and comfortably
    # under the Cloud Run 900s request timeout / Cloud Tasks dispatchDeadline.
    #
    # WHY 480 IS SAFE DESPITE BEING SHORTER THAN THE INCIDENT IT ANSWERS: the
    # run that provoked it took ~580s, but ~481 of those were a single hung
    # optional-pass call that `PipelineConfig.optional_pass_timeout_s` now caps
    # at ~82s. The same document under this code is ~210s end to end, so the
    # budget carries roughly 2.3x headroom over the run that actually failed.
    # And the budget NEVER cancels a call in flight (services/transcription/
    # budget.py): it clamps the next call's timeout and refuses to START a phase
    # it cannot cover, so a slow-but-succeeding upload keeps its patience and a
    # document only ever dies at a phase boundary.
    transcription_task_budget_s: float = 480.0

    # LangSmith settings
    langchain_tracing_v2: Optional[str] = "false"
    langchain_endpoint: Optional[str] = "https://api.smith.langchain.com"
    langchain_api_key: Optional[SecretStr] = None

    # DECLARED, not swallowed. These five arrived through `extra = "allow"`,
    # which types them as plain strings and puts them in the model repr — which
    # is exactly how an AttributeError printed every key in this file to the
    # test log. Declaring them is the fix; the __repr_args__ net below covers
    # whatever `extra` swallows next.
    anthropic_api_key: Optional[SecretStr] = None
    xai_api_key: Optional[SecretStr] = None
    supabase_access_token: Optional[SecretStr] = None
    gmail_service_account_json: Optional[SecretStr] = None
    langchain_project: Optional[str] = "Test-Grader-AI"
    
    # Database settings (Supabase/PostgreSQL)
    # Carries the production password. Stays `str` because 14 call sites do
    # string operations on it (`.replace("+asyncpg", "+psycopg2")`), where
    # `.get_secret_value()` would buy nothing this policy does not already
    # guarantee — but it NEVER renders.
    database_url: str = Field(
        default="postgresql+asyncpg://user:password@localhost:5432/grader",
        repr=False)
    test_database_url: Optional[str] = Field(default=None, repr=False)
    
    # Sign in with Google (auth PR). The SAME value the browser holds as
    # NEXT_PUBLIC_GOOGLE_CLIENT_ID — a client ID is public by design; it is not
    # a secret and is deliberately NOT a SecretStr.
    #
    # The backend needs it to check the `aud` claim: without that check, an ID
    # token minted by Google for a DIFFERENT application is still a
    # perfectly-valid Google token, and accepting one would let any other app's
    # user sign in here. Empty ⇒ the endpoint refuses every request (503)
    # rather than verifying against nothing.
    #
    # No client SECRET: the ID-token flow (owner ruling A2) does not use one,
    # and declaring it would invite someone to start depending on it.
    google_oauth_client_id: Optional[str] = None

    # Email delivery. `console` by default so an unconfigured environment — and
    # every test process is one — cannot send real mail. See email_service.
    email_provider: str = "console"
    resend_api_key: Optional[SecretStr] = None
    email_from: str = "Vivi <noreply@vivi-assistant.com>"

    # [028] Where operational digests go (the 14-day re-ask digest, §7).
    #
    # DECLARED, not inherited from `extra = "allow"`: ALERT_EMAIL has been in
    # backend/.env since before this PR and no code ever read it, so it typed
    # as an undeclared string on the model and the digest would have had to
    # reach for `getattr(settings, "alert_email", None)` — the defensive
    # boundary read CLAUDE.md §6 names as the thing that turns a loud failure
    # into a quiet lie. None ⇒ the digest refuses to run rather than sending
    # nowhere.
    alert_email: Optional[str] = None

    # [028] The Google Sheet the onboarding queue projects into (§6).
    #
    # Unset ⇒ the projection is a NO-OP that logs once. This is load-bearing,
    # not politeness: the sheet is a DERIVED view (ONB-3 — the DB is the
    # record, and `rebuild_onboarding_sheet` can reconstruct it from the users
    # table alone), so an environment without it must still boot, still take
    # her answer, and still commit it. Every test process is such an
    # environment.
    onboarding_sheet_id: Optional[str] = None

    # [028] The queue carrying the sheet-upsert task. Its OWN queue, per the
    # substrate's standing rule that kinds tune independently — and here it
    # matters more than usual: this is the only kind whose work is a call to a
    # THIRD-PARTY API with its own quota, and letting a Sheets rate limit
    # share a queue with grading would let a spreadsheet throttle a grade.
    cloud_tasks_onboarding_sheet_queue: str = "onboarding-sheet"

    # Google Cloud Storage settings
    gcs_bucket_name: str = "grader-vision-pdfs"
    gcs_credentials_file: Optional[str] = None  # Uses default credentials if not set
    
    # Rubric Generator settings
    frontend_base_url: str = "https://vivi-assistant.com"  # Production domain
    rubric_generation_model: str = "gpt-4o"
    rubric_llm_timeout_seconds: int = 60
    
    # Grading Agent settings
    grading_timeout_seconds: int = 60  # Timeout for each LLM grading call
    grading_max_retries: int = 3       # Max retry attempts for transient failures
    
    # Classifier LLM settings
    # Primary model for DOCX rubric classification and verification.
    # gpt-5.2 is OpenAI's strongest reasoning model as of Feb 2026.
    # If the API returns an unknown-model error, verify the exact string at
    # https://platform.openai.com/docs/models and update here.
    CLASSIFIER_MODEL_OPENAI: str    = "gpt-5.2-2025-12-11"
    CLASSIFIER_MODEL_ANTHROPIC: str = "claude-sonnet-4-20250514"

    # 8192 covers the largest rubrics (multi-question, many sub-questions,
    # full example solutions). 4096 was the previous limit and caused
    # Q2+ content to be silently truncated mid-generation.
    CLASSIFIER_MAX_TOKENS: int = 8192

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "allow"

    # THE NET. `extra = "allow"` means .env can introduce fields this class
    # never declared, and pydantic renders them. Declaring the credentials we
    # know about (above) does not protect the next one someone adds, so the
    # repr itself refuses to print anything secret-shaped.
    #
    # Name-matched, because that is what a new secret has in common with the
    # old ones. `*_file` is excluded: those are PATHS (`config/token.json`),
    # and redacting them would hide useful diagnostics for no gain.
    def __repr_args__(self):
        for name, value in super().__repr_args__():
            if name and _is_secret_name(name):
                if value is None or value == "":
                    continue
                yield name, "**********"
            else:
                yield name, value


settings = Settings()


# --- ONE definition of "is this a development environment" -------------------
# Promoted here (closeout) so main.py's docs gate and database.py's create_all
# guard cannot drift apart about what "dev" means — two answers to that
# question is the two-auth-resolvers disease in a smaller organ. Unknown or
# unset ⇒ NOT dev (fail closed): every caller GRANTS something under dev.
DEV_ENVS = frozenset({"development", "dev", "local", "test", "testing"})


def is_dev_env() -> bool:
    return settings.app_env.strip().lower() in DEV_ENVS

# --- Extraction LLM pin → os.environ bridge --------------------------------------
# The docx_v3 extraction pipeline reads model / provider / reasoning_effort /
# max_tokens from os.environ DIRECTLY (so the eval runner can override them per-run,
# see tests/rubric_eval_suite/runner.py). Pydantic populates `settings` from .env/env
# but NEVER writes back to os.environ — so without this bridge the live backend falls
# through to the pipeline's gpt-4o code default (the model the eval gate was never
# earned at; gpt-4o misreads trace-table numbers as points). Export the pin here;
# `setdefault` preserves any explicit override already in os.environ (the eval runner
# or a shell export), so it never fights a deliberate per-run choice.
import os as _os
for _env_key, _val in {
    "EXTRACTION_LLM_PROVIDER": settings.extraction_llm_provider,
    "EXTRACTION_LLM_MODEL": settings.extraction_llm_model,
    "EXTRACTION_LLM_REASONING_EFFORT": settings.extraction_llm_reasoning_effort,
    "EXTRACTION_LLM_MAX_TOKENS": settings.extraction_llm_max_tokens,
}.items():
    if _val is not None:
        _os.environ.setdefault(_env_key, str(_val))


# =============================================================================
# LangSmith tracing interface
# =============================================================================

# Master toggle for LangSmith tracing.
# - False: disable tracing for all nodes below, regardless of their individual flags.
# - True:  enable tracing only for nodes whose *_trace flag is True.
langsmith_interface_trace: bool = True

# --- DOCX rubric pipeline (docx_rubric_service / classifier / enhancer) ---

# Layer: Orchestrator (DOCX rubric extraction)
# Input: DOCX bytes + ExtractionConfig
# Output: ExtractionResult (includes ExtractRubricResponse, RubricStructure, metadata)
# Purpose: Top-level DOCX rubric extraction chain.
docx_rubric_service_extract_rubric_from_docx_trace: bool = False

# Layer: 3 — Classifier (document header metadata)
# Input: [DOCUMENT_HEADER] text slice from renderer
# Output: HeaderMetadataResponse (test_title, test_date, evidence)
# Purpose: Extracts grounded test title/date before classification.
docx_classifier_call_llm_header_metadata_trace: bool = False

# Layer: 3 — Classifier (per-question chunk classification)
# Input: Prompt with TEXT/TABLE chunks for one question
# Output: QuestionChunkClassificationResponse (roles, table types, row mappings)
# Purpose: Classifies question structure and tables in chunk pipeline.
docx_classifier_call_llm_chunk_classification_trace: bool = False

# Layer: 3 — Classifier (full-document classification)
# Input: Full rendered document text
# Output: ClassificationResponse dict (questions, tables, row_to_sub_question)
# Purpose: Legacy / fallback full-document rubric classification.
docx_classifier_call_llm_classification_trace: bool = False

# Layer: 3 — Classifier (verification)
# Input: Verification prompt with rendered document + classification JSON
# Output: VerificationResult dict (is_valid, corrections)
# Purpose: Audits classifier output against the source document.
docx_classifier_call_llm_verification_trace: bool = False

# Layer: 4 — Question enhancer (Call 1: purpose + criteria rebalancing)
# Input: QuestionEnhancementContext + raw criteria
# Output: QuestionEnhancementResult (purpose + complete, normalized criteria)
# Purpose: Infers question purpose and locks teacher criteria.
question_enhancer_call_enhance_question_criteria_trace: bool = False

# Layer: 4 — Question enhancer (Step 1B: proposals)
# Input: QuestionEnhancementContext + base criteria
# Output: ProposalResult (proposed criteria + enhanced_distribution)
# Purpose: Proposes additional criteria and point redistribution for teacher review.
question_enhancer_call_propose_criteria_trace: bool = False

# Layer: 4 — Question enhancer (Call 2: rules + levels)
# Input: One criterion description + context (purpose, SQ text, solution)
# Output: CriterionRulesResult (rules, levels, evaluation_guidance)
# Purpose: Generates reduction rules, levels, and guidance per criterion.
question_enhancer_call_generate_rules_and_levels_trace: bool = False

# Layer: 4 — Question enhancer (main pipeline entry)
# Input: raw_criteria + QuestionEnhancementContext
# Output: EnhancementOutput (base_criteria + optional proposals)
# Purpose: Full ontological enhancement chain for DOCX rubric.
question_enhancer_enhance_criteria_for_question_trace: bool = False

# Layer: 4 — Question enhancer (post-acceptance)
# Input: accepted criteria list (+ context)
# Output: Enhanced criteria list with rules/levels
# Purpose: Runs Call 2 on teacher-accepted criteria proposals.
question_enhancer_enhance_accepted_criteria_trace: bool = False


# --- Test Grader agent (graph + nodes) ---

# Layer: Grading graph node (evaluation LLM call)
# Input: GradingAgentState (current_criterion + student answer + feedback)
# Output: Updated state with pending_evaluation JSON
# Purpose: Core LLM grading call for a single rubric criterion.
test_grader_evaluate_criterion_llm_trace: bool = False

# Layer: Grading graph node (validation + routing)
# Input: GradingAgentState with pending_evaluation and contract
# Output: Updated state (accept / retry / skip decision)
# Purpose: Validates LLM grading output and steers ReAct loop.
test_grader_validate_response_trace: bool = True

# Layer: Grading graph entrypoint
# Input: Contract, student answers, metadata
# Output: Final grading state with graded_test_draft
# Purpose: Top-level grading workflow chain for a full test.
test_grader_run_grading_agent_trace: bool = True


# --- PDF rubric generator (rubric_generator_service) ---

# Layer: Question detection (PDF → questions)
# Input: PDF bytes
# Output: List[DetectedQuestion] (numbers, texts, SQ IDs, suggested points)
# Purpose: Detects exam questions and basic structure from PDF text.
rubric_generator_service_detect_questions_from_pdf_trace: bool = False

# Layer: Criteria generation per question
# Input: DetectedQuestion + total_points + context
# Output: ExtractedQuestion with generated criteria and rules
# Purpose: LLM-based rubric synthesis for a single question.
rubric_generator_service_generate_criteria_for_question_trace: bool = False

# Layer: Full rubric generation
# Input: List[DetectedQuestion] with points
# Output: LegacyExtractRubricResponse for RubricEditor
# Purpose: Generates a complete rubric from detected questions.
rubric_generator_service_generate_full_rubric_trace: bool = False


# --- PDF rubric extraction / enhancement (rubric_service) ---

# Layer: VLM example solution extraction
# Input: Base64 page images + context
# Output: List[str] of sanitized example solutions
# Purpose: Extracts teacher example code solutions from rubric PDFs.
rubric_service_extract_example_solutions_from_pages_trace: bool = False

# Layer: Enhanced criteria extraction (3-stage pipeline)
# Input: PDF bytes + images + page indexes + context
# Output: Dict with criteria list, total_points, status, example_solutions
# Purpose: Extracts and enhances rubric criteria from PDF tables.
rubric_service_extract_criteria_enhanced_trace: bool = False

# Layer: Question text extraction (PDF text → questions)
# Input: Full PDF text + question numbers
# Output: Dict with question texts and SQ breakdown
# Purpose: Extracts clean question stems and sub-question texts from PDFs.
rubric_service_extract_all_questions_trace: bool = False

# Layer: Rubric extraction with page mappings
# Input: PDF bytes + QuestionPageMappings + metadata
# Output: LegacyExtractRubricResponse with questions and criteria
# Purpose: High-level rubric extraction pipeline for PDFs.
rubric_service_extract_rubric_with_page_mappings_trace: bool = False


# --- VLM rubric extractor (vlm_rubric_extractor) ---

# Layer: VLM criteria extraction
# Input: Base64 rubric images + context
# Output: VLMCriteriaResult (criteria, total_points, status)
# Purpose: Vision-based rubric table interpretation.
vlm_rubric_extractor_extract_criteria_trace: bool = False

# Layer: VLM question text extraction
# Input: Base64 question images + question_number
# Output: VLMQuestionResult (text, total_points, SQs, status)
# Purpose: Vision-based extraction of question text and sub-questions.
vlm_rubric_extractor_extract_question_text_trace: bool = False


# --- Vision document parser (document_parser) ---

# Layer: Student name extraction (vision)
# Input: Base64 first-page image
# Output: Optional student name string
# Purpose: Extracts student name from test header.
document_parser_extract_student_name_from_page_trace: bool = False

# Layer: Student code extraction (vision)
# Input: Base64 answer page images + question/sub-question ids
# Output: Dict with answer_text, has_code, metadata
# Purpose: Transcribes student code answers from scanned tests.
document_parser_extract_code_from_pages_trace: bool = False

