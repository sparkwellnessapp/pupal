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

## CHANGE 2026-08-27c — SUT-path verification · sut_hash · E7 clause RATIFIED + grader-v3 · E8 registered

BLOCKING CONDITION — SUT PROVENANCE: CLEARED. All nine grader-path files
  verified clean (no working-tree modification): app/agents/grader/{grader,
  prompt,schemas,validator}.py · app/services/{gradable_compiler,
  selection_scoring}.py · app/schemas/{graded_test_draft,gradable,
  ontology_types}.py. NONE of the 31 pre-existing modified app/ files lies on
  the grader path. Stronger check also run: the last commit touching the SUT
  path is 71305dc (PR-G1 v2), which PREDATES the C2 run — no commit since C2
  has touched it. C2 is reproducible and E7 is a true one-variable comparison.
sut_hash LANDED (red-first; ImportError on _sut_paths/_sut_hash captured first):
  sha256 over exactly the nine grader-path files, computed at run time, stamped
  in results.json provenance beside suite_hash and surfaced in summary.md.
  DELIBERATELY DISJOINT from _hashed_paths() — the instrument can change without
  the SUT changing and vice versa; a combined hash would make a C2<->E7
  comparison unverifiable. Pins: exact file-set coverage, disjointness from
  suite_hash, presence in provenance.
  C2-era sut_hash = 7e0b1f0316a2ae67 (recorded here as the baseline SUT identity;
  C2's own results.json predates the field, so this RUNLOG line is its anchor).
E7 CLAUSE — RATIFIED WITH THREE AMENDMENTS, inserted VERBATIM as SYSTEM_PROMPT
  rule 3, rest renumbered (reasoning 3->4, award 4->5, confidence 5->6, return
  6->7). Amendments accepted as ruled: (1) the deductible list is now explicitly
  NON-EXHAUSTIVE ("including, but not limited to") plus the BEHAVIOURAL
  discriminator — form if only the written form is wrong and the intended
  computation is unambiguous; conceptual if what the code would DO differs from
  what the criterion requires. This closes the hazard the owner identified:
  din's if(LowestRateChannel == arr[i].getName()) — a function named but never
  invoked — sat one inference from "truncated or malformed but clearly-referring
  name" and would have been a K2 failure. (2) K1 encoded as a constraint the
  model READS, not only a detector we measure: "This rule never creates credit —
  a criterion whose required work is absent scores zero however well the rest is
  written." (3) "correct by definition" narrowed to "has made no naming error".
  No worked examples (they would pattern-match onto these five fixtures).
GRADING_PROMPT_VERSION bumped grader-v2 -> grader-v3 in the SAME commit as the
  clause. Version pins updated. NOTE: the flag-off byte-identity pin still
  passes and correctly so — it covers build_user_message (the USER message),
  which this change does not touch; SYSTEM_PROMPT is a separate constant.
E8 REGISTERED, NOT RUN: "The rubric's stated tariffs are the only source of
  deductions — do not invent tariffs the rubric does not name." Exclusion reason
  RECORDED in PREDICTIONS so a future reader sees it was chosen: E8 would also
  move q2.ב.c4.s3 («לא להוריד, לכתוב הערה»), destroying one-variable attribution
  and invalidating E7's "42.50 must remain" falsifiability check.
affects: app/ touched ONLY by the single prompt.py clause + version bump (the
  ruling's explicit allowance). suite_hash and sut_hash BOTH shift. No GT
  amended, no threshold set, no model change (D6 + Terra stay queued).
  Batteries 89 passed / 1 xfailed. Zero spend so far.
next: E7 run — k=5 x 5, prior_context OFF, ~$1.75; K1/K2/K3 reported FIRST.
corrections: none

## RUN 20260827-191547_gpt-4o — E7 (grader-v3, surface-form clause) — ALL KILL CRITERIA PASS; PREDICTION FALSIFIED

ref: C2 baseline 20260826-174645 · one variable: the ratified clause.
provenance: prompt_version grader-v3 · sut_hash 2c2cb60b2175ce90 (C2:
  7e0b1f0316a2ae67) · prior_context False · k=5 · cost $1.85. sut_hash EARNED
  ITS KEEP ON FIRST USE: it proves the SUT changed and that the only grader-path
  file in the diff is prompt.py, so the clause is provably the single variable
  rather than an assumption.
KILL CRITERIA (first, as ruled): K1 GT-ZERO->AI-ZERO 80/80 PASS (zero false
  credit — the never-creates-credit sentence held) · K2 GT-PARTIAL->AI-FULL 2.0%
  vs 2.4% PASS · K3 within-precision 0.7232 vs 0.6589 PASS. No kill fired.
validity: 25/25 valid · 0 reruns · 0 wall hits · parse-rate 0 (R6 not triggered)
  · $0.0738/test under ceiling · tier1 23/25, taxonomy {T1-STITCHED: 3}, ZERO
  fabrications (dan r2 x2 reproduced + a new omer r3/q1.b.c3).
PREDICTION: mean signed delta FALSIFIED — improved only 0.0307 (-0.3089 ->
  -0.2782) vs predicted >=0.12. GT-FULL->AI-PARTIAL CONFIRMED — 236 -> 111.
check (a) out-of-reach REMAINED EXACTLY 63.00 -> 63.00 (q2.b.c4.s3
  rubric-underdetermined 18.50->19.50, din wrong-target 15.00->15.00, din
  wrong-target elsewhere 29.50->28.50). No over-compliance. q2.b.c4.s3 stays
  rank 2 at -34.50 — untouched, as E7's design requires; E8 is what moves it.
check (b) q2.a.c1 WORSE overall (-49.00 -> -51.00) but mixed underneath: moran's
  deterministic 7.5 DID break (-> 8.0/7.5 mix); omer now 10.0/10.0/9.5/10.0/9.5;
  dan improved; yonatan flat; DIN COLLAPSED to a deterministic 5.0 and wiped out
  the other four fixtures' gains.
check (c) REDISTRIBUTION CONFIRMED — the headline. 12 terminals worsened,
  -24.50 pts of NEW harshness; 1 previously-clean terminal now harsh (q1.g.c6
  0 -> -1.00). Cross-tab: GT-PARTIAL->AI-ZERO 54 -> 72, GT-FULL->AI-ZERO 22 ->
  28, while GT-FULL->AI-PARTIAL 236 -> 111 and GT-FULL->AI-FULL 367 -> 486.
  125 shaves fixed, ~24 new zeros created; a zero costs the whole criterion, so
  -24.50 cancels most of +53.75 => net +29.25. q1.b.c2 jumped rank 10 -> 3.
MECHANISM (SS-R, read from the reasoning, not aggregates): TWO causes.
  (i) BEHAVIOURAL-TEST OVER-APPLICATION, dominant — the clause said WHAT is
  deductible but not HOW MUCH. The model now catches conceptual defects it
  previously missed and charges them far harder than the teacher: moran/q2.b.c1
  1.00 -> 0 x5 citing "this is a conceptual defect" (this is P2's named
  [100]-vs-[101] prediction — C2 missed it, E7 catches it and over-charges);
  dan/q1.a.c1 applies the behavioural test CORRECTLY ("the code would not work")
  then charges 1.0-1.5 where GT charges 0.5; dan/q1.b.c2 1.50 -> 0 in 3 trials.
  (ii) RESIDUAL NON-COMPLIANCE, smaller — some pure PL-1 still charged and
  sometimes harder: dan/q2.b.c0 "LowesRateChannel" spelling 1.75 -> 0.50;
  din/q2.a.c1 still cites the missing semicolon.
  WINS read the same way: din/q1.a.c0 3.00 -> 4.00 x5 ("no conceptual problems");
  moran/q1.a.c0 "durationInMinutes ... but this is not a problem" — the R-alpha
  element landing precisely. q1.a.c0 -9.50 -> -0.75, the biggest single win.
tier2/3: exact-rate 0.6084->0.7137 · MAE 0.34->0.3118 · SHIPPABLE 0.0->0.16
  (4/25 — first shippable trials in the suite's history) · boundary-flip
  0.80->0.52 · under-awards 352->252, exact 578->678 · ECE 0.2438->0.2156 ·
  instability 37.4%->30.0% · E5 inverted 1.6%->0.5%, GT-tie->AI-split
  26.3%->20.5%, directional agreement 95.8%->98.6%. NEW: compensating_error
  0 -> 4. Per-fixture 4/5 improved (moran +3.25, dan +2, omer +2 landing exactly
  on GT 89.0, yonatan +0.25); din regressed -1.5. Q2 share 82.9% -> 84.4%.
decisions: NONE taken. Verdict recorded as adopt-with-reservation, OWNER's call.
  This run is the evidence for E8 (tariff exclusivity) being the natural
  successor: the missing half is HOW MUCH. E8 stays registered and unrun.
surfaced, not acted on: residual PL-1 non-compliance; din/q2.a.c1's new
  deterministic wrong answer; compensating_error appearing for the first time
  (4 trials — total-level agreement now masks terminal disagreement on ~1/6).
cost: $1.85  wall: ~10 min
corrections: none

## CHANGE 2026-08-27d — E7-record corrections · grader-v3 ADOPTED · grader-v4 clause installed · E8 registered

E7 CORRECTION C-1 (owner ruling): "first shippable trials in the suite's history"
  was a CANCELLATION artifact and I reported it as a positive. Verified
  independently: ALL FOUR shippable trials are omer, ALL FOUR fired
  compensating_error; r0 has total_delta 0.00 against sum|terminal delta| 3.00.
  My report stated both facts on the same page and never connected them. RESTATED:
  shippable_grade_rate is NOT evidence of terminal correctness at this n;
  edit_burden is the honest cost metric (omer's BEST trial still needs 2 fixes).
  Standing PLAYBOOK rule added: a shippable trial that also fires
  compensating_error is reported as cancellation, never as a pass.
E7 CORRECTION C-2 (owner ruling): an instability REGRESSION was not surfaced.
  I reported 37.4% -> 30.0% as improvement; that measure counts HOW MANY terminals
  move, not HOW FAR the total moves. Verified: dan ai_total_spread 3.25 -> 14.00
  (totals 64.00/68.75/70.00/71.75/78.00 on IDENTICAL input, crossing grade
  boundaries 65 AND 75); yonatan 5.75 -> 7.25; din 6.75 -> 7.75; only moran
  (3.00->1.50) and omer (3.00->2.50) improved. Corpus max 6.75 -> 14.00. Pattern:
  the two weakest papers by GT destabilised, dan dominating — consistent with rule
  3 introducing a judgment call that is itself a variance source. BOTH measures now
  computed and printed every run (aggregate()["instability"], surfaced in
  summary.md), red-first, pinned by test_aggregate_reports_both_instability_measures.
DECISION (owner): grader-v3 ADOPTED as the pin. All kill criteria passed;
  within-precision +6.4pp, exact-rate +10.5pp, boundary-flip 0.80->0.52, E5
  inversions 1.6%->0.5%. The transcription playbook's redistribution rule is
  DELIBERATELY NOT FIRED: E7's redistribution has a named mechanism and a
  registered successor. If E8 also redistributes, the rule FIRES and the model
  seam (D6 -> the owner's registered Terra prior P1) becomes the next move.
grader-v4 CLAUSE INSTALLED BY THE OWNER (verbatim, not drafted by me): rule 4
  "DEDUCTION SIZE IS SET BY THE RUBRIC, NOT BY YOU", rules renumbered 5-8, rule 3
  untouched, provenance comment included, GRADING_PROMPT_VERSION = grader-v4.
  Verified: rules 1..8 sequential; rule 3 precedes rule 4; the order-of-authority
  (a named tariff -> b criterion itemisation -> c share of required work) present;
  anti-zero-inflation, note-don't-deduct and charge-once sentences all present.
  WORDING NOTE (owner ruling): E8 is NOT "the rubric is the only source of
  deductions" — false, the rubric is silent on many cases — but an ORDER OF
  AUTHORITY.
pins updated red-first (version pin grader-v3 -> grader-v4 captured red first);
  NEW test_system_prompt_rule_structure_v4 pins numbering + both ratified clauses.
  prior_context OFF path RE-VERIFIED byte-identical (sha256 5b5d72a2… = the E7
  A2_CONTENT anchor): rule 4 touches SYSTEM_PROMPT only, never build_user_message.
  sut_hash 2c2cb60b2175ce90 -> ca642409227a86ad; prompt.py confirmed the ONLY
  dirty grader-path file.
E8 REGISTERED verbatim in PREDICTIONS with K1-K4 (K4 new: max per-fixture
  ai_total_spread must not exceed 14.00 and the corpus max should fall; failure is
  diagnostic of PROMPT-SURFACE EXHAUSTION).
affects: app/ limited to prompt.py (owner-installed). Batteries 91 passed /
  1 xfailed. Zero spend so far.
corrections: this entry CORRECTS two claims in the 2026-08-27 E7 entry
  (shippable-as-positive, instability-as-improved); that entry stands unedited.

## RUN 20260827-203313_gpt-4o — E8 (grader-v4, deduction-size authority) — K2 FAILED; REDISTRIBUTION RULE FIRES

ref: E7 20260827-191547 · one variable: rule 4 (owner-installed verbatim).
provenance: grader-v4 · sut_hash ca642409227a86ad (E7 2c2cb60b2175ce90) ·
  prior_context False · k=5 · $1.98 · prompt.py the only dirty grader-path file.
KILL CRITERIA (first): K1 GT-ZERO->AI-ZERO 80/80 PASS · K2 GT-PARTIAL->AI-FULL
  7/245 = 2.9% vs bar <=2.0% ***FAIL*** · K3 within-precision 0.7400 PASS ·
  K4 max ai_total_spread 14.00 -> 8.25 PASS.
  ==> E8 IS KILLED BY ITS OWN PRE-REGISTERED CRITERION. Rule 4's leniency floor
  ("present but imperfect earns partial credit, not zero" + clause (c)'s share
  judgment) pushed two extra GT-PARTIAL terminals to full credit. K2 caught
  over-forgiveness BEFORE the improved metrics could sell it as an accuracy win.
validity: 25/25 · 0 reruns · parse 0 (R6 not triggered) · $0.079/test under
  ceiling · tier1 19/25, taxonomy {T1-STITCHED: 9} — a 3x increase.
PREDICTIONS: GT-PARTIAL->AI-ZERO 72 -> 72 FALSIFIED (no movement) ·
  GT-FULL->AI-ZERO 28 -> 32 FALSIFIED (worse) · mean signed delta -0.2782 ->
  -0.2574, improved 0.0208 vs predicted >=0.10 FALSIFIED · within_precision
  0.7400 CONFIRMED · max spread 8.25 CONFIRMED · q2.ב.c4.s3 moved CONFIRMED.
  CENTRAL THESIS FALSIFIED: magnitude authority did NOT reverse zero-inflation.
check (a) q2.ב.c4.s3 MOVED -34.50 -> -23.50 and for exactly the right reason:
  omer 1.5-3.0 -> 3.00 x5, moran -> 3.00 x4, and the reasoning quotes the
  instruction verbatim — moran r0 "לפי ההנחיות, אין להוריד נקודות על כך, אלא רק
  לציין זאת"; omer r0 "יש לציין זאת כהערה". Rule 4(a) is a clean success: the
  model now reads a NAMED TARIFF and obeys it, including the note-don't-deduct
  instruction it had overridden since C2. din stays 0 (wrong-target, correctly
  outside rule 4's scope).
check (b) E7's zeros did NOT come back: of 180 E7 zero cells, 22 recovered, 158
  unchanged, 26 NEWLY created => net +4 more zero cells.
check (c) dan's spread FELL 14.00 -> 8.25; yonatan 7.25 -> 2.00; din 7.75 ->
  6.00; moran/omer rose trivially. Corpus max 14.00 -> 8.25 — the E7 regression
  I failed to surface is repaired. dan still spans 67.50-75.75 (crosses 75).
check (d) REDISTRIBUTION AGAIN, LARGER THAN E7: 11 terminals worsened for -33.25
  (E7 -24.50); q1.ב.c7 clean -> -1.00; q2.ג.c0.s3 -15.00 -> -29.50.
  ==> THE REDISTRIBUTION RULE FIRES. Two successive clauses, each with a named
  mechanism, each MOVING failure rather than eliminating it — the
  prompt-surface-exhaustion signature. Per the standing condition, the model
  seam (D6) + the registered Terra prior (P1) are now the evidence-based next
  move. NOTE: the earlier judgment "this is a standards failure, not a capability
  failure" is what E8 tested; two failed clauses is evidence against it.
SS-R: T1-STITCHED 3 -> 9 is the second finding, concentrated in 5 cells
  (omer/q1.ב.c3 x3, dan/q1.ג.c1 x2, dan/q1.ג.c7 x2, moran/q1.ג.c6, moran/q1.ג.c7).
  Rule 4 asks the model to reason about WHICH COMPONENTS ARE PRESENT, and it now
  assembles multi-component citations to evidence that reasoning — the same
  instruction that improved tariff reasoning degrades citation integrity. The
  single-quote contract forces fabricated contiguity; the multi-span step-3
  design input is no longer speculative.
  SHIPPABLE reported as CANCELLATION per the new PLAYBOOK rule: all 4 are omer,
  all 4 compensating, edit_burden 3-4; rate unchanged at 0.16 and NOT evidence
  of terminal correctness.
tier2/3: within-precision 0.7232->0.7400 · exact 0.7137->0.7316 · MAE
  0.3118->0.2942 · under-awards 252->233, exact 678->695 · boundary-flip
  0.52->0.44 · ECE 0.2156->0.1987 · E5 inverted 0.5%->0.3%, GT-tie->split
  20.5%->15.3%, dir-agreement 98.6%->99.3%. INSTABILITY DIVERGES (both measures,
  per the new rule): terminals moving 30.0% -> 35.3% (worse) while max total
  spread 14.00 -> 8.25 (much better) — more terminals move, totals move less.
  Per-fixture: din +2.5, moran +1.0, yonatan +0.75, dan -0.5, omer -0.5.
decisions: NONE. E8 not adopted (K2). Recommended sequence surfaced for the
  owner, NOT chosen: (a) narrow rule 4(c) to remove the discretionary share
  judgment and re-run as E9, or (b) accept prompt-surface exhaustion and move to
  D6/Terra.
cost: $1.98  wall: ~11 min
corrections: none

---

## 2026-08-28 — MISSION START: grader-v5 closed loop (MISSION_grader_v5_closed_loop.md, RATIFIED)

Feature-First Mode. Build order (V5-A → F → V5-B → [STOP H-4] → §4 loop):

1. REVERT app prompt to grader-v3 (f3c56d3). Rationale: E8 killed by K2 — leaving
   rule 4 in the default prompt is de-facto adoption; every §2 baseline is
   grader-v3; the champion×grader-v3 attribution run needs v3 runnable. Proof
   obligation: post-revert sut_hash == E7's 2c2cb60b2175ce90 (E8 dirtied only
   prompt.py). test_system_prompt_rule_structure_v4 updated to the v3 structure.
2. F — K2 forensics (zero spend): 6 C2 + 5 E7 + 7 E8 GT-PARTIAL→AI-FULL cases
   side by side → K2_FORENSICS.md → feeds the verifier's absence-audit wording.
   (Pulled BEFORE the prompt is written, not parallel — it is an input to it.)
3. V5-A instrument & schemas (zero spend), red-first:
   - app/agents/grader/: plan_schemas.py (GradingPlan/TerminalPlan/PlanCheck),
     plan_validator.py (sum-exact, grid, tariff bounds, note_only pointless,
     totality vs contract), pricer.py (met/partial/not_met; tariff once per
     charge_group; clamp+grid; note_only→annotation), verifier_schemas.py
     (CheckVerdict — decode order check_id→evidence_quote→basis_he→verdict→
     confidence, the grader-v2 lever carried forward), verifier_prompt.py
     (VERIFIER_PROMPT_VERSION="grader-v5"; carries ONLY the two proven clauses
     + F-informed absence audit; verdicts are POINT-BLIND), grader_v5.py
     (PlanVerifyGrader: same skip/failure/semaphore skeleton as GraderAgent,
     SC-3 optional), llm_factory.py (openai+anthropic via docx_v3's _llm_params
     — one kwargs policy, imported not forked; gemini branch raises with the
     §1.7 ruling).
   - Draft schema additions (all optional, additive): evidence_quotes (multi-span
     — the E8 T1-STITCHED structural fix), cached_input_tokens/total_cached_
     input_tokens (§1.3 provenance), plan_version. New GradingAnnotation types:
     unverified_check, tariff_coerced, note_only.
   - Suite: scoring.py multi-span awareness (per-span verbatim validation;
     declared spans are never "stitched"; any absent span ⇒ T1-FABRICATED);
     reporting.py adds corpus edit_burden{median,max} + strict_shippable_rate;
     runner.py model seam (config: architecture v3|v5, params, plan, sc_n;
     DL-4 env-pin assert replaced by a stronger post-trial assert
     draft.model_version == spec.model_id); _SUT_RELPATHS += the v5 files;
     plans/ swept into suite_hash; provenance += architecture/params/
     plan_version/plan_sha256/cached tokens; tools/gates.py (kills-first K1/K2/
     K4 + GA-1..7 + R.3 cross-tab from results.json — mechanized, because E8's
     K2 was hand-computed and hand arithmetic has already erred twice).
   - Registry: add claude-sonnet-5 + claude-opus-5 (prices web-verified before
     entry); roster note: ALL Google entrants SKIPPED — §1.7 isolation cannot
     be positively established (this machine's google-genai path rides Vertex on
     GOOGLE_CLOUD_PROJECT = the production project; no separate eval key exists).
   - PLAYBOOK STOP-list items 4/5/6 annotated as mission-superseded (dated);
     GA gates recorded. PREDICTIONS.md: Sonnet-5 hypothesis registered.
4. V5-B — author plans/hobby_tvshow.plan.json from the CONTRACT TEXT ONLY
   (every check carries its rubric span for traceability; agent GT-exposure
   risk stated plainly in the render for the owner's review) + validator green
   + human-readable Hebrew render → [STOP H-4].

Deviations from §4 search policy: none yet. Spend so far: $0.

## 2026-08-28 — V5-A + F + V5-B COMPLETE (zero spend) → [STOP H-4]

**Step 1 — grader-v3 restore, PROVEN:** prompt.py restored from f3c56d3;
post-revert sut_hash == E7's `2c2cb60b2175ce90` byte-for-byte (E8 had dirtied
only prompt.py). Version pins updated (test_system_prompt_rule_structure_v3,
test_prior_context version literal).

**F — K2_FORENSICS.md:** all 18 GT-PARTIAL→AI-FULL cells across C2/E7/E8 are
THREE terminals: omer/q1.ב.c4 15/15 deterministic (defect-UNFOUND — presence-
verification instead of behavior-tracing over an inverted guard); yonatan/
q2.ב.c4.s1 2 cells (one unfound, one FOUND-BUT-UNCHARGED — «לא בצורה הנכונה…
עם זאת» → full credit); dan/q2.ג.c0.s3 1 cell (HALLUCINATED PRESENCE of the
absent null check). → three verifier counters: per-check evidence gating,
verdict-only output, behavior-tracing + absence-audit prompt language.

**V5-A shipped (all red-first, 130 suite+agent tests green):**
- app/agents/grader/: plan_schemas (GradingPlan/PlanCheck/CheckVerdict —
  decode order evidence→basis→verdict, the grader-v2 lever), plan_validator
  (V1–V8), pricer (evidence-gated credit, tariffs once per charge_group,
  note_only→annotation, clamp+snap), verifier_prompt (grader-v5: the two
  proven clauses + F-informed rules 3/4; POINT-BLIND rendering — a model that
  can see prices reasons about outcomes instead of evidence), grader_v5
  (PlanVerifyGrader; SC-3 median; per-span validation via the shared
  quote_match_status), llm_factory (openai+anthropic via docx_v3's _llm_params
  — one kwargs policy; gemini/xai refuse loudly).
- D6 seam: GraderAgent(llm=, model_version=) — default path byte-identical
  (pins green); eval always constructs through the factory.
- Draft schema (additive): evidence_quotes ([] = v5 marker — a caught seam bug:
  every-span-refused terminals must still gate), cached_input_tokens,
  plan_version; FlagReason +3; GradingAnnotation +5 types.
- Instrument: scoring.py per-span/refusal-claim rules (v3 path byte-unchanged);
  reporting.py strict_shippable_rate + corpus edit_burden + run_cost_usd_total;
  runner.py seam configs (architecture/plan/sc_n/params), plan hash-pin +
  pre-spend validation, DL-4 → per-trial draft-stamp assert (stronger),
  SCREENING stamp, cached-token cost, spend print; _SUT_RELPATHS +6;
  plans/ in suite_hash. Latent score_only gt_sources NameError fixed.
- tools/gates.py: kills-first K1/K2/K4 + GA-1..7 + R.3 cross-tab, mechanized;
  KNOWN-ANSWER VALIDATED against the E8 dir — reproduced the ratified record
  exactly (80/80 · 7/245=2.86% KILLED · 8.25 · cross-tab 72/32/7).
- Registry: claude-sonnet-5 ($2/$10/$0.20) + claude-opus-5 ($5/$25/$0.50),
  VERIFIED 2026-08-28 from platform.claude.com (Sonnet 5's $2/$10 is the
  STANDARD price — the scheduled Sept-1 rise to $3/$15 "will not occur", so no
  sol-style list-rate conservatism applies; ~30% tokenizer inflation noted on
  the cards). haiku-4.5 card re-verified correct.
- §1.7 Google isolation: FAILED to establish (google-genai rides Vertex on the
  production GOOGLE_CLOUD_PROJECT; no separate eval key) → ALL Google entrants
  SKIPPED; llm_factory refuses the provider. xAI excluded per roster default.
- Configs: 9 Stage-1 entrants (haiku45/nano/luna/gpt4o/sonnet5/gpt55-medium/
  terra-medium/terra-high/opus5, all -v5, ceiling 0.08). PLAYBOOK STOP 4/5/6
  amended (mission supersessions, dated); §1b mission-era gates section added.
  PREDICTIONS: P-S5 + P-ARCH registered pre-spend; P1 activation noted.

**V5-B — plans/hobby_tvshow.plan.json AUTHORED + VALIDATED:** 38 terminals,
75 checks (62 required / 12 tariff / 1 note_only), validator CLEAN against the
real contract, hash-pinned to the corrected snapshot. plan_sha256
4ce8a6bbc9463ec6…. Human render: plans/hobby_tvshow_plan_review.md with FOUR
open questions (Q-1 the q2.ב.c4.s3 «סה"כ 2» contradiction — comparison-carries-3
authored, ruling requested; Q-2 max-search tariff placement at s3; Q-3 the six
authored splits incl. the K2 q1.ב.c4 1.5+1.5; Q-4 the two additive schema
fields) + the honesty note (this agent has read GT during C2–E8; the owner
review is the anti-leak gate).

**Deviations from §4 policy:** none. **Spend: $0.00 · envelope $60.00 intact.**

LEDGER — mission spend
| item | cost | cumulative | remaining |
|---|---|---|---|
| V5-A + F + V5-B (build, zero spend) | $0.00 | $0.00 | $60.00 |

**Battery verdict (2026-08-28, before commit):** agents + api + root structural
+ this suite: GREEN with the diff (agents/api covered by the 418-pass -x run +
spot re-verification; 178 root structural; 130 suite+agents; import app.main
OK; collect-only 901 OK). tests/rubric_eval_suite + tests/services: 320 passed,
9 failed — ALL NINE PRE-EXISTING and foreign to this diff: 8× test_pedagogical
(one root cause — benchmark read_text() without encoding, Windows-cp1252
latent; file unmodified by us) and 1× test_contract_parity hobby_tvshow
(golden-benchmark drift shipped in commit b687b88, the rubric-findings
workstream; benchmark + test + compiler all unmodified in the working tree;
the failure is the benchmark's own arithmetic, 44≠60). A no-`-x` full run also
produced ~161 environmental failures (test-DB churn on back-to-back full
sweeps) — spot re-runs pass; enumeration discipline: never pipe a battery
through tail again. Surfaced to owner in the H-4 report; NOT fixed (other
mission's instrument).

## 2026-08-28 — H-4 RATIFIED WITH AMENDMENTS; items 1–5 + 7 EXECUTED; loop unblocked

**Rulings recorded:** Q-1 as authored (comparison 3 / usage note_only — the 2+1
alternative makes five ratified GT 3s unreachable) · Q-2 as authored · Q-3 as
authored except A-1 · Q-4 both fields stay. Item 5 accepted-as-known: dan
q2.א.c1 faithful-path 8.5 vs GT 9 — deliberate ±0.5 non-overfit, recorded in
the review render, not patched.

**Amendments applied (plan v2, 78 checks = 64 required / 13 tariff / 1
note_only):** A-1 q1.א.c1 → 1+1+1+1 per-parameter · A-2 q2.ב.c4.s2 start-index
tariff 0.5 + base-candidate equivalence · A-3 q1.ב.c7 semantic-flag equivalence
[PL-8] · A-4 min-index idiom on s0/s4 [PL-3] · A-5 cw/CR shorthand on q1.ב.c3
[PL-2] · A-6 wrong-math verdict semantics on q1.ג.c6/c7 (met + tariff, never
compounded). plan_version hobby_tvshow/v2 · plan_sha256 55017347381002da….

**Expressibility guard (item 3) — RED→GREEN exactly as ordered:** vs v1:
188/190 with PRECISELY the two known failures (dan/q1.א.c1 3.5 unreachable
under 2+2; yonatan/q2.ב.c4.s2 1.5 with no start-index tariff) — no third. vs
v2: **190/190**. Permanent: plan_expressibility.py + test_plan_expressibility
+ wired into _load_plan (pre-spend refusal).

**COST_TRUTH (item 4, was blocking) — LANDED:** (a) served-model truth-chain:
both agents capture the provider-REPORTED id → draft.served_models →
per-trial runner assert vs the registry model_id (date-suffix tolerant) →
provenance (absence surfaced as <unreported-by-provider>, never equated);
(b) registry unit test — **first run caught a real card defect:**
claude-sonnet-4-6 carried the 5-min cache-WRITE rate (3.75) in the cache-READ
field; corrected to 0.30 per the platform table (the old value overcharged
cached input 12.5×, affecting the transcription suite's cost math too);
(c) tools/cost_truth.py per-(UTC-day, model) ledger incl. invalid trials
(the provider billed them regardless); (d) COST_TRUTH.md protocol. Ledger
note recorded: Sonnet 5 projects ~$0.062/test pre-caching, inside the ceiling.

**Item 7 — GOOGLE RULING REVERSAL (owner, 2026-08-28):** §1.7's isolation
condition WITHDRAWN — DSQ headroom sits far above three months of launch
volume; eval traffic on the production Vertex project is immaterial. Executed:
llm_factory gemini branch is now a google-genai/Vertex adapter (_GenAIChat:
native response_schema structured output, temp 0, reasoning_effort→
ThinkingLevel, output_tokens = candidates+thoughts because thoughts BILL as
output, timeout 240s) — and EVERY call carries the Vertex request label
`vivi-workload: grading-eval` (Vertex has no per-key split; the label is what
makes the GCP billing view separable — the COST_TRUTH attribution the owner
mandated). genai ServerError added to the v5 transient tuple (429 deliberately
not — class-indistinguishable from 400; the runner's D7 re-run owns it).
gemini-3.1-pro-preview card re-verified 2026-08-28 ($2/$12 short-context
confirmed; id production-proven on this project); flash-lite card already
verified 2026-08-15. Configs: flashlite-v5 (cheap position), gemini31pro-v5
(mid). Mission §1.7 + PLAYBOOK §0.6 + ONBOARDING amended with the ruling.
Envelope unchanged. xAI stays out.

Stage-1 order (11 entrants, cheap→expensive): haiku45 → flashlite → nano →
luna → gpt4o (control) → sonnet5 → gemini31pro → gpt55-medium → terra-medium
→ terra-high → opus5. Batteries: 135 suite+agents+eval_common green.

---

## STAGE 1 — the §4 loop (k=3 screens, kills first, cheap→expensive)

**S1-1 HYPOTHESIZE — haiku45-v5 (k=3):** checklist verification is exactly the
task class small Claude models are strong at (mission §3 — the prime cheap-tier
candidate). Expected: GA-1 100% (pricer-enforced by construction), GA-5 well
under 8.25 (verdicts + deterministic pricing kill magnitude wobble), GA-2 is
the open question (can a cheap model TRACE behavior — the omer guard — or only
match presence), cost ~$0.06/test. Kill exposure: K2 via over-generous met
verdicts on partially-present work. Pre-run: one k=1 dan smoke (PROVISIONAL,
ledgered) to validate the live v5 wire — first real Anthropic structured-output
call, first live pricer pass — before 15 trials ride on it.

**S1-1 SMOKE (k=1 dan, PROVISIONAL, $0.0868):** run 20260828-194827. The whole
v5 wire held on first live contact: Anthropic structured output parsed 6/6
scopes; pricer refused credit on 3 unverifiable spans; served-model truth-chain
live (`claude-haiku-4-5-20251001`, prefix-verified). Findings:
(a) INSTRUMENT FIX (labels only, gates unchanged, red-first): all 3 refusals
    were REAL INK — adjacent statements joined on one line with ';' skipping an
    inline comment — but the DL-2 fragment splitter (newlines only) labeled
    2/3 FABRICATED. Constituents now split on ';' as well; all three relabel
    T1-STITCHED (the ratified definition applied faithfully; 0.85 bar
    untouched; both labels gate so pass/fail moved for NOTHING). Rescore
    20260828-195130 confirms. Fire-messages for the refusal path now say
    "credit already refused" instead of the false "positive award".
    score_only mode + its NameError fix validated live in the same pass.
(b) ZERO fabricated evidence — haiku invented no ink. Trust datum.
(c) T1-COST: $0.0868/test > the $0.08 hard ceiling PRE-CACHING (in 30.5k /
    out 11.3k tok — the v5 check-render + basis_he outputs are token-heavy and
    the Claude 4.7+ tokenizer +30% bites). The prime cheap candidate screens
    OVER-CEILING uncached; Anthropic caching (Stage-2 axis) is its only path
    under. Recorded, screen proceeds for information.
(d) dan k=1: Δ −9.75 (GT 84 → 74.25) — harsh-side; k=3 decides.

**Deviation (one-line rationale):** provider-independent screens run in
PARALLEL (isolated results dirs, one queue per provider); analysis stays
sequential, kills-first per run.

LEDGER: smoke $0.0868 · cumulative $0.09 · remaining $59.91

**S1-2 SMOKE flashlite-v5 (k=1 dan, $0.0326):** the gemini/Vertex adapter's
first live call — 6/6 scopes parsed, labels attached, served id verified
(`gemini-3.5-flash-lite`), thoughts-inclusive token accounting. **Δ −0.50**
(GT 84 → 83.5) at $0.033/test — under the $0.05 TARGET. 2× T1-STITCHED
(same join-adjacent-statements citation class as haiku), zero fabricated.
Full k=3 launched.
**S1-2 HYPOTHESIZE — flashlite-v5 (k=3):** cheapest viable entrant (~$0.03);
smoke suggests startlingly strong agreement; open question is stability
(GA-5) — flash-tier nondeterminism is the roster's stated concern.

**S1-3 SMOKE nano-v5 (k=1 dan, $0.0244):** first OpenAI-lane v5 call —
**tier1 PASS**, see line below. Full k=3 launched.
**S1-3 HYPOTHESIZE — nano-v5 (k=3):** the deliberate GA-5 probe (nano's
known temp-0 nondeterminism); expect verdict-median + pricing to damp spread
vs the E-series; accuracy unknown; ~$0.025/test.

LEDGER: smokes flashlite $0.0326 + nano $0.0244 · cumulative $0.14 · remaining $59.86
