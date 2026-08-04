# PR: S1 — ORM models for the new grading schema

**Sprint:** S1
**Depends on:** S0 (cleanup, merged), migration 007 (executed), migration 008 (executed)
**Foundation refs:** `phase_0a_architecture.md`, `phase_0c_target_ddl.md`, `phase_0d_erd.md`
**Frontend lockstep:** none — this PR is backend-only, no API surface changes

---

## 1. Summary

Migration 008 created the new schema in the database. This PR makes the SQLAlchemy ORM layer mirror that schema exactly. It creates four new models (`Student`, `Class`, `ClassMembership`, `Transcription`), rebuilds two reshaped models (`GradedTest`, `GradingBatch`), and wires every relationship and back-reference.

**This PR contains no endpoints, no Pydantic schemas, no services, no business logic.** It is the data-access foundation only. Every later sprint (S2 auth, S3 students/classes endpoints, S4 transcription, S6/S7 agent, S8 grading, S9 approval) builds on these models. If the models are wrong, everything downstream inherits the error — so this PR's bar is *faithful mirror of the migrated schema*, verified by tests.

---

## 2. Context

The grading pipeline redesign replaced the old `graded_tests` (which conflated transcription and grading) with a chain of typed artifacts, each following the Draft/Contract pattern the rubric domain already uses. See `phase_0a_architecture.md` §2 for the artifact inventory and §3 for the lifecycle state machines. The schema that encodes this is specified column-by-column in `phase_0c_target_ddl.md` and visualized in `phase_0d_erd.md`.

The database already has this schema (migration 008, executed). The ORM models in `app/models/` are now out of sync with the database: `GradedTest` references columns that no longer exist, and four tables have no model at all. This PR closes that gap.

---

## 3. Scope

### In scope
- Create `Student` model (`students` table)
- Create `Class` model (`classes` table)
- Create `ClassMembership` association-object model (`class_memberships` table)
- Create `Transcription` model (`transcriptions` table)
- Rebuild `GradedTest` model against the new `graded_tests` shape
- Re-create `GradingBatch` model against the new `grading_batches` shape (the old class was deleted in S0)
- Add the new relationships and `back_populates` on the existing `User`, `Rubric`, and `SubjectMatter` models
- Update `app/models/__init__.py` to export the new models
- Tests verifying the models match the DB and the relationships traverse correctly

### Out of scope (explicitly deferred)
- **Pydantic models for the JSONB columns** (`TranscriptionDraft`, `TranscriptionContract`, `GradedTestDraft`, `GradedTestContract`). The ORM maps these columns as raw `JSONB`. The typed shapes land in S4 (transcription) and S6/S8/S9 (grading). **Do not** add `TypeDecorator` or Pydantic validation on the JSONB columns in this PR.
- **Any endpoint, route, or API schema.** No `app/api/` changes.
- **Any service or business logic.** No `app/services/` changes.
- **The `GradableTest` artifact.** It is in-memory only (Phase 0a §8) — no table, no ORM model, ever.
- **Auth wiring.** `Depends(get_current_user)` lands in S2.

---

## 4. Files

### Create
| File | Contents |
|---|---|
| `app/models/student.py` | `Student` |
| `app/models/classroom.py` | `Class`, `ClassMembership` (NOTE: file is named `classroom.py`, not `class.py` — `class` is a reserved word and `app.models.class` is unimportable) |
| `app/models/transcription.py` | `Transcription` |

### Modify
| File | Change |
|---|---|
| `app/models/grading.py` | Rebuild `GradedTest`; re-create `GradingBatch`; add new relationships to `Rubric` |
| `app/models/user.py` | Add relationships: `students`, `classes`, `transcriptions`, `graded_tests`, `grading_batches` |
| `app/models/__init__.py` | Import and export the new models |
| (wherever `SubjectMatter` is defined) | Add `classes` relationship |

---

## 5. Model specifications

Each model below mirrors the DDL in `phase_0c_target_ddl.md`. Column types, nullability, and FK targets must match migration 008 exactly. Where this spec and the executed migration disagree, **the migration wins** — verify against the live DB, not against this document.

### 5.1 `Student` (`app/models/student.py`)

Mirrors `phase_0c_target_ddl.md` §1.

```
Columns:
  id          UUID PK, default uuid4
  user_id     UUID FK → users.id, NOT NULL
  full_name   String(255), NOT NULL
  notes       Text, nullable
  created_at  DateTime(tz), NOT NULL, default now
  updated_at  DateTime(tz), NOT NULL, default now

Table args:
  UniqueConstraint(user_id, full_name)  -- name: students_unique_name_per_user

Relationships:
  user            → User           (back_populates="students")
  class_memberships → ClassMembership (back_populates="student", passive_deletes=True)
  transcriptions  → Transcription   (back_populates="student", passive_deletes=True)
  graded_tests    → GradedTest      (back_populates="student", passive_deletes=True)
```

### 5.2 `Class` (`app/models/classroom.py`)

Mirrors `phase_0c_target_ddl.md` §2. Python class name `Class`, table name `classes`.

```
Columns:
  id                 UUID PK, default uuid4
  user_id            UUID FK → users.id, NOT NULL
  name               String(255), NOT NULL
  subject_matter_id  Integer FK → subject_matters.id, nullable
  school_year        String(20), nullable
  created_at         DateTime(tz), NOT NULL, default now
  updated_at         DateTime(tz), NOT NULL, default now

Table args:
  UniqueConstraint(user_id, name)  -- name: classes_unique_name_per_user

Relationships:
  user           → User            (back_populates="classes")
  subject_matter → SubjectMatter   (back_populates="classes")
  memberships    → ClassMembership (back_populates="school_class", passive_deletes=True)
```

### 5.3 `ClassMembership` (`app/models/classroom.py`)

Mirrors `phase_0c_target_ddl.md` §3. **Association-object pattern**, not a bare `secondary=` table — because the join carries `created_at` (per Phase 0c RD-5, for the BI roadmap).

```
Columns:
  class_id    UUID FK → classes.id, PK part, NOT NULL
  student_id  UUID FK → students.id, PK part, NOT NULL
  created_at  DateTime(tz), NOT NULL, default now

Table args:
  PrimaryKeyConstraint(class_id, student_id)

Relationships:
  school_class → Class    (back_populates="memberships")
  student      → Student  (back_populates="class_memberships")
```

Optional: add association proxies so `student.classes` and `school_class.students` work directly. Nice-to-have, not required for this PR. If added, keep them read-through only; do not add write-side proxy magic.

### 5.4 `Transcription` (`app/models/transcription.py`)

Mirrors `phase_0c_target_ddl.md` §4.

```
Columns:
  id               UUID PK, default uuid4
  user_id          UUID FK → users.id, NOT NULL
  rubric_id        UUID FK → rubrics.id, NOT NULL
  student_id       UUID FK → students.id, nullable
  student_name     String(255), nullable
  gcs_uri          String(500), NOT NULL
  gcs_bucket       String(255), NOT NULL
  gcs_object_path  String(500), NOT NULL
  filename         String(500), nullable
  draft_json       JSONB, NOT NULL
  contract_json    JSONB, nullable
  approved_at      DateTime(tz), nullable
  status           String(20), NOT NULL, default 'transcribed'
  created_at       DateTime(tz), NOT NULL, default now
  updated_at       DateTime(tz), NOT NULL, default now

Relationships:
  user         → User        (back_populates="transcriptions")
  rubric       → Rubric      (back_populates="transcriptions")
  student      → Student     (back_populates="transcriptions")
  graded_tests → GradedTest  (back_populates="transcription", passive_deletes=True)

Notes:
  - draft_json / contract_json are raw JSONB. No Pydantic, no TypeDecorator (deferred to S4).
  - The CHECK constraint transcriptions_approval_consistency lives in the DB
    (migration 008). Do NOT re-declare it in the ORM; the DB owns it. The model
    does not need to mirror CHECK constraints.
  - status is a plain String. The valid values are DB-enforced via CHECK. Do not
    use a Python Enum column type — keep it String to match the migration.
```

### 5.5 `GradedTest` (rebuild — `app/models/grading.py`)

Mirrors `phase_0c_target_ddl.md` §5. The existing `GradedTest` class is rebuilt — drop every old column, add the new shape.

```
Columns:
  id                       UUID PK, default uuid4
  user_id                  UUID FK → users.id, NOT NULL
  rubric_id                UUID FK → rubrics.id, NOT NULL
  transcription_id         UUID FK → transcriptions.id, NOT NULL
  student_id               UUID FK → students.id, NOT NULL
  batch_id                 UUID FK → grading_batches.id, nullable
  rubric_contract_version  String(50), NOT NULL
  student_name             String(255), NOT NULL
  filename                 String(500), nullable
  draft_json               JSONB, nullable
  draft_created_at         DateTime(tz), nullable
  contract_json            JSONB, nullable
  approved_at              DateTime(tz), nullable
  regraded_from_id         UUID FK → graded_tests.id, nullable
  regraded_to_id           UUID FK → graded_tests.id, nullable
  status                   String(20), NOT NULL, default 'pending'
  error_message            Text, nullable
  total_score              Numeric(10,2), nullable
  total_possible           Numeric(10,2), nullable
  percentage               Numeric(5,2), nullable
  llm_calls_count          Integer, NOT NULL, default 0
  grading_duration_ms      Integer, NOT NULL, default 0
  model_version            String(50), nullable
  created_at               DateTime(tz), NOT NULL, default now
  updated_at               DateTime(tz), NOT NULL, default now

Relationships:
  user           → User           (back_populates="graded_tests")
  rubric         → Rubric         (back_populates="graded_tests")
  transcription  → Transcription  (back_populates="graded_tests")
  student        → Student        (back_populates="graded_tests")
  batch          → GradingBatch   (back_populates="graded_tests")
  regraded_from  → GradedTest     (self-referential — see Critical Note 1)
  regraded_to    → GradedTest     (self-referential — see Critical Note 1)

Notes:
  - draft_json / contract_json raw JSONB (deferred to S6/S8/S9).
  - The CHECK constraint graded_tests_status_consistency and the partial unique
    index idx_graded_tests_one_leaf_per_chain live in the DB. Do NOT re-declare
    them in the ORM. The model does not enforce them; the DB does.
  - total_score etc. are Numeric — map to Python Decimal, not float.
```

### 5.6 `GradingBatch` (re-create — `app/models/grading.py`)

Mirrors `phase_0c_target_ddl.md` §6. This class was deleted in S0; it is re-created here against the new shape. The DB table already has the new columns (migration 008 renamed `teacher_id` → `user_id`, retyped `class_id`, dropped the count columns).

```
Columns:
  id                       UUID PK, default uuid4
  user_id                  UUID FK → users.id, NOT NULL
  rubric_id                UUID FK → rubrics.id, NOT NULL
  rubric_contract_version  String(50), NOT NULL
  name                     String(255), nullable
  class_id                 UUID FK → classes.id, nullable
  status                   String(30), NOT NULL, default 'pending'
  started_at               DateTime(tz), nullable
  completed_at             DateTime(tz), nullable
  created_at               DateTime(tz), NOT NULL, default now
  updated_at               DateTime(tz), NOT NULL, default now

Relationships:
  user         → User        (back_populates="grading_batches")
  rubric       → Rubric      (back_populates="grading_batches")
  school_class → Class       (no back_populates required — or add classes.batches if wanted)
  graded_tests → GradedTest  (back_populates="batch", passive_deletes=True)

Notes:
  - No total_sessions / completed_sessions / failed_sessions columns. Counts are
    derived at query time (Phase 0a §2.2.C). Do NOT add them back.
  - class_id is UUID FK now, not the old VARCHAR. Type it as UUID.
  - status is String(30) — note the wider width than other status columns
    (the value 'partially_completed' is 19 chars; keep the migration's 30).
```

### 5.7 Existing model edits

**`User`** — add (all `passive_deletes=True`, all `back_populates`):
```
students        → Student
classes         → Class
transcriptions  → Transcription
graded_tests    → GradedTest
grading_batches → GradingBatch
```

**`Rubric`** — add (all `passive_deletes=True`, all `back_populates`):
```
transcriptions  → Transcription
graded_tests    → GradedTest
grading_batches → GradingBatch
```
(Note: S0 already removed the old `grading_sessions` and `grading_batches` relationships from `Rubric`. This re-adds only `grading_batches` in its new form, plus the two new ones.)

**`SubjectMatter`** — add:
```
classes → Class  (back_populates="subject_matter")
```

---

## 6. Relationship symmetry map

Every relationship has two sides. A mismatch in `back_populates` names causes a SQLAlchemy mapper-configuration error at app boot. Verify this table holds in both directions before considering the PR done.

| Parent side | Child side | back_populates pair |
|---|---|---|
| `User.students` | `Student.user` | students ↔ user |
| `User.classes` | `Class.user` | classes ↔ user |
| `User.transcriptions` | `Transcription.user` | transcriptions ↔ user |
| `User.graded_tests` | `GradedTest.user` | graded_tests ↔ user |
| `User.grading_batches` | `GradingBatch.user` | grading_batches ↔ user |
| `Rubric.transcriptions` | `Transcription.rubric` | transcriptions ↔ rubric |
| `Rubric.graded_tests` | `GradedTest.rubric` | graded_tests ↔ rubric |
| `Rubric.grading_batches` | `GradingBatch.rubric` | grading_batches ↔ rubric |
| `SubjectMatter.classes` | `Class.subject_matter` | classes ↔ subject_matter |
| `Class.memberships` | `ClassMembership.school_class` | memberships ↔ school_class |
| `Student.class_memberships` | `ClassMembership.student` | class_memberships ↔ student |
| `Student.transcriptions` | `Transcription.student` | transcriptions ↔ student |
| `Student.graded_tests` | `GradedTest.student` | graded_tests ↔ student |
| `Transcription.graded_tests` | `GradedTest.transcription` | graded_tests ↔ transcription |
| `GradingBatch.graded_tests` | `GradedTest.batch` | graded_tests ↔ batch |
| `GradedTest.regraded_from` | `GradedTest.regraded_to` | self-referential — see Critical Note 1 |

---

## 7. Critical implementation notes

### Critical Note 1 — the self-referential revision chain

`GradedTest.regraded_from_id` and `regraded_to_id` both FK to `graded_tests.id`. This is a one-to-one self-reference forming a doubly-linked list. SQLAlchemy needs `remote_side` to disambiguate direction. The pattern:

```python
regraded_from = relationship(
    "GradedTest",
    foreign_keys=[regraded_from_id],
    remote_side=[id],
    back_populates="regraded_to",
    uselist=False,
)
regraded_to = relationship(
    "GradedTest",
    foreign_keys=[regraded_to_id],
    remote_side=[regraded_from_id],
    back_populates="regraded_from",
    uselist=False,
)
```

Get `remote_side` and `foreign_keys` right or SQLAlchemy raises at mapper configuration. Add a focused test (see §8) that creates a two-row chain and traverses it in both directions.

### Critical Note 2 — `passive_deletes=True` everywhere

Migration 008 defined every ON DELETE rule at the DB level (CASCADE for ownership, SET NULL for associations — see `phase_0d_erd.md` §7 for the full FK list). The ORM must NOT try to emulate these in the Python session. Set `passive_deletes=True` on every collection relationship so SQLAlchemy defers to the DB's ON DELETE rules rather than loading children and nulling/deleting them in Python. Without this, you get double-handling: SQLAlchemy issues redundant UPDATEs/DELETEs and can conflict with the DB constraints.

The DB owns cascade behavior. The ORM respects it.

### Critical Note 3 — do not re-declare DB constraints in the ORM

The CHECK constraints (`transcriptions_approval_consistency`, `graded_tests_status_consistency`, `grading_batches_status_check`) and the partial unique index (`idx_graded_tests_one_leaf_per_chain`) are owned by the DB. The ORM models should NOT redeclare them via `CheckConstraint(...)` or `Index(...)` in `__table_args__`. Reasons: (a) they already exist in the DB, (b) re-declaring risks drift if the wording differs, (c) the ORM isn't the source of truth for these.

The ORM SHOULD declare the simple `UniqueConstraint`s (`students_unique_name_per_user`, `classes_unique_name_per_user`) and the composite `PrimaryKeyConstraint` on `class_memberships` — these are structural and harmless to mirror. The line: mirror keys and unique constraints; do not mirror CHECK constraints or partial indexes.

### Critical Note 4 — JSONB columns are raw

`draft_json` and `contract_json` map to `sqlalchemy.dialects.postgresql.JSONB` with no further typing. No `TypeDecorator`, no Pydantic coercion, no default `{}`. The application code in later sprints serializes Pydantic models into these columns explicitly via `.model_dump()`. Keeping them raw here avoids coupling the model layer to schemas that don't exist yet.

### Critical Note 5 — status columns are `String`, not `Enum`

Every `status` column is a plain `String` whose valid values are enforced by a DB CHECK constraint. Do not use SQLAlchemy's `Enum` type — it would create a Postgres ENUM type that doesn't match the migration's VARCHAR+CHECK approach, causing a schema mismatch.

### Critical Note 6 — `Numeric` maps to `Decimal`

`total_score`, `total_possible`, `percentage` are `NUMERIC` in the DB. Map them to SQLAlchemy `Numeric` (which yields Python `Decimal`), not `Float`. The grading domain uses `Decimal` throughout for point precision; mixing in `float` here would reintroduce floating-point error at the persistence boundary.

---

## 8. Testing requirements

Tests go in `tests/models/`. The DB is empty pre-launch, so these run against a real (test) database — they verify the ORM matches the migrated schema.

### Required tests
1. **App boots.** `import app.main` succeeds — proves the mapper configuration is valid (catches `back_populates` mismatches and self-referential FK errors). This is the single most important test; a mapper misconfiguration fails here.
2. **Each model round-trips.** For each of the six models, create an instance with valid FKs, commit, re-fetch, assert fields match. (Requires creating a `User` and `Rubric` fixture first.)
3. **Relationships traverse.** Given a `User` with a `Student`, a `Transcription`, and a `GradedTest`, assert `user.students`, `user.transcriptions`, `user.graded_tests` return them, and the reverse (`student.user`, etc.) resolves.
4. **Revision chain traverses both directions.** Create two `GradedTest` rows, set `R1.regraded_to_id = R2.id` and `R2.regraded_from_id = R1.id`, commit, then assert `R1.regraded_to is R2` and `R2.regraded_from is R1`.
5. **M:N via association object.** Create a `Student` and `Class`, add a `ClassMembership`, assert `class.memberships[0].student is student` and `student.class_memberships[0].school_class is class`.
6. **Unique constraints fire.** Inserting two `Student`s with the same `(user_id, full_name)` raises `IntegrityError`. Same for `Class` `(user_id, name)`.
7. **CHECK constraint fires (DB-level).** Inserting a `Transcription` with `status='approved'` but `contract_json=NULL` raises `IntegrityError` — verifies the migration's CHECK is active and the ORM doesn't bypass it.
8. **Partial unique index fires.** Inserting two `GradedTest` rows for the same `(transcription_id, rubric_id)` both with `regraded_to_id=NULL` raises `IntegrityError` — verifies RGC-1's enforcement.

Tests 7 and 8 are the most valuable: they prove the DB-level invariants (which the ORM deliberately doesn't mirror) are live and that the ORM writes flow through them.

---

## 9. Acceptance criteria

- [ ] `import app.main` succeeds (mapper configuration valid).
- [ ] All six models exist with columns matching migration 008 exactly (verify against live DB schema, not just this doc).
- [ ] Every relationship in §6 traverses in both directions.
- [ ] The self-referential revision chain traverses both directions (test 4).
- [ ] `passive_deletes=True` on every collection relationship.
- [ ] No CHECK constraints or partial indexes redeclared in the ORM.
- [ ] JSONB columns are raw `JSONB`, no Pydantic / TypeDecorator.
- [ ] Status columns are `String`, not `Enum`.
- [ ] Numeric columns map to `Decimal`.
- [ ] No `total_sessions`/`completed_sessions`/`failed_sessions` on `GradingBatch`.
- [ ] No endpoints, no Pydantic JSONB schemas, no services touched.
- [ ] `app/models/__init__.py` exports all new models.
- [ ] All eight tests in §8 pass.
- [ ] `pytest --collect-only` succeeds (no import errors in the test suite).

---

## 10. Known follow-ups (do NOT do in this PR)

- **S2** adds `Depends(get_current_user)` to endpoints and starts populating `user_id` from auth.
- **S3** adds students/classes management endpoints + frontend.
- **S4** adds `TranscriptionDraft` / `TranscriptionContract` Pydantic models and the `/transcribe` + `/grade` (transcription-contract side) endpoints.
- **S6** adds the `GradableTest` schema + compiler.
- **S8/S9** add `GradedTestDraft` / `GradedTestContract` Pydantic models and the grading + approval endpoints.

If during implementation you find the migrated DB schema disagrees with `phase_0c_target_ddl.md`, **stop and flag it** — do not silently make the ORM match one or the other. The DB and the spec must agree; if they don't, that's a defect in migration 008 that needs resolving before S1 proceeds.
