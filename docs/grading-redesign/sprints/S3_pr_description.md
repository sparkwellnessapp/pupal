# PR: S3 — Students & Classes management (endpoints + frontend)

**Sprint:** S3
**Depends on:** S1 (ORM models), S2 (auth + ownership pattern) — both merged
**Foundation refs:** `phase_0a_architecture.md` §2.2.A (Student), §2.2.B (Class), §6 (permissions), RD-1 (M:N join), RD-4 (student selection at review time); `phase_0c_target_ddl.md` §1–§3
**Frontend lockstep:** yes — this PR ships the roster management UI and the reusable student-picker component

---

## 1. Summary

S3 builds the supporting-entity layer: CRUD for students and classes, class-membership management, and the roster UI. This is the first sprint to build genuinely new product surface using the S2 auth + ownership pattern.

S3 is sequenced before S4 (transcription) deliberately: the transcription review screen assigns a `student_id` (Phase 0a RD-4), so the student roster must exist first. S3 also ships the **reusable student-picker component** (select-existing-or-create-new) that S4 will wire into the review screen — but S3 does not touch transcription or grading.

**What S3 is NOT:** it is not the "My Classroom" BI feature (longitudinal performance, analytics — that's a future roadmap item). It is the CRUD scaffolding that the BI layer will later build on. Student/class detail views in S3 show only roster data (name, notes, memberships), because transcriptions and graded tests don't exist yet.

---

## 2. Scope

### In scope
- **Students CRUD:** create, list, detail, update, delete (with dependency guard).
- **Classes CRUD:** create, list, detail, update, delete (with dependency guard).
- **Class membership management:** add/remove students to/from a class (the canonical editing direction).
- **Subject-matter listing:** an endpoint to populate the class subject dropdown (if one doesn't already exist).
- **Frontend `/my-classroom` page** with internal tabs (Students | Classes), slotted into the sidebar between "My Rubrics" and "Graded Tests" using the `GraduationCap` icon.
- **Reusable `StudentPicker` component** (select-existing-or-create-new) — built and unit-usable in S3, wired into the transcription review screen in S4.
- Tests: endpoint auth/ownership tests (copying the S2 pattern), CRUD happy paths, the uniqueness-conflict (409) path, the delete dependency-guard (409) path.

### Out of scope (explicitly deferred)
- **Anything touching transcriptions or graded_tests.** Those endpoints don't exist yet (S4/S8). The delete dependency-guard (§4.3) is written forward-looking but has nothing to guard against in S3 — verify it returns the right error shape via a unit test that mocks a dependent, not an integration test.
- **The "My Classroom" BI / analytics layer.** Student detail shows roster data only.
- **Bidirectional membership editing.** S3 ships one canonical direction (edit a class → manage its students). The student detail view shows class memberships **read-only**. Editing memberships from the student side is a future enhancement.
- **Wiring the StudentPicker into the transcription review screen.** That's S4. S3 ships the component standalone.
- **Soft-delete / archive.** Phase 0a §11.7 deferred it. S3 uses hard delete, guarded.

---

## 3. Backend — endpoints

All endpoints require `Depends(get_current_user)` (S2 pattern). All reads are scoped by `user_id == current_user.id`. All detail/update/delete use `get_owned_or_404` (from `app/api/deps.py`). The owning `user_id` on every write is `current_user.id`, never from the request body (S2 §3.2).

Place these in a new router file `app/api/v0/classroom.py` (mounted under an appropriate prefix, e.g. `/api/v0/classroom` — match the existing router-mounting convention in `app/main.py` or wherever routers are registered).

### 3.1 Students

| Method + path | Handler | Request | Response | Notes |
|---|---|---|---|---|
| `POST /students` | `create_student` | `{ full_name, notes? }` | `StudentResponse` | `user_id` from token. 409 on duplicate `(user_id, full_name)`. |
| `GET /students` | `list_students` | — | `{ students: StudentResponse[] }` | Scoped to current user. Optionally `?class_id=` filter (see §3.3). |
| `GET /students/{id}` | `get_student` | — | `StudentDetailResponse` | `get_owned_or_404`. Detail includes class memberships (read-only list). |
| `PATCH /students/{id}` | `update_student` | `{ full_name?, notes? }` | `StudentResponse` | `get_owned_or_404`. 409 on rename collision. |
| `DELETE /students/{id}` | `delete_student` | — | `204` | `get_owned_or_404`. Dependency guard (§4.3): 409 if the student has graded_tests. |

### 3.2 Classes

| Method + path | Handler | Request | Response | Notes |
|---|---|---|---|---|
| `POST /classes` | `create_class` | `{ name, subject_matter_id?, school_year? }` | `ClassResponse` | `user_id` from token. 409 on duplicate `(user_id, name)`. |
| `GET /classes` | `list_classes` | — | `{ classes: ClassResponse[] }` | Scoped to current user. Each includes a student count (derived). |
| `GET /classes/{id}` | `get_class` | — | `ClassDetailResponse` | `get_owned_or_404`. Detail includes the member students. |
| `PATCH /classes/{id}` | `update_class` | `{ name?, subject_matter_id?, school_year? }` | `ClassResponse` | `get_owned_or_404`. 409 on rename collision. |
| `DELETE /classes/{id}` | `delete_class` | — | `204` | `get_owned_or_404`. Dependency guard (§4.3): 409 if the class has dependent grading_batches. |

### 3.3 Class membership

| Method + path | Handler | Request | Response | Notes |
|---|---|---|---|---|
| `POST /classes/{id}/students` | `add_student_to_class` | `{ student_id }` | `204` | `get_owned_or_404` on BOTH the class and the student (both must belong to current user). Idempotent: adding an already-member student is a no-op 204, not a 409. |
| `DELETE /classes/{id}/students/{student_id}` | `remove_student_from_class` | — | `204` | `get_owned_or_404` on both. Removing a non-member is a no-op 204. |

The `GET /students?class_id=` filter (§3.1) is the read side: "list students in this class." Implemented as a join through `class_memberships`.

### 3.4 Subject matters

| Method + path | Handler | Request | Response | Notes |
|---|---|---|---|---|
| `GET /subject_matters` | `list_subject_matters` | — | `{ subject_matters: [{ id, code, name_he, name_en }] }` | NOT user-scoped — `subject_matters` is a global reference table (migration 001). Still requires auth (any logged-in teacher can read it), but no `user_id` filter. |

**Check first:** an endpoint listing subject matters may already exist (the rubric flow uses subjects). If it does, reuse it — don't duplicate. If not, add this one.

---

## 4. Backend — critical implementation notes

### Note 1 — `user_id` from token, ownership scoping (S2 pattern)
Every write sets `user_id = current_user.id`. Every read filters by it. Every detail/update/delete goes through `get_owned_or_404`. Cross-user access returns 404. This is the established S2 pattern — copy the rubric endpoints as the reference implementation. Do not reinvent.

### Note 2 — translate `IntegrityError` to 409, not 500
The DB enforces `students_unique_name_per_user` and `classes_unique_name_per_user` (migration 008). A duplicate-name write raises `sqlalchemy.exc.IntegrityError`. Catch it and return **409 Conflict** with a clear Hebrew message, e.g.:
- Student: `"כבר קיים תלמיד בשם זה"` ("A student with this name already exists")
- Class: `"כבר קיימת כיתה בשם זה"` ("A class with this name already exists")

Do not let the `IntegrityError` propagate to a 500. Catch it at the endpoint (or in a shared handler) and map to 409. Be careful to roll back the session after the IntegrityError before returning.

### Note 3 — membership endpoints check ownership of BOTH entities
`POST /classes/{id}/students` must verify that BOTH the class AND the student belong to `current_user`. A teacher must not be able to add another teacher's student to their class, nor add their student to another teacher's class. Use `get_owned_or_404` on each. This is the cross-tenant isolation guarantee applied to the M:N relationship.

### Note 4 — the delete dependency guard
Per Q1 decision: **block deletion of students/classes that have dependent graded_tests (or grading_batches), return 409 with a clear message.**

- `DELETE /students/{id}`: before deleting, check whether any `graded_tests` row references this `student_id`. If yes → 409, message e.g. `"לא ניתן למחוק תלמיד עם מבחנים בדוקים"` ("Cannot delete a student with graded tests"). If no → hard delete (cascade removes class_memberships automatically).
- `DELETE /classes/{id}`: before deleting, check whether any `grading_batches` row references this `class_id`. If yes → 409, message e.g. `"לא ניתן למחוק כיתה עם בדיקות מבחנים"` ("Cannot delete a class with grading batches"). If no → hard delete (cascade removes class_memberships).

**Important sequencing reality:** in S3, `graded_tests` and `grading_batches` are empty (no grading endpoints exist yet). So the guard will never fire against real data during S3. Build it anyway (the endpoint outlives S3), but test it by inserting a dependent row directly in the test DB (a `graded_tests` or `grading_batches` row with valid FKs) and asserting the 409 — not by going through a grading flow that doesn't exist.

The check is a `SELECT EXISTS(...)` against the dependent table, not a reliance on the DB's CASCADE (CASCADE would happily delete the dependents, which is exactly what we're preventing). The guard is application-level; the DB CASCADE is the fallback for when a teacher account is deleted wholesale.

### Note 5 — `class_memberships` is an association object
S1 created `ClassMembership` as a full model (it carries `created_at`), not a bare `secondary=` table. Membership writes create/delete `ClassMembership` rows. The `created_at` is set on insert (the BI roadmap wants "when did the student join this class"). Don't bypass the model with raw association-table inserts.

### Note 6 — student count on class list (derived, not stored)
`GET /classes` returns each class with a student count. Compute it via a join/subquery (`COUNT` over `class_memberships`), not a stored column. Consistent with the "derive, don't store counts" principle from the batch redesign (Phase 0a §2.2.C).

---

## 5. Backend — Pydantic response schemas

New schemas in `app/schemas/classroom.py` (or wherever response schemas live). Keep them thin — these are API response shapes, distinct from the ORM models.

```
StudentResponse:
  id, full_name, notes, created_at

StudentDetailResponse (extends StudentResponse):
  classes: [{ id, name }]        # read-only membership list

ClassResponse:
  id, name, subject_matter_id, subject_matter_name?, school_year, student_count, created_at

ClassDetailResponse (extends ClassResponse):
  students: [{ id, full_name }]  # the member students

SubjectMatterResponse:
  id, code, name_he, name_en
```

These do NOT include `user_id` in the response — ownership is implicit (the caller is always the owner; they can't fetch anyone else's). Including `user_id` would be redundant and slightly leaky.

---

## 6. Frontend — the roster UI

Per the nav analysis: add a single `/my-classroom` route, slotted into the sidebar between "My Rubrics" (`/my-rubrics`) and "Graded Tests" (`/my-graded-tests`), using the already-imported-but-unused `GraduationCap` icon. Hebrew label: `כיתות שלי` ("My Classroom").

### 6.1 Nav integration
- Add the nav item to `navItems` in `SidebarLayout.tsx` (between index 1 and 2 — after My Rubrics, before Graded Tests).
- Use the `GraduationCap` lucide icon (already imported at `SidebarLayout.tsx:10`, currently unused).
- Route: `/my-classroom`.

### 6.2 The `/my-classroom` page — internal tabs
A single page with two tabs:
- **Tab 1 — Students** (`תלמידים`): a list of the teacher's students, a "create student" action, and per-row edit/delete.
- **Tab 2 — Classes** (`כיתות`): a list of the teacher's classes (with student counts), a "create class" action, and per-row edit/delete/manage-students.

RTL Hebrew UI, consistent with the existing sidebar/pages.

### 6.3 Student management (Tab 1)
- **List:** student name, notes preview, the classes they belong to (chips/badges).
- **Create:** a form/modal with `full_name` (required) and `notes` (optional). On 409, show the duplicate-name message inline.
- **Edit:** same form, prefilled. PATCH on save.
- **Delete:** confirmation dialog. On 409 (has graded tests), show the block message — don't present delete as succeeding.

### 6.4 Class management (Tab 2)
- **List:** class name, subject (resolved name, not id), school year, student count.
- **Create:** form/modal with `name` (required), `subject_matter_id` (dropdown populated from `GET /subject_matters`, optional), `school_year` (optional free text). On 409, show duplicate-name message.
- **Edit:** same form, prefilled.
- **Delete:** confirmation dialog. On 409 (has grading batches), show the block message.
- **Manage students:** from a class row/detail, open a "manage students" view — add students (from the teacher's roster, via the StudentPicker or a multi-select) and remove current members. This is the canonical membership-editing direction.

### 6.5 The reusable `StudentPicker` component
Build a standalone, reusable component: **select an existing student or create a new one inline.**

- Props: roughly `{ value: studentId | null, onChange: (studentId) => void }` plus whatever's idiomatic in the codebase.
- Behavior: a combobox/dropdown listing the teacher's students (from `GET /students`), with a search filter, and a "create new student" affordance that calls `POST /students` inline and selects the newly created student.
- This component is **built and usable in S3** (it can be exercised within the classroom page's "manage students" flow, or at minimum unit-tested / storybook-able), but its wiring into the transcription review screen is **S4's job**. Build it to be drop-in reusable: no dependencies on transcription state.

Keep the component free of transcription/grading concerns. It talks only to the student endpoints. That's what makes it reusable in S4 without modification.

### 6.6 API client methods
Add to `frontend/src/lib/api.ts` (with `...getAuthHeaders()` on every call, per S2):
- `listStudents(classId?)`, `getStudent(id)`, `createStudent(body)`, `updateStudent(id, body)`, `deleteStudent(id)`
- `listClasses()`, `getClass(id)`, `createClass(body)`, `updateClass(id, body)`, `deleteClass(id)`
- `addStudentToClass(classId, studentId)`, `removeStudentFromClass(classId, studentId)`
- `listSubjectMatters()` (if not already present)

TypeScript types mirroring the §5 response schemas go in the appropriate types file (e.g. `frontend/src/types/classroom.ts`).

---

## 7. Testing requirements

Backend tests in `tests/api/` (copy the S2 two-user fixture harness). Frontend per the existing testing convention.

### Backend — required tests
1. **Auth required.** Each endpoint returns 401 without a token. (Smoke-level — one per resource is fine.)
2. **Create + read round-trip.** Create a student / class, fetch it back, fields match. `user_id` is the token's user.
3. **Cross-tenant isolation.** User A cannot read/update/delete user B's student or class (404). User A's list returns only A's resources.
4. **Uniqueness conflict → 409.** Creating a second student with the same `full_name` (same user) returns 409, not 500. Same for class name. Session is properly rolled back (a subsequent valid create in the same session works).
5. **Membership — both-ownership check.** User A cannot add user B's student to A's class (404). User A cannot add A's student to user B's class (404).
6. **Membership idempotency.** Adding an already-member student returns 204 (no-op), not 409. Removing a non-member returns 204.
7. **Delete dependency guard → 409.** Insert a `graded_tests` row referencing a student (directly in the test DB, with valid FKs — grading endpoints don't exist yet), then `DELETE /students/{id}` returns 409. Same for a class with a `grading_batches` row.
8. **Delete happy path.** Deleting a student with no dependents returns 204; their `class_memberships` are gone (cascade); the student is no longer fetchable.

Tests 3 and 5 are the cross-tenant security tests — the S3 equivalents of S2's tests 4/5/6. Treat them as the security bar.

### Frontend — required
- The `/my-classroom` page renders both tabs, lists resources, and the create/edit/delete flows call the right endpoints with auth headers.
- The `StudentPicker` lists existing students and can create a new one inline (this is the component S4 depends on — verify it works standalone).
- 409 responses surface as inline user-facing messages, not silent failures or generic errors.

---

## 8. Acceptance criteria

- [ ] All student + class CRUD endpoints exist, require auth, scope by `user_id`, use `get_owned_or_404`.
- [ ] `user_id` is sourced from the token on every write, never from request body.
- [ ] Duplicate-name writes return 409 with a clear Hebrew message (not 500); session rolls back cleanly.
- [ ] Membership add/remove checks ownership of both class and student; idempotent.
- [ ] Delete dependency guard: 409 when a student has graded_tests or a class has grading_batches; hard delete otherwise.
- [ ] `GET /subject_matters` exists (or the existing one is reused) and is auth-gated but not user-scoped.
- [ ] `/my-classroom` nav item added between My Rubrics and Graded Tests, using `GraduationCap` icon.
- [ ] `/my-classroom` page with Students and Classes tabs; full CRUD; subject dropdown populated; RTL Hebrew.
- [ ] `StudentPicker` component built, standalone-reusable, talks only to student endpoints (no transcription coupling).
- [ ] All API client methods attach auth headers.
- [ ] All backend tests pass; tests 3 and 5 (cross-tenant isolation) explicitly verified.
- [ ] Frontend 409s surface as inline messages.
- [ ] `import app.main` succeeds; `pytest --collect-only` succeeds; frontend type-checks.

---

## 9. Known follow-ups (do NOT do in this PR)

- **S4** wires the `StudentPicker` into the transcription review screen and builds `/transcribe` + `/grade` (transcription-contract side). The picker built here drops in unmodified.
- **The "My Classroom" BI feature** (longitudinal student performance, class analytics) builds on these CRUD endpoints later. S3's student/class detail views show roster data only; the analytics layer comes when graded tests exist to analyze.
- **Bidirectional membership editing** (manage a student's classes from the student side) — future enhancement. S3 ships class-side editing + student-side read-only.
- **Soft-delete / archive** — deferred per Phase 0a §11.7. If the block-on-dependents guard proves too restrictive once real grading data exists, archive is the escape hatch, added then.

If during implementation the existing nav or page conventions make a different placement or structure cleaner than what §6 specifies, **flag it** rather than forcing the spec — the §6 layout is the intended shape, but the codebase's established patterns win if they conflict.
