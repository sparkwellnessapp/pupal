# DESIGN RECOVERY SUITE — RubricDocument to world-class, with eyes open

**The failure being corrected:** Sprint 2 shipped UI its builder never saw.
Every gate was structural (tsc/vitest/SSR/build); zero gates were visual. The
result renders raw `[TABLE]` markers, mounts the rail inside the content card,
and draws buttons as plain text. The correction is not "try harder at design"
— it is an APPARATUS: eyes, a ruler, a loop, and a finish line that cannot be
declared without evidence.

**The standard (read this twice):** you are operating as a perfectionist
product designer with a Steve-Jobs-grade bar. That bar is not a vibe — in
this document it is operationalized as three audit passes and a fixed-point
rule (§5). You are DONE only when a full audit of fresh screenshots produces
zero new findings, twice consecutively. "The tests pass" is not done. "It
looks fine" is not done. Done is: you have interrogated every pixel of every
state and can no longer find anything to fix — and the written audit trail
proves it.

**One law above all: NEVER mark any visual work complete without having
looked at the rendered result.** Every iteration ends with you reading the
screenshot files you produced. Shipping blind is the defect this suite
exists to kill.

---

## Phase 0 — Eyes (build this first, everything depends on it)

1. **Browser:** `npx playwright install chromium` (self-contained; the
   "no headless browser" blocker is solvable in-env — verify, and if the
   environment truly cannot run it, STOP and surface; do not proceed blind).
2. **`/design-lab` dev route** (excluded from prod build): renders
   `RubricDocument` deterministically for every state × every golden fixture
   — no polling, no mocks, direct props: bagrut (nested + finding), employee
   (selection), csharp (code-heavy), hobby, foundations (clean/zero-findings)
   × states: at-rest, finding-open, editing-a-point, undo-toast-visible,
   solutions-expanded, arrival-card.
3. **`npm run snap`:** Playwright script capturing named full-page PNGs of
   every lab state at 1440×900 and 1280×800 into `design/shots/<iter-N>/`.
   Deterministic naming (`bagrut_at-rest_1440.png`).
4. **The observation mandate:** after every snap run, you READ the images.
   Your audit report (§5) cites them by filename.

## Phase 1 — The ruler

### 1a. Layout system (numbers, not adjectives)
- Page grid: content column `max-width: 52rem`, centered in the space
  remaining after the app sidebar; horizontal padding `24px` minimum.
- The outline rail: OUTSIDE the content column, at its inline-start edge,
  `width: 160px`, gap `32px` from content, sticky below the 64px app header
  (top offset 80px). It is a sibling of the content column in a flex row —
  never a child of the white card.
- Spacing scale: 4/8/12/16/24/32/48/64 only. Vertical rhythm: question
  sections separated by 48px; sub-question blocks 32px; paragraph spacing
  INSIDE prose 8px (the current line-per-paragraph airiness dies — prose
  line-height 1.7, no inter-line margins).
- Type scale (Rubik): page title 28/600 · question heading 20/600 ·
  sub-question 17/600 · body 16/400 · criteria table 15/400 · captions/meta
  13/400. Points chips: 15/600 `tabular-nums`.
- Color discipline: existing brand tokens only; borders `1px` in a single
  neutral border token; ONE accent (teal) for interactive/active; amber
  reserved for findings; red reserved for blocking. No new colors.
- Tokens hardened in the Tailwind config + a lint gate: component classes may
  not contain raw hex or arbitrary px values (`text-[#...]`/`p-[13px]`
  banned); tokens only. The gate runs in CI.

### 1b. The Visual Acceptance Checklist (Pass-1 material; binary; per screen)
**Layout:** content column centered at 52rem ✧ rail outside content, sticky,
tracks scroll ✧ nothing overflows horizontally at either viewport ✧ header
metadata block reads as one composed unit (name · total · selection line),
not scattered fragments.
**Fidelity of rendering:** ZERO raw markers anywhere (`[TABLE`, `[[color`,
`[IMAGE` never visible) ✧ question-embedded tables render as bordered
mini-tables ✧ code renders as grouped LTR monospace blocks with tight line
spacing — never one-line-per-paragraph ✧ mixed Hebrew/Latin lines render
without bidi mangling ("Check (arr, 6)" reads correctly — Latin runs
bidi-isolated).
**Criteria table:** visible structure (hairline row borders or zebra — pick
one, apply everywhere) ✧ header row present and muted ✧ points column
aligned `tabular-nums` ✧ long descriptions wrap, never horizontal-scroll ✧
chevrons only on rows with breakdowns.
**Affordances:** every interactive element is visibly interactive at rest
(buttons look like buttons: fill or border + radius + hover state; links
underline or color+weight) ✧ editable values show affordance on hover
(underline hint/pencil) and a focus ring when active ✧ destructive actions
never bare at rest.
**Findings:** the blocking banner reads as Vivi's voice, anchored jump works,
`scopeLabel` labels only (no raw ids) ✧ finding cards visually distinct from
content but in the document's family.
**States:** zero-findings shows the reassurance line ✧ empty parents show no
empty boxes ✧ undo toast styled, positioned, readable RTL.
**Craft floor:** all spacing on the scale ✧ all type on the scale ✧ one
border weight ✧ focus-visible everywhere ✧ `prefers-reduced-motion`
honored.

### 1c. Reference targets — REQUIRED INPUT FROM NOAM
2–3 screenshots of products whose feel is the bar (e.g., Linear docs, Notion
page, Craft) + one paragraph of "the feel." You imitate a concrete target;
you do not invent taste from adjectives. BLOCK on receiving these before
Phase 2's craft pass.

## Phase 2 — P0 functional fixes (before any polish iteration)

These are logic bugs wearing CSS costumes; fix and unit-test first:
1. **Marker-aware table parsing.** Production `question_text` contains
   `[TABLE N: RxC]` marker lines followed by row lines (see shot evidence —
   the wire carries them). `detectTableRuns` must consume markers FIRST
   (strip the marker line, take the announced dimensions as the row/col
   contract for the following lines) with the numeric heuristic as fallback
   for unmarked runs. The marker literally announces the table; parsing it
   beats guessing. Update fixture tests with real marker-bearing texts.
2. **Code-run grouping.** Consecutive code-looking lines (Latin/symbol-dense,
   brace-only lines) group into ONE `CodeBlock` (LTR, monospace, tight
   leading) instead of N airy paragraphs. Precision-biased like the table
   parser; fixture-tested on bagrut/csharp question texts.
3. **Bidi isolation.** Latin runs inside Hebrew prose wrapped in `<bdi>`/
   `dir="ltr"` spans at the RichText level — kills the "Check (arr, 6)B"
   class everywhere at once.
4. **Rail extraction.** Move the rail out of the content card to the §1a
   position; run the sticky-vs-`overflow-hidden` live check that was specced
   and not reported; apply the pre-approved `position:fixed` fallback if
   needed.

## Phase 3 — The loop protocol

Each iteration: **build → snap → audit → report → fix**, where AUDIT is three
written passes over the fresh screenshots:

- **Pass 1 — Structure:** the §1b checklist, item by item, per screen,
  pass/fail with filename citations. Any fail = finding.
- **Pass 2 — Craft:** grid alignment (is every element on the layout grid?),
  spacing rhythm (any gap not on the scale?), type hierarchy (can you tell
  heading levels at a squint?), color discipline (any color doing two jobs?),
  density (does any region feel crowded or deserted?), optical alignment
  (numerals, chips, icons visually centered, not just box-centered).
- **Pass 3 — The Jobs interrogation.** For every screen, answer IN WRITING:
  What can be REMOVED without losing function? Is any element arbitrary —
  could its size/position/color not be justified out loud? Does every element
  earn its place? Is there one clear focal point? Do the details survive
  200% zoom? Would you demo this on a stage to a skeptical audience?
  Any "no," "unsure," or squirm = a finding.

**Report format** (committed per iteration to `design/audits/iter-N.md`):
findings list with severity + screenshot citation + the fix taken. Findings
are framed as CLASSES where possible (one bidi fix, not five text patches).

**Iteration budget & the fixed point:** up to 3 autonomous iterations per
round. STOP when either (a) the cap is hit — post the full gallery + open
findings and wait, or (b) the finish line: Pass 1 at 100% AND Passes 2–3
produce ZERO new findings on two consecutive audits of fresh snapshots.
Only (b) may be called "exhausted." Self-certifying done while findings
exist, or without fresh screenshots, is the one unforgivable process
violation in this suite.

## Phase 4 — Noam's taste round (the ruling layer)

Post the gallery. Noam returns margin notes; each note becomes a finding;
one more loop round. Expect 2–3 rounds — taste convergence is iterative BY
DESIGN, not a failure of the loop. The agent's fixed point is necessary but
not sufficient; Noam's approval ratifies.

## Phase 5 — The regression lock

Every screen that passes Phase 4 is frozen as a Playwright
`toHaveScreenshot` baseline (key screens CI-gated, sensible thresholds).
Design regressions become loud diffs — the visual `suite_hash`. From this
point, the standing rule for ALL future UI work (Sprints 3–4 inherit it):
no visual change ships without a snap + audit, and no PR closes with a
failing baseline it didn't intentionally re-freeze with a stated reason.

## Definition of done

- [ ] Phase 0 apparatus committed and demonstrated (gallery of all states exists)
- [ ] Token lint gate live in CI
- [ ] P0 fixes landed with unit tests (markers, code-runs, bidi, rail) — zero raw markers in any screenshot
- [ ] The fixed point reached and documented in the audit trail
- [ ] Noam's taste round(s) completed; notes resolved
- [ ] Baselines frozen and CI-gated
- [ ] CLAUDE.md: the observation mandate + loop protocol recorded as the standing definition-of-done for UI work
