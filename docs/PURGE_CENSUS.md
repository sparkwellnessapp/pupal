# PURGE CENSUS — the blast radius of deleting a student

**Phase B0 deliverable** of `PR_student_profile.md` §11. **Gate: no purge code before Noam approves this document.**

**Author:** Claude · **Read date:** 2026-09-22 · **Status:** awaiting approval

**What was read.** Production Postgres (Supabase project `ngkqawsyqqbhqthgdkpk`, eu-central-1, migration head **030**) with SELECT-only queries; GCP project `gen-lang-client-0438328890` via `gcloud` describe/list; the code at `perf/rubric-extraction-latency`. Every number below carries the query or command that produced it. Where a fact could not be established from code or a console I have access to, the row says **UNVERIFIED** and names who must check it. Nothing here was inferred from the schema docs.

**Production scale at read time** (so the numbers below are read in proportion):

```sql
SELECT COUNT(*) FROM students;            -- 18
SELECT COUNT(*) FROM transcriptions;      -- 38   (21 approved, 17 'transcribed')
SELECT COUNT(*) FROM graded_tests;        -- 22   (2 with returned_exam_key)
SELECT COUNT(*) FROM transcription_jobs;  -- 39   (38 with transcription_id, 39 with source_filename)
SELECT COUNT(*) FROM graded_test_pdfs;    -- 0
SELECT COUNT(*) FROM class_memberships;   -- 0
```

---

## 0. The finding that reorders Part B

`DELETE FROM students WHERE id = S` **succeeds today**, and what it does is decided by the database before any code can enumerate the objects those rows point at. Simulated from the live constraint graph (row 1), a delete of one student right now:

**Deletes, silently:** her `class_memberships`; every `graded_tests` row naming her (**CASCADE**), and with them every `graded_test_pdfs` row (**CASCADE**); every **approved** `transcriptions` row naming her (**CASCADE**), and with each of those every `graded_tests` row pointing at it (**CASCADE**).

**Leaves behind, every time:**

| Survivor | Why | What it still holds | Count in prod |
|---|---|---|---|
| Every GCS object | No FK reaches storage | the scan PDF, page thumbnails, the signed exam PDF | 38 scans + thumbs + 2 returned PDFs |
| `transcription_jobs` rows | `transcription_id` is **SET NULL**, not CASCADE | `source_filename` (teachers name files after students) and `source_gcs_object_path` | 39 rows, all with a filename |
| `transcriptions` with `status='transcribed'` | `student_id` is **NULL** until the gate (008 CHECK), so no FK attributes them to her at all | `draft_json` — the student's transcribed handwriting — and `gcs_object_path` | 17 rows (0 carry a `student_name` today) |
| `grading_batches.transcription_failures` | jsonb, no FK | filenames of her failed uploads | 0 batches carry entries today |

So the hazard is not that deletion fails. **It is that deletion succeeds and leaves the student's handwriting in a bucket, her filename in a job row, and her transcript in a row nothing points at.** A purge built on top of this graph would pass its own tests while PRV-6 (*plan equals execution*) is false by construction: execution would be "whatever the constraints cascade", and any FK added later silently widens or blocks it. AM-B1's inversion — drop the cascades, delete explicitly, let every other path fail loudly — is what this census supports.

---

## 1. Postgres — the FK graph, with delete rules (the before-state)

Read with (full output in the purge-plan tests' fixture):

```sql
SELECT tc.table_name, kcu.column_name, ccu.table_name AS ref_table, rc.delete_rule,
       tc.is_deferrable, tc.initially_deferred, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
JOIN information_schema.referential_constraints rc ON tc.constraint_name = rc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
  AND ccu.table_name IN ('students', 'graded_tests', 'transcriptions')
ORDER BY 3, 1, 2;
```

**Every FK into the student-data graph, as production has it on 2026-09-22.** This table is the before-state PRV-8 is tested against and the one migration 032 is written from — 032 must be generated from a fresh read of this query, not from this text.

| # | Constraint | FK | Today | 032 target | Note |
|---|---|---|---|---|---|
| 1 | `class_memberships_student_id_fkey` | `class_memberships.student_id → students.id` | **CASCADE** | CASCADE *(kept)* | The AM-B1 exception: a pure join table, no children, no objects. The purge deletes it explicitly anyway. |
| 2 | `graded_tests_student_id_fkey` | `graded_tests.student_id → students.id` | **CASCADE** | **NO ACTION** | Finding. Deletes grades and, through #4, their PDFs. |
| 3 | `transcriptions_student_id_fkey` | `transcriptions.student_id → students.id` | **CASCADE** | **NO ACTION** | Finding. Deletes approved scans' rows; objects survive. |
| 4 | `graded_test_pdfs_graded_test_id_fkey` | `graded_test_pdfs.graded_test_id → graded_tests.id` | **CASCADE** | **NO ACTION** | Finding. Row carries `gcs_object_path`; deleting it loses the only pointer to the object. |
| 5 | `graded_tests_transcription_id_fkey` | `graded_tests.transcription_id → transcriptions.id` | **CASCADE** | **NO ACTION** | Finding. The second path by which grades disappear. |
| 6 | `transcription_jobs_transcription_id_fkey` | `transcription_jobs.transcription_id → transcriptions.id` | **SET NULL** | **NO ACTION** | Finding of a different shape: it *orphans* rather than deletes, keeping filename + object path with nothing to find them by. |
| 7 | `graded_tests_regraded_from_id_fkey` | self | SET NULL | SET NULL *(kept)* | Chain back-pointer. |
| 8 | `graded_tests_regraded_to_id_fkey` | self, **DEFERRABLE INITIALLY DEFERRED** | SET NULL | **unchanged** | Migration 010. §13's one-statement chain delete depends on this deferral; 032 must not touch it. |

**Why NO ACTION and not RESTRICT.** RESTRICT is checked immediately, per row, and cannot be deferred; under it the purge's single-statement delete of a whole revision chain becomes order-dependent. NO ACTION is checked at statement end, which is exactly what §13's dependency order needs. Both refuse an unexplained delete; only NO ACTION lets the correct one through.

**Outside the graph but worth recording** (no change proposed, listed so 032's author does not widen by accident): `graded_tests.batch_id → grading_batches` SET NULL; `transcriptions.batch_id → grading_batches` SET NULL; `transcription_jobs.batch_id → grading_batches` **CASCADE**; everything `→ rubrics` and `→ users` CASCADE. A user delete therefore still cascades the whole tree — out of scope here, and a separate hazard worth its own ruling one day.

---

## 2. Postgres — text and JSONB carrying the student

Read with `information_schema.columns` filtered on `%student_name%`, `%filename%`, `%gcs%`, `%object_path%`, `%_key`, and `data_type='jsonb'`. **This is the PII registry** the §16.1 test set-compares against; a new column matching those patterns fails that test until it is classified here.

| Column | Holds | Disposition |
|---|---|---|
| `graded_tests.student_name` | her name | deleted with row (#2 set) |
| `graded_tests.filename` | file the teacher named after her | deleted with row |
| `graded_tests.draft_json` / `contract_json` | her answers, the grading, the feedback | deleted with row |
| `graded_tests.returned_exam_key` | cache key → the object at `returned_exams/{id}/{key}.pdf` | row deleted; **object deleted by prefix** (row 5) |
| `transcriptions.student_name` | her name | deleted with row |
| `transcriptions.filename` | her filename | deleted with row |
| `transcriptions.draft_json` / `contract_json` / `review_json` | **her handwriting, transcribed** | deleted with row |
| `transcriptions.gcs_uri` / `gcs_bucket` / `gcs_object_path` | → the scan | row deleted; object deleted |
| `transcription_jobs.source_filename` | her filename | **delete the row** (§13 #4), never NULL it |
| `transcription_jobs.source_gcs_object_path` | → the same scan PDF | row deleted; object deleted |
| `graded_test_pdfs.filename` / `gcs_*` | → the signed exam PDF | row + object (0 rows in prod; see row 3) |
| `grading_batches.transcription_failures` (jsonb) | `{filename, error, at, net_verdict}` of failed uploads | **scrub in place** — the batch is the teacher's and survives |
| `grading_batches.stamp_position_default` (jsonb) | no student data | untouched |
| `grading_plans.plan_json` / `skeleton_json` | rubric algebra only, no student data | untouched |
| `rubrics.*`, `rubric_extraction_jobs.*`, `raw_rubrics.*` | the **teacher's** documents | untouched — out of scope by definition |
| `grading_sessions.student_name` / `filename` / `state_snapshot` / `graded_test_draft_json` | legacy | see row 3 → `OD-B1` |
| `raw_graded_tests.student_name` / `filename` / `graded_json` / `student_answers_json` | legacy | see row 3 → `OD-B1` |

---

## 3. Postgres — the legacy tables (FB-3)

```sql
SELECT COUNT(*) FROM grading_sessions;  -- 0
SELECT COUNT(*) FROM raw_graded_tests;  -- 0
SELECT COUNT(*) FROM raw_rubrics;       -- 0
```

All three are **empty in production** and **nothing in `app/` constructs them** (`grep -rn "GradingSession(\|RawGradedTest(" app/` → no matches). `raw_rubric.py` is already marked DEPRECATED in CLAUDE.md §8. `grading_sessions` and `raw_graded_tests` have no FK into the student graph (they reach `rubrics` and `users` only), so a purge would not touch them even if populated.

> **`OD-B1` — legacy tables. Recommendation: the purge covers them defensively; a drop migration is a separate decision.**
> The purge's plan includes `DELETE FROM grading_sessions/raw_graded_tests WHERE student_name = <her name>`… **no** — that is name-matching, which this document argues against everywhere else. Recommendation, precisely: the purge does **not** reference these tables (they are unreachable from the student graph and empty), the PII registry records them as *dead*, and dropping them (with `rubrics.raw_rubric_id`) is proposed as its own cleanup migration after Part B. If Noam prefers belt-and-braces, the alternative is to have `verify_purged` assert they are still empty, which costs one query and no policy.

---

## 4. GCS — buckets and policies (FB-5)

`gcloud storage buckets list --project gen-lang-client-0438328890`:

| Bucket | Location | Soft-delete | Versioning | Lifecycle | Public access |
|---|---|---|---|---|---|
| **`grader-vision-pdfs-0438328890`** — the only one holding student data | europe-west1 | **604800 s = 7 days** | not enabled | none | prevented |
| `gen-lang-client-0438328890_cloudbuild` | US | 7 days | not enabled | none | build artefacts only |
| `run-sources-…-europe-west1` / `…-us-central1` | — | 7 days | not enabled | none | deploy sources only |

**The 7-day soft delete is the single most important residual copy in this document.** A deleted object is restorable by anyone with bucket permissions for 7 days; `gcloud storage ls` does **not** show it, so a verify that lists prefixes will report "empty" while the bytes still exist. Verify with `gcloud storage ls --soft-deleted gs://grader-vision-pdfs-0438328890/<prefix>/`.

> **`OD-B3` — the soft-delete window. Recommendation: keep it at 7 days, document it, and make `verify_purged` report it rather than hide it.**
> Turning it off (`--clear-soft-delete-policy`) would make an accidental deletion of a *teacher's* live batch unrecoverable, which is a larger and more likely harm than a 7-day restorable window after a deliberate, confirmed purge. The honest posture is: the purge deletes; the verify states "objects deleted; recoverable by a project administrator until {date}"; and the privacy page says so in `OD-B5`'s sentence. If Noam wants zero-day, it is one command on that bucket and a paragraph removed — but it should be a decision, not a default.

---

## 5. GCS — writers, naming, and how the purge finds objects (FB-4)

Every code path that writes an object, with the prefix it writes under. Verified by reading each writer; prefixes cross-checked against the live rows (`SELECT split_part(gcs_object_path,'/',1), COUNT(*) FROM transcriptions GROUP BY 1` → `transcriptions/` ×38; same for `transcription_jobs.source_gcs_object_path` ×39).

| Writer | Object path | Student data? | Found by |
|---|---|---|---|
| `batch_grading.append_file` (`app/api/v0/batch_grading.py:690`) | `transcriptions/{user_id}/{uuid4}.pdf` | **the scan** | the exact path on `transcriptions.gcs_object_path` **and** `transcription_jobs.source_gcs_object_path` (same object, two rows) |
| `transcribe_one` (`:101`, retry `:150`) | `transcriptions/{user_id}/{uuid4}.pdf` | **the scan** (single flow) | same |
| page thumbnails (`api/v0/transcription.py:481` via `thumbnail.gcs_object_path`) | `thumbs/{transcription_id}/p{n}_{width}x{q}-{dpi}.webp` | **rendered page images** | **prefix listing** `thumbs/{transcription_id}/` — the variant token is a settings-derived suffix, so reconstructing names would miss every object written under a previous setting |
| returned exam (`returned_exam_store.py:132` via `returned_exam.gcs_object_path`) | `returned_exams/{graded_test_id}/{cache_key}.pdf` | **the signed exam** | **prefix listing** `returned_exams/{graded_test_id}/` — content-addressed by cache key, and superseded keys are *left in place by design*, so only a listing finds them all |
| rubric sources (`rubric_extraction_jobs.py:210`) | `rubric-sources/{user_id}/{sha256}.docx\|pdf` | teacher's document | out of scope |
| `gcs_service.upload_pdf_with_pages` | `{folder}/{session_id}/…` | — | **DEAD: no caller in `app/`.** Recorded so a future caller is a conscious choice. |

**This is M-B7 stated as evidence, not preference:** two of the four student-data prefixes hold objects whose names cannot be reconstructed from a row (variant tokens; superseded cache keys). The purge **must** enumerate `thumbs/{transcription_id}/` and `returned_exams/{graded_test_id}/` by listing, and may use exact paths only for the two scan columns.

**Deletion mechanics.** `gcs_service.delete_folder(prefix)` exists and **has no caller today** — the purge is its first. Verify emptiness with:

```
gcloud storage ls -r gs://grader-vision-pdfs-0438328890/thumbs/{transcription_id}/
gcloud storage ls -r gs://grader-vision-pdfs-0438328890/returned_exams/{graded_test_id}/
gcloud storage ls    gs://grader-vision-pdfs-0438328890/transcriptions/{user_id}/{uuid}.pdf
# and, for the soft-delete window (row 4):
gcloud storage ls --soft-deleted gs://grader-vision-pdfs-0438328890/thumbs/{transcription_id}/
```

---

## 6. Signed URLs and caches (FB-8)

- **No student-data path serves a signed URL.** `gcs_service.generate_signed_url` / `get_signed_urls_for_pages` exist but their only callers are each other (`grep -rn` across `app/` finds no third caller) — dead, like `upload_pdf_with_pages`.
- Page images and the returned PDF are served as **bytes through authenticated API routes** (`/api/v0/transcriptions/{id}/pages/{n}/image`, `…/returned-exam`), behind `Authorization: Bearer`.
- **`next/image` is not used for them** and there is no remote-pattern config for the API host, so **Vercel's edge cache holds none of it**.
- **Browser caching is real and is the residual copy here:** the page-image route answers `Cache-Control: private, max-age=31536000, immutable` when the URL pins a variant (`app/services/thumbnail.py`). A teacher's browser can hold her students' page thumbnails for a year. `private` keeps it out of shared caches. Not purgeable; documented for `OD-B5`.
- **In-process page cache** (`app/services/page_cache.py`) holds rendered page bytes per Cloud Run instance; it dies with the instance and is keyed by `(transcription_id, page, variant)`. Not purgeable, bounded by instance lifetime; worth naming in the audit.

---

## 7. LLM providers — who receives the student's work

From `two_phase_engine.PROD_CONFIG`, `identity.py`, `config.py` and the grader:

| Stage | Provider / model | Receives |
|---|---|---|
| P1 perception | **Google `gemini-3.1-pro-preview`** | the scan **page images** |
| P1 strike check | Google `gemini-3.5-flash` | page images |
| P2 segmentation | **OpenAI `gpt-5.6-luna`** | the transcribed **text** |
| Student identity | Google gemini (top-35 % crop of page 1) | an image containing **her name** |
| Grading | **Anthropic `claude-sonnet-5`** | the transcription text + rubric |
| Rubric extraction | OpenAI `gpt-5.6-terra` | the teacher's DOCX (no student data) |

`GOOGLE_GENAI_USE_VERTEXAI` is set on the service, so the Google calls go through Vertex AI in `GOOGLE_CLOUD_LOCATION` rather than the public Gemini API — a different retention regime from consumer Gemini, and one Noam may want stated in `OD-B5`.

**Retention: UNVERIFIED from here.** Each provider's data-retention terms (and whether zero-retention is enabled on the OpenAI and Anthropic accounts) must be read from those accounts' settings by Noam. This is a residual copy to **document**, never something the purge can reach.

---

## 8. LangSmith (FB-6)

**Tracing is ON in production.** `gcloud run services describe gradervision-backend` shows `LANGCHAIN_TRACING_V2=true`, plus `LANGCHAIN_PROJECT` and `LANGCHAIN_API_KEY`; `app/main.py:37-46` exports them when `langchain_tracing_v2` is set.

**A trace therefore contains the prompts**, which for P2 and for grading are **the student's transcribed answers**, and for the grader also the rubric. The student's *name* reaches a prompt only through the identity crop (an image) — but the trace of a grading call carries her work verbatim.

**Retention and per-run deletion: UNVERIFIED** — both are LangSmith account settings/API, not readable from this repo.

> **`OD-B2` — LangSmith. Recommendation: turn tracing OFF for student-data calls in production, and keep it for rubric extraction.**
> Tagging runs so they can be deleted per `graded_test_id` means building a second deletion system against a third party's API, with its own failure ledger, to protect a copy we do not need to keep. The cheap, complete alternative is not to send it: a flag on the two student-facing stages. If Noam wants the traces for debugging, then the fallback is a short retention set in LangSmith plus that sentence in `OD-B5` — but "we can delete a trace later" should not be believed until someone has done it through the API once.

---

## 9. Logs and error tracking (FB-7)

- **Cloud Logging `_Default` bucket retention: 30 days** (`gcloud logging buckets describe _Default --location=global` → `30`, not locked).
- **Log lines do carry filenames.** The transcription and upload paths log `filename=` (e.g. `transcribe_one`'s retry line, `batch_grading`'s append line, the eval/pipeline lines quoted in CLAUDE.md §13's playbook) — and teachers name files after students. They do **not** carry answers or transcript text. `extra={}` fields render nowhere (CLAUDE.md §8), so only what is in the message string exists.
- There is **no Sentry-like error tracker** in `requirements.txt` or the code.

> **`OD-B4` — log scrubbing. Recommendation: stop logging raw filenames; log the job/transcription id instead, and accept the existing 30-day window for what is already written.**
> The id is what an operator actually needs to join a log line to a row (the 2026-09-10 incident in CLAUDE.md §13 is explicit that the doc id was the missing field, not the filename). This is a small, mechanical change to a handful of log statements, and it removes the only student-identifying content in the logs. Retroactive scrubbing of existing entries is not possible in Cloud Logging without deleting whole buckets; the 30-day expiry is the answer, and it belongs in `OD-B5`'s sentence.

---

## 10. Email (FB-7)

`email_service.py` sends exactly three things: the **verification code**, the **rubric-share** mail (`sender_name`, `rubric_name`, links), and the **onboarding re-ask digest** (`app/scripts/onboarding_reask.py` — teacher name, phone, next-exam date, to `ALERT_EMAIL`). **No student name, filename, grade or answer is ever sent.** `EMAIL_PROVIDER=resend` in production; Resend's retention applies only to teacher-facing mail. Nothing to purge.

---

## 11. Database backups

**UNVERIFIED from here — Noam must read it in the Supabase dashboard** (Project `ngkqawsyqqbhqthgdkpk` → Database → Backups): whether PITR is enabled and its window, and the daily-backup retention for the current plan. There is no SQL that reports a project's backup policy.

Whatever it says, it is a residual copy the purge **cannot** reach: a purged student's rows exist in any backup taken before the purge, until that backup ages out. This is the sentence `OD-B5` most needs to get right. (CLAUDE.md §12 also records an archived pre-migration dump at `gs://grader-vision-pdfs/db-archive/vivi_premigration_20260822.dump` — a frozen copy of the pre-2026-08-23 database, which no purge will ever touch. It should either be named in `OD-B5` or deleted on a schedule; that is a decision, not a finding.)

---

## 12. Client side

- **Downloaded PDFs** on the teacher's machine — outside our control, permanent.
- **Browser HTTP cache** of page thumbnails — up to a year, `private` (row 6).
- **`usePageThumbnails` blob cache** (`frontend/src/components/grade-review/usePageThumbnails.ts`): page images fetched as `blob:` object URLs, held in a `Map` for the life of the mounted component and revoked on unmount. Bounded by the tab's lifetime; it never reaches storage. Named here because a teacher with the dashboard open during a purge keeps her students' page images on screen until she navigates.

---

## 13. Every DELETE path in the codebase (new row)

`grep -rn "db.delete(\|session.delete(\|delete(\|DELETE FROM"` across `app/`, classified. After 032 each row that touches the graph must be explicit and carry its own test.

| Path | Deletes | Relies on a cascade today? | After 032 |
|---|---|---|---|
| `classroom.delete_student` (`:189`) | `students` | **YES — this is the one** | replaced by the purge (AM-B2); the interim guard becomes the blockers step |
| `classroom.delete_class` (`:368`) | `classes` | yes: `class_memberships.class_id` CASCADE | unchanged — #1 keeps its cascade; guard already 409s when batches exist |
| `classroom.remove_student_from_class` (`:423`) | one `class_memberships` row | no | unchanged |
| `users.delete_rubric_share` (`:402`) | `rubric_shares` | no | unchanged |
| `auth_nonce.py:96` | expired `auth_nonces` | no | unchanged |
| `school_resolution.py:151,186` | `user_schools` for one user | no | unchanged |
| `gcs_service.delete_folder` (`:233`) | GCS objects | n/a | **no caller today**; the purge is its first |
| — | **No raw `DELETE FROM` anywhere in `app/`** | | PRV-9 asserts this stays true |

**There is no admin/ops deletion path, no management command, and no scheduled deletion job.** The API endpoint is the only way a student row is deleted today, which is why the interim guard held — and exactly why it is not a safety mechanism (AM-B2).

---

## 14. Supabase triggers, functions, policies, scheduled jobs (new row)

| Check | Result |
|---|---|
| Triggers on graph tables | **one**, unrelated: `update_rubrics_updated_at` on `rubrics` (UPDATE) |
| Public functions | **one**: `update_updated_at_column()` (the trigger's body) |
| RLS enabled | **none** (`pg_class.relrowsecurity` false on every public table) |
| Policies | **none** (`pg_policies` empty) |
| `pg_cron` | **not installed**; extensions are `pg_stat_statements, pgcrypto, plpgsql, supabase_vault, uuid-ossp` |
| Supabase Edge Functions / webhooks | **UNVERIFIED** — not visible from SQL; Noam to confirm none exist on these tables |

Nothing in the database will act on a purge behind our back, and nothing will re-create what it deletes.

---

## 15. `FA-12` lands in §13 — the batch count recompute

`grading_batches.test_count` counts **files that landed**, not graded tests: it is incremented under the FOR-UPDATE lock in `batch_grading.append_file` (`locked_batch.test_count = count + 1`, where `count` is `COUNT(transcription_jobs)`), and the rollup's own truth for jobs-era batches is `COUNT(jobs)` (B9.5). The recompute in the purge is therefore exactly:

```sql
UPDATE grading_batches b
   SET test_count = (SELECT COUNT(*) FROM transcription_jobs j WHERE j.batch_id = b.id)
 WHERE b.id = ANY(:affected_batch_ids);
```

Batch-less (single-flow) tests recompute nothing. M-B6 stands: counts are recomputed from rows, never decremented, and a batch is never auto-deleted.

---

## 16. `FB-2` answered — what `returned_exam_key` references

It is **not** a foreign key and **not** an object name. It is the **cache key** (`returned_exam.current_cache_key`: contract version + stamp position + include-criteria + feedback hash) that names the object at **`returned_exams/{graded_test_id}/{key}.pdf`**. Superseded keys are deliberately left in the bucket (content-addressed; "a stale render is never overwritten in place"), so **the prefix, not the column, is what the purge must delete** (row 5). 2 of 22 production graded tests currently carry a key.

`graded_test_pdfs` is a **separate, empty (0 rows) table** — the older PDF store. It is in the purge set defensively (§13 #2) and its emptiness is recorded here so that a non-zero count later is a signal, not a surprise.

---

## 17. The decision this census adds

> **`OD-B6` (new) — the un-attributable scan. Recommendation: the plan SURFACES it; it never deletes it silently, and it never guesses.**
>
> A transcription with `status='transcribed'` has `student_id` **NULL** by CHECK (the student is assigned at the gate), and no `graded_tests` row points at it. **17 of 38 production transcriptions are in that state.** Such a scan can be a student's exam — her handwriting is in `draft_json` and her paper is in the bucket — and *nothing in the schema attributes it to her*. Today 0 of them carry even a `student_name`.
>
> §0.6 says: when unsure whether something belongs to the student, it does — surface it. So `plan_purge` should report un-attributable scans in the student's **batches** as `unattributable_candidates` (count + job ids, never a name match), the preview should show them, and the dialog should say plainly that unassigned scans in the same exam events are **not** deleted. Deleting them on a name match would delete another student's paper; deleting them silently is the failure this census exists to prevent.
>
> The alternative — extend the purge to name-matched rows — I recommend against, and it is Noam's call.

---

## 18. Recommendations summary (for ratification)

| ID | Decision | My recommendation |
|---|---|---|
| **OD-B1** | Legacy tables (`grading_sessions`, `raw_graded_tests`) | Not in the purge (unreachable, empty, unwritten); `verify_purged` may assert they stay empty; drop them in a later cleanup migration |
| **OD-B2** | LangSmith | Turn tracing **off** for the P2 and grading calls in production; keep it for rubric extraction |
| **OD-B3** | GCS soft-delete | **Keep 7 days**, report it in the verify output, state it on the privacy page |
| **OD-B4** | Log scrubbing | Log ids, not filenames, going forward; accept the 30-day window for what exists |
| **OD-B5** | The privacy-page sentence | Draft: *"When you delete a student, Vivi deletes their scans, transcriptions, gradings and generated files from its database and storage immediately. Copies may persist outside that deletion for a limited time: in encrypted database backups, in deleted-object recovery for up to 7 days, in server logs for up to 30 days, and with the AI providers that processed the exam under their own retention terms."* — every clause is a row above, and each needs its unverified half confirmed (rows 7, 8, 11) before it is published. |
| **OD-B6** | Un-attributable scans | Surface as candidates; never delete on a name match |

---

## 19. What must be true before purge code is written

1. Noam approves this document (the Part B gate).
2. `OD-B1..B6` are ruled.
3. Rows 7, 8 and 11 have their **UNVERIFIED** halves filled in by whoever holds those accounts.
4. Migration 032 is generated from a **fresh** read of row 1's query against production at deploy time — not from this table, which is a 2026-09-22 snapshot of a schema that is still changing.
