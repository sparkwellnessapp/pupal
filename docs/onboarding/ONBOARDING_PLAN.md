# Vivi Onboarding — implementation plan

> Status: **IMPLEMENTED 2026-08-31.** §0–§8 are the approved plan as written before the work;
> **§9 records where the implementation diverged from it and why** — read §9 alongside any
> section it amends. Written after a codebase pass; every "already exists" claim below was
> verified in the working tree on 2026-08-31.
> Owner decisions are recorded in §0 and are the spec. Deviating from one is an open decision,
> not an edit (CLAUDE.md §0.2, §0.3).

---

## 0. Owner rulings (the spec)

| # | Decision | Ruling |
|---|---|---|
| D1 | Where the Israeli high-school list lives | **Frontend data module, dynamic-imported.** Client-side trie prefix search. A pick commits by NAME through the existing normalized-exact create-or-pick. No school-directory seed migration, no search endpoint. |
| D2 | One school or many | **Many.** New `user_schools` junction. |
| D3 | PR-G6 override-attribution key under multi-school | **`users.school_id` stays the attribution key**, set to the teacher's FIRST school. The junction is the full truth; the column is the key. `override_attribution.py` is UNCHANGED. |
| D4 | Gender | **Store it; do not re-gender the app.** New nullable `users.gender`. Used by onboarding + future greetings only. The ~54 existing Hebrew surfaces keep their feminine copy this PR. |
| D5 | Onboarding completion | **DB column `users.onboarding_completed_at`** + a dedicated `/onboarding` route. |
| D6 | Subject options | **Only the three supported subjects** (english / mathematics / computer_science), resolved to real `subject_matters` rows. |
| D7 | Required vs skippable | **Steps 2 and 4 required. Step 3 (schools) is the only skippable one.** |
| D8 | Writing `full_name` | **New `PATCH /api/v0/users/me/profile`** `{full_name?, gender?}`. NOT mounted at `/users/me`. |

**Assumption stated, not decided (flag if wrong):** D7 says step 4 is required. Step 4 collects
name *and* gender, so both are required to advance — which is only fair because the gender
control carries a third option, «מעדיפ/ה לא לציין», that any teacher can answer honestly. If you
want gender optional while the name is required, that is a one-line change to the step's
`canAdvance` predicate.

---

## 1. What already exists (do not rebuild it)

| Thing | Where | Note |
|---|---|---|
| `schools` table + normalized-exact unique index | `backend/migrations/018_schools.sql` | `lower(regexp_replace(btrim(name),'\s+',' ','g'))` |
| `users.school_id` nullable FK | migration 018 | PR-G6's fifth attribution key |
| `School` model | `backend/app/models/school.py` | thin by design |
| `normalize_school_name()` | `backend/app/services/override_attribution.py` | mirrors the SQL index exactly |
| `PATCH /api/v0/users/me/school` | `backend/app/api/v0/users.py` | create-or-pick by name, IntegrityError → re-read |
| `subject_matters` table + 16-row seed | `backend/migrations/001_add_users_and_raw_tables.sql` | includes all three we need |
| `GET /users/subject-matters`, `GET|PUT /users/me/subject-matters` | `users.py` | PUT replaces the whole set |
| `GET /auth/me` + `build_user_response` | `backend/app/api/v0/auth.py` | THE profile shape; `users.py`'s duplicate was deleted 2026-08-17 |
| `Modal` dialog primitive (focus trap, Esc, `data-autofocus`) | `frontend/src/components/batch/Modal.tsx` | the onboarding shell must NOT hand-roll a fourth dialog |
| Combobox pattern (filter + outside-click + create-inline) | `frontend/src/components/StudentPicker.tsx` | the shape `SchoolCombobox` follows |
| `apiFetch` / `jsonInit` seam | `frontend/src/lib/api.ts` | every new call goes through it |
| Copy module + executable gate | `frontend/src/copy/batch.ts`, `frontend/scripts/check-copy.mjs` | onboarding joins the BLOCKING surfaces |
| Turquoise ramp | `frontend/tailwind.config.ts` → `primary.*` (500 = `#14b8a6`) | the progress bar's color; no new token needed |

**Does not exist anywhere:** a gender column; any endpoint that writes `full_name` (the profile
page's save button is a stub that does nothing); any onboarding marker; any
`updateMySubjectMatters` client function; any `user_schools` table.

---

## 2. Backend

### 2.1 Migration `022_onboarding_profile.sql`

Idempotent throughout (§8 convention: re-running the whole file is always the answer).
Commit token LAST.

```sql
-- 022: onboarding — gender, completion stamp, and the multi-school junction.
--
-- users.school_id (018) REMAINS the PR-G6 override-attribution key and is set to
-- the teacher's FIRST school. user_schools is the full truth; the column is the
-- key. This is a denormalization, deliberately, like graded_tests.total_score:
-- one concept, two granularities, with the write path (PUT /users/me/schools) as
-- the single place that keeps them in agreement.

ALTER TABLE public.users
    ADD COLUMN IF NOT EXISTS gender TEXT,
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

DO $BODY$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'users_gender_valid') THEN
        ALTER TABLE public.users
            ADD CONSTRAINT users_gender_valid
            CHECK (gender IS NULL OR gender IN ('female','male','unspecified'));
    END IF;
END
$BODY$;

CREATE TABLE IF NOT EXISTS public.user_schools (
    user_id    UUID NOT NULL REFERENCES public.users(id)   ON DELETE CASCADE,
    school_id  UUID NOT NULL REFERENCES public.schools(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, school_id)
);

CREATE INDEX IF NOT EXISTS idx_user_schools_school_id ON public.user_schools (school_id);

-- Backfill: every teacher who already answered the one-field 018 prompt keeps her
-- answer as a junction row, so the two surfaces never disagree at cutover.
INSERT INTO public.user_schools (user_id, school_id)
SELECT id, school_id FROM public.users WHERE school_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Commit token LAST: this row lands only if every statement above landed.
INSERT INTO public.schema_migrations (version, note)
VALUES ('022', 'users.gender + users.onboarding_completed_at + user_schools junction — onboarding')
ON CONFLICT DO NOTHING;
```

`backend/app/database.py` → `EXPECTED_MIGRATIONS` gains `"022"`. Without it the boot check logs
`SCHEMA MISMATCH` forever (§8, rule 2).

`gender` is `TEXT` + CHECK, **not** a PG enum: `subscription_status` is this codebase's one enum
and it is declared `create_type=False`, i.e. the DDL owns it. A CHECK is idempotent, visible in
`\d`, and widens with an `ALTER`. `'unspecified'` is a **stored value, not `NULL`** — «מעדיפ/ה לא
לציין» is an *answer*, and conflating it with "never asked" would make
`onboarding_completed_at IS NOT NULL AND gender IS NULL` unreadable.

### 2.2 Models

`app/models/school.py`:

```python
user_schools = Table(
    'user_schools', Base.metadata,
    Column('user_id',    UUID(as_uuid=True), ForeignKey('users.id',   ondelete='CASCADE'), primary_key=True),
    Column('school_id',  UUID(as_uuid=True), ForeignKey('schools.id', ondelete='CASCADE'), primary_key=True),
    Column('created_at', DateTime, default=datetime.utcnow, nullable=False),
)

# on School:
teachers = relationship("User", secondary=user_schools, back_populates="schools")
```

`app/models/user.py` — add `gender`, `onboarding_completed_at`, and
`schools = relationship("School", secondary="user_schools", back_populates="teachers", passive_deletes=True)`.

`School.users` (the existing `school_id` back_populates) and `School.teachers` (the junction) are
two different relationships over two different columns. Keep both names distinct — a shared name
is a mapper misconfiguration that fails at `import app.main`.

> ⚠️ `auth_service.get_user_by_id` and `get_user_by_email` eager-load `User.subject_matters` only.
> **Add `selectinload(User.schools)` to both**, or `/auth/me` raises `MissingGreenlet` the moment
> `build_user_response` touches the new collection — an async lazy load, the same class of failure
> that 500'd `/auth/login` for 271 users in the timestamp incident.

### 2.3 Service — one create-or-pick, one place

The create-or-pick block currently sits inline inside `update_me`. Two callers now need it
(`PATCH /me/school`, `PUT /me/schools`), so extract it **before** adding the second caller:

`app/services/school_resolution.py`

```python
async def resolve_or_create_school(db, name: str, city: str | None) -> School:
    """Normalized-exact (never fuzzy) create-or-pick, mirroring migration 018's
    unique index. On IntegrityError — a concurrent create of the same normalized
    name — re-read and use the winner: a race must not fail a teacher's onboarding."""
```

`update_me` is refactored to call it. Behavior byte-identical; **its existing tests must stay
green untouched — that is the proof the extraction was faithful.**

### 2.4 Endpoints

All in `users.py`, all `Depends(get_current_user)`, owner always `current_user.id`, never a body
or query parameter (§9).

**`PATCH /api/v0/users/me/profile` → `UserResponse`**

```python
class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    gender: Optional[Literal['female', 'male', 'unspecified']] = None
```

Both optional; sending neither is a no-op, not an error. `full_name` is `.strip()`ed and rejected
422 if it strips empty (the column is NOT NULL). Returns the full profile through
`build_user_response` imported from `auth.py` — one profile shape, never re-hand-built (the
`AnnotationSchema` mirror lesson, §6).

Path note: **not** `PATCH /users/me`. Mounting any method there turns `GET /api/v0/users/me` from
404 into 405 and fires `test_duplicate_users_me_is_gone`, the guard left by the auth incident.
`/me/profile` follows its two existing siblings.

**`PUT /api/v0/users/me/schools` → `List[SchoolResponse]`**

```python
class SchoolInput(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    city: Optional[str] = None

class UpdateSchoolsRequest(BaseModel):
    schools: List[SchoolInput] = Field(default_factory=list, max_length=20)
```

Semantics — **full replacement**, like `PUT /me/subject-matters` beside it. (No merge semantics
exist anywhere in this codebase; `review_json` set that precedent explicitly.)

1. `resolve_or_create_school` each entry, in order, de-duplicating by normalized name.
2. `current_user.schools = [...]` — SQLAlchemy diffs the junction.
3. **The D3 rule, in exactly one place:** `current_user.school_id = resolved[0].id if resolved else None`.
   First in the submitted list is the primary. A teacher who reorders her list moves the
   attribution key; that is intended, and is the only way a single-column key can follow a
   multi-valued answer.
4. One commit.

**`POST /api/v0/users/me/onboarding/complete` → `UserResponse`**

Stamps `onboarding_completed_at = datetime.utcnow()` **only if currently NULL** — idempotent, so a
double-click, a retry, or a re-entry never re-stamps and never 409s. Deliberately a POST rather
than a PATCH with a boolean: the client does not get to *unset* it.

`GET /api/v0/users/me/schools` is **not** built — nothing needs it; `/auth/me` carries the list.

### 2.5 Wire shape

`schemas/user.py`:

```python
class SchoolResponse(BaseModel):
    id: UUID
    name: str
    city: Optional[str] = None

class UserResponse(BaseModel):
    ...                                          # unchanged fields
    gender: Optional[str] = None
    onboarding_completed_at: Optional[datetime] = None
    schools: List[SchoolResponse] = Field(default_factory=list)
    primary_school_id: Optional[UUID] = None     # == users.school_id, the PR-G6 key, named for what it is
```

`build_user_response` populates all four. This changes the `/auth/me`, `/login` and `/signup`
payloads → **`npm run gen:api` is mandatory**, or the api-types drift CI job fails (§10 codegen).

---

## 3. Frontend

### 3.1 File map (new unless marked)

```
src/data/israeli-schools.ts                      ← D1. THE MenuTrie payload. Drop your file here.
src/utils/school-search.ts                       ← pure prefix search over it (+ .test.ts)
src/copy/onboarding.ts                           ← every Hebrew string in the flow
src/lib/onboarding.ts                            ← step list, ids, canAdvance predicates (pure)
src/components/onboarding/OnboardingDialog.tsx   ← shell: logo + progress + body + footer
src/components/onboarding/ProgressBar.tsx
src/components/onboarding/steps/WelcomeStep.tsx
src/components/onboarding/steps/SubjectsStep.tsx
src/components/onboarding/steps/SchoolsStep.tsx
src/components/onboarding/steps/IdentityStep.tsx
src/components/onboarding/steps/ReadyStep.tsx
src/components/onboarding/SchoolCombobox.tsx
src/components/OnboardingGate.tsx                ← the redirect gate, mounted in the root layout
src/app/onboarding/page.tsx                      ← the route
                                                 — modified —
src/components/batch/Modal.tsx                   ← + `dismissible` and `size` props (defaults preserve callers)
src/lib/api.ts                                   ← 4 new functions
src/lib/auth.tsx                                 ← User interface + the new fields
src/app/layout.tsx                               ← mount <OnboardingGate /> inside <AuthProvider>
src/lib/api-types.ts                             ← REGENERATED, never hand-edited
scripts/check-copy.mjs                           ← onboarding joins BLOCKING_SURFACES
```

### 3.2 The school data (D1) — placement and shape

**Put your file at `frontend/src/data/israeli-schools.ts`**, exporting exactly the shape you
described:

```ts
export type School = { id: string; name: string; city: string; label: string };
export const schools: School[] = [ /* … */ ];
```

Three rules make this safe:

1. **It is never imported statically.** `SchoolsStep` loads it on mount with
   `const { schools } = await import('@/data/israeli-schools')`. A ~2k-entry list is a few hundred
   KB of JS; a static import puts it in the shared first-load chunk of every route. A dynamic
   import keeps it off every page except the one that asks. Show «טוען רשימת בתי ספר…» while it
   resolves.
2. **`id` and `label` are display-only.** The `id` in your file is *not* a `schools.id` UUID and
   must never be sent as one. The commit is by NAME (`PUT /me/schools` → `resolve_or_create_school`),
   so two teachers picking the same row converge on one DB row through the 018 normalized index.
   That property is exactly why D1 needs no seed migration.
3. **Search is a pure function, tested separately.** `school-search.ts` exports
   `searchSchools(index, query, limit)`. If your payload is already a trie it walks it; if it is
   the flat array above, the module builds the index once (memoized at module scope) over `name`
   and `city`, so «רמת גן» finds Blich by city as well as by name. Either way the component imports
   one function and knows nothing about the structure — swapping the payload format later touches
   one file. Match normalization: trim, collapse whitespace, strip Hebrew niqqud and the
   geresh/gershayim variants (`׳ ״ ' "`), case-fold. Conservative normalized-prefix, **never fuzzy**
   — same discipline as `normalize_school_name`.

Free text is allowed: a teacher whose school is missing types it and gets an explicit
«הוסיפי את «X» כפי שכתבת» affordance. It commits by name like any other pick.

### 3.3 The gate (D5)

`OnboardingGate` is a client component mounted once in `app/layout.tsx` inside `<AuthProvider>`.
It renders nothing.

```
if (isLoading) return null                       // never redirect on an unresolved session
if (!isAuthenticated) return null                // SidebarLayout already owns the /login redirect
if (user.onboarding_completed_at) return null
if (PUBLIC_PATHS.has(pathname)) return null      // /login, /signup, /onboarding itself
router.replace('/onboarding')
```

`replace`, not `push` — onboarding must not sit in the back stack. A completed user who navigates
to `/onboarding` directly is `replace`d to `/`.

`/onboarding` renders the dialog over a dimmed Vivi background (the signup page's gradient orbs,
reused) — **not** over the live app. Nothing loads behind a wall the teacher cannot reach.

> **Blast radius, said out loud:** all 273 existing users have `onboarding_completed_at = NULL` and
> will be walked through this flow once on their next login. See §7.4 for the exemption backfill if
> that is not wanted.

### 3.4 The dialog shell

Built on the existing `Modal` primitive (focus trap, Esc, `data-autofocus`) with two deviations
passed as props, because onboarding is a *wall*, not a dismissible dialog:

- `dismissible={false}` — no backdrop click-to-close, no Esc close, no X.
- `size="lg"` — `max-w-2xl` instead of `max-w-md`.

Both are added to `Modal` with the current behavior as the default, so all three existing callers
are untouched. Extending the one primitive is the point; a fourth hand-rolled dialog is what
F8/R9 exists to prevent.

Layout, top to bottom, **fixed across all five steps** so nothing jumps:

```
┌────────────────────────────────────────────┐
│               [ Vivi logo ]                │  h-12, /vivi-logo-no-background-no-slogan.png
│  ████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░  │  the progress bar
│                                            │
│  <step title>                              │  text-2xl font-semibold
│  <step subtitle>                           │  text-sm text-gray-500
│                                            │
│  <step body>                               │  min-h-[18rem] — the reserved well
│                                            │
│                     [ חזרה ]  [ הבא → ]    │  footer, always in the same place
└────────────────────────────────────────────┘
```

`min-h` on the body is load-bearing: without it the popup resizes between step 1 (prose) and
step 2 (chips), and the footer buttons move under the teacher's cursor mid-flow.

### 3.5 Progress bar

Turquoise straight from the existing ramp — no new token:

```tsx
<div className="h-1.5 w-full overflow-hidden rounded-full bg-surface-200">
  <div
    className="h-full rounded-full bg-gradient-to-l from-primary-400 to-primary-600
               transition-[width] duration-500 ease-out motion-reduce:transition-none"
    style={{ width: `${(step / TOTAL_STEPS) * 100}%` }}
    role="progressbar"
    aria-valuenow={step} aria-valuemin={0} aria-valuemax={TOTAL_STEPS}
    aria-label={PROGRESS_LABEL}
  />
</div>
```

`from-primary-400 to-primary-600` = `#2dd4bf → #0d9488`. `bg-gradient-to-l` because the document is
RTL and the bar must fill from the right. `motion-reduce:` per the standing rule that every
animation collapses under `prefers-reduced-motion`.

### 3.6 State and the commit model

One `useReducer` in `OnboardingDialog` over
`{ step, subjectIds, schools, fullName, gender, busy, error }`, seeded from `useAuth().user` so a
re-entry prefills everything already answered.

**Commit on Next, per step** — not one write at the end:

| Step | On «הבא» | Advance blocked while |
|---|---|---|
| 1 Welcome | nothing | never |
| 2 Subjects | `PUT /users/me/subject-matters` | `subjectIds.length === 0` (D7) |
| 3 Schools | `PUT /users/me/schools` (also on «דלגי», with the current — possibly empty — list) | never (D7) |
| 4 Identity | `PATCH /users/me/profile` | `!fullName.trim() \|\| !gender` (D7 + the §0 assumption) |
| 5 Ready | `POST /users/me/onboarding/complete` → `refreshUser()` → `router.replace('/')` | never |

Rationale: a teacher who closes the tab at step 4 keeps her subjects and schools. Buffering
everything and writing once loses all of it and gains nothing.

Failure handling: the button enters `busy`; on error the step **does not advance** and an inline
Hebrew banner appears (domain error) or `surfaceError` toasts (transport/auth) — the existing
error-surface convention. A 401 mid-flow is terminal and lands on `/login` through `ApiAuthError`.
**No auto-retry at the seam** — these are mutations.

«חזרה» is local navigation only; it never un-writes a committed step. Re-advancing re-sends, which
is safe because all three writes are full replacements or idempotent by construction.

### 3.7 `api.ts` additions

```ts
export async function updateMySubjectMatters(ids: number[]): Promise<SubjectMatterOption[]>
  // PUT   /api/v0/users/me/subject-matters   { subject_matter_ids: ids }
export async function setMySchools(schools: { name: string; city?: string }[]): Promise<SchoolWire[]>
  // PUT   /api/v0/users/me/schools           { schools }
export async function updateMyProfile(body: { full_name?: string; gender?: Gender }): Promise<UserWire>
  // PATCH /api/v0/users/me/profile
export async function completeOnboarding(): Promise<UserWire>
  // POST  /api/v0/users/me/onboarding/complete
```

All four through `apiFetch` + `jsonInit` — the one seam. `listSubjectMatters` already exists and is
reused to resolve the three codes to ids (D6):
`ONBOARDING_SUBJECT_CODES = ['english', 'mathematics', 'computer_science'] as const`, filtered
against the endpoint's response so a code that is ever unseeded degrades to a missing chip rather
than a crash.

`auth.tsx`'s local `User` interface gains `gender`, `onboarding_completed_at`, `schools`,
`primary_school_id`.

---

## 4. The copy (`src/copy/onboarding.ts`)

Every string in one module — the `copy/batch.ts` pattern — so the gate can see it and a copy change
is one file. Feminine address throughout, matching the app and the check-copy gate.

```ts
// ── Step 1 · welcome ──
export const WELCOME_TITLE = 'ברוכה הבאה ל‑Vivi, הפלטפורמה המובילה בישראל לבדיקת מבחנים בכתב יד';
export const WELCOME_BODY = [
  'Vivi היא העוזרת האישית שלך לבדיקה. את מעלה את המחוון ואת מבחני הכיתה — Vivi מתמללת את כתב היד, בודקת מול המחוון, ומגישה הצעת ציון עם נימוק וציטוט מדויק מתוך תשובת התלמיד.',
  'ההחלטה תמיד שלך: Vivi מציעה, את מחליטה. שום ציון לא נסגר בלי שעברת עליו.',
  'מה שנשאר לך הוא מה שחשוב באמת — ללמד.',
];
export const WELCOME_CTA = 'בואי נתחיל';

// ── Step 2 · subjects ──
export const SUBJECTS_TITLE = 'אילו מקצועות את מלמדת?';
export const SUBJECTS_SUBTITLE = 'נתאים לך את המחוונים וההמלצות למקצועות שלך.';
export const SUBJECTS_HINT = 'בחרי לפחות מקצוע אחד כדי להמשיך';

// ── Step 3 · schools ──
export const SCHOOLS_TITLE = 'באילו בתי ספר את מלמדת?';
export const SCHOOLS_SUBTITLE = 'נתאים את החוויה לבית הספר שלך. אפשר לבחור יותר מאחד.';
export const SCHOOLS_PLACEHOLDER = 'התחילי להקליד שם של בית ספר או עיר…';
export const SCHOOLS_LOADING = 'טוען רשימת בתי ספר…';
export const SCHOOLS_EMPTY = 'לא מצאנו בית ספר כזה ברשימה.';
export const SCHOOLS_ADD_FREE_TEXT = (q: string) => `הוסיפי את «${q}» כפי שכתבת`;
export const SCHOOLS_SKIP = 'דלגי לעת עתה';
export const SCHOOLS_REMOVE = (label: string) => `הסירי את ${label}`;   // aria-label

// ── Step 4 · identity ──
export const IDENTITY_TITLE = 'איך לפנות אלייך?';
export const IDENTITY_SUBTITLE = 'כמעט סיימנו — נשארו רק הפרטים שלך.';
export const IDENTITY_NAME_LABEL = 'שם מלא';
export const IDENTITY_GENDER_LABEL = 'מגדר';
export const GENDER_OPTIONS = [
  { value: 'female',      label: 'אישה' },
  { value: 'male',        label: 'גבר' },
  { value: 'unspecified', label: 'מעדיפ/ה לא לציין' },
] as const;

// ── Step 5 · welcome aboard ──
export const READY_TITLE = (firstName: string) => `ברוכה הבאה על הסיפון, ${firstName}`;
export const READY_TIPS = [
  { title: 'התחילי מהמחוון',
    body: 'העלי את קובץ ה‑Word של המחוון. Vivi קוראת אותו בדיוק כפי שכתבת — כולל טעויות — ומסמנת כל אי‑התאמה לפני שממשיכים.' },
  { title: 'העלי מקבץ מבחנים',
    body: 'אפשר להעלות כיתה שלמה בבת אחת. התמלול מתחיל מיד, ואת חופשית לעשות בינתיים דברים אחרים.' },
  { title: 'עברי על התמלול לפני הבדיקה',
    body: 'התמלול מוצג לצד הסריקה המקורית. מה שתאשרי — זה מה שייבדק.' },
  { title: 'הציון האחרון תמיד שלך',
    body: 'לכל ניקוד יש נימוק וציטוט מהתשובה. אפשר לשנות כל ניקוד, וההסבר מתעדכן בהתאם.' },
];
export const READY_CTA = 'קדימה, לעבודה';

// ── Shell ──
export const NEXT = 'הבא';
export const BACK = 'חזרה';
export const PROGRESS_LABEL = 'התקדמות בתהליך ההיכרות';
export const STEP_OF = (i: number, n: number) => `שלב ${i} מתוך ${n}`;
```

`check-copy.mjs`: add `join('src','components','onboarding')` and `join('src','app','onboarding')`
to `BLOCKING_SURFACES` (`src/copy` is already gated). Note the copy says **מקבץ**, never אצווה
(OD4) — that gate is blocking everywhere.

---

## 5. Tests

Pure logic first — the codebase's bar is that anything pure is tested with zero mocks.

| File | Pins |
|---|---|
| `utils/school-search.test.ts` | prefix match on name; match on city; niqqud/gershayim normalization; `limit` respected; empty query → empty result (never the whole 2k list) |
| `lib/onboarding.test.ts` | `canAdvance` per step — the D7 matrix literally: step 2 blocked at 0 subjects, step 3 never blocked, step 4 blocked without name or without gender |
| `components/onboarding/OnboardingDialog.render.test.tsx` | logo + progress bar on every step; progress width per step; footer never absent; `dismissible={false}` (Esc does not close) |
| `components/onboarding/SchoolCombobox.render.test.tsx` | free-text affordance on no-match; picked schools render as removable chips; a duplicate pick does not double-add |
| `backend/tests/api/test_onboarding.py` | every endpoint requires auth (§9); **`PUT /me/schools` sets `school_id` to the FIRST school — the D3 named-protocol guard**; replacement semantics (3 → 1 leaves exactly one junction row); `complete` is idempotent (twice → same timestamp); the gender CHECK rejects garbage |
| `backend/tests/test_schema_canon.py` | already set-compares migrations ↔ `EXPECTED_MIGRATIONS`; adding `"022"` is what keeps it green |
| `e2e/onboarding.spec.ts` | route-mocked walk of all five steps; a fresh user is redirected in; a completed user is not; back-navigation preserves answers |

Backend suite runs in two invocations on Windows (§8 caveat). No test calls OpenAI.

---

## 6. Sequenced work

Each stage ends green; none leaves the tree half-wired.

- **S1 — schema.** Migration 022 + `EXPECTED_MIGRATIONS` + models + `selectinload(User.schools)`.
  Gate: `python -c "import app.main"`, `pytest --collect-only`, `test_schema_canon` green.
- **S2 — service + endpoints.** Extract `resolve_or_create_school` (existing `/me/school` tests
  green and untouched = proof), then the three endpoints + `UserResponse` fields +
  `build_user_response`. Gate: `tests/api/test_onboarding.py` and `test_users_auth.py` green.
- **S3 — wire.** `npm run gen:api`; `auth.tsx` User interface; the four `api.ts` functions.
  Gate: `npx tsc --noEmit`; api-types drift job clean.
- **S4 — shell.** `Modal` gains `dismissible`/`size`; copy module; `OnboardingDialog` + ProgressBar
  + steps 1/2/4/5; the route; `OnboardingGate`. Gate: `npm test`, `npm run check:copy`.
- **S5 — schools.** Your data file lands; `school-search.ts` + `SchoolCombobox` + `SchoolsStep`
  with the dynamic import. Gate: `npm test`, plus a bundle check that `israeli-schools` sits in its
  own chunk and not in the shared one.
- **S6 — journey + polish.** `e2e/onboarding.spec.ts`; reduced-motion pass; RTL/focus-order pass;
  and wire the profile page's stubbed save button to the now-real `PATCH /me/profile` — two lines,
  and leaving a button that visibly does nothing while its endpoint sits there would be *new* debt,
  not deferred debt.

---

## 7. Deploy

1. **Apply migration 022 to the Frankfurt DB before the backend rolls.** The columns are additive
   and nullable so either order is safe, but the ledger check logs `SCHEMA MISMATCH` until applied.
2. Backend: `gcloud run deploy gradervision-backend --source backend --project gen-lang-client-0438328890 --region europe-west1`.
3. Frontend: mirror `frontend/` → `grader-frontend/` (excluding `node_modules`, `.next`,
   `test-results`), commit, `git subtree push --prefix grader-frontend origin frontend-deployment`,
   then `git push origin main`.
4. **The 273 existing users will each see onboarding once on their next login.** If that is not
   wanted, the exemption is one statement in 022 —
   `UPDATE users SET onboarding_completed_at = created_at WHERE created_at < '<cutover>'` — and it
   is a product call, not made here.

---

## 8. Non-goals (named so they are not silently absorbed)

- Re-gendering the product's Hebrew copy (D4). The column is collected; nothing outside onboarding
  reads it yet.
- Seeding `schools` from the MenuTrie (D1). Rows are created on first pick.
- Changing PR-G6 override attribution (D3). `override_attribution.py` is not touched.
- A school-search endpoint, a school directory admin, or school editing after onboarding (until a
  profile surface is built, re-answering means re-running the flow).
- Any change to signup: it keeps collecting `full_name`, which step 4 prefills and can correct.

---

## 9. Implementation notes — what actually shipped (2026-08-31)

The plan above was followed. Five things came out **different from the plan**, each
because building it surfaced something the plan had wrong. They are recorded here
because a plan that silently disagrees with the code is worse than no plan.

### 9.1 The junction carries an explicit `position` column

**Planned:** a plain `secondary=` relationship; "schools[0] is the key" was documented as
if the collection had an order.

**Shipped:** `user_schools.position INTEGER NOT NULL DEFAULT 0`, the relationship is
`viewonly=True, order_by=user_schools.c.position`, and BOTH surfaces are written by one
function (`school_resolution.set_user_schools`).

**Why:** a many-to-many has no inherent order. `PUT /me/schools` answered in submitted
order while `GET /auth/me` answered in whatever order Postgres returned — so the profile
could name a different "first" school than `users.school_id` actually pointed at, and a
teacher re-submitting the list she was shown would silently move the PR-G6 attribution
key. Caught by `test_schools_first_is_the_attribution_key`, which is the D3 guard doing
exactly the job it was written for.

### 9.2 `onboarding_completed_at` is `DateTime(timezone=True)`

**Planned:** a plain `DateTime`, like its neighbours.

**Shipped:** `timezone=True`, and the endpoint stamps `datetime.now(timezone.utc)`.

**Why:** the DB column is `TIMESTAMPTZ` (as all of them are) while the ORM declares naive
`DateTime`. Binding an aware value then fails outright in asyncpg, and binding a naive one
serializes WITHOUT an offset on the write path while every later read carries one — a
browser parses the offset-less form as LOCAL time, three hours off in Israel. The
neighbouring columns carry that latent bug; a new column does not have to. Caught by
`test_complete_is_idempotent`, which compared the write-path and read-path values.

### 9.3 `PATCH /me/school` now maintains the junction too

**Planned:** untouched apart from the resolver extraction.

**Shipped:** it calls `ensure_user_school`, which adds the school to the junction (as a
UNION — it never drops the others) and gives it position 0.

**Why:** it is a WRITER of `users.school_id`. Leaving it writing only the column would put
the two surfaces in exactly the disagreement 022's backfill exists to prevent.

### 9.4 The e2e user fixtures needed the completion stamp

`e2e/fixtures.ts::USER`, `e2e/seedBatch.ts::AUTH_ME`, and one **inline** `/auth/me` object
in `batch-review-journeys.spec.ts` all describe a teacher already using the product.
Without `onboarding_completed_at` the new gate redirected the entire Playwright suite into
onboarding. The inline copy is now `AUTH_ME` — it had drifted from the shared fixture, and
since `/auth/me` OVERWRITES the seeded session, that drift was invisible until the day a
field mattered.

### 9.5 `Modal` gained `dismissible` and `size`

Both default to the original behaviour, and `primitives.render.test.tsx` pins the defaults
so the three pre-existing callers cannot be rewritten by a drifting default.

### 9.6 The 273-user note in §7.4 is void

There is exactly ONE live account (the owner's own test user). The migration therefore
carries **no completion backfill** and says so: every existing row sees onboarding once,
which is the intent.

### 9.7 Verification actually run

| Gate | Result |
|---|---|
| `backend/migrations/022` applied to Vivi-Test, then re-applied | idempotent, ledger `…021,022` |
| `python -c "import app.main"` | OK |
| `pytest tests/api/test_onboarding.py` (21 tests) | pass |
| `pytest tests/api/test_users_auth.py` (§9 structural guards, 36) | pass |
| `pytest tests/test_schema_canon.py` (29) | pass |
| `npx tsc --noEmit` | clean |
| `npm test` (vitest, 787 + the new 57) | pass |
| `npm run check:copy` (onboarding now BLOCKING) | pass |
| `npm run check:tokens` | pass |
| `npx playwright test onboarding.spec.ts` (7 journeys) | pass |
| full Playwright suite | pass except one PRE-EXISTING failure — `rubric-review.spec.ts:53` (`employee: … structured 400 then clean save`), reproduced with the onboarding gate unmounted, so it is not this change |

**Production migration APPLIED 2026-08-31** (owner-instructed). Frankfurt was at a clean head 021
(no gaps) with 6 user rows; after 022 the ledger reads `…021,022`, both `users` columns exist, the
`users_gender_valid` CHECK is present, `user_schools` carries `position`, and re-running the whole
file was a no-op (idempotent on prod as on test). The app's own `verify_schema_head()` against the
production URL reports `SCHEMA OK: migration head 022`.

⚠️ **The DB is now AHEAD of the deployed backend** until the Cloud Run deploy lands. That is the
safe direction and the boot check handles it by design: old code sees 022 as an *unknown* version
(not a missing one) and logs it as a WARNING — "usually a rollback deploy: DB ahead of code. Not
fatal." The new columns are additive and nullable, so the running service ignores them.

**Still owned by the owner:** the deploy itself (§7) — backend to Cloud Run, frontend via the
mirror-then-subtree-push.

### 9.8 The real school dataset landed (2026-08-31) — and the trie was declined

`src/data/israeli-schools.ts` now holds the Ministry export: **2,194 schools, 328KB**, each row
carrying `id` (סמל מוסד), `name`, `city`, `label`, `gradeLow`, `gradeHigh`. The `School` type moved
to `utils/school-search.ts` (the consumer owns it); the data module `import type`s it back, which
is erased at compile time and so creates no runtime edge that could drag the payload into another
bundle.

**A prefix trie over the same data was offered and declined**, on measurement rather than taste:
the flat scan costs **1.5ms per keystroke** over the real 2,194 rows (haystacks memoized per index
— one normalization pass per session, not per letter). The trie buys ~1.4ms of that and costs a
payload that roughly doubles, 328KB → ~640KB, on the one screen where she is actually waiting for
it, plus a generated 19,498-node artifact that must be regenerated in lockstep with the array.
Two representations of one dataset is the §0.4 duplication; 1.4ms is not worth it at this scale.
Recorded in the module docstring so it is not re-argued from first principles.

**Three normalization rules WERE adopted** from the offered code, because the real export justifies
each one — 500 of the 2,194 names contain quote marks, 98 contain hyphens, 68 contain punctuation:
NFC composition, punctuation dropped (`ע.ש` → `עש`), and **hyphens folded to spaces, never removed**
(`אורט-רוגוזין` must stay findable by either half; deleting the hyphen would glue it into a word no
prefix reaches). Ranking also moved to name-start › name-word › city-only, which is more meaningful
than the raw match position it replaced. Verified against the live data: «עש רבין» and «ע"ש רבין»
both resolve, and name+city combines («אורט אשקלון» → 3 hits). «אורט חיפה» returns nothing because
this export contains **zero** ORT schools in Haifa — checked before "fixing" it.

**Prefetch:** the dialog warms `import('@/data/israeli-schools')` while she is on the SUBJECTS
step, one ahead of where it is needed, so a 328KB download is not started at the moment she wants
to type. It fails silently — `SchoolCombobox` still owns the real load, its error state, and its
free-text fallback.

**Not taken:** `schoolLabels` and `schoolsById` (nothing consumes them; unused exports are weight),
and the trie helpers. **Worth a later decision (NOT made here):** the export carries the Ministry
institution symbol, a stable national identity. Today a pick commits by NAME (D1), so two spellings
of one school create two rows. Persisting `schools.ministry_symbol` (unique) would make school
identity exact instead of normalized-exact — a backend schema change and a revision of D1, so it is
surfaced, not slipped in.

---

## 10. Migration 023 — school identity is the Ministry symbol (owner-approved 2026-08-31)

The follow-up flagged in §9.8 was approved and implemented. It **revises D1**: a pick still sends
the name, but identity is now the symbol.

### 10.1 The evidence that set the design

Measured against the shipped export, not recalled:

| Fact | Value |
|---|---|
| institutions | 2,194 |
| unique Ministry symbols | 2,194 (all 6-digit numeric) |
| normalized names shared by more than one institution | **82 groups / 213 rows** |
| same normalized name **in the same city** | **15 groups** — 13 pairs + 2 triples; largest is three «ישיבת חזון נחום» in בני ברק |
| names containing a quote character | 407 |

The same-city case is the one that settles it: name identity, even name+city, cannot separate
those three schools. The symbol can. (An earlier draft of this table said "four rows in
פרדס חנה-כרכור" — that came from a looser substring filter, not the exact normalized-name
grouping. The corrected figure is both accurate and stronger.)

### 10.2 What shipped

* `schools.ministry_symbol TEXT`, partial-unique **where not null**.
* **018's whole-table name index RETIRED and re-created partial, where the symbol is null.** This
  is the load-bearing half and was nearly missed: 018 was unique on the normalized name across the
  whole table, so it *forbade* the second «בית אקשטיין» — the column alone would have changed
  nothing. Each index now names the population it rules.
* An identity ladder in `resolve_or_create_school`: **symbol present ⇒ the symbol is the identity**
  (look up, create if absent, never fall back to a name match); **symbol absent ⇒ the pre-023 name
  rule, unchanged.**
* `SchoolInput.ministry_symbol` validated `^\d{4,12}$` — numeric, but NOT hard-coded to the six
  digits today's export happens to use, because the format is the Ministry's to change and a
  teacher whose school is numbered differently must not be locked out of onboarding.
* The symbol round-trips through `/auth/me`, without which re-saving an unchanged list would
  silently demote every picked school to free text.
* Frontend: `PickedSchool.ministrySymbol` — set from the dataset row on a list pick, `null` on free
  text. One `fromIndex()` mapper is the single place that knows the dataset's `id` IS the symbol.

### 10.3 The ruling that is easiest to get wrong later

**A symbol never adopts a name match.** It is tempting to stamp an incoming symbol onto an existing
symbol-less row with the same name — "surely the same school". The data says otherwise, and doing
it would invent precisely the identity this column exists to establish. Two rows is the honest
answer: one known institution, one "a school someone typed". Reconciliation is an operator action
with evidence, never an automatic UPDATE. Pinned by `test_a_symbol_never_adopts_a_name_match`.

### 10.4 Verification

| Gate | Result |
|---|---|
| 023 applied to Vivi-Test, then re-applied | idempotent; both partial indexes present, 018's retired |
| 023 applied to **production**, then re-applied | idempotent; identical index set; `verify_schema_head()` → `SCHEMA OK: migration head 023 (5 partial indexes verified)` |
| `tests/api/test_onboarding.py` (28, incl. 7 new symbol rules) | pass |
| `tests/api/test_onboarding_real_dataset.py` (8, the REAL export) | pass |
| frontend unit (incl. 4 new shipped-dataset assertions) | pass |
| `e2e/onboarding.spec.ts` (8, incl. symbol-on-the-wire and free-text-null) | pass |

`test_onboarding_real_dataset.py` reads the export **in place** from
`frontend/src/data/israeli-schools.ts` (the precedent: the frontend vitest suite reads the golden
rubrics in place from the backend eval suite). It asserts the parser sees all 2,194 rows — so it
cannot silently degrade to testing a subset — that every real symbol survives the endpoint's
validation, that the collision premise still holds in the data, and then drives the real
same-name-same-town rows through the real endpoint and gets four distinct schools back.
