# PRE-REGISTRATION — multisubject beta, transcription (P1/P2 for English prose and Math)

**Written:** 2026-09-08, BEFORE the seam (Phase 1 of `vivi-multisubject-execution-plan.md`) was
written and before any non-CS page was transcribed under it.
**Authority:** `vivi-multisubject-execution-plan.md` §7; `docs/MULTISUBJECT_PLAN.md` §5.

> Written before any result is observed. If the outcome contradicts what is written below, the
> outcome wins; the prediction is not edited after the fact. These are the numbers the founder's
> smoke pages (n=1 per subject — plumbing, not accuracy) and the incoming dataset will test.
> **No accuracy claim for English or Math rides on this file.**

## What moves, what is held

Moves: the P1 system prompt for `english` / `mathematics` (F-3 fragments, assembled per profile;
stamps `t1.4-tables+english` / `t1.4-tables+mathematics`). Held: the CS P1/P2 text (sha-pinned in
`tests/subjects/test_prompt_identity.py`), P2 text for every profile (ALPHA-GAP A-8), models,
`PROD_CONFIG`, the scorer (no non-CS profile exists yet — ALPHA-GAP A-7; the numbers below are
measured with `doc_ratio_strict` on a hand-authored raw GT and by hand where the metric is alpha).

## Predictions

| id | claim | metric | number | kill |
|---|---|---|---|---|
| P-1 | P1 Math fidelity on the founder's handwritten page under the linear convention (`^`, `(a)/(b)`, `sqrt(...)`, `\|x\|`) | `doc_ratio_strict` vs hand-authored raw GT, no canonicalizer | ≥ 0.85 on ≥ 4/5 repeats | < 0.75 on ≥ 3/5 ⇒ the linear rule or the fragment, not the page |
| P-2 | P1 does not solve, simplify or correct | the deliberate arithmetic error transcribed as written | 5/5 | any repeat that "corrects" it kills F-3 (mathematics) |
| P-4 | paragraph fidelity (English) | paragraph count on the founder's page (two breaks) + the merged-paragraph variants, counted by hand this cycle | exact on ≥ 4/5 | off by ≥ 2 on any repeat ⇒ the F-3 rule or the P2 join |
| P-6 | misspelling preservation (English) | 5 injected misspellings × 3 typed keys; 3 handwritten on the founder's page | 100 % typed; ≥ 2/3 handwritten | any typed correction kills (the corrector must be `off`) |
| P-9 | figure description matches the ink | the founder's sketched graph → one `[איור: …]` line, reviewer-judged | 5/5 | any invented label or point kills the description line; fallback is nothing at the figure |
| P-13 | form-fill furniture (English booklets) | first English scans: P1's printed-text exclusion vs students writing on the booklet | ≥ 90 % of answer lines captured, ≤ 10 % printed stems leaked | either bound broken ⇒ a `form_fill` modality rule |

D-9 (ruled): crossed-out ink is omitted whatever pen struck it; the founder's crossed-out attempt
must be absent 5/5 (counted under P-2's run).
