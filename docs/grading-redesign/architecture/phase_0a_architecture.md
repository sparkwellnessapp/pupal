# Vivi — Grading Pipeline Architecture Lock (Phase 0a)

**Owner:** Noam
**Status:** LOCKED — changes require re-running Phase 0
**Locked at:** 2026-05-24
**Scope:** The transcription, grading, and graded-test persistence pipeline. The rubric pipeline is treated as upstream context, not in scope for change.

---

## 0. Purpose

This document is the single source of truth from which the schema (Phase 0c), the ERD (Phase 0d), the data flow diagrams (Phase 0e), and every subsequent migration and sprint derive. Mistakes in this document propagate furthest. The bar it must clear:

> A year from now, when shipping "My Classroom" BI and personalized learning material generation, this document is still the right map. Every architectural decision below has been weighed against that bar.

What this document locks:
- The complete artifact inventory (every domain object the system manipulates)
- Each artifact's lifecycle (states, transitions, what triggers them)
- The persistence boundary for each artifact (table + column + Pydantic model shape)
- The invariants that must always hold
- The actors and the permission model
- The single-source-of-truth map (where each piece of information lives, where copies exist, which is authoritative)
- Re-grading and rubric versioning semantics
- Annotations as the unified diagnostic surface
- What is deliberately NOT in scope

What this document does NOT lock:
- Pydantic field-by-field schemas (lives in `app/schemas/*.py`)
- Endpoint signatures (lives in individual sprint specs)
- Migration SQL (Phase 0c)
- UI mockups (out of scope; UI follows architecture)

---

## 1. Domain Language

These terms are used throughout this document. Each is defined once. If a future reader is unsure what a term means, the answer is here.

| Term | Definition |
|------|------------|
| **Rubric** | The teacher-authored definition of what is being graded. Already implemented; not in scope for change. Lives in the `rubrics` table. |
| **Rubric Draft** | Editable rubric, lives in `rubrics.draft_json`. The teacher's working copy. |
| **Rubric Contract** | Frozen, validated, compiled rubric. Lives in `rubrics.contract_json`. Carries a `contract_version` (UUID, fresh on each compile). The artifact graders see. |
| **Transcription** | The artifact representing one student's handwritten test, OCR'd from the PDF. Has a Draft side (VLM output, immutable) and a Contract side (teacher-approved answers, frozen). |
| **Transcription Draft** | What the VLM produced. Immutable from moment of write. Lives in `transcriptions.draft_json`. |
| **Transcription Contract** | The teacher-approved student answers, frozen at the moment of submission to grading. Lives in `transcriptions.contract_json`. Carries a `contract_version` (UUID). |
| **GradableTest** | The marriage object: `RubricContract + TranscriptionContract`, closed-world per-question pre-sliced. The agent's typed input. **Not persisted** — derived deterministically from its two inputs. Lives in memory only, recomputable on demand. |
| **GradedTest** | The artifact representing one (transcription, rubric-version, grading-pass) triple. Has a Draft side (agent output, teacher-editable) and a Contract side (teacher-approved, frozen). |
| **GradedTest Draft** | The agent's output plus the teacher's overlay edits. Lives in `graded_tests.draft_json`. |
| **GradedTest Contract** | The frozen, approved graded test. Lives in `graded_tests.contract_json`. Carries a `contract_version` (UUID, fresh on approval). |
| **GraderAgent** | The new stupid-simple agent: one LLM call per question, deterministic post-validation. Consumes `GradableTest`, produces a draft outcome set. Replaces the deprecated LangGraph TestGraderAgent. |
| **Annotation** | A typed diagnostic data point, severity-coded, target-scoped. The single diagnostic surface across all domains. Same shape as the rubric-domain `Annotation`. |
| **TeacherOverride** | A sparse per-criterion record of teacher edits to a graded draft. Contains `points_override` and/or `teacher_comment`. Stored in `GradedTestDraft.teacher_overrides`. |
| **Student** | A persistent identity for a learner. New first-class entity. Lives in `students` table. Owned by a teacher. May belong to one or more classes. |
| **Class** | A teacher-defined grouping of students. New first-class entity. Lives in `classes` table. Per-teacher (no shared classes across teachers in this PR). |
| **Batch** | A teacher-defined grouping of grading operations submitted together. Lives in `grading_batches` table. Restructured: counts are derived from `graded_tests`, not stored. |
| **Re-grade** | Producing a new `GradedTest` row that grades the same `TranscriptionContract` against a different `RubricContract` version. The new row links back to its predecessor via `regraded_from_id`. The previous row is preserved unmodified. |

### A note on "Draft" vs "Contract"

This document uses "Draft" and "Contract" as paired terms across three domains: rubric, transcription, graded test. The pattern is identical in each:

- **Draft** = mutable until promoted, may carry validation annotations, accepts in-progress work.
- **Contract** = frozen on promotion, fully validated, carries a `contract_version` UUID for reproducibility, is what downstream consumers depend on.

The promotion event differs per domain:
- Rubric: teacher hits "compile" → ContractCompiler validates and freezes.
- Transcription: teacher hits "submit to grade" → answers freeze.
- Graded test: teacher hits "approve" → outcomes + overrides freeze.

This uniformity is intentional. One mental model. The cost of remembering "draft is mutable, contract is frozen" pays for itself the second time you reach for it in a new domain.

---

## 2. Artifact Inventory

The system manipulates five core artifacts and four supporting entities. Listed in the order they appear in a typical grading session.

### 2.1 The five core artifacts

#### A. Transcription (Draft + Contract)

**Purpose:** Bridges the physical world (handwritten PDF) and the digital pipeline. Represents one student's answers as text.

**Why two sides:**
- **Draft** preserves what the VLM produced, byte-for-byte. This is non-negotiable. Today's code discards this the moment the teacher edits; the redesign keeps it forever. The reason is strategic: the gap between draft and contract is the highest-value signal we have for measuring VLM quality, detecting OCR failure modes, and (eventually) generating training data for a fine-tuned transcription model. It costs one JSONB column to gain a permanent record of "what we thought we read" vs "what the teacher confirmed." We don't pay this cost twice.
- **Contract** is what every downstream stage depends on. The grader doesn't grade what the VLM saw; it grades what the teacher confirmed. Pinning the contract with a version UUID makes every grading run reproducible against the exact answers it consumed.

**Lifetime:** Created when transcription completes. The draft is never modified after creation. The contract is written once, on submission to grading. After that the row is read-only.

**Identity:** Each Transcription is owned by exactly one `(user_id, student_id, rubric_id)` triple. The student is assigned at transcription review time (per B1).

#### B. GradableTest (in-memory only)

**Purpose:** The marriage object the agent consumes. The agent's interface is *one well-typed input* — `GradableTest` — not "the rubric dict and the answers dict, figure it out."

**Why not persisted:** Two reasons. First, the existence proof: given the same `RubricContract` (pinned by version) and the same `TranscriptionContract` (pinned by version), the compilation is deterministic. Persistence would cache a derivation. Second, the rule: do not persist what you can recompute from authoritative sources. Caching breeds drift, and drift breeds bugs that show up months later when the cache and the source diverge.

**What the compiler does:**
1. Resolves identity (transcription's `question_number` → contract's `question_id`).
2. Resolves sub-question identity (transcription's Hebrew letter → contract's `sub_question_id`). This is currently unimplemented in production code; the new compiler fixes it.
3. Slices the contract per question — each `GradableQuestion` carries only its own criteria tree, example_solution, trace tables, and the matched answer.
4. Computes per-scope alignment status (matched / answer_missing / scope_not_in_contract).
5. Collects orphan transcribed answers (no matching contract scope) as diagnostic data on the `GradableTest`.

**Lifetime:** Built on demand. Lives for the duration of one grading invocation. Garbage-collected after.

**Closed-world guarantee:** By construction. The agent literally cannot see any criterion ID not sliced in by the compiler. This is the load-bearing property — closed-world is a structural fact, not a post-hoc validation.

#### C. GradedTest (Draft + Contract)

**Purpose:** The grading output for one (transcription, rubric-version) pair. Carries the agent's outcomes and the teacher's overrides separately, so the audit trail of "what did the AI award vs what did the teacher decide" survives forever.

**Why two sides:**
- **Draft** is the editable layer. The agent's outcomes are stored unchanged; the teacher's edits are a sparse overlay. The teacher can revise their overlay any number of times before approval. Draft is for thinking.
- **Contract** is the frozen, approved final form. Once approved, the row's `contract_json` is set and never changes. This is what shows up in analytics, in the parent communication PDF (future), and in the student's longitudinal record.

**The teacher's edit model:** Per B5, the teacher modifies two things only — `points_awarded` per criterion, and `teacher_comment` per criterion. Both are stored as a sparse `TeacherOverride` map keyed by `criterion_id`. The agent's full output (reasoning, evidence quote, flags) is preserved unchanged. This means at any time we can answer "what did the AI think" and "what did the teacher decide" separately.

**Revision chain — two actions extend it.** Each `GradedTest` row carries `regraded_from_id` (the row it replaces) and `regraded_to_id` (the row that replaces it). The chain is a linked list per `(transcription_id, rubric_id)` pair. The leaf of the chain (`regraded_to_id IS NULL`) is the current grade.

The chain is extended by two distinct teacher actions, both applicable only to rows in `status = 'approved'`. The persistence mechanism is identical for both; what differs is the trigger and what gets pre-loaded into the new row's draft:

| Action | Trigger | New row's starting draft | Agent invoked? |
|---|---|---|---|
| **Re-grade** | Rubric contract has changed; teacher hits "regrade against current rubric" | Fresh AI output against the new contract version | Yes |
| **Manual edit** | Teacher disagrees with their own previously approved grade and wants to revise | Previous row's contract is copied into the new draft (outcomes + teacher overrides as starting point) | No — teacher edits directly |

Both actions create a new row, link it to the previous via `regraded_from_id` / `regraded_to_id`, and produce a new leaf. The previous row is preserved unmodified except for `regraded_to_id` being set.

**Why two actions, not one:** They differ in *why they exist* and *what's safe to carry forward*. Re-grade implies the rubric changed, so old teacher decisions may reference criterion IDs that no longer exist — starting fresh is the safe choice. Manual edit implies the rubric is unchanged, so the previous decisions are still valid — the teacher wants to revise them, not start over. The persistence shape is identical; the teacher's intent and the new draft's starting state are not.

**Identity:** `(transcription_id, rubric_id, rubric_contract_version)` is NOT enforced unique — a manual-edit chain can have multiple rows at the same rubric contract version, each representing a successive revision by the teacher. The uniqueness invariant is RGC-1: exactly one leaf (`regraded_to_id IS NULL`) per `(transcription_id, rubric_id)` pair.

### 2.2 The four supporting entities

#### A. Student

**Purpose:** Persistent identity for a learner. Replaces the current free-text `student_name` string with a real entity.

**Why first-class now:** This is the load-bearing dimension for the 6-month BI feature and the 12-month personalized learning materials feature. Free-text names would close both doors. Landing it now costs one new table plus a one-screen UI control; landing it later would require backfilling every existing graded test and migrating every analytics query.

**Required fields:** `full_name`, `user_id` (the owning teacher).
**Optional fields:** `class_id` (FK to classes, nullable — students can exist before being assigned to a class), `notes` (free text).
**Per B2:** No `external_id`. No email. No grade level. No subject. No photo. If the 6-month feature needs these, they get added in a follow-up — but minimum viable today.

**Identity:** `(user_id, full_name)` is unique per teacher. Two teachers can each have a student named "Yossi Cohen"; they're different students. (Per B3 — classes per teacher; students follow the same per-teacher scoping.)

**Lifetime:** Permanent. Soft-delete via `archived_at` if needed (out of scope for this PR; future).

#### B. Class

**Purpose:** Teacher-defined grouping of students.

**Why first-class now:** Same reasoning as Student. The teacher's mental model is "my כיתה י3 students" — landing this entity now means analytics queries can group by class from day one.

**Required fields:** `name` (free text — "כיתה י3"), `user_id`.
**Optional fields:** `subject_matter_id` (FK to existing `subject_matters`), `school_year`.

**Per-teacher scoping:** Each teacher's classes are isolated. No shared classes across teachers.

**Student-to-class relation:** Many-to-many. A student can be in multiple classes (math, CS, physics taught by different teachers' classes — but in the current per-teacher model, a single teacher's student belongs to that teacher's classes). The relation lives in a join table `class_memberships`.

**Lifetime:** Permanent. Same archival pattern as Student.

#### C. Batch

**Purpose:** Teacher-facing grouping of grading operations submitted together. Reused from existing infrastructure but slimmed down.

**Key change from current schema:** Batches no longer store per-status counts (`total_sessions`, `completed_sessions`, `failed_sessions`). Counts are derived from a `GROUP BY graded_tests.status` against `WHERE batch_id = ?`. This eliminates a class of bugs where the count and the underlying state disagree.

**What batches link:** `(user_id, rubric_id, rubric_contract_version, class_id)`. The `class_id` is the optional teacher-set tag — "this is grading class י3's midterm."

**Lifetime:** Permanent. Batches are part of the historical record of what was graded when.

#### D. (`grading_sessions` is DELETED.)

The current `grading_sessions` table existed for the deprecated LangGraph agent's per-criterion state machine. The new architecture has no per-criterion state. The teacher-facing batch dashboard concept is preserved by querying `graded_tests` directly (filtering on `batch_id`, grouping on `status`).

---

## 3. Lifecycle State Machines

One diagram per artifact. Each transition names its trigger (the user action or system event), its precondition (what must be true to transition), and its post-condition (what becomes true after).

### 3.1 Transcription lifecycle

```
                  ┌────────────────────────────┐
                  │   (does not yet exist)     │
                  └────────────┬───────────────┘
                               │
                               │  TRIGGER: teacher uploads PDF
                               │           via POST /transcribe
                               │  PRECONDITION: user authenticated,
                               │                rubric_id valid + compiled
                               │  ACTION:  upload PDF to GCS;
                               │           run VLM transcription;
                               │           INSERT row with draft_json
                               ▼
                  ┌────────────────────────────┐
                  │  status = 'transcribed'    │
                  │                            │
                  │  draft_json     populated  │
                  │  contract_json  NULL       │
                  │  student_id     NULL       │
                  │  gcs_uri        populated  │
                  └────────────┬───────────────┘
                               │
                               │  TRIGGER: teacher reviews + submits
                               │           via POST /grade
                               │  PRECONDITION: student_id has been
                               │                selected (existing or
                               │                newly created);
                               │                edited answers provided
                               │  ACTION:  UPDATE student_id;
                               │           UPDATE contract_json = edited;
                               │           UPDATE contract_version = new UUID;
                               │           UPDATE status = 'approved'
                               ▼
                  ┌────────────────────────────┐
                  │  status = 'approved'       │
                  │                            │
                  │  draft_json     populated  │
                  │  contract_json  populated  │
                  │  student_id     populated  │
                  │  contract_version  set     │
                  │  approved_at    populated  │
                  └────────────────────────────┘
                  (terminal — row never mutates again)
```

**Invariants:**
- `draft_json` is set on INSERT and never updated.
- `contract_json`, `contract_version`, `student_id`, `approved_at` are set in one atomic update at submission time.
- A transcription with `status = 'approved'` is read-only forever.

### 3.2 GradedTest lifecycle

```
                  ┌────────────────────────────┐
                  │   (does not yet exist)     │
                  └────────────┬───────────────┘
                               │
                               │  TRIGGER: POST /grade after
                               │           transcription approval
                               │  PRECONDITION: transcription is in
                               │                'approved' state
                               │  ACTION:  INSERT row, status='pending'
                               ▼
                  ┌────────────────────────────┐
                  │  status = 'pending'        │
                  │  draft_json     NULL       │
                  │  contract_json  NULL       │
                  └────────────┬───────────────┘
                               │
                               │  TRIGGER: grading worker picks up
                               │  ACTION:  load contracts;
                               │           compile GradableTest;
                               │           UPDATE status='grading'
                               ▼
                  ┌────────────────────────────┐
                  │  status = 'grading'        │
                  └────┬───────────────────┬───┘
                       │                   │
            agent fails│                   │agent completes
                       │                   │
                       ▼                   ▼
       ┌──────────────────┐    ┌────────────────────────────┐
       │ status='failed'  │    │  status = 'draft'          │
       │ error_message    │    │  draft_json populated      │
       │   populated      │    │  (agent outcomes +         │
       │ (terminal)       │    │   empty overrides)         │
       └──────────────────┘    └────────────┬───────────────┘
                                            │
                                            │  TRIGGER: teacher edits draft
                                            │  (zero or more times)
                                            │  ACTION: UPDATE draft_json
                                            │          (overrides only —
                                            │           agent outcomes never
                                            │           mutate)
                                            │
                                            │  (loops back to 'draft')
                                            ▼
                               ┌────────────────────────────┐
                               │  status = 'draft'          │
                               │  (with teacher overlay)    │
                               └────────────┬───────────────┘
                                            │
                                            │  TRIGGER: POST /approve
                                            │  PRECONDITION: no closed-world
                                            │                violations in
                                            │                proposed contract
                                            │  ACTION: compile GradedTestContract
                                            │          (validates INV-R1/R2 +
                                            │           closed-world);
                                            │          UPDATE contract_json;
                                            │          UPDATE contract_version
                                            │            = new UUID;
                                            │          UPDATE status='approved';
                                            │          UPDATE approved_at,
                                            │                 approved_by
                                            ▼
                               ┌────────────────────────────┐
                               │  status = 'approved'       │
                               │  contract_json populated   │
                               │  contract_version  set     │
                               │  (terminal —               │
                               │   row never mutates again) │
                               └────────────────────────────┘
```

**Invariants:**
- A GradedTest row in `status IN ('approved', 'failed')` is read-only for all fields **except** `regraded_to_id`, which may be set exactly once (when this row is replaced by a new row via re-grade or manual edit).
- Once `regraded_to_id` is set, the row is fully read-only forever.
- `draft_json` is set when the agent completes (for AI-graded rows) or at INSERT (for manual-edit rows; the previous contract is pre-loaded). The agent's outcomes within `draft_json` are immutable; only the `teacher_overrides` sub-field is updated by subsequent edits.
- `contract_json` is set in one atomic update at approval.
- Both re-grade and manual edit create a new row and update the previous row's `regraded_to_id` in the same transaction. The previous row's other fields are not touched.

### 3.3 Re-grade and Manual Edit flows

Both actions extend the revision chain. They share the same persistence shape; they differ in trigger, in whether the agent is invoked, and in what gets pre-loaded into the new row's draft.

#### 3.3.1 Re-grade flow

```
  Existing row R1:
  ┌──────────────────────────────────────────┐
  │ id = uuid_A                              │
  │ transcription_id = T                     │
  │ rubric_id = R                            │
  │ rubric_contract_version = V1             │
  │ status = 'approved'                      │
  │ regraded_from_id = NULL                  │
  │ regraded_to_id = NULL  ← leaf of chain   │
  └──────────────────────────────────────────┘

         │
         │  TRIGGER: teacher recompiles rubric R → V2
         │  EFFECT:  R1.rubric_contract_stale becomes TRUE
         │           (computed at query time;
         │            see §9)
         ▼

  ┌──────────────────────────────────────────┐
  │ id = uuid_A                              │
  │ rubric_contract_stale = TRUE             │
  │ (computed; everything else unchanged)    │
  └──────────────────────────────────────────┘

         │
         │  TRIGGER: teacher hits "Regrade against current rubric"
         │  ACTION:  INSERT new row R2 with V2 contract
         │           UPDATE R1.regraded_to_id = uuid_B
         │           Agent runs (status: pending → grading → draft)
         ▼

  Existing row R1 (now historical):
  ┌──────────────────────────────────────────┐
  │ id = uuid_A                              │
  │ rubric_contract_version = V1             │
  │ status = 'approved'                      │
  │ regraded_from_id = NULL                  │
  │ regraded_to_id = uuid_B  ← chain forward │
  └──────────────────────────────────────────┘

  New row R2 (the current grade):
  ┌──────────────────────────────────────────┐
  │ id = uuid_B                              │
  │ transcription_id = T  (same)             │
  │ rubric_id = R         (same)             │
  │ rubric_contract_version = V2  (new)      │
  │ status = 'pending' → 'grading' → 'draft' │
  │ draft_json = (fresh AI output)           │
  │ regraded_from_id = uuid_A                │
  │ regraded_to_id = NULL  ← new leaf        │
  └──────────────────────────────────────────┘
```

#### 3.3.2 Manual edit flow

```
  Existing row R1:
  ┌──────────────────────────────────────────┐
  │ id = uuid_A                              │
  │ transcription_id = T                     │
  │ rubric_id = R                            │
  │ rubric_contract_version = V1             │
  │ status = 'approved'                      │
  │ contract_json = (approved outcomes +     │
  │                  teacher overrides)      │
  │ regraded_to_id = NULL  ← leaf of chain   │
  └──────────────────────────────────────────┘

         │
         │  TRIGGER: teacher hits "Edit grade manually"
         │           (rubric has not changed)
         │  ACTION:  INSERT new row R2 with:
         │             - same rubric_contract_version V1
         │             - draft_json = R1.contract_json (copied in)
         │             - status = 'draft' (no agent invocation)
         │           UPDATE R1.regraded_to_id = uuid_B
         ▼

  Existing row R1 (historical):
  ┌──────────────────────────────────────────┐
  │ id = uuid_A                              │
  │ regraded_to_id = uuid_B  ← chain forward │
  └──────────────────────────────────────────┘

  New row R2 (current; teacher is editing):
  ┌──────────────────────────────────────────┐
  │ id = uuid_B                              │
  │ transcription_id = T  (same)             │
  │ rubric_id = R         (same)             │
  │ rubric_contract_version = V1  (same!)    │
  │ status = 'draft' (no 'grading' phase)    │
  │ draft_json = (copy of R1.contract_json,  │
  │              now editable)               │
  │ regraded_from_id = uuid_A                │
  │ regraded_to_id = NULL  ← new leaf        │
  └──────────────────────────────────────────┘

         │
         │  ... teacher edits draft_json ...
         │  ... teacher hits "Approve" ...
         │  ACTION:  compile GradedTestContract;
         │           UPDATE R2.contract_json;
         │           UPDATE R2.status = 'approved';
         │           UPDATE R2.approved_at, approved_by
         ▼

  Row R2 (now terminal):
  ┌──────────────────────────────────────────┐
  │ id = uuid_B                              │
  │ status = 'approved'                      │
  │ contract_json = (newly approved)         │
  │ regraded_to_id = NULL  ← still the leaf  │
  └──────────────────────────────────────────┘
```

**Invariants for both actions:**
- The chain only grows forward. Once a row has `regraded_to_id` set, it never changes again.
- Exactly one leaf (`regraded_to_id IS NULL`) per `(transcription_id, rubric_id)` pair (RGC-1, enforced by partial unique index).
- All historical rows in the chain remain queryable forever. Analytics queries that want "current grade only" filter on `regraded_to_id IS NULL`. Queries that want the audit trail walk the linked list backward via `regraded_from_id`.

**Differences between the two actions:**

| Aspect | Re-grade | Manual edit |
|---|---|---|
| Precondition | Source row in `'approved'` AND `rubric_contract_stale = TRUE` | Source row in `'approved'` (no staleness requirement) |
| New row's `rubric_contract_version` | New version (current rubric contract) | Same as source row |
| New row's initial `draft_json` | Fresh AI output (empty teacher overrides) | Copy of source row's `contract_json` |
| New row passes through `'grading'` status | Yes | No — goes directly from `'pending'` to `'draft'` |
| LLM invoked | Yes | No |
| Carries forward teacher overrides | No | Yes (as starting point) |

---

## 4. Persistence Boundary Map

Every artifact lives in exactly one place. Derived copies exist for query performance; they are clearly marked.

| Artifact | Table | Column | Pydantic model | Mutability |
|----------|-------|--------|----------------|------------|
| Rubric Draft | `rubrics` | `draft_json` | `ExtractRubricResponse` | Mutable until compile |
| Rubric Contract | `rubrics` | `contract_json` | `GradingRubricContract` | Frozen on compile |
| Transcription Draft | `transcriptions` | `draft_json` | `TranscriptionDraft` (new) | Set on INSERT, never updated |
| Transcription Contract | `transcriptions` | `contract_json` | `TranscriptionContract` (new) | Set once on submission, never updated |
| GradableTest | (none) | (none) | `GradableTest` (new) | In-memory only, recomputable |
| GradedTest Draft | `graded_tests` | `draft_json` | `GradedTestDraft` (new) | Agent outcomes immutable; `teacher_overrides` sub-field updated by teacher edits |
| GradedTest Contract | `graded_tests` | `contract_json` | `GradedTestContract` (new) | Frozen on approval |

**Denormalized fields** (single source of truth elsewhere, copy here for query performance):

| Table | Column | Authoritative source | Why denormalized |
|-------|--------|---------------------|------------------|
| `transcriptions` | `student_name` | `students.full_name` (via `student_id`) | List queries grouping by student name without joining |
| `graded_tests` | `student_name` | `students.full_name` (via `student_id`) | Same |
| `graded_tests` | `total_score`, `total_possible`, `percentage` | `contract_json` (computed) | List views show scores without parsing JSONB |
| `graded_tests` | `rubric_contract_stale` | Derived from `rubric_contract_version` vs `rubrics.contract_version` | Trigger or computed-at-query-time; locked in §9 |

**Invariant for denormalized fields:** Whenever the authoritative source changes, the denormalized copy is updated in the same transaction. Schema-level FK constraints + application-level update hooks enforce this.

---

## 5. Invariants

Numbered, grouped by domain. These are constraints that must always hold; violation indicates a bug.

### 5.1 Identity invariants

- **IDN-1** — Every `transcription` has exactly one `user_id` and exactly one `rubric_id`. Both NOT NULL.
- **IDN-2** — Every `transcription` in `status = 'approved'` has exactly one `student_id`. Transcriptions in `status = 'transcribed'` may have NULL `student_id`.
- **IDN-3** — Every `graded_test` has exactly one `transcription_id`. The transcription must be in `status = 'approved'` before any graded_test referencing it can transition out of `pending`.
- **IDN-4** — Every `graded_test` has exactly one `rubric_id` and exactly one `rubric_contract_version`. Both NOT NULL.
- **IDN-5** — Every `student`, `class`, `transcription`, `graded_test`, `grading_batch` has exactly one `user_id` (the owning teacher). All NOT NULL.

### 5.2 Lifecycle invariants

- **LCY-1** — A `transcription` in `status = 'approved'` is read-only. The only field that may change is `regraded_to_id` on `graded_tests` referring to it (which doesn't modify the transcription itself).
- **LCY-2** — A `graded_test` in `status IN ('approved', 'failed')` is read-only, with one exception: `regraded_to_id` may be updated exactly once (when a re-grade is initiated against this row).
- **LCY-3** — Once `regraded_to_id` is set on a row, that row's status remains in its terminal state forever.

### 5.3 Closed-world invariants (extending the rubric domain's INV-6 to grading)

- **CW-1** — Every `criterion_id` referenced in a `GradedTestDraft.outcomes` exists in the corresponding `RubricContract.all_criteria_ids`. Enforced **by construction** at `GradableTest` compile time (the agent literally cannot see other IDs).
- **CW-2** — Every `criterion_id` referenced in a `GradedTestDraft.teacher_overrides` exists in the corresponding `RubricContract.all_criteria_ids`. Enforced at draft-edit time — the API rejects override edits that reference unknown IDs.
- **CW-3** — Every `criterion_id` referenced in a `GradedTestContract` exists in the corresponding `RubricContract.all_criteria_ids`. Enforced at contract-compile (approval) time. This is the hard error; an edited draft that violates CW-3 cannot be approved.

### 5.4 Point-sum invariants (mirror INV-R1, INV-R1b, INV-R2 from the rubric domain)

- **PTS-1 (INV-R1)** — For every question in a `GradedTestContract`: Σ(direct criterion points_awarded + sub_question points_awarded) = question.points_awarded. Enforced at approval.
- **PTS-2 (INV-R1b)** — For every sub-question in a `GradedTestContract`: Σ(criterion points_awarded) = sub_question.points_awarded. Enforced at approval.
- **PTS-3 (INV-R2)** — For every criterion with sub_criteria in a `GradedTestContract`: Σ(sub_criterion points_awarded) = criterion.points_awarded. Enforced at approval.

Note: The graded-side equivalent of INV-R3 (rubric total) is implicit — Σ(question points_awarded) over the whole contract is the test's total_score, which is denormalized to a column. INV-R3 is not a separate constraint at the graded layer; it's a sanity check on the denormalization.

### 5.5 Revision chain invariants

The chain is extended by either re-grade or manual edit; both produce a new row linked to the previous. The invariants below apply uniformly to both.

- **RGC-1** — For every `(transcription_id, rubric_id)` pair, exactly one row has `regraded_to_id IS NULL`. Enforced by partial unique index.
- **RGC-2** — If row R1 has `regraded_to_id = R2`, then R2 has `regraded_from_id = R1`. Bidirectional.
- **RGC-3** — No cycles in the revision chain. (Structurally impossible if RGC-1 and RGC-2 hold and chains only grow forward.)
- **RGC-4** — All rows in a revision chain share the same `transcription_id` and `rubric_id`. They may differ in `rubric_contract_version` (a re-grade introduces a new version; a manual edit preserves the same version).
- **RGC-5** — A row's `regraded_to_id` is set exactly once, atomically with the creation of the row it points to. After being set, it never changes.

### 5.6 Annotation invariants

- **ANN-1** — All system-generated diagnostics about a `GradedTestDraft` are stored as `GradingAnnotation` objects in `GradedTestDraft.annotations`. No parallel diagnostic surfaces.
- **ANN-2** — All system-generated diagnostics about a `TranscriptionDraft` are stored in `TranscriptionDraft.annotations`. (VLM low-confidence flags, etc.)
- **ANN-3** — Annotations are produced by the system. The teacher does not author annotations. (Teacher commentary is a separate concept: `TeacherOverride.teacher_comment`, scoped per criterion.)
- **ANN-4** — Severity values are `error`, `warning`, `info`. Same taxonomy as the rubric domain.

### 5.7 Versioning invariants

- **VER-1** — `transcription_contract_version` is a fresh UUID generated at submission time. Reproducibility: given the same transcription_id and contract_version, the resulting contract is byte-identical.
- **VER-2** — `rubric_contract_version` on a `graded_test` is pinned at row creation. It does not change. Rubric recompilations produce new contract versions but never modify the version pinned to existing graded tests.
- **VER-3** — `graded_test.contract_version` is a fresh UUID at approval. Re-approving (which doesn't exist as an action; approvals are terminal) would never happen.

---

## 6. Actors and Permission Model

### 6.1 The actors

The system has one actor type in scope for this PR: **the teacher** (`User` in the existing schema).

Future actors that are explicitly NOT in scope:
- **Student.** Students do not have logins, do not see graded tests directly. (Parent communication PDFs are generated by the teacher in a future PR.)
- **Co-teacher / TA.** A teacher cannot grant another teacher access to their rubrics or graded tests. This may come later via `rubric_shares` (which already exists) being extended to grading, but not now.
- **Admin.** No admin role today.

### 6.2 The permission rule

**The teacher owns all artifacts created by their actions, and can read/write only their own artifacts.** Enforced at every endpoint via `Depends(get_current_user)`. Enforced at every query via `WHERE user_id = current_user.id`.

There is no shared access, no cross-teacher visibility, no public artifacts. This PR explicitly does not implement sharing of graded tests across teachers. (Rubric sharing exists in the codebase; graded test sharing does not, and is not being added.)

### 6.3 Auth implementation

Every grading-related endpoint adds `Depends(get_current_user)`. No grading endpoint is anonymous. This is a hard prerequisite, not optional — the new schema's `NOT NULL` constraints on `user_id` columns make anonymous grading structurally impossible.

The auth dependency populates `user_id` on every write. The query layer filters on `user_id` on every read. There is no "admin bypass," no "service account," no "internal-only" mode that skips auth. If a background job needs to operate on behalf of a user (e.g., a scheduled re-grade), it carries that user's identity explicitly.

---

## 7. Single Source of Truth Map

For every piece of information the system tracks, this table identifies the authoritative source and any denormalized copies.

| Information | Authoritative source | Copies (kept consistent) | How consistency is maintained |
|-------------|---------------------|--------------------------|------------------------------|
| Student's name | `students.full_name` | `transcriptions.student_name`, `graded_tests.student_name` | Updated in same transaction when student name changes. UI-driven; rare. |
| Class membership | `class_memberships` (M:N join table) | (none) | Single source. |
| The rubric the teacher built | `rubrics.draft_json` | (none) | Single source. |
| The frozen rubric for grading | `rubrics.contract_json` | (none) | Single source. The `rubric_contract_version` is copied to `graded_tests.rubric_contract_version` for pinning, but that's a different identifier (a version reference, not the contract itself). |
| What the VLM transcribed | `transcriptions.draft_json` | (none) | Single source. Immutable. |
| What the teacher confirmed for grading | `transcriptions.contract_json` | (none) | Single source. |
| What the agent graded | `graded_tests.draft_json.outcomes` | (none) | Single source. Immutable after agent completes. |
| The teacher's edits to a graded draft | `graded_tests.draft_json.teacher_overrides` | (none) | Single source. Mutable until approval. |
| The frozen approved grade | `graded_tests.contract_json` | `graded_tests.total_score`, `total_possible`, `percentage` (denormalized for list view performance) | Computed from contract_json at approval time, written in same transaction. |
| Re-grade lineage | `graded_tests.regraded_from_id`, `graded_tests.regraded_to_id` | (none — a leaf is queried via `regraded_to_id IS NULL`) | Bidirectional FK. Updated in the same transaction that creates the new row. |
| Whether a graded test is against a stale rubric | `graded_tests.rubric_contract_stale` | Derivable from comparing `graded_tests.rubric_contract_version` vs `rubrics.contract_version` | See §9. |
| Batch progress (counts of pending/grading/done/failed) | Derived at query time from `graded_tests` GROUP BY `status` | Not stored. The current schema's stored counts are a maintenance burden and are removed. | N/A — always derived. |
| Which teacher owns what | `*.user_id` columns | (none) | NOT NULL on all entity tables. |

---

## 8. The "GradableTest" — Why It Doesn't Live in the Database

The redesign has a tempting alternative: persist `GradableTest` as its own table or JSONB column. We deliberately do not. The reasoning, fully spelled out:

**The conjecture being rejected:** "Materializing `GradableTest` would save the recompilation cost on each grading invocation."

**The argument for materializing:** A `GradableTest` is the per-question slice of a `RubricContract` joined with a `TranscriptionContract`. Building it requires loading both, validating both, and running the compiler. If grading is the hot path, why pay this cost every time?

**Why this argument fails:**

1. **Cost is negligible.** Building a `GradableTest` is in-memory string and dict manipulation. For a 10-question rubric with 30 criteria, building it is sub-millisecond. The LLM call that follows is 1-10 seconds. The compiler's cost rounds to zero against the LLM's.

2. **Caching introduces a consistency problem we don't have.** If we persist `GradableTest`, we now have three things that must agree: the rubric contract, the transcription contract, and the gradable test built from them. Drift between them is a bug class. The rule "do not persist what you can recompute from authoritative sources" exists precisely to avoid this class of bug.

3. **Recompute is the audit trail.** When investigating a strange grade six months from now ("why did the agent see only three criteria when the rubric has five?"), the answer is to load the pinned `rubric_contract_version` and `transcription_contract_version` and recompile the `GradableTest`. The compilation is the explanation. If we cached, we'd have to ask "is this cached `GradableTest` the one the agent actually saw, or has the cache been invalidated since?"

4. **Reproducibility is preserved without persistence.** Given the two pinned contract versions, the compiler is deterministic. The pinned versions are the persisted state; the gradable test is the function of them.

**The decision is locked.** `GradableTest` is in-memory only. The compiler is a pure function. The agent's input is built fresh on each grading invocation.

---

## 9. Revision Semantics: Re-grade and Manual Edit

This section locks the full set of revision actions on approved graded tests. References §3.3 (the state-machine diagrams) and §5.5 (the chain invariants).

### 9.1 The rubric recompilation trigger

When the teacher recompiles a rubric (e.g., adjusts point values or adds a new criterion), `rubrics.contract_version` changes to a new UUID. All existing `graded_tests` referencing the rubric remain pinned to their original `rubric_contract_version`, which now differs from the rubric's current `contract_version`.

### 9.2 The `rubric_contract_stale` flag — computed at query time

This flag indicates "the rubric this grade was made against has been recompiled since this grade was approved." Two implementation options were considered:

- **(a) Stored column, trigger-maintained.** Add `rubric_contract_stale` as a stored boolean. A DB trigger updates it on `rubrics.contract_version` changes.
- **(b) Computed at query time.** Don't store the flag. Join `graded_tests` to `rubrics` and compute `(graded_tests.rubric_contract_version != rubrics.contract_version) AS rubric_contract_stale` in every list query.

**Decision: (b) — computed at query time.** Reasons:
- Recompilation is rare; querying graded tests is frequent. The expensive operation is the rare one; cheap on the common path.
- No trigger maintenance. Triggers are surprisingly hard to keep consistent across migrations and replicas.
- One source of truth: the join. No "is the flag stale" meta-problem.

The list query becomes a one-liner addition: `LEFT JOIN rubrics ... AS rc, computing the boolean as a derived column`. Trivial cost.

The flag is only meaningful for re-grade. Manual edit ignores it.

### 9.3 The re-grade action

**Endpoint:** `POST /graded_tests/{id}/regrade`

**Precondition:** Source row is in `status = 'approved'` AND `rubric_contract_stale` is TRUE (computed at the join).

**Steps (all in one transaction):**
1. Verify preconditions.
2. INSERT a new `graded_tests` row with `regraded_from_id = source.id`, `rubric_contract_version` = current rubric contract version, status `'pending'`, empty `draft_json`.
3. UPDATE source row: `regraded_to_id = new.id`.
4. Enqueue the agent (transitions through `'grading'` to `'draft'`).
5. Return the new row's id. The teacher's UI navigates to the new draft for review.

Atomicity: steps 1–3 are in one transaction. Step 4 is the agent invocation; if it fails, the new row transitions to `'failed'` (not rolled back). The failed row is still the current leaf — re-grade failure is a real state, not a transient error to swallow.

### 9.4 What is NOT carried forward in a re-grade

- The previous row's teacher overrides are NOT applied to the new row. They were against the previous contract; some criterion IDs may not exist in the new contract, and even those that do may have had their point values change. The teacher starts from a fresh AI grade.
- The previous row's annotations are NOT carried forward. Annotations are tied to a specific grading run.
- The previous row's `total_score` is preserved on the previous row, not copied. The new row's score is computed from its own grading.

What IS carried forward:
- The `transcription_id`. Same student answers.
- The `student_id`. Same student.
- The `rubric_id`. Same rubric (just a new version).

### 9.5 The manual edit action

**Endpoint:** `POST /graded_tests/{id}/manual_edit`

**Precondition:** Source row is in `status = 'approved'`. No staleness check — manual edit is always available on approved rows.

**Steps (all in one transaction):**
1. Verify preconditions.
2. INSERT a new `graded_tests` row with:
   - `regraded_from_id = source.id`
   - `rubric_contract_version = source.rubric_contract_version` (unchanged — rubric hasn't changed)
   - `transcription_id`, `student_id`, `rubric_id`, `user_id` copied from source
   - `draft_json` = `source.contract_json` (the previously approved outcomes + teacher overrides become the starting point for further edits)
   - `status = 'draft'` (no `'grading'` phase — no agent invocation)
3. UPDATE source row: `regraded_to_id = new.id`.
4. Return the new row's id. The teacher's UI navigates to the new draft.

The teacher edits `draft_json.teacher_overrides` as normal, then hits approve. The new row transitions to `'approved'` with a fresh `contract_version` UUID, exactly like any other draft approval.

**What gets carried forward:** Everything from the source row's `contract_json` — both the AI's outcomes and the teacher's previous overrides. The teacher's previous decisions are the starting point because the rubric hasn't changed; those decisions are still valid, and the teacher's intent is to revise them, not start over.

**Note on closed-world:** Since the rubric contract version is unchanged, every criterion ID in the carried-forward draft is still valid. Closed-world enforcement at approval (CW-3) applies as normal.

### 9.6 Which action does the teacher use?

The UI surfaces both controls on an approved graded test:
- "Regrade against updated rubric" — visible only when `rubric_contract_stale = TRUE`.
- "Edit grade manually" — visible whenever the row is in `status = 'approved'`.

A teacher can legitimately do either, or both in sequence (regrade, then manually edit the regrade result). Each action consumes the current leaf and produces a new leaf.

---

## 10. Annotations as Unified Diagnostic Surface

The rubric domain already commits to this pattern (per CLAUDE.md). The grading and transcription domains adopt the same shape — one Pydantic type, one severity taxonomy, one rendering model.

### 10.1 The `GradingAnnotation` shape

(Mirroring the existing rubric-side `Annotation`.)

- `id` — UUID
- `severity` — `'error' | 'warning' | 'info'`
- `target_id` — the scope of the annotation (criterion_id, sub_question_id, question_id, or `'graded_test'` for whole-test scope; `'transcription'` for whole-transcription scope)
- `annotation_type` — string discriminator (`'no_answer'`, `'quote_not_found'`, `'low_confidence'`, `'closed_world_violation'`, `'vlm_uncertainty'`, etc.)
- `message` — human-readable Hebrew string
- `metadata` — open JSON for type-specific data (e.g., `expected_value`, `actual_value`)

### 10.2 What produces annotations on a TranscriptionDraft

- VLM confidence per page (low confidence regions surface as warning-severity annotations).
- VLM-detected uncertain handwriting (specific text regions flagged).
- Missing student name (info-severity if VLM couldn't detect a name in the header).

### 10.3 What produces annotations on a GradedTestDraft

- Agent flags: `no_answer`, `quote_not_found`, `low_confidence` (per criterion).
- Post-LLM validator: `closed_world_violation` (warning if the agent referenced an unknown criterion ID — though by construction this shouldn't happen; defense in depth).
- Post-LLM validator: bounds violations (points outside [0, max], precision mismatches).
- Pre-approval validator (compile-time): point sum mismatches (INV-R1, INV-R1b, INV-R2 violations).

### 10.4 What does NOT produce annotations

- **Teacher actions never produce annotations.** Teacher edits to a draft are recorded as `TeacherOverride` entries, not annotations. Annotations are system diagnostics; overrides are teacher decisions. Distinct semantics.
- **Successful operations.** Annotations are not status messages. "Grading completed successfully" is not an annotation; it's the row's `status` field.

### 10.5 Save-blocking behavior

Same rule as the rubric domain:

- **`error`-severity annotations block save/approval.** A `GradedTestDraft` with any `error` annotation cannot be approved until the teacher resolves the underlying issue. (For closed-world violations: the teacher's overlay must be edited to remove the offending reference. For point-sum violations: the teacher must adjust their overrides to balance.)
- **`warning`-severity annotations are visible but non-blocking.** The teacher sees them, can choose to ignore, and approval proceeds.
- **`info`-severity annotations are informational.** No UI block.

---

## 11. Non-Goals

Things this architecture deliberately does NOT address. Listing them so future readers don't assume an omission is an oversight.

1. **Student-facing features.** Students do not log in, do not view graded tests, do not receive notifications. The schema does not include any student-auth concept. Parent/student communication is a future feature.

2. **Cross-teacher sharing of graded tests.** Rubrics can be shared (existing functionality). Graded tests cannot. There is no schema support for it. If/when this is added, it goes via the existing `rubric_shares` pattern extended to graded tests, in a future PR.

   **Forward-looking note — multi-owner pattern (OQ-2).** Today every entity (`rubrics`, `students`, `classes`, `transcriptions`, `graded_tests`, `grading_batches`) carries a single `user_id NOT NULL` for its owning teacher, and we use `ON DELETE CASCADE` to wipe a teacher's workspace cleanly on user deletion. This is the right choice for pre-launch single-teacher workspaces, but it creates an inflection point we must remember:

   When a future PR introduces multi-owner sharing — e.g., a "share_class" feature where two teachers co-own a class, or extending `rubric_shares` to graded tests — the single `user_id` column will need to be replaced (or supplemented) by a many-to-many ownership pattern. The natural shape is an `ownerships` join table per entity type (or a polymorphic `entity_ownerships` table), with the cascade rule changing from "delete entity when owner deleted" to "remove ownership row; delete entity only when last owner is removed."

   This migration is non-trivial: every list query (currently `WHERE user_id = current_user`) becomes a join query (`WHERE EXISTS (SELECT 1 FROM ownerships WHERE entity_id = X AND user_id = current_user)`), and every CASCADE rule needs revisiting. The work is deferred to the PR that introduces the first multi-owner feature; the architecture lock here is "single-owner today, full rewrite of the ownership layer when sharing lands."

3. **Real-time push notifications for grading completion.** Per OD7 — out of scope for this PR. The architecture deliberately models "grading in progress" as a real state (`status = 'grading'`), so adding SSE/WebSocket later is a small change. But it is not in this PR.

4. **Co-teachers, TAs, admins.** No multi-role permission model. One teacher per artifact, full stop.

5. **Anonymization, pseudonymization, GDPR deletion flows.** Future regulatory work. Not in this PR.

6. **Class-level analytics queries.** The schema supports them (everything is queryable per class via the join table), but no analytics endpoints are added in this PR. They land with the "My Classroom" BI feature.

7. **Bulk approval ("approve all clean drafts").** Per B6 — added later when ≥90% of non-flagged drafts get teacher-approved unchanged. The architecture does not need to change to support this; only a new endpoint.

8. **Teacher-authored annotations / todo flags.** Per B7 — teachers do not write annotations. If they want to flag something for later, they use `teacher_comment` on the relevant criterion's override.

9. **PDF annotation output ("graded test as marked-up PDF").** The infrastructure exists (`graded_test_pdfs` table, GCSService), but the annotation endpoint is a 501 stub today. This PR deletes the unused `graded_test_pdfs` table; the feature lands in a future PR when actually needed.

10. **Subject-matter denormalization on `graded_tests`.** Per OD8 — skipped. Subject is reachable via `graded_tests → rubrics → subject`, two joins, fine for query patterns.

11. **External student ID (school ID, parent contact, etc.).** Per B2 — minimum viable. Not in this PR.

12. **Re-grading against the same rubric version.** Not a supported operation. If a teacher wants to "regrade" without rubric changes, they edit the existing draft. Re-grade only fires when the rubric contract version differs.

13. **A confidence score per draft.** Per B6 — not added until bulk approval lands. Can be computed at that time from existing annotations without schema changes.

---

## 12. Resolved Decisions from Phase 0a Review

These were surfaced during the architecture review and resolved during the lock pass. Recorded here so the rationale survives.

**RD-1 — Class membership: `class_memberships` join table.**
Decision: ship with a M:N join table even though most rows will have one entry. Source: B3 (students can belong to multiple classes). The cost is one table; the benefit is no migration when M:N becomes common. The principle: model the actual relationship, not the common case.

**RD-2 — Cascade rule on teacher deletion: `ON DELETE CASCADE`.**
Decision: keep CASCADE for all teacher-owned entities (`rubrics`, `students`, `classes`, `transcriptions`, `graded_tests`, `grading_batches`). Source: OQ-2. Rationale: pre-launch, no shared data, clean wipe on user deletion. The multi-owner inflection point is documented in §11 as a forward-looking non-goal.

**RD-3 — `transcription_contract_version`: top-level Pydantic field only, NOT denormalized to a column.**
Decision: keep `contract_version` as a top-level field inside `TranscriptionContract` only. No `transcriptions.contract_version` column. Source: OQ-3. Rationale: no query patterns justify denormalizing it; recoverable from `contract_json.contract_version` if ever needed. The graded_test's `transcription_contract_version` pinning is implicit via `transcription_id` FK.

**RD-4 — Student selection happens during transcription review.**
Decision: the UI for picking an existing student or creating a new one lives on the transcription review screen, after VLM completes and before submission to grading. Source: B1 / OQ-4. Rationale: by review time, the teacher has seen the transcribed content (which may include the student's name written at the top of the page) and can make an informed selection. The architecture lock: `transcriptions.student_id` must be populated before `transcriptions.status` can transition to `'approved'`.

**RD-5 — Class memberships: no order, no labels.**
Decision: the `class_memberships` join table carries only `(class_id, student_id, created_at)`. No `position`, `period_label`, or per-membership metadata. Source: OQ-5. Rationale: minimum viable now; if labels become needed, that's a future column on the join table without a structural change.

**RD-6 — Two revision actions on approved graded tests: re-grade and manual edit.**
Decision: both actions extend the revision chain via the same persistence mechanism, but with different semantics. Re-grade fires when the rubric contract version changes and produces a fresh AI grade. Manual edit fires whenever the teacher wants to revise their own approved decisions and produces a new row pre-loaded with the previous contract. Source: review pushback on §3.2 ("approved is read-only" was too strong). Both are documented fully in §3.3 and §9.

---

## 13. Summary — What This Architecture Locks In

In one paragraph: every artifact has exactly one writer path, exactly one persistence location, and a clear lifecycle. The same Draft/Contract pattern that the rubric domain established is extended uniformly to transcription and grading. Teachers own everything they create, with no cross-teacher visibility in scope (single-owner today, multi-owner ownership-table pattern locked as a forward-looking inflection point in §11). Approved graded tests are revised — never mutated — through two actions: re-grade (against an updated rubric contract) and manual edit (against the same rubric, teacher-driven revision). Both extend the same revision chain; neither destroys history. Closed-world is structurally enforced at GradableTest compile time, not as a runtime warning. The teacher-vs-AI distinction is preserved forever by storing AI outcomes and teacher overrides separately. Students and classes are first-class entities from day one, scoped per teacher. Annotations are the single diagnostic surface, mirroring the rubric domain's commitment. Every endpoint authenticates. Every entity has `user_id NOT NULL`. The `GradableTest` exists in memory only — a function of two pinned contract versions, never persisted, always recomputable.

The architecture is locked. Phase 0b (deletion manifest), 0c (DDL), 0d (ERD), 0e (DFD), and 0g (sprint plan) derive from this document.
