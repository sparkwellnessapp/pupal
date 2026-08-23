# REPORT — Delivery, isolation, and the scale-up measurement

**PR:** `PR_delivery_isolation_scaleup.md` · **Executed:** 2026-08-23 (night) · **Launch:** 2026-09-01

---

## 1. Verdict per task

| Task | Verdict |
|---|---|
| **A** — ship the frontend | ✅ **Shipped and browser-verified.** Bigger than briefed: the deployable delta was 5 weeks of UI, and production's batch flow was 422-broken until it landed |
| **B** — pytest isolation | ✅ **The suite can no longer reach production.** Fail-closed guard + dedicated Vivi-Test project; cleanup executed under separate approval — 324 test users and their subtree removed, Viviana's data untouched |
| **§7** — Mumbai retirement | ✅ Dumped (697,767 B), archived to GCS, **restore-verified**, project deleted |
| **C** — the measurement | ✅ **Two clean arms; §3.2's prior is REFUTED** — the split is ≈260 MB/doc + ≈480 MB loaded-fixed, and it retro-fits every historical data point |
| **D** — memory bump | ⏸ **Gated on your ruling — and the measurement says you may not need it** (see §5) |
| **E** — queue raise | ⏸ Gated — **the measurement decouples it from D entirely** (see §5) |

---

## 2. Task A — deploy evidence

**The five §1.1 answers** (sources cited in-flight): Vercel builds `frontend-deployment` at root (CLAUDE.md §10/§12.5 + live-bundle match); auto on push (confirmed by this deploy); previews unknown (dashboard); no review flow; `NEXT_PUBLIC_API_URL` set (inferred from the working old build).

**Pre-flight findings that changed the task** (each surfaced before acting, per the process rule):
- The C=6 change was **untracked, not committed** — the brief's premise was stale.
- The deploy gap was **5 weeks**: `frontend-deployment` and the mirror froze Jul 16, before the entire batch-redesign UI.
- **Production's batch flow was broken**: the served Jul-16 bundle sends multipart to the now-JSON-only `POST /batches` → 422. The pilot batches worked only because they ran on a local dev frontend (all 16 of her jobs carry `client_file_id`; her first batch started 10 min after the intake-v2 backend deploy).
- Your ruling: **full ship.** Executed: commit `6ecd777` (133 files, frontend-only, verified), mirror refresh, `git subtree push` → `frontend-deployment ff5eaeb..43df226`, fast-forward.

**Gates before push:** vitest **623 passed**, `tsc` clean, copy gates pass, `next build` clean.

**Browser verification (real Chromium against production):**
- Served bundle: `client_file_id` ✓, `מקבץ` ✓, `אצווה` gone ✓, and the inlined constant **`Math.max(0,6-` — concurrency 6 confirmed in the shipped code**.
- Real batch through the deployed UI: login → בדיקת מבחנים → rubric → dropzone → start: `POST /batches` 201, **7/7 appends 200, ≥6 concurrent uploads observed on the wire** (counter peaked 7 with ±1 event-ordering skew), upload 26.1 s.
- **Clock 1 = 0.0 s** — the first test was reviewable in the UI before the upload finished. No regression; the overlap design works in a real browser.
- One measurement lesson recorded: my "still old build" poll compared the webpack-runtime chunk hash, which is identical across builds — the deploy had been live for ~30 min. Content markers are the right instrument.

*Vercel CLI handover (your request): create a token at vercel.com/account/tokens scoped to `sparkwellnessapps-projects`, drop `VERCEL_TOKEN=...` into `backend/.env`; I verify with `vercel whoami` and future deploys become monitorable from here.*

## 3. Task B — isolation design and evidence

**Established first:** tests resolve the DB via `TestClient(app)` → `settings` → `.env` = production; `s2test.com` rows come from `conftest._signup` through the real signup endpoint (by design — the auth-postmortem forbids faking auth); **CI was already clean** (battery runs pure tests only; drift-check uses a dummy URL). The exposure was local pytest runs.

**Q1 ruled: dedicated Supabase test project.** Implemented:
- **`Vivi-Test`** (`eqnbojbxsdafwtxvuyuy`, eu-central-1, PG 17.6 — same engine, same Supavisor transaction pooler as production).
- Schema provisioned from the **production schema dump** (after my first attempt — replaying migrations onto a fresh DB — failed exactly as the canon predicts: the base tables predate migration 001; ledger tokens landed past skipped statements under `ON_ERROR_STOP=0`. Reset and restored the dump instead: 20 tables, ledger 17, deferrable FK, RGC-1, all 3 CHECKs — catalog-verified).
- **The hard guard** (`tests/conftest.py`): `TEST_DATABASE_URL` redirect + allow-list keyed on **(host, pooler-tenant)** — host alone is insufficient because Supabase's regional pooler host is shared across projects, including production. Fail closed, session-abort, offending host+tenant named.
- **Proof:** guard vs production URL → session aborts, exit 1. Auth suite (the `s2test` producer) vs Vivi-Test → **43 passed**; **3 new users on Vivi-Test, zero on production.**

**§2.4 cleanup — separately approved, then executed:** one transaction, child→parent, predicate `email LIKE '%@s2test.com'`. Deleted exactly the dry-run counts: **324 users, 242 graded_tests, 147 rubrics, 50 batches, 14 transcriptions, 734 students, 170 classes, 4+4 jobs**. Verified after: 0 s2test remaining, **Viviana's 54 transcriptions untouched**, ledger intact. Backup taken and **restore-verified before** any delete (`db-archive/vivi_precleanup_20260823.dump`). Residue candidates left per ruling: `debug@test.com`, plus two newly-surfaced `latlab-*@example.com` accounts — flagged, untouched (`Q3`).

## 4. §7 — Mumbai retirement

```
dump:    vivi_premigration_20260822.dump  697,767 bytes  → gs://grader-vision-pdfs/db-archive/
verify:  restored into scratch → 20 tables, 330 users, ledger 17  ✓
delete:  hkctksimfrobotfpingj (Pupal-AI) — DELETE 200; project list confirms gone
```
Docs updated: CLAUDE.md's rollback pin now points at the archived dump (the `database-url:1` secret references a deleted project). The pre-cleanup Frankfurt dump sits beside it in the archive.

## 5. Task C — the measurement (§3.5 deliverable)

**Method:** same 35-doc batch at `--concurrency=2` and `=5`; **uploads isolated by pausing the transcription queue** during the upload phase (identical upload pattern both arms, conc 6); peak memory read as max-across-instances, per revision; zero container kills in either arm.

| Arm | Phase | Hottest-instance memory | Peak active instances |
|---|---|---|---|
| C=2 | upload only (queue paused) | 164 MB (8.0%) | (sub-minute churn — below metric resolution) |
| C=2 | transcription | **1,000 MB (48.9%)** | **15** |
| C=5 | transcription | **1,779 MB (86.9%)** | 10–11 |

**The solve** (hottest instance saturated at C docs — supported by the memory itself):
```
fixed + 2·d = 1,000 MB
fixed + 5·d = 1,779 MB      →  d ≈ 260 MB/doc,  fixed ≈ 480 MB (loaded)
```
Boot-only footprint (cold instance, light requests): ~164 MB — the pipeline's imports/buffers account for the rest of "fixed" on first document.

**§3.2 verdict: REFUTED.** The prior (71 MB/doc, 1,385 MB fixed) is inverted — **per-document memory dominates.** The refutation is strong because the model retro-fits every earlier point: conc-8-era 85% at ~5 docs/instance → predicted 1,780 vs observed 1,740; previous PR's 73.9% → predicted 1,520 at 4 docs vs observed 1,513.

**Consequences, with the arithmetic:**
- Safe docs/instance at 2 GiB, 85% line (1,740 MB): (1740−480)/260 = **4.8 → C=5 sits exactly AT the safe line** (86.9% observed — marginally over, no kills). This is the real finding: today's config has ~zero memory margin per instance, and the earlier "73.9%, comfortable" reading was luck of uneven packing.
- At 4 GiB, 85% (3,482 MB): (3482−480)/260 = **11.5 docs/instance**.
- **Per-instance memory is a function of `--concurrency`, NOT of queue depth.** Raising the queue 25→50 at C=5 leaves the hottest instance at the same 1,779 MB — it costs **instances** (≈10 for transcription), not memory. **Task E does not need Task D.** The memory bump becomes about *margin at C=5* (or enabling higher C), not about unblocking the queue.
- Throughput side-finding: both arms drained 35 docs in ~2.5 min (**~14–15 docs/min** vs the 6.6 measured pre-Frankfurt) — the queue at 25 now carries roughly **2× the capacity plan's assumed rate**.

**§3.4 — instances per simultaneous uploader:** the browser run (6 concurrent uploads during active transcription, C=5) burst to **14 instances**; upload-only phases churn faster than the 60 s metric granularity resolves — stated as a limitation. Working figure: ~6 concurrent requests ÷ 5 slots ≈ **1.2–2 instances per active uploader**. At `--max-instances=40` with ~10 reserved for a raised queue: ceiling ≈ **(40−10)/1.5 ≈ 20–25 simultaneous uploaders** — above the 10–20 launch target but not by much; **no raise needed before 09-01**, revisit with real telemetry.

**Stopped here per §3.5.** D and E are your decisions; the inputs:

| Decision | What the numbers say |
|---|---|
| **D** (4 GiB) | Not needed for E. Worth it only to buy margin at C=5 (86.9% → 43% of 4 GiB) or enable C≈11. Cost ≈ +$0.0000035/instance-s ≈ +~85% on instance-hours' memory component — at current usage, single-digit $/mo. A **cheaper alternative the measurement suggests: C=4 at 2 GiB** (1,520 MB = 74%, real margin, +~2 instances per batch). |
| **E** (queue 50) | Feasible **today** memory-wise; costs ~10 transcription instances of the 40; throughput already 15 docs/min at 25 — 50 would be ~30/min, far beyond launch need. Recommendation: **defer past 09-01** — capacity is not the launch problem (their own words in §0.1's spirit). |

## 6. Carry-forwards

- **P5** (append RTTs): ruled deferred (Q2).
- **P8** (`rubric-extraction maxAttempts=1`): failure UX today — a transient LLM error mid-extraction lands the job in `failed` with the error on the row; the teacher sees the failed state and has an explicit **`/retry` endpoint** (heartbeat-staleness + retry is the designed recovery, per the PR-1 ADR: "never blind task redelivery"). So the UX is *manual-retry-visible*, not silent loss. Recommendation: keep `maxAttempts=1` (the ADR's reasoning stands — redelivery of a 3-LLM-call chain risks double spend and confused provenance); if anything, add a frontend retry affordance polish later. No change made.
- **P4**: untouched, as ruled.

## 7. Open decisions

| ID | Item | Recommendation |
|---|---|---|
| Q1 | Isolation approach | ✅ ruled & done (Supabase test project ~$10/mo) |
| Q2 | P5 in this PR | ✅ ruled: deferred |
| **Q3** | `debug@test.com` + 2 `latlab-*@example.com` accounts remain in production | Delete with the same protocol if you confirm they're yours; 2-minute job |
| **Q4** | C=5 sits at exactly the 85% memory line (86.9% measured) | Either accept (measured, no kills, launch load is small) or take **C=4** as the free-margin option; 4 GiB only if you want C≈11 later. Your ruling — none applied |
| **Q5** | Task E timing | Defer past launch; 25 already carries 2× the assumed rate post-Frankfurt |

## 8. What I could not determine

- **Upload-phase instance counts** at 60 s metric granularity (requests too short post-Frankfurt) — the §3.4 ceiling is bounded from the browser-run burst + arithmetic, not directly measured.
- **Vercel preview-deployment availability** (dashboard-only; moot for this ship).
- Whether the hottest instance in the C=5 arm carried exactly 5 docs (inferred from the memory model's fit across 5 independent points; per-instance request attribution isn't exposed by Cloud Run metrics).
- The origin of the `latlab-*` accounts.

## 9. Spend & state

- Verification spend: ~77 synthetic docs ≈ **$2.3** Gemini + ~$0.15 OpenAI. Recurring: Vivi-Test ≈ $10/mo (Q1 ruling). Mumbai compute shed.
- End-state verified: concurrency 5 (rev `00036-v6p`), queue RUNNING@25, health 200, `import app.main` OK, **907 tests collected** (guard active), `tsc` clean.
- Commits on `perf/rubric-extraction-latency`: `6ecd777` (frontend ship), mirror commit, `92bd3bf` (guard + docs) — all pushed. `frontend-deployment` at `43df226`, **live in production**.

---

# Addendum — post-ruling execution (2026-08-23 afternoon)

## Rulings executed

| Ruling | Done |
|---|---|
| **Q4: C=4** + companion `--max-instances 40→60` | ✅ rev `00037-tt7`. **Verified under a live 35-doc batch: 71.97% peak memory vs the model's 74.2% prediction** — the memory model's fourth independent confirmation, at a concurrency it had never seen. Zero errors, zero kills. Docs synced |
| **Q5: queue raise deferred** | ✅ no change |
| **Q3: latlab forensics before deletion** | ✅ **NOT my residue — not deleted.** Created **Aug 11–12**, nine days before my latency work began (Aug 20); one owns 4 rows. Timing coincides with the 2026-08-12 shared-provider-infrastructure work — plausibly your own experiments. If you don't recognize them, it's the public-signup conversation. `debug@test.com` (Jun 1, owns 0 rows) also left pending your explicit word |
| **P8 affordance check** | ✅ In the shipped commit by construction: `useExtractionJob` treats failed/stale-extracting as retryable, wired in `page.tsx`, both in `6ecd777`. Direct bundle grep inconclusive (Next code-splits per route) — stated rather than claimed |
| **Build-SHA in the bundle** | ✅ **Live and self-proving**: `VERCEL_GIT_COMMIT_SHA` baked via `next.config.js`, exposed as `<meta name="build-sha">`. Deployed `7684ef2` — and the live meta reads `7684ef24…` = `origin/frontend-deployment` HEAD exactly. `curl -s https://www.vivi-assistant.com \| grep build-sha` is the five-second answer |
| **35-doc batch through production** | ✅ Real Chromium, deployed UI: **35/35 transcribed, Clock 2 = 28.6 s after upload-done.** (Launcher log filter trimmed the Clock-1 line; Clock 1 stands at 0.0 s from the 7-doc run, same overlap mechanism) |
| **VERCEL_TOKEN caution** | Acknowledged — when the token lands, minimal scope + rotation note; no token present yet |

## The full-suite answer (your question)

**Every one of the 907 tests executes green against Vivi-Test.** Evidence: the complement chunk (773 tests) printed green dots to completion before wedging; the eval block runs standalone **133 passed, 1 skipped in 29.75 s** and exits cleanly; earlier, the auth chunk exited cleanly too.

**The wedge is not a test — it is session teardown**, py-spy-verified: the session-scoped `TestClient`'s lifespan shutdown hangs in `IocpProactor._poll` inside the event-loop `close()` — an orphaned pooled-connection overlapped op that never completes, accumulated over ~700 tests of pooler churn. It **survives `engine.dispose()`** (which `close_db()` does call), is **volume-dependent** (43-test runs exit clean), **Windows-only** (IOCP; prod is Linux + SIGTERM — unaffected), and almost certainly **pre-existing** (same pooler class on Mumbai; CI never ran the api tests; nobody ran 907 single-process).

**Standing discipline (documented in CLAUDE.md §8):** run the suite as two invocations — `pytest --ignore=tests/transcription_eval_suit` + `pytest tests/transcription_eval_suit`. Chasing the orphaned-op root cause is a **Q6** for after launch (candidate suspects: pooler-reset connection residue; the two_phase shared-infra HTTP clients, which nothing closes on shutdown).

## Updated open decisions

| ID | Item | State |
|---|---|---|
| Q3 | latlab-* origin | **Back to you** — predates my work; recognize them or it's a signup-endpoint question |
| Q6 *(new)* | Windows teardown wedge root cause | Post-launch; two-invocation rule holds meanwhile |
