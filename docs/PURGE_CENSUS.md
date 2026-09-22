# PURGE CENSUS v2 — the blast radius of deleting a student

**Phase B0 deliverable** of `PR_student_profile.md` §11. **Gate: migration 032, and anything that deletes, waits for Noam's sign-off on this version.** Commit (1), the red tests, proceeds in parallel (ruling 2026-09-22).

**Author:** Claude · **v1:** 2026-09-22 · **v2 read dates:** 2026-09-22/23 · **Status:** v2, awaiting sign-off

**What was read.** Production Postgres (Supabase `ngkqawsyqqbhqthgdkpk`, eu-central-1, ledger head **030**) with SELECT-only queries; every GCP project this account can see (33, via `gcloud projects list`) and every bucket in each; the code at **`origin/main` 2232f3d** (rows 5, 6, 9, 10, 13 re-read there, as ruled); the providers' current published terms, fetched 2026-09-22; the LangSmith workspace through its API. Where a fact could not be read, the row says **UNVERIFIED**, names who can read it, and names what is missing.

**Production scale at read time:**

```sql
SELECT COUNT(*) FROM students;            -- 18   (notes IS NOT NULL: 0)
SELECT COUNT(*) FROM transcriptions;      -- 38
SELECT COUNT(*) FROM graded_tests;        -- 22   (2 with returned_exam_key; 7 approved, 0 batch-less)
SELECT COUNT(*) FROM transcription_jobs;  -- 39   (38 with transcription_id)
SELECT COUNT(*) FROM graded_test_pdfs;    -- 0
SELECT COUNT(*) FROM grading_batches;     -- 15
```

### What changed from v1

| Where | Change |
|---|---|
| Row 1, #8 | **Corrected.** The deferral on `regraded_to_id` exists for `extend_chain`'s insert order, not for the delete. |
| Row 1 | Rewritten to AM-B1's final form: keyed on referencing **tables**, so all 18 FKs out of the five tables are listed, not just edges into the graph. AM-B4's composite FKs added. |
| Row 2 | Pattern set gains `%name%`; `students.full_name` added (G). Every column the pattern catches is classified. |
| Rows 5, 6, 9, 10, 13 | Re-read on `main`. Line numbers corrected; the `delete_student` guard on main checks graded tests only (Part A widens it). `next.config` does declare `images.remotePatterns` (v1 said none), but for `http://localhost` only. |
| Row 7 | Retention per provider with links; `GOOGLE_CLOUD_LOCATION`; the pre-GA question answered; live Vertex cache setting read. |
| Row 8 | **Corrected.** v1 said P2's prompts reach LangSmith. They do not: only the grader and feedback calls are traced. Retention tier, region, copies and the deletion proof recorded. |
| Row 11, 14 | Still **UNVERIFIED** — the Management API token in `backend/.env` answers **401** and the CLI is not logged in. **I need an access token from Noam.** |
| New | A (every project and bucket, the dump located), B (shared objects), C (historical orphans), D (consistency), E (`test_count` eras), F (DELETE paths beyond `app/`), rulings OD-B1..B8, amendments AM-B1/B4/B5/B6, PRV-8/10/11/12. |
| New decisions | **OD-B9** (three more database archives, one of them after launch) and **OD-B10** (students' work in the two public repositories). |

---

## 0. The finding that reorders Part B (unchanged)

`DELETE FROM students WHERE id = S` succeeds today, and what it does is decided by the constraint graph before any code can list the objects those rows point at. It deletes her memberships, every graded test naming her, every approved transcription naming her and, through those, their graded tests. **It leaves every GCS object, every `transcription_jobs` row (SET NULL keeps filename and object path with nothing to find them by), and every never-assigned transcription.** A purge on top of this graph would pass its own tests while PRV-6 is false by construction. AM-B1 turns the cascades off, and the purge deletes explicitly.

---

## 1. Postgres — the FK graph (before and after 032)

Fresh read, 2026-09-22, production:

```sql
SELECT tc.table_name, kcu.column_name, ccu.table_name AS ref, rc.delete_rule,
       tc.is_deferrable, tc.initially_deferred, tc.constraint_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
JOIN information_schema.constraint_column_usage ccu
  ON tc.constraint_name = ccu.constraint_name AND tc.table_schema = ccu.table_schema
JOIN information_schema.referential_constraints rc
  ON tc.constraint_name = rc.constraint_name AND tc.table_schema = rc.constraint_schema
WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
  AND tc.table_name IN ('students','transcriptions','graded_tests','graded_test_pdfs',
                        'transcription_jobs','class_memberships')
ORDER BY 1, 2;
```

**AM-B1, final form:** every FK whose **referencing table** is one of `students`, `transcriptions`, `graded_tests`, `graded_test_pdfs`, `transcription_jobs` becomes **ON DELETE NO ACTION**, including FKs to `rubrics`, `users` and `grading_batches` and the chain self-FKs. `class_memberships` is outside the set and keeps its cascades. 032 is generated from a fresh read of the query above at deploy time, not from this table.

| # | Constraint | FK | Today | 032 target |
|---|---|---|---|---|
| 1 | `graded_test_pdfs_graded_test_id_fkey` | `graded_test_pdfs.graded_test_id → graded_tests` | CASCADE | **NO ACTION** |
| 2 | `graded_test_pdfs_rubric_id_fkey` | `graded_test_pdfs.rubric_id → rubrics` | CASCADE | **NO ACTION** |
| 3 | `graded_tests_batch_id_fkey` | `graded_tests.batch_id → grading_batches` | SET NULL | **NO ACTION** |
| 4 | `graded_tests_regraded_from_id_fkey` | `graded_tests.regraded_from_id → graded_tests` | SET NULL | **NO ACTION** |
| 5 | `graded_tests_regraded_to_id_fkey` | `graded_tests.regraded_to_id → graded_tests`, **DEFERRABLE INITIALLY DEFERRED** | SET NULL | **NO ACTION, deferral kept** |
| 6 | `graded_tests_rubric_id_fkey` | `graded_tests.rubric_id → rubrics` | CASCADE | **NO ACTION** |
| 7 | `graded_tests_student_id_fkey` | `graded_tests.student_id → students` | CASCADE | **NO ACTION** |
| 8 | `graded_tests_transcription_id_fkey` | `graded_tests.transcription_id → transcriptions` | CASCADE | **NO ACTION** |
| 9 | `graded_tests_user_id_fkey` | `graded_tests.user_id → users` | CASCADE | **NO ACTION** |
| 10 | `students_user_id_fkey` | `students.user_id → users` | CASCADE | **NO ACTION** |
| 11 | `transcription_jobs_batch_id_fkey` | `transcription_jobs.batch_id → grading_batches` | CASCADE | **NO ACTION** |
| 12 | `transcription_jobs_rubric_id_fkey` | `transcription_jobs.rubric_id → rubrics` | CASCADE | **NO ACTION** |
| 13 | `transcription_jobs_transcription_id_fkey` | `transcription_jobs.transcription_id → transcriptions` | **SET NULL** | **NO ACTION** |
| 14 | `transcription_jobs_user_id_fkey` | `transcription_jobs.user_id → users` | CASCADE | **NO ACTION** |
| 15 | `transcriptions_batch_id_fkey` | `transcriptions.batch_id → grading_batches` | SET NULL | **NO ACTION** |
| 16 | `transcriptions_rubric_id_fkey` | `transcriptions.rubric_id → rubrics` | CASCADE | **NO ACTION** |
| 17 | `transcriptions_student_id_fkey` | `transcriptions.student_id → students` | CASCADE | **NO ACTION** |
| 18 | `transcriptions_user_id_fkey` | `transcriptions.user_id → users` | CASCADE | **NO ACTION** |
| — | `class_memberships_class_id_fkey` | `class_memberships.class_id → classes` | CASCADE | CASCADE *(outside the set)* |
| — | `class_memberships_student_id_fkey` | `class_memberships.student_id → students` | CASCADE | CASCADE *(outside the set; the purge still deletes memberships explicitly)* |

**#5, corrected.** The deferral exists for **`extend_chain`'s insert order** (link R1 → flush → insert R2 → commit; migration 010), not for any delete. A one-statement delete of a whole chain needs only statement-end checking, which NO ACTION already gives. 032 must not touch the deferral, for `extend_chain`'s sake.

**Why NO ACTION and not RESTRICT.** RESTRICT is checked per row and cannot be deferred, so a one-statement delete of a revision chain becomes order-dependent. NO ACTION is checked at statement end. Both refuse an unexplained delete; only NO ACTION lets the planned one through.

**Consequence (AM-B1).** After 032, deleting a rubric, a user or a batch **fails loudly** while student data references it. No code path in `app/` does any of those today (row 13). Every test teardown that does is listed in F and becomes explicit in the 032 commit.

**AM-B4 — tenant consistency, enforced by the database.** 032 also adds:

| New constraint | Definition |
|---|---|
| `students_id_user_id_key` | `UNIQUE (id, user_id)` on `students` |
| `transcriptions_id_user_id_key` | `UNIQUE (id, user_id)` on `transcriptions` |
| `transcriptions_student_tenant_fkey` | `(student_id, user_id) → students(id, user_id)` |
| `graded_tests_student_tenant_fkey` | `(student_id, user_id) → students(id, user_id)` |
| `graded_tests_transcription_tenant_fkey` | `(transcription_id, user_id) → transcriptions(id, user_id)` |
| `transcription_jobs_transcription_tenant_fkey` | `(transcription_id, user_id) → transcriptions(id, user_id)` |

All four `*_tenant_fkey` are NO ACTION (AM-B1 covers them: their referencing tables are in the set). The single-column FKs stay, so ORM relationships are untouched; `__table_args__` mirrors the new constraints for the schema-canon suite. MATCH SIMPLE means a NULL `student_id` (a never-assigned scan) is not checked, which is correct. **Query D found no violating rows**, so nothing blocks 032 on this account.

---

## 2. Postgres — the PII registry

Patterns: `%name%`, `%student_name%`, `%filename%`, `%gcs%`, `%object_path%`, `%_key`, and `data_type = 'jsonb'`. The §16.1 registry test set-compares the columns these catch against this table; an unclassified new column fails it.

**Every `%name%` column in `public`** (G), classified:

| Column | Holds | Disposition |
|---|---|---|
| `students.full_name` | **her name** | **deleted with the row** (the last step of the plan) |
| `graded_tests.student_name` | her name | deleted with the row |
| `graded_tests.filename` | a filename, often her name | deleted with the row |
| `transcriptions.student_name` | her name | deleted with the row |
| `transcriptions.filename` | a filename, often her name | deleted with the row |
| `transcription_jobs.source_filename` | a filename, often her name | deleted with the row, never NULLed |
| `graded_test_pdfs.filename` | a filename | deleted with the row (0 rows) |
| `grading_sessions.student_name`, `.filename` | legacy | OD-B1: not referenced; `verify_purged` asserts the table is empty |
| `raw_graded_tests.student_name`, `.filename` | legacy | OD-B1: same |
| `raw_rubrics.name`, `.source_filename` | teacher's document, legacy | out of scope; empty |
| `rubric_extraction_jobs.source_filename` | teacher's rubric file | out of scope |
| `rubrics.name` | teacher's rubric | out of scope |
| `grading_batches.name` | exam-event name, teacher's | out of scope (the batch survives) |
| `classes.name` | class name, teacher's | out of scope |
| `users.full_name` | the teacher | out of scope (account deletion is a follow-up) |
| `schools.name` | an institution | out of scope |
| `subject_matters.name_en`, `.name_he` | reference data | out of scope |

**The other patterns** (unchanged from v1 except where noted):

| Column | Holds | Disposition |
|---|---|---|
| `graded_tests.draft_json` / `contract_json` | her answers, the grading, the feedback | deleted with the row |
| `graded_tests.returned_exam_key` | cache key → `returned_exams/{id}/{key}.pdf` | row deleted; object deleted **by prefix** (row 5) |
| `transcriptions.draft_json` / `contract_json` / `review_json` | her handwriting, transcribed | deleted with the row |
| `transcriptions.gcs_uri` / `gcs_bucket` / `gcs_object_path` | → the scan | row deleted; object deleted from **the row's own** `gcs_bucket` |
| `transcription_jobs.source_gcs_object_path` | → the same scan | row deleted; object deleted once (PRV-12) |
| `graded_test_pdfs.gcs_*` | → a signed exam PDF | row + object (0 rows) |
| `grading_batches.transcription_failures` (jsonb) | `{filename, …}` of failed uploads | scrubbed in place; **0 batches carry entries** (E) |
| `grading_batches.stamp_position_default` (jsonb) | no student data | untouched |
| `grading_plans.plan_json` / `skeleton_json` | rubric algebra | untouched |

---

## 3. Postgres — the legacy tables (OD-B1, ruled)

`grading_sessions` 0 rows, `raw_graded_tests` 0, `raw_rubrics` 0; nothing in `app/` constructs them. **Ruling:** the purge does not reference them; `verify_purged` asserts they stay empty; they are dropped in a later cleanup PR.

---

## 4. GCS — every project, every bucket (A)

**Projects.** `gcloud projects list` shows 33 projects on this account. Every bucket in every one was listed. **Only `gen-lang-client-0438328890` holds Vivi buckets.** It is also the only project the backend and its deploys use (Cloud Run, Cloud Build, Cloud Tasks, Vertex AI, Secret Manager).

| Bucket | Location | Soft delete | Holds |
|---|---|---|---|
| **`grader-vision-pdfs-0438328890`** | europe-west1 | **7 days** | all student data, plus `db-archive/` (row 4a) and `rubric-sources/` |
| `gen-lang-client-0438328890_cloudbuild` | US | 7 days | build artefacts |
| `run-sources-gen-lang-client-0438328890-europe-west1` | europe-west1 | 7 days | deploy sources (code only) |
| `run-sources-gen-lang-client-0438328890-us-central1` | us-central1 | 7 days | deploy sources (code only) |

**Rows → buckets:**

```sql
SELECT gcs_bucket, COUNT(*) FROM transcriptions   GROUP BY 1;  -- grader-vision-pdfs-0438328890: 38
SELECT gcs_bucket, COUNT(*) FROM graded_test_pdfs GROUP BY 1;  -- no rows
```

`transcription_jobs` has no bucket column. All 39 of its paths are under `transcriptions/`.

**The three prefix families, in every bucket:** they exist only in `grader-vision-pdfs-0438328890`. The other three buckets hold none.

| Prefix | Objects | Size | Soft-deleted now |
|---|---|---|---|
| `transcriptions/` | 39 | 156.3 MB | 0 |
| `thumbs/` | 45 | 1.7 MB | 0 |
| `returned_exams/` | 2 | 4.4 MB | 0 |

**Bucket handling (ruled).** Scans are deleted from each row's own `gcs_bucket`. Prefix families are listed in every bucket in the known set. A row naming a bucket outside the set makes the purge refuse. **The known set today is `{grader-vision-pdfs-0438328890}`.**

**OD-B3 (ruled):** keep the 7-day soft-delete window. `verify_purged` reports the soft-deleted object count and the restorable-until date (`gcloud storage ls --soft-deleted`). The window is also the safety net under PRV-11.

### 4a. The database archives

**The dump is not in a separate bucket.** CLAUDE.md §12 names it `gs://grader-vision-pdfs/db-archive/…`, and that bucket does not exist. The archive is `db-archive/` **inside the student-data bucket itself**, and it holds **four** objects, not one:

| Object | Uploaded (UTC) | Size | Contents (`pg_restore -l`) |
|---|---|---|---|
| `db-archive/vivi_premigration_20260822.dump` | 2026-08-22 23:10:02 | 698 KB | the Mumbai database before the Frankfurt move; 20 tables incl. `students`, `transcriptions`, `graded_tests`, `transcription_jobs`, `graded_test_pdfs` |
| `db-archive/vivi_precleanup_20260823.dump` | 2026-08-22 23:10:35 | 707 KB | the Frankfurt copy before the test-data cleanup; same 20 tables |
| `db-archive/vivi_prod_prelaunch_20260911_114639.dump` | 2026-09-11 11:49:10 | 1.4 MB | production before the pre-launch wipe; 59 `TABLE DATA` entries incl. `auth.users`, `students`, `transcriptions`, `graded_tests`, `transcription_jobs`, `graded_test_pdfs`, `class_memberships` |
| `db-archive/vivi_prod_prelaunch_20260911_114639.json` | 2026-09-11 11:49:32 | 9.3 MB | a JSON export of the same moment: 25 tables, incl. **21 students, 175 transcriptions, 45 graded tests, 148 jobs** |

All four are under the bucket's 7-day soft-delete policy. No lifecycle rule ages them out.

- **The ruled one (`vivi_premigration_20260822.dump`).** Confirmed a pre-2026-08-23 copy. **Not deleted yet**, because "anything that deletes waits for v2 sign-off". On sign-off:
  ```
  gcloud storage rm gs://grader-vision-pdfs-0438328890/db-archive/vivi_premigration_20260822.dump \
      --project gen-lang-client-0438328890
  ```
  It stays restorable for 7 days after that (OD-B3), and I will record the restorable-until date.
- **The other three** are the subject of **OD-B9** (row 18). The September 11 pair is the notable one. It postdates launch preparation, holds **more student rows than production does today** (18 students now, 21 then), and so keeps data that production has since deleted. Any future purge will miss it.

---

## 5. GCS — writers, naming, and how the purge finds objects (re-read on `main`)

| Writer | Object path | Student data? | Found by |
|---|---|---|---|
| `batch_grading.append_file` (`app/api/v0/batch_grading.py:690`, upload `:693`) | `transcriptions/{user_id}/{uuid4}.pdf` | **the scan** | the exact path, on `transcriptions.gcs_object_path` **and** `transcription_jobs.source_gcs_object_path` |
| `transcribe_one` (`app/services/transcribe_one.py:99`, upload `:101`, retry `:150`) | `transcriptions/{user_id}/{uuid}.pdf` | **the scan** (single flow) | same |
| page thumbnails (`app/api/v0/transcription.py:427` path, `:481` upload; `thumbnail.gcs_object_path`, `app/services/thumbnail.py:228`) | `thumbs/{transcription_id}/p{n}_…` (variant token in the name) | **rendered page images** | **prefix listing** `thumbs/{transcription_id}/` |
| returned exam (`app/services/returned_exam_store.py:101` path, `:132` upload; `returned_exam.gcs_object_path`, `app/services/returned_exam.py:670`) | `returned_exams/{graded_test_id}/{cache_key}.pdf` | **the signed exam** | **prefix listing** `returned_exams/{graded_test_id}/` |
| rubric sources (`app/api/v0/rubric_extraction_jobs.py:210`, upload `:211`) | `rubric-sources/{user_id}/{sha256}.docx\|pdf` | teacher's document | out of scope |
| `gcs_service.upload_pdf_with_pages` (`app/services/gcs_service.py:176`) | `{folder}/{session_id}/…` | — | **no caller** |

Thumbnail names carry a settings-derived variant token, and superseded returned-exam keys are left in place by design. **So two of the four student-data families can only be found by listing** (M-B7). Exact paths are used only for the two scan columns.

**Deletion mechanics.** `gcs_service.delete_folder` (`app/services/gcs_service.py:233`, `blob.delete()` at `:245`) has **no caller** on main. The purge is its first caller, behind PRV-11.

### 5a. Shared objects (B)

Grouping every `(bucket, path)` across `transcriptions ∪ transcription_jobs ∪ graded_test_pdfs`:

- **38 objects are referenced by more than one row**, and in every case the two rows are a transcription and its own job (the same upload, two pointers).
- **0 objects** are referenced by more than one transcription, **0** by rows of different students, **0** by rows of different users.

**PRV-12 (SharedObjects):** an object is deleted only if every row referencing it is in the plan; otherwise the purge refuses and reports. The transcription-and-its-job pair is always inside one subtree (AM-B5), so today's data never trips it.

### 5b. Historical orphans (C, OD-B7)

- `transcription_jobs` with `transcription_id IS NULL`: **1**, and it is `failed`. `status <> 'failed'`: **0**. **No job was orphaned by a student-delete cascade** in the current data.
- **Bucket diff.** Every object under the three prefixes, compared with every path, `thumbs/{transcription_id}/` and `returned_exams/{graded_test_id}/` the rows reference: **0 objects** older than 24 h have no referencing row. (The failed job's scan is referenced by that job row, so it is not an orphan object. It is a row nothing attributes to a student, which is OD-B6/OD-B8's population.)
- **Proposed one-time sweep list: empty.** Nothing to approve. `orphan_sweep_list.json` is kept with the census evidence.

---

## 6. Signed URLs and caches (re-read on `main`)

- **No student-data path serves a signed URL.** `gcs_service.generate_signed_url` (`:100`) has one caller, `get_signed_urls_for_pages` (`:213`, calling it at `:229`), and that function has **no caller** in `app/`. (`:138` is the storage client's own `blob.generate_signed_url` inside it.)
- Page images and the returned PDF are served **as bytes through authenticated routes**: `/api/v0/transcriptions/{id}/pages/{n}/image` and `/api/v0/graded_test/{id}/returned-exam` (`app/api/v0/grading.py:919`); the batch ZIP is at `app/api/v0/batch_grading.py:1053`.
- **`next/image` is not imported anywhere in `frontend/src`.** `next.config` declares `images.remotePatterns` for `http://localhost` only, so the Vercel image optimiser caches none of these images.
- **Browser cache:** the page-image route answers `Cache-Control: private, max-age=31536000, immutable` when the URL pins a variant, else `private, max-age=60` (`app/api/v0/transcription.py:415-419`; `IMMUTABLE_MAX_AGE`, `UNPINNED_MAX_AGE` at `app/services/thumbnail.py:67,70`). A year, on possibly shared staff-room machines, is a named follow-up. The returned-exam routes set no `Cache-Control`.
- **In-process page cache** (`app/services/page_cache.py`, used at `transcription.py:331,421`): per Cloud Run instance, dies with it.

---

## 7. LLM providers — who receives the student's work, and for how long (H)

| Stage | Provider / model | Receives | Traced to LangSmith? |
|---|---|---|---|
| P1 perception | Google Vertex AI, `gemini-3.1-pro-preview` | the scan's **page images** | **no** (google-genai SDK directly) |
| Student identity | Google Vertex AI, `gemini-3.1-pro-preview` (same provider and slot pool as P1) | a crop of page 1 **with her name**, and the filename | no |
| P1 strike check | Google Vertex AI, `gemini-3.5-flash` | page images | no |
| P2 segmentation | OpenAI `gpt-5.6-luna` (`chat.completions`, `store` left at its default, false) | the transcribed **text** | **no** (OpenAI SDK directly) |
| Grading (v5) | Anthropic `claude-sonnet-5` (`config.grader_model_*`, no service override) | the transcribed answers + rubric | **yes** (LangChain) |
| Feedback | Anthropic `claude-sonnet-5` (`config.feedback_model_*`, no service override) | verdicts + quotations of her answers | **yes** (LangChain) |
| Rubric extraction, plan builds | OpenAI / Anthropic | the teacher's rubric only | out of scope |

**Service environment** (`gcloud run services describe gradervision-backend`): `GOOGLE_GENAI_USE_VERTEXAI=true`, **`GOOGLE_CLOUD_LOCATION=global`**, `TRANSCRIPTION_ENGINE=two_phase`. Vertex lists `global` as the model's only supported location, so **no data residency is selected** for the Google calls.

**Retention, from each provider's current published terms (read 2026-09-22):**

| Provider | Default retention of API inputs/outputs | Exceptions | Source |
|---|---|---|---|
| **Anthropic** (API) | deleted **within 30 days** of receipt or generation | up to **2 years** if flagged under the Usage Policy (classifier scores up to 7 years); 5 years for submitted feedback; longer if required by law; **zero data retention by agreement** | [privacy.claude.com — How long do you store my organization's data?](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data) (updated 2026-07-01); [API and data retention](https://platform.claude.com/docs/en/manage-claude/api-and-data-retention) |
| **OpenAI** (API) | abuse-monitoring logs up to **30 days** | zero data retention / modified abuse monitoring **by approval**; `store=true` objects persist until deleted (Vivi does not set it) | [Your data — OpenAI API](https://developers.openai.com/api/docs/guides/your-data) |
| **Google** (Vertex AI) | **in-memory cache, 24-hour TTL**, on by default and **ON for this project** (`GET …/projects/gen-lang-client-0438328890/cacheConfig` returns no `disableCache`) | prompt logs **up to 90 days**, only when safety classifiers flag a prompt and only for customers under the GCP Terms of Service (opt-out by request); request–response logging **off** (no `PublisherModelConfig` exists for either Gemini model) | [Zero data retention](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/data-governance) (updated 2026-09-22); [Abuse monitoring](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/abuse-monitoring) (updated 2026-09-22) |

Training exclusion: Noam confirms all three process under terms that exclude training use. For Google I read the clause myself: the Service Terms' "Training Restriction" section, restated on the Vertex zero-data-retention page. **Whether zero retention is enabled on our OpenAI and Anthropic accounts is Noam's to confirm** (account settings, not readable from here).

**The pre-GA question.** The Service Specific Terms, *Pre-GA Offerings Terms* §(d) (last modified 2026-09-16), say:

> "Except as otherwise expressly indicated in a written notice or Google documentation, no data processing terms (including the Cloud Data Processing Addendum) apply to Pre-GA Offerings and Customer should not use Pre-GA Offerings to process personal data…"

**The exception applies to our model.** The `gemini-3.1-pro-preview` model page (launch stage "Public preview"; page updated 2026-09-22) states:

> "For this Generative AI Preview offering, Customers may elect to use it for production or commercial purposes, or disclose Generated Output to third-parties, and may process personal data as outlined in the Cloud Data Processing Addendum, subject to the obligations and restrictions described in the agreement under which you access Google Cloud."

The [Generative AI Preview Products terms](https://cloud.google.com/terms/genai-preview-products) (last modified 2026-08-31) list **Gemini 3.1 Pro** among the models exempt from the "evaluation and testing only" restriction. **So for this model, pre-GA status does not change data handling: the Cloud Data Processing Addendum applies, by Google's own documentation.** The exemption rests on a documentation statement Google can change. If Vivi moves to another preview model, this check must be repeated, because the default for pre-GA is **no data processing terms at all**.

---

## 8. LangSmith (H, OD-B2)

- **What is traced.** Only LangChain calls: the grader and the feedback agent (row 7). The two-phase transcription engine (P1, identity, strike check, P2) calls its SDKs directly. **Page images never reach LangSmith. P1 has no trace at all.**
- **The rollback caveat.** The legacy engine (`TRANSCRIPTION_ENGINE=legacy`, the documented rollback) decorates its vision calls with `@traceable` (`app/services/handwriting_transcription_service.py:152, 351, 449, 1049, …`), and their arguments are the **base64 page images** (`images_b64`, `page_b64`). **A rollback to the legacy engine would send scans to LangSmith.** It needs tracing off, or the same tagging, before it is ever used again.
- **Project, tier, region.** Production `LANGCHAIN_PROJECT=lang-projects`, retention tier **`shortlived`** (base, **14 days**, the shortest available); the workspace default is also `shortlived`. Endpoint `api.smith.langchain.com`, so the data is in the **US** region. ([Data retention](https://docs.langchain.com/langsmith/data-purging-compliance): base 14 days; extended tier capped at 180 days from 2026-09-14.)
- **Copies.** The workspace has **no datasets, no annotation queues and no automation rules**, so no production trace has been copied anywhere that would outlive it. Keeping it that way (OD-B2) is a workspace policy; code cannot enforce it.
- **Local development writes to the same project.** `backend/.env` also carries `LANGCHAIN_PROJECT=lang-projects`. Recommendation: rename the local project (for example `vivi-dev`) so production traces are the only thing in `lang-projects`.
- **Tagging (OD-B2, shipped as its own PR, `feat/langsmith-student-run-metadata`).** Every grading and feedback run carries `graded_test_id` and `transcription_id` metadata and the `student-data` tag.
- **The deletion proof, and what it found.**
  1. Two tagged runs in a dedicated dev project `vivi-erasure-proof`, created with the real helper: a TARGET and a CONTROL.
  2. `POST /api/v1/runs/delete` **by metadata** answered **403 "bulk run deletes are not enabled"** on this workspace.
  3. The same endpoint **by trace id** (`session_id` + `trace_ids`) answered **202 "Run deletes queued"** (2026-09-22).
  4. **Not yet gone.** At 22:08 UTC on 2026-09-22 the target was still readable and the control still present. LangSmith's documentation states that the delete job **runs on the weekend**, with no confirmation. **I will re-check after the weekend (Monday 2026-09-28)**, then delete the dev project.
- **The runbook this makes true.** For an explicit erasure request:
  1. **Find** by metadata: `list_runs(project_name="lang-projects", filter='and(eq(metadata_key, "graded_test_id"), eq(metadata_value, "<id>"))')`, and the same for `transcription_id`.
  2. **Delete** by trace id: `POST /api/v1/runs/delete {session_id, trace_ids}`, up to 1000 per request.
  3. **Verify** by re-querying after the weekend job.

  Deleting by metadata, as ruled, needs LangSmith to enable bulk deletes on the workspace. **That is a support request for Noam.** Until then the find-then-delete-by-id form is the working path. Either way, the 14-day tier expires every trace before most erasure requests could be processed.

---

## 9. Logs and error tracking (re-read on `main`; OD-B4)

- **Cloud Logging `_Default` retention: 30 days**, not locked (re-read 2026-09-22).
- **On `main`, 17 live log statements** carry a filename or a name-shaped identifier. The largest is the transcription pipeline using the original filename as its `doc_id`, which prefixes every pipeline line. Also: `identity.py` logs the name it found; `batch_grading` logs append failures with the filename; `transcribe_one`'s retry line; `net_diag` labels. **OD-B4's PR (`fix/log-ids-not-filenames`) removes all 17** and adds `tests/test_logs_carry_no_student_names.py`: a structural scan of `app/` whose exemptions are themselves re-verified as dead code. **The 30-day clock for what is already written starts at that deploy.**
- Request logs carry URL paths, which contain ids only. `extra={}` fields render nowhere (CLAUDE.md §8).
- No Sentry-like error tracker exists.

---

## 10. Email (re-read on `main`)

`app/services/email_service.py` has four provider `send_email` implementations (`:43`, `:114`, `:346`, `:428`) and `send_rubric_share_email` (`:491`). Live callers: `app/services/verification_email.py:65` (the verification code) and `app/scripts/onboarding_reask.py:259` (the re-ask digest to `ALERT_EMAIL`: teacher name, phone, exam date). **No student name, filename, grade or answer is sent.** The only sender that would carry student data is `app/grading_orchestrator.py:149` (a Gmail "grading complete" mail), and that module is **dead**: nothing imports it, which OD-B4's test now pins.

---

## 11. Database backups (H) — UNVERIFIED, token needed

**I lack an access token.** The `SUPABASE_ACCESS_TOKEN` in `backend/.env` answers **401** on `GET https://api.supabase.com/v1/projects/ngkqawsyqqbhqthgdkpk/database/backups`, and Supabase CLI 2.110.0 is not logged in. **Noam: please provide a Management API token** (Account → Access Tokens). With it I will read:

- `GET /v1/projects/ngkqawsyqqbhqthgdkpk/database/backups`: whether PITR is on, its window, and the daily-backup list and retention;
- the plan's encryption-at-rest statement. Supabase encrypts storage at rest, but the ruling makes "encrypted" conditional on this row, so it stays out of the sentence until it is read.

Whatever the answer, a purged student's rows persist in every backup taken before the purge until it ages out. That is `{N}` in OD-B5.

---

## 12. Client side (unchanged)

Downloaded PDFs on the teacher's devices (permanent, outside our control); the browser cache of page images (row 6); the `usePageThumbnails` `blob:` cache (tab lifetime).

---

## 13. Every DELETE path (re-read on `main`, plus F)

### In `app/`

| Path (`main`) | Deletes | Relies on a cascade? | After 032 |
|---|---|---|---|
| `classroom.delete_student` (`app/api/v0/classroom.py:151`, delete `:165`) | `students` | **yes** | main's guard 409s **only when graded tests exist**. Part A widens it to graded tests **or** transcriptions (`student_has_data`). Part B replaces the endpoint with the purge. |
| `classroom.delete_class` (`:307`, delete `:321`) | `classes` | yes: `class_memberships.class_id` CASCADE | unchanged (outside the set) |
| `classroom.remove_student_from_class` (`:356`, delete `:376`) | one membership | no | unchanged |
| `users.delete_rubric_share` (`app/api/v0/users.py:376`, delete `:402`) | `rubric_shares` | no | unchanged |
| `auth_nonce` (`app/services/auth_nonce.py:96`) | expired nonces | no | unchanged |
| `school_resolution` (`app/services/school_resolution.py:151, 186`) | `user_schools` of one user | no | unchanged |
| `gcs_service.delete_folder` (`app/services/gcs_service.py:233`) | GCS objects | n/a | **no caller**; the purge is its first, behind PRV-11 |

No raw `DELETE FROM` exists in `app/`. There is no admin deletion path and no scheduled deletion job.

### Beyond `app/` (F)

Searched: `backend/tests/`, `backend/scripts/`, `backend/app/scripts/`, the three eval suites, `backend/migrations/`, `.github/workflows/`.

Each teardown's rows were read at its fixture, not guessed from its name.

**Two helpers break (12 call sites):**

| Where | Deletes | Breaks under 032 because | Fix in the 032 commit |
|---|---|---|---|
| `tests/api/test_batch_grading.py:527` `_delete_batch_cascade` (called at `:602`, `:723`) | a batch created through the real append flow | named for the cascade it relies on: the batch's jobs (#11) and transcriptions (#15) now refuse | delete the batch's subtrees explicitly, children first |
| `tests/api/test_revision_flows.py:319` `_delete_row_cascade` (10 call sites, `:362`–`:603`) | **one** row of a revision chain (R2, or R1 at `:578`) | its chain neighbour still references it: R1's `regraded_to_id` (#5, checked at commit) or R2's `regraded_from_id` (#4) | delete the **whole chain in one statement** |

**The rest survive, because their deletes are already explicit and in dependency order:**

| Where | Deletes | Why it survives |
|---|---|---|
| `tests/api/test_revision_flows.py:828` | the batch's graded tests (one statement), then the batch | the chain goes in one statement; the fixture's transcription carries no `batch_id` |
| `tests/api/test_graded_test_approval.py:197` | one graded test | approval builds no chain; nothing references the row |
| `tests/api/test_s3_classroom.py:242` | a batch | it only exists to block a class delete; no rows reference it |
| `tests/api/test_s3_classroom.py:296, 301` | graded test, then transcription | already in order; no job was created |
| `tests/api/test_transcription_endpoints.py:187` | **a rubric** | the request under test answers 400, so no row references the rubric |
| `tests/api/test_transcription_page_render.py:113` | a transcription | its fixture creates no graded test and no job |
| `tests/api/test_transcription_review.py:174-182` | graded tests → transcriptions → batch | already in order; these tests create no jobs |
| `tests/services/test_onboarding_reask.py:70` | **users** | the users it makes own nothing |
| `tests/services/test_plan_build_runner.py:201`, `tests/services/test_plan_kick.py:48` | `grading_plans`, then **a rubric** | no student row references these rubrics |

**Not FK paths:**

| Where | What | Disposition |
|---|---|---|
| `backend/scripts/gcs_prefix_cleanup.py` | deletes GCS objects by hand (dry-run by default) | must pass PRV-11's allow-list before any real run |
| `backend/scripts/schema_attest.py:15` | documents the owner's hand-run `TRUNCATE` wipe | a `TRUNCATE` fires no row-level FK actions, and refuses FK-referenced tables unless all are listed or `CASCADE` is given; the procedure is the owner's |
| `backend/migrations/007`, `008` | `DROP TABLE … CASCADE` | historical, already applied |
| eval suites, conftests, CI | — | no deletes found |

**Never exempted (ruling F).** The two fixes make the deletion explicit in dependency order. Neither loosens a constraint. The survivors depend on having no dependents, so a fixture that later adds one fails loudly, which is the point. The proof is not this reading. The 032 commit runs the full suite against a database that has 032 applied.

**Operational note.** Vivi-Test is **shared** by every branch. Applying 031 there broke main-based branches (`UndefinedColumn notes`), and I restored it. 032 on Vivi-Test will break every **main-based** branch's cascade-reliant teardowns in the same way. Apply it there only on the commit that fixes them, and tell whoever else is running the suite.

---

## 14. Supabase triggers, functions, policies, jobs (H)

Unchanged from v1: one trigger, unrelated (`update_rubrics_updated_at`); one function; no RLS; no policies; no `pg_cron`. Database webhooks would appear as triggers, and none exist. **Edge Functions: UNVERIFIED**, blocked on the same missing token (`supabase functions list --project-ref ngkqawsyqqbhqthgdkpk`).

---

## 15. `test_count` eras (E)

```sql
-- batches with test_count > 0 and zero jobs (pre-jobs era): 0 of 15
-- jobs-era batches whose test_count ≠ COUNT(jobs):          0
-- batches with transcription_failures entries:               0
```

Every production batch is jobs-era, and every one already satisfies `test_count = COUNT(jobs)`. So the recompute is exact on all current data:

```sql
UPDATE grading_batches b
   SET test_count = (SELECT COUNT(*) FROM transcription_jobs j WHERE j.batch_id = b.id)
 WHERE b.id = ANY(:affected_batch_ids)
   AND EXISTS (SELECT 1 FROM transcription_jobs j WHERE j.batch_id = b.id);
```

**Recommendation: exclude pre-jobs-era batches explicitly.** A batch with zero jobs is not recomputed, and the plan reports it by id as `legacy_count_batches`. The jobs-count expression would zero such a batch, and its true count is unrecoverable. There are 0 today, so the rule costs nothing and cannot surprise. Counts are recomputed from rows, never decremented. Batch rows are locked `FOR UPDATE` in id order before the recompute (AM-B6), and a batch is never auto-deleted.

---

## 16. `returned_exam_key` (unchanged)

A cache key, not an FK. It names `returned_exams/{graded_test_id}/{key}.pdf`, and superseded keys stay in the bucket by design, **so the prefix, not the column, is what the purge deletes.** Deleting superseded renders on re-render is a named follow-up.

---

## 17. Unassigned scans (OD-B6, ruled; OD-B8)

17 of 38 production transcriptions have `status = 'transcribed'` and a NULL `student_id`. **Ruling:** never delete on a name match. The plan **counts** unassigned transcriptions in the affected batches, and records the count and their job ids in the **verify report** and the **audit line**. **Not in the preview or the dialog:** the teacher has no action to take. Their erasure is **OD-B8**: 90 days after the exam event's last activity, on the erasure core, in a follow-up PR. The privacy page states it only once that ships.

---

## 18. Rulings and open decisions

| ID | Decision | Status |
|---|---|---|
| **OD-B1** | Legacy tables: not referenced; `verify_purged` asserts empty; drop later | **Ruled** |
| **OD-B2** | LangSmith: keep tracing, tag every student-data run, shortest tier, no copies, manual runbook | **Ruled.** Tagging PR pushed; tier already shortest; no copies. Metadata-delete needs LangSmith support (row 8); proof pending the weekend job. |
| **OD-B3** | GCS soft delete: keep 7 days; verify reports count and restorable-until | **Ruled** |
| **OD-B4** | Logs: ids, not filenames | **Ruled.** PR pushed; the 30-day clock starts at its deploy. |
| **OD-B5** | Privacy sentence | **Ruled**; placeholders below |
| **OD-B6** | Unassigned scans: counted in verify and audit, not shown | **Ruled** |
| **OD-B7** | Historical orphans | **Ruled.** Sweep list is empty (5b). |
| **OD-B8** | Never-assigned retention: 90 days after last activity | **Ruled** (follow-up PR) |
| **OD-B9** | **The three other archives** (4a) | **Open.** Recommendation below. |
| **OD-B10** | **Students' work in the public repositories** | **Open.** Recommendation below. |

> **OD-B9 — the other three database archives. Recommendation: delete all three on the same terms as the ruled one.**
> The ruling's reasoning ("production has run on the migrated schema for a month, and Supabase keeps its own backups; a frozen copy of every student row has no remaining use") applies to `vivi_precleanup_20260823.dump` word for word: it was taken 33 seconds after the ruled dump. It applies with more force to the September 11 pair. That pair holds **data production has since deleted** (21 students then, 18 now), and it sits in the same bucket the purge lists, outside every prefix the purge may touch (PRV-11). If there is an operational reason to keep the September 11 export (a pre-launch audit, say), then it needs an owner and an expiry date, and OD-B5 must name it. Otherwise no purge can make the privacy sentence true while it exists.

> **OD-B10 — students' work in the public GitHub repositories. Recommendation: stop the bleeding now, and rule the history separately.**
> `origin/main` (`sparkwellnessapp/pupal`) tracks **21 test files named after 10 students**, holding their transcribed answers and ground truth: `tests/transcription_eval_suit/{fixtures,raw_benchmarks,draft_benchmarks}/` (15) and `tests/grading_eval_suite/fixtures/` (6). `vivi-origin/perf/rubric-extraction-latency` (`sparkwellnessapp/vivi-codebase`) carries the same 21. Both repositories are **public**. No purge can reach a copy that anyone may already have cloned.
> Three separable steps, each Noam's call. The ground-truth files are on the §17.7 stop list, so I have edited none of them:
> 1. **Make both repositories private.** One setting each. It stops new copies immediately and changes nothing else.
> 2. **Move the eval ground truth out of git** into a private location the suites read, such as a private bucket prefix outside PRV-11's families.
> 3. **Decide on history.** Rewriting history removes the files from future clones, but not from existing clones, forks, or GitHub's cached views of old commits (which, as I found earlier, stay reachable by SHA). Making the repositories private covers most of what a rewrite would.
> Until this is ruled, the privacy page should not claim that deleting a student removes her work everywhere Vivi keeps it.

### OD-B5 — the sentence with its placeholders

> When you delete a student, Vivi immediately deletes their scans, transcriptions, gradings and the exam files it generated, from its database and its file storage. Some copies outlive that deletion, for a limited time: in deleted-file recovery for up to **7** days; in encrypted database backups for up to **{N}** days; in debugging records for up to **14** days; in server logs, file names only, for up to 30 days; and with the AI providers that processed the exam, which do not use it for training, under their retention terms. Scans never assigned to a student are deleted automatically **{X}** days after the exam event's last activity. Exams you downloaded, and pages your browser cached, remain on your devices.

| Placeholder | Value | Source |
|---|---|---|
| `{M}` | **14** | LangSmith `shortlived` tier (row 8) |
| `{N}` | **UNVERIFIED** | row 11; needs the token. "Encrypted" also waits on row 11. |
| `{X}` | **90**, once OD-B8 ships | OD-B8. The sentence is omitted until then. |
| "7 days" | 7 | GCS soft delete (row 4) |
| "30 days, file names only" | 30 | row 9; **dropped 30 days after OD-B4 deploys** |
| "their retention terms" | Anthropic 30 days; OpenAI 30 days; Google 24 h cache + up to 90 days if flagged | row 7. Not spelled out in the sentence, but linked from the privacy page. |

**The sentence is not publishable yet.** It is false while OD-B9 and OD-B10 stand, and `{N}` is unread.

---

## 19. Amendments and invariants Part B is built against

- **AM-B1** (final): row 1. Regression tests show `regrade`, `manual_edit` and `retry` still work after 032.
- **AM-B4**: row 1. Query D is clean.
- **AM-B5, the erasure core.** The unit is a **transcription subtree**: the transcription, its jobs, `thumbs/{id}/`, and all its graded-test chains with their PDFs and `returned_exams/{id}/`. The student purge is the subtrees of S's transcriptions, plus S's memberships, plus the student row, **last**. The plan also selects `graded_tests` by `student_id` and **asserts the two selections are equal**; if they differ, it refuses and reports. Part B ships only the student purge.
- **AM-B6, locking.** One transaction; `SELECT … FOR UPDATE` on the student row; compute the plan; delete exactly that plan. Before the recompute, lock the affected batch rows `FOR UPDATE` in id order (`append_file` takes the same lock). A concurrent assignment to S either commits first (and is in the plan) or blocks and then fails its FK check → 409. The preview is an unlocked read.
- **PRV-8 NoSilentCascade (restated).** Every FK whose referencing table is one of the five has `delete_rule` NO ACTION or RESTRICT, tested from `information_schema` on every run. A direct delete of any parent with dependents present raises and deletes nothing.
- **PRV-10 Consistency.** No row references a student or transcription of another user, and every graded test's `student_id` equals its transcription's. Enforced by AM-B4 and by the plan's equality assertion.
- **PRV-11 PrefixSafety.** Every storage target matches one of `^thumbs/[0-9a-f-]{36}/$`, `^returned_exams/[0-9a-f-]{36}/$`, `^transcriptions/[0-9a-f-]{36}/[0-9a-f-]{36}\.pdf$`, **and** names a bucket in the known set, before any storage call. Anything else raises. An empty or `None` id, a missing trailing slash, and a foreign bucket each raise with **zero** storage calls. **Checked against production:** all 39 scan paths, all 38 transcription ids and all 22 graded-test ids fit the allow-list, so it refuses nothing that exists today.
- **PRV-12 SharedObjects.** An object is deleted only if every row referencing it is in the plan; otherwise the purge refuses and reports.

**Two things the implementation must not do** (ruling 2026-09-22):
1. It must not delete the student row first and let the constraints do the rest. That makes PRV-6 a lie.
2. It must not soften a NO ACTION that breaks some flow back into a cascade. Either make that flow's deletion explicit, or bring it to Noam.

---

## 20. What must be true before 032 and anything that deletes

1. Noam signs off this v2.
2. OD-B9 and OD-B10 are ruled. Neither blocks 032, but the sentence waits on both.
3. Row 11 and row 14 are read, which needs the token.
4. 032 is generated from a **fresh** read of row 1's query against production at deploy time, and query D is re-run **immediately before** it (AM-B4: stop if it finds violations).
5. The F teardowns are made explicit **in the same commit** as 032. Vivi-Test is migrated only at that commit.
