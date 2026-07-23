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
