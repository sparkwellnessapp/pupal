# Vivi — Phase 0c: Target DDL Specification

**Owner:** Noam
**Status:** LOCKED — derived from Phase 0a (architecture) and Phase 0b (cleanup, executed)
**Locked at:** 2026-05-24
**Scope:** The complete target schema for the new grading pipeline. Defines every new table and every column added to existing tables. Phase 0b dropped what dies; Phase 0c defines what replaces it.

---

## 0. How to read this document

This is a **specification**, not a migration. The SQL below is the target state. The actual migration file (`008_phase_0c_new_schema.sql`, written and executed in S1) is a mechanical translation of this spec into ordered DDL statements.

Each table section contains:
- The DDL.
- Per-column rationale (why this column exists, what writes to it, what reads from it).
- The Pydantic model whose `.model_dump()` serializes into each JSONB column.
- Indexes, with the query pattern each one serves.
- ON DELETE cascade rules and their rationale.
- Invariants enforced at the schema level (via CHECK / UNIQUE constraints).

When the migration in S1 lands, it must match this spec column-by-column. Any deviation requires re-opening Phase 0c and re-locking.

**Conventions throughout:**
- All table names plural snake_case.
- All `created_at` / `updated_at` are `TIMESTAMPTZ NOT NULL DEFAULT now()`. Application updates `updated_at`; no DB triggers.
- All UUIDs use `gen_random_uuid()` (matches recent migration style).
- Numeric points use `NUMERIC(10, 2)` — matches backend `NumericPolicy.precision = "0.25"` with margin.
- Status columns use inline `CHECK (status IN (...))` rather than ENUM types (easier to migrate).
- ON DELETE CASCADE is the default for teacher-owned hierarchies (per Phase 0a RD-2 and §11 forward-looking note).
- JSONB columns carry exactly one Pydantic model's serialized output. The model is named in the column comment.

---

## 1. New Table: `students`

The first-class identity for a learner. Per Phase 0a §2.2.A.

```sql
CREATE TABLE public.students (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    full_name         VARCHAR(255) NOT NULL,
    notes             TEXT,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A teacher cannot have two students with the exact same full_name.
    -- Different teachers may each have a student with the same name; those
    -- are different students (per-teacher scoping per Phase 0a §2.2.A).
    CONSTRAINT students_unique_name_per_user UNIQUE (user_id, full_name)
);

CREATE INDEX idx_students_user ON public.students (user_id);
```

**Column rationale:**

| Column | Rationale |
|---|---|
| `id` | Surrogate key. UUID for distributed-safe generation. |
| `user_id` | The owning teacher. NOT NULL enforces per-teacher scoping. CASCADE on user deletion wipes the workspace cleanly. |
| `full_name` | The student's display name. Per Phase 0a B2 — minimum viable; no email, no external_id, no grade level. Length 255 is overkill but matches existing convention on similar columns. |
| `notes` | Optional free-text. Reserved for the teacher's notes about the student (e.g., "תלמיד עם הקלות"). TEXT (not VARCHAR) because length is genuinely unbounded. |

**Indexes:**

- `idx_students_user` — covers "list my students" query (`SELECT * FROM students WHERE user_id = ?`). The most common student-related query.
- The unique constraint `students_unique_name_per_user` doubles as an index on `(user_id, full_name)` for "find the student named X" lookups.

**Why no `class_id` column on `students`:** Per Phase 0a RD-1 / B3, students can belong to multiple classes (1:n). The relationship lives in `class_memberships` (§3).

**ON DELETE CASCADE behavior:**
- User deleted → student deleted (parent of teacher's workspace).
- Student deleted → its `class_memberships` rows deleted (§3).
- Student deleted → its `transcriptions` deleted (§4).
- Student deleted → its `graded_tests` deleted (§5).

---

## 2. New Table: `classes`

Teacher-defined grouping of students. Per Phase 0a §2.2.B.

```sql
CREATE TABLE public.classes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,

    name              VARCHAR(255) NOT NULL,
    subject_matter_id INTEGER REFERENCES public.subject_matters(id) ON DELETE SET NULL,
    school_year       VARCHAR(20),

    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- A teacher cannot have two classes with the same name.
    -- Different teachers may both have a class named "כיתה י3".
    CONSTRAINT classes_unique_name_per_user UNIQUE (user_id, name)
);

CREATE INDEX idx_classes_user ON public.classes (user_id);
```

**Column rationale:**

| Column | Rationale |
|---|---|
| `user_id` | Per-teacher scoping. CASCADE on user deletion. |
| `name` | Free text — "כיתה י3", "Honors CS 11", whatever the teacher uses. |
| `subject_matter_id` | Optional FK to existing `subject_matters` table. Tags the class with its subject. `ON DELETE SET NULL` — if the subject_matter row is deleted (rare), the class survives without a subject tag rather than cascading. |
| `school_year` | Optional free text — "2025-2026", "תשפ״ו". Not a date because schools represent academic years inconsistently across regions. |

**Indexes:**

- `idx_classes_user` — covers "list my classes" query.
- Unique constraint doubles as index on `(user_id, name)`.

**ON DELETE CASCADE behavior:**
- User deleted → class deleted.
- Class deleted → its `class_memberships` rows deleted.
- `subject_matters` deleted → class survives with `subject_matter_id = NULL` (SET NULL, not CASCADE — the class is the teacher's, not the subject's).

---

## 3. New Table: `class_memberships`

The M:N join table between students and classes. Per Phase 0a §2.2.B and RD-1.

```sql
CREATE TABLE public.class_memberships (
    class_id          UUID NOT NULL REFERENCES public.classes(id) ON DELETE CASCADE,
    student_id        UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),

    PRIMARY KEY (class_id, student_id)
);

CREATE INDEX idx_class_memberships_student ON public.class_memberships (student_id);
```

**Column rationale:**

| Column | Rationale |
|---|---|
| `class_id` | The class this membership joins. |
| `student_id` | The student joined to the class. |
| `created_at` | When the student was added to the class. Useful for the BI roadmap ("when did Yossi enter this class"). |
| (no other columns) | Per Phase 0a RD-5 — no order, no labels. If "Yossi is in 4th period" labels become needed, that's a future column. |

**Indexes:**

- The PK `(class_id, student_id)` covers "list students in this class" queries (PK is a btree index on the composite key, searchable by leading column).
- `idx_class_memberships_student` covers the reverse direction: "what classes is this student in."

**ON DELETE CASCADE behavior:**
- Class deleted → membership rows deleted.
- Student deleted → membership rows deleted.
- (The teacher-deletion cascade fires through `classes` or `students`, then through here.)

**Why a join table for what's currently 1:1 in most cases:** Per Phase 0a RD-1 — model the actual relationship, not the common case. The cost is one table; the benefit is no migration when M:N becomes common.

---

## 4. New Table: `transcriptions`

The transcription artifact — Draft + Contract for one student's handwritten test. Per Phase 0a §2.1.A.

```sql
CREATE TABLE public.transcriptions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rubric_id           UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,

    -- Student is assigned at transcription review time (Phase 0a RD-4).
    -- NULL while status='transcribed'; populated when status transitions to 'approved'.
    student_id          UUID REFERENCES public.students(id) ON DELETE CASCADE,
    -- Denormalized from students.full_name for list query performance.
    -- Kept consistent at write time. NULL when student_id is NULL.
    student_name        VARCHAR(255),

    -- Source PDF in GCS (uploaded at transcription time, per Phase 0a OD2).
    -- NOT NULL — a transcription row's existence implies the PDF is in GCS.
    gcs_uri             VARCHAR(500) NOT NULL,
    gcs_bucket          VARCHAR(255) NOT NULL,
    gcs_object_path     VARCHAR(500) NOT NULL,
    filename            VARCHAR(500),

    -- Draft side — what the VLM produced. Immutable from INSERT onward.
    -- Pydantic model: TranscriptionDraft (defined in S4).
    draft_json          JSONB NOT NULL,

    -- Contract side — teacher-approved StudentAnswer set, frozen.
    -- Pydantic model: TranscriptionContract (defined in S4).
    -- contract_version lives inside the JSONB (Phase 0a RD-3 — no column).
    -- NULL while status='transcribed'; populated when status transitions to 'approved'.
    contract_json       JSONB,
    approved_at         TIMESTAMPTZ,

    -- Lifecycle.
    status              VARCHAR(20) NOT NULL DEFAULT 'transcribed'
                        CHECK (status IN ('transcribed', 'approved')),

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Status invariant: an approved transcription has all the approval fields set.
    CONSTRAINT transcriptions_approval_consistency
        CHECK (
            (status = 'transcribed' AND contract_json IS NULL AND approved_at IS NULL AND student_id IS NULL)
            OR
            (status = 'approved' AND contract_json IS NOT NULL AND approved_at IS NOT NULL AND student_id IS NOT NULL)
        )
);

CREATE INDEX idx_transcriptions_user_rubric ON public.transcriptions (user_id, rubric_id);
CREATE INDEX idx_transcriptions_user_student ON public.transcriptions (user_id, student_id)
    WHERE student_id IS NOT NULL;
CREATE INDEX idx_transcriptions_status ON public.transcriptions (status);
```

**Column rationale:**

| Column | Rationale |
|---|---|
| `user_id` | Per-teacher scoping. NOT NULL. |
| `rubric_id` | Which rubric this transcription is for. Pinned at creation; never changes. CASCADE on rubric deletion. |
| `student_id` | Nullable while in `'transcribed'` status; required by CHECK constraint at `'approved'`. Phase 0a §3.1 invariant LCY-1 enforces this. |
| `student_name` | Denormalized from `students.full_name`. Updated atomically when `students.full_name` is updated (application-level — no trigger). Enables "list transcriptions by student name" without joining. |
| `gcs_uri`, `gcs_bucket`, `gcs_object_path` | Per OD2 — original student PDF persisted in GCS at transcription time. All three NOT NULL because the row's existence implies a successful GCS upload. (`gcs_uri` is the full `gs://bucket/path` URI; `gcs_bucket` and `gcs_object_path` are decomposed for query convenience.) |
| `filename` | The original PDF's filename. Nullable because some sources may not provide one. |
| `draft_json` | VLM output. NOT NULL — INSERT requires the VLM to have completed. Once written, never updated. |
| `contract_json` | Teacher-approved student answers. NULL until status transitions to `'approved'`. Set once, then immutable. |
| `approved_at` | When the teacher submitted. NULL until approval. |
| `status` | Two values only — `'transcribed'` (just-VLM'd) and `'approved'` (teacher submitted to grade). Transcription has no `'failed'` state because failed transcriptions don't produce rows (the endpoint returns an error and no INSERT happens). |
| `transcriptions_approval_consistency` CHECK | Enforces LCY-1 at the schema level. A row in `'approved'` status must have all approval fields populated. A row in `'transcribed'` status must have none of them populated. Prevents partial-state rows. |

**Indexes:**

- `idx_transcriptions_user_rubric` — covers "list all my transcriptions for rubric X" (the most common list query — for example, the batch dashboard).
- `idx_transcriptions_user_student` — partial index (only rows with `student_id` populated) — covers "list all transcriptions for student X" (used in the My Classroom feature, future).
- `idx_transcriptions_status` — covers admin/observability queries grouping by status.

**ON DELETE CASCADE behavior:**
- User deleted → transcription deleted.
- Rubric deleted → transcription deleted.
- Student deleted → transcription deleted (when student_id is set).
- Transcription deleted → its `graded_tests` rows deleted (§5).

**Note on `transcription_id` direct deletion:** No application endpoint currently deletes transcriptions directly. Deletes happen only via cascade from User / Rubric / Student. If a "delete transcription" endpoint is ever added (e.g., teacher wants to wipe and re-transcribe a PDF), the dependent `graded_tests` rows cascade out automatically.

---

## 5. Reshape: `graded_tests`

The graded test artifact — Draft + Contract for one (transcription, rubric version, grading pass) triple. Per Phase 0a §2.1.C.

The S1 migration drops every column from the current `graded_tests` table (which lost its dead columns in Phase 0b) and rebuilds it in this shape. Since the table is empty pre-launch, this is `DROP TABLE` + `CREATE TABLE`. The migration file makes this explicit.

```sql
CREATE TABLE public.graded_tests (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                     UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rubric_id                   UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,
    transcription_id            UUID NOT NULL REFERENCES public.transcriptions(id) ON DELETE CASCADE,
    student_id                  UUID NOT NULL REFERENCES public.students(id) ON DELETE CASCADE,
    batch_id                    UUID REFERENCES public.grading_batches(id) ON DELETE SET NULL,

    -- The exact GradingRubricContract version this row was graded against.
    -- Pinned at INSERT; never changes (Phase 0a invariant VER-2).
    rubric_contract_version     VARCHAR(50) NOT NULL,

    -- Denormalized from students.full_name. Kept consistent at write time.
    student_name                VARCHAR(255) NOT NULL,
    -- Denormalized from transcriptions.filename. Set at INSERT.
    filename                    VARCHAR(500),

    -- Draft side — agent outcomes + teacher overrides.
    -- Pydantic model: GradedTestDraft (defined in S6/S8).
    -- NULL while status IN ('pending', 'grading'); populated when status='draft' or beyond.
    draft_json                  JSONB,
    draft_created_at            TIMESTAMPTZ,

    -- Contract side — frozen, approved.
    -- Pydantic model: GradedTestContract (defined in S9).
    -- contract_version lives inside the JSONB.
    -- NULL until status='approved'.
    contract_json               JSONB,
    approved_at                 TIMESTAMPTZ,

    -- Revision chain (per Phase 0a §2.1.C, §3.3, §5.5).
    -- regraded_from_id: the row this row replaces (NULL for first grade).
    -- regraded_to_id: the row that replaces this row (NULL for the current leaf).
    regraded_from_id            UUID REFERENCES public.graded_tests(id) ON DELETE SET NULL,
    regraded_to_id              UUID REFERENCES public.graded_tests(id) ON DELETE SET NULL,

    -- Lifecycle.
    status                      VARCHAR(20) NOT NULL DEFAULT 'pending'
                                CHECK (status IN ('pending', 'grading', 'draft', 'approved', 'failed')),
    error_message               TEXT,

    -- Denormalized score for list view performance.
    -- Computed from draft_json (agent outcomes + teacher overrides) at each draft write.
    -- Frozen-final on approval (set from contract_json).
    -- NULL until grading completes.
    total_score                 NUMERIC(10, 2),
    total_possible              NUMERIC(10, 2),
    percentage                  NUMERIC(5, 2),

    -- Observability — populated from agent output at grading completion.
    llm_calls_count             INTEGER NOT NULL DEFAULT 0,
    grading_duration_ms         INTEGER NOT NULL DEFAULT 0,
    model_version               VARCHAR(50),

    created_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Status invariants — enforce LCY-2 and the draft/contract presence rules.
    CONSTRAINT graded_tests_status_consistency
        CHECK (
            (status = 'pending' AND draft_json IS NULL AND contract_json IS NULL)
            OR
            (status = 'grading' AND draft_json IS NULL AND contract_json IS NULL)
            OR
            (status = 'draft' AND draft_json IS NOT NULL AND contract_json IS NULL)
            OR
            (status = 'approved' AND draft_json IS NOT NULL AND contract_json IS NOT NULL AND approved_at IS NOT NULL)
            OR
            (status = 'failed' AND error_message IS NOT NULL)
        )
);

-- RGC-1 enforcement: exactly one leaf (regraded_to_id IS NULL) per
-- (transcription_id, rubric_id) pair. Partial unique index.
CREATE UNIQUE INDEX idx_graded_tests_one_leaf_per_chain
    ON public.graded_tests (transcription_id, rubric_id)
    WHERE regraded_to_id IS NULL;

-- Query indexes.
CREATE INDEX idx_graded_tests_user_rubric    ON public.graded_tests (user_id, rubric_id);
CREATE INDEX idx_graded_tests_user_student   ON public.graded_tests (user_id, student_id);
CREATE INDEX idx_graded_tests_batch          ON public.graded_tests (batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX idx_graded_tests_transcription  ON public.graded_tests (transcription_id);
CREATE INDEX idx_graded_tests_status         ON public.graded_tests (status);
CREATE INDEX idx_graded_tests_regraded_from  ON public.graded_tests (regraded_from_id)
    WHERE regraded_from_id IS NOT NULL;
```

**Column rationale:**

| Column | Rationale |
|---|---|
| `user_id` | Per-teacher scoping. NOT NULL. Even though `transcription_id` would let us derive this via join, denormalizing is the existing convention everywhere and dramatically simplifies the auth check (`WHERE user_id = current_user`) without joining. |
| `rubric_id` | Which rubric this grade is against. NOT NULL. Same join-avoidance rationale. |
| `transcription_id` | The transcription that was graded. NOT NULL — every graded test has a transcription. CASCADE on transcription deletion. |
| `student_id` | NOT NULL — by the time a graded test exists, the transcription is approved and has a student. Denormalized for query performance (avoids joining through transcription). |
| `batch_id` | Nullable — single-test grading doesn't use a batch. `ON DELETE SET NULL` per the rationale in Phase 0a §2.2.C. |
| `rubric_contract_version` | The exact contract version this row was graded against. NOT NULL. Pinned at INSERT, never changes. Used for the `rubric_contract_stale` computation (Phase 0a §9.2) by joining to `rubrics.contract_version`. |
| `student_name`, `filename` | Denormalized for list query performance. Kept consistent at write time. |
| `draft_json` | Agent outcomes + teacher overrides. NULL during `pending`/`grading`; populated from `draft` onward. The agent's outcomes within `draft_json` are immutable post-grade (per Phase 0a §3.2); only `teacher_overrides` mutate. |
| `draft_created_at` | When the agent completed and produced the draft. Distinguishes "draft was created at T1, teacher last edited at T2" if/when we add a `teacher_overrides_updated_at` later. For now just T1. |
| `contract_json` | Frozen approved form. NULL until `'approved'`. Pydantic model: `GradedTestContract`. |
| `approved_at` | When the teacher approved. NULL until `'approved'`. |
| `regraded_from_id` | FK to the row this replaces. Self-referential. NULL for first grade. `ON DELETE SET NULL` — if the predecessor is somehow deleted, this row survives orphaned but auditable. |
| `regraded_to_id` | FK to the row that replaces this. NULL for the current leaf. `ON DELETE SET NULL` for the same reason. |
| `status` | Five values. State machine per Phase 0a §3.2. CHECK constraint enforces statuses. |
| `error_message` | Populated only when `status='failed'`. Free text. |
| `total_score`, `total_possible`, `percentage` | Denormalized score for list views. Updated whenever `draft_json` changes (application-level). Frozen on approval. |
| `llm_calls_count`, `grading_duration_ms`, `model_version` | Observability. Set from agent output. |
| `graded_tests_status_consistency` CHECK | Schema-level enforcement of the state machine's invariants. A row with `status='approved'` cannot have NULL `contract_json`. A row with `status='draft'` must have `draft_json` populated. A row with `status='failed'` must have `error_message`. Encoded as one omnibus CHECK because PostgreSQL evaluates them atomically. |

**Indexes:**

- `idx_graded_tests_one_leaf_per_chain` — **the load-bearing index for RGC-1.** Enforces "exactly one leaf per `(transcription_id, rubric_id)` pair" by partial uniqueness on `WHERE regraded_to_id IS NULL`. Also serves the "find the current grade for this (transcription, rubric) pair" query, the most common access pattern.
- `idx_graded_tests_user_rubric` — covers the teacher's primary list query: "show me all grades against rubric X." (Combined with `WHERE regraded_to_id IS NULL` at query time to show only current leaves.)
- `idx_graded_tests_user_student` — covers "show me all grades for student Y." Critical for the My Classroom roadmap feature.
- `idx_graded_tests_batch` — partial index — covers "show me a batch's grades." The dashboard.
- `idx_graded_tests_transcription` — covers transcription→grade lookup, and walks revision chains forward (a row's siblings in the chain share `transcription_id`).
- `idx_graded_tests_status` — admin/observability grouping.
- `idx_graded_tests_regraded_from` — partial index — covers the backward chain walk ("which row was this one created from"). Used for displaying revision history in the UI.

**On the absence of `idx_graded_tests_regraded_to`:** Not needed. The forward direction is already covered by `idx_graded_tests_one_leaf_per_chain` (it's an index on `(transcription_id, rubric_id)` with the partial predicate, but PostgreSQL can use partial-index columns for non-partial queries).

**ON DELETE behavior summary:**
- User deleted → graded_test deleted (CASCADE).
- Rubric deleted → graded_test deleted (CASCADE).
- Transcription deleted → graded_test deleted (CASCADE) — fires only when transcription is directly deleted; otherwise user/rubric cascade fires first.
- Student deleted → graded_test deleted (CASCADE).
- Batch deleted → graded_test survives with `batch_id = NULL` (SET NULL — the grade is the teacher's, not the batch's).
- Predecessor/successor in revision chain deleted → row survives with NULL FK (SET NULL — preserves the audit even if half the chain is gone, though this shouldn't happen in practice).

---

## 6. Reshape: `grading_batches`

Slimmed per Phase 0a §2.2.C. Phase 0b dropped the three count columns; this section defines the surviving shape.

```sql
-- grading_batches existed before Phase 0b and had three columns dropped.
-- The remaining shape after migration 007:

CREATE TABLE public.grading_batches (
    id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id                  UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    rubric_id                UUID NOT NULL REFERENCES public.rubrics(id) ON DELETE CASCADE,

    rubric_contract_version  VARCHAR(50) NOT NULL,

    name                     VARCHAR(255),
    class_id                 UUID REFERENCES public.classes(id) ON DELETE SET NULL,

    status                   VARCHAR(30) NOT NULL DEFAULT 'pending'
                             CHECK (status IN ('pending', 'in_progress', 'completed',
                                               'partially_completed', 'failed')),

    started_at               TIMESTAMPTZ,
    completed_at             TIMESTAMPTZ,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_grading_batches_user ON public.grading_batches (user_id);
```

**Changes from pre-Phase-0b shape:**

- **Dropped (in 007):** `total_sessions`, `completed_sessions`, `failed_sessions` — counts are now derived at query time from `SELECT status, count(*) FROM graded_tests WHERE batch_id = ? GROUP BY status`.
- **Reshaped (in 008):** `class_id` becomes a real FK to the new `classes` table (was free-text VARCHAR pre-Phase-0a; the column is renamed and re-typed as part of migration 008). Old `class_id` data is wiped because there are no real users.
- **Renamed (in 008):** `teacher_id` → `user_id` for consistency with the rest of the schema. Same column, new name, FK already in place.

**Column rationale:**

| Column | Rationale |
|---|---|
| `user_id` | Owning teacher. |
| `rubric_id` | Which rubric was graded. |
| `rubric_contract_version` | Pinned contract version for the whole batch — all `graded_tests` in this batch share this version. |
| `name` | Free text — "Midterm 2026" or whatever the teacher chose. Nullable. |
| `class_id` | Optional FK to the class being graded. Nullable. SET NULL on class deletion. |
| `status` | Batch-level status. Derived counts (pending/in_progress/completed/failed) come from a `GROUP BY` query on `graded_tests.status`; the batch's own `status` is a roll-up of the children's states, written by the application when batch transitions are detected. |
| `started_at`, `completed_at` | Wall-clock timestamps for the batch's overall run. |

**Indexes:**

- `idx_grading_batches_user` — covers "list my batches."

**ON DELETE CASCADE behavior:**
- User deleted → batch deleted.
- Rubric deleted → batch deleted.
- Class deleted → batch survives with `class_id = NULL`.
- Batch deleted → `graded_tests.batch_id` set to NULL (per §5).

---

## 7. Untouched tables (for reference)

These existed before Phase 0c and are not modified by it:

- `users` — auth and teacher identity. Unchanged.
- `rubrics` — already has `draft_json`, `contract_json`, `contract_version` from earlier migrations. Phase 0b dropped two dead columns; the rest survives.
- `subject_matters`, `user_subject_matters` — unchanged.
- `rubric_shares`, `rubric_share_history`, `rubric_share_tokens` — unchanged.
- `raw_rubrics` — unchanged (the rubric-side raw artifact, distinct from the now-dropped `raw_graded_tests`).

---

## 8. Cross-table invariants enforced at the schema level

Phase 0a §5 specifies invariants at the architecture level. The schema enforces a subset of them via constraints:

| Invariant | How enforced |
|---|---|
| **IDN-1** — Every transcription has exactly one user_id and rubric_id | `NOT NULL` columns + FK |
| **IDN-2** — An approved transcription has a student_id | `transcriptions_approval_consistency` CHECK |
| **IDN-3** — Every graded_test has a transcription | `transcription_id NOT NULL` FK |
| **IDN-4** — Every graded_test has a rubric and version | `rubric_id NOT NULL` FK + `rubric_contract_version NOT NULL` |
| **IDN-5** — Every entity has a user_id | `user_id NOT NULL` FK on every table |
| **LCY-1** — Approved transcription is read-only except for cascade fields | CHECK + application-level (transitions blocked) |
| **LCY-2** — Approved/failed graded_test is read-only except for `regraded_to_id` | CHECK + application-level |
| **RGC-1** — One leaf per (transcription_id, rubric_id) pair | `idx_graded_tests_one_leaf_per_chain` partial unique index |
| **OWN** — Per-teacher scoping | All `user_id NOT NULL` + every query filters on `user_id = current_user` |

Invariants enforced at the application layer (not the schema):

| Invariant | Why not schema |
|---|---|
| **CW-1, CW-2, CW-3** — Closed-world criterion ID references | The valid criterion IDs live inside `rubrics.contract_json` (JSONB). CHECK constraints can't reach into JSONB. Enforced at GradableTest compile time (by construction) and at approval (validator). |
| **PTS-1, PTS-2, PTS-3** — Point-sum invariants | Same reason — sums live across nested JSONB structures. Validator at approval. |
| **RGC-2** — Bidirectional FK consistency (R1.regraded_to_id = R2 ↔ R2.regraded_from_id = R1) | Could be enforced by trigger but isn't (per the no-triggers convention). Enforced atomically by the application transaction that creates the new row. |
| **RGC-3, RGC-4, RGC-5** — Chain shape | Application-level. RGC-1 (the leaf uniqueness) is the load-bearing one; the rest follow from atomic transaction structure. |
| **VER-1, VER-2, VER-3** — Version UUIDs | Application generates them at the right moments. |
| **ANN-1 through ANN-4** — Annotations as unified surface | All annotations live inside JSONB. Schema can't see them. |

---

## 9. Denormalization map (where consistency is enforced)

Per Phase 0a §4 and §7, several columns carry denormalized data from authoritative sources. The schema does NOT enforce consistency (no triggers); the application does, atomically per transaction.

| Denormalized column | Authoritative source | When updated |
|---|---|---|
| `transcriptions.student_name` | `students.full_name` (via `student_id`) | On student creation / rename. Same transaction. |
| `graded_tests.student_name` | `students.full_name` | Same. |
| `graded_tests.filename` | `transcriptions.filename` | At graded_test INSERT (copied in once; transcriptions don't rename). |
| `graded_tests.total_score`, `total_possible`, `percentage` | `draft_json` (or `contract_json` post-approval) | At each draft update; at approval. |

**The consistency contract:** Whenever an authoritative source changes, every denormalized copy is updated in the same transaction. A schema-level check is not used; application-level discipline is. The application's data-access layer must encapsulate this — direct UPDATE statements on `students.full_name` without updating denormalized copies are a bug.

---

## 10. ERD-derivation hints (for Phase 0d)

When Phase 0d generates the ERD from this DDL, the relationships to surface visually:

- `users` (1) ─── (N) `students`, `classes`, `transcriptions`, `graded_tests`, `grading_batches` [all CASCADE]
- `students` (M) ─── (N) `classes` via `class_memberships`
- `rubrics` (1) ─── (N) `transcriptions`, `graded_tests`, `grading_batches` [all CASCADE]
- `transcriptions` (1) ─── (N) `graded_tests` [CASCADE]
- `students` (1) ─── (N) `transcriptions`, `graded_tests` [CASCADE]
- `classes` (0,1) ─── (N) `grading_batches` [SET NULL]
- `graded_tests` (0,1) ─── (0,1) `graded_tests` via `regraded_from_id` / `regraded_to_id` [self-referential, SET NULL]
- `subject_matters` (0,1) ─── (N) `classes` [SET NULL]
- `grading_batches` (0,1) ─── (N) `graded_tests` [SET NULL]

---

## 11. What's NOT in this DDL

Listed so future readers know what they shouldn't expect to find:

1. **`rubric_contract_stale` column** — per Phase 0a §9.2, computed at query time via join, not stored.
2. **`transcriptions.contract_version` column** — per RD-3, lives inside `contract_json` JSONB.
3. **`graded_tests.transcription_contract_version` column** — recoverable from `transcription_id` + `transcriptions.contract_json`. Not denormalized.
4. **`approved_by` columns** — single-owner today; always equals `user_id`. Adds nothing now. Lands when multi-owner sharing arrives.
5. **Triggers** — none. All consistency rules are application-enforced.
6. **JSONB GIN indexes** — none. No query patterns search inside JSONB. Add later if a pattern emerges.
7. **Soft-delete columns (`archived_at`, `deleted_at`)** — none. Hard delete via CASCADE for now.
8. **`students.external_id`, `email`, `grade_level`** — per B2, minimum viable.
9. **`class_memberships.position` or labels** — per RD-5, minimum viable.
10. **`graded_test_pdfs` table or annotation-output columns** — feature deferred (Phase 0a §11.9).

---

## 12. Sanity check before locking

Before sealing this Phase 0c document, verify:

- [x] Every column has a documented writer and reader (or a marked "deferred to S{N}" path).
- [x] Every FK has an explicit ON DELETE rule, justified inline.
- [x] Every index has a named query pattern it serves.
- [x] Every CHECK constraint encodes a Phase 0a invariant.
- [x] The denormalization map (§9) names every column where the same data lives twice, plus the consistency-enforcement story.
- [x] §11 explicitly lists every column-we-might-have-added-and-didn't, with the reason.
- [x] No table or column from Phase 0b's deletion list reappears here.

Locked.

---

## 13. Next phase

**Phase 0d (ERD)** — derived mechanically from this DDL. The ERD's purpose is visual cross-check, not design. If §10 above contains the right relationship list, the ERD should be a faithful diagram of it.

**Phase 0e (DFD)** — derived from Phase 0a's lifecycle diagrams (§3) crossed with this DDL's tables. Each data flow lands in a specific table+column.

**S1 migration** — `008_phase_0c_new_schema.sql` — mechanical translation of §1–§6 above into ordered DDL statements (create new tables first, then alter existing ones). The migration includes its own preflight comment confirming Phase 0b has been run.
