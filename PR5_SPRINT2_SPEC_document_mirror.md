# PR-5 SPRINT 2 SPEC — The Document-Mirror

**Design source:** PR5_DREAM_UX.md (Law 4 is this sprint's constitution: the
review surface must read as *her rubric, annotated by Vivi* — the quit
condition is an editor that doesn't resemble her DOCX). **Evidence base:**
pr5_context_answers.md. **Prerequisite:** Sprint 1 merged (`scopeLabel`,
`countFindings`, arrival step exist).
**Prime architectural fact (census A1, verified):** the mirror is a NEW
SIBLING VIEW. It consumes `questions` + `annotations` + `errorBannerRef`,
emits through `onQuestionsChange`/`onTotalPointsChange`/`onMetadataChange`,
and never touches `rubric-transform.ts` or its golden suite.

---

## 0. First principles — what a "mirror" is and is not

Her DOCX is a linear document: question headers carrying points, task prose
with embedded code and data tables, lettered/numbered parts, scoring TABLES,
red solution blocks. The current editor inverts every one of those into form
furniture: text becomes input boxes, tables become draggable card rows,
hierarchy becomes repeated generic headers, absence becomes empty boxes.

The mirror inverts back. Three principles govern every component:

1. **Typography first, chrome on intent.** Everything renders as document
   text. Edit affordances (underline hint, pencil, focus ring) appear on
   hover/focus only. A screenshot of the mirror at rest should be mistakable
   for a cleanly-typeset version of her rubric.
2. **Structure is communicated by document hierarchy, named by the naming
   law.** Headings carry paper identity (שאלה 2 · סעיף א · תת-סעיף 1 — via
   the same identity-preferred/ordinal-fallback rule as `scopeLabel`).
   Indentation is outline-depth, not card-nesting.
3. **The mirror displays; it never reinterprets state.** Every
   display-transformation (table detection, prefix de-emphasis) is a pure
   render-side function over verbatim state. Dehydrated output must be
   byte-identical to the card editor's for the same logical edits.

**Not in the mirror (scope fences):** findings redesign (Sprint 3 — this
sprint RELOCATES the existing summary banner + inline `AnnotationBanner`
faithfully, behavior unchanged); wait/arrival/save screens (Sprint 1); any
transform/dehydrate change; drag-reorder (deferred — ops exist, the document
metaphor makes drag heavy; BACKLOG).

## 1. Decided micro-rulings (veto window — one line each)

**D-1: Kill-switch = `USE_DOCUMENT_MIRROR` boolean, nothing else.** (Ruled
after agent verification: there is NO PDF-rubric flow — upload hard-rejects
non-DOCX and `sourceType` is a hardcoded literal, so a `sourceType==='docx'`
guard would defend an unreachable branch and teach readers a false fact.)
`RubricEditor` stays in-tree as the rollback target; the boolean flips a
release back.
**D-2: Solutions are read-only in the mirror this sprint.** Collapsed
"פתרון לדוגמה" disclosure per scope where `example_solution` exists; opening
shows the LTR block. Editing solutions is rare during review, was safe under
B-11 carry, and `ExampleSolutionEditor` can mount later; deferring keeps the
sprint honest.
**D-3: Add/delete exist but stay quiet — and delete is undo-over-confirm.**
Delete (question/sub-question/criterion) via the overflow menu (⋯) / hover
gutter, executing IMMEDIATELY with a 6-second undo toast ("סעיף ב נמחק ·
ביטול") instead of a confirm interruption — reversibility replaces ceremony
(see §2b). Never a bare trash icon at rest (census walkthrough flagged
destructive-prominent). Add-criterion = ghost row at
table foot ("+ הוסיפי קריטריון"); add-question/sub-question via a subtle
inter-section affordance on hover. All through the EXISTING ops
(`rubric-editor-ops.ts`) — generated ids are already handled by S1's
`scopeLabel` ordinal fallback.
**D-4: Verbatim routing prefixes get display-only de-emphasis.** A criterion
whose description begins with a token duplicating its scope heading
("סעיף א:") renders that token muted — state stays verbatim (round-trip
fidelity is untouchable); the regex lives in render only, tested.

## 2a. The five elevations (the Anthropic bar)

**E-1 — Reversibility as architecture (universal undo).** A bounded history
stack (last ~50 snapshots of the FULL editable tuple
`{questions, declaredTotal, name}` — ruled: a questions-only stack would make
Ctrl+Z silently no-op after a rename or total edit, teaching her the
mechanism can't be trusted) at the page level — the controlled-
immutable seam makes this cheap: push on every `onQuestionsChange`, pop on
Ctrl+Z / the quiet «ביטול» affordance in the document header. Deletes ride
the same stack (D-3's undo toast restores the previous snapshot). This is
the brand invariant — the teacher decides, and nothing she does is final —
implemented as a mechanism. Absorbs Sprint 3's per-fix «בטלי» into one
concept. History is page-session-scoped (clears on save), never persisted. No redo
at MVP (deliberate; backlogged). CORRECTNESS INVARIANT, not convention:
every mutation goes through the pure `*AtPath` ops — snapshots are pushed by
reference and rely on structural sharing; one in-place mutation retroactively
corrupts earlier snapshots (the verified `updateCriterion` landmine in the
old editor — backlogged as its own bug).

**E-2 — The outline rail (המפה).** A slim sticky rail at the document's
inline-start edge: "שאלה 1…N" as quiet links, active section highlighted on
scroll (IntersectionObserver — REQUIRED: `rootMargin` top offset ~-72px matching
the sticky app header + `scroll-margin-top` on anchors, or active-tracking
runs one section ahead and rail-clicks land headings under the header), a
small amber dot on sections holding an open finding — via the NEW pure
helper `findingSectionsByQuestion(annotations, questions)` (a scalar
`countFindings` cannot attribute findings to sections, and `target_id` comes
in three shapes — bare qid / dotted path / bare criterion id — requiring a
tree walk; helper lives beside `countFindings`, both consuming ONE shared
severity-predicate + dedup module, lowercase severities as wired).
E-2's commit begins with a live sticky-vs-`overflow-hidden` check on the
SidebarLayout ancestor; if sticky breaks, the pre-approved fallback is
`position: fixed` with a computed inline-start offset. One
glance = the whole territory + where the work is. Collapses below ~1100px
viewport. Kills the lostness quit-condition structurally, not just
nominally.

**E-3 — Living sums (visible cascade).** On commit of any point value: the
committed chip settles (brief tint fade ~250ms), then each ancestor chip
that `recalculateParentsFromCriteria` changed glows softly in upward
sequence (~600ms total). She watches the arithmetic stay true — trust
through visible causality, not copy. Implementation: value-change keyed CSS
transitions; no layout shift. Plus: `font-variant-numeric: tabular-nums` on
every points surface — columns align like a ledger.

**E-4 — Continuity of arrival (lightweight approximation — ruled).** The
metaphor is carried by CONTENT identity: the card's facts are verbatim the
header's facts. Motion underlines it without cross-step DOM continuity (the
card and header live in different step branches; true shared-element rigs
are brittle in Next 14/React 18 and were ruled out): the header fades/slides
in from the top, sections stagger in beneath (~300ms total). Same thing, now
open — at ~10% of the shared-element risk. ALL motion
(E-1..E-4) behind `prefers-reduced-motion` — reduced means instant, never
broken.

**E-5 — Designed silences.** Zero findings ⇒ one warm line under the
header: "ויוי לא מצאה אי-התאמות במחוון ✓" (absence as reassurance).
Keyboard flow in the criteria table: Enter commits and advances to the next
row's points; Tab moves description↔points; Escape cancels. A11y as
default: `aria-label` on every editable ("ניקוד סעיף א — לחצי לעריכה"),
real `<table>` semantics, `focus-visible` rings, the outline rail as `<nav>`.
A ten-line voice table in the PR for all micro-copy (⋯ menu, ghost row,
undo toasts, tooltips): warm, feminine-addressed, verb-first, no jargon.

## 2. Component architecture

```
RubricDocument.tsx                     (prop seam = RubricEditor's PLUS selectionGroups
                                       — the old seam is a floor, not the contract)
├── OutlineRail                        E-2: sticky map, finding dots, <nav>
├── DocumentHeader                     name (EditableText) · achievable total ·
│                                      selection line · «ביטול» (E-1) ·
│                                      the zero-findings line (E-5)
├── QuestionSection                    per question, data-scope-id={question_id}
│   ├── SectionHeading                 "שאלה 2" + PointsChip + selection chip + (⋯)
│   ├── QuestionBody                   RichText(question_text) + CodeBlock(code_blocks)
│   │                                  + DataTable(context/trace tables, lifted)
│   ├── SubQuestionSection (recursive) data-scope-id={fullPath}
│   │   ├── SectionHeading             "סעיף א" / "תת-סעיף 1" + PointsChip
│   │   ├── body / children / CriteriaTable / SolutionBlock
│   ├── CriteriaTable                  per scope owning criteria
│   └── SolutionBlock                  collapsed disclosure → LTR pre
└── (relocated) summary banner + inline AnnotationBanner at anchors
```

New primitives (the design-system seeds — there are no existing ones, census
D10): **`EditableText`** (renders as typography; click/focus → autosizing
textarea; commit on blur, cancel on Escape; `dir` per content), 
**`EditablePoints`** (points chip; click → number input; coercion via the
existing `safeParseFloat`/`formatPoints` utilities — never raw), 
**`CodeBlock`** (the shared LTR island: `dir="ltr"`, Fira Code, replaces the
three copy-pasted `<pre>` variants), **`DisclosureRow`** (chevron + label,
used by solutions and breakdown rows — chevron renders ONLY when content
exists; this single rule kills the empty-expander noise class).

Lifted from RubricEditor (moved to files, not rewritten):
`AnnotationBanner` (:1520 — fixes the CLAUDE.md §10 doc-drift; lift ONLY this
one — the two other inline annotation renderers in transcription/grading
panels have different props/types and stay put), `TraceTablesDisplay` (:1008),
`QuestionContextTablesDisplay` (:1079), restyled to document aesthetic
(hairline borders, no card chrome).

## 3. The CriteriaTable (the centerpiece)

The dominant DOCX rubric pattern, mirrored: a real `<table>` per
criteria-owning scope.

- Columns: description (flex, RTL) · נק' (fixed narrow, LTR numerals) ·
  hover-only affordance gutter. One thin header row ("קריטריון · נק'"),
  muted.
- Each row: `data-scope-id={criterion_id}`; description via `EditableText`
  (multi-line capable — long verbatim criteria WRAP, never truncate into
  horizontal scroll: the census walkthrough flaw dies here); points via
  `EditablePoints` — the commit path calls the SAME
  `updateCriterionAtPath` + `recalculateParentsFromCriteria` as today (the
  one cascade site; ops imported, never forked).
- Breakdown rows (`sub_criteria`): a chevron on rows that HAVE them; expanded
  rows render indented beneath as lighter table rows, editable the same way.
  Rows without breakdowns have no chevron (D10's `DisclosureRow` rule).
- Row delete on hover-gutter (undo-toast semantics per D-3); ghost add-row
  at foot. Keyboard flow per E-5 (Enter advances down the points column).
  `tabular-nums` on the points column (E-3).
- Inline `AnnotationBanner`s for criterion-anchored annotations render
  directly under the owning row, full-width.

## 4. The mini-table parser (the ONE interpretation site)

Problem (census D11 + our own convention): extraction flattens
question-embedded tables to space-joined rows — the digit soup is our
convention rendering, not a bug. The wire has no `[TABLE]` markers, and
adding them is a pipeline variable (rejected).

`detectTableRuns(text: string): Segment[]` — pure, display-only, tested:
- A **table run** = ≥2 consecutive non-empty lines, each whitespace-splitting
  to ≥2 tokens, equal token counts across the run (first line may be a
  header), and ≥60% of tokens numeric-ish (`-?\d+(\.\d+)?`).
- Runs render as bordered mini-tables (cells `dir="ltr"` for numeric content
  — negative numbers in RTL context are the classic mangling site).
- Everything else renders as `RichText` paragraphs (the existing
  newline-preserving behavior).
- **Bias to precision:** when unsure, do NOT tableize — the fallback is clean
  preformatted lines (monospace, line-preserved), which is honest; a false
  positive mangles her prose, which is not. Unit tests use the REAL fixture
  texts (bagrut q2's mirror-array examples, q3's dice-output rows) with
  expected segmentations as fixtures — the golden benchmarks are the test
  corpus.

## 5. Empty parents, headers, and the document at rest

- A parent (question or sub-question) with no prose renders: heading +
  points + children. NO text box, no placeholder paragraph. An
  "הוסיפי טקסט לשאלה" affordance appears in the (⋯) menu only — absence at
  rest, exactly per the Dream ruling.
- `DocumentHeader`: rubric name as `EditableText` (→ `onMetadataChange`);
  the total shown is ACHIEVABLE (PR-4's `rubric-achievable.ts` — already the
  header convention post-PR-4); selection exams state the structure in words
  ("מבחן בחירה — מענה על 4 מתוך 6 שאלות · 100 נקודות"); member questions of
  a group carry a quiet "שאלת בחירה" chip on their heading.
- Declared-total editing (`onTotalPointsChange`, teacher-authoritative)
  lives behind an edit affordance on the header total — parity with today's
  capability, not prominence.

## 6. Findings relocation (faithful, not redesigned)

The top summary banner mounts above the document (same `errorBannerRef`
contract — the blocked-save scroll keeps working); its jump buttons now show
`scopeLabel(...)` labels (S1 already fixed the raw-id leak). Inline
`AnnotationBanner`s render at their anchored positions in the flow: under
the section heading for node-level annotations, under the owning criterion
row for criterion-level ones. `data-scope-id` anchors preserved at every
level — `scrollToScope`, `RubricErrorDisplay`'s jump, and the Playwright
selectors keep working unchanged. Sprint 3 replaces the *visuals* of both
treatments; this sprint guarantees their *positions and behavior*.

## 7. Tests

- **SSR render suite over all five golden benchmarks** (sibling of
  `RubricEditor.render.test.tsx`): every fixture renders without error;
  assertions per fixture: zero empty text boxes for null-text parents;
  criteria-table row counts match state; chevrons only where breakdowns
  exist; solution disclosures only where solutions exist; bagrut's nested
  headings show identity labels ("סעיף א" under "שאלה 1").
- **Ops-parity (byte-identity form — ruled):** for the same logical edit,
  assert DEHYDRATED OUTPUT is byte-identical between mirror and old editor.
  (Spy-on-call-sequence was dropped: it tests mechanism, not guarantee, and
  is literally false on the old editor's direct-criteria path. The mirror
  routes ALL criteria edits — direct and nested — through
  `updateCriterionAtPath` + recalc, making it strictly safer than what it
  replaces.)
- **No-mutation-on-render:** rendering any fixture leaves the `questions`
  prop reference-equal (the mirror displays; it never "fixes" state).
- **`detectTableRuns` unit table** on real fixture texts + adversarial
  prose (numbered lists, short code lines) proving precision bias.
- **Primitives:** EditableText commit/cancel/dir behavior; EditablePoints
  coercion (string-wire seatbelt cases included).
- **Playwright:** both journeys migrated to the mirror. Bagrut: recognizes
  document shape (heading assertions), finding visible at its anchor, fix
  the points **in the criteria table**, save unblocks, zero `pageerror`.
  Employee: selection header line + achievable-50 + clean save. These two
  remain the render-half guard.
- **Elevation tests:** undo stack (edit→undo→state identical; delete→toast
  restore; history clears on save); outline rail renders one entry per
  question with dots matching deduped open findings; cascade animation
  hooks fire for exactly the ancestors the op changed (spy on keys, not
  pixels); reduced-motion renders instantly; a11y smoke (labels present,
  table semantics, rail is nav).
- The 8 vitest suites + golden round-trip: green, untouched.

## 8. Commit order

1. Primitives + `detectTableRuns` (+ tests) — no UI switch yet.
2. `RubricDocument` read-only skeleton; SSR suite green on all five.
3. Editing wired through ops; ops-parity tests.
4. Findings relocation + anchors; Playwright migration.
5. Elevations: E-1 undo stack + D-3 toast semantics; E-2 outline rail;
   E-3 cascade + tabular-nums; E-4 arrival continuity; E-5 silences/
   keyboard/a11y + the voice table.
6. D-1 flag flip for docx flow; polish (D-3 affordances, D-4 de-emphasis);
   CLAUDE.md §10 update (mirror architecture, lifted components, kill-switch,
   AnnotationBanner drift fixed).

## 9. Definition of done (Dream §3 conformance)

The bagrut session, in the mirror: she opens review and sees a document she
recognizes — her questions under their real names, her scoring tables as
tables, her solutions folded where she left them, nothing empty staring
back. The one finding sits anchored where it belongs. She clicks the 0.5,
types 1.5, the sums cascade correctly, save unblocks. At no point does the
surface show a technical id, an input box for absent text, an expander with
nothing inside, or a horizontal scrollbar on her own words. The screenshot
test: at rest, it could be her DOCX, typeset by someone who cares.

## 10. Voice table (E-5 — all mirror micro-copy)

Warm, feminine-addressed, verb-first, no jargon. As shipped in `RubricDocument`.

| Surface | Copy |
|---|---|
| Add criterion (ghost row) | `+ הוסיפי קריטריון` |
| Delete criterion (aria) | `מחקי קריטריון N` |
| Undo toast | `{סעיף ב} נמחק` · action `ביטול` |
| Undo (document header) | `ביטול` |
| Rubric name (aria / placeholder) | `שם המחוון — לחצי לעריכה` / `שם המחוון` |
| Declared total (label / aria) | `מוצהר` / `ניקוד מוצהר — לחצי לעריכה` |
| Criterion points (aria) | `ניקוד קריטריון N — לחצי לעריכה` |
| Criterion description (aria) | `תיאור קריטריון N — לחצי לעריכה` |
| Sub-question points (aria) | `ניקוד {סעיף א}` |
| Solution disclosure | `פתרון לדוגמה` |
| Selection line | `מבחן בחירה: מענה על k מתוך N שאלות` |
| Selection member chip | `שאלת בחירה` |
| Zero findings (silence) | `ויוי לא מצאה אי-התאמות במחוון ✓` |
| Blocking summary | `יש לתקן לפני שמירה:` |
| Outline rail (aria) | `מפת המחוון` · finding dot `ממצא פתוח` |

## 11. As-built deltas from the spec (surfaced, not silent)

1. **Trace/context tables were NOT shared-lifted** (§2 said "lift from RubricEditor").
   The mirror got FRESH document-aesthetic renderers (`document/DataTables.tsx`) and
   RubricEditor kept its inline copies byte-stable (rollback safety + genuinely different
   aesthetic). Only `AnnotationBanner` was truly lifted+shared (the CLAUDE.md §10 drift IS
   fixed). Unify later with a `variant` prop if wanted → BACKLOG B-16.
2. **Prose / sub-question-title / solution editing deferred** (read-only display this
   sprint; the Dream DoD is criteria-points-centric) → BACKLOG B-16.
3. **"Fix points → save unblocks" Playwright step:** the migrated bagrut journey asserts
   document shape + finding-at-anchor + save-blocked + the criteria cell is editable; the
   full fix→unblock arithmetic (INV-R1b vs INV-R1 coupling) is fixture-specific and left to
   manual/CI verification (Playwright can't run headless in this dev env).