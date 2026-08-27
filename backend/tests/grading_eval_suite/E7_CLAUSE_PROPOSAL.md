# E7 CLAUSE PROPOSAL — awaiting owner ratification (2026-08-27)

**Status: DRAFT. Nothing runs until this clause is ratified.** E7 is authorized;
the run is gated on your approval of the text below. This opens step 3 — it is a
change to `app/agents/grader/prompt.py`.

**It is derived from your ratified rulings, not invented.** Provenance for every
element is given in §2. Effectively **constitution entry #1** (§13.2 Stage-1 SEED:
seeded from teacher artifacts — the model solutions and the rubric's own tariff
vocabulary — never from the grader's guesses).

---

## 1. The clause, as it would be inserted

Added to `SYSTEM_PROMPT` as rule 3, renumbering the rest. No worked examples —
they could be pattern-matched onto these five fixtures.

```
3. SURFACE FORM IS NOT A DEDUCTION. This is a handwritten exam that was never
   compiled. Deduct only for conceptual defects — absent machinery, wrong
   algorithm, a missing guard or check, direct attribute access where the rubric
   requires a getter, a wrong loop bound or range. Do NOT deduct for how the
   student wrote it when the intent is unambiguous: identifier case, spelling,
   an obvious local left undeclared, parentheses where brackets belong, a
   truncated or malformed but clearly-referring name, a missing semicolon, or
   garbled braces. When the EXAMPLE SOLUTION is present, it — not your own
   convention — is the authority on naming and form: a student who matches the
   example solution's naming is correct by definition.
```

## 2. Provenance — every element traces to a ratified ruling

| Clause element | Ratified source | Baseline evidence it addresses |
|---|---|---|
| identifier case, spelling, naming | **PL-1** | 19 of 34 sampled shaving cases: *"printAverages ולא PrintAverages"*, *"'Public' ו-'Static'"*, *"שגיאת כתיב במילה Return"* |
| malformed-but-referring member access; parens-for-brackets | **PL-10** (and **AUDIT-2**, which ruled `A[J].get.chl()` full credit) | 3 cases, incl. the exact AUDIT-2 idiom: *"ניגש לערוץ באמצעות get.chl(), אך התחביר שגוי"* |
| shorthand IO (`cw`/`CR`) | **PL-2** | 3 cases: *"השימוש ב-CW במקום Console.WriteLine … לכן אני מוריד מעט מהניקוד"* |
| example solution is the naming authority | **R-α** | 3 cases deducting `durationInMinutes` — **the teacher's own model solution, present in the prompt, declares that exact field** |
| deductible list (absent machinery, wrong algorithm, missing guard, getter required, wrong bound) | the rubric's own deduction vocabulary — **entirely conceptual** | the tariffs GT itself applies |
| "never compiled" rationale | your framing | states the *reason*, not just the rule |

## 3. Run parameters — one variable

`grader-v3` (`GRADING_PROMPT_VERSION` bumped in the same commit) · k=5 · the same
five fixtures · `prior_context` **OFF** · ~$1.75. Nothing else moves.

## 4. Pre-registered kill criteria (already written into PREDICTIONS.md)

| # | Criterion | Baseline | Kill if |
|---|---|---|---|
| K1 | GT-ZERO → AI-ZERO | **80/80 (100%)** | **any** false credit appears. Kills the change regardless of Δ improvement |
| K2 | GT-PARTIAL → AI-FULL | 6/245 = **2.4%** | exceeds 2.4% |
| K3 | `terminal_within_precision_rate` | **0.6589** | fails to improve — a change that moves mean signed Δ without improving within-precision is adding noise, not accuracy |

## 5. Expected effect — restated **excluding** the rubric_underdetermined class

The original E7 prediction was sized against the full 201.75 shaving total. That
was too generous. Corrected sizing:

| Class | Points | E7 reach |
|---|---|---|
| Surface-form cited cause | **159.25** | **addressable (78.9%)** |
| `q2.ב.c4.s3` — rubric self-contradiction («סה"כ 2 נקודות» vs `points_possible=3`) | 18.50 | **out of reach** |
| `q2.ב.c4.s3` — din wrong-target zeroing | 15.00 | **out of reach** |
| din wrong-target zeroing, rest of q2.ב | 9.00 | **out of reach** |
| **Total outside E7** | **42.50 (21.1%)** | — |

**Restated prediction:** mean signed terminal Δ moves from **−0.3089** toward 0 by
**≥0.12** (≈75% of the addressable 78.9% share, allowing for partial compliance),
with the GT-FULL→AI-PARTIAL cell falling from **236** toward **<130**. The
**42.50 points of `rubric_underdetermined` and wrong-target harshness will
remain** — and if the post-run analysis shows them gone, that is itself suspicious
and should be read as over-compliance, not success.

## 6. What this clause deliberately does NOT do

- It does not touch `q2.ב.c4.s3`'s contradiction — that is a **rubric defect**,
  a §13 constitution ruling, not a grader fix.
- It does not address din's wrong-target zeroing — the grader has no rule for
  *"solves a different problem with correct structure"*; that is a separate,
  un-drafted clause and **not** part of this one variable.
- It does not touch the `q2.א.c1` 10-point monolith's lack of itemization.
- It does not touch the stitched-quote defect (step-3 multi-span design input).

---

## Ratification

On your approval I will: bump `GRADING_PROMPT_VERSION` → `grader-v3`, insert the
clause, run k=5 × 5 with `prior_context` OFF (~$1.75), and analyse **under §R in
full** — including a fresh stratified bucketing pass and the K1–K3 kill checks
reported before any headline number.

**No part of this is implemented. `app/` is untouched.**
