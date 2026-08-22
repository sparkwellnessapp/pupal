# Design Recovery — Audit iter-1 (Pass 1: Structure)

**Apparatus:** `/design-lab?fixture=&state=` + `npm run snap` → `design/shots/iter-{0,1}/`
(30 + a synthetic `markers_demo` = shots at 1440 & 1280). **Baseline (iter-0)** captured the
broken mirror; **iter-1** captured after Phase 2 (P0 fixes) + Phase 1 (layout ruler + tokens).
Every finding below was read off the named PNG — no blind claims.

## iter-0 → iter-1: what the P0 fixes changed (read, not assumed)

| Defect (iter-0) | Evidence (iter-0) | iter-1 result | Evidence (iter-1) |
|---|---|---|---|
| Raw `[TABLE N: RxC]` + pipe rows | `markers_demo_at-rest_1440` (literal `[TABLE 1: 3x4]`, `\|---\|`) | **real bordered table** | `markers_demo_at-rest_1440` |
| Raw `[[color:…]]` / `[IMAGE:…]` | same | color **stripped**; image → **dashed placeholder** | same |
| Code as bidi-mangled RTL lines (`;int sum = 0`, braces flipped) | `markers_demo`, `csharp_..._at-rest_1440` | **one LTR monospace block**, correct braces | `markers_demo_at-rest_1440` |
| `Check(arr, 6)` mangled in RTL | `csharp_..._at-rest_1440` | reads **correctly** (bidi `<bdi>`) | `markers_demo_at-rest_1440` |
| Rail cramped INSIDE the card, top-right | `csharp_..._at-rest_1440` (iter-0) | rail **outside** the card, gutter-pinned | `csharp_..._at-rest_1440` (iter-1) |
| Content full-width (~80rem), lines too long | all iter-0 | **52rem** column | all iter-1 |
| Airy line-per-paragraph (bagrut 8741px tall) | `bagrut_..._findings_1440` (iter-0) | code grouped; shorter | iter-1 |

## §1b checklist — Pass 1 (binary, per screen)

**Layout:** content column centered @52rem ✓ · rail outside content, position:fixed (sticky proven
broken under the overflow-hidden ancestor), IO active-tracking ✓ · no horizontal overflow ✓
(code/tables `overflow-x-auto`) · header reads as a unit — **PARTIAL** (F1).
**Fidelity:** ZERO raw markers ✓✓ (VERIFIED, `markers_demo`) · embedded tables → bordered ✓ ·
code → grouped LTR monospace ✓ for standalone code; **PARTIAL** for code embedded *inside* Hebrew
sentences (csharp Q2 — the wire interleaves signature + prose on one line; bidi isolates the Latin
runs, but it isn't a code block) — **F2** · mixed Hebrew/Latin without mangling ✓ (VERIFIED).
**Criteria table:** hairline borders ✓ · muted header ✓ · `tabular-nums` points ✓ · long
descriptions wrap ✓ · chevrons only where breakdowns exist ✓.
**Affordances:** editable-at-rest looks interactive — **FAIL (F3)** points/name render as plain text
at rest (chrome-on-hover). *This is a taste ruling, not a bug* — the Sprint-2 spec's "typography
first, chrome on intent" directly conflicts with §1b's "buttons look like buttons." Needs Noam.
· hover affordance + focus ring present in code (not visible in a static shot).
**Findings:** blocking banner in Vivi's voice, anchored jump, `scopeLabel` only ✓ · finding cards
distinct-but-in-family — **PARTIAL** (Sprint 3 redesigns the visuals).
**States:** zero-findings reassurance ✓ · empty parents show no box ✓ · undo toast — **not yet
captured** (needs an interactive snap state) — **F4**.
**Craft floor:** type on scale ✓ (doc-title/q/sq/body/table/meta) · one border weight ✓ ·
reduced-motion honored ✓ · spacing mostly on scale — **PARTIAL** (craft Pass-2).

## Open findings (framed as classes)

- **F1 — header composition (craft).** Name · achievable total · declared · selection · reassurance
  read as stacked fragments, not one composed unit. Needs the reference "feel" to calibrate.
- **F2 — code-in-prose (data-shape, not render).** When the pipeline emits a signature on the SAME
  line as Hebrew prose, code-grouping can't fire (Hebrew ⇒ prose). Bidi isolation carries it
  legibly. A true fix is a pipeline concern (structured code spans) — noted, not forced.
- **F3 — affordance philosophy (RULING NEEDED).** chrome-on-intent (shipped) vs buttons-look-like-
  buttons (§1b). Blocks the Affordances row of Pass-1 until ruled.
- **F4 — capture the interactive states** (undo-toast, editing-a-point) via snap-script driving —
  apparatus TODO before the craft loop.
- **Rail visual (craft).** Correct + outside the card, but reads as a small floating label for
  few-question docs. Reference targets will set the bar.

## Verdict

Pass-1 **fidelity + layout** items are **met and verified by eye** — the P0 defects the suite exists
to kill (raw markers, mangled code, rail-in-card, over-wide column) are gone. Pass-1 is **not 100%**:
F1/F3/F4 + craft items remain, and they are **craft/taste** items that per §1c *cannot* be resolved
without Noam's reference targets. **This is the designed block point.** Passes 2–3 (craft, Jobs) and
the fixed point begin once the reference targets + the F3 ruling arrive.
