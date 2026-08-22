# Design Recovery — Audit iter-01af1ef (Round 2: D3/D4/D5/D7/D8/D9)

**Apparatus:** `/design-lab?fixture=&state=` + `node scripts/snap.mjs 01af1ef` →
`design/shots/iter-01af1ef/` — **44 shots**: 6 fixtures × 3 states × 2 viewports (36) **plus the
8 new named/interactive captures** that close iter-1's **F4** (`header`, `editing-point`,
`editing-prose`, `rail-landing` × 2 viewports). Commit `01af1ef` (on `51440f8`).
Every claim below was read off the named PNG.

## Round-2 directives — evidence

| Directive | Result | Evidence (named PNG / gate) |
|---|---|---|
| **D3** header is a real band | **MET** | `bagrut_899371_header_1440` — ONE composed unit: name `bagrut_899371` + selection line + reassurance on the start side, the single total chip on the end. Its own surface, above the body card (`editing-point_1440` shows band → gap → document). |
| **D4** מוצהר leaves the header | **MET** | `header_1440` shows exactly one number (100 נק' · סה"כ) and no מוצהר. Pinned: `RubricDocument.render.test.tsx` "the header exposes NO declared-total affordance" + "exactly ONE total renders". |
| **D5** points editable at every node | **MET** | `editing-point_1440` — **סעיף א**'s chip is an open number input (15, selected, spinner). Question / sub-question / inner all carry `— לחצי לעריכה`. Ops-level semantics in `RubricDocument.round2.test.ts`; browser-level in the D5 Playwright case. |
| **D7** the lying warning | **MET (class a)** | Root cause traced to `pipeline.py:1554` + `page.tsx:872` — see below. 14 regression tests in `finding-severity.test.ts`, 6 in `scope-label.test.ts`. |
| **D8** all prose editable, rich/raw | **MET** | `editing-prose_1440` — Q2's prose opened as a bordered textarea holding the **RAW** source (`[TABLE 6: 1x6]`, `\| 7 \| -3 \| …`, `\|---\|`), while at rest the same text renders as real tables. Verbatim round-trip pinned in `round2.test.ts`. |
| **D9** rail landing | **MET** | `rail-landing_1440` — clicking שאלה 4 lands the **TITLE** at the viewport top (y≈93px), fully visible, rail marking it active. Measured in a real browser at **1440 and 1280** (`expect(box.y).toBeLessThan(220)`). |

## D7 — root cause, stated as a class (the directive's gate)

**Class (a): the stale-assertion class.** Not a pipeline defect — the pipeline was *right when
it spoke*; the message's **present tense** is what is false.

1. `pipeline.py:1554` bakes the extraction-time numbers **into a string**:
   `f"…ב{issue.scope} הוא {issue.computed:.4g} נקודות, אך כותרת השאלה מצהירה על {issue.declared:.4g}…"`.
   That one f-string carries **both** reported symptoms — the frozen `40`/`21` **and** the raw
   id rendered as `בQ1`.
2. `page.tsx:872` returns `[...extractionAnnotations, ...liveAnnotations]`. Only the live half
   re-derives from `extractedQuestions`; the extraction half is set once (`:552`) and passed
   through forever. Edit a point → the frozen claim contradicts the header.
3. Both anchor the **same node** (backend `target_id = issue.scope.lower()` → `q1`; live INV-R1 →
   `q1`), so `annotationsFor()` rendered both.
4. `finding-severity.ts::dedupeOpenFindings` already treated that pair as **one finding for
   counting** (the flaw-1 ruling). Round 2 extends the same pairing rule to **render**.

**Not class (b):** none of the five gallery fixtures can produce `40/21/25` — their live-validator
output is bagrut `q1.א.2` 3≠2; hobby `q2` 60≠44 and `q2.ב` 29≠45; the other three clean. So the
shot came from a live-app run, consistent with a teacher edit moving the header while the frozen
message stood still. No job id was needed to classify it, because the staleness is **structural**:
any extraction message goes stale the moment state moves.

**Structural fix:** `visibleAnnotations()` in the shared severity module — a static message is not
rendered when a LIVE entry covers the same scope (rubric scope normalised across its two
spellings, `null` and `'rubric'`). **Rule adopted:** an extraction-origin message may never assert
a present-tense claim about editor state. Plus `humanizeScopeIds()` so no raw id reaches her eyes
inside a message **body**.

### Open — carried to Sprint 3 (flagged, not hidden)

- **F5 — the residual lie.** Suppression cures the *contradiction* case. It does **not** cure the
  case where she **resolves** the mismatch: the live twin disappears and the static message renders
  **alone**, still citing the old numbers. Suppression cannot see that. The Sprint-3 "original
  document" residual card — which re-frames extraction findings as **past-tense provenance** — is
  what closes it. This is the same lie, one state later.

## iter-1 findings — status

- **F1 (header composition)** → **CLOSED** by D3/D4.
- **F4 (capture interactive states)** → **CLOSED**; `snap.mjs` now drives them.
- **F3 (affordance philosophy — chrome-on-intent vs buttons-look-like-buttons)** → **STILL OPEN,
  needs Noam.** D5/D8 widened the *surface* of chrome-on-intent (every point chip and every prose
  block is now a resting-typography element that reveals its affordance on hover/focus), which
  makes the ruling *more* load-bearing, not less. Deliberately not pre-empted.
- **F2 (code-in-prose)** unchanged — a data-shape issue, not a render one.
- **Rail visual (craft)** unchanged — awaiting §1c reference targets.

## Craft notes read off the new shots (not regressions, for the craft pass)

- `editing-point_1440` doubles as fidelity proof for the marker work in `51440f8`: the data array
  renders as a bordered one-row table (no bold header), and the trace **scaffold** renders its
  header **plus five empty placeholder rows** — the blank rows survive (`isSeparator` now requires
  a dash, so an all-blank pipe row is DATA, not a separator).
- The band's reassurance line and the selection line stack on the start side; at 1280 the
  composition holds (`header_1280`).
- The open number input inherits browser spinner chrome — acceptable at this pass, a craft item if
  the reference targets call for a custom stepper.

## Gates

`npx tsc --noEmit` clean · `npx vitest run` **237 passed / 20 files** · `npm run check:tokens`
token-clean · `npx next build` clean · Playwright: D9 ×2 viewports, D5, D8 green.

## Verdict

All six Round-2 directives are **met and read off named PNGs**. The round does **not** claim the
Recovery fixed point: **F3 still blocks the Affordances row** of Pass 1 and the craft/Jobs passes
still await §1c reference targets — unchanged from iter-1, and still the designed block point.
New this round: **F5**, the residual half of the lying warning, scoped to Sprint 3.
