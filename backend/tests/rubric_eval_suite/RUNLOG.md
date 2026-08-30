## RUN 20260706-163706_gpt-5.5
ref: 20260705-160259_gpt-5.5 (CONTAMINATED — 2 vars moved; see corrections)
purpose: instrument-verification probe (pedagogical rendering + provenance fixes live)
variable changed vs ref: TWO (effort high→medium; instrument code fixes) — unattributable
config: gpt-5.5  k: 1  model: gpt-5.5  effort: medium
prompt_version: 3.1.0-fp123  suite_hash: f0eb205aae6620bd
validity: 5/5 valid; excluded: none
gate: 1/5 (employee_course_select1 pass)
surprises: pedagogical diffs now visible — bagrut FP point_sum_mismatch@א (downstream of
  leaf_vs_branch flatten; representational overlap with rubric_mismatch annotation);
  hobby miss structural_mislabel@2 (model silently restructured instead of flagging).
  example_solution bagrut flipped 11-spurious → 3-spurious+8-missing (run-unstable).
attribution: render_loss=1, extraction_loss=19 (95% extraction)
decisions: none (k=1, no changes taken)
next: re-run k=5 unchanged — kill criterion: a failure not reproducing ≥4/5 is noise
cost: $1.51 total ($0.30/doc)  wall: ~bagrut 429s
corrections: none (first ledger entry; prior runs + 2 variable-changes remain unlogged)

## CHANGE 2026-07-06
what: PR-1 text-fidelity instrument. (1) GT text population: all 60
  question_text/sq.text nodes mechanically authored by tools/populate_texts.py
  from the fixture renders (43 populated, 2 genuinely-null, 15 open items —
  conventions + rulings R1-R3 + open-item table in GT_AUDIT.md addendum).
  (2) scoring: text_ratio null-semantics fix (GT-null ⇒ None, never 0.0;
  pred-null vs GT-text ⇒ 0.0) + new per-node text_line_recall (LINE_TAU 0.85,
  provisional) + three RubricScore aggregates (question_text_fidelity_min,
  subquestion_text_fidelity_min, text_line_recall_min — worst-node, UNGATED).
  (3) reporting: per-rubric text-fidelity block + summary diagnostic table;
  results.json keys additive. gates.py UNTOUCHED — gate_pass unchanged.
  pipeline.py zero-diff (instrument change, not a pipeline variable).
why: all 60 GT text nodes were null, so per-node text_ratio measured GT nullness
  (0.0 walls) while the pipeline spends paid retries on EMPTY_SQ_TEXT — a
  property demanded, enforced, consumed downstream, and never measured. Ungated
  because gating would mean threshold-by-guessing (zero distribution data).
by: PR-1 spec (Noam); executed mechanically by agent
affects: text metrics exist from the next run onward; the next k≥5 baseline
  carries text data from day one. suite_hash shift EXPECTED (scorer + schemas +
  reporting + benchmarks all changed) — a shifted hash on the next run is this
  change announcing itself, not drift. Round-trip prediction P-T1 CONFIRMED
  offline (1.0/None across all five fixtures); baseline expectations P-T2/P-T3
  pre-registered in PREDICTIONS.md. Full battery green (32 pytest tests:
  test_scoring, test_pedagogical, test_llm_policy, test_fp123 incl. golden
  self-pass 5/5).

## CHANGE 2026-07-09
what: GT csharp_plane_combine.json q1.c0–c5 — 6 criterion descriptions re-authored
  from label-only to the SECTION-3 two-column form "<detail>: <label>" (task A3).
  New strings copied BYTE-EXACT from the 20260708-180713 run's spurious_criteria
  (the model's byte-stable output); GT had under-encoded the detail column. Only
  the 6 description strings changed (no-op re-dump proved formatting preserved);
  Pydantic-valid; points/ids/structure untouched.
why: csharp crit recall/precision stuck 0.750/0.750 across two prompts with
  byte-identical missed↔spurious pairs — the symmetric ratio-match double-penalized
  the model's convention-correct two-column form. Ruling: model form is correct,
  GT was wrong (source rubric table has two text columns) — a GT fix, NOT
  training-to-model.
by: task A3 (Noam); executed mechanically by agent.
affects: suite_hash WILL shift next run (benchmark changed) — expected, this change
  announcing itself, not drift. Offline nz.ratio(new_gt, cached model output)=1.0
  for all 6 ⇒ next run csharp criterion_recall & precision → 1.000; csharp's last
  gate gap closes (PASS iff no other regression). csharp round-trip golden
  self-pass unaffected. SURFACED (not A3): test_fp123 now fails on foundations_cs
  (question_text_fidelity_min expected None, but PR-1 populated its GT text →
  now 1.0) — pre-existing stale expectation, independent of this edit, needs a ruling.

## CHANGE 2026-07-10 — instrument batch B1–B5 (one bisectable variable; no LLM runs)
what: (B1) parser_render reads the run-level <w:highlight> channel → [[hl:name]]
  contrast marks, same local-contrast architecture as color; white/none excluded
  (paste artifacts); whitespace-only runs unmarked. Root cause CORRECTED vs brief:
  foundations q1.ג marker is w:highlight yellow, NOT <w:color> — the renderer was
  channel-blind, not color-buggy. (B1b) audit_annotation_channels(docx, rendered):
  per-channel docx-ink vs rendered-marks guard → runner meta warnings; PLUS
  normalize.render_token_set now strips render markup (markers glued to ink mangled
  tokens — bagrut's "render_loss=1" on 'ניקוד: 6 נקודות' was this instrument artifact,
  will flip to extraction_loss). (B2) SuggestedParams typed model (from-alias/to,
  extra=forbid) replaces Dict[str,object]; AdjudicationResult now strict-valid —
  old shape reproduced the exact 400 path ($.properties.suggested_params.anyOf[0]).
  (B3) test_tier_b_schema_strict_valid walks the SDK's to_strict_json_schema.
  (B4) warnings/errors: Tier-B swallow → warnings_sink → pipeline warnings →
  RubricScore.warnings/errors → reports + summary. (B5) runner persists
  predictions/<doc>_r<k>.json + <doc>_render.md per trial, written as they arrive.
why: three instrument holes proved this cycle (highlight-blind render; Tier-B 400
  invisible in artifacts; conclusions inferred because predictions vanish).
by: mission Phase 1 (Noam-approved map); executed+designed by agent.
affects: suite_hash shifts next run (expected). Renders CHANGE for bagrut (8 hl
  spans), hobby (39), foundations (7); csharp/employee byte-identical; all five
  ink-identical modulo markers (verified) → A6 re-ground on Noam. render_loss/
  extraction_loss counts may shift (tokenizer fix — more honest). Battery 36/36
  (4 new tests). Pre-existing, NOT this batch: API-layer failures (grading_batches.
  test_count column drift, stale 501-stub test, PDF page-count env) — 211 others pass.
  Prompt UNTOUCHED (3.2.0-textconv); model frozen. Next: Run A k=1 validation.

## RUN 20260710-014257_gpt-5.5
ref: 20260708-180713_gpt-5.5
purpose: Run A — validate instrument batch B1–B5 + GT A1–A3 (prompt/model FROZEN)
variable changed vs ref: instrument batch + GT edits (one bisectable wave, no prompt/model change)
config: gpt-5.5  k: 1  model: gpt-5.5  effort: medium
prompt_version: 3.2.0-textconv  suite_hash: 5da255ad066b5383
validity: 5/5 valid; excluded: none
gate: 3/5 (employee, csharp, hobby) — first multi-pass in suite history
predictions: employee PASS CONFIRMED (control held); csharp PASS CONFIRMED (A3 GT fix
  live); hobby PASS CONFIRMED — Tier B succeeded e2e FIRST TIME (structural_mislabel,
  conf 0.97; the 400 was the only blocker; adjudicator judgment sound); bagrut FAIL
  CONFIRMED; foundations CONDITIONAL-NEGATIVE: model copied marked option into q1.ג
  text (marker stripped) but example_solution=None → the pre-registered S3 misroute.
deltas vs ref: bagrut ex_sol .455→.727 (A4 scopes q2.ב/q5.א/q5.ב ALL 1.0000 by B5
  direct diff — cleaning did NOT reproduce; only remaining sol failures are the 3
  leaf_vs_branch spurious). bagrut render_loss 1→0 (tokenizer fix; ניקוד:6 now
  extraction_loss — honest). bagrut text fidelity all-1.0. foundations ex_sol .5→.8
  (4 of 5 sols ok; only marked-option node missing). No [[hl:]]/[[color:]] leakage
  into ANY prediction. B4 live: PREFLIGHT_INV1 warning in artifacts.
surprises: A4 cleaning hypothesis WEAKENED, not confirmed — verbatim-perfect this
  draw on identical input (k=1 both draws → unstable behavior, pin via prompt).
  bagrut now SINGLE root cause: leaf_vs_branch nesting (drives structure, crit
  recall 13 losses, 3 spurious sols, annotation anchor, ped FP).
decisions: proceed Run B: (i) SECTION-8 nesting via scoring structure; (ii) SECTION-4
  verbatim pinning (worded from measured instability); (iii) S3 marked-option→
  example_solution routing + teach [[hl:]] convention. One prompt version, bisectable.
next: Run B k=1 — kill: bagrut structure+ex_sol+crit_recall→1.0, foundations
  ex_sol→1.0, employee/csharp/hobby HOLD, zero new leaf_vs_branch; redistribution ⇒
  prompt surface exhausted → escalate design. Expected 5/5.
cost: $1.68 total ($0.336/doc)  wall: bagrut 466s/$0.94/1 retry (same faithful-error retry)
corrections: none

## CHANGE 2026-07-10 — prompt 3.2.0-textconv → 3.3.0-nest-verbatim-hl (Run B items)
what: EXTRACTION_SYSTEM_PROMPT, three changelog-bisectable items, one version:
  (i) SECTION 8 + detect-by-SCORING-STRUCTURE: multiple task statements each with
  its own ניקוד block under one lettered SQ = nested parts labeled 1,2..., even
  with no "(2)" marker (bagrut's source never writes it — verified in render).
  (ii) SECTION 4 verbatim pinning: ALL alternative options, dead/commented code,
  boundary lines, teacher typos — never select/clean/normalize. Worded from Run A
  evidence: same input scored .63/.73/.79 (20260708) then 1.0/1.0/1.0 (Run A) —
  UNSTABLE behavior pinned, not a confirmed persistent defect corrected.
  (iii) SECTION 3: [[hl:name]] convention taught + MARKED-OPTION=ANSWER routing
  (Run A direct evidence: model copied marked option into text, solution=None).
why: bagrut collapsed to single root cause (leaf_vs_branch cascade); foundations'
  only gap is the marked-option misroute; solution verbatim needs pinning.
by: mission Phase 3 map + Run A evidence; executed by agent.
affects: invalidates comparison to any pre-3.3.0 run for prompt-attributable
  metrics. Run B pre-registration: bagrut structure+ex_sol+crit_recall→1.0,
  annotation@q1.א.2, ped FP gone, retry likely dies; foundations ex_sol→1.0;
  employee/csharp/hobby HOLD PASS; zero new leaf_vs_branch anywhere. Kill:
  any redistribution (a passer breaks) ⇒ that behavior's prompt surface is
  EXHAUSTED → stop prompting, escalate design. Expected 5/5.

## RUN 20260710-020038_gpt-5.5
ref: 20260710-014257_gpt-5.5 (Run A)
purpose: Run B — variable test: prompt 3.2.0-textconv → 3.3.0-nest-verbatim-hl
variable changed vs ref: prompt only (3 bisectable items: nesting-by-scoring-structure;
  verbatim pinning; [[hl:]] + marked-option routing)
config: gpt-5.5  k: 1  model: gpt-5.5  effort: medium
prompt_version: 3.3.0-nest-verbatim-hl  suite_hash: 5da255ad066b5383
validity: 5/5 valid; excluded: none
gate: 4/5 (employee, csharp, hobby HELD + foundations NEW) — no redistribution,
  escalation trigger NOT fired
predictions: foundations ex_sol→1.0 CONFIRMED (S3 routing worked; PASS). bagrut
  →1.0 PARTIAL: structure .700→.929 (q1.א+q1.ב now nest, points exact; annotation
  anchors q1.א.2 → annotation_match PASSES as cascade predicted), crit_recall
  .787→.885 (13→7 losses), ex_sol .727→.846. NOT reached 1.0 — residuals below.
deltas vs ref: bagrut remaining failures now decomposed by B5 direct evidence:
  (R1) q3.ב still flat — GT nests 12+3 but render shows NO scoring-split signal
  (one 'סעיף ב' row-run, one סה"כ 15); GT's two parts carry a DUPLICATED identical
  example_solution → GT-GROUNDING QUESTION, surfaced to Noam, NOT prompt-iterable.
  All 7 crit losses + the 1 spurious sol are this node.
  (R2) ped SPURIOUS point_sum_mismatch@2 (was @א) — DETERMINISTIC Tier A fires on
  any FAITHFUL draft of the teacher's 1.5+0.5-under-3 error, while GT expects
  ped=[] + rubric_mismatch annotation. GT and detector mutually inconsistent by
  construction ⇒ bagrut gate UN-PASSABLE until ruled. SURFACED (3 options).
  (R3) q1.א.1 sol 'missing' at ~0.77: model included the trace-table HEADER row;
  GT (per SECTION-4 convention) wants values only. Model-side near-miss, k=1.
  (R4 ungated) q1.ב.1 text ratio .284 — model used final instruction line as text,
  code listing omitted. Ungated; logged.
surprises: retry design smell RECURRED post-nesting-fix (PREFLIGHT_INV1 now @q1.א.2,
  1 retry, $0.92, 352s) — per mission: proposal owed, not a patch.
decisions: HOLD Run C — bagrut cannot pass regardless of further prompt work (R1/R2
  are Noam's rulings); k=5 on a tree about to change wastes budget. No further
  prompt iteration on R3 alone (already-instructed behavior; k=1 undecidable).
next: surface R1/R2 rulings + retry proposal to Noam — kill criterion for resumed
  loop: rulings land ⇒ Run C k≥5 confirms 5/5 (or 4/5 + ruled-out bagrut) stable.
cost: $1.71 total ($0.342/doc)  wall: bagrut 352s/$0.92/1 retry
corrections: none

## CHANGE 2026-07-10 — GT bagrut_899371.json q3.ב flattened (R1 ruling)
what: q3.ב's two nested parts (.1: 6 criteria/12pts, .2: 1 criterion/3pts) unified
  into a single leaf sub-question: 7 direct criteria (byte-exact from the parts,
  re-id q3.ב.c0–c6, Σ=15=declared), ONE example_solution (the parts carried a
  byte-identical duplicate — deduplicated verbatim), sub_questions=[]. No-op
  round-trip proved formatting preserved; Pydantic-valid; nothing else touched.
why: R1 RULED by Noam: GT was wrong — the split was inferred (identical criteria
  ownership + duplicated solutions on both parts; no scoring-split ink in source).
  Model's flat form is the faithful reading.
by: Noam (ruling 2026-07-10); executed mechanically by agent.
affects: suite_hash shifts next run (benchmark changed — expected). OFFLINE
  re-score of Run B's persisted bagrut prediction vs ruled GT (B5 payoff, $0):
  structure 1.0, crit R/P 1.0/1.0, pt_exact 1.0, annotation True. bagrut residuals
  now EXACTLY: ex_sol 0.9231 (R3 — q1.א.1 header-row inclusion, 1 node) +
  pedagogical_mismatch (R2 — awaiting ruling). Battery green post-edit.
  R2 ruling + retry proposal still pending; Run C held.

## CHANGE 2026-07-10 — R2 ruling (a)+scope: pedagogical consistency invariant (GT+instrument)
what: (1) GT bagrut pedagogical_mistakes gains the Tier-A emission TRANSCRIBED from
  a probe on the faithful round-trip draft — mistake_id pts:q1.2, point_sum_mismatch,
  target '2', evidence children_sum=2.0/declared=3.0. Probe verified byte-identical
  to the LIVE Run-B draft's serialized emission (B5) — zero hand-authored strings.
  (2) test_fp123 round-trip: stopped copying gt.pedagogical_mistakes; now runs the
  REAL Tier A (llm=None) on every fixture's faithful draft + injects only
  Tier-B-kind GT entries (hobby structural_mislabel), asserts pedagogical_match —
  the invariant GT ≡ TierA(faithful) ∪ expected-Tier-B is now battery-enforced.
  (3) invariant documented: GT_AUDIT conventions + playbook §4 pedagogical.
  (4) PREDICTIONS: P-PED1 (pedagogical = second never-reconcile tripwire),
  P-PED2 (retro-diagnosis of the 20260705/06/08 bagrut ped "FP").
why: R2 RULED by Noam: option (a) with scope extension — the deliverable is the
  consistency invariant, not the GT entry alone (the entry would wait for the next
  fixture to break identically). Teacher point-error = two surfaces, one event.
by: Noam (ruling); executed by agent.
affects: pedagogical comparisons vs ALL prior runs invalidated (prior "FP" was the
  detector working); suite_hash shifts (GT+test). Battery 36/36 with invariant live.
  OFFLINE re-score Run B pred vs post-R2 GT: pedagogical_match=True; bagrut
  failures now EXACTLY ONE — example_solution_fidelity=0.9231 (R3 q1.א.1
  header-row node). RETRY PROPOSAL: deferred by ruling (mechanism circular —
  persistence is established BY the retry; stateless run can't gate on it; any
  change = pipeline variable). BACKLOGGED with trigger: baseline shows material
  retry-burns on faithful-mismatch docs at production settings, OR any retry
  "succeeds" by reconciling (post-(a) detectable as Tier-A-silence signature) ⇒
  retry policy becomes its own pre-registered change, options {keep,
  non-retryable-point-mismatches}, judged on annotation false-alarm cost.

## RUN 20260710-154422_gpt-5.5
ref: 20260710-020038_gpt-5.5 (Run B)
purpose: Run C — k=5 confirmation baseline (post R1+R2 GT/instrument; prompt/model frozen)
variable changed vs ref: GT+instrument only (R1 q3.ב flatten; R2 pedagogical invariant)
config: gpt-5.5  k: 5  model: gpt-5.5  effort: medium
prompt_version: 3.3.0-nest-verbatim-hl  suite_hash: ca786aca5b2e82ba
validity: 23/25 valid; excluded: csharp r0+r1 (OpenAI 429 insufficient_quota —
  transport, transient: cleared by r2; coincided with a CONCURRENT unattributed k=1
  run 16:07–16:18, see next entry — double spend in one window)
gate: 18/25 — per-fixture: employee 5/5, foundations 5/5 (S3 marked-option routing
  STABLE), hobby 5/5 (Tier B judgment STABLE — the run's genuine unknown, answered),
  csharp 3/3-valid (5/5 model-wise; 2 quota invalids), bagrut 0/5.
predictions: passers-stable CONFIRMED (no fixture failed a valid repeat on any axis).
  R3 verdict: STABLE DEFECT — bagrut ex_sol=0.9231 on ALL 5 repeats, same node
  q1.א.1 (trace-table header row in solution), everything else 1.0 ×5
  (structure/crit/points/annotation/pedagogical). P-PED2 CONFIRMED 5/5: serialized
  Tier-A emission byte-matches GT (pts:q1.2). P-PED1 unexercised (no reconcile
  draw occurred — good). Text distribution: worst q_text .9203 (employee),
  sq_text .2837 / line_recall .0714 (bagrut q1.ב.1 = known ungated R4).
surprises: retry burn WORSE than feared: fired 5/5 bagrut repeats (r3 fired TWICE,
  $1.40 trial). Faithful-error doc costs $0.91–1.40/extraction vs ~$0.19 clean —
  the backlogged retry trigger's "material at production settings" arm is now MET.
decisions: R3 becomes the final prompt item (one variable): SECTION 4 — filled
  trace-table solutions = VALUES ONLY, headers are question scaffold (rule exists;
  needs the explicit table-header exclusion example). NOT landed yet — quota
  exhaustion risk + billing headroom is Noam's call before ~$11 more spend.
next: on go: prompt 3.3.1 R3 fix → k=1 validate → k=5 close-out. kill: bagrut
  ex_sol→1.0 5/5 with zero regression on 4 stable passers ⇒ 5/5 at k≥5 = MISSION GATE.
cost: $8.67 total ($0.377/doc-trial mean, max $1.40)  wall: 15:44–16:48
corrections: my 16:20 liveness check attributed dir 160712's artifacts to this run —
  WRONG: that was the concurrent k=1. This run's dir is 154422. Retraction per §11.1.

## RUN 20260710-160712_gpt-5.5
ref: n/a (unattributed side run)
purpose: UNKNOWN — k=1, launched 16:07 NOT by the loop agent (presumed manual/Noam).
variable changed vs ref: none vs Run C tree (same suite_hash ca786aca5b2e82ba)
config: gpt-5.5  k: 1  effort: medium  prompt_version: 3.3.0-nest-verbatim-hl
validity: 4/5; hobby INVALID (429 insufficient_quota — the shared-window casualty)
gate: 3/5 (csharp, employee, foundations) — results CONSISTENT with Run C r-trials:
  bagrut ex_sol 0.9231 same R3 node; pedagogical/annotation ALL PASS.
decisions: none; logged for ledger completeness (it spent quota concurrently with
  Run C and explains the 429 window). If not Noam's launch — investigate.
cost: ~$1.52  wall: 16:07–16:18
corrections: none

## CHANGE 2026-07-10 — prompt 3.3.0-nest-verbatim-hl → 3.3.1-tracehdr (R3 fix)
what: SECTION 4, one item: HEADER ROW EXCLUSION sub-bullet on the filled-trace-table
  rule — copy VALUE rows only into example_solution; never repeat the header line
  (with the exact bagrut q1.א.1 shape as the worked example). Version bumped.
why: R3 = STABLE DEFECT (Run C: 5/5 repeats, ex_sol 0.9231, same node q1.א.1, model
  prepends the header row). The values-vs-headers rule existed; it lacked the
  explicit copy-time exclusion + example.
by: agent, on Noam's go (quota confirmed $10; k=2 confirmation ORDERED BY NOAM —
  gate owner amends the k≥5 confirmation bar for budget; logged as his ruling).
affects: invalidates prompt-attributable comparisons vs 3.3.0 runs. Pre-registration
  for the k=2 run: bagrut ex_sol → 1.0 on BOTH repeats (kill: header row still
  present in q1.א.1 solution on any repeat = fix insufficient); zero regression on
  employee/csharp/foundations/hobby (kill: any passer fails a valid repeat =
  redistribution ⇒ revert + escalate). Expected 5/5 both repeats ⇒ mission gate
  (at Noam's amended k=2 bar). Budget: ~$3.8 of $10.

## RUN 20260710-180307_gpt-5.5
ref: 20260710-154422_gpt-5.5 (Run C)
purpose: variable test: prompt 3.3.0 → 3.3.1-tracehdr (R3 fix), k=2 per Noam's amended bar
variable changed vs ref: prompt only (SECTION 4 header-row exclusion)
config: gpt-5.5  k: 2  effort: medium
prompt_version: 3.3.1-tracehdr  suite_hash: ca786aca5b2e82ba
validity: 10/10 valid
gate: 7/10 raw → 9/10 after the GT-consistency fix below (offline re-score of the
  SAME persisted predictions), 10th cell = transport.
predictions: R3 fix CONFIRMED — bagrut PASS BOTH repeats (first bagrut PASS in suite
  history; ex_sol 1.0, q1.א.1 starts at values, header gone). Kill criterion
  (passer regression) INVESTIGATED, NOT FIRED:
  (1) foundations 0.800 ×2 = INSTRUMENT: GT q1.א solution was authored
  HEADER-INCLUSIVE (pre-3.3.1 model behavior) while bagrut GT was values-only —
  the GT corpus was internally inconsistent on the R3-ratified convention; the
  3.3.1 model is convention-correct on both docs. GT fixed (entry below);
  offline both repeats → 1.0/PASS.
  (2) hobby r1 = TRANSPORT: Tier B "Connection error" (B4 warning made this a
  one-line diagnosis); Tier A kept, trigger skipped → missing structural_mislabel.
  hobby r0 PASSED; Run C had 5/5. Not prompt-attributable.
surprises: Tier B has NO transient-transport retry (grader has one) — a single
  connection blip silently costs the detection for that extraction. BACKLOG
  (small, pre-registered when opened): extend the grader's transient-retry
  convention to the Tier-B call. Latent GT note: bagrut q1.ב.1 solution still
  carries a mid-text header line ('sum i arr[i] check(arr,i)') — sub-threshold
  (long solution, ratio survives), flagged for the next GT audit, NOT blocking.
decisions: foundations GT header-line strip (mechanical consequence of R3 ruling;
  transcription-verified). Recommend one k=1 close-out sweep (~$1.9) for a clean
  all-cells-green closing entry; Noam's call vs accepting 9/10 + Run C history.
cost: $3.81 ($0.381/doc-trial)  wall: 18:03–18:59
corrections: none

## CHANGE 2026-07-10 — GT foundations_cs.json q1.א example_solution: header line stripped
what: removed line 1 (the trace-table header 'פלט i<=num2 ... n2 n1') from q1.א's
  example_solution; remaining values-only text verified BYTE-EXACT equal to the
  3.3.1 model emission before writing (transcription, not authoring). Format
  preserved (no-op round-trip); Pydantic-valid; battery 36/36.
why: mechanical consequence of the R3 ruling (values-only is the ratified
  convention; bagrut GT already follows it). Foundations GT was authored under the
  old header-inclusive model behavior — internal GT inconsistency, not model error.
by: agent, executing the existing R3 ruling; surfaced to Noam in the same report.
affects: suite_hash shifts next run. foundations 3.3.1 predictions re-scored
  offline: 1.0/PASS both repeats.

## RUN 20260711-131057_gpt-5.5 — CLOSING ENTRY: MISSION GATE MET
ref: 20260710-180307_gpt-5.5
purpose: final close-out sweep on the fully-consistent tree (Noam's option (a))
variable changed vs ref: GT foundations q1.א header-strip only (prompt/model frozen)
config: gpt-5.5  k: 1  effort: medium
prompt_version: 3.3.1-tracehdr  suite_hash: 50994d2a97e3accf
validity: 5/5 valid
gate: 5/5 PASS — every gated metric 1.0 worst-case across all five fixtures.
predictions: CONFIRMED in full — foundations offline re-score confirmed live;
  hobby pedagogical clean (transport permitting — it permitted); bagrut third
  consecutive passing draw at 3.3.1.
cumulative evidence at close: bagrut 3/3 draws (k=2 + this); foundations 2 offline
  + 1 live; employee/csharp unbroken since Run A; hobby clean-transport cells 3/3
  (+5/5 pedagogical in Run C at 3.3.0). Confirmation bar: k=2+1 per Noam's amended
  ruling (mission spec was k≥5; the amendment is his, logged).
open items handed back: (1) retry-policy change — trigger ARMED (Run C: 5/5
  recurrence, $1.40 max trial), opens as its own pre-registered change;
  (2) Tier-B transient-transport retry (backlog; one blip = lost detection);
  (3) latent GT: bagrut q1.ב.1 mid-text header line (sub-threshold);
  (4) ungated text-fidelity tail unchanged (bagrut q1.ב.1 ratio .284/recall .071 = R4);
  (5) parked: answer-key marker-lines-as-furniture convention; (6) A6 guard re-run
  is Noam-side; (7) ~$4.4 budget remains.
loop arc: 1/5 (20260705) → 3/5 (Run A: instrument batch + GT A1–A3) → 4/5 (Run B:
  prompt nesting/verbatim/hl-routing) → R1+R2 rulings → 5/5 stable ex-R3 (Run C k=5)
  → R3 prompt fix + foundations GT consistency → 5/5 (this run). Instrument-first
  discipline held: of every "model failure" investigated this cycle, more were
  instrument/GT (csharp gloss, foundations color-drop+header, hobby 400, phantom
  render_loss, ped invariant, q3.ב split) than model (nesting, header-row, misroute).
cost: $1.70 this run  wall: 13:11–13:21
corrections: none. LOOP CLOSED — handing back to Noam.

## CHANGE 2026-07-11 — RULING: two-column convention = concatenation (standing); PR-2 formally closed
ruling: when a rubric table has two text columns, the criterion `description` is the two
  cells CONCATENATED "detail: label" (SECTION-3 prompt rule, unchanged since ≤3.1.0). This
  is the STANDING convention. PR-2 §2a (single-cell description + detail→evaluation_guidance)
  is SUPERSEDED — not pending, not deferred. This entry changes NO prompt/GT/scorer; it
  records, as an explicit findable convention, a ruling that was enacted piecemeal earlier.
why (three grounds):
  (1) scored-field coherence — concatenation keeps the detail column INSIDE `description`,
      matched at TEXT_TAU=0.85 (scoring.py) and feeding the gate-blocking
      criterion_recall/precision. §2a routes that detail into `evaluation_guidance`, which
      the scorer never reads: content carried but UNMEASURED — the exact incoherence class
      the PR-1 text-fidelity work exists to remove.
  (2) empirical — prompt and GT agree on concatenation; csharp criterion R/P = 1.0
      worst-case, stable across Run A/B/C (k=5). No open failure argues for §2a.
  (3) cost inversion — csharp GT is ALREADY concatenated (CHANGE 2026-07-09). Enacting §2a
      now would re-audit those 6 criteria BACK and split each into description+guidance —
      moving measured content into an unscored field. Net negative.
honesty / provenance gap (the reason to write this):
  - §2a's premise was TRUE when written (2026-07-06): csharp GT held the single component
    cell (label-only), desk-verified. CHANGE 2026-07-09 confirms it — it re-authored those
    6 descriptions "from label-only" to concatenated.
  - The GT re-edit WAS logged (2026-07-09, under "task A3") — but ONLY as a narrow GT-data
    fix. Never recorded until now: that it settles the two-column convention as
    concatenation going forward, and that it thereby SUPERSEDES PR-2 §2a (which stayed
    "pending" on paper). That missing convention-level linkage — a ruling enacted in
    GT+prompt yet never recorded AS a ruling — is precisely what forced the 2026-07-11 PR-2
    reconciliation forensics. (Corrects PR-A's framing that "no CHANGE entry existed": one
    did for the GT data; none did for the ruling.) See playbook §11 rule 3, amended in this PR.
  - P-C1..P-C4 (PR-2's predictions) were NEVER registered in PREDICTIONS.md. They are NOT
    backfilled — post-hoc registration is prediction laundering. The complete, honest record
    is: they were never registered, and the work they would have gated was overtaken by the
    R1–R3 loop.
PR-2 closure (all four edits accounted for):
  - §2a two-column → SUPERSEDED (opposite ruling ratified, above).
  - §2b structure faithfulness → SATISFIED IN SUBSTANCE. SECTION 2 FAITHFUL STRUCTURE covers
    the hobby body-vs-מחוון mislabel; the two never-reconcile tripwires (annotation_match +
    pedagogical_match, R2 ruling) guard the behavior regardless of SECTION-0-vs-SECTION-2
    placement. The SECTION-0 cardinal-rule generalization is PARKED (P-PARK-1 below).
  - §2c text-span teaching → SHIPPED AND EXPANDED (R1–R3: SECTION 1 splitting, table
    cell-encoding, given-code-as-context, verbatim pinning).
  - §2d version bump → SUPERSEDED by 3.3.1-tracehdr (via 3.2.0-textconv).
parked (named triggers; PR-A A3):
  - P-PARK-1 SECTION-0 cardinal-rule generalization of structure faithfulness. A prompt
    change purchased against ZERO observed failure. TRIGGER: a label-repair failure on a
    future fixture that SECTION 2's scoped rule misses. Until then, do not add it.
  - P-PARK-2 [IMAGE]-marker convention divergence. PR-1 GT convention keeps [IMAGE] markers;
    the prompt DROPS [IMAGE: ...] markers. Currently UNEXERCISED (PREDICTIONS P-T2: no
    populated GT text contains one). TRIGGER: first fixture with an image inside question
    prose — at which point re-rule JOINTLY (GT + prompt in ONE change), never one side alone
    (the two-column bug class).
by: Noam (ruling); recorded by agent (PR-A ledger closure).
affects: no run comparison invalidated (zero prompt/GT/scorer change). Closes PR-2;
  supersedes the "pending §2a" status wherever referenced.

## CHANGE 2026-07-11 — PIPELINE 3.0.0 → 3.1.0: point-mismatches non-retryable (PR B)
what: (1) pipeline.py _extract_with_retry: POINT_MISMATCH_* issues no longer
  TRIGGER a retry (new _is_point_mismatch guard on the trigger set). When only
  point-mismatches remain, they downgrade IMMEDIATELY via the UNCHANGED
  _downgrade_persistent_mismatches path → identical RUBRIC_MISMATCH_WARNING →
  identical rubric_mismatch annotation (type+anchor) via unchanged _build_response.
  Other retryable classes (EMPTY_SQ_TEXT, structure, duplicates, parse) unchanged;
  when they fire a retry, mismatches are re-evaluated post-retry exactly as before
  (feedback text incl. mismatch guidance untouched). Prompt UNTOUCHED —
  EXTRACTION_PROMPT_VERSION stays 3.3.1-tracehdr. (2) instrument, additive:
  results.json provenance now stamps pipeline_version FROM THE RUN
  (result.metadata), not the decorative config field — suite_hash does not cover
  pipeline.py, so this stamp is the change's only tree-drift signal.
  (3) tests: test_retry_policy.py — mismatch-only ⇒ exactly 1 LLM call + immediate
  downgrade + annotation; EMPTY_SQ_TEXT ⇒ still retries; mixed ⇒ one retry +
  mismatch downgrade @ correct anchor. Battery 39/39.
why: trigger armed and fired (Run C: 5/5 recurrence, $0.92/352s per burn, $1.40
  max). With both never-reconcile tripwires live, a "successful" retry on a
  faithful teacher error could only succeed by falsifying — pure cost + temptation.
  Residual value (genuine misread) unobserved corpus-wide; if one occurs it
  surfaces as the designed teacher-visible annotation.
by: Noam (PR B, pre-registered pipeline change); implemented by agent.
affects: ALL cost/latency comparisons vs pre-3.1.0 runs invalidated (accuracy
  comparisons unaffected if P-R2 holds). P-R1..R3 pre-registered in PREDICTIONS.md
  BEFORE the run. Verification run split pre-registered: all-5 × k=3 (~$3.75) =
  verification + NEW strip-down baseline (supersedes 20260711-131057) + bagrut
  3-consecutive-draw top-up.

## RUN 20260711-140120_gpt-5.5
ref: 20260711-131057_gpt-5.5 (5/5 close-out) — pipeline 3.0.0 → 3.1.0 is the ONE variable
purpose: PR B verification (P-R1..R3) + new strip-down baseline + bagrut draw top-up
config: gpt-5.5  k: 3  effort: medium
prompt_version: 3.3.1-tracehdr  pipeline_version: 3.1.0 (STAMPED FROM RUN — the new
  provenance channel announcing the change; suite_hash blind to pipeline.py as expected)
validity: 13/15; excluded: bagrut r0+r1 (Connection error at the extraction LLM call —
  transport, pre-validation; no policy involvement)
gate: 13/13 valid trials PASS.
predictions:
  P-R2 (KILL) HOLDS — zero gated-metric movement; 5/5 worst-run on every valid
  repeat; NO REVERT.
  P-R3 CONFIRMED (n=1 valid bagrut draw): rubric_mismatch@q1.א.2 annotation present;
  pedagogical emission byte-matches GT (pts:q1.2) — no-retry-policy surfaces identical.
  P-R1 PARTIAL: mean/doc $0.25 ✓ (predicted .25–.28; was .38). Worst-doc UNPROVEN:
  the single valid bagrut draw retried once — but the trigger was EMPTY_SQ_TEXT
  (legitimate non-mismatch class; falsifier condition explicitly NOT met; the
  mismatch rode along in feedback per spec). $0.908/299s for that draw. The
  mismatch-only no-retry branch was NOT exercised live this run (covered by the
  3 offline tests); the pre-change 5/5 mismatch-only pattern simply didn't recur
  in n=1 valid draws.
surprises: (1) bagrut transport fragility is now the dominant loss mode: 2/3 draws
  lost to Connection errors (longest trial ≈5 min = most exposed); extraction
  _call_llm has NO transient-transport retry (GraderAgent does) — same gap class
  as the Tier-B one, now 3 casualties across 3 runs. (2) NEW tension observed:
  EMPTY_SQ_TEXT fires on q1.א — a BRANCH sub-question whose GT text is null (the
  legal SECTION-8 pure-splitter shape). The validator can fight the prompt's own
  convention and burn a retry on a legitimate shape — same design-smell family as
  the mismatch retry. Candidate future change (pre-register first): exempt branch
  SQs (those with sub_questions) from EMPTY_SQ_TEXT.
decisions: baseline supersession PARTIAL — non-bagrut cost baseline solid at k=3
  ($0.16–0.22/doc, 0 retries anywhere); bagrut cost baseline n=1. Bagrut top-up
  (3 consecutive post-change draws) NOT met: 1/3 valid. Remaining budget ≈$1.1 <
  expected cost of 2 more full-suite draws — NOT spending; surfaced to Noam with
  options (top-up run w/ fresh budget ± a --only runner filter; and/or the two
  transport-retry gaps as the next pre-registered change).
cost: $3.26 ($0.25/doc-trial mean)  wall: 14:01–14:4x
corrections: none

## CHANGE 2026-07-12 — pipeline.py on_progress seam (PIPELINE_VERSION 3.1.0 → 3.2.0; PR-1)
what: additive observability seam in extract_rubric_from_docx: ProgressEvent
  (frozen pure-data dataclass) + optional on_progress callback, emitted at the
  existing log-line boundaries (render / per-attempt llm_call+validate / retry /
  build / pedagogical start+end / complete). Injected never imported; every
  invocation try/except-swallowed; payload pure data (no ORM/session). None
  default ⇒ byte-identical behavior — pinned offline by
  tests/services/test_extraction_job_seam.py (None-vs-callback identical dumps
  modulo the per-run uuid4 rubric_id; raising callback harmless; exact stage
  sequence). EXTRACTION_SYSTEM_PROMPT and EXTRACTION_PROMPT_VERSION UNTOUCHED
  (3.3.1-tracehdr); retry policy untouched.
why: PR-1 async job lifecycle persists mid-run progress on the job row; the
  runner owns persistence, the pipeline stays pure (bytes in → result out).
by: PR-1 spec (Noam-approved ADRs); executed by agent.
affects: no gated metric, no prompt-attributable comparison (prompt frozen;
  observability-only class). Full offline battery 39/39 green post-change.
  Runs stamp pipeline_version 3.2.0 from now on — a 3.2.0 stamp in the next
  run's provenance is this change announcing itself, not drift.

## CHANGE 2026-07-13 — PIPELINE 3.2.0 → 3.3.0: own the transport budget (PR-2)
what: pipeline.py transport policy, one bisectable unit.
  (1) BOUNDED CLIENTS: _llm_params now emits `timeout` (env EXTRACTION_LLM_TIMEOUT_S,
  default 360s) + `max_retries=0` for openai/anthropic. Gemini deliberately untouched
  (that branch is undeployable — langchain_google_genai is not installed).
  (2) ONE RETRY LAYER: _transport_retry_async/_sync (default 1 retry ⇒ 2 attempts)
  wrapping the ainvoke INSIDE the pipeline, with a predicate table:
  APIConnectionError/APITimeoutError/InternalServerError/RateLimitError ⇒ retry;
  `insufficient_quota` ⇒ TERMINAL with a billing message; 401/403/400 ⇒ TERMINAL;
  content/parse failures ⇒ re-raised untouched. Tier B uses the same layer (sync twin).
  (3) DEADLINE at THREE points: validation-loop entry (T+60), each transport attempt
  (T+10), and Tier-B entry (T+10 ⇒ else SKIP with the distinct string
  "Tier B skipped: time budget …"). Runner passes 840 − measured pre-work (monotonic).
  (4) PIPELINE_VERSION 3.3.0; llm_config provenance gains timeout_s/transport_retries/
  task_budget_s. Prompt UNTOUCHED (3.3.1-tracehdr).
why: the context sweep falsified "add retries". A retry layer ALREADY existed and was
  invisible (openai SDK max_retries=2 — LangChain passes None, so the SDK default
  applied); the TIMEOUT was INFINITE (LangChain passes timeout=None EXPLICITLY,
  overriding the SDK's own 600s default → httpx Timeout(None)). Measured consequence:
  one attempt ran 1736s (hobby_tvshow r1, retry_count=0) — 1.9× the entire 900s task
  budget, i.e. a guaranteed Cloud Run kill in prod. Every organic failure had ALREADY
  exhausted 3 SDK attempts, so attempts 4–9 were evidence-free; and all 3 observed
  429s were `insufficient_quota` — permanent billing, retried anyway because the SDK
  cannot discriminate it. So: bound it, disable the hidden layer, own one, fail fast
  on permanent conditions.
by: PR-2 spec (Noam); F1–F7 corrections surfaced by the agent and RULED by Noam before
  implementation (the spec's single-layer guard was unsound: a logical call is
  attempts×T, not T, so a call admitted at T+60 could still overrun by ~2×T and blow
  the very kill it existed to prevent. Deadline is now enforced at both layers, plus
  Tier-B. T ruled 360 not 300 on asymmetric-cost grounds: the distribution is bimodal
  (≤235s vs 1736s, nothing between), so the choice is insurance pricing, and a false
  timeout costs two attempts + a teacher-visible failure while the insurance costs 60s
  on a genuine hang).
affects: TRANSPORT/LATENCY/COST comparisons vs pre-3.3.0 runs are invalidated
  (accuracy comparisons unaffected if P-T3 holds). GATE UNTOUCHED BY CONSTRUCTION:
  the eval runner passes deadline_seconds=None ⇒ unbounded ⇒ no entry guard and no
  Tier-B skip; the deadline path is production-only. P-T1..T3 registered in
  PREDICTIONS.md BEFORE any k-run; T=360 is the #1 knob to watch. Battery green
  (gated metrics unmoved; policy-test expectations updated for the new params, exact-
  dict equality PRESERVED — the pin that caught the reasoning_effort drift stays a
  pin). 19 new transport tests incl. the fake-clock proof that an unaffordable retry
  is REFUSED, not started.
meta (schema-drift alarm, first real catch): migration 013's ledger fired
  "SCHEMA MISMATCH … NOT APPLIED" on its own unapplied migration. That is the alarm
  working, not an embarrassment — it is exactly the silently-wrong-prod species it was
  built to make loud. Applied before the PR-2 deploy.

## CHANGE 2026-07-13 — PR-3: Contract parity for the extended ontology (compiler + ALL grading consumers, ATOMIC)
what: the compiler and grader predated the ontology the extraction pipeline earned 5/5
  producing (selection groups, depth-2 nesting). Five changes, ONE atomic merge:
  (1) ContractCompiler: INV-2 RECURSIVE (mirrors pipeline._walk_sq; full-path target_id),
  INV-4 ACHIEVABLE-aware (compute_achievable_points), selection_groups PROPAGATED (the
  field existed with a docstring apologising for its own non-population), INV-6 WARNING
  -> INFO, error payload additive (invariant/expected/actual/real Hebrew).
  (2) gradable_compiler: scopes are LEAVES at any depth + parent-answer fallback.
  (3) NEW services/selection_scoring.py — the SINGLE selection-aware scorer.
  (4) grading_runner AND graded_test_contract_compiler (the approval gate) both consume
  it; neither re-sums scopes.
  (5) graded_by gains "excluded_by_selection"; ContractScopeOutcome gains counted_in_total.
why: two of five rubric archetypes could not compile at all — hard MVP dead-ends AFTER a
  successful extraction. Worse, the flat INV-2 MASKED the faithful teacher error at
  q1.א.2 (it fired at the parents, which sum to 0, and never visited the child) — the
  rubric gate was blind to the exact mistake it exists to surface. And if compiled
  anyway, a nested rubric dropped its inner scopes silently and a selection exam HALVED
  the student's grade (perfect employee answer = 50%).
ATOMICITY (the rule that dominated this PR): today's broken compiler was ACCIDENTALLY
  SAFE — its INV-2/INV-4 rejections made the grader's nesting-blindness and the
  halved-denominator bug unreachable (prod: 40/40 contracts flat + selection-free, so
  NOTHING corrupt ever shipped). A compiler-only fix would have UN-GATED both, turning
  two loud rejections into two silent wrong grades. Merged as one unit.
by: PR-3 spec (Noam) + F1-F4 corrections surfaced by the agent and RULED before code.
  F1 was load-bearing: the spec fixed ONE of the TWO score computations. The approval
  gate independently re-summed the denominator, so a selection grade would have been
  reviewed at 100% and FROZEN at 50% — a silent disagreement at the trust boundary,
  strictly worse than the honest rejection it replaced. Both sites now share one helper.
affects: GRADING OUTPUT for nested/selection rubrics is invalidated vs pre-PR-3 —
  which in prod is the EMPTY SET (no such contract has ever compiled), so no stored
  grade changes. Flat selection-free contracts are bit-for-bit unchanged (asserted).
  Eval suite UNTOUCHED BY CONSTRUCTION (zero pipeline contact) — ran anyway, green.
fourth consumer (B-5, folded in): the REVIEW PANEL was computing its own aggregate —
  runningTotal sums EVERY scope against the now-achievable denominator, i.e. the wrong
  numerator over the right one. Suppressed on selection exams; the server's figure is
  shown labelled "סה״כ סופי מחושב בשמירה (מבחן בחירה)" (a stale number rendered as
  CURRENT would be merely a different lie), per-scope points stay live. Invariant written
  into the component and pinned by vitest: never display an aggregate that could disagree
  with what approval would freeze; when it isn't computable client-side, show none. The
  real live best-k preview stays B-5 → PR-4 precisely because it is NOT a one-liner
  (exclusion can flip mid-edit) and must not be improvised into this merge.
fixture archaeology (the quiet proof of the whole PR): two long-standing fixtures encoded
  IMPOSSIBLE contracts — one declared total_points=10 while its scopes summed to 15,
  another paired a contract with a draft referencing a question the contract did not
  contain. They passed for months because the code RE-SUMMED scopes instead of trusting
  the contract; the tests had internalised the very worldview that produced the halved
  grade. Rebuilt as real contracts, their assertions came out UNCHANGED — the
  single-source principle validated from the archaeological record, not just from the
  new tests.
verification: 899371 now rejects with EXACTLY ONE error, invariant=INV-2,
  location=q1.א.2, expected=3, actual=2. csharp/hobby/foundations/employee compile CLEAN
  in ONE round trip (the ack dance is gone); employee's contract carries total_points=50
  (ACHIEVABLE, not the 100 offered) + its selection group. 182 backend tests green
  (21 new) incl. an override that FLIPS best-k membership and the byte-identical
  flat-contract regression; frontend 25 green, tsc clean.

  THE MILESTONE, in one line: extraction, the eval GT, Tier-A/B detection, and now
  compilation all independently point at the SAME teacher mistake at the SAME node —
  q1.א.2. The compiler's INV-2 error and the pipeline's own rubric_mismatch annotation
  finally agree. That convergence is what the three-week arc was for.

addendum 2026-07-14 (deploy day) — THREE consumers were silently dropping the payload,
  and every one of them made PR-3's actual outcome unreachable through the product while
  182 backend tests stayed green:
    (1) the WIZARD dropped selection_groups from the save body. The compiler was correct
        and the client was starving it of the one field that made it correct — prod would
        have answered a fixed selection exam with INV-4 expected=50 actual=100, i.e. the
        exact dead-end PR-3 exists to remove, now blamed on the fix.
    (2) the API duplicated the ENGLISH message into message_he. An RTL Hebrew UI would
        have shown a teacher an English sentence at the one moment it tells her she is
        wrong.
    (3) the WIZARD never rendered the error list. RubricErrorDisplay already showed node +
        numbers + Hebrew; page.tsx's catch collapsed all of it to "שגיאה בהכנת המחוון" —
        the precise diagnosis reduced to the generic banner it replaced.
  Then the LIVE E2E against the deployed service (deploy/e2e_pr3_archetypes.sh) found two
  MORE, both invisible to 200 passing tests, because the suite tested the compiler and the
  payload builder in isolation and never asked what survived the trip between them:
    (4) AnnotationSchema — a hand-maintained API MIRROR of Annotation — carried 5 of its 9
        fields. So prod answered the bagrut's real INV-2 violation with
        invariant=null expected=null actual=null and the ENGLISH string sitting in the
        field named message_he. The compiler had been right the whole time; the MIRROR was
        lossy. Two things conspired: a duplicate schema (a §0.4 violation), and my own
        getattr(err,...,None) defensiveness in the payload builder, which turned what
        should have been a type error into a SILENT TRUNCATION. Fixed by making the mirror
        total; pinned by a structural test that set-compares the two field lists so the
        NEXT added field cannot go missing. Deleting the mirror = B-10.
    (5) calculate_rubric_stats was the FIFTH re-summing site — Σ of every question's
        total_points, i.e. the OFFERED sum. It reported 100 for an exam achievable at 50,
        and the save path writes that number to the rubrics.total_points COLUMN: the row
        contradicted its own contract_json, and the rubric card advertised a total the
        grader would never award. It also counted only depth-1 criteria (a nested rubric's
        18 criteria reported as 6) — the same nesting-blindness INV-2 had. The contract's
        total is now passed in as authoritative and nothing is re-summed.
        BLAST RADIUS AUDITED: exactly 1 row, an E2E artifact of our own. All 41 real
        compiled rubrics agree with their contracts — because before PR-3 no selection exam
        could compile, so no teacher was ever exposed. The bug was born and killed the same
        day the feature that could reach it shipped.
  All five fixed and shipped inside PR-3 (a fix whose value cannot reach a teacher is not
  shipped). Recorded as a CLASS in BACKLOG.md, not five coincidences: when a PR changes
  what a payload MEANS, grep every producer and every consumer of that payload, and drive
  the real path once. A green backend suite proves the engine turns; it says nothing about
  whether the value reaches the teacher.
live E2E, deployed revision 00026-rx8, both archetypes GREEN:
  employee_course_select1 -> SAVED + COMPILED, stats.total_points=50.0 (achievable, not the
    100 offered), 18 criteria counted. The selection exam is no longer a dead end IN PROD.
  bagrut_899371 -> REJECTED 400 with exactly one error:
    location=q1.א.2  invariant=INV-2  expected=3  actual=2
    message_he="סעיף q1.א.2: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)"
  That payload is the answer to the PR-4 anchor question: the flat-list renderer already
  shows node + numbers + real Hebrew, so PR-4's anchor work is POLISH, not rescue.

## CHANGE 2026-07-19 — Phase 0 latency instrument (MISSION_rubric_extraction_latency; ADDITIVE)
what: additive latency measurement, confined to schemas.py/reporting.py/runner.py
  (the mission's one sanctioned suite edit). (1) schemas: StageTiming dataclass +
  RubricScore latency fields total_seconds/render_seconds/wall_seconds/input_tokens/
  output_tokens/stage_timings (all Optional, None-default). (2) runner: per-step
  wall-clocks via the EXISTING on_progress pure-data seam (injected, NOT a pipeline
  edit; failures swallowed) + a monotonic wall wrap (wall_seconds) as an independent
  cross-check of the pipeline's time.time() total; fields populated AFTER scoring
  (scorer immutable); NEW --only screening filter (default=all fixtures). (3)
  reporting: per-fixture median/max t_doc, headline=max-over-fixtures of median,
  tail=max-over-fixtures of max, per-step decomposition in summary + per-rubric report.
why: the suite measured cost, not time. The mission optimises latency; you cannot
  optimise what the instrument does not measure. Nothing about scoring/gating/prompt/
  model/pipeline behaviour changes — pipeline.py is byte-identical (on_progress is its
  own public seam; PIPELINE_VERSION unchanged at 3.3.0).
by: MISSION (Noam) Phase 0; executed by agent on branch perf/rubric-extraction-latency
  (commit efc92fc).
affects: suite_hash 50994d2a97e3accf -> 77db3bb9aea7658b. Pre-instrumentation runs are
  NO LONGER hash-comparable, but SCORES remain comparable (proven: score_only re-score
  of all 5 cached 20260711-131057 predictions is byte-identical on every scoring field;
  39/39 offline guards pass). reasoning_tokens/cached_tokens are NOT yet exposed (would
  need a pipeline _call_meta_from_raw touch) — deferred; noted for Phase 2. NO GT
  artifact touched. This entry is instrument-only; no LLM run, no gated-metric claim.

## RUN 20260720-131556_gpt-5.5 — INVALID-RUN (transport cascade)
ref: none (first instrumented baseline attempt, Phase 1 Block A)
purpose: baseline Block A (k=3, all 5) — noise band + latency model
variable changed vs ref: none (prod pin gpt-5.5/medium/3.3.1-tracehdr/pipeline 3.3.0)
config: gpt-5.5  k: 3  suite_hash: 77db3bb9aea7658b
validity: 1/15 valid — 14 INVALID (APIConnectionError after 2 transport attempts;
  network-level, NOT quota, NOT gate failures). Cascade: bagrut k0 OK, then every
  trial after failed → a sustained connectivity window, not isolated blips.
  Post-run csharp k=1 probe (20260721-134442) PASSED → window was transient, cleared.
latency (n=1 valid, attribution only): bagrut k0 t_doc=451.2s, llm=450.9s (99.9%),
  render=0.35s, out_tok=25691, retries=1, $0.956. Confirms bagrut = headline fixture,
  decode-dominated, retries (EMPTY_SQ_TEXT branch-SQ mechanism); the retry ≈ one full
  extra ~225s call ≈ half of t_doc — the L1 lever's headline target.
decisions: retain bagrut k0 as valid attribution; relaunch baseline (reserve covers
  one transport re-run, mission §4). No baseline/noise-band computable from n=1.
cost: ~$0.96 this run (failed calls ~$0). Running total ~$1.30 of $35.
corrections: none

## RUN 20260721-134812_gpt-5.5 — baseline Block A2 (VALID)
ref: none (first valid instrumented baseline block, Phase 1)
purpose: baseline block 1/2 — latency model + 5/5 reproduction
variable changed vs ref: none (prod pin gpt-5.5/medium/3.3.1-tracehdr/pipeline 3.3.0)
config: gpt-5.5  k: 3  suite_hash: 77db3bb9aea7658b
validity: 15/15 valid; gate: 15/15 PASS (5/5 fixtures × 3) — baseline reproduces 5/5.
latency (t_doc median | max, s): bagrut 220.4 | 432.0 · foundations 107.8 | 114.8 ·
  hobby 110.3 | 112.3 · csharp 77.6 | 84.2 · employee 76.0 | 82.8. HEADLINE (max-over-
  fixtures of median) = bagrut 220.4s. Decode-dominated: t_doc≈render(~0.1-0.35s)+llm;
  local overhead ~1ms. t_doc ≈ output_tokens / ~57 tok/s.
key: bagrut retry (EMPTY_SQ_TEXT on the null-text BRANCH sub-question, a legitimate
  SECTION-8 splitter) fired 1/3 here (k0), 2/4 across both blocks; when it fires,
  out_tok ~doubles (11.6k→25.7k) and t_doc ~doubles (185→432). This is the L1 lever's
  quantified target — the single largest movable term on the headline fixture.
cost: $4.21 this run ($0.281/doc-trial mean). Running total ~$5.51 of $35.
corrections: none

## RUN 20260721-142212_gpt-5.5 — baseline Block B (VALID)
ref: 20260721-134812 (Block A2) — SAME tree (no variable changed); 2nd block for noise band
purpose: baseline block 2/2 — between-block run-to-run noise band
config: gpt-5.5  k: 3  suite_hash: 77db3bb9aea7658b
validity: 15/15 valid; gate: 15/15 PASS (5/5 × 3).
latency (t_doc median, s): bagrut 413.9 · foundations 119.2 · hobby 104.4 · csharp 76.2 · employee 76.8.
noise band (between-block median spread A2 vs B): csharp 1.8% · employee 1.1% · hobby 5.6% ·
  foundations 10.6% · bagrut 104.7%. Clean-fixture noise floor ~1-11% (decode nondeterminism);
  MDE (2×) ~2-22%. bagrut's 105% is RETRY-DRIVEN: retry fired 3/3 here vs 1/3 in A2 (5/7 across
  both blocks). The retry is the dominant latency AND variance source on the headline fixture.
key: bagrut retry present ⇒ ~393-451s (out ~24-26k); absent ⇒ ~186-220s (out ~12k). ~2× switch.
cost: ~$5.05 this run. Running total $10.56 of $35 (32 valid billed trials). BASELINE COMPLETE —
  no further paid runs (scope: baseline + attribution + pre-register, then stop).
corrections: none

## CHANGE 2026-07-21 — FINDING: unrelated commit 64fa19a on the perf branch (NOT authored by this mission)
what: `git log main..HEAD` shows TWO commits: efc92fc (mine, the 3-file latency instrument) and,
  ON TOP of it, 64fa19a "PR-5: document mirror (Sprint 2) + async capture flow (Sprint 1)" — 46
  app/frontend files. It was committed by another actor during this mission's background baseline
  runs (the repo had large uncommitted PR-5 working-tree changes when the perf branch was cut).
impact: touches NO immutable-set file (targeted `git diff --name-only main...HEAD -- <immutable>`
  is EMPTY; all 5 benchmarks byte-identical to the pre-mission sha snapshot) ⇒ gate integrity intact.
  It only pollutes the branch's file list. NOT reset/rebased away: I did not author it and it may be
  wanted work (operating rule: don't delete what you didn't create — surface it). Handed to Noam.

## CHANGE 2026-07-23 — PIPELINE 3.3.0 → 3.4.0: P-L1 branch-SQ EMPTY_SQ_TEXT exemption
what: pipeline.py _validate_extraction — the EMPTY_SQ_TEXT check gains `not sq.sub_questions`
  so it fires ONLY on LEAF sub-questions. A branch/splitter SQ (carries sub_questions,
  legitimately null text per SECTION-8) no longer raises the retryable issue. PIPELINE_VERSION
  3.3.0→3.4.0. Prompt/GT/scorer/config UNTOUCHED. Immutable test_retry_policy still green
  (its EMPTY_SQ_TEXT cases use LEAF SQs — unaffected). All 39 guards pass.
why: P-L1 (pre-registered PREDICTIONS.md). bagrut's false EMPTY_SQ_TEXT retry fires ~71% of
  baseline draws, ~doubles the doc (186→414s), and drives its 105% variance.
protocol (gate owner ruling, 2026-07-23): k=1 per lever (screening, NON-PROMOTABLE — cannot
  distinguish safe from lucky), then ONE k=3 all-5 validation on the winning config only, to
  save spend. Amends the mission's k=5/k=8 bar; logged as the owner's ruling. Stop on 403.
by: owner (Noam) authorized; implemented by agent. Run entry follows.

## RUN 20260723-154310_gpt-5.5 — P-L1 screen (k=1 all-5, NON-PROMOTABLE)
ref: baseline 20260721-134812/-142212. ONE variable: pipeline 3.3.0→3.4.0 (P-L1). config gpt-5.5 (medium).
purpose: screen P-L1 (branch-SQ EMPTY_SQ_TEXT exemption). k=1 per owner protocol.
validity: 5/5 valid; gate: 5/5 PASS. pipeline_version 3.4.0 stamped.
result: P-L1 CONFIRMED (k=1 signal). bagrut retries=0 (was ~71% of draws → the false retry is
  structurally gone), t_doc 206.3s vs baseline median 413.9s = -50.2% HEADLINE reduction; out_tok
  13135 vs retry-present ~25.7k (halved). Other fixtures within noise (csharp 63.5, employee 65.3,
  foundations 108.5, hobby 114.6). NO gated regression on any fixture.
predictions: P-L1 CONFIRMED at k=1 (headline -50%, retry→0, 0 gated move). Clears 30% target + 50%
  stretch. k=1 cannot distinguish safe from lucky — the k=3 validation is the confirmation.
cost: $1.30 this run. Running total ~$11.86 of $35.
next: screen P-L6-low (effort=low on the L1 pipeline) — the risky Tier-2 lever; watch bagrut gate.
corrections: none

## RUN 20260723-155345_gpt-5.5-low — P-L6-low screen (k=1 all-5, NON-PROMOTABLE) — FALSIFIED
ref: P-L1 screen 20260723-154310. ONE variable: reasoning_effort medium→low (config gpt-5.5→
  gpt-5.5-low). SAME L1 pipeline 3.4.0.
purpose: screen effort=low (biggest raw decode knob, Tier-2 accuracy-risky).
validity: 5/5 valid; gate: 4/5 — bagrut FAILS.
result: P-L6-low FALSIFIED — KILL criterion fired (pre-registered). bagrut gate=False on SIX
  metrics: annotation_match=False + pedagogical_match=False (the never-reconcile tripwires — the
  model RECONCILED the 1.5+0.5-under-3 teacher error, silencing both the rubric_mismatch
  annotation and the Tier-A point_sum_mismatch), subquestion_structure_match=0.929,
  criterion_recall/precision=0.967, point_exactness=0.987, example_solution_fidelity=0.188.
  bagrut out_tok 10259 (was 13135@medium), t_doc 152s — faster but BROKEN. Clean fixtures held
  5/5 and were much faster (csharp 46.8, employee 52.7, foundations 52.9, hobby 78.8; out ~2.8-4k).
decision: REVERT — do NOT stack effort=low. WINNER = L1-only at effort=medium. config gpt-5.5-low
  marked FALSIFIED in its note (kept as experiment record). One clear multi-metric gate break
  FALSIFIES at k=1 (killing needs 1 failure; confirming safety needs k≥5).
predictions: P-L6-low predicted-risk CONFIRMED — effort=low reconciles the faithful error exactly
  as registered. The decode knob trades away the one property the product exists for.
cost: ~$0.79 this run. Running total ~$12.65 of $35.
next: k=3 all-5 VALIDATION on the winner (gpt-5.5 medium, L1 pipeline 3.4.0).
corrections: none

## RUN 20260723-160327_gpt-5.5 — P-L1 k=3 validation — INCOMPLETE (billing quota, insufficient_quota 429)
ref: baseline 20260721-134812/-142212. Winner config gpt-5.5 (medium) on L1 pipeline 3.4.0.
purpose: k=3 all-5 validation of the winner (owner's amended confirmation bar).
validity: 1/15 valid — 14 INVALID (OpenAI insufficient_quota 429, billing quota exhausted;
  permanent/not-retryable, caught by the PR-2 fast-fail predicate). Only bagrut k0 completed.
result: bagrut k0 t_doc=191.2s, retries=0, gate PASS (out 12510) — a 2nd confirming L1 bagrut
  draw (with the k=1 screen's 206.3s). STOPPED per owner instruction (stop on billing quota).
status: P-L1 CONFIRMED at SCREENING (k=1 all-5 5/5; 2 bagrut L1 draws 206.3/191.2s retry=0,
  median 198.8s = -52.0% vs baseline 413.9s; delta 215s >> 2× noise). FORMAL k=3×5 validation
  BLOCKED by billing — RE-RUN needed when quota restored (config gpt-5.5, pipeline 3.4.0).
  P-L6-low remains FALSIFIED. Winner = L1-only (medium).
cost: total session spend $13.33 of $35 (quota now exhausted).
corrections: none

## RUN 20260723-162200_gpt-5.5 — P-L1 k=3 all-5 VALIDATION — CONFIRMED (owner k=3 DoD met)
ref: baseline 20260721-134812/-142212 (headline 413.9s). Winner: config gpt-5.5 (medium), L1
  pipeline 3.4.0. ONE variable vs baseline: pipeline 3.3.0->3.4.0 (P-L1). suite_hash 0890967969239e3f.
purpose: formal k=3 all-5 validation (owner's amended confirmation bar; re-run after billing restored).
validity: 15/15 valid; gate: 15/15 PASS (5/5 x 3), 0 INVALID.
result: P-L1 CONFIRMED. bagrut retries=0 on ALL 3 draws (t_doc 195.4/194.7/175.3s), median 194.7s
  vs baseline 413.9s = -53.0% HEADLINE (clears 30% target + 50% stretch; delta 219s >> 2x the 1-11%
  clean-fixture noise band). bagrut's baseline 105% retry-driven variance is GONE (three tight draws
  175-195s). Other fixtures within noise, no regression (csharp 64.3, employee 64.0, foundations 106.0,
  hobby 99.3). Cost/doc DROPPED (bagrut ~$0.45 vs baseline ~$0.96 retry-present) — latency win that
  also saves money, not a trade.
verdict: PROMOTABLE per owner k=3 bar. Honest power: 3 clean draws/fixture is weaker than the
  mission's k=8 (bounds per-trial failure loosely, ~<10% rule-of-three over 15 trials) — an explicit
  owner budget tradeoff; NOT "proven identical".
cost: $3.80 this run. Total session $17.12 of $35.
corrections: none

## CHANGE 2026-07-25 — GT hobby_tvshow q2.ב faithful completion (one error, TWO surfaces)
what: q2.ב total_points 45 -> 29 (faithful: teacher declared LowestRateChannel "סה"כ 29" — 45 is only
  the lumped sum, never written). PrintLowRatingChannel (16 pts) STAYS under ב (mislabeled), per
  faithful extraction. GT now documents the ONE teacher error (mislabel) on BOTH surfaces:
  - pedagogical_mistakes: structural_mislabel@q2 [Tier-B, existing] + point_sum_mismatch@q2 (44 vs 60)
    + point_sum_mismatch@ב (45 vs 29) [Tier-A, TRANSCRIBED from a probe of the faithful draft].
  - annotations: rubric_mismatch@q2 + rubric_mismatch@q2.ב [TRANSCRIBED from the faithful draft].
why: FAITHFUL-CAPTURE ruling (2026-07-25, Noam): preserve exactly what the teacher wrote + surface
  every resulting inconsistency; never invent a consistent total, never move the criterion. Reverting
  to 45 would HIDE the arithmetic shadows and invent a total the teacher never wrote (silent-repair
  anti-pattern). The single teacher fix (reassign criterion to ג) resolves all shadows at once.
by: Noam (ruling); transcribed by agent via live Tier-A + faithful-draft probe.
affects: test_fp123 GREEN (39/39 guards). The GT file ALSO carries a concurrent [TABLE] question_text
  change by ANOTHER agent (unrelated, preserved) — hobby_tvshow.json left UNCOMMITTED in the working
  tree so as not to entangle that agent's in-progress work; commit it once the [TABLE] work settles.
  Principle recorded (generalized) in CLAUDE.md §2 + RUBRIC_EVAL_PLAYBOOK.md §4.


## CHANGE 2026-07-25 — prompt 3.4.0-tablemarkers -> 3.5.0-solutiontables (solution tables render as tables)
what: SECTION 4 FILLED trace/solution-table rule REVERSED from flatten-to-cell-text to
  PRESERVE-AS-[TABLE]-MARKDOWN (marker + header + separator + value rows, empty cells kept,
  [[color]]/[[hl]] ink stripped) — symmetric with the SECTION 1 context-table rule. The
  HEADER ROW EXCLUSION sub-rule (2026-07-10) is REVERSED to HEADER ROW INCLUSION: the
  solution table keeps its header, so it renders as a self-labeled table. Added a 1x1-table
  EXCEPTION (SECTION 1 + 4): a single-cell table is a code/prose CONTAINER, not a grid —
  unwrap it (drop marker + pipes, keep the cell content) so model-solution code the teacher
  wrapped in a 1x1 table is not marked/rendered as a table.
why: example_solution trace tables rendered as plain monospace in RubricDocument
  (SolutionBlock used CodeBlock). Now SolutionBlock routes [TABLE]-bearing solutions through
  DocumentText (marker-aware); code solutions stay CodeBlock; stripColorMarkers also [[hl]].
gt: 3 example_solution tables marked to full form from the render, colors/hl stripped,
  trailing all-empty rows trimmed — bagrut q1.A.1 [TABLE 3: 6x5], bagrut q1.B.1 [TABLE 5: 11x4]
  (red prose kept around it), foundations q1.A [TABLE 1: 11x9]. 1x1 code solutions unchanged.
safety: example_solution_fidelity is gated but scored by nz.ratio >= 0.85; GT + prompt moved
  together. VERIFIED by k=1 live trials (gpt-5.5): bagrut gate PASS fidelity 1.000; foundations
  gate PASS fidelity 1.000 (q1.A [TABLE] marked, q2/q3.B code UNWRAPPED no marker).
by: Noam (D1 include-header + D2 conditional-render + D3 hl-strip rulings); agent implemented.
affects: test_fp123 GREEN (39/39); frontend vitest GREEN (199); tsc clean.


## CHANGE 2026-07-25 (follow-up) — 1x1-table unwrap moved to parser_render (strongest safeguard)
what: The 1x1-table EXCEPTION (single-cell container -> cell content, no [TABLE] marker) is now
  enforced DETERMINISTICALLY in parser_render._render_table, not just via the prompt. A 1x1 table
  emits ONLY its cell content (no marker/separator/pipes; real | kept un-escaped; same contrast
  baselines so teacher ink is unchanged). The LLM never SEES a [TABLE 1x1] marker, so it cannot
  preserve one; the GT slicer and review UI never receive one either. The prompt 1x1 exception +
  DocumentText 1x1 guard are KEPT as defense-in-depth.
scope: corpus survey — ONLY foundations has 1x1 tables (q2, q3.B, both model-solution code);
  bagrut/csharp/employee/hobby have ZERO. table_index is consumed in the main loop, so unwrapping
  does NOT renumber downstream markers (GT [TABLE 1: 11x9] etc. unchanged). Also IMPROVES the gate:
  GT foundations q2/q3.B hold the unmarked code, so a marker-less extraction matches more cleanly.
verify: 0 [TABLE ...: 1x1] remain in any of the 5 renders; no code leak into question_text
  (generator preview); test_fp123 39/39; frontend vitest 199; tsc clean; k=1 foundations gate PASS
  fidelity 1.000 (q1.A [TABLE 1: 11x9] still marked; q2/q3.B code UNWRAPPED, no marker).
by: Noam (proposed the parser-level safeguard); agent implemented.


## CHANGE 2026-07-26 — prompt 3.5.0-solutiontables -> 3.6.0-scaffoldsplit (trace-scaffold dual emission)
what: SECTION 4 — a teacher-FILLED table now gets a ROLE decision by JUDGEMENT (contrast ink is a
  HINT, not a rule; classify by role, SECTION 3). Three outcomes: (a) colored cells ARE an answer-fill
  of a table the student was to complete -> DUAL emit: filled table -> example_solution AND the blank
  SCAFFOLD (answer cells emptied) -> question_text; (b) colored cells are mere emphasis on a given data
  table -> whole table -> question_text context; (c) table under a solution label (teacher own working)
  -> example_solution only. Fixes the trace scaffold being ABSENT from question_text (Failure #2 — the
  teacher never saw the empty trace table).
why: the 3.5.0 rule mentioned the scaffold only as a descriptive parenthetical, never imperative, so the
  LLM routed the one filled table to example_solution and dropped the scaffold.
gt: NO change — GT already encodes the target (q1.A.1 text has [TABLE 3: 6x5] header + 5 empty rows; its
  example_solution has the filled block). Prompt-only.
verify: test_fp123 39/39; k=1 bagrut gate PASS, example_solution_fidelity 1.000, question_text_fidelity_min
  1.0. q1.A.1 text NOW carries the empty [TABLE 3: 6x5] scaffold; example_solution the filled one.
  WATCH: q1.B.1 sub_text ratio 0.2292 — the shared What code+array landed on the PARENT q1.B (GT puts it on
  child q1.B.1); array [TABLE 4] preserved + renders — a context-placement variance (Failure #1 class),
  ungated, single-run, not cleanly attributable to the change vs LLM noise.
by: Noam (prompt-only, judgement-based ruling); agent implemented.

## CHANGE 2026-07-30 — pipeline 3.4.0 -> 3.5.0 (PR-6 backend: Step 2c becomes consumable)
what: three coupled changes to what Step 2c EMITS, landed as ONE pipeline change because
  they share a version, a battery and a GT canon.
  (a) A2 — point-sum mistakes now carry a real SuggestedFix (operation='adjust_points',
      params={target, field, new_value, current_value} taken from the SAME evidence).
      new_value is the node's own children-sum: nothing invented. requires_teacher_input
      STAYS True — the ruling on record: it means "never apply without the teacher", and a
      one-click PROPOSAL she must click is that flag implemented, not overridden.
  (b) A2b — sub-question mistakes anchor on the FULL PATH (q1.A.2) via a new
      _walk_sub_questions walker; Question.all_sub_questions flattens and drops the parent
      chain, which is why the bare id shipped. The bare id was unpairable with its own live
      blocker and ambiguous across questions (every question has an aleph).
  (c) A5 — advisory-scan status stamped into extraction_metadata
      (advisory_scan: complete|partial, advisory_scan_reason: tier_b_skipped_time_budget |
      tier_b_disabled | detector_failed). Provenance belongs with provenance, and unlike a
      job-row warning it SURVIVES into the saved draft, so partial-scan honesty cannot
      silently vanish on reopen. No stamp at all (older drafts) = unknowable, never
      "complete".
DEVIATION from the directive, on record: selection_normalization KEEPS suggested_fix=None.
  The directive said "all four Tier-A sites"; the fourth has no correction to propose —
  normalization intent is unknowable (equalise? drop? scale?) and the model's own contract
  reserves requires_teacher_input for exactly that. Emitting adjust_points there would
  fabricate a number the teacher never wrote (FC). It stays card variant 3 (info-only).
gt: pedagogical canon RE-TRANSCRIBED via the probe method (TierA(faithful draft) union
  expected-Tier-B), never by hand — bagrut pts:q1.2/target '2' -> pts:q1.A.2/target 'q1.A.2';
  hobby pts:q2.B target 'B' -> 'q2.B'; employee hand-written id -> the detector's real
  selnorm:sg0. Tier-B hobby_q2_mislabel preserved verbatim (conf 0.9). pedagogical_match is
  scored on (kind, target_id), so the canon had to move atomically with the emission.
verify: rubric_eval_suite 39/39 (5/5 fixtures hold); new offline contract battery
  tests/services/test_pedagogical_fix_payload.py 8/8; extraction_job_seam + transport_budget
  27/27. PRE-EXISTING RED, unrelated and confirmed by stashing to HEAD:
  test_contract_parity::test_golden_drafts_compile_clean_in_one_round_trip[hobby_tvshow] —
  hobby GT deliberately carries the faithful teacher error (q2 44 vs 60), so it cannot
  compile clean; that test predates the GT change and is stale, not caused here.
by: Noam (rulings A2/A2b/A5 + pipeline discipline); agent implemented.

## 2026-07-31 — CHANGE: the general fix wire (EditSteps) + per-question Tier-B batching (D1–D8)
what: PIPELINE_VERSION 3.5.0 -> 3.6.0. Noam's rulings D1–D8 implemented end to end:
  (a) THE WIRE — SuggestedFix gains `steps: List[EditStep]` (ontology EDIT_OPS =
      set_points | move_criterion | move_text over the dotted scope-path vocabulary;
      op leash is a field_validator, one place). A fix is an ordered plan applied
      ATOMICALLY by the client (frontend utils/edit-steps.ts, ONE interpreter; every
      mutation routes through the pure *AtPath ops). `params` demoted to the legacy
      shape (pre-3.6.0 drafts; client translation arm keeps them working). A move
      to_scope that doesn't exist is AUTO-VIVIFIED (how "create missing סעיף ג" is
      expressed without a create op); a vivified node with no explicit set_points gets
      points := Σ of the criteria moved into it (deterministic bookkeeping — observed
      live: the model emits the moves and forgets the set_points).
  (b) TIER-B BATCHING (D6) — one structured call PER ANOMALOUS QUESTION carrying ALL
      its anomalies (structural trigger + point mismatches + precomputed sums/deltas +
      indexed criteria + verbatim sub-question texts). Output QuestionAdjudication
      {findings:[{kind, target_id, explanation, fix{description, steps}, resolves,
      confidence}]}; strict-valid by construction (walked in test_tier_b_schema_strict_valid).
      Tier A stays the only DETECTOR of point-sum facts; Tier B only chooses fixes.
      Degrade: llm=None / budget / failure keeps the deterministic adjust-declared
      fallback fix on every mismatch (pre-D6 behaviour, never no-fix).
  (c) SUBORDINATION (D3) — PedagogicalMistake gains `explained_by`; a shadow whose
      root-cause fix resolves it carries the link and NO local fix (the client refuses
      to resurrect one even from the evidence fallback). The UI card points at the root.
  (d) PROMPT — rewritten _TIER_B_SYSTEM: decision ladder (reassign-by-delta > single
      typo > round 1–2 children to declared [D1 default, halves permitted D2] >
      justified declared-override), root-cause principle, verbatim-quote rule for
      move_text, and OUTPUT-VOICE contract (standalone feminine display copy, never an
      answer to a question — kills the live "כן. ..." phrasing; the old user prompt
      literally ended with a yes/no question). User prompt is task-framed with
      precomputed arithmetic — the model corroborates, never computes.
gt: hobby pedagogical canon updated in lockstep — root renamed to the detector's real
  adj:q2:structural_mislabel with the full D5 steps plan (move_text carve is the exact
  substring of ב's text incl. the double space); pts:q2 + pts:q2.ב subordinated
  (explained_by set, suggested_fix null). pedagogical_match scores (kind, target_id) —
  unaffected. GT rewritten via model round-trip (model_dump_json indent=2), which also
  normalized the mixed str/num points to canonical strings.
verify: rubric_eval_suite 39/39 + fix-payload battery green; frontend 390/390 + tsc +
  next build clean (new edit-steps battery proves the hobby full fix settles ALL of
  q2's arithmetic in one click, atomicity, vivify, verbatim-carve refusal). LIVE k=1
  Tier-B trial via pipeline._make_adjudicator on the hobby draft: first-shot success —
  root cause found (conf 0.9), BOTH shadows resolved via `resolves`, verbatim carve,
  clean standalone explanation, moves-only plan (the bookkeeping backstop covers it).
by: Noam (D1–D8 + the steps-wire approval); agent implemented.

## CHANGE 2026-08-15 — xai provider branch (PIPELINE 3.6.0 → 3.6.1) + configs/grok-4.6.json
what: (1) pipeline.py — additive `xai` provider: _llm_params xai branch (reasoning-family
  policy: temperature OMITTED, max_tokens default 32k, reasoning_effort passed only when
  set, PR-2 bounds timeout+max_retries=0 — same SDK as openai, same hidden layer to
  disable); _get_llm constructs ChatOpenAI against https://api.x.ai/v1 with a REQUIRED
  XAI_API_KEY (no silent OPENAI_API_KEY fallback). Zero behavior change for
  openai/anthropic/gemini; PIPELINE_VERSION bumped 3.6.0→3.6.1 purely so the provenance
  stamp announces the pipeline-code change (suite_hash is blind to pipeline.py).
  (2) NEW configs/grok-4.6.json — provider xai, prices 2.00/6.00 per 1M (xAI pricing page
  2026-08-15, <=200K tier; cached-input rate not modeled — pipeline doesn't split cached
  tokens, so cost is a conservative upper bound), cost_ceiling 2.0, effort null.
  (3) test_llm_policy.py — xai pins added: param policy, sweep-config price pairing
  (grok-4.6/xai/2.00/6.00), construction wiring (base_url + api_key + bounds).
why: model sweep — grok-4.6 candidate vs the gpt-5.5-medium prod pin; k=2 trial ordered
  by Noam (2026-08-15).
by: Noam (trial order); agent implemented.
affects: suite_hash shifts next run (test_llm_policy.py edited; configs are hash-excluded).
  pipeline_version stamps 3.6.1 from now on — a 3.6.1 stamp is this change announcing
  itself, not drift. No prompt/GT/scorer change; no run comparison invalidated. Battery
  40/40 green post-change (incl. the 3 new xai pins).

## RUN 20260815-173146_grok-4.6 — SMOKE, ABORTED (xAI billing; $0 spent)
ref: none (first xai-provider run ever)
purpose: repeats=1 --only employee_course_select1 screening smoke (config-note discipline:
  verify parse + finish_reason before the k-run)
variable changed vs ref: n/a (new provider branch under test)
config: grok-4.6  k: 1 (screening subset — NON-PROMOTABLE)
validity: 0/1 — INVALID (PermissionDeniedError 403: xAI team has no credits/licenses)
gate: 0/1 (invalid)
surprises: none mechanical — auth reached x.ai, request was well-formed, and the PR-2
  fast-fail predicate correctly classified the billing 403 as TERMINAL (0 retries, $0).
  The xai wiring is proven up to the paywall.
decisions: HALT — credits are Noam's purchase (console.x.ai). On credits: re-run this
  smoke, then the ordered k=2 all-5 trial vs ref 20260723-162200_gpt-5.5 (last full-suite
  gpt-5.5-medium k=3 15/15; note confound: tree has since moved prompt 3.3.1→3.7.0-tabledir,
  pipeline 3.4.0→3.6.1, GT hobby/bagrut/foundations edits — model comparison is
  cross-tree, not single-variable).
next: awaiting xAI credits — kill criterion unchanged from the smoke discipline (parse
  success + non-null finish_reason on all fixtures).
cost: $0.00  wall: <1 min
corrections: none

## RUN 20260815-173636_grok-4.6 — SMOKE #2, INVALID (per-attempt timeout at T=360)
ref: 20260815-173146 (smoke #1, billing 403 — credits since purchased by Noam)
purpose: repeats=1 --only employee_course_select1 screening smoke, post-credits
config: grok-4.6  k: 1 (screening subset — NON-PROMOTABLE)
validity: 0/1 — INVALID (ExtractionError: 2 transport attempts, both APITimeoutError at
  the PR-2 default T=360s)
gate: 0/1 (invalid)
surprises: grok-4.6 needs >360s/attempt on the EASIEST fixture (employee — gpt-5.5-medium
  does it in ~64s). Either genuinely slow reasoning/decode or pathological generation;
  indistinguishable from a timeout alone.
decisions: retry smoke ONCE with EXTRACTION_LLM_TIMEOUT_S=900 (env knob, PR-2's
  designated #1 knob; recorded here because it travels ambient env, not the config).
  If it completes → real-latency datum, proceed to k=2 with the same env. If it times
  out again at 900 → pathology; STOP and surface (do not burn the k=2 budget).
cost: ~$0 metered by us (timed-out calls carry no usage back; xAI-side billing for
  abandoned generations unknown — watch the $5 balance)
corrections: none

## RUN 20260815-174922_grok-4.6 — SMOKE #3, INVALID (timeout at T=900) → pathology confirmed
ref: 20260815-173636 (smoke #2, T=360 timeout)
purpose: smoke retry at EXTRACTION_LLM_TIMEOUT_S=900 (pre-registered: complete ⇒ latency
  datum; timeout again ⇒ pathology, STOP)
config: grok-4.6  k: 1 (screening subset — NON-PROMOTABLE)
validity: 0/1 — INVALID (2 transport attempts, both APITimeoutError at 900s; httpx trace
  shows the server never returned response HEADERS)
gate: 0/1 (invalid). Kill criterion FIRED — k=2 NOT launched on this tree.
decisions: diagnostic probe ladder OUTSIDE the suite (tiny direct API calls, ~$0.03):
  (1) /models lists grok-4.6 (id valid); (2) tiny plain completion 1.7s; (3) tiny
  json_schema 3.9s; (4) FULL RubricExtraction strict schema + tiny prompt 6.3s
  (response_format) / 5.9s (tools) — recursive $refs INNOCENT; (5) REAL prompt
  (22.9k-char system + 6.8k-char render) + schema, non-streaming, max_tokens=8000:
  HANG >600s; (6) REAL prompt NO schema non-streaming max_tokens=1500: HANG 620s;
  (7) REAL prompt + schema STREAMED: TTFT 1.5s, complete 156s, 1613 chunks.
attribution: x.ai's NON-STREAMING response path hangs on large-prompt/long-generation
  requests, independent of schema — transport/provider defect, not model, not
  instrument. Secondary finding: decode ~10 tok/s on the real workload (1500 tok in
  156s) vs gpt-5.5 ~57 tok/s — trials will be LONG even once unblocked.
next: pipeline 3.6.2 (xai streaming) + re-smoke at T=1800 — kill criterion: smoke must
  return a VALID scored record (any gate result) with non-null finish_reason + usage.
cost: ~$0.03 (probes)  wall: ~50 min incl. diagnosis
corrections: none

## CHANGE 2026-08-15 — PIPELINE 3.6.1 → 3.6.2: xai branch streams (empirically forced)
what: _get_llm xai branch now constructs ChatOpenAI(streaming=True, stream_usage=True).
  LangChain aggregates the streamed response; usage rides stream_options.include_usage.
  Other providers untouched. test_llm_policy xai wiring pin updated (exact-dict style
  preserved). Battery 40/40 green.
why: probe-proven (previous entry): x.ai non-streaming hangs on real extraction
  workloads; streaming returns TTFT 1.5s on the identical request. Without this the
  ordered k=2 trial cannot run at all.
by: agent (fix confined to the experimental xai branch; prod pin untouched — openai
  path byte-identical); trial itself ordered by Noam 2026-08-15.
affects: pipeline_version stamps 3.6.2. suite_hash shifts (test_llm_policy edit).
  WATCH on the smoke: finish_reason + usage must survive stream aggregation (if usage
  comes back 0/None, cost_usd=None and the gate's cost criterion silently vacuates —
  that would need its own fix before any cost claim).

## RUN 20260815-184729_grok-4.6 — SMOKE #4 (streaming, T=1800): VALID — transport SOLVED
ref: 20260815-174922 (smoke #3) + CHANGE pipeline 3.6.2
purpose: verify the streaming fix end-to-end (kill: valid record + finish_reason + usage)
config: grok-4.6  k: 1 (screening subset — NON-PROMOTABLE)  pipeline: 3.6.2  prompt: 3.7.0-tabledir
validity: 1/1 VALID — finish_reason=stop, usage intact (11259 in / 4115 out), cost
  $0.047, retries 0. Stream aggregation preserved everything the record needs.
gate: 0/1 — QUALITY failures, not transport: criterion_recall 0.944, annotation_mismatch,
  pedagogical_mismatch (k=1 — noise vs stable defect undecidable; the k=2 answers).
latency: t_doc 359.1s vs gpt-5.5-medium ~64s on the same fixture (~5.6×; ~11.5 tok/s
  aggregate — matches the probe).
decisions: kill criterion MET → k=2 all-5 trial LAUNCHED (T=1800 env, same config).
  Expected ~1.5-3h wall, ~$1 of the $5 budget.
cost: $0.047  wall: ~6 min
corrections: none

## RUN 20260815-185359_grok-4.6 — MODEL SWEEP: grok-4.6 k=2 all-5 — FALSIFIED (FC violation)
ref: 20260723-162200_gpt-5.5 (k=3 all-5, 15/15) — CROSS-TREE, see confound below
purpose: variable test: model gpt-5.5(openai,medium) -> grok-4.6(xai). Ordered by Noam.
variable changed vs ref: NOT ONE — model AND tree (prompt 3.3.1-tracehdr -> 3.7.0-tabledir,
  pipeline 3.4.0 -> 3.6.2, GT hobby/bagrut/foundations edits since 2026-07-25). The
  aggregate gate delta is therefore NOT cleanly model-attributable; the FC findings below
  ARE (they are direct source-vs-prediction comparisons, tree-independent).
config: grok-4.6  k: 2  model: grok-4.6  effort: null (not sent)
prompt_version: 3.7.0-tabledir  pipeline_version: 3.6.2  suite_hash: ba88c7b06e1a0ff8
validity: 10/10 valid (finish_reason=stop, usage intact, ZERO retries, zero truncation)
gate: 4/10 — per-fixture PERFECTLY BIMODAL and repeat-stable (identical metrics on both
  draws of every fixture): csharp 2/2 PASS, foundations 2/2 PASS, bagrut 0/2,
  employee 0/2, hobby 0/2. The 3 failures are exactly the 3 teacher-error fixtures.
predictions: P-PED1 (pedagogical/annotation = never-reconcile tripwire) CONFIRMED — it
  fired exactly as designed, on a NEW model, catching the forbidden behavior by name.
  Playbook §4's worked example predicted the literal number: it warns that writing
  ב=45 "would HIDE the arithmetic shadows and invent a total the teacher never wrote".
  grok wrote 45.
FC VIOLATIONS (the finding; both repeats identical, verified vs source):
  (1) hobby q2.ב — teacher wrote declared 29 (criteria sum 45). grok emitted declared
      45: SILENT REPAIR. Result: point_sum_consistency=True (a "clean" rubric), and
      BOTH rubric_mismatch annotations + BOTH point_sum_mismatch mistakes MISSING.
      Tier-B structural_mislabel@2 WAS found — so the mislabel is seen while its
      arithmetic shadows are erased. GT here was TRANSCRIBED from a faithful gpt-5.5
      draft probe (CHANGE 2026-07-25), i.e. gpt-5.5 demonstrably emits 29 + shadows.
  (2) bagrut q1.א.2 — teacher wrote declared 3 (children sum 2; the canonical INV-2
      node). grok emitted declared 1.5 / sum 1.5: SILENT REPAIR of the suite's
      flagship teacher error. Real rubric_mismatch@q1.א.2 MISSING.
  (3) CRY-WOLF CASCADE (the mirror failure): grok drops low-value code-quality criteria
      (attribution=extraction_loss, i.e. present in the render) — bagrut crit_recall
      0.820 (11 losses), employee 0.944 (1 loss: "קוד קריא... שמות משתנים משמעותיים",
      0.75pt). Those losses break the sums Tier A then honestly reports, producing 5
      SPURIOUS rubric_mismatch + 5 spurious point_sum_mismatch on bagrut (q1.א,q2-q5)
      and 1+1 on employee (q1) — false alarms on nodes the teacher wrote correctly.
      Net: silent on the 2 real errors, loud on 6 non-errors. Both directions of FC
      broken at once — the click-through-training failure INV-6's history warns about.
latency/cost (per full 5-fixture sweep, grok vs gpt-5.5 ref): 2750s vs 528s = 5.2x
  SLOWER (10.8 vs 61.1 tok/s aggregate); $0.313 vs $1.266 = 4x CHEAPER. bagrut 1479s
  vs 195s (7.6x). Zero retries (the L1 exemption holds for grok too).
transport: pipeline 3.6.2 streaming fix is load-bearing and WORKED — 10/10 valid, no
  timeouts, usage/finish_reason survive stream aggregation.
decisions: DO NOT ADOPT grok-4.6 for extraction. Cheaper and it never truncates, but it
  fails the product's foundational invariant (FC) on every fixture that has a teacher
  error to be faithful about — the exact property the rubric gate exists to provide.
  Same verdict class as P-L6-low (2026-07-23), reached on stronger evidence (k=2
  identical draws + direct source diff, vs that run's k=1).
next: OPTIONAL same-tree control — gpt-5.5 k=2 all-5 on prompt 3.7.0/pipeline 3.6.2
  (~$2.5 OpenAI, NOT spent without Noam's go) to de-confound criterion_recall and the
  aggregate count. Kill criterion: if gpt-5.5 also drops the code-quality criteria on
  3.7.0, that is a PROMPT regression owed its own fix, independent of the model verdict
  (which the FC findings already settle).
cost: $0.626 of the $5 xAI credit (~$4.37 remains)  wall: 18:54-20:26 (~92 min)
corrections: none

## CHANGE 2026-08-23 — model interface normalized onto the shared registry (INSTRUMENT change, no model variable moved)
what: (1) NEW tests/eval_common/models_registry.py — the transcription suite's
  registry MOVED to a shared home (+ a grok-4.6 entry sourced from this suite's
  own config notes; xAI, 2.00/6.00, cached-in omitted = conservative upper
  bound); the transcription-side file is now a re-export shim (its established
  idiom). (2) All 7 configs/ rewritten: identity+prices deleted, replaced by
  ONE `model_key` resolved through the registry; dead fields `temperature` /
  `pipeline_version` deleted. (3) runner: `_load_config` rejects legacy
  identity/price keys loudly; key resolved BEFORE the fixture loop; env
  identity now always spec-sourced (model_id + provider — no ambient leakage);
  cost via the ONE shared `cost_usd` (cached-input aware); provenance gains
  model_key/registry_as_of/models block; suite_hash now COVERS the registry.
  (4) schemas: RubricScore + model_key/tier/cached_tokens/reasoning_tokens
  (runner-attached, scorer untouched). (5) tests: eval_common battery (config
  keys of BOTH suites must resolve offline — caught + fixed the transcription
  suite's stale 'gpt-5.4-nano' in v0_p2_correct_spec.json); llm_policy sweep
  test now pins prices/provider AGAINST the registry; NEW cost-parity test
  pins cost_usd(18968,13546)@gpt-5.5 == 0.50122 — the exact value RUN
  20260726-144104 recorded under the legacy formula. gates.py / scoring.py /
  reporting aggregates / benchmarks / prompts: ZERO diff.
why: identity+price lived in 7 config files (split brain; CLAUDE.md §0.4) —
  consequences: the cost gate was silently DISABLED for any config without
  prices (default.json + prod_gpt55.json: cost_usd=None ⇒ gate skipped, never
  once enforced); provider could leak from ambient env (default.json had no
  provider key); a model typo surfaced as a provider 4xx, not a harness error;
  cached_tokens were measured then ignored by the cost formula. One registry =
  one fact per model across BOTH eval suites; `model_key` becomes the
  cross-suite join key for per-model metrics.
by: PLAN_model_registry_normalization.md (approved by Noam 2026-08-23:
  D1 shared home OK; D2 moot — Vertex A/B closed; D8 ceiling $1.00);
  executed by agent.
affects: suite_hash WILL shift next run (runner/schemas/test .py + the newly
  covered registry) — this change announcing itself, not drift. Historical
  cost numbers DO NOT move: cached_tokens=0 on all persisted records and the
  parity test is the receipt. CEILING CORRECTIONS (gate semantics, ruled, not
  silent): prod_gpt55 0.40→1.00 (the 0.40 was inherited from the gpt-4o
  baseline and never enforced — no prices ⇒ no cost ⇒ no check; measured
  worst-doc $0.501 would have failed every bagrut trial the moment the gate
  armed); gpt-5.5 / gpt-5.5-low 2.00→1.00 (owner ruling — ~2x headroom over
  the measured $0.501 worst doc). default.json's 0.40 gate is now ARMED for
  the first time (~$0.19 worst-doc upper bound, safe). KNOWN LOWER BOUND
  (pre-existing, NOT fixed here): Tier-B pedagogical adjudication runs without
  include_raw ⇒ its tokens are invisible ⇒ every cost number past and present
  under-reports by the Tier-B spend (BACKLOG B-30a owns the fix).
corrections: none

## RUN 20260823-012101_default — ACCEPTANCE SMOKE for the registry migration (k=1, csharp only, SCREENING/NON-PROMOTABLE)
ref: CHANGE 2026-08-23 (registry normalization) — this run is its paid acceptance check, per PLAN §6.4
purpose: prove the migrated plumbing end-to-end on ONE cheap trial: registry-resolved
  identity reaches the pipeline; new provenance stamps land; the cost gate is ARMED on
  default.json for the first time; score_only parity on the same prediction.
variable changed vs ref: NONE (no model/prompt/config-value/scorer change — plumbing verification)
config: default  k: 1  model: gpt-4o (via model_key)  effort: n/a
prompt_version: 3.7.0-tabledir  pipeline_version: 3.6.2  suite_hash: c45b344ef842d36f
  (shifted as pre-announced — instrument change + newly-hashed registry; matches the
  offline dry-run hash exactly)
validity: 1/1 valid (finish_reason=stop, zero retries)
gate: 1/1 PASS (csharp on gpt-4o clears the full conjunctive gate — noted, NOT promoted; k=1 screening subset)
acceptance criteria (ALL MET):
  - provenance.model_version=gpt-4o (env hop delivered the registry model_id);
    model_key=gpt-4o, registry_as_of=2026-08-15, models block with id/provider/tier/price stamped.
  - cost_usd=0.054235 NON-NULL on default.json for the first time ever (F1 armed) and
    cross-checks the registry card exactly: 10426*2.50/1e6 + 2817*10.00/1e6. Well under
    the 0.40 ceiling. cached_tokens=0, reasoning_tokens=0 (non-reasoning family — consistent).
  - score_only re-score of the persisted prediction: gate_pass=True, ZERO diffs across
    all 13 gated fields vs the run record — the scorer is untouched by the migration.
surprises: the final "[done] ... →" print CRASHED on the cp1252 Windows console AFTER
  write_all (artifacts intact, exit ugly) — the output-side sibling of the Family-D
  charmap class. FIXED in the same sitting: runner.py prints ASCII "->" now.
decisions: migration accepted; no further paid verification owed (nothing to re-baseline —
  no model/prompt/scorer moved).
cost: $0.054  wall: ~30s t_doc
corrections: none

## CHANGE 2026-08-23 — gpt-5.6 sweep armed: registry +terra/+sol, 9 configs, pin test extended (INSTRUMENT change; no run yet)
what: (1) registry gains `gpt-5.6-terra` (2.00/12.00, cached 0.20) and
  `gpt-5.6-sol` — sol pinned at the **LIST** card 5.00/30.00/0.50, NOT the
  promotional 4.00/20.00/0.40 that bills today (promo runs "at least through
  2026-11-21"). RULING, logged as one: an adoption decision outlives a promo,
  so the conservative direction is list; at list, sol's card is identical to
  gpt-5.5's, which makes any sol cost win a pure token-volume result and a
  FLOOR (promo would only improve it). `gpt-5.6-luna` was already present
  (transcription P2) and is UNTOUCHED — including its deliberately absent
  cached-in rate, so luna's cost stays a conservative upper bound; changing it
  would move the OTHER suite's numbers, which is not this mission's variable.
  (2) NINE configs `gpt-5.6-{luna,terra,sol}[-low|-high].json` — each identical
  to prod_gpt55.json except model_key + reasoning_effort (max_output_tokens
  32000, cost_ceiling 1.00 held fixed so the gate is apples-to-apples).
  (3) test_llm_policy's registry pin extended with the three MEDIUM anchors
  (the -low/-high variants stay unpinned, exactly as gpt-5.5-low is — effort is
  the sweep variable). ZERO diff to prompt, pipeline, scorer, gates, GT.
why: owner-ordered sweep (equal-or-better accuracy AND cost at lower latency).
  gpt-5.6-* needs NO pipeline change: `_is_openai_reasoning` matches on the
  "gpt-5" prefix, so the effort knob and the 32k completion budget already
  route correctly.
by: agent, on Noam's 2026-08-23 instruction.
live wiring probe (~$0.001, 9/9 OK, before any paid sweep — the grok
  probe-ladder discipline): all three model ids resolve, all three efforts are
  accepted, structured output parses, usage + finish_reason=stop land. luna
  effort=high is the only cell that returned reasoning tokens on a trivial
  prompt (11) — a first hint that the effort knob bites differently per tier.
affects: suite_hash SHIFTS (registry + test .py are both hashed) — announced
  here, not drift. All 41 instrument guards green after the edit. Every run of
  this sweep, baseline included, is on the POST-edit hash, so the sweep is
  internally comparable; it is NOT comparable to any pre-2026-08-23 hash.

## CHANGE 2026-08-23 — P-M56 search order amended by the owner (protocol ruling, no file variable moved)
what: PREDICTIONS.md P-M56 pre-registered the screen order as luna -> terra -> sol
  (cheapest-first). Noam's instruction (2026-08-23, after RUN ZERO launched):
  "start with the first trial you would bet on to work best", plus standing
  approval to iterate to a winner or to exhaust all 9 cells, with the bar stated
  as "NO benchmark regressions vs base".
ruling: order becomes BET-FIRST. Cell #1 = **gpt-5.6-terra @ medium**, on this
  reasoning: (a) accuracy — the gate is FC-hard (bagrut/hobby faithful teacher
  errors killed gpt-5.5@low AND frontier-class grok-4.6), so an economy tier is
  the long shot, not the front-runner; a mid tier one generation NEWER than
  gpt-5.5 is the best odds of matching it; (b) cost — terra's card is 2.5x under
  gpt-5.5 on both legs, so passing accuracy AT ALL wins the cost axis outright,
  whereas sol at LIST prices must win on token volume alone; (c) latency —
  t_doc is ~99% decode, so the mid tier's faster decode + a newer generation's
  lower reasoning-token appetite attack the dominant term, while effort=high
  would push output tokens the WRONG way. luna and sol are not dropped — they
  are cells 2..9 of the same sweep.
why logged: the pre-registered order is part of the pre-registration; changing
  it silently would be post-hoc protocol drift (§11 rule 3 — a ruling is a
  variable change even when no file's value moves). The KILL CRITERIA and the
  promotion bar in P-M56 are UNCHANGED and were not renegotiated.
by: Noam (order + standing approval); agent (which cell "best bet" resolves to).
affects: nothing already run. RUN ZERO (prod_gpt55 k=3) was launched before this
  and is unaffected — it is the reference for every cell either way.

## RUN 20260823-191643_prod_gpt55 — RUN ZERO: the same-tree gpt-5.5 baseline. 12/15 — the PROD PIN NOW SILENTLY REPAIRS hobby q2.ב
ref: 20260723-162200_gpt-5.5 (k=3 all-5, 15/15) — CROSS-TREE, which is exactly why this run exists
purpose: baseline for the P-M56 gpt-5.6 sweep — accuracy AND $/doc AND t_doc on the CURRENT tree
variable changed vs ref: NOT ONE — the TREE (prompt 3.3.1-tracehdr -> 3.7.0-tabledir, pipeline
  3.4.0 -> 3.6.2, GT hobby/foundations edits 2026-07-25, registry migration). Model/effort/budget
  are the prod pin, unchanged: gpt-5.5 / medium / 32000.
config: prod_gpt55  k: 3  model: gpt-5.5  effort: medium
prompt_version: 3.7.0-tabledir  pipeline_version: 3.6.2  suite_hash: 19607f69e6bc3432
validity: 15/15 valid (finish_reason=stop; ~7 transient APIConnectionErrors were absorbed by the
  PR-2 retry layer with no measurable t_doc inflation — spreads stayed tight)
gate: 12/15 — bagrut 3/3, csharp 3/3, employee 3/3, foundations 3/3, **hobby 0/3**
THE FINDING (stable, 3/3 IDENTICAL draws, verified against the persisted prediction):
  hobby q2.ב — the teacher wrote "סה"כ 29"; its criteria sum to 45. GT (TRANSCRIBED 2026-07-25
  from a FAITHFUL gpt-5.5 probe on prompt 3.5.0) says points=29. **gpt-5.5-medium on prompt
  3.7.0-tabledir now emits points=45.0** — the lumped sum the teacher never wrote. SILENT REPAIR.
  ONE defect, THREE gate failures, all explained by it:
    point_exactness 0.9792 (1 of 48 point values wrong) · annotation_mismatch (BOTH expected
    rubric_mismatch@q2 and @q2.ב MISSING — with ב=45 the rubric is arithmetically consistent,
    so there is nothing left to flag; point_sum_consistency came back True) · pedagogical_mismatch
    (BOTH Tier-A point_sum_mismatch@2 (44 vs 60) and @q2.ב (45 vs 29) MISSING).
  Tier-B structural_mislabel@2 IS still found — the mislabel is seen while its arithmetic
  shadows are erased.
  This is BYTE-FOR-BYTE the FC violation grok-4.6 was rejected for on 2026-08-15 (RUN
  20260815-185359, finding (1)), now committed by the PRODUCTION PIN. The grok entry's own
  "next" pre-registered this possibility: a same-tree gpt-5.5 control, with "if gpt-5.5 also
  [regresses] on 3.7.0, that is a PROMPT regression owed its own fix, independent of the model
  verdict". The control has now been run and it does. ATTRIBUTION: prompt/tree, NOT model —
  the same model+effort emitted 29 at prompt 3.5.0 (that emission is what the GT was
  transcribed from). NOT FIXED HERE: a prompt edit is a second variable and would invalidate
  every cell of the sweep it is meant to serve. Surfaced for Noam as its own mission.
latency (t_doc median | max, s): bagrut 183.8 | 192.3 · hobby 104.3 | 104.4 · foundations
  95.6 | 97.4 · csharp 60.6 | 61.0 · employee 59.0 | 64.7. HEADLINE = bagrut 183.8s.
  Sum-of-medians (one full suite pass) = 503.3s. Decode rate ~70 tok/s (was ~55 in July).
  bagrut retries 0/3 — the P-L1 exemption still holds on 3.6.2; the July retry bimodality is gone.
cost: $3.255 total, $0.217/doc mean; bagrut $0.394 (worst), employee $0.130 (best). Ceiling
  1.00 never approached. NOTE the known lower bound: Tier-B adjudication tokens are invisible
  (B-30a), so this under-reports by the Tier-B spend on hobby.
predictions: P-M56 unaffected (it is registered against THIS run, which is the point).
THE BAR FOR EVERY P-M56 CELL, now that base is not 5/5: no NEW failure anywhere. A candidate
  failing hobby on exactly these three metrics ties base; a candidate emitting ב=29 with both
  annotations + both mistakes BEATS the prod pin on the product's foundational invariant.
next: cell #1 gpt-5.6-terra @ medium, k=1 all-5 screen (bet-first order, ruled above).
  kill criterion: any gated regression vs THIS run on ANY fixture.
corrections: none

## RUN 20260823-194348_gpt-5.6-terra — P-M56 cell 1/9 (terra @ medium), k=1 all-5 SCREEN — FALSIFIED (bagrut regression)
ref: 20260823-191643_prod_gpt55 (RUN ZERO, same tree, same hash) — a TRUE one-variable comparison
purpose: screen the bet-first cell. k=1 all-5, NON-PROMOTABLE (owner 2026-07-23 protocol)
variable changed vs ref: exactly ONE — model_key gpt-5.5 -> gpt-5.6-terra (effort medium, budget
  32000, ceiling 1.00 all held)
config: gpt-5.6-terra  k: 1  effort: medium  prompt: 3.7.0-tabledir  pipeline: 3.6.2
  suite_hash: 19607f69e6bc3432
validity: 5/5 valid (finish_reason=stop, 0 retries, no truncation)
gate: 3/5 — csharp PASS, employee PASS, foundations PASS, hobby FAIL (ties base), **bagrut FAIL
  (base passes 3/3)** => KILL CRITERION FIRED.
bagrut regression, itemized (this is the whole verdict):
  - example_solution_fidelity 0.167: TEN of twelve scopes lost their example solution (q2.א/ב,
    q3.א/ב, q4.א/ב, q5.א/ב, q6 — most extracted as None outright). The dominant defect: terra
    at medium is not executing the prompt's verbatim solution-capture at all on a long document.
  - subquestion_structure_match 0.917: q1.ב FLATTENED (leaf_vs_branch — the FP2 signature),
    which then cost 3 GT criteria (criterion_recall 0.951) and invented 1 spurious criterion at
    q1.א.2 (criterion_precision 0.983).
  - CRY-WOLF CASCADE, exactly grok-4.6's mirror failure: the flattening breaks sums the extractor
    then honestly reports -> SPURIOUS rubric_mismatch@q1.ב + SPURIOUS point_sum_mismatch@q1.ב on
    a node the teacher wrote correctly (annotation_mismatch + pedagogical_mismatch by spuriousness,
    not by silence). render_loss 0 / extraction_loss 3 — every loss is the model's, not the renderer's.
hobby: FAILS with the EXACT base signature (annotation_mismatch, pedagogical_mismatch,
  point_exactness 0.9792) — i.e. terra commits the same q2.ב silent repair as the prod pin. A TIE,
  not a regression; and independent confirmation that the hobby defect is tree/prompt-borne, not
  model-borne (two different models, identical failure, identical numbers).
latency/cost (the prize, and it is large): headline 115.5s vs 183.8s = **-37.1%**; suite
  sum-of-medians 287.9s vs 503.3s = **-42.8%**; $0.0712/doc vs $0.2170 = **-67.2%**. Every fixture
  faster: csharp -44%, employee -40%, foundations -53%, hobby -44%, bagrut -37%. All far beyond
  the ~1-11% clean-fixture noise band (MDE ~2x). Reasoning tokens are TINY (384-1006 vs
  gpt-5.5's 1024-3291) — the mechanism is P-M56.3's "fewer output tokens", and on bagrut that is
  exactly what dropped the solutions.
predictions: P-M56.3 CONFIRMED and its RED FLAG clause fired as written — "a win that is purely
  fewer output tokens on the faithful-error fixtures is a RED FLAG, not a win". P-M56.4 CONFIRMED
  (terra beats base cost trivially). P-M56.2's cry-wolf mechanism reproduced on a mid tier.
decision: terra@medium FALSIFIED. Per the adaptive protocol, next = SAME model at HIGH effort:
  the failure class is under-execution (missing solutions, flattened branch), which is precisely
  what more reasoning attacks, and there is enormous budget headroom (115s vs 183.8s; $0.14 vs
  $0.39 on bagrut) to spend on it and still win.
next: cell 2/9 gpt-5.6-terra-high, k=1 all-5. kill criterion: any gated regression vs RUN ZERO.
cost: $0.356  wall: ~5 min
corrections: none

## RUN 20260823-194923_gpt-5.6-terra-high — P-M56 cell 2/9 (terra @ high), k=1 all-5 SCREEN — CANDIDATE (ties base, -25% headline, -59% cost)
ref: 20260823-191643_prod_gpt55 (RUN ZERO). Also pairs against cell 1 (terra @ medium) — vs THAT
  run the single variable is reasoning_effort medium -> high.
purpose: screen cell 2 (protocol: medium failed -> screen high). k=1, NON-PROMOTABLE.
config: gpt-5.6-terra-high  k: 1  effort: high  prompt 3.7.0-tabledir  pipeline 3.6.2
  suite_hash 19607f69e6bc3432
validity: 5/5 valid (finish_reason=stop, 0 retries, 0 truncation)
gate: 4/5 — bagrut PASS, csharp PASS, employee PASS, foundations PASS, hobby FAIL.
  **EXACTLY base's pass set.** A metric-by-metric diff of all 13 gated fields x 5 fixtures against
  base's WORST-of-3 returns SAME on every cell, hobby's failure included (annotation_mismatch,
  pedagogical_mismatch, point_exactness 0.9792 — the same three, the same numbers). Zero
  render_loss, zero extraction_loss on all five.
effort is the whole difference (cell 1 -> cell 2, one variable): bagrut example_solution_fidelity
  0.167 -> 1.0, subquestion_structure_match 0.917 -> 1.0, criterion_recall 0.951 -> 1.0,
  criterion_precision 0.983 -> 1.0, and the spurious rubric_mismatch/point_sum_mismatch@q1.ב
  cry-wolf pair is GONE. bagrut reasoning tokens 433 -> 1806 bought all of it. This is the
  cleanest attribution in the sweep: the terra failure was under-execution, and effort fixed it.
UNGATED diagnostics IMPROVE over base (watched, never gated — reported because a tie on the gate
  plus a gain here is a different verdict than a bare tie): bagrut subquestion_text_fidelity_min
  0.2266 -> 0.7071 and text_line_recall_min 0.0625 -> 0.4167 (the ONBOARDING §9 item-4 tail, the
  worst number in the suite, materially better); foundations 0.6631 -> 0.8364 / 0.5 -> 1.0 /
  0.75 -> 1.0. csharp, employee, hobby identical. NOTHING got worse.
latency/cost vs base: headline 138.7s vs 183.8s = **-24.5%**; suite sum-of-medians 354.5s vs
  503.3s = **-29.6%**; $0.0882/doc vs $0.2170 = **-59.4%** (at terra's registry card, no promo).
  Per fixture: bagrut -24.5%, csharp -24.8%, employee -22.4%, foundations -38.9%, hobby -36.6% —
  every one past the ~1-11% clean-fixture noise band; the two smallest (-22.4%, -24.5%) sit at
  ~2x the band, i.e. AT the stated MDE, which is precisely why k=3 confirmation is owed.
decision: CANDIDATE, not winner (k=1 cannot distinguish safe from lucky). Before spending the k=3
  confirmation, screen the cells that could BEAT it — a confirmation spent on the first passing
  cell would have to be re-spent if a better one exists.
protocol refinement (logged, evidence-derived from cell 1 -> cell 2): when a model's failure class
  is UNDER-EXECUTION, **HIGH is the discriminating cell for the whole model row** — low and medium
  are strictly weaker on that axis, so a failure at high kills the row in one screen. Applied to
  luna next (cell 3), whose economy tier makes under-execution the expected failure.
next: cell 3/9 gpt-5.6-luna-high (kills or promotes the entire luna row in one $0.05 screen), then
  cell 4/9 gpt-5.6-sol @ medium (the only cell that could beat a tie by BEATING base — i.e. by
  emitting hobby q2.ב = 29 and passing 5/5). Then k=3 confirmation on the best of them.
  DEFERRED with reason (not silently dropped): gpt-5.6-terra-low. P-M56 pre-registered "screen LOW
  after a failed medium only if HIGH passes"; high did pass, so it is owed. But medium already
  collapsed on under-execution and low is strictly weaker on that exact axis, so its expected
  information is ~0. It is queued behind the decision-relevant cells and will be run for
  completeness if the winner is still in question.
cost: $0.441  wall: ~6 min
corrections: none

## RUN 20260823-195615_gpt-5.6-luna-high — P-M56 cell 3/9 (luna @ high), k=1 all-5 SCREEN — FALSIFIED; the luna ROW is dead
ref: 20260823-191643_prod_gpt55 (RUN ZERO)
purpose: the DISCRIMINATING cell for the whole luna row (refinement logged on cell 2: when the
  expected failure class is under-execution, a failure at HIGH kills low+medium by construction).
config: gpt-5.6-luna-high  k: 1  effort: high  suite_hash 19607f69e6bc3432
validity: 5/5 valid (0 retries, 0 truncation — transport and schema are fine; this is pure quality)
gate: 1/5 — employee PASS only. bagrut FAIL, csharp FAIL, foundations FAIL, hobby FAIL.
regressions vs base (all NEW except hobby):
  - csharp criterion_precision 0.958 / criterion_recall 0.958 — **the CLEAN-TABLE CONTROL fixture,
    the suite's regression guard.** A model that cannot read the clean table is not a candidate;
    this alone is disqualifying.
  - bagrut example_solution_fidelity 0.923 · foundations example_solution_fidelity 0.600 — the same
    solution-capture weakness terra showed at medium, unfixed here even at HIGH.
  - hobby: base signature exactly (annotation/pedagogical/point_exactness 0.9792) — a tie, and the
    THIRD independent model to reproduce it. The hobby q2.ב defect is now confirmed tree/prompt-borne
    across gpt-5.5, terra and luna.
the interesting part — luna@high is not even fast: foundations 97.3s vs base 95.6s = **+2%** (no
  win at all) while burning 7723 reasoning tokens, MORE than gpt-5.5's 3291 on the same fixture;
  bagrut 4729 vs 2048. The economy tier reaches for reasoning to compensate for capability and
  spends the latency budget doing it. Suite -25.9% is worse than terra-high's -29.6% despite a far
  cheaper card. P-M56.2 CONFIRMED (luna's failure is quality, not transport/truncation).
cost: $0.0134/doc (-93.8% vs base) — irrelevant at 1/5. Cheapness cannot buy the gate.
decision: luna FALSIFIED at its strongest cell => ROW DEAD. luna-low and luna-medium are strictly
  weaker on the exact axis that failed (under-execution of solution capture + criterion fidelity),
  so they are killed BY INFERENCE and are not worth $0.10 to re-observe. Stated honestly: those two
  cells remain FORMALLY UNRUN — the inference is used to prioritize spend, and is NOT counted as
  "exhausted the 9" if the sweep ever has to fall back on that clause.
next: cell 4/9 gpt-5.6-sol @ medium. It is the only remaining cell that could BEAT (rather than tie)
  the terra-high candidate — by emitting hobby q2.ב=29 and passing 5/5, which would beat the PROD
  PIN on the product's foundational invariant. terra-high already wins cost decisively, so a sol
  tie changes nothing.
cost: $0.067  wall: ~6 min
corrections: none

## RUN 20260823-200259_gpt-5.6-sol — P-M56 cell 4/9 (sol @ medium), k=1 all-5 SCREEN — ties accuracy, LOSES the mission axis
ref: 20260823-191643_prod_gpt55 (RUN ZERO)
purpose: the only cell that could BEAT rather than tie the terra-high candidate — by emitting
  hobby q2.ב = 29 and clearing 5/5, which would beat the PROD PIN on faithful capture.
config: gpt-5.6-sol  k: 1  effort: medium  suite_hash 19607f69e6bc3432
validity: 5/5 valid (0 retries, 0 truncation)
gate: 4/5 — bagrut/csharp/employee/foundations PASS, hobby FAIL with the base signature
  (annotation_mismatch, pedagogical_mismatch, point_exactness 0.9792). Accuracy TIES base. It does
  NOT fix hobby => it does not beat base, and the "could beat" hypothesis is FALSIFIED.
latency/cost vs base: headline **212.1s vs 183.8s = +15.4% SLOWER** (bagrut); suite -3.7% and
  $0.2047/doc vs $0.2170 = -5.7% — BOTH inside the 1-11% noise band, i.e. not distinguishable
  from base. The one primary axis of this mission moves the WRONG way.
verdict: NOT the winner. Pre-registered rule applied verbatim — "a candidate that passes accuracy
  but is SLOWER or MORE EXPENSIVE than baseline is reported as such and does not stop the search."
  terra-high DOMINATES it: same accuracy, 138.7s vs 212.1s headline, $0.088 vs $0.205/doc.
  NOTE the promo caveat cuts the other way here and still does not save it: even at sol's
  PROMOTIONAL card (4.00/20.00) its cost would be ~$0.14/doc, still above terra-high's $0.088,
  and price has no effect at all on the +15.4% headline.
FOURTH independent reproduction of the hobby q2.ב silent repair (gpt-5.5, terra@med, terra@high,
  luna@high, sol@med — five model/effort configurations now, spanning three tiers and two
  generations, all emitting 45.0 and all losing the same three metrics). The tree/prompt
  attribution is no longer a hypothesis.
decision on the remaining sol cells (logged, not silently skipped): sol-high and sol-low are NOT
  screened. sol-high would cost more and be slower than sol-medium (effort raises output tokens,
  the dominant latency term) while the ONLY thing it could buy — passing hobby — is now contradicted
  by five reproductions across every effort level. sol-low attacks latency, but sol's card is 2.5x
  terra's, so even a large token cut leaves it ~$0.25/doc vs terra-high's $0.088 — it cannot be
  "best overall" — and effort=low is the exact knob that FALSIFIED gpt-5.5-low (2026-07-23) and
  terra-medium (cell 1) on the faithful-error fixtures. Both remain FORMALLY UNRUN.
next: k=3 all-5 CONFIRMATION of gpt-5.6-terra-high (the owner's promotion bar). Pre-registered
  promotion criteria: 12/15 with NO new failure class on any fixture (base's pass set exactly),
  AND worst-fixture median t_doc below base's 183.8s, AND mean $/doc <= $0.2170.
cost: $1.023  wall: ~7 min
corrections: none

## RUN 20260823-201145_gpt-5.6-terra-high — P-M56 CONFIRMATION of the candidate, k=3 all-5 — **FALSIFIED** (the k=1 pass was a lucky draw)
ref: 20260823-191643_prod_gpt55 (RUN ZERO) + 20260823-194923 (the same config at k=1, which passed 4/5)
purpose: the owner's promotion bar — k=3 all-5 on the winning config. Pre-registered criteria:
  base's pass set exactly (12/15, no NEW failure class) AND headline < 183.8s AND $/doc <= 0.2170.
config: gpt-5.6-terra-high  k: 3  effort: high  suite_hash 19607f69e6bc3432
validity: 15/15 valid (0 truncation)
gate: **10/15** — csharp 3/3, employee 3/3, foundations 3/3, hobby 0/3 (base signature, tie),
  **bagrut 1/3 where base is 3/3** => PROMOTION CRITERIA NOT MET. FALSIFIED.
the bagrut instability, per draw (this is the finding, and it is a STABLE defect, not a flake):
  r0 FAIL t=163.5s out=12669 rsn=1951 retry=0 — criterion_precision 0.968: a SPURIOUS criterion at
     q1.ב.2, which breaks that node's sum and manufactures a FALSE rubric_mismatch@q1.ב.2 +
     FALSE point_sum_mismatch@q1.ב.2 on a node the teacher wrote CORRECTLY.
  r2 FAIL t=153.8s out=12071 rsn=1770 retry=0 — the SAME spurious criterion + the same two false
     alarms, plus example_solution_fidelity 0.923 (one solution lost).
  r1 PASS t=185.7s out=17918 rsn=3538 **retry=1** — the only clean draw is the one where a
     VALIDATION RETRY fired: +5.2k output tokens and +1.8k reasoning over its siblings. terra-high
     gets bagrut right when it gets a SECOND PASS, not on the first.
  So 2/3 draws commit the CRY-WOLF half of the FC failure — the mirror of silent repair, and the
  same class grok-4.6 was rejected for (RUN 20260815-185359, finding (3)). It is not a marginal
  metric wobble: false alarms on correct teacher nodes are exactly the click-through training
  INV-6's history warns about.
lesson (the protocol earning its keep): at k=1 this identical config returned bagrut PASS with
  ZERO spurious anything. One draw in three is clean, so a k=1 screen had a ~1/3 chance of
  showing the true behaviour and showed the lucky one. "k=1 cannot distinguish safe from lucky"
  is not a slogan — this run is the receipt. Nothing was promoted on it, which is the design.
latency/cost at k=3 (recomputed, and materially weaker than the k=1 draw suggested): headline
  163.5s vs 183.8s = **-11.0%** (was -24.5% at k=1 — the k=1 bagrut draw was also a fast one);
  suite sum-of-medians 380.1s vs 503.3s = -24.5%; $0.0845/doc vs $0.2170 = **-61.1%**.
  The headline -11.0% is now INSIDE 2x the bagrut noise band — i.e. even the latency claim would
  not have survived its own MDE test at this k. Both halves of the k=1 result were optimistic.
decision: gpt-5.6-terra-high FALSIFIED. No promotable config from the terra row: medium fails
  by under-execution, high fails by cry-wolf on 2/3 draws, and low is strictly weaker than medium
  on the axis medium already failed.
next: cell 5 gpt-5.6-sol-low — the last cell with any live path to the mission goal (a latency win
  at tied accuracy). Pre-registered doubt, stated BEFORE the run so the result cannot be
  laundered: sol's measured DECODE RATE is ~57 tok/s (12104 out / 212.1s at medium) vs base
  gpt-5.5 ~70 tok/s, terra ~77, luna ~127. Decode rate, not token count, is sol's binding
  constraint, so sol-low would need out_tok < ~10.5k on bagrut merely to TIE base's 183.8s.
  sol-medium emitted 12.1k. PREDICTION: sol-low does not clear base's headline by more than
  noise even if its accuracy holds. If that lands, the sol row is out on latency grounds.
cost: $1.267  wall: ~19 min
corrections: none

## RUN 20260823-203248_gpt-5.6-sol-low — P-M56 cell 5/9 (sol @ low), k=1 all-5 SCREEN — partial tie, ONE INVALID; promoted to confirmation
ref: 20260823-191643_prod_gpt55 (RUN ZERO)
purpose: the last cell with a live path to the mission goal (latency win at tied accuracy).
config: gpt-5.6-sol-low  k: 1  effort: low  suite_hash 19607f69e6bc3432
validity: **4/5 valid** — employee_course_select1 INVALID: ExtractionError, APITimeoutError after
  2 transport attempts (the PR-2 bounded layer, T=360s each). TRANSPORT, not quality: the same
  fixture is the suite's FASTEST doc and sol@medium extracted it in 56.2s an hour earlier; RUN
  ZERO absorbed ~7 transient APIConnectionErrors on this same network. Excluded from accuracy
  aggregates; the fixture's behaviour under sol-low is simply UNKNOWN, and is not scored as a fail.
gate: 3/5 raw. On the four VALID fixtures: bagrut PASS, csharp PASS, foundations PASS, hobby FAIL
  (base signature — the fifth model/effort config to reproduce the q2.ב silent repair). That is
  base's pattern on those four.
NOTE — effort=low did NOT reproduce the P-L6-low / terra-medium failure here: bagrut came back
  clean (annotation_match + pedagogical_match both true, example_solution_fidelity 1.0) on just
  433 reasoning tokens. P-M56.1 is therefore NOT confirmed on sol: the tripwire that fired for
  gpt-5.5@low and terra@medium did not fire for sol@low. Recorded as a genuine model-capability
  observation at k=1 — and k=1 is exactly the evidence that just proved untrustworthy on
  terra-high (1 clean draw in 3), so it is a HYPOTHESIS, not a result.
latency/cost vs base — **CORRECTED, see the instrument note below**: headline 159.3s vs 183.8s =
  -13.3%. Like-for-like over the 4 commonly-valid fixtures: $/doc $0.2111 vs $0.2262 = **-6.7%**
  (at sol's LIST card; at the promo card it would be ~-25%), Sigma t_med -22.7%.
INSTRUMENT NOTE (my own analysis tool, caught and fixed before it reached a verdict): the scratch
  sweep_report divided TOTAL cost by n INCLUDING the invalid record, i.e. it priced a crashed doc
  at $0 and reported sol-low at "-22.2% $/doc". Validity before significance applies to the COST
  column too. Fixed to average over VALID records only and to re-base both runs on the fixtures
  valid in BOTH — which turns a -22% cost claim into -6.7%. The suite's own reporting.py was never
  affected (it aggregates validity correctly); the bug was in the scratchpad helper only.
decision: PROMOTE TO CONFIRMATION — k=3 all-5. It is the only cell left that can satisfy the
  mission (tie accuracy AND cut latency), and its two open questions are exactly what k=3 answers:
  (a) is bagrut@low stable or a 1-in-3 lucky draw (the terra-high trap), (b) does employee extract
  at all once transport cooperates.
next: RUN sol-low k=3 all-5. Promotion criteria unchanged: base's pass set (12/15, no NEW failure
  class), headline < 183.8s, like-for-like $/doc <= base.
cost: $0.844  wall: ~9 min (incl. the 2x360s timeout burn on employee)
corrections: none

## RUN 20260823-214739_gpt-5.6-sol-low — P-M56 CONFIRMATION of cell 5, k=3 all-5 — FALSIFIED (closest miss of the sweep)
ref: 20260823-191643_prod_gpt55 (RUN ZERO) + 20260823-203248 (same config, k=1)
purpose: the owner's promotion bar on the last live candidate. Two pre-registered questions:
  (a) is bagrut@low stable or a lucky draw, (b) does employee extract once transport cooperates.
config: gpt-5.6-sol-low  k: 3  effort: low  suite_hash 19607f69e6bc3432
validity: **15/15 valid** — question (b) ANSWERED: employee 3/3 PASS at 52.1s median. The k=1
  INVALID was transport, exactly as attributed; nothing about the fixture or the model.
gate: **11/15** vs base 12/15 — csharp 3/3, employee 3/3, foundations 3/3, hobby 0/3 (tie),
  **bagrut 2/3** => one gated regression vs base's 3/3. KILL CRITERION FIRED. FALSIFIED.
question (a) ANSWERED — bagrut per draw: r0 PASS (rsn 404), r1 PASS (rsn 384), r2 FAIL
  example_solution_fidelity 0.929 (rsn **219** — the lowest-reasoning draw is the one that lost a
  solution). Not the terra-high pattern (2/3 failing) and not stable either: 2/3 clean, and the
  failure mechanism is the same under-execution family — when the model reasons least, a verbatim
  example solution goes missing. P-M56.1 is NOT confirmed for sol (no faithful-error reconciliation
  at low; annotation_match and pedagogical_match held on every bagrut draw) — a real
  model-capability difference from gpt-5.5@low, and worth remembering. But the gate is conjunctive:
  a lost solution fails it just as surely as a reconciled error.
latency: headline 168.5s vs 183.8s = **-8.3%** — INSIDE the 1-11% clean-fixture noise band, so
  even with accuracy set aside this is not a credible headline win. Suite sum-of-medians -18.1%.
  Mechanism: sol's decode rate ~66 tok/s here vs base ~70 — the pre-registered decode-rate doubt
  (logged before this run) is CONFIRMED. sol cannot buy latency with fewer tokens because tokens
  are not what makes it slow.
cost: like-for-like over all 5 fixtures $0.1598/doc vs $0.2069 = **-22.7%** at sol's LIST card
  (~-45% at the promo card). The one axis sol-low genuinely wins — and it is the axis the mission
  ranks last.
decision: FALSIFIED. No confirmed winner in the sweep. Remaining cells (terra-low, luna-medium,
  luna-low, sol-high) launched at k=1 for FORMAL EXHAUSTION rather than left on inference: the
  owner's stopping condition is "a winner or all 9", and a measured 3x3 map is worth ~$1.7 to the
  next person who asks this question (e.g. after the hobby prompt defect is fixed).
predictions: P-M56.3 CONFIRMED again (fewer output tokens = the lost solution). P-M56.4 CONFIRMED
  (sol wins cost on volume alone even at list). The sweep-wide pattern is now unmistakable and is
  the real finding — see the closing entry.
cost: $2.463  wall: ~35 min
corrections: none

## RUN 20260823-220928_gpt-5.6-terra-low — P-M56 cell 6/9 (terra @ low), k=1 all-5 — FALSIFIED (inference CONFIRMED by measurement)
ref: RUN ZERO. purpose: formal exhaustion of the terra row (was "dead by inference" after cells 1-2).
gate: 3/5 — csharp/employee/foundations PASS; hobby FAIL (base signature); bagrut FAIL:
  example_solution_fidelity 0.286 (10 of 14 solutions lost), criterion_precision 0.968, plus the
  annotation/pedagogical cry-wolf pair. Same failure family as terra@medium, slightly different mix.
verdict: the terra row is now MEASURED, not inferred: low 3/5, medium 3/5, high 4/5@k=1 -> 10/15@k=3.
  No terra cell reaches base. cost: $0.278

## RUN 20260823-221411_gpt-5.6-luna — P-M56 cell 7/9 (luna @ medium), k=1 all-5 — FALSIFIED (worst cell of the sweep)
ref: RUN ZERO. gate: **0/5** — every fixture fails. New failure class not seen elsewhere:
  question_recall 0.667 (employee) and 0.500 (hobby) — it drops WHOLE QUESTIONS, and hobby also
  fails total_points_incorrect. csharp (the clean-table control) criterion recall/precision 0.750.
verdict: luna@medium is the worst cell measured. cost: $0.041

## RUN 20260823-221908_gpt-5.6-luna-low — P-M56 cell 8/9 (luna @ low), k=1 all-5 — FALSIFIED + a TRANSPORT finding
ref: RUN ZERO. gate: 1/5 (employee only). bagrut subquestion_structure_match 0.917 +
  criterion_recall 0.689 · csharp criterion recall/precision 0.750 (the control, again) ·
  foundations example_solution_fidelity 0.600 · hobby structure 0.833.
  The luna row is now MEASURED: low 1/5, medium 0/5, high 1/5. Dead, as inferred on cell 3.
TRANSPORT FINDING (the reason this run took ~55 min): bagrut t_doc 2188.5s of which the extraction
  LLM was 49.1s and **Tier-B pedagogical was 2138.8s (97.7%)**. Tier-B is batched PER QUESTION
  (CHANGE 2026-07-31 D1-D8) and bagrut has SIX questions, so a degraded provider window multiplies
  the 360s per-attempt bound by the question count: 6 x 360 ~= 2160s. csharp likewise 1038s ~=
  3 x 346s, one bound per step of the 3-step chain. NOT a model property — a provider/network
  degradation window (~22:19-23:14 local) that also produced sol-low's k=1 employee timeout.
  PROD IS PROTECTED: _make_adjudicator passes the wall `deadline` into _transport_retry_async, and
  the runner passes 840s - pre-work; the EVAL path is deliberately deadline-free
  (deadline_seconds=None), which is why the eval saw the full 36 minutes. Worth a look anyway —
  the per-question fan-out means the Tier-B worst case scales with question count, and the
  deadline is the only thing standing between a teacher and that multiplication. cost: $0.036
CONTAMINATION NOTE: every decision-grade run in this sweep PRE-DATES that window (RUN ZERO 19:16,
  terra-high k=3 20:11, sol-low k=3 21:47 — all with tight per-draw spreads). Cells 6-9 ran inside
  or across it, so their LATENCY numbers are read as suspect and their ACCURACY as sound (accuracy
  does not depend on wall-clock). No verdict in this sweep rests on a contaminated timing.

## RUN 20260823-231425_gpt-5.6-sol-high — P-M56 cell 9/9 (sol @ high), k=1 all-5 — ties accuracy, LOSES BOTH other axes
ref: RUN ZERO. gate: 4/5 — bagrut/csharp/employee/foundations PASS, hobby FAIL (base signature;
  the SIXTH independent reproduction of the q2.ב silent repair, now spanning 3 tiers x 3 efforts
  x 2 generations).
latency/cost: headline **+37.0%** (251.8s vs 183.8s), suite +23.0%, like-for-like $/doc **+15.5%**
  ($0.2389 vs $0.2069). Slower AND more expensive than the pin it was meant to replace. Timings
  ran inside the degraded window so they are an upper bound — but sol@medium was already +15.4%
  in a CLEAN window and effort=high only adds output tokens, so the direction is not in doubt.
verdict: FALSIFIED for this mission. Not confirmed at k=3 and deliberately not spent on: a cell
  that loses the primary axis cannot become a winner by being measured more precisely. cost: $1.195

## CLOSING ENTRY 2026-08-23 — P-M56 gpt-5.6 sweep: ALL 9 CELLS MEASURED, **NO WINNER**. Prod pin stays gpt-5.5/medium.
scope: owner-ordered (2026-08-23) — find a gpt-5.6 (luna|terra|sol) x effort (low|medium|high)
  pairing with equal-or-better accuracy AND cost at LOWER latency. Stop at a confirmed winner or
  at exhaustion. Outcome: EXHAUSTED, no winner. 12 runs, 65 scored trials, $11.35.

THE 3x3 MAP (k=1 screens; k=3 where confirmed. base = 12/15, headline 183.8s, $0.2069/doc l-f-l):
  model \ effort |      low       |     medium      |      high
  luna           |  1/5           |  0/5            |  1/5
  terra          |  3/5           |  3/5            |  4/5 -> **10/15 @k=3**
  sol            |  3/5 -> **11/15 @k=3** | 4/5 (+15.4% t) | 4/5 (+37.0% t, +15.5% $)

WHY EACH ROW DIED — three distinct mechanisms, not one:
  luna (economy): capability. Fails the CLEAN-TABLE CONTROL at every effort (csharp criterion
    recall/precision 0.750-0.958) and at medium drops whole QUESTIONS (question_recall 0.500).
    Not a latency story either: at high it burns MORE reasoning than gpt-5.5 (7723 vs 3291 on
    foundations) and still lands +2% on that fixture. Cheapness cannot buy the gate.
  terra (mid): a knife-edge between two failure modes with NO passing setting between them.
    At low/medium it UNDER-EXECUTES (10-of-14 example solutions lost; q1.ב flattened, the FP2
    signature). Raising effort fixes that and immediately buys the OPPOSITE failure: at high,
    2/3 bagrut draws inject a SPURIOUS criterion at q1.ב.2 and manufacture a false
    rubric_mismatch + false point_sum_mismatch on a node the teacher wrote correctly — the
    CRY-WOLF half of FC. The single clean draw is the one where a validation retry fired.
  sol (frontier): DECODE RATE, measured ~57-66 tok/s vs base gpt-5.5 ~70, terra ~77, luna ~127.
    Its accuracy ties base at medium/high, but it is structurally unable to win the mission's
    primary axis: it cannot buy latency by emitting fewer tokens because tokens are not what makes
    it slow. sol-low (the only fast-enough sol) fails bagrut 1/3 on a lost solution. This doubt
    was PRE-REGISTERED before sol-low ran, and confirmed.

THE CROSS-CUTTING FINDING (bigger than the sweep): **the prod pin itself now violates FC.**
  RUN ZERO established that gpt-5.5/medium on prompt 3.7.0-tabledir emits hobby q2.ב = 45.0 —
  the lumped total the teacher never wrote — instead of the 29 the teacher DID write, erasing both
  rubric_mismatch annotations and both Tier-A point_sum_mismatch mistakes. SIX independent
  model/effort configurations (gpt-5.5@med, terra@low/med/high, luna@high, sol@low/med/high)
  reproduce it IDENTICALLY, with the identical point_exactness 0.9792. That uniformity across
  three tiers and two generations is the attribution: it is TREE/PROMPT-borne, not model-borne.
  The GT was transcribed from a faithful gpt-5.5 probe at prompt 3.5.0, so the behaviour was
  introduced somewhere in 3.5.0 -> 3.7.0. NOT FIXED HERE (a prompt edit is a second variable and
  would invalidate the sweep it serves). It is the highest-value follow-up in this area and it
  is a LIVE PRODUCTION DEFECT, not an eval artifact: today's deployed extractor silently repairs
  a teacher's arithmetic error on the rubric-review gate.

RECOMMENDATION: keep `EXTRACTION_LLM_MODEL=gpt-5.5`, `REASONING_EFFORT=medium` (CLAUDE.md D-2).
  Do NOT adopt any gpt-5.6 cell. The nearest miss, terra@high, is genuinely tempting on economics
  (-61% $/doc, -24.5% suite latency) and its gap to base is ONE named defect on ONE fixture
  (spurious criterion at bagrut q1.ב.2, 2/3 draws) — if someone wants to chase it, that is the
  target, and it needs its own mission with its own kill criterion. It is not adoptable today.

WHAT THE PROTOCOL BOUGHT (worth keeping): the k=1 -> k=3 rule paid for itself twice in one evening.
  terra-high passed 4/5 at k=1 and collapsed to 10/15 at k=3 (1 clean draw in 3 — a k=1 screen had
  a ~1/3 chance of showing the truth and showed the lucky one), and its headline win shrank from
  -24.5% to -11.0% on the same re-measurement. Both halves of a k=1 result were optimistic. Nothing
  was promoted on a k=1 number.

artifacts: configs/gpt-5.6-*.json (9, verdicts stamped in their notes) · registry entries
  gpt-5.6-terra/-sol · PREDICTIONS.md P-M56 (pre-registered before run one) · 12 results dirs
  20260823-19* .. -23*. suite_hash 19607f69e6bc3432 on every run incl. the baseline, so the whole
  sweep is internally comparable; it is NOT comparable to any pre-2026-08-23 hash.
cost: $11.353 total (under-reported by the Tier-B spend, B-30a). wall: ~19:16-23:25.
corrections: my scratch analysis helper priced INVALID records at $0 and briefly reported sol-low
  at "-22.2% $/doc"; corrected to valid-only, like-for-like (-6.7% at k=1, -22.7% at k=3). The
  suite's own reporting.py was never affected. Logged at RUN 20260823-203248.

## CORRECTION 2026-08-24 — RETRACTION: the hobby q2.ב "silent repair / FC violation / live production defect" claim was WRONG
retracts: the FINDING block in `RUN 20260823-191643_prod_gpt55` (RUN ZERO); every repetition of
  "silent repair" in `RUN 20260823-194348` (terra), `-195615` (luna-high), `-200259` (sol),
  `-203248` + `-214739` (sol-low), `-231425` (sol-high); and the "THE CROSS-CUTTING FINDING"
  paragraph of the P-M56 CLOSING ENTRY. Those entries stay as written (append-only); THIS entry
  is the correction of record. ONBOARDING.md §1/§8 have been rewritten to match.
what was claimed: that gpt-5.5/medium on prompt 3.7.0-tabledir "silently repairs" hobby q2.ב by
  emitting 45.0 instead of the teacher's 29, "erasing" the diagnostics, and that this was a LIVE
  PRODUCTION FC VIOLATION on the rubric-review gate.
what is actually true (owner ran the fixture through the live extractor 2026-08-24 and ruled;
  re-verified by me against this suite's OWN persisted prediction, RUN ZERO
  predictions/hobby_tvshow_r0.json): the extraction emits `structural_mislabel@q2` carrying
  (a) an explanation that names the root cause AND states the remediation "...ויעדכן את ניקוד
  סעיף ב׳ ל-29 כך שסך השאלה יישאר 60 נקודות", and (b) a MACHINE-EXECUTABLE `suggested_fix` with
  steps: move_criterion q2.ב[6] -> q2.ג · move_text q2.ב -> q2.ג · **set_points q2.ב value="29"
  current_value="45"**. The teacher is shown the error, its cause, and a one-click fix that
  restores 29. That is capture -> surface -> propose -> teacher decides. It is FC WORKING, not
  FC violated. Nothing is silent and nothing is repaired behind her back.
why I got it wrong (the methodological lesson, which is the point of logging this): I read
  `pedagogical_mistakes` ONLY as the scorer's match keys — the (kind, target_id) tuples the
  set-comparison uses — and never opened the payload. The scorer compares keys BY DESIGN;
  a human reading its output must not inherit that projection. `explanation`, `suggested_fix`,
  `evidence` and `explained_by` are exactly where "did the teacher actually get told?" is
  answered, and I never looked. Prime directive 5 ("read the reports by hand") extends to the
  PREDICTION payload, not just the report tables. A gate failure is evidence that predicted !=
  GT — it is NEVER by itself evidence of a product defect.
what the divergence REALLY is: a REPRESENTATION CONVENTION difference between GT and current
  behaviour, both of which surface the one teacher error with a fix.
    GT convention:  ב declared 29 (teacher's literal) -> rubric internally INCONSISTENT ->
      Tier-A emits point_sum_mismatch@q2 (44 vs 60) + @q2.ב (45 vs 29), both `explained_by`
      the structural_mislabel, whose fix sets q2.ג = 16.
    live behaviour: ב declared 45 (sum of what is placed under ב) -> internally CONSISTENT ->
      no arithmetic shadows -> the structural_mislabel carries the whole story, and its fix
      sets q2.ב = 29 (current_value 45 stated explicitly).
  The gate fails only because annotations/mistakes are set-compared by key, so absent shadows
  read as a miss. OWNER RULING 2026-08-24: the live behaviour is correct.
consequence for the GT (SURFACED, NOT TOUCHED — GT is owner territory, STOP list): if the ruling
  stands, then `benchmarks/hobby_tvshow.json` and `RUBRIC_EVAL_PLAYBOOK.md` §4's worked example
  are what now diverge — the playbook says in as many words "the faithful GT therefore declares
  ב = 29 ... NOT 45, the lumped sum the teacher never wrote", and §4's pedagogical-consistency
  invariant (GT == TierA(faithful draft) + expected Tier-B) is what mechanically produces the two
  shadows GT expects. Updating either is a Noam decision and needs the invariant re-derived, not
  a benchmark hand-edit. Until then hobby_tvshow fails the gate for EVERY model, uniformly.
consequence for the P-M56 sweep: **NONE.** Every terra and sol cell failed hobby with the identical
  signature, so it cancels in every cell-vs-base comparison. The verdict stands unchanged: no
  gpt-5.6 cell is adoptable, and terra-high's gap to base is ENTIRELY bagrut. What changes is only
  the characterisation of hobby — it is a GT/convention divergence, not a defect, and the words
  "live production defect" should never have been written.
corrections: this entry corrects the entries named at the top.

## CHANGE 2026-08-24 — SNAPSHOT + PROMPT 3.7.0-tabledir -> 3.8.0-labeltest (terra-high chase, iteration 1; ONE variable)
mission: owner-ordered 2026-08-24 — close terra-high's gap to gpt-5.5 and win on cost+latency with
  NO other benchmark regression. One variable per iteration.
(0) ROLLBACK SNAPSHOT taken first, per the order: snapshots/2026-08-24_pre-terra-chase/ —
  EXTRACTION_SYSTEM_PROMPT.txt (22,890 chars, extracted from the live module, not hand-copied),
  pipeline.py.snapshot, parser_render.py.snapshot, models_registry.py.snapshot, all 16 configs,
  pipeline_vs_HEAD.patch, git_head.txt, and MANIFEST.md with a one-step restore recipe.
  The `.snapshot` suffix is load-bearing: `_suite_hash` globs suite_dir.rglob("*.py"), so a real
  .py copy under the suite would have shifted the hash and made this chase incomparable to its
  own baseline. Verified: hash still 19607f69e6bc3432 after the snapshot landed.
diagnosis (from the k=3 artifacts, no new spend): terra-high's bagrut failures are ONE parsing
  error, twice — it emits the point-TOTAL label rows as criteria ("ניקוד: 3 נקודות" 3.0 @ q1.א.2,
  "ניקוד: 4 נקודות" 4.0 @ q1.ב.2), identical in both failing draws, ZERO criteria missed. At
  q1.ב.2 that doubles the node (4 real + 4 phantom vs declared 4) and the pipeline then honestly
  raises point_sum_mismatch + rubric_mismatch on a node the teacher wrote CORRECTLY.
  The prompt ALREADY had the right rule (SECTION 7 L215/L216). The gap is that L216 says the
  label is a total when "FOLLOWED by itemized component lines", and in BOTH failing cases the
  components are NOT adjacent — they sit behind an intervening line that is itself defined as
  non-criteria by the prompt: q1.א.2 has a DEDUCTION note (L218's class) between label and
  components; q1.ב.2 has a פתרון: EXAMPLE-SOLUTION line (L217's class). The control case that
  terra gets RIGHT (q1.ב.1) is the one with no components at all. gpt-5.5 bridges the gap;
  terra reads "FOLLOWED by" literally, falls through to L215, and emits the label.
what changed (exactly one rule pair, SECTION 7): L215/L216 replaced by an explicit TOTAL-LABEL
  TEST — scan the scope's WHOLE scoring block before emitting; components anywhere in the block
  => the label is the scope's points and each component is a criterion, and the label itself is
  NOT emitted; only a block with no components anywhere makes the label a criterion. Plus a named
  "INTERVENING LINES DO NOT BREAK THE ASSOCIATION" clause (solution lines and deduction notes are
  not separators) and a WHY paragraph stating the cost of the error (double-counting -> a false
  alarm on a correct node -> destroys trust in real flags).
  Nothing else touched: no other section, no pipeline code, no config, no GT, no scorer.
version: EXTRACTION_PROMPT_VERSION 3.7.0-tabledir -> **3.8.0-labeltest**. PIPELINE_VERSION stays
  3.6.2. suite_hash UNCHANGED (19607f69e6bc3432) — the prompt lives outside the suite by design,
  which is why prompt_version is stamped separately. 46/46 instrument guards green after the edit.
affects: RE-BASELINING IS OWED. Every P-M56 number was measured at 3.7.0. This chase compares
  terra-high@3.8.0 against gpt-5.5@3.7.0 for the ABSOLUTE bar (does it reach 12/15 with base's
  pass set), and the incumbent gpt-5.5 MUST be re-run at 3.8.0 before any adoption claim — a
  prompt that fixes terra but regresses the deployed pin is a net loss, and only that run can
  falsify it. Planned as the last step, not skipped.
by: agent, on Noam's 2026-08-24 order.
kill criterion for iteration 1 (pre-registered, before the screen returns): the two phantom
  criteria must be GONE from bagrut (spurious_criteria empty) with no new failure on any fixture.
  If phantoms persist -> the prompt surface is not the lever and the next iteration is the
  deterministic one (a retryable POINTS_LABEL_AS_CRITERION validation issue, which is a
  DIFFERENT class from the 3.1.0 non-retryable point-mismatch policy and must not be conflated
  with it). If phantoms go but a NEW failure appears elsewhere -> revert and rethink.

## RUN 20260824-120539_gpt-5.6-terra-high — chase iteration 1 SCREEN (prompt 3.8.0-labeltest), k=1 all-5 — TARGET MET, one residual
ref: 20260823-201145 (terra-high k=3 @ prompt 3.7.0) for the defect; 20260823-191643 (gpt-5.5 @
  3.7.0) for the bar. ONE variable vs the terra-high k=3 run: prompt 3.7.0 -> 3.8.0-labeltest.
config: gpt-5.6-terra-high  k: 1  suite_hash 19607f69e6bc3432 (unchanged — prompt is outside the suite)
validity: 5/5 valid. gate: 3/5.
KILL CRITERION (pre-registered before the run): "the two phantom criteria must be GONE with no new
  failure on any fixture." **MET.** spurious_criteria = [] on ALL FIVE fixtures (was
  ['ניקוד: 3 נקודות','ניקוד: 4 נקודות'] on bagrut), missed_criteria = [] everywhere (the fix cost
  NO recall — it did not trade a phantom for a miss), criterion_precision back to 1.0, and the
  spurious rubric_mismatch@q1.ב.2 + spurious point_sum_mismatch@q1.ב.2 are GONE. csharp, employee
  and foundations still PASS — no collateral damage on the clean-table control or anywhere else.
residual (the ONLY thing still failing bagrut): example_solution_fidelity 0.923 — q5.א, ratio
  0.7905 vs the 0.85 bar. Same scope and the IDENTICAL ratio as the 3.7.0 k=3 r2 failure, so it is
  a stable recurring defect, not a flake.
diagnosed (free, from artifacts): terra TRIMS the trailing ruler line that closes the solution
  block. GT q5.א ends "...GetName();
}
//---------------------------------------------------".
  terra's failing draws end at "}". INSTRUMENT CLEARED — this is NOT a GT artifact: gpt-5.5 emits
  the ruler on ALL THREE draws, and terra's OWN passing draw at 3.7.0 emitted it too. GT matches
  strong-model behaviour; the omission is a real fidelity gap. (Contrast ONBOARDING §9 item 3,
  where a GT solution DOES carry questionable furniture — that one stays owner-territory; this one
  is model behaviour and is fixable from the prompt.)
hobby: unchanged, still the GT/convention divergence (CORRECTION 2026-08-24) — a constant.
latency/cost at k=1: headline 147.4s vs base 183.8s = -19.8%; like-for-like $/doc -57.2%.
THE PATTERN (worth more than either fix): BOTH defects were already covered by the prompt.
  SECTION 7 L215/L216 had the total-label rule; SECTION 4 L160 lists "//------" separator lines by
  name as must-copy ink. terra does not fail for lack of a RULE — it fails to apply rules written
  as PROSE LISTS, and applies the same rules when written as explicit named PROCEDURES with a
  negative case ("do NOT emit X") and a stated consequence. gpt-5.5 bridges prose; terra needs the
  test spelled out. That is a reusable fact about prompting a cheaper tier, not a bagrut fact.
next: iteration 2 — ONE variable, prompt 3.8.0 -> 3.9.0-blockend: a BLOCK-BOUNDARY TEST in
  SECTION 4 (walk forward to the next scope's content; a closing "}" is not a stop signal; a ruler
  line after it still belongs to this solution; never invent a ruler that is not in the source).
  kill criterion: q5.א example_solution ratio >= 0.85 with example_solution_fidelity == 1.0 on
  bagrut, AND csharp's seven verbatim code solutions still at 1.0 (the over-capture risk — a
  boundary rule that runs too far would swallow the next solution's header there first).

## CHANGE 2026-08-24 — PROMPT 3.8.0-labeltest -> 3.9.0-blockend (chase iteration 2; ONE variable)
what: SECTION 4 gains a BLOCK-BOUNDARY TEST — walk forward from the solution's first line to the
  next scope's content (its label, rubric table, or scoring lines) and copy everything before that
  boundary; "the end of the CODE is not the end of the BLOCK"; a closing "}" is NOT a stop signal
  and a ruler line after it still belongs to this solution; and an explicit anti-invention clause
  ("copy only what is actually present — never add a ruler the teacher did not write").
why: iteration 1 left exactly one failure — bagrut q5.א example_solution ratio 0.7905 (< 0.85),
  terra trimming the "//----" ruler that closes the block. The rule already existed (L160 lists
  "//------" separator lines BY NAME as must-copy ink); it was prose in a long list. Same shape as
  iteration 1: terra applies procedures, not prose lists.
version: EXTRACTION_PROMPT_VERSION 3.8.0-labeltest -> 3.9.0-blockend. Pipeline/scorer/GT/configs
  untouched; suite_hash unchanged (19607f69e6bc3432); 41/41 suite guards green.
by: agent, on Noam's 2026-08-24 order.

## RUN 20260824-121533_gpt-5.6-terra-high — chase iteration 2 SCREEN (prompt 3.9.0-blockend), k=1 all-5 — KILL CRITERION MET
ref: 20260824-120539 (iteration 1) — ONE variable: prompt 3.8.0 -> 3.9.0.
gate: **4/5 — base's pass set exactly.** bagrut PASS, csharp PASS, employee PASS, foundations PASS,
  hobby FAIL (the GT/convention constant).
kill criterion (pre-registered): "q5.א ratio >= 0.85 with example_solution_fidelity == 1.0 on
  bagrut, AND csharp's seven verbatim code solutions still 1.0." **BOTH MET.** Every fixture now
  reports example_solution_fidelity 1.000, criterion_precision 1.000, criterion_recall 1.000,
  spurious_criteria [] and missed_criteria [] — csharp included, so the over-capture risk the
  criterion was written to catch did NOT materialise.
latency/cost at k=1: headline 161.2s vs base 183.8s = -12.3%; like-for-like $/doc -57.1%.
  bagrut cost 12602 out tokens (vs 11924 at 3.8.0) — the boundary rule buys its fidelity with a
  small, expected output increase.
NOT PROMOTED: k=1 is exactly the evidence that lied at prompt 3.7.0 (4/5 at k=1 -> 10/15 at k=3).
next: k=3 all-5 confirmation of terra-high @ 3.9.0. Promotion criteria (unchanged): base's pass
  set on every draw (12/15, no NEW failure class), headline < 183.8s, like-for-like $/doc <=
  $0.2069. AFTER that, and only then, the incumbent re-baseline: gpt-5.5 k=3 @ 3.9.0 — a prompt
  that fixes terra but regresses the deployed pin is a net loss, and that run is the only thing
  that can falsify it.

## RUN 20260824-122318_gpt-5.6-terra-high — chase CONFIRMATION, k=3 all-5 @ prompt 3.9.0-blockend — **12/15, base's pass set, every draw clean**
ref: 20260823-201145 (same config, same k, prompt 3.7.0 — 10/15) and 20260823-191643 (gpt-5.5 @ 3.7.0 — 12/15)
variable vs the 3.7.0 terra run: the prompt only (3.7.0 -> 3.9.0, via the two logged iterations).
config: gpt-5.6-terra-high  k: 3  effort: high  pipeline 3.6.2  suite_hash 19607f69e6bc3432
validity: 15/15 valid, ZERO retries on all 15 draws, no truncation.
gate: **12/15** — bagrut 3/3 (was 1/3), csharp 3/3, employee 3/3, foundations 3/3, hobby 0/3
  (the GT/convention constant, identical on every draw). This is base's pass set EXACTLY.
draw-level quality (the thing k=3 exists to check): all 15 draws report spurious_criteria 0,
  missed_criteria 0, example_solution_fidelity 1.000. The 3.7.0 failure modes are gone in EVERY
  draw, not on average — no phantom label-criteria, no trimmed solution, and therefore none of the
  false rubric_mismatch/point_sum_mismatch alarms. bagrut's three draws are tight (147.5/155.5/
  164.4s) with no retry, where at 3.7.0 the single passing draw needed one.
latency/cost vs the 3.7.0 base: headline 155.5s vs 183.8s = **-15.4%**; suite sum-of-medians
  414.2s vs 503.3s = -17.7%; like-for-like $/doc $0.0770 vs $0.2069 = **-62.8%**.
  CAVEAT STATED BEFORE THE NEXT RUN, NOT AFTER: those deltas straddle TWO PROMPTS. 3.9.0 is ~1.2k
  chars longer than 3.7.0 (prefill up) and changes what gets emitted (decode changed), so part of
  the movement may belong to the prompt rather than to the model. The comparison is only clean
  against gpt-5.5 measured on the SAME prompt. That run is now in flight and is the arbiter of
  BOTH remaining success conditions (better cost, better latency, no regression).
next: RUN gpt-5.5 k=3 @ 3.9.0 (incumbent re-baseline). Pre-registered readings:
  (a) if gpt-5.5 holds 12/15 with its pass set -> the prompt is safe for the deployed pin, and the
      terra-vs-gpt-5.5 comparison is re-computed on THAT run;
  (b) if gpt-5.5 REGRESSES anywhere -> the prompt is a net loss regardless of what terra does, and
      the snapshot rollback is the answer, not a patch on top;
  (c) if gpt-5.5 IMPROVES (e.g. hobby flips) -> that is a finding about the prompt, and terra must
      then match the NEW bar, not the old one.

## RUN 20260824-124427_prod_gpt55 — INCUMBENT RE-BASELINE, gpt-5.5 k=3 all-5 @ prompt 3.9.0-blockend — NO REGRESSION (reading (a))
ref: 20260823-191643_prod_gpt55 (same config, same k, prompt 3.7.0). ONE variable: the prompt.
purpose: the falsification run for the chase — a prompt that fixes terra but costs the DEPLOYED
  pin anything is a net loss. Three readings were pre-registered before it ran (see RUN
  20260824-122318); this is reading **(a)**.
config: prod_gpt55  k: 3  model gpt-5.5  effort medium  suite_hash 19607f69e6bc3432
validity: 15/15 valid, 0 retries, no truncation.
gate: **12/15 — bagrut 3/3, csharp 3/3, employee 3/3, foundations 3/3, hobby 0/3.** IDENTICAL pass
  set to its own 3.7.0 run. The prompt is SAFE for the production pin: no fixture, no metric, no
  draw regressed. (b) and (c) are FALSIFIED — it neither broke nor improved the incumbent.
its own latency/cost vs 3.7.0: headline +2.4%, suite sum-of-medians +1.2%, like-for-like $/doc
  +3.1% — all INSIDE the 1-11% noise band. The 3.9.0 prompt is ~1.2k chars longer, and that shows
  up as nothing measurable for gpt-5.5. This is what retires the cross-prompt caveat logged on
  RUN 20260824-122318: the earlier terra-vs-base deltas were NOT prompt artefacts.

## VERDICT 2026-08-24 — the terra-high chase SUCCEEDS. Same prompt, same k, same instrument.
the comparison the mission asked for (terra-high @ 3.9.0 k=3 vs gpt-5.5 @ 3.9.0 k=3 — one variable,
the model+effort; identical prompt 3.9.0-blockend, pipeline 3.6.2, suite_hash 19607f69e6bc3432):
  ACCURACY  12/15 vs 12/15 — IDENTICAL pass sets. Every one of terra's 15 draws reports
            spurious_criteria 0, missed_criteria 0, example_solution_fidelity 1.000, retry 0.
            The only failing fixture is hobby, which fails IDENTICALLY for both models and is the
            GT/convention constant (CORRECTION 2026-08-24), not a discriminator.
  LATENCY   headline 155.5s vs 188.1s = **-17.4%**; suite sum-of-medians 414.2s vs 509.4s =
            **-18.7%**. Faster on EVERY fixture: bagrut -17%, csharp -25%, employee -18%,
            foundations -16%, hobby -20% — all beyond the 1-11% clean-fixture noise band.
  COST      like-for-like **$0.0770/doc vs $0.2132/doc = -63.9%**.
owner's success bar ("better at cost/latency with NO other benchmark regressions"): **MET.**
how it was earned — two prompt iterations, one variable each, on a defect that was never a model
  capability wall: (1) 3.8.0-labeltest killed the phantom point-label criteria and with them the
  false rubric_mismatch/point_sum_mismatch alarms; (2) 3.9.0-blockend stopped the solution block
  being trimmed at the closing brace. BOTH rules already existed in the prompt as PROSE; terra
  applies them once written as named PROCEDURES with a negative case and a stated consequence.
  That is the transferable finding: the cheaper tier does not need more rules, it needs the same
  rules made procedural. gpt-5.5 is unaffected either way (this run proves it).
NOT YET ADOPTED — what adoption still needs, stated plainly:
  - k=3 is the owner's bar, not proof of identity: 3 clean draws/fixture bounds per-trial failure
    only loosely (~<10% by the rule of three over 15 trials). The 3.7.0 lesson (4/5 at k=1 ->
    10/15 at k=3) is the standing warning against reading a small k as safety.
  - the fixtures are FIVE rubrics from one subject; nothing here says terra generalises to an
    unseen exam shape. The prompt iterations were authored against bagrut's specific failures,
    so some over-fitting risk to this fixture set is real and is NOT measurable from inside it.
  - prod pin change is a D-2 decision (CLAUDE.md §12 env: EXTRACTION_LLM_MODEL/REASONING_EFFORT)
    and belongs to Noam, together with the registry's sol/terra price caveats.
  - the hobby GT/convention fix is PROPOSED AND AWAITING APPROVAL (nothing edited). If approved,
    both models go to 15/15 and the comparison above is unchanged in shape — the delta is
    hobby-independent by construction.
cost: $3.283 (this run) — chase total $6.50 across 6 runs; sweep+chase grand total ~$17.85.

## CHANGE 2026-08-24 — PROD PIN (D-2) FLIPPED: gpt-5.5/medium -> gpt-5.6-terra/high (owner-ordered)
what (in-repo, done): app/config.py extraction pin defaults gpt-5.5/medium -> gpt-5.6-terra/high,
  plus extraction_llm_max_tokens 38000 -> 32000 (aligning the code default with BOTH the deployed
  Cloud Run value and the eval config the pin was validated at — a latent 3-way drift that would
  only have surfaced if the env var were ever removed; non-binding either way, the largest
  single-call output observed on any fixture is ~18k). CLAUDE.md §12 D-2 rewritten with the
  evidence and the two ⚠ traps below. configs/gpt-5.6-terra-high.json marked THE PROD PIN;
  configs/prod_gpt55.json marked ROLLBACK REFERENCE. 46/46 guards green; app.main imports.
why (the evidence, all from runs in this ledger): terra-high vs gpt-5.5 measured on the SAME
  prompt (3.9.0-blockend), SAME pipeline (3.6.2), SAME instrument (suite_hash 19607f69e6bc3432),
  both k=3 all-5 — RUN 20260824-122318 vs RUN 20260824-124427:
    accuracy 12/15 vs 12/15, IDENTICAL pass sets; all 15 terra draws report spurious_criteria 0,
      missed_criteria 0, example_solution_fidelity 1.000, retry 0. The only failing fixture is
      hobby, which fails identically for BOTH models (the GT/convention constant).
    latency headline 155.5s vs 188.1s = -17.4%; suite sum-of-medians -18.7%; faster on EVERY
      fixture (-16% to -25%), all beyond the 1-11% noise band.
    cost like-for-like $0.0770/doc vs $0.2132/doc = -63.9%.
  The incumbent was re-baselined on the new prompt FIRST (RUN 20260824-124427) precisely so this
  flip could not rest on a cross-prompt comparison: gpt-5.5 holds 12/15 with an unchanged pass set
  at 3.9.0, and its own latency/cost moved +1.2%/+3.1% (inside noise).
⚠ TRAP 1 — MODEL AND PROMPT ARE A PACKAGE. terra-high is 12/15 on prompt 3.9.0-blockend and
  **10/15 on 3.7.0-tabledir** (RUN 20260823-201145: it emits point-total label rows as criteria,
  producing FALSE rubric_mismatch/point_sum_mismatch alarms on nodes the teacher wrote correctly).
  Setting this pin on an image built before 3.9.0 SHIPS A REGRESSION. gpt-5.5 is 12/15 on both
  prompts, which is what makes the model half a safe one-line rollback.
⚠ TRAP 2 — THE CODE DEFAULT IS NOT PRODUCTION. Verified live 2026-08-24: the Cloud Run service
  `gradervision-backend` sets EXTRACTION_LLM_PROVIDER/MODEL/REASONING_EFFORT/MAX_TOKENS as
  EXPLICIT env vars (openai / gpt-5.5 / medium / 32000), and config.py bridges its defaults with
  `setdefault`, so the service env WINS. **This change alone does not alter production.** The live
  revision is gradervision-backend-00037-tt7, created 2026-08-23T11:55Z — i.e. BEFORE the 3.8.0/
  3.9.0 prompt work, so its image carries prompt 3.7.0. Flipping only the env var on that image
  would land exactly the 10/15 configuration of TRAP 1.
STATUS: production is UNCHANGED and still serving gpt-5.5/medium on prompt 3.7.0 (12/15). The
  deploy that would make this live is SURFACED TO THE OWNER, not executed — it is an outward-facing
  change to a service real teachers use, and it must ship the prompt and the pin TOGETHER:
    gcloud run deploy gradervision-backend --source backend \
      --project gen-lang-client-0438328890 --region europe-west1 \
      --update-env-vars EXTRACTION_LLM_MODEL=gpt-5.6-terra,EXTRACTION_LLM_REASONING_EFFORT=high
  (one command: --source rebuilds the image from the local tree, carrying prompt 3.9.0-blockend,
  and --update-env-vars flips the two overrides in the same revision. Existing env/secrets are
  preserved.) ROLLBACK is a revision revert, or the same command with gpt-5.5/medium.
by: Noam (ordered the flip); agent (executed the in-repo half, surfaced the deploy).
affects: nothing already measured. Every eval number in this ledger was produced by the eval
  runner's own per-run env override, which is unaffected by this default.

## CHANGE 2026-08-24 — backend/.gcloudignore ADDED (deploy-hygiene; owner-approved)
what: NEW backend/.gcloudignore — excludes .env / .env.* / *.pem / *.key /
  gen-lang-client-*.json / *service-account*.json / *credentials*.json, the venvs and
  caches, tests/ and scripts/, run artifacts, and (owner-requested) *.md.
why: `gcloud run deploy --source backend` uploads the source directory to the project's
  _cloudbuild staging bucket, where it PERSISTS as a build artifact. With no
  .gcloudignore, gcloud INFERS the ignore set from backend/.gitignore — which probably
  did the right thing (it lists .env, .venv and gen-lang-client-*.json), but inference is
  not a guarantee, and this directory holds a GCP SERVICE-ACCOUNT PRIVATE KEY plus a .env
  with OpenAI/Anthropic/xAI/LangSmith keys, DATABASE_URL and SUPABASE_ACCESS_TOKEN.
  "Probably excluded" is not the standard for a private key; CLAUDE.md §10 names these
  two filenames explicitly as never-commit items.
safety check done BEFORE writing it (the *.json trap): app/ contains ZERO .json files, so
  no runtime asset is stripped; its two .md files are docs/debug and are never READ
  (rendered_output.md is write-only, parser_render.py:676). A rule-simulation over the
  file confirmed requirements.txt / Dockerfile / app/**.py all still ship while .env,
  .env.pre-vertex-bak, gen-lang-client-*.json, tests/ and .venv/ are all excluded.
  The runtime image is unaffected regardless: the Dockerfile copies ONLY app/ + requirements.txt.
by: agent surfaced; Noam approved and requested the *.md addition.

## DEPLOY 2026-08-24 — prod pin gpt-5.6-terra/high + prompt 3.9.0-blockend went LIVE (owner-ordered)
command: gcloud run deploy gradervision-backend --source backend
  --project gen-lang-client-0438328890 --region europe-west1
  --update-env-vars EXTRACTION_LLM_MODEL=gpt-5.6-terra,EXTRACTION_LLM_REASONING_EFFORT=high
  ONE revision carries BOTH halves, which TRAP 1 (previous entry) requires: --source rebuilt the
  image from the working tree (prompt 3.9.0-blockend) while --update-env-vars flipped the two
  overrides that actually govern prod.
result: revision **gradervision-backend-00038-tq7**, 100% of traffic (was 00037-tt7, built
  2026-08-23T11:55Z on prompt 3.7.0).
VERIFIED POST-DEPLOY (each of these was checked, not assumed):
  - live env: EXTRACTION_LLM_PROVIDER=openai, MODEL=gpt-5.6-terra, REASONING_EFFORT=high,
    MAX_TOKENS=32000. All other service env survived --update-env-vars (APP_ENV, DATABASE_URL,
    TRANSCRIPTION_ENGINE, EXTRACTION_EXECUTION_MODE, GCS_BUCKET_NAME, OPENAI_API_KEY, ...).
  - prompt shipped: pipeline.py was NOT among the 58 skipped upload entries (under app/ only
    __pycache__ dirs and ONTOLOGY_INTEGRATION_PLAN.md were skipped); local constant reads
    EXTRACTION_PROMPT_VERSION="3.9.0-blockend", mtime 12:14, upload began 13:49.
  - secrets excluded — the .gcloudignore did its job, from gcloud's own log:
    "Using ignore file at [backend\.gcloudignore]" then "Skipping file [.env]",
    "Skipping file [.env.pre-vertex-bak]", "Skipping file [gen-lang-client-...json]".
  - boot clean: "SCHEMA OK: migration head 017 (17 applied; 1 constraint attribute(s) + 3 partial
    index(es) verified)", "create_all SKIPPED (APP_ENV=production)", startup complete, no errors.
  - GET /health -> HTTP 200 in 0.77s.
ALSO SHIPPED (owner-accepted, outside this mission's verification): app/api/v0/batch_grading.py
  and app/services/transcription/two_phase/{pipeline,trust}.py + two_phase_engine.py — in-flight
  work from other sessions that was newer than revision 00037. Migration 017, which the
  batch_grading change depends on, is confirmed applied to the prod DB (ledger 001-017 complete).
WHAT IS **NOT** PROVEN BY THIS DEPLOY: no rubric has been extracted in production on the new pin.
  The evidence is the eval suite (k=3, 5 fixtures) plus a clean boot — the prod path adds Cloud
  Tasks dispatch, GCS fetch and the 840s wall budget, none of which the suite exercises. terra-high's
  worst measured doc is ~155s against that 840s budget, so the margin is large, but the first live
  extraction is the real confirmation. A live smoke is one rubric upload away and is NOT done here.
ROLLBACK (either is one step): `gcloud run services update-traffic gradervision-backend
  --to-revisions gradervision-backend-00037-tt7=100` (reverts pin AND prompt together), or re-run
  the deploy with EXTRACTION_LLM_MODEL=gpt-5.5,EXTRACTION_LLM_REASONING_EFFORT=medium (keeps the
  new prompt; safe because gpt-5.5 scores 12/15 on BOTH prompts).
by: Noam (ordered deploy + accepted the extra files + requested *.md in .gcloudignore); agent executed.

## RUN 20260824-155058_gpt-5.6-terra-high — REGRESSION CONFIRMED (owner-reported): terra omits the SOURCE-side set_points in the Tier-B fix
ref: owner ran hobby_tvshow through the LIVE extractor 2026-08-24 and reported: accepting the
  proposed fix created סעיף ג' with 16 points correctly, but did NOT reduce סעיף ב' 45 -> 29.
purpose: k=3 hobby-only trial on the DEPLOYED config to test consistency. (--only = screening subset.)
config: gpt-5.6-terra-high  k: 3  prompt 3.9.0-blockend  pipeline 3.6.2 — i.e. exactly what
  revision 00038-tq7 serves.
RESULT — CONSISTENT, 3/3 draws omit it. Pooled over every draw on this tree: terra-high @3.9.0 is
  **0 of 7**. Full census of the suggested_fix steps by model:
    gpt-5.5   @3.7.0  3/3 emit set_points@q2.ב=29     gpt-5.5   @3.9.0  3/3 emit it
    terra-hi  @3.7.0  2/3                              terra-hi  @3.8.0  0/1
    terra-hi  @3.9.0  0/7   <-- DEPLOYED               terra-med @3.7.0  0/1
    sol-med   @3.7.0  0/1                              sol-low   @3.7.0  3/3
  gpt-5.5 never misses it, on either prompt. It is MODEL-attributable, and the swap put it in prod.
IMPACT (simulated by applying each model's own steps to its own draft):
    gpt-5.5's fix  -> א15 + ב29 + ג16 = 60 = declared. ב 29 == its criteria 29. FULLY RESOLVES.
    terra's fix    -> א15 + ב45 + ג16 = **76 vs declared 60**, and ב declared **45 vs criteria 29**.
  The teacher accepts a proposed fix and lands with TWO mismatches, one of which (76 vs 60) did not
  exist before she accepted. That is worse than not offering a fix at all — it is the trust
  failure the review gate exists to prevent (CLAUDE.md §2: propose, teacher decides).
ROOT CAUSE — the same shape as the two defects fixed in the chase, in a DIFFERENT prompt.
  The Tier-B prompt (app/services/docx_v3/pedagogical_mistakes.py, the EditStep block ~L365) says:
  "a to_scope that does not exist is created automatically ... a sub-question created this way
  AUTOMATICALLY receives points equal to the sum of the criteria moved into it; add set_points FOR
  IT only if the correct points differ from that sum."
  It fully specifies the TARGET's points and is SILENT on the SOURCE: nothing states that moving a
  criterion OUT of a scope leaves that scope's declared points stale and needing an explicit
  set_points. gpt-5.5 infers the unstated half (6/6); terra does not (0/7). Prose vs procedure,
  third instance.
INSTRUMENT BLIND SPOT (the reason the sweep never caught this, and an owner decision):
  `pedagogical_match` set-compares mistakes by (kind, canonical target) ONLY — `suggested_fix`,
  its steps, and `explanation` are NEVER scored. So a fix payload can be wrong, or absent, and the
  fixture still passes. Every "12/15 = 12/15, identical pass sets" statement in this ledger remains
  literally true and was scoped to what the gate measures; this field is outside it. Extending the
  scorer to cover fix steps is a GATE change = STOP list, surfaced here, not taken.
STATUS: production revision 00038-tq7 is LIVE with this defect. Mitigation options put to Noam:
  (A) fastest, no rebuild (~1 min) — `gcloud run services update gradervision-backend
      --update-env-vars EXTRACTION_LLM_MODEL=gpt-5.5,EXTRACTION_LLM_REASONING_EFFORT=medium`
      (new revision on the SAME image, so prompt 3.9.0 is retained; gpt-5.5@3.9.0 is verified
      12/15 and 3/3 on the fix step);
  (B) fix the Tier-B prompt's source-side rule, k=3 re-verify on hobby, redeploy terra;
  (C) (A) now, then (B), then re-deploy terra once it is 3/3.
  Recommendation: (C) — the latency/cost win is not worth a teacher accepting a fix that makes her
  rubric wrong, and (A) is one command and proven safe.
cost: $0.19  corrections: none

## CHANGE 2026-08-24 — TIER-B PROMPT: source-side set_points rule + closing check (regression fix; ONE variable)
what: app/services/docx_v3/pedagogical_mistakes.py `_TIER_B_SYSTEM`, the EditStep ops block —
  added, immediately after the existing TARGET auto-points sentence:
   (1) "המקור אינו מתעדכן אוטומטית — וזו הטעות הנפוצה": move_criterion does NOT change the
       SOURCE scope's declared points; after every move_criterion, compute the sum of the criteria
       REMAINING in the source and add set_points on the SOURCE with that value and the old
       declared as current_value. Skip only if the remaining sum already equals the declared.
   (2) "בדיקת סגירה" — before returning the fix: sum the declared points of all sub-questions AS
       THEY WILL BE after applying the steps and compare to the question's declared total; if they
       differ, a step is missing, almost always a set_points on the source.
  Nothing else changed — no other rule, no code, no schema, no GT, no config.
why: RUN 20260824-155058 — terra omits the source-side step in 0/7 draws, so accepting its fix
  leaves q2 at 76 vs declared 60. The prompt specified the TARGET's points fully and was silent on
  the SOURCE. Rule א already demanded the outcome ("ודאי שההעברה מיישבת גם את סכום השאלה כולה")
  but never named the mechanism; gpt-5.5 infers it, terra does not. Third instance of prose-vs-
  procedure, so the fix is written in the shape that worked twice: explicit procedure + the common
  error named + a closing self-check.
version: EXTRACTION_PROMPT_VERSION 3.9.0-blockend -> **3.10.0-fixsource**. ⚠ NOTE A REAL GAP: the
  Tier-B prompt has NO version constant of its own, so a change to it is invisible to provenance.
  I am borrowing the extraction prompt's constant so this change is not silent. Giving _TIER_B_SYSTEM
  its own stamped version is a follow-up worth taking (it would have made this regression's
  provenance self-evident). suite_hash unchanged (both prompts live outside the suite).
PRE-REGISTERED VERIFICATION — written BEFORE any run, all four must pass to declare success:
  V1 DIRECT (k=3 hobby-only, terra-high): 3/3 draws emit set_points on scope q2.ב with value 29
     (and current_value 45). Anything less than 3/3 = NOT FIXED; k=1 or 2/3 is not success.
  V2 SEMANTIC (simulate applying each draw's own steps to its own draft): for all 3 draws,
     א+ב+ג declared == 60 (the question's declared total) AND ב declared == the sum of the
     criteria remaining in ב (29). This is the test the owner actually ran by hand; the step being
     PRESENT is not enough, it must also carry the right value.
  V3 NO COLLATERAL (k=3 all-5, terra-high): gate result must be >= the 3.9.0 terra k=3 baseline
     (12/15, hobby the only failing fixture) with NO new failure class on ANY fixture, and
     spurious/missed criteria still 0 and example_solution_fidelity still 1.000 everywhere —
     the two earlier chase fixes must not have been disturbed.
  V4 ROLLBACK INTEGRITY (k=3 hobby-only, gpt-5.5): gpt-5.5 must STILL emit the step 3/3 on the NEW
     Tier-B prompt. Without this the documented rollback target is unverified on the shipped tree —
     my earlier "rollback is safe" claim was measured on the OLD Tier-B prompt and does not carry.
by: Noam ruled option (B) with "be extremely rigorous"; agent implemented. Pre-launch window
  (launch 2026-09-01) is why (A) was declined — the prod regression is not urgent to revert.

## RUN 20260824-160706_gpt-5.6-terra-high — V1+V2 of the Tier-B fix (k=3 hobby-only): BOTH PASS 3/3
ref: 20260824-155058 (same config, same k, same fixture, OLD Tier-B prompt — 0/3). ONE variable:
  the Tier-B source-side rule (prompt 3.9.0-blockend -> 3.10.0-fixsource).
config: gpt-5.6-terra-high  k: 3  --only hobby_tvshow (screening subset, diagnostic — NON-PROMOTABLE)
V1 DIRECT — 3/3 PASS. Every draw now emits set_points on scope q2.ב with value 29 and
  current_value 45. Step order varies across draws (r0 puts it between the two moves, r1/r2 last),
  which is fine — the steps are applied as one ordered unit and the value is what matters.
V2 SEMANTIC — 3/3 PASS. Simulating each draw's OWN steps against its OWN draft: א15 + ב29 + ג16
  = 60.0 == the question's declared 60, and ב declared 29 == the 29.0 its criteria sum to after the
  16-point criterion leaves. This is the owner's hand-test, now reproduced green on every draw.
  Before/after on the identical config and fixture: 0/3 -> 3/3 on both criteria.
NOT YET SUCCESS: V3 (k=3 all-5, no collateral damage) and V4 (gpt-5.5 rollback integrity on the
  NEW Tier-B prompt) are pre-registered and still owed. A fix verified only on the fixture it was
  written for is exactly the over-fitting this suite exists to catch — the two earlier chase fixes
  each had to clear an all-5 sweep too, and one of them (3.7.0 terra-high) looked fine at k=1 and
  died at k=3.
cost: $0.19

## RUN 20260824-161209 + 20260824-163444 — V3 + V4 of the Tier-B fix: BOTH PASS. All four criteria met.
V3 NO COLLATERAL (terra-high k=3 all-5 @ prompt 3.10.0-fixsource, RUN 20260824-161209): **12/15**,
  identical to the pre-fix 3.9.0 sweep and to gpt-5.5's own result. bagrut 3/3, csharp 3/3,
  employee 3/3, foundations 3/3, hobby 0/3 — and hobby's ONLY failures are the three known
  GT-convention metrics (annotation_mismatch, pedagogical_mismatch, point_exactness 0.9792).
  NO new failure class on any fixture. The two earlier chase fixes are undisturbed: across ALL 15
  draws spurious_criteria=0, missed_criteria=0, example_solution_fidelity=1.000,
  criterion_precision=criterion_recall=1.000, retries 0, validity 15/15.
  vs gpt-5.5 @3.9.0 (its own k=3, RUN 20260824-124427): headline 156.9s vs 188.1s = **-16.6%**,
  suite sum-of-medians -12.7%, like-for-like $/doc $0.0805 vs $0.2132 = **-62.3%**. The economics
  survive the fix (the extra step costs a few output tokens, nothing structural).
V4 ROLLBACK INTEGRITY (gpt-5.5 k=3 hobby-only @ the NEW Tier-B prompt, RUN 20260824-163444):
  **3/3 PASS** — gpt-5.5 still emits set_points@q2.ב=29. The documented rollback target is
  re-verified ON THE SHIPPED TREE, not inherited from a stale measurement. (Its gate line reads
  0/3 as always: hobby fails the GT convention for every model. The V4 criterion was the fix step,
  never the gate — stated that way when it was pre-registered, not after seeing the number.)
VERDICT — the regression is GONE and the fix is clean:
  V1 3/3 · V2 3/3 · V3 12/15 with zero new failure classes · V4 3/3.  Before/after on the
  identical config+fixture: set_points@q2.ב present 0/7 -> 3/3; after-accept sums 76-vs-60 -> 60=60.
HONEST RESIDUAL RISK (what these four runs do NOT establish):
  - hobby_tvshow is the ONLY fixture in the suite that triggers a structural_mislabel with a
    move+repoint fix, so V1/V2 are single-fixture evidence for the repaired behaviour. The suite
    cannot tell me whether terra now handles a DIFFERENT mislabel shape (two criteria moving, a
    move that empties a scope, a mislabel across questions). That is a fixture-coverage gap, not
    something more k buys.
  - the eval gate STILL does not score suggested_fix (the blind spot that hid this for a whole
    sweep). These four criteria were checked by hand-written probes, so nothing in CI will catch
    the next regression of this class. Closing it means extending pedagogical_match to compare
    fix steps = a GATE change = STOP list = Noam's call. Recommended, and not taken here.
cost: V3 $1.217 + V4 $0.51

## DEPLOY 2026-08-24 (2nd) — Tier-B fix live: revision 00039-t8r, prompt 3.10.0-fixsource
command: gcloud run deploy gradervision-backend --source backend --project gen-lang-client-0438328890
  --region europe-west1   (no --update-env-vars needed: the pin was already flipped on 00038-tq7
  and --source only rebuilds the image)
delta shipped vs 00038-tq7: EXACTLY two files, verified by mtime before deploying —
  app/services/docx_v3/pedagogical_mistakes.py (the Tier-B source-side rule) and
  app/services/docx_v3/pipeline.py (the version bump). No new secret-shaped files since the last
  deploy; .gcloudignore in place (1564 bytes) and doing its job.
result: **gradervision-backend-00039-t8r**, 100% of traffic.
verified post-deploy: pin intact (openai / gpt-5.6-terra / high / 32000) · GET /health 200 in
  0.37s · ZERO warnings or errors on the revision · boot clean ("SCHEMA OK: migration head 017",
  "create_all SKIPPED (APP_ENV=production)", "Application startup complete").
production state now: terra-high + prompt 3.10.0-fixsource — i.e. the configuration that passed
  V1-V4, not the one that carried the regression. The owner-reported defect (accepting the hobby
  fix left ב at 45 and q2 at 76) is fixed in the code that is now serving.
STILL NOT PROVEN IN PROD: no rubric has been extracted through the live service on this pin — the
  same caveat as the first deploy. The owner's own live upload is what found the last defect;
  a live re-run of hobby_tvshow against 00039-t8r is the natural confirmation and is HIS to run
  (or mine on request). The eval evidence is k=3 x 5 fixtures plus the four V-criteria.
open items carried forward (none blocking, all owner-territory):
  1. hobby GT/convention proposal — PROPOSED 2026-08-24, still awaiting the owner's reasoning.
     UNCHANGED by any of today's work; nothing in benchmarks/ has been edited.
  2. pedagogical_match does not score suggested_fix — the blind spot that let this regression
     through a full 9-cell sweep. Extending it is a GATE change (STOP list). RECOMMENDED.
  3. _TIER_B_SYSTEM has no version constant; today's change borrowed EXTRACTION_PROMPT_VERSION
     to avoid being silent. Giving it its own stamp is a small, high-value follow-up.
  4. fixture coverage: hobby is the ONLY fixture exercising a move+repoint structural fix, so the
     repaired behaviour has single-fixture evidence. A second mislabel-shaped fixture would be
     worth more here than more repeats.

## CHANGE 2026-08-24 — RULING (owner): hobby_tvshow GT/convention stays AS IS. No file changed.
ruling: Noam, 2026-08-24, on the four-part proposal of the same date — "leave as is".
  benchmarks/hobby_tvshow.json keeps q2.ב = 29 (the teacher's literal), both Tier-A
  point_sum_mismatch shadows and both rubric_mismatch annotations. Edits 1-4 of that proposal
  are WITHDRAWN, unapplied. RUBRIC_EVAL_PLAYBOOK §4's worked example and CLAUDE.md §2's corollary
  therefore also stand unchanged — no doc rewrite is owed.
logged because a convention ruling is a variable-change entry EVEN WHEN NO FILE MOVES (§11 rule 3;
  the named cost of skipping this was the 2026-07-11 reconciliation forensics).
STANDING CONSEQUENCE — read this before diagnosing hobby again: hobby_tvshow will FAIL the gate
  for EVERY model, permanently, on exactly three metrics (annotation_mismatch,
  pedagogical_mismatch, point_exactness=0.9792). The suite's maximum achievable score is therefore
  **12/15 at k=3**, and 12/15 IS a full pass. hobby is a CONSTANT, not a discriminator: it cancels
  in every model-vs-model comparison in this ledger. Do not read it as a model defect, do not
  "fix" it by editing GT, and do not chase it. The extractor's behaviour there (declaring ב=45,
  the sum of what it placed under ב, and surfacing the teacher's error through
  structural_mislabel with an executable fix that restores 29) is OWNER-RATIFIED CORRECT —
  see CORRECTION 2026-08-24.

## CHANGE 2026-08-24 — TIER_B_PROMPT_VERSION added + stamped into provenance (owner-approved item 3)
what: (1) NEW constant `TIER_B_PROMPT_VERSION = "1.1.0-fixsource"` in pedagogical_mistakes.py,
  placed next to _TIER_B_SYSTEM (the EXTRACTION_PROMPT_VERSION convention: the version lives
  beside the text it versions, so a rollback of the text restores the stamp with it). Retroactive
  label 1.0.0-baseline names everything before today; it was never stamped and never will be.
  (2) pipeline.py stamps it into `extraction_metadata` via a lazy, exception-swallowing accessor
  `_tier_b_prompt_version()` — provenance must never be able to break an extraction.
  (3) runner.py carries it from result.metadata into results.json provenance, beside
  prompt_version and pipeline_version.
why: the suite now tracks THREE independent prompt/code surfaces (extraction prompt, Tier-B
  adjudication prompt, pipeline code) and only two were stamped. The Tier-B regression fixed
  earlier today shipped and was diagnosed with NOTHING in results.json able to say which Tier-B
  text produced a given run — the gap was found by reading source, not the record.
affects: **suite_hash 19607f69e6bc3432 -> 79e28de864cab534** (runner.py is hashed). Announced, not
  drift. Every run before this entry is on the old hash; the two are comparable on ACCURACY
  (scorer, gates and benchmarks are byte-identical — this change is provenance-only and adds no
  scored field), and the next run will be the first to carry a tier_b_prompt_version stamp.
  46/46 guards green; app.main imports.
by: Noam approved item 3 of the 2026-08-24 follow-up list; agent implemented.

## CHANGE 2026-08-24 — FIX-EFFECT CHECK implemented (P0+P1 done, gate NOT armed — one ruling owed)
approved: Noam ruled D1 (sibling metric, not folded into pedagogical_match), D2(b) (cross-pinned
  vectors), D3 (vacuous => skip) on the plan of the same date.
what shipped (all green):
  - scoring.py `fix_effect_check(predicted)` — simulates each suggested_fix's POINTS effect and
    requires every touched scope AND its ancestors to add up. Mirrors the ONLY real applier,
    frontend/src/utils/edit-steps.ts, rule for rule (R1 criterion-set cascades living sums;
    R2 scope-set does not; R3 moves adjust NEITHER side; R4 vivified targets get Sigma-of-arrivals;
    R5 rubric-scope is single-step).
  - schemas.py `fix_effect_consistent: Optional[bool]` + `fix_effect_violations: List[str]`.
  - NEW tests/fixtures/edit_step_points_cases.json — 4 vectors, read IN PLACE by BOTH
    tests/rubric_eval_suite/test_fix_effect.py and frontend/src/utils/edit-steps.test.ts
    (the selection_expectation_cases.json precedent). The TS side runs the REAL applier; if the
    two ever disagree the vectors fail loudly instead of the gate silently lying.
  - NEW test_fix_effect.py — vectors + vacuity + a KNOWN-ANSWER pair on a REAL prediction: the
    as-emitted gpt-5.5 fix passes, and deleting its source-side set_points (the exact omission
    terra made 0/7 times) must flip it. 6 tests. Frontend: 18 tests green.
P1 MEASUREMENT (offline, $0, 301 cached predictions — arming without this is guessing):
  229 vacuous (76%) / 51 reconcile / 21 broken. Per fixture: csharp 0 broken, foundations 0,
  employee 1, bagrut 7, hobby 13. **The SHIPPED configuration (terra-high @ 3.10.0) scores ZERO
  broken across 5 fixtures x 3 draws**, while the SAME config+fixture BEFORE the Tier-B fix is
  3/3 BROKEN. The criterion fires exactly on the defect and nowhere on good output.
SELF-INFLICTED BUG, CAUGHT BY THE SUITE'S OWN GUARDS (worth recording): my first patch inserted the
  wire line using `rindex("    return rs\n")`, which matched INSIDE the 8-space `return rs` of the
  truncation branch and split it — de-indenting that return to function level, so score_rubric
  returned early for EVERY record and all real scoring became dead code. 9 guards went red
  immediately. Repaired by line index; 52 pass. This is what "run test_scoring.py after ANY scorer
  edit" is for, and it is the second time today a guard earned its keep.
THE RULING OWED — why the gate is implemented but NOT armed: arming it as written reds
  test_fp123's round-trip on **bagrut's own GT**, and the cause is NOT the instrument. Tier A's
  `_adjust_points_fix` on the flagship teacher error (q1.א.2 declared 3, children 2) proposes
  set_points@q1.א.2=2, which necessarily leaves the PARENT q1.א declaring 15 against 14 of
  children — because that 15 was consistent with the child's ERRONEOUS 3. Cascading to 14 would
  invent a number the teacher never wrote, which is exactly what that function's docstring says
  Tier A may never do ("It INVENTS NOTHING ... the only fix Tier A may emit on its own"), leaving
  the root-cause fix to Tier B.
  So there are two DIFFERENT kinds of fix and the criterion should probably know it:
    - operation="adjust_points" (Tier A, deterministic, minimal): claims only to correct the node
      it targets. Checking its ancestors punishes it for a promise it never made.
    - operation="reassign_subquestion" / any multi-step structural fix (Tier B): claims ROOT-CAUSE
      resolution ("one fix settles all shadows", Tier-B prompt principle 3) — ancestors ARE its
      promise, and this is the class the owner's live defect belonged to.
  OPTION A (recommended): scope the criterion by the fix's own claim — ancestors checked for
    root-cause fixes, only the targeted node for adjust_points. Principled, derived from the
    code's stated contract, still catches the regression that motivated the work.
  OPTION B: arm as-is and treat Tier A's chain-of-proposals as a defect to fix in product code
    (a real question: each accepted local fix can spawn the next finding one level up).
  OPTION C: arm as-is and quarantine the round-trip assertion — REJECTED as hiding evidence.
  Gate left DISARMED with a commented block naming the ruling, so nothing is half-applied and the
  tree is green (52 backend + 18 frontend).
affects: suite_hash -> f8b56e4ac0d7822a (scoring/schemas/gates/new test). Accuracy-comparable to
  earlier runs: no scored field changed and the new criterion does not gate.

## CHANGE 2026-08-24 — FIX-EFFECT gate ARMED under owner ruling "Option A"
ruling: Noam, 2026-08-24 — judge a fix BY WHAT IT CLAIMS.
  - a MOVE-BEARING plan claims root-cause resolution (Tier-B principle 3, "one fix settles all
    shadows") => its promise includes the ANCESTORS, and they are checked.
  - a PURE set_points plan is a MINIMAL LOCAL correction (Tier A's `_adjust_points_fix`, whose
    contract is that it "INVENTS NOTHING") => held ONLY to the node it targets. Holding it to
    ancestors would demand it write a number the teacher never wrote — the one thing FC forbids.
  Discriminated on the STEPS, not on `suggested_fix.operation`: that label is derived from exactly
  this predicate upstream and is documented as analytics metadata the client never dispatches on.
  The steps are what get applied, so the steps are what get judged.
WHY THIS WAS THE RIGHT CUT (the evidence that produced the ruling): the strict version red-flagged
  bagrut's round-trip, and investigation showed the failing proposal was NOT from a live model —
  test_fp123 runs `detect_pedagogical_mistakes(..., llm=None)`, Tier B DISABLED, zero API calls.
  It was Tier A's deterministic fallback setting q1.א.2 from 3 to 2, which necessarily leaves the
  parent q1.א at 15 against 14 because that 15 was consistent with the child's ERRONEOUS 3.
  In LIVE runs Tier B REPLACES that fix with the correct one, exactly as its docstring promises —
  verified in the artifacts: terra-high proposes q1.א.2 criterion[0] 1.5 -> 2.5, gpt-5.5 proposes
  criterion[1] 0.5 -> 1.5. BOTH raise ONE criterion by 1 so the criteria reach the teacher's
  declared 3, the parent stays 15 and nothing ripples — the "declared is the authority" rule from
  the Tier-B ladder. The crude fix only ever appears on the LLM-less degrade path.
measured before arming (301 cached predictions, offline, $0): 229 vacuous / 55 reconcile /
  17 broken (strict version was 21; bagrut 7 -> 3, and the 3 survivors are grok fixes that fail to
  reconcile even the node they TARGET, which is a local failure and correctly caught).
  SHIPPED config: ZERO broken. Same config before the Tier-B fix: 3/3 broken — re-scored through
  the ARMED gate, the three pre-fix draws now fail with `fix_effect_inconsistent` and the three
  post-fix draws pass. The gate would have caught the owner's defect.
also updated (doc-truth, the gate list lives in two places): RUBRIC_EVAL_PLAYBOOK §5 and
  ONBOARDING §5 now list the criterion and explain the claim-scoping.
state: backend 54 passed + 1 xfailed; frontend 18 passed; app.main imports.
  suite_hash -> 604e9453d7225d59. Runs before this entry are accuracy-comparable (no scored field
  changed for them; the new criterion is vacuous wherever no fix is proposed), but any run from
  here carries a gate criterion they did not.

## CHANGE 2026-08-24 — FRONTEND SOURCE AUTO-REPAIR + ID RE-DERIVATION (owner-ruled; one PR, two commits)
rulings taken: (1) ids reflect current location = "B"; (2) add the ungated fix_plan_complete
  diagnostic; (3) a source emptied by a move is LEFT ALONE; (4) one PR, two commits.

COMMIT 1 — the applier repairs a move SOURCE (frontend/src/utils/edit-steps.ts).
  The symmetric half of the rule that has always repaired a vivified TARGET. Two guards, and
  they are the design, not caveats:
    guard 1 — ONLY IF THE SOURCE WAS CONSISTENT BEFORE THE MOVE. If it already declared a number
      that disagreed with its criteria, that number is the TEACHER'S FINDING; rewriting it would
      be the silent repair the product forbids. (Costs nothing on the canonical case: the faithful
      hobby draft declares 29 and lands on 29 either way.)
    guard 2 — NEVER WHEN THE MOVE EMPTIES THE SCOPE. Sigma of nothing is 0 and 0 is a number she
      never wrote; an empty husk she must resolve is honest, a fabricated zero is not.
  Precedence unchanged: an explicit set_points on that scope wins. Question totals never auto-touched.
  MIRRORED IN THE SCORER in the same commit (R6 in scoring.py) — the cross-pinned vectors demanded
  it by construction, which is the cross-pin doing its job on its first real test. The simulation
  was refactored into ONE function `fx_simulate` that the check AND its tests now observe; the
  test previously re-implemented the replay, which was itself a drift risk.
  VECTORS: 4 -> 6 cases. Cases 1 and 3 CHANGED VERDICT (the source is now repaired) and two new
  cases pin the guards. The real applier passes all six.
  NEW UNGATED DIAGNOSTIC `fix_plan_complete` = the same check with the source repair DISABLED,
  i.e. "would this plan have reconciled WITHOUT the app compensating?". Rationale, and this was
  the non-obvious part of the plan: making the bug harmless would otherwise make it INVISIBLE —
  the gate mirrors the applier, so a model that forgets the step would silently stop failing.
  Measured on cached hobby draws AFTER the change:
      teacher-visible broken : 0/3 0/6 0/6 0/12   (the app protects her everywhere)
      plan INCOMPLETE        : 0/3 0/6 0/6 10/12  (pre-fix terra still exposed)
  The known-answer test now asserts BOTH verdicts on the same injected omission: harmless to the
  teacher (True), still incomplete as a plan (False).

COMMIT 2 — a moved criterion is renamed to its new home.
  `reidCriterion` derives `{to_scope}.c{index}` for the moved criterion and `{newCid}.sc{i}` for
  its sub-criteria, with a uniqueness check falling back to the editor's own opaque `c_<uid>`
  (an opaque id claims nothing, so it cannot lie either). `uid` is now EXPORTED from
  rubric-editor-ops — one id minter, so a fallback can never take a different shape from the ids
  the editor mints.
  SCOPED TO THE MOVED CRITERION ONLY. Siblings keep their ids even though their numeric suffix is
  now off by one, because those ids key grading terminals, teacher overrides (CW-3) and
  data-scope-id anchors. The rule is therefore stated explicitly in the code: **an id's digits
  record BIRTH ORDER, not current position; its SCOPE is kept true.**
  4 new TS tests: destination-derived id, sub-criteria following the parent, siblings deliberately
  untouched, and the collision fallback (the squatter test had to be corrected — it originally
  seeded the wrong id and so never exercised the fallback at all).

honest scope note recorded during research, so nobody re-derives it later: the id drift was NOT a
  grading-correctness bug. Ids are OPAQUE keys everywhere that consumes them (nothing parses a
  criterion_id; the only .split(".") is on a target_id), the compiler passes them through, and a
  move preserves uniqueness. It was a data-integrity and legibility defect — an id asserting a
  location that is false — plus a latent collision risk if anyone ever added path-derived
  regeneration. Worth fixing, not worth alarm.
state: frontend 50 files / all green + `npx tsc --noEmit` clean; backend 56 passed + 1 xfailed;
  app.main imports. suite_hash -> e3ed1086c4c3dff2.
NOT DEPLOYED: this is frontend + eval-scorer only. The frontend deploys by the §12.5 mirror +
  subtree flow and is the owner's call; nothing here changes the backend image now serving.
