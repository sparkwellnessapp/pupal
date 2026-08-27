# RUNLOG — grading eval suite (append-only hard memory)

Every run and every variable change gets an entry (hypothesis, variable,
pre/post, attribution, decision, cost). An analysis is not done until its
entry exists. Read this file at the start of every iteration.

## CHANGE 2026-08-24 — Phase A: the instrument exists (zero spend)

what: suite skeleton per MISSION v0 — schemas (FixtureGT/TrialScore), fixtures
  (manifest pairing [F3], hash pins [D5], GT guards [SS5], R1 blind sequencing),
  scoring (Tier-0..3 per SS6/SS7; [T1-*] tripwires; [DL-1/2/3] operational
  definitions), reporting (worst-test-first, PROVISIONAL stamps, ECE n-flagged),
  runner (grade | score_only | --scopes; 300s wall + exactly one transport
  re-run [D7]; DL-4 model-pin refusal; provenance incl. suite_hash covering
  snapshots + shared registry [D3]), configs/gpt-4o.json (deployed pin, $0.10
  ceiling), eval_common dry-resolve extension, fixture tools (F0 staged
  proposal, F1 converter with 5/5 parity, F2 rebuild, F4 skeleton), docs
  (ONBOARDING, PLAYBOOK with STOP list, GT_CONVENTIONS skeleton with C-1..C-5).
why: MISSION SS11 Phase A. Failing-test-first: red captured with the
  implementation absent (ModuleNotFoundError x3 collection errors), then
  44 passed / 1 xfailed (the eval_common D5 sentinel).
evidence: PHASE_A_REPORT.md (proofs per item). Guards include the known-answer
  self-pass and one injected-error test per metric [SS10]. Zero API calls in
  pytest -q (verified: no OPENAI key needed for the battery).
affects: suite_hash exists from this commit; F0 correction proposal STAGED in
  H1_CORRECTION_PROPOSAL.md — [STOP] awaiting owner ratification [R5/H1].
  Phase B blocked on H1 + C-1..C-5 rulings + owner blind grading [F5/R1].
corrections: none

## CHANGE 2026-08-24 — Phase B: C-2 Tier-2 exclusion + item-6 reporting (INSTRUMENT change, owner-ruled)

what: (1) scoring [C-2, ratified]: ungradable-scope terminals now EXCLUDED from
  all Tier-2 agreement metrics (MAE / within-precision / exact / edit_burden /
  compensating-error input) and from the calibration input; best-guess awards
  participate in TOTALS only (score_with_selection). TerminalScore gains
  ungradable_scope + gt_note. Tier-1 ungradable-guess tripwire UNCHANGED.
  (2) reporting [item 6]: fixture report displays the GT note column
  ([C1-TABLE] terminals visible to the read-by-hand ritual) + the
  "total includes N ungradable-scope terminals" mark; per-fixture Tier-3
  counts c1_table_terminals + ungradable_terminals.
why: Phase-B ruling items 4 + 6 (verbatim text in GRADING_GT_CONVENTIONS.md).
protocol: failing tests FIRST (4 red: 2 scoring + 2 reporting), then
  implementation, then 48 passed / 1 xfailed. Calibration exclusion is an
  agent judgment EXTENDING the ruling's logic (best-guess correctness is
  noise) — documented in PLAYBOOK SS4, flagged for reviewer.
affects: suite_hash SHIFTS (scoring/reporting/schemas + new snapshots) —
  harmless pre-baseline (no baseline exists). No sibling files touched.
corrections: none

## CHANGE 2026-08-24 — Phase B: fixtures land (F0 ratified -> F2/B3 -> B4)

what: sibling GT edits committed FIRST (6337fbc, owner-attributed:
  din_ezra.md + yonatan_basiuk.md — snapshots point at committed state);
  F1 parity re-run POST-commit: 5/5 byte-identical (evidence hygiene);
  H1 RATIFIED -> benchmarks/contracts/hobby_tvshow_corrected.contract.json
  + .provenance.json (ratified_by Noam, 2026-08-24, DL-5 + DL-6 accepted);
  F2: 5 transcription contracts snapshotted (6 answers each) + B3: 5
  per-fixture manifests with sha256 pins; B4: 5 GT skeletons emitted for
  the owner's blind grading.
why: Phase-B ruling items 1/2/7, executed in the ruled order.
affects: [STOP] F5 — owner blind-grades from the skeletons [R1]. No
  grade-mode run exists or may exist before GT lands. Phase C gated on P2.
corrections: none

## CHANGE 2026-08-24 — H1-A1 supersede (DL-7 ruled: children rename with their parent) + D2/D3 ratifications

what: [D1/H1-A1] the moved criterion's sub-criteria now rename with it —
  q2.ב.c6.s0..s3 -> q2.ג.c0.s0..s3 (DL-5's own principle at the terminal
  level). RED-FIRST x2: (a) F0 pin test extended to assert the new sub-ids —
  red vs the current tool (['q2.ב.c6.s0'...] != ['q2.ג.c0.s0'...]);
  (b) NEW class-closing path-honesty structural guard
  (test_terminal_ids_are_path_honest_in_all_bundles: every terminal id
  prefixed by its full ancestor chain, across all five bundles) — red vs the
  first ratified snapshot with exactly the 4x5 DL-7 offenders. Tool extended
  (prefix-swap preserves suffixes); SUPERSEDE per the ruled mechanics: prior
  snapshot + provenance DELETED in the supersede commit (git history is the
  archive), --ratify re-run (its exists-refusal untouched — deletion IS the
  supersede path); new provenance records DL-5 + DL-6 + DL-7 + the H1-A1
  amendment block; Amendment section APPENDED to H1_CORRECTION_PROPOSAL.md
  (original text restored from HEAD after the tool's template regeneration,
  then appended — never rewritten). Downstream regenerated: manifests x5
  (new rubric sha256 c988eb7d1856f041; transcription snapshots byte-identical
  5/5) + skeletons x5. Terminal universe UNCHANGED: 38/fixture, 190 total,
  ids-only delta (-4 ב-prefixed / +4 ג-prefixed per fixture), judgments null.
why: Phase-B follow-up ruling D1 (verbatim in the owner message; recorded as
  H1-A1, ratified_by Noam, 2026-08-24).
also: [D2] DL-8 two-file deviation RATIFIED (norm restated: surface-before-
  execute default; executed-then-disclosed passes only when the alternative is
  a silently-false ruling). [D3] the calibration exclusion of ungradable-scope
  terminals RATIFIED (reviewer verdict + owner approval) — PLAYBOOK SS4
  stamped; the 2026-08-24 C-2 CHANGE entry's flagged judgment is hereby
  marked RATIFIED (append-only discipline: marked here, prior entry untouched).
affects: suite_hash SHIFTS (tool + tests + snapshot + manifests + skeletons) —
  harmless, no baseline exists. Batteries: suite 49 passed / 1 xfailed;
  transcription 134/1 baseline-identical; rubric 17 failed = 8 known Family-D
  + 9 in files a CONCURRENT session has mid-edit (fix-effect work in
  scoring/schemas/runner — none of this suite's diff touches rubric files).
  [STOP] F5 — owner blind-grades from the REGENERATED skeletons only.
corrections: none

## CHANGE 2026-08-25 — SUT change (owner lever): grader-v2-evidence-first decode order

what: the OWNER reordered TerminalGrade's fields (app/agents/grader/schemas.py)
  to quote_text -> reasoning -> points_awarded -> confidence. Field order flows
  into the structured-output JSON schema and therefore into DECODE order: the
  award is generated conditioned on the evidence just located and the reasoning
  just written — evidence-before-verdict, mechanically enforced. Blast-radius
  sweep (agent-executed on owner instruction): SYSTEM_PROMPT rules + OUTPUT
  FORMAT resequenced to match (sentences byte-identical to grader-v1; only
  order/numbering moved); GRADING_PROMPT_VERSION grader-v1 ->
  grader-v2-evidence-first (the constant's own bump contract: a change that can
  affect grades); decode-order PIN added
  (tests/agents/test_grader_agent.py::test_terminal_grade_decode_order_is_evidence_first
  — field order + json-schema property order + OUTPUT-FORMAT coaching order);
  synth.py now stamps drafts with the live constant; config notes +
  PREDICTIONS P2 updated. Order-safe by construction everywhere else
  (pydantic forbids positional init; validator/grader/tests access by name;
  TerminalGrade never persists). Inert literals in test_graded_test_approval /
  test_revision_flows / test_grading_runner left as fixture data.
why: owner ruling 2026-08-25 — "the single most promising cheap accuracy lever
  in grader-v1"; applied PRE-BASELINE, the zero-cost moment (no baseline
  exists, nothing re-run). R7's "gpt-4o + grader-v1" is hereby AMENDED to
  gpt-4o + grader-v2-evidence-first; the Phase-C baseline measures the new pin.
  NOTE (recorded, no action): this is an app/ change executed on explicit owner
  instruction — the mission's no-production-changes fence is owner-amended for
  exactly this diff; step-3 items (D6 seam, GRADER_VERSION, _compute_cost)
  remain fenced.
affects: Phase-C provenance will stamp prompt_version=grader-v2-evidence-first
  automatically (runner imports the constant). Suite battery + agent battery
  green. Blindness untouched: no grade-mode run has ever executed.
corrections: none

## CHANGE 2026-08-25 — PR-G1 v2: prefix-context seam (RATIFIED) + round-0 carryover

carryover (M1 + version + dispositions): FixtureGT gains the M1 provenance
  classes — gt_source now {teacher_manual, teacher_validated,
  production_approval}; teacher_validated requires blind:false + proposed_by +
  validated_by (loader refuses blind:true on it; refuses missing attribution);
  v0 GATES on the teacher_validated class per owner ruling; production_approval
  stays non-gating; gt_source surfaced in results.json provenance + summary.md.
  Landed BEFORE any GT file is committed (benchmarks/gt/ holds skeletons only —
  verified). GRADING_PROMPT_VERSION canonicalized "grader-v2-evidence-first" ->
  "grader-v2" (decode-order lever unchanged; pin test green). PREDICTIONS
  dispositions appended: P4 WITHDRAWN-UNMEASURABLE, E1 OVERTAKEN-BY-OWNER-
  ACTION, E3 RESOLVED-BY-ARGUMENT. Skeleton-header regen to M1 form: SKIPPED
  (optional per ruling — owner grading now; M1 fields default null).
what (the seam): PriorPartContext {sub_question_id, sub_question_text,
  example_solution, student_answer_text, answer_missing} — owner-ratified
  shape, prior criteria + prior awarded points DELIBERATELY EXCLUDED;
  GradableScope.prior_parts (additive, default []). Compiler populates
  prefix-only, document order, per question (leaf-level accumulation: equals
  "all preceding sub-questions" at depth-1; preceding LEAVES in reading order
  when nested; parent splitters contribute nothing); direct-criteria + first
  parts get []. Prompt: flag GRADER_PRIOR_CONTEXT_ENABLED (default OFF) —
  ON renders parent QUESTION -> prior parts (text -> example solution ->
  answer, «לא נענה» when missing) under the ruled Hebrew header -> current
  material exactly as today; OFF is BYTE-IDENTICAL to the pre-change renderer
  (sha256 pin c575112f6d85237e..., captured pre-change, green post-change).
  Version integrity: stamped prompt_version = pure function of code + flag
  (grader-v2 / grader-v2+priorctx) — grader.py's two stamp sites now call
  effective_prompt_version() (MINIMAL enabling touch outside the named files;
  item 4 is unsatisfiable without it — disclosed). Eval runner: config key
  prior_context (default false) -> env flag set explicitly both ways ->
  stamped in provenance; baseline runs OFF; the E4 run's single variable is
  the flag flip.
red-first: 6 reds captured pre-implementation (compiler prefix, on-path
  render, version mapping, 3x M1 loader); off-path byte-pin + OV-1 overlap
  pin green pre AND post (affirmation pins). OV-1 ruling recorded in the pin:
  quote validation is an existence check, never exclusivity; within-scope
  overlap legal for v0; any future constraint = owner ruling + Tier-3 counter
  first, never a validity gate.
affects: terminal universe UNCHANGED (all five bundles, 38/fixture, 190 total
  — pinned by test_terminal_universe_unchanged_after_prior_context_seam);
  nothing the suite hashes moved (prior_parts is compiler output). suite_hash
  shifts (instrument files). E4 registered verbatim in PREDICTIONS.
corrections: none

## CHANGE 2026-08-25 — H1-A2: ratified model solutions embedded (supersede #2) + dan_basiuk GT landed

prereq: M1 loader change confirmed ALREADY LANDED (PR-G1 v2, commit 71305dc) —
  dan's teacher_validated GT loads under it.
what: (1) source artifact committed: benchmarks/contracts/_sources/
  model_solutions_transcription.md (owner screenshots, transcribed by
  claude-fable-5, T-1/T-2/T-3 conventions ratified, one in-review correction —
  minChannel comment; RATIFIED Noam 2026-08-25). (2) RED-FIRST: two new pins
  (six example_solution fields byte-equal to the ratified blocks incl. the
  stray '//', the multiline 'if (' formatting, 'internal class', Hebrew
  comments verbatim; q2.א = constructor+UpdateRate concatenated in order) —
  red = ImportError + all-six-NONE; plus the D5 hash guard already refusing
  dan's placeholder-hashed GT mid-supersede (the guard working as designed).
  (3) tool embeds the six blocks (fences stripped, zero normalization) into
  draft + compiled contract; SUPERSEDE #2 per H1-A1 mechanics (prior snapshot
  + provenance deleted in the supersede commit; --ratify re-run; provenance
  chain H1+A1+A2; H1 doc restored-from-HEAD after the tool's template regen —
  it DID recur as the ruling predicted — then the A2 Amendment appended;
  original + A1 text byte-untouched). (4) downstream: 5 manifests re-pinned
  to rubric sha256 480c15cff2face1e...; transcription snapshots asserted
  byte-unchanged 5/5; 4 remaining skeletons regenerated with M1 headers
  (teacher_validated / blind:false / proposed_by / validated_by); dan's
  obsolete skeleton retired (superseded by the real GT — judgment call,
  disclosed). (5) dan_basiuk.gt.json landed: sha256 stamped mechanically;
  authored_at left for the OWNER's commit; full loader guard suite GREEN
  (totality 38/38, bounds, 0.25 grid, hash pin, M1 provenance); zero judgment
  fields altered; gt_total via real selection_scoring = 83.5/100. NOTE: grade
  mode stays refused for dan until authored_at is stamped (fromisoformat on
  the placeholder raises in the R1 sequencing check — correct, not a bug).
  (6) delta proof old->new contract: exactly 6 example_solution fields +
  contract_version — nothing else; universe ids UNCHANGED (38/fixture).
  (7) byte-identity pin re-anchored DELIBERATELY: split into RENDERER pin
  (solution-stripped scope reproduces the pre-seam hash c575112f... exactly —
  renderer never drifted) + renderer+content pin (A2 anchor 5b5d72a2...);
  skeleton pin updated to the M1 header form. Both are ruled-change pin
  updates, not instrument weakening.
provenance note: from H1-A2 onward compiled scopes carry model solutions —
  the baseline measures the grader WITH the EXAMPLE SOLUTION section rendered
  (production-realistic; referent and SUT symmetric). E4/prior_parts
  unaffected — flag off for baseline.
affects: suite_hash shifts (snapshot + manifests + skeletons + tools + tests
  + the source artifact) — harmless, pre-baseline, no drafts exist. Batteries
  83 passed / 1 xfailed; import + collect green. Zero app/ changes; zero spend.
corrections: none

## CHANGE 2026-08-26 — Phase B closeout: five GTs verified; HOLD at P2

what: (1) dan version check GREEN — q2.ב.c3.s2 == "2" (AUDIT-2 correction
  present, revised PL-10) and real selection_scoring returns 84.0, not the
  pre-audit 83.5. The stale file is NOT in place. (2) MECHANICAL FIX, precedented
  by the H1-A2 ruling ("stamp the sha256 ... (mechanical); leave authored_at for
  the owner"): dan + din_ezra still carried the FILL_AT_COMMIT_H1A2_SHA256
  placeholder (dan's stamped value was replaced when the owner placed the
  AUDIT-2 correction), so the D5 hash guard was REFUSING both. Stamped the live
  ratified hash 480c15cff2face1e... into those two ONLY after positive evidence
  each was authored against the A2 contract (both carry H1-A1 path-honest
  q2.ג.c0.s* ids; din's notes cite the model solutions via R-β/PL-*). moran /
  omer / yonatan already carried the correct hash. NO judgment field touched in
  any file. (3) all five verified through the FULL loader guard suite:
  totality 38/38, bounds, 0.25 grid, D5 hash pin, M1 provenance
  (teacher_validated / blind:false / proposed_by / validated_by),
  _instructions removed; terminal-id universes IDENTICAL across all five
  (single 38-id universe). (4) corpus totals via REAL selection_scoring —
  din 55.5 · dan 84.0 · omer 89.0 · moran 92 · yonatan 92.5, all matching the
  owner's expected values under Decimal equality (omer/moran differ only in
  Decimal string form, 89.0 vs 89 — numerically equal, not a mismatch).
  evidence_exists=false counts: din 8 · dan 3 · omer 2 · moran 1 · yonatan 1.
  ungradable_scopes EMPTY in all five. (5) NEW corpus pin
  (test_corpus_totals_via_real_selection_scoring) makes this verification
  permanent: any silent GT edit moves a total and reds. Re-anchor only on an
  owner-ratified GT amendment, RUNLOG-entried — never to make a number pass.
  (6) two corpus gaps registered in ONBOARDING's seed-gap register (findings,
  no action): C-1's table-interpretation clause and C-2's ungradable path both
  ship UNTESTED — this exam has no tabular answers and no illegible scopes;
  fixture expansion (n>=10, >=2 exams) must deliberately include a trace-table
  answer and one genuinely illegible scope.
STOP surfaced (Phase-B exit condition NOT met): authored_at is
  'FILL_AT_COMMIT_ISO8601' in ALL FIVE GT files, so assert_blind_sequencing
  REFUSES grade mode for every fixture. This is NOT a blindness violation —
  results/ does not exist, zero cached drafts, so the moment the owner stamps
  authored_at all five permit. The stamp is the OWNER's act by ruling
  (authored_at is the R1 provenance anchor; an agent-invented timestamp would
  fabricate provenance) — not stamped here, deliberately.
also: §13 (grading constitution) read as CONTEXT ONLY — nothing built. E5
  deferred per ruling: computable post-hoc from results.json, does not gate or
  delay the baseline; NOT implemented.
affects: suite_hash shifts (two GT files + ONBOARDING + the corpus pin).
  Batteries 84 passed / 1 xfailed; transcription 134/1 baseline-identical;
  import + collect green. Zero spend, zero app/ changes.
next: [STOP] P2 — the pre-baseline prediction (owner + reviewer) must land in
  PREDICTIONS.md before any spend. Then C2 unchanged: k=5 x 5, deployed pin,
  prior_context OFF, ~$1, doubling as the U2/G-21 multi-scope smoke.
corrections: none

## RUN 20260826-172246_gpt-4o — C2 BASELINE ATTEMPT: ABORTED BY BILLING (0/25 valid, $0 spent)

ref: P2 (registered 2026-08-26, pre-run) · config gpt-4o · k=5 x 5 fixtures
purpose: the Phase-C baseline of the deployed pin; doubles as the U2/G-21
  multi-scope smoke.
variable: none (baseline).
config: gpt-4o  k: 5  prior_context: False  prompt_version: grader-v2
  suite_hash: 8e66db31f1df7490  registry_as_of: 2026-08-15
  gt_sources: all five teacher_validated

VALIDITY (Tier 0) — THE RESULT: 0/25 valid, 25/25 INVALID.
  Every scope of every trial failed: 150/150 scope failures, all
  exception_class=RateLimitError, all carrying the SAME provider payload —
  "Error code: 429 ... 'You have no credits remaining. Add credits to continue
  using the API', type: insufficient_quota".
  Tokens consumed: 0 in / 0 out. ACTUAL SPEND: $0.00 — no call ever reached
  the model. The ~$1 baseline budget is UNSPENT and still available.
  D7's one-rerun fired on all 25 trials and correctly did not help (the
  condition is permanent, not transient). Zero wall-bound hits. Zero parse
  failures — R6 escalation NOT triggered. Median trial latency 11.8s (pure
  429-round-trip time).

NO BASELINE DATA EXISTS. Consequently:
  * P2 is UNSCORED — not confirmed, not falsified, not indeterminate. There is
    no measurement to score it against. It stands registered and untouched for
    the re-run.
  * No worst test, no terminal tables, no Tier-2 distributions, no calibration.
    Reporting any of these would be fabrication.
  * Tier-1 tripwires: vacuous (no graded terminal existed to trip them).

INSTRUMENT VERDICT — the harness behaved exactly as designed under total
  provider failure. It classified the failures as transport (not parse),
  invalidated every trial, COUNTED them, excluded them from aggregates, wrote
  full artifacts + drafts, and reported 0/0 rather than inventing numbers.
  Tier-0-validity-before-significance did its whole job on its first real
  contact with reality. Provenance stamped correctly throughout.

FIELD CONFIRMATION OF G-3 (recorded, NOT actioned — app/ is fenced, PR-7 owns
  it): this is the documented defect family observed live. `insufficient_quota`
  is a PERMANENT billing 429, but it arrives as openai.RateLimitError, which
  sits in GraderAgent.TRANSIENT_EXCEPTIONS — so the agent retried each scope
  once (GA-3) before failing. Cost of the mis-classification here: 25 wasted
  trial re-runs = 150 additional doomed calls, ~12s of latency per trial. Free
  in dollars only because the account was already at zero. CLAUDE.md predicted
  exactly this ("insufficient_quota — a permanent billing 429 — is retried as
  if transient"); the baseline attempt is its first empirical confirmation.

R1 INTACT: the failed run's drafts (20260826-172246) POSTDATE authored_at
  2026-08-26T00:00:00, so assert_blind_sequencing still PERMITS grade mode for
  all five — verified post-run. The local-midnight stamping choice is what
  preserved this; a same-day-afternoon anchor would have blocked the re-run.

decisions: STOP surfaced to the owner. The re-run is a billing action, not an
  engineering one: add OpenAI credits, then re-run the identical command. No
  code, config, GT, or prediction changes are needed or permitted for it —
  the re-run's single variable is "credits exist".
next: [STOP] owner adds credits -> re-run `python -m
  tests.grading_eval_suite.runner --config gpt-4o --mode grade -k 5` ->
  full PLAYBOOK analysis + P2 scoring on real data.
cost: $0.00  wall: ~5 min
corrections: none

## RUN 20260826-174645_gpt-4o — C2 BASELINE (k=5 x 5, deployed pin) — COMPLETE

ref: P2 (registered 2026-08-26 pre-run) · re-run of the billing-aborted attempt;
  SINGLE VARIABLE vs that attempt: credits exist. Zero code/config/GT/prediction
  changes.
config: gpt-4o  k: 5  prior_context: False  prompt_version: grader-v2
  suite_hash: 8e66db31f1df7490  registry_as_of: 2026-08-15
validity: 25/25 VALID, 0 invalid. D7 re-runs 0. Wall hits 0. Parse failures 0 ->
  R6 escalation NOT triggered. Cost mean $0.0698/test (max $0.0726) under the
  $0.10 ceiling. Latency median 12.3s. Total spend $1.7462.
MULTI-SCOPE SMOKE (U2/G-21) PASSED — first multi-scope evidence in the system's
  history (all 50 production drafts were single-scope): 150 scope-gradings,
  graded_by = 150 llm / 0 failed / 0 skipped; D3 totality held on all 25 trials;
  parent_answer_fallback never fired (correct, depth-1 rubric).
tier1: 24/25 pass. Taxonomy {T1-FABRICATED: 2}, BOTH in dan_basiuk r2
  (q1.ג.c1 GT1/AI1.00 not_found conf1.00; q1.ג.c7 GT0.5/AI1.00 not_found
  conf0.80). dan's other four trials clean => 1-in-25 stochastic, not
  systematic. Quote status 878 exact / 64 none / 6 fuzzy / 2 not_found.
worst test: din_ezra, median |dtot| 22.5 (GT 55.5 -> AI 33.0).
tier2 (PROVISIONAL, n=5 one exam): within_precision 0.6589 · exact 0.6084 ·
  MAE 0.34 · MEAN SIGNED DELTA -0.3089 · direction census over20/under352/
  exact578 · shippable 0/25 · pooled median |dtot| 10.00 · boundary_flip_rate
  0.80 · compensating_error 0 · exclusion_mismatch 0.
  EVERY fixture under-scored; not one over-scored.
  Harshness attribution by scope: q2.ב -129.75 · q2.א -58.5 · q2.ג -55 ·
  q1.ג -18.5 · q1.א -18.25 · q1.ב -13.5. Q2 = -243 of -264.
tier3: repeat instability 71/190 terminals (37.4%) non-zero spread across k=5;
  per-test total spread up to 6.75 (din). Calibration ECE 0.2438 over n=950,
  NON-MONOTONE (0.8-bin accuracy 0.387 < 0.7-bin 0.451); 465/950 terminals
  emitted at confidence exactly 1.00.
hand-read tables (2, per the read-two rule): (1) din q2.ב — the grader ZEROED
  the entire scope at confidence 1.00 (GT 9.5 -> AI 0). It registered that din
  solved a different problem, then refused all partial credit the teacher gave
  for the correct structural components (loop, min-search, return). The failure
  is confident all-or-nothing annihilation, NOT a missed wrong target.
  (2) omer q1.ב — 7/8 terminals exact and stable; the lone miss is P2's named
  q1.ב.c4 landing exactly (inverted !=null guard missed, 3.00 vs GT 1.5, 5/5).
P2 SCORED: CONFIRMED 1,2,3(pooled),4,6,10,12,14 · FALSIFIED 7,9,11,13,15,16 ·
  SPLIT 5 (under-ceiling confirmed; $0.03 estimate falsified at $0.0698) ·
  INDETERMINATE 8. P2's OWN FALSIFIER FIRED: "negative mean signed delta
  (systematic harshness rather than leniency)" — -0.3089. The leniency model is
  falsified in SIGN; absence-leniency is real (omer q1.ב.c4 exactly as named)
  but swamped ~17:1 by Q2-concentrated harshness.
decisions: NONE. No grader change proposed, no threshold set — both come after
  this report per the ruling. E5 (pairwise ordering agreement) remains deferred
  and is now computable post-hoc from this results.json.
next: owner review of C2_BASELINE_REPORT.md -> Tier-2 threshold candidates
  pre-registered from THIS distribution -> Phase D judge bootstrap.
cost: $1.7462  wall: ~9 min
corrections: none

## CHANGE 2026-08-27 — PLAYBOOK §R inserted (gating) + C2 addendum: mechanism CORRECTED

what: (1) PLAYBOOK gains §R "The qualitative read (MANDATORY, gating)", inserted
  verbatim per owner ruling (R.0 rationale · R.1 six mandatory reads R-1..R-6 +
  conditional triggers · R.2 seven-bucket taxonomy · R.3 the three distribution
  reads · R.4 report contract). §3's analysis contract gains: "...and §R is
  complete, with its bucket counts and R.3 tables in the report body."
  Docs-only; no code, no suite_hash concern.
  (2) C2_BASELINE_ADDENDUM.md — re-analysis of the SAME run (20260826-174645),
  zero spend, zero re-measurement.
CORRECTION 1 — MY REPORTED MECHANISM WAS WRONG. "Confident all-or-nothing
  annihilation" is falsified by my own results.json. Cross-tab (n=950,
  independently computed; cells match the owner's exactly): GT-ZERO 80/80 -> AI
  ZERO (100%); GT-PARTIAL 245 -> AI ZERO 54 (22.0%); GT-FULL 625 -> AI PARTIAL
  236 (37.8%). AI partial share 44.3% vs GT 25.8%. The real mechanism is
  SHAVING: 258 cases where GT gave full and AI deducted (236 FULL->PARTIAL + 22
  FULL->ZERO), median 0.5, 201.75 pts = 68.7% of NET harshness (293.50).
  Annihilation is 54 cases / 49.5 pts / 16.9% — real but a quarter the size.
  din's zeroed q2.b is ONE scope in ONE fixture (4/5 trials; trial 3 gave 3.0).
  HEADLINE POSITIVE: zero false credit, 80/80 — the grader never invents merit.
  ARITHMETIC CORRECTION to the first report: I wrote "Q2 -243 of -264"; the net
  total is -293.50 and Q2 = -243.25 = 82.9%. Conclusion survives; numbers were
  wrong and are restated.
CORRECTION 2 — CALIBRATION. "Non-monotone" was NOISE (0.8 band 38.7% n=111 vs
  0.7 band 45.1% n=164); I over-read small cells and withdraw it as a property.
  Now reported in TWO registers: absolute (ECE 0.2438; 465/950 at conf 1.0 ->
  auto-verification stays blocked, unchanged) and RANK-USEFULNESS (conf 1.0 ->
  86.2% within-precision; flagging conf<1.0 reviews 51.1% and captures 76.3% of
  total |delta|, lift 1.49x; residual risk at conf=1.0 is 13.8%). Different
  properties: review triage is defensible today, auto-verification is not.
concentration: top-3 terminals -106.00 = 36.1% of net harshness; worst scope
  q2.b -129.75 = 44.2%; Q2 -243.25 = 82.9%. Named: q2.a.c1 -1.96/trial (~17% of
  all harshness — the un-itemized 10-pt UpdateRate monolith; GT gave three
  students 10/10) and q2.b.c4.s3 -33.50 (its own rubric text says do-not-deduct-
  write-a-note; the grader deducts anyway on 3 of 5 fixtures at confidence 1.00).
SS-R reads: R-1 din q2.b stable annihilation 4/5 · R-2 omer 7/8 exact, the miss
  is P2's named q1.b.c4 · R-3 caught a genuine right_award_wrong_reason (moran
  q2.g.c0.s3, GT=AI=6.00; the reasoning asserts the null check is present AND
  absent in one sentence, then deducts, and still lands on the right number —
  invisible to every metric) · R-4 below · R-5 din q2.b.c4.s3 GT3->AI0 at conf
  1.00 in 4 trials, against an explicit no-deduct tariff · R-6 14 terminals with
  spread >=1.0, ALL in din's wrong-target scope => prompt underspecification
  about wrong-target answers, not genuine ambiguity.
R-4 FINDING — T1-FABRICATED IS MISCLASSIFIED HERE. dan r2's two violations are
  ONE bad scope-call in one trial. ALL FOUR constituent quote lines are present
  VERBATIM in dan's answer; the model STITCHED non-contiguous real ink.
  Validator ratios 0.7190 and 0.8370 (bar 0.85 — the second is 0.013 short).
  DL-2's definition ("the model invented evidence") does not describe this.
  SURFACED, NOT ACTED ON (validator is app/ = fenced; the tripwire definition is
  instrument = STOP-list item 2). Candidate follow-ups for owner ruling: (a) a
  multi-fragment quote check before declaring not_found; (b) a prompt line
  forbidding concatenation of non-adjacent lines.
bucket counts (34 sampled shaving cases across all five fixtures):
  interpretive_divergence 34/34 (100%). Sub-class: PL-1 cosmetic 19 · PL-10
  malformed-but-unambiguous 3 (incl. the exact AUDIT-2 get.chl() case) · PL-2
  CW/CR 3 · R-alpha contradicted-by-the-model-solution 3 (durationInMinutes —
  the teacher's own solution declares it) · explicit-tariff violations 3 · other
  interpretive 3. ZERO evidence_miss / evidence_fabricated / gt_questionable /
  transcription_artifact / rubric_underdetermined.
E5 (post-hoc, zero spend): aggregation = per-terminal MEDIAN AI award across
  k=5; 380 comparisons (38 terminals x 10 fixture pairs). Both-tie 129 (33.9%) ·
  GT-tie->AI-splits 100 (26.3%) · GT-differs->AI-ties 9 (2.4%) · agree 136
  (35.8%) · INVERTED 6 (1.6%). Directional agreement where both order: 136/142 =
  95.8%. READING: shaving is largely ORDER-PRESERVING (student ranking
  substantially intact), but 26.3% of comparisons are the grader manufacturing a
  distinction between students the teacher graded IDENTICALLY — the SS13.1
  cross-student inconsistency / appeal exposure, invisible to MAE.
SS-R.4 deliverable: mechanism "cosmetic-slip tariffing"; the single change is one
  SYSTEM_PROMPT instruction (do not deduct for unambiguous surface-form
  deviation); the metric that moves is mean signed terminal delta (-0.3089).
  Registered as E7 in PREDICTIONS.md, NOT RUN (needs owner authorization: a
  prompt change to app/ + ~$1.75 spend).
affects: docs + analysis only. No grader change, no threshold set, no GT
  amended, no app/ touched, zero spend. Batteries green.
corrections: this entry CORRECTS the mechanism and the Q2 arithmetic in the
  2026-08-26 baseline entry; that entry stands unedited (append-only).

## CHANGE 2026-08-27b — stratified bucketing correction · DL-2 split · reasoning_incoherent · E7 clause drafted

item 1 — BUCKET CORRECTION (my 34/34 flat result was unsafe; owner was right).
  Verified INDEPENDENTLY: q2.ב.c4.s3 has points_possible=3 while its own
  description ends «...סה"כ 2 נקודות», and the only thing that could forfeit the
  third point (the >0 usage check) is explicitly «לא להוריד, לכתוב הערה». The
  model reads the rubric literally and defensibly; GT awards 3. BOTH readings
  defensible => rubric_underdetermined (gt_questionable secondary). NOT
  interpretive_divergence. Corroborating q2.א.c1 data confirmed exactly as the
  owner stated: moran GT10 -> AI 7.5 on all five trials (deterministic);
  yonatan -2.00, dan -3.20, omer -0.70 mean (din -1.40, unstated). Deterministic
  wrongness = standards signature, not reasoning failure. q2.א.c1 verified as a
  10-point monolith with NO itemization (its description text even runs into the
  constructor signature).
  STRATIFIED PASS, top 6 terminals by |signed Δ|, 25 observations each (5 fixtures
  x 5 trials), flat sample retained separately. POINTS attribution of the 201.75
  shaving total: surface-form cited cause 159.25 (78.9%, E7-addressable);
  q2.ב.c4.s3 rubric_underdetermined 18.50; q2.ב.c4.s3 din wrong-target 15.00;
  din wrong-target elsewhere in q2.ב 9.00 => 42.50 (21.1%) OUTSIDE E7's reach.
  DISCREPANCY REPORTED: the owner estimated "~25 of those 33.5 points outside
  E7's reach" for q2.ב.c4.s3; my computation says ALL 33.5 are outside — 18.50
  rubric_underdetermined + 15.00 wrong-target annihilation, neither of which is
  cosmetic-slip tariffing.
item 2 — DL-2 SPLIT (owner ruling). evidence_fabricated (cited ink ABSENT, trust
  catastrophe) vs evidence_stitched (real ink, non-contiguous, misrepresented as
  one span; citation defect that breaks span-highlighting). BOTH gate Tier-1
  under distinct tags [T1-FABRICATED] / [T1-STITCHED]. Classification signal:
  do the quote's fragments exist VERBATIM in the answer. RED-FIRST (AttributeError
  on the new slots field). The 0.85 bar is UNTOUCHED — the scorer re-LABELS an
  already-failed quote, never re-scores one; a pin asserts the stitched fixture
  still scores below 0.85. Re-scored the real dan r2 event: both terminals now
  evidence_stitched, tier1 still fails => THE CORPUS CONTAINS ZERO FABRICATIONS.
  Step-3 design input recorded (do NOT build): the structural fix is likely
  allowing multiple quote spans instead of forcing one.
item 3 — reasoning_incoherent added as a §R.2 sub-bucket: award AND deduction
  cause both match GT, but the reasoning asserts P and not-P. Distinct from
  right_award_wrong_reason (where the cause diverges). Exemplar moran/q2.ג.c0.s3;
  flagged as a Phase-D J2 exemplar.
item 4 — E7 CLAUSE DRAFTED (E7_CLAUSE_PROPOSAL.md), NOT RUN. One clause, no
  worked examples, every element traced to a ratified ruling (PL-1 / PL-10 +
  AUDIT-2 / PL-2 / R-α + the rubric's own conceptual deduction vocabulary),
  states the never-compiled reason, and makes the example solution the authority
  on naming and form. Effectively constitution entry #1 (§13.2 SEED). E7 restated
  in PREDICTIONS excluding the 42.50 out-of-reach points: mean signed Δ moves
  >=0.12; GT-FULL->AI-PARTIAL 236 -> <130; K1 80/80 must hold (any false credit
  kills), K2 <=2.4%, K3 within-precision must improve.
affects: scoring.py + schemas.py (instrument, owner-ruled) => suite_hash SHIFTS.
  PLAYBOOK Tier-1 taxonomy and §R.2 updated. No GT amended, no threshold set, no
  model change (D6 seam and the Terra sweep stay queued — the buckets say this is
  a STANDARDS failure, not a capability failure, and a stronger model would
  likely reproduce the same category error). Batteries 86 passed / 1 xfailed.
  Zero spend.
corrections: this entry CORRECTS the 34/34 interpretive_divergence result in the
  2026-08-27 addendum entry; that entry stands unedited (append-only).
