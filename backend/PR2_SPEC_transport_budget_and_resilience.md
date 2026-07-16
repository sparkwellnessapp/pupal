# PR-2 SPEC — Own the transport budget (backend) + the resilience seam (frontend)

**Kind:** two halves of different kinds, one PR, separable commits.
Backend half = PIPELINE VARIABLE (behavior-affecting transport policy inside
`pipeline.py`) → version bump, offline battery, pre-registered predictions,
RUNLOG. Frontend half = client infrastructure, no pipeline contact.
**Evidence base:** the PR-2 context report (pr-2_answer_items.md). Every design
choice below cites its finding.

---

## 0. What the evidence changed (read before coding)

The original conception was "add a transient-retry layer + auth refresh." The
context sweep falsified both halves as framed:

1. **A retry layer already exists and is invisible.** The OpenAI SDK retries
   twice internally (`max_retries=2` default; LangChain passes `None` → SDK
   default applies). Combined with our 3-attempt validation loop: up to
   **9 API calls per extraction, each unbounded** (A1/A4).
2. **The timeout is infinite — this is the root defect.** LangChain passes
   `timeout=None` EXPLICITLY, overriding the SDK's own 600s default. Observed:
   one successful attempt ran **1736s (29 min)** — 1.9× the entire 900s task
   budget. On today's prod that job is killed mid-flight by Cloud Run →
   stranded `extracting` → stale after 15 min → manual retry (A3).
3. **More retries are evidence-free.** Every observed organic failure
   (connection errors, Tier-B's one real failure) arrived AFTER the SDK's 3
   attempts were exhausted (B5/B7). Attempts 4–9 have no supporting evidence.
4. **The observed 429s were all permanent.** `insufficient_quota` is billing
   exhaustion, not rate pressure — the SDK retried it anyway, twice, per call
   (B5). A predicate that can't discriminate it burns budget on a condition
   that cannot succeed.
5. **Auth reality:** the only 403 our backend emits is the Cloud Tasks internal
   gate; everything else is 401 (expired/malformed indistinguishable server-
   side) or 404 (C8). A pre-expiry `/auth/refresh` endpoint EXISTS and is
   unused by the client (C9). A forced re-login destroys all in-progress
   review edits — zero client-side persistence (C10).
6. **The frontend has no seam:** 41 hand-rolled `fetch` sites in api.ts, no
   wrapper, no interceptor. PR-1's `ApiAuthError` (5 functions) is the
   precedent to generalize (D11). A mounted, RTL-configured, essentially
   unused sonner `<Toaster>` is the strongest existing error surface (D11).

**Design principles derived:** (i) ONE retry layer, owned explicitly — never
stacked (A4's non-multiplying placements only); (ii) every attempt bounded;
(iii) a **controlled in-budget failure beats an infra kill** — failing cleanly
at 840s with a message and a working retry button is strictly better UX and
ops than being SIGKILLed at 900s into a stale row; (iv) permanent errors fail
fast with a human-readable cause.

---

## PART 1 — Backend: transport policy in `pipeline.py`

### 1.1 Bounded, explicit client parameters
`_llm_params` gains, for openai + anthropic branches (gemini branch untouched —
see out-of-scope):
- `timeout = EXTRACTION_LLM_TIMEOUT_S` (env, **default 300**) — per-attempt
  bound. Covers the entire observed successful-attempt distribution except the
  1736s outlier (clean docs 67–108s; retried-run attempts ~200–230s). Verify
  the exact constructor field name against installed langchain-openai 1.1.7 /
  langchain-anthropic 1.4.0 (the context report proves the plumbing:
  LC passes `timeout=self.request_timeout` through).
- `max_retries = 0` — the SDK's hidden layer is DISABLED, because it cannot
  discriminate `insufficient_quota` (finding 4). All retrying moves to one
  app-level layer we control.

### 1.2 One transport-retry helper (the single layer)
`_transport_retry(invoke, *, attempts=1+EXTRACTION_TRANSPORT_RETRIES,
deadline=None)` in pipeline.py, wrapping the `structured.ainvoke` inside
`_call_llm` (inside the pipeline, around the call — B5: types survive only on
`__cause__`, so the predicate CANNOT live at the runner boundary), plus a sync
variant for the Tier-B adjudicator's `.invoke`.
- `EXTRACTION_TRANSPORT_RETRIES` env, **default 1** (2 attempts total) — the
  GraderAgent's "one surgical retry" convention, now made true here.
- Jittered backoff between attempts (1s base, ×4 max — short; the budget is
  precious).
- **Predicate — retry ONLY:** `openai.APIConnectionError`,
  `openai.APITimeoutError` (now REACHABLE for the first time — the timeout
  makes this branch live), `openai.InternalServerError`/5xx, and
  `openai.RateLimitError` **only when** its error code ≠
  `insufficient_quota`. Anthropic equivalents mirrored.
- **Terminal (fail fast, no retry):** `insufficient_quota` → raise
  `ExtractionError("OpenAI quota exhausted — billing issue, not retryable")`;
  provider 401/403/BadRequest → clear message naming the cause. Preserve
  `from e` chaining AND include the underlying exception type name in the
  message (B5 lesson: the string is what reaches artifacts and humans).

### 1.3 Deadline plumbing — controlled failure beats infra kill
`extract_rubric_from_docx` gains `deadline_seconds: Optional[float] = None`
(None ⇒ no deadline — eval CLI and dev behavior unchanged unless configured).
The PR-1 runner passes **840** (900s task budget − 60s reserve; GCS download
worst-case is bounded at 120s by library defaults per E13 but is seconds in
practice — reserve covers it).
- Before each VALIDATION-loop logical call: if remaining <
  `EXTRACTION_LLM_TIMEOUT_S + 60`, raise
  `ExtractionError("time budget exhausted after N attempts (…s elapsed)")` →
  the job lands as durable `failed` + message + instant retry, instead of a
  Cloud Run kill → stale → 15-minute discovery lag.
- Residual documented honestly: an in-flight call started with budget can
  still overshoot into the infra kill in a rare double-failure tail; the
  heartbeat-staleness path remains the backstop. Do not try to make the
  overshoot impossible — that trades common-case clarity for tail-case purity.

### 1.4 Tier-B adjudicator
Same helper, same predicate, sync variant, `attempts=2`, per-trigger isolation
(F1) unchanged. Evidence-driven at n=1 (B7: one real connection failure cost
one gate cell) — the fix is the bounded timeout + one controlled retry, NOT
more attempts (it already had 3 and failed).

### 1.5 Provenance + discipline
- The runner's `llm_config` snapshot gains `timeout_s` and
  `transport_retries` (effective env values) — the constants are now
  experiment-relevant and must be self-describing per job, same rationale as
  the D-2 model pin snapshot.
- `PIPELINE_VERSION` → **3.3.0** (behavior-affecting transport policy;
  prompt constant untouched at 3.3.1-tracehdr).
- Full offline battery green (mocked layer ⇒ zero movement expected — that IS
  the assertion). New unit tests: predicate table (each exception class →
  retry/terminal), quota fails fast with the billing message, deadline
  short-circuit raises the budget message, backoff bounded, Tier-B retry
  isolated per trigger, `deadline_seconds=None` ⇒ behavior identical.
- RUNLOG CHANGE entry (pipeline variable; affects comparisons vs pre-3.3.0
  runs).
- **Pre-register in PREDICTIONS.md before the next k-run:**
  P-T1: quota-class failures fail in seconds with the billing message
  (eval-era behavior: 3 slow attempts then opaque string).
  P-T2: the 1736s-outlier class now times out at 300s and retries once —
  outcome either a faster success (reasoning nondeterminism) or a clean
  budget failure; zero stranded/stale rows from this class.
  P-T3: zero gated-metric movement otherwise. KILL: any gated regression ⇒
  revert 1.1–1.3 (they're one commit).

---

## PART 2 — Frontend: the seam, the renewal, the stash

### 2.1 `apiFetch` wrapper — create the seam (D11)
One `apiFetch(path, init)` in api.ts; migrate all 46 call sites (mechanical —
they all repeat the same 4 lines). Behavior: attaches auth headers; normalizes
errors to typed `ApiError{status, detail}`; 401 → throws `ApiAuthError`
(generalizing PR-1's precedent). **No silent retries at this layer** —
mutations must never auto-repeat; poll-loop retry behavior stays in the hooks
where it's visible and bounded.

### 2.2 Sliding renewal — make expiry ~impossible for active users (C9)
`/auth/refresh` exists, works pre-expiry, and nothing calls it. Client-side:
on app mount + a low-frequency interval while the tab is active, decode the
stored JWT's `exp` locally (it's readable client-side — no backend change);
if remaining TTL < 48h, call `/auth/refresh` and store the new token. With a
7-day TTL this makes mid-session expiry effectively unreachable for any
active teacher — the cheapest possible resolution of the original "auth
refresh" scope, using an endpoint that already exists.

### 2.3 401 policy + the minimal stash (C10)
Global handling on `ApiAuthError`: decode stored token locally — if `exp` has
passed, message = "פג תוקף ההתחברות, יש להתחבר מחדש"; otherwise generic auth
error (no backend change to distinguish expired/malformed needed — the client
already knows). Before the logout-redirect: **stash in-progress review state**
(`extractedQuestions`, annotations/overrides, wizard step) to a single
localStorage key; after next login, offer restore ("נמצאה עבודה שלא נשמרה —
לשחזר?"). Scope discipline: this is stash-on-auth-failure ONLY — the smallest
cut of the persistence gap C10 exposed. General draft autosave remains PR-5;
note that post-PR-1 the extraction RESULT is already durable server-side (the
job row) — what the stash protects is the teacher's edits on top.

### 2.4 Error-surface convention (D11 table)
Adopt the mounted-but-unused sonner toast as the TRANSPORT/AUTH error surface:
`apiFetch` failures surface as `toast.error` with normalized Hebrew messages.
Domain/validation errors keep their existing inline `setError` banners and the
wizard modal — do NOT migrate the 54 inline sites; the convention is
transport=toast, domain=inline, documented in the frontend README/CLAUDE.md.
Wire toasts only where failures are currently swallowed to console.

### 2.5 The one-line debt (D12)
`useBatchProgress`: 401/403 terminal (via `ApiAuthError` once it routes
through `apiFetch`) — kills the infinite silent poll loop in the grading flow.

### 2.6 Frontend tests
apiFetch unit (401→ApiAuthError, error normalization, headers), renewal logic
against fake `exp` values, stash/restore round-trip, hook terminal-on-auth
test. `tsc` clean.

---

## Out of scope (explicit, with owners and reasons)

- **GraderAgent transport (same defect family: 2×3 unbounded calls/scope, dead
  `APITimeoutError` branch, quota retried)** → PR-7 (its Cloud Tasks
  migration), where its per-task budget math belongs; PR-2 only corrects the
  CLAUDE.md misstatement now ("one surgical retry" → documents the real 6-call
  worst case, with a pointer to PR-7). The `_transport_retry` helper is
  written to be reusable there.
- **Gemini branch undeployable** (`langchain_google_genai` not installed) —
  flag in CLAUDE.md; adding the dep is a deliberate decision for a sweep, not
  a side effect here.
- **Integration tests writing to PROD Supabase + 9 leaked job rows** — real
  finding, separate decision (test-DB isolation) + one-time cleanup; do not
  fold into PR-2. Needs a Noam ruling on test-DB strategy.
- **Backend expired-vs-malformed distinction** — unnecessary (client decodes
  `exp` locally).
- **General draft autosave** → PR-5.

## Acceptance

- [ ] Grep-provable: no LLM client constructed without explicit `timeout` and `max_retries=0`; exactly one retry layer exists
- [ ] Predicate table tested per exception class; `insufficient_quota` fails fast with the billing message
- [ ] Deadline: runner passes 840s; budget exhaustion produces durable `failed` + readable message (demonstrated in a test with a slow-mock)
- [ ] `deadline_seconds=None` + mocked layer ⇒ offline battery byte-green; PIPELINE_VERSION=3.3.0; RUNLOG + P-T1..T3 registered before any k-run
- [ ] `llm_config` snapshot carries timeout/retries
- [ ] All 46 fetch sites route through `apiFetch`; `tsc` clean; no mutation auto-retries anywhere
- [ ] Renewal proven: token with <48h remaining gets refreshed on activity
- [ ] Forced-401 mid-review: edits stashed, restore offered after login
- [ ] `useBatchProgress` terminal on auth error
- [ ] CLAUDE.md: grader-retry correction, Tier-B precision fix, gemini note
