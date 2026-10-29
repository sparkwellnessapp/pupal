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

---

# PRE-REGISTRATION — MISSION_transcription_accuracy, Bet 1 (P1 model sweep)

**Written:** 2026-09-27, BEFORE the Bet-1 screen ran (plumbing probes on one fixture only, to
catch 400s/truncation — not scored for selection). Baseline = `configs/prod.json` (PROD_CONFIG).
Screen configs `configs/s1_*.json` isolate the P1 model: strike check OFF for every arm INCLUDING
the incumbent control, so the arms differ in exactly the model (plus the family's effort knob,
held at `low` everywhere).

**Hypothesis H-P1.** Most of the P1 wall is the model; a newer/other family can move all three
dimensions at once, and several candidates are cheaper than the incumbent.

| id | claim | metric | prediction | kill |
|---|---|---|---|---|
| B1-1 | a challenger beats the incumbent on the P1 WORST doc | `doc_ratio_strict`, p1_only, 10 fixtures, k=1 screen → k=3 finalist | best challenger worst-doc ≥ incumbent worst-doc + 0.005 | no challenger ≥ incumbent on the worst doc of ANY dimension within C2 → keep the incumbent, go to Bet 3 |
| B1-2 | the top prior (gemini-3.8-flash) is not worse and is cheaper | worst-doc P1 ratio; $/doc at LIST price | ≥ incumbent − 0.005, $/doc ≤ incumbent | worse by > 0.01 on the worst doc |
| B1-3 | a model change moves Hebrew | Hebrew-projection ratio (P1 vs raw), worst doc | best challenger improves the worst doc by ≥ half its gap to 0.98 | no challenger improves it at all |
| B1-4 | table shape is not a model problem | table shape-exact over the 6 GT tables | every finalist 100% shape; cell-exact differs by model | a finalist < 100% shape → Bet 2 needs Bet 4's crops |
| B1-5 | no cross-exam split | every claim above holds on BOTH exams | a win on one exam only is labeled, not adopted | a win on one exam with a regression on the other → stop and surface |

**Standing caveat (Phase-0 finding, recorded before the screen):** 3/5 bagrut fixtures carry
marker-only lines in their draft GT and non-canonical markers in raw GT (§4.3/§3.3 violations,
surfaced to the owner). Their GATE is capped by GT, independent of the model; ranking uses the
ratio and the diagnostics, and gate counts are read with that cap stated.


---

## MISSION Bet 2 — table adherence (pre-registered 2026-09-27, before any run)

**Variable (one):** the P1 prompt's table rule gains two sentences — (a) a row is ONE line: a
cell whose ink wraps (a long header condition) is joined onto its row's line with a space; (b) a
check mark is `✓`, a cross mark `x` (the owner's raw GT as of 16:07). Prompt version bump.
**Run:** the Bet-1 winner, `p1_only`, the 3 table docs, k=3, against the winner's own k=3.
- B2-1: table shape → 100% on all 3 docs, all repeats (flash's wrapped-header row split is the
  whole shape loss in the screen).
- B2-2: micro cell-exact ≥ 0.97 and worst table doc ≥ 0.95.
- B2-3: no non-table effect beyond noise — P1 worst doc and Hebrew prose worst doc within ±0.01
  of the winner's k=3.
- **Kill (mission):** shape < 100% after this ONE revision → tables need Bet 4's crop machinery.

## MISSION Bet 4 — the focus pass (pre-registered 2026-09-27, before any run)

**Variable (one):** `p1_focus_localizer_model_key` on (reader = same model, the P1 winner's
family) — localize Hebrew-bearing lines → read each from a crop of the 200-dpi render → splice by
line id under the skeleton guard (code unrepresentable as a change).
**Run:** winner config (+ Bet 2 if it held), `p1_only`, 10 docs, k=3; then 4b if budget allows.
- B4-1: Hebrew PROSE worst doc (excluding din_ezra, no prose in GT) improves by ≥ half its gap
  to 0.98. The biggest movers should be yonatan / omer (right-margin comments, dropped or
  hallucinated in the baseline).
- B4-2: zero splices refused for `skeleton` that were correct Hebrew fixes is NOT predicted —
  the guard will refuse some good readings; counted, not optimised this round.
- B4-3: (d)-class normalization in accepted splices: ≤ 1 across 30 docs (read by hand from
  `outputs/*.json → focus`).
- B4-4: cost +$0.01–0.03/doc; C2 holds on the winner.
- **Kill (mission):** Hebrew worst doc improves < half the gap, or (d)-class normalizations
  appear that one prompt revision cannot remove.

---

## MISSION Bet 2b / boxed values / Bet 3 (pre-registered 2026-09-27 18:20, before any run; owner adopted row-join + `[X]`, authorized the arrow-case fixes)

**Bet 2b — row-join (owner-adopted).** Variable: `p1_join_split_table_rows` on top of Bet 2
(winner + `p1_table_rows`). 3 table docs × k=3, `p1_only`.
- B2b-1: cells ≥ 0.95 micro (offline replay of Bet 2's outputs: 0.966); shape ≈ 13/18.
- B2b-2: the misses left are the two table-EDGE cases only (dan's boxed `74` row, itay_katav's
  absorbed «ב) 1)» column) — no new miss class. Non-table text unchanged (join is format-only).

**Boxed values.** Variable: `p1_boxed_values` on top of Bet 2b. dan + noam × k=3, `p1_only`.
- BX-1: dan's `✓ [74]` cell becomes exact on ≥ 2/3 repeats (the model now has a spelling).
- BX-2: noam p2's framed «מוחזר - 76» comes back bracketed — which the GT (no brackets) will
  score as a LOSS until the owner rules on it. Predicted, and it is a GT question, not a regression.

**Bet 3 — arrow instructions.** Variable: `p1_instructions` on the winner e2e config
(`w1_flash35_e2e`). ALL 10 docs × k=3, `per_doc` (false relocations are counted corpus-wide).
- B3-1: placement ≥ 3/5 cases on every repeat (the three single-arrow cases are the easy ones;
  itay_katav#02's `*` pairing and yonatan's mid-line target are the hard ones).
- B3-2: **0 false relocations** on the 7 docs without cases — the prompt's "when unsure, don't
  report" is the whole bet. Any false relocation is surfaced (mission stop condition if it
  survives one revision).
- B3-3: P1 ratio (physical pages) unchanged within ±0.01 — instructions are a separate field.
- Kill: any false relocation that one prompt revision or a tighter rule cannot remove.

## MISSION Bet 3 revision r1 (pre-registered 2026-09-27, before running)

Trigger: ONE false relocation (itay_katav, 1 of 4 repeats) — the boxed note «בהנחה המערך מונים
ממולא…» reported as an INSERTION and spliced into the code; the other 3 repeats reported it as
the attachment it is. Variable (one): the instruction block's kind test becomes what the text
IS (answer content → insertion; a note ABOUT a line → attachment), with "unsure between the
two → attachment" (an attachment can never change the answer's content).
Run: all 10 docs × k=3 `per_doc`, plus itay_katav × 3 more (6 itay_katav repeats in total).
- B3r-1: 0 false relocations across all 33 document-runs.
- B3r-2: placement not below Bet 3's 6/15 on the 3 case docs.
- Kill (mission): a false relocation survives this revision → surface; no second revision.

---

## Round 2 (owner-approved recs 1–5, 2026-09-28; +$10 envelope, cap $28.30) — pre-registered before any run

Base = `rec` (its k=5 `check_goal` run is the control; P1 metrics are on physical pages, so a
`p1_only` arm is comparable). One variable per arm.
- **R2 strike check `minimal`** (10 × k=3, p1_only): strike-check cost −60–80%; P1 worst doc and
  the struck-ink docs (din p1, itay_katav p1) within ±0.01 of control. Kill: any struck block
  that control removed now leaks on ≥2/3 repeats.
- **R3a pages_per_call = 1** (10 × k=3, p1_only): P1 worst doc +≥0.005 (more focus per page);
  cost ≤ +15% (prompt overhead per call). Kill: worst doc down or C4 breaks.
- **R3b P1 thinking `low`** (5 docs × k=1, p1_max_tokens 12000 — a PROBE): cost ≈ +$0.08/doc
  (C2-dead as priced on 2026-09-27); run to learn whether accuracy would justify it at all.
- **R1 table re-read** by gemini-3.1-pro (3 table docs × k=3, p1_only): table SHAPE back to 100%
  on all 3 and cells ≥ 0.97; prose on those pages unchanged (only grids are swapped). Cost
  +$0.02–0.05/doc on table docs only. Kill: a count-mismatch refusal on ≥1/3 of table pages,
  or shape < 100%.
- **R5 narrow Hebrew re-read** (10 × k=3, p1_only): localizer flash@minimal, reader 3.1-pro,
  ONLY lines P1 left without Hebrew. Hebrew PROSE worst doc (excl. din) +≥0.05; no doc's prose
  down >0.01 (it cannot touch Hebrew P1 wrote); cost ≤ +$0.03/doc. Kill: any accepted splice
  whose Hebrew is not on the page (read by hand from `outputs → focus`).
