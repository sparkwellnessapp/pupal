# P1 Eval Run Log

One line per run. Format: `date | config | diff-vs-prev | gate | worst-valid doc+ratio | med latency | cost | note`

2026-06-12 | v0_p1_only (gemini-3.1-flash-lite, t1.0, dpi200, 3pg/call, 3000tok) | first run | gate FAIL (0/5; 0/4 valid — din_ezra INVALID/truncated ch1) | worst-valid dan_basiuk 0.9039 | med 53.7s | $0.0086/doc (9.3x headroom) | binding metric method_call_recall 0.65–0.92 + unauthorized edits (CW→Console.WriteLine, y→'y', While→while); render=53% of wall
2026-06-14 | v0_p1_only (gemini-3.1-flash-lite, t1.1, dpi200, 2pg/call, 4000tok) | CONFOUNDED 3-field move vs t1.0/3pg/3000 | gate FAIL (0/5, all valid) | worst din_ezra 0.8854 | med 62.4s | $0.0034/doc (23.7x headroom) | binding method_call_recall 0.65–0.82; NEW regression CW→cw lowercasing 4/5 (was 1/5); model-time ~3x for no accuracy gain
2026-06-17 | v0_p1_only (gemini-3.1-pro-preview, t1.1, dpi200, 2pg/call, 4000tok) | one-field: model flash-lite→pro | gate FAIL (0/5, all valid) | worst dan_basiuk 0.8891 | med 61.7s | $0.0290/doc (2.75x headroom, 8.6x cheap) | ratio +0.029 mean (din +0.075) BUT method_call_recall flat 0.65–0.82 + GT now binding (omitted name-headers, minuteS over-fixed); next = GT audit
2026-06-17 | v0_p1_only (gemini-3.1-pro-preview, t1.2, dpi200, 2pg/call, 4000tok) | one-field: prompt t1.1→t1.2 (identity exclusion) | gate FAIL (0/5, all valid) | worst dan_basiuk 0.9407 | med 81.5s* | $0.0289/doc (2.77x) | Policy-2 WORKED: names gone (dan +0.052, moran→0.9868 over ratio bar); residual = case-lowering CW/CR→cw/cR (hits abbrev+method_call) + identifier-misread perception ceiling; *render spike = env noise, not the change
2026-06-21 | v0 (gpt-5.4-nano P2 + gemini-3.1-pro-preview P1, t1.2, dpi200, 2pg/call, correction=off) | FIRST end-to-end run | gate FAIL (0/5) | attribution PARTIAL: omer→P2(Q2.ב↔ג swap), yonatan→P2(page-split→Q2.ג drop, cov 0.83); dan/din/moran→P1 fidelity | worst omer e2e 0.8764 | spec-tier: UNDERPOWERED (off, not exercised) | $0.0309/doc | next = run p2_only to confirm P2 attribution
2026-06-22 | v0 (gpt-5.4-nano P2, t1.2 NEW content-first P2 prompt, correction=off) | mode=p2_only (clean P2 signal, perfect input) | gate FAIL (1/5; dan PASS) | attribution: omer/yonatan→P2 Q2 ב/ג mis-route (spec lacks sub-q signatures), moran→P2 input-dump (0.68, regression), din→DRAFT-GT typos not P2 | worst moran 0.6789 | spec-tier: UNDERPOWERED (off) | $0.0026/doc | next = enrich exam_spec with per-sub-question signatures
2026-06-22 | v0 (gpt-5.4-nano P2, t1.2, correction=off) | one-field: exam-spec ENRICHED with per-sub-question signatures | mode=p2_only | gate FAIL (2/5; dan+omer PASS) | FIX CONFIRMED: omer swap 0.53->1.0, yonatan Q2 shift 0.0->1.0 (kill-criterion did not fire) | worst moran 0.6789 (input-dump, unchanged) | spec-tier UNDERPOWERED (off) | $0.0027/doc | next = P2 anti-dump guard for moran
2026-06-23 | v0 (gpt-5.4-nano P2, t1.2, correction=off) | one-field: P2 anti-dump/orphan guard | mode=p2_only | gate FAIL but 3/5 PASS (dan+moran+omer) | FIX CONFIRMED: moran dump 0.68->1.0, dan orphan-note 0.98->1.0, zero regressions | remaining: din DRAFT-GT typo (getisSportiv) + boundary, yonatan 1x'}' | worst din/yonatan ~0.99 | spec-tier UNDERPOWERED (off) | $0.0024/doc | next = run per_doc (e2e ship gate) - P2 validated, attribute residual to P1
2026-06-23 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off) | END-TO-END ship gate (vs 06-23 p2_only) | gate FAIL (0/5) | attribution: dan/din/moran/yonatan->P1 perception (e2e-p2_only -0.01..-0.06, no misroute); omer->P1-marker-misread->P2-followed-marker SWAP (Q2.ב/ג 0.53, e2e 0.882 vs p2_only 0.989) | worst omer 0.8821 | spec-tier UNDERPOWERED (off) | $0.0312/doc | next = P2 harden content-over-marker (kill: else escalate P2 model); dominant wall = P1 method_call_recall + CW/CR case (lever: image_max_px)
2026-06-25 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off) | one-field: image_max_px 2000->2400 | END-TO-END | gate FAIL (0/5; moran INVALID-truncated) | RESOLUTION FALSIFIED: method_call_recall flat on all valid docs (0.69-0.79), din -0.033 (page-1 over-read), moran MAX_TOKENS, cost +59% | worst-valid din e2e 0.9267; omer Q1.ג=0.0 (P2 merge, doc-ratio-masked) | spec-tier UNDERPOWERED (off) | $0.0496/doc | next = REVERT image_max_px; pivot to gate-calibration + GT cleanup

--- INSTRUMENT CHANGE (not a run) ---
2026-06-25 | SCORER semantics changed — ⚠ COMPARABILITY BREAK on method_call_recall + abbreviations_altered | Change A: abbreviation match now case-insensitive (CW==cw; expansion CW→Console.WriteLine STILL flagged). Change B: new ScoringPolicy.case_insensitive_keywords (default ON, stamped in results.json `scoring` block) folds C# keyword case in method_calls (For()==for()). Identifier-content misreads (GetRate→getRate) and operator/structural checks UNCHANGED. | EFFECT: every run above was scored case-SENSITIVE on keyword/abbrev case; their method_call_recall (recurring 0.65–0.82 residual, partly the CW/CR→cw/cR + While→while case-lowering flagged 06-12/06-14/06-17) is NOT comparable to runs stamped scoring.case_insensitive_keywords=true. Re-baseline before reading the next run as a delta.
2026-06-25 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off) | CONFOUNDED: new content-first 2-step P2 prompt + scorer case-folding (case_insensitive_keywords ON) | END-TO-END | gate FAIL (0/5; din INVALID-P2-refused cov 0.00) | prompt: +omer swap FIXED (Q2 by content 0.99) BUT -din REFUSAL 0.97->0.00 + -yonatan Q2.ב merge | instrument: method_call_recall NO LONGER cross-run comparable, abbr now real-loss-only | worst din e2e 0.0 | spec-tier UNDERPOWERED (off) | $0.0315/doc | next = P2 prompt MUST never emit empty/refuse (kill: else escalate P2 model)
2026-06-25 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off, case_insensitive_keywords ON) | one-field: P2 prompt (best-effort, never-empty) | END-TO-END | gate FAIL (0/5) | din REFUSAL FIXED (0.00->0.8817 cov 1.0, kill did not fire) BUT yonatan NEW DUPLICATION (LowestRateChannel in Q2.א+Q2.ב, 0.9384->0.8695, worst doc) | omer Q2 stays fixed; dan/moran P1-bound | worst yonatan 0.8695 | spec-tier UNDERPOWERED (off) | $0.0322/doc | next = P2 prompt must SPLIT nested method (not merge/duplicate); dominant wall = P1 method_call ~0.87 + gate calibration

--- STOP-AND-SURFACE (analysis of the 15:35 e2e run; NO new API run — cost-tier rule §17.2) ---
2026-06-27 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off) | DECOMPOSED every e2e method_call_recall miss across all 5 docs (the §10.2 diagnostic, read all 5 report_*.md by hand) | STOP — benchmark unreachable by any permitted lever | EVERY doc fails method_call_recall (dan 0.806, din 0.786, moran 0.865, omer 0.853, yonatan 0.778; gate needs ==1.0) and EVERY miss is {CASE-normalization | GT-typo | genuine-misread} — none fixable by a model-behavior lever I may pull: CASE = model irrepressibly normalizes identifier case (CW->cw, GetChl->Getchl, TvShow->Tvshow, printAverages->PrintAverages) — §7 floor "prompt cannot suppress", scorer folds keyword case but NOT identifier case (Noam's ruling); GT-TYPO = pupulateHobbies (GT penalizes faithful output, §7); MISREAD = Tv Show->TvShow join, getisSportive->getisSortive, !=->==, GetArrShows dropped-s, updateRate->UpdatRate. E2E method_call ≈ P1 method_call on all docs => pure P1 perception, P2 passes it through faithfully (coverage 1.0 everywhere). | P2 PROMPT KILL CRITERION FIRED (§17.8): prompt ALREADY mandates SPLIT (lines 175-182) yet yonatan still duplicates nested LowestRateChannel, model's own routing_note admits the exclusivity violation — 3rd redistribution of the same nested-method (06-23 fine -> merge/refusal -> duplicate). Do not write another P2 prompt. | NO-PROGRESS BREAKER tripped (§17.9): e2e gate 0/5 across every e2e run; worst-doc bounced (omer .876 -> omer .882 -> din INVALID -> din .000 -> yonatan .870), never climbing to a pass. | The 3 levers that could move the gate — gate calibration, GT cleanup, P1/P2 model escalation — are ALL on the STOP list (Noam's). SURFACED via AskUserQuestion. Did NOT spend check_goal.sh: cheap diff signal is conclusive (0/5), §17.2 forbids burning it when the cheap signal says the gate cannot pass.
2026-06-27 | CALIBRATION EVIDENCE (Noam chose "gate calibration"; full decomposition in CALIBRATION_EVIDENCE_20260627.md; verified vs instrument, recall_check==reported 4/5 docs) | FINDING: calibration is REAL but PARTIAL — folding identifier case in method_call passes EXACTLY ONE doc (moran 0.865->1.000, all misses CW/CR case); moran's only other blocker is dropped student-REDUNDANT `((` parens (also grade-irrelevant). The other 4 fail on GENUINELY grade-critical errors the gate SHOULD keep catching: op flips omer `!=`->`==` + dan `<`->`<=`, dropped `;` (omer/yonatan), real name misreads (Tv Show->TvShow, getisSportive->getisSortive, GetArrShows->GetArrShow, updateRate->UpdatRate) + GT-typo din pupulateHobbies. => "all 5 pass" NOT reachable by calibration alone. | CRUX surfaced to Noam: folding identifier case REVERSES §8 locked ruling (identifier case-sensitive) — deciding Q is a grading ruling: "is method-name case graded in Bagrut CS?" If NO->fold safe (passes moran); if YES->don't fold, model case-normalization is a real fidelity failure. Several blockers (omer !=, dan <, dropped ;, din pupulateHobbies) need PDF adjudication (model-misread vs GT-bug) = Noam's. Awaiting ruling; will NOT touch scoring.py/GateConfig without it.

--- INSTRUMENT CHANGE (Noam ruled: method-name case NOT graded -> authorized the fold) ---
2026-06-27 | SCORER: Change C — case_insensitive_method_calls (ScoringPolicy, default ON, stamped in results.json `scoring`). extract_signature gains fold_identifier_case: folds ALL method-call identifier case (printAverages==PrintAverages, CW==cw, GetChl==Getchl), SUPERSEDING the keyword-only Change-B fold. ⚠ COMPARABILITY BREAK on method_call_recall vs every prior run (which were identifier-case-SENSITIVE). Reverses §8 lock per Noam's 2026-06-27 ruling. SAFETY PRESERVED: folds case ONLY — a content misread (GetArrShows->GetArrShow, a letter add/drop) STILL misses (pinned: test_change_c_identifier_casefold_does_not_mask_content_misread). Updated 2 tests that pinned the old lock (now require both folds off for case-sensitive baseline); added 2 Change-C tests. test_scoring + test_eval_gate: 31 passed. PREDICTED effect on 06-25 docs (offline): moran method_call 0.865->1.000; others lifted but still <1.0 on genuine misreads (dan .903, omer .941, yonatan .944, din .852). NOT yet measured e2e (no API spend) — pending GT cleanup.
2026-06-27 | DELIVERABLES this session (no eval run): CALIBRATION_EVIDENCE_20260627.md (calibration passes only moran), GT_VERIFICATION_TASKS_20260627.md (8 PDF-check items for Noam + grade-critical attribution list). FINDING: GT appears EDITED since 06-25 run (din arr(0)->arr[0]; moran [?] — stale test test_moran_aharon_fixture_structure asserts a [?] that NO benchmark contains, grep-confirmed; surfaced to Noam, did NOT touch test/GT). Other 5 suite failures = genai SDK ImportError (documented env gap). BLOCKED on Noam: GT adjudication, then ONE authoritative check_goal.sh on clean GT + folded scorer. Did NOT spend check_goal.sh (§17.2: GT not yet trustworthy).

=== AUTHORITATIVE RUN (results/20260627_175854_v0) — Noam confirmed GT 100% faithful; folded scorer ON ===
2026-06-27 | v0 (P1 gemini-3.1-pro-preview + P2 gpt-5.4-nano, t1.2, correction=off, case_insensitive_method_calls=True [Change C fold] + CLEAN/verified GT) | AUTHORITATIVE check_goal.sh k=5, all 5 fixtures | GOAL: FAIL (instrument self-consistent: runner agg agrees, exit 1 not 2) | VALIDITY: parse_failure_total=2 — din rep2 P2 truncation (finish_reason=length, cov 0.0), moran rep4 P1 truncation (finish_reason=MAX_TOKENS, cost $0.15); BOTH non-deterministic (1/5 each), config-fixable (raise p2_max_tokens / p1_max_tokens). | ACCURACY (valid reps): moran 3/5 PASS, dan/din/omer/yonatan 0/5. | FOLD+GT cleanup WORKED as predicted: method_call_recall moran 0.865->1.000 (now passes 3/5), dan 0.806->0.87-0.94, din 0.786->0.889, omer 0.853->0.941, yonatan 0.778->0.944. moran PROVES the conjunctive gate IS achievable (gate not miscalibrated to impossibility). | RESIDUAL on the other 4 = GENUINE grade-critical perception, CONFIRMED (GT clean) and SYSTEMATIC (recalls identical across reps): operator_recall 0.985 dan (`<`->`<=`) + omer (`!=`->`==`); structural dropped `;`/brackets everywhere; real identifier misreads (getisSportive->getisSortive, GetArrShows->GetArrShow, updateRate->UpdatRate). NOT safely calibratable (real deductions); prompt/resolution exhausted/falsified per §16. yonatan ALSO still P2-duplicates LowestRateChannel (kill criterion long fired). | cost $0.0372/doc (2.2x headroom). | MY accuracy levers EXHAUSTED -> SURFACED the evidence-based model-escalation decision (§17.7, Noam's) vs accept-ceiling/rescope. Will bundle the max_tokens truncation fix with whichever model config is chosen. Did NOT auto-retry/iterate (genuine perception wall is not a prompt/config surface).
2026-06-27 | v0_p1_only (claude-sonnet-4-6, t1.2, dpi200, 2pg/call, folded scorer) [Noam ran; I analyzed per P1_EVAL_PLAYBOOK -> results/20260627_201307_v0_p1_only/P1_Eval_Analysis.md] | one-field: P1 model gemini-3.1-pro -> claude-sonnet-4-6 | mode=p1_only repeats=1 | gate FAIL (0/5) | ESCALATION FALSIFIED: sonnet WORSE on 19/20 doc×metric cells vs gemini (median 5rep), 1 tie, 0 wins (worst mc din 0.750 vs 0.917, yonatan 0.765 vs 0.941; ALL ratios + operators + structurals lower) + NEW FABRICATION (invents Hebrew words 'כלב פארו' + a 'class TVRate' decl — violates F4 abstention) + abbreviations_altered CW/CR on din/omer/yonatan (gemini clean) | worst din ratio 0.8621 | med 47.6s (sonnet ~2.5x faster per call) | $0.0602/doc P1-only (~2x gemini, 1.33x headroom) | KEY: escalation is NOT a free win — gemini-3.1-pro remains best P1 perceiver tried; genuine wall stands | next = REVERT P1 to gemini-3.1-pro; decision narrows to (try a DIFFERENT model, gamble) vs (accept ceiling + rescope/expand fixtures); calibrating remaining grade-critical floors stays unsafe | n=1 caveat (k=5 would formally confirm but margins/fabrication make it robust)
2026-06-28 | v0_p1_only (gemini-3.1-pro-preview REVERTED, t1.2, folded) [Noam ran; I analyzed deep -> results/20260627_202529_v0_p1_only/P1_Eval_Analysis.md] | mode=p1_only repeats=1 | gate FAIL (0/5) | gemini>>sonnet RECONFIRMED (all metrics higher, no fabrication) | DEEP FINDING: gemini P1 is NON-DETERMINISTIC at temp0 ON the ==1.0 floors — moran mc 1.000->0.973 + ratio 0.978 (now FAILS; was 3/5 in k=5) caused by a VERBATIM-FIDELITY WOBBLE (gemini intermittently 'corrects' student errors: hobbies(countHobbies)->hobbies[...], rw->CW, CRL->CR, GetdurationInMinutes->add ()); dan mc 0.844->0.938 (swings both ways). IMPLICATION: k=5-all-green ==1.0 bar is STATISTICALLY UNREACHABLE given per-rep variance (moran P(pass all 5) ~3-12%), independent of accuracy — the wall is STABILITY not just accuracy. | din p1 ratio 0.605 (worst page) = SUSPECTED GT/CHUNK-BLEED: 3 model runs (sonnet+2 gemini) all read a SchoolHobbies class on din p1 that raw GT p1 OMITS -> recommend trial p1_pages_per_call=1 (stop cross-page bleed; one variable) OR re-verify din p1/p2 boundary (GT may be incomplete there despite verification) | worst din 0.8852 | med 39s | $0.0315/doc | strategic: redefine DONE to absorb stochasticity (floor<1.0 or best/median-of-k = Noam's grading call) vs expand fixtures n>=10 vs gamble different model
2026-06-28 | CORRECTION to the line above (Noam flagged it): the 202529 run was p1_pages_per_call=1, NOT 2. My "temp-0 nondeterminism" deep finding was CONFOUNDED (compared ppc=1 single-rep vs ppc=2 k=5 baseline) and is RETRACTED. RIGOROUS re-test (ppc=1 value vs ppc=2 per-rep min-max band): within ppc=2 gemini method_call is actually STABLE (moran 1.0x4, omer 0.946x5, yonatan 0.941x5, din 0.917x4; only dan mild 0.844-0.906) -> the wall is the STABLE systematic accuracy gap, not stability. ppc=1 vs ppc=2 = MIXED but net WORSE for the benchmark: ppc=1 raises the hopeless docs' mc ABOVE band (dan->0.938, din->0.958) but pushes the NEAR-PASS docs BELOW band (moran mc 1.0->0.973 + ratio 0.978 + struct 0.992 all below; omer op->0.985 mc->0.919; yonatan mc->0.882). ppc=1 broke the only pass-capable doc (moran) -> REVERT to ppc=2. (caveat: 1 ppc=1 rep vs 4-5 rep band; directionally clear, clean verdict needs ppc=1 @ k>=5). CONFIRMED: din p1 SchoolHobbies is GT-incomplete, NOT chunk-bleed (appeared even at 1 page/call = zero cross-page context). Lesson: I violated one-variable-per-comparison in my own analysis; always verify config.p1_pages_per_call from results.json, never assume from the config file (it had been edited between runs).
2026-06-28 | v0_p1_only (gemini-3.1-pro, t1.2, folded, VERIFIED p1_pages_per_call=3) [Noam ran; I analyzed deep -> results/20260628_174401_v0_p1_only/P1_Eval_Analysis.md] | one-field: ppc 2->3 | mode=p1_only repeats=1 | gate FAIL (4/5) BUT **moran_aharon PASSES** (FIRST p1_only gate pass ever; verified real: mc/op/st all 1.0, ratio 0.9815, kept student's `hobbies(countHobbies)` verbatim so wobble didn't fire) + **omer 1 structural token away** (only st 0.996; ratio 0.980 op 1.0 mc 1.0). | SWEEP CONCLUSION ppc=3 > ppc=2 > ppc=1: ppc=3 lifts NEAR-PASS docs' method_call ABOVE the ppc=2 band (omer 0.946->1.000, din 0.917->0.958) — exact INVERSE of ppc=1 (which broke moran). Trade-off (not free): yonatan mc 0.941->0.853 (below band), dan structural down. Hypothesis: more per-call context anchors transcription + suppresses the verbatim wobble. | validity clean (0 parse fail, no truncation at 12000 tok/call), cost $0.0285/doc (lowest of sweep), med 68s (slowest per call). | din p1 STILL worst (0.882) = GT-incomplete page1 (SchoolHobbies; confirmed not chunk-bleed by the ppc=1 run). | n=1 CAVEAT. NEXT = run ppc=3 @ k>=5 (p1_only) to confirm moran passes stably (was 3/5 at ppc=2) + whether omer firms up; kill: if moran <4/5 at ppc=3 or regressions widen -> revert ppc=2. Parallel (Noam): fix din p1 GT; pin omer's 1 structural token (grade-relevant or not = is omer effectively passing).
2026-06-28 | v0_p1_only (gemini-3.1-pro, t1.2, folded, VERIFIED ppc=3) [Noam ran after correcting GT from GT_TYPO_CANDIDATES; I analyzed deep -> results/20260628_191544_v0_p1_only/P1_Eval_Analysis.md] | one-field: GT corrected | mode=p1_only repeats=1 | gate FAIL (0/5) | GT FIXES CREDITED (no regressions): din ratio 0.882->0.896 (parce CRL->CR(), parse((->parse(, page5 blank-void->printLowChannel applied), yonatan ratio 0.951->0.958 + mc 0.853->0.882 (int-string/double-int fixes), dan flat (its GT items were real student-errors, correctly left), omer held (Char anwern->answer applied). | **REFRAME OF THE GATE QUESTION**: with clean GT+ppc3 the LEADERS are blocked by NON-grade-critical residuals: moran is grade-critically PERFECT (op/st/mc all 1.0, abbrev clean, cov 1.0) and fails ONLY doc_ratio 0.9796<0.98 — and FLIPPED PASS->fail vs 174401 (0.9815) on a 0.002 ratio wobble = knife-edge nondeterminism at the 0.98 floor (this time genuinely same-config, not a confound); omer 1 structural token (0.996, stable across 2 runs, sole blocker). | din page-1 GT STILL incomplete (SchoolHobbies block missing) = worst-doc driver (page1 ratio 0.62, doc 0.8955) — the one Tier-1 item Noam hasn't applied. | SURFACED to Noam (instrument=STOP-list): is doc_ratio>=0.98 the right HARD floor when the critical-token recalls already certify grade-safety? moran = the clean motivating case (grade-perfect, ratio-blocked). | dan mc 0.906 + yonatan mc 0.882 = residual GENUINE perception wall (real misreads). | worst din 0.8955, med 74s, $0.0282/doc | NEXT = ppc=3 @ k>=5 to measure stable pass-rate (moran/omer are AT threshold, single runs flip them); kill: if moran passes <3/5 purely on doc_ratio with criticals=1.0 -> escalate the ratio-floor calibration decision. Parallel: add din p1 GT block; pin omer's 1 structural token.
2026-06-29 | v0 (P1 gemini-3.1-pro + P2 nano, t1.2, correction=off, VERIFIED ppc=3, fixed GT) [Noam ran END-TO-END per_doc; I analyzed deep -> results/20260629_150356_v0/P2_Eval_Analysis.md] | what changed: mode=per_doc (e2e) with ppc=3 + fixed GT | repeats=1 | gate FAIL (1/5) | **MORAN PASSES THE E2E SHIP GATE — FIRST EVER e2e gate pass** (ratio 0.986, op/st/mc all 1.0, cov 1.0; VERIFIED real: faithful verbatim incl. kept student's hobbies(countHobbies) parens, no merge-masking). E2E ratio 0.986 MORE robust than its P1 0.98 (draft GT excludes hard Hebrew comments). | **omer is ONE draft-GT typo from passing**: sole E2E blocker is op 0.985 from Q1.ב `if(hobbies[i] != null)` (draft GT) vs pred `== null` — BUT omer P1/raw GT has `== null` matching model+logic (populate-empty-slot). RAW vs DRAFT GT DISAGREE -> draft GT is the typo; fix -> omer passes e2e. | P2 SEGMENTATION CLEAN: coverage 1.0 all docs, seg-tax -0.0016, no missed/extra keys, content-routing correct, NO yonatan duplication this run -> P2 is NOT the wall. ATTRIBUTION (partial, no p2_only, but seg-health conclusive): residual = P1 PERCEPTION on dan(mc .935)/din(.926)/yonatan(.889) — genuine misreads + op flips, E2E≈P1. | vs old k=5 e2e (ppc2,oldGT): 0->1 passing, omer mc 0.941->1.0, dan 0.871->0.935, din 0.889->0.926 (GT-fix+ppc3 confounded but clearly positive at the gate). | din STILL worst e2e 0.900 = raw-GT page1 SchoolHobbies still missing. | cost $0.0310/doc, med 79s, parse_fail 0. | n=1 CAVEAT. NEXT = check_goal.sh (ppc3, k>=5 e2e) to measure moran's STABLE ship-gate pass-rate (kill: if moran <4/5 on doc_ratio/op wobble with criticals=1.0 -> escalate gate-calibration). Parallel (Noam): resolve omer !=/== raw-vs-draft inconsistency (-> likely 2nd passing doc) + add din p1 GT block. Strategic: dan/din/yonatan = genuine perception ceiling (gate-calibration vs model-escalation, Noam's).
2026-06-29 | CORRECTION to omer (Noam adjudicated PDF): the GT operator is `!=` (student wrote !=); Noam fixed RAW GT ==->!=. So omer's e2e op 0.985 is a GENUINE MODEL MISREAD (!=->==), NOT a draft-GT typo. omer is NOT a near-pass — it has a real grade-critical operator flip like dan/din/yonatan. ONLY MORAN is at the ship gate. (My lean was wrong; the raw-vs-draft mismatch diagnostic still correctly flagged a GT inconsistency, it just resolved toward the draft.) | LAUNCHED check_goal.sh (ppc=3, k=5 e2e, fixed GT) bg=b5jvid4kk to measure moran's STABLE ship-gate pass-rate (expect FAIL overall: omer/dan/din/yonatan genuine perception; moran the question).
2026-06-29 | v0 (gemini-3.1-pro + nano, ppc=3, fixed GT, correction=off) | AUTHORITATIVE check_goal.sh k=5 e2e -> results/20260629_161219_v0/P2_Eval_Analysis.md | GOAL: FAIL (1/5) | **MORAN PASSES THE E2E SHIP GATE 5/5 — STABLE** (ratio 0.981-0.988 all >=0.98, op/st/mc=1.0 every rep). The p1_only ratio knife-edge does NOT bite on e2e (draft GT excludes hard Hebrew comments -> more headroom). Stability question RESOLVED: pipeline reliably passes this doc. | omer 0/5 = ONE stable operator misread (!=->==, op 0.985 x5; else perfect: ratio✓ struct✓ mc 1.0) -- the sharp gate-calibration case (is 1 control-flow flip across a whole exam a ship-block?). | dan 0/5 rock-stable perception (ratio .945, mc .935). yonatan 0/5 (mc .86-.89 + a P2 wobble rep1 ratio .871). din 0/5 BIMODAL ratio 0.64/0.90 -- raw-GT page1 SchoolHobbies STILL missing -> P2 dumps merged page1 blob into Q1.א some reps. | VALIDITY CLEAN (0 parse fail, no truncation @15k tok, runner agg agrees -> not exit 2). cost $0.0309/doc. | P2 CLEAN (cov 1.0 all docs/reps, no missed/extra) -> residual = GENUINE grade-critical P1 PERCEPTION, now k=5-confirmed with clean GT. | MY MODEL-BEHAVIOR LEVERS EXHAUSTED (ppc=3 best config, GT clean bar din p1, P2 clean, prompt spent). SURFACED to Noam: (a) din page1 GT fix; (b) gate-calibration vs model-escalation for the genuine perception wall (STOP-list, evidence-based, Noam's). No cheap config sweep left to try.

--- INSTRUMENT ADDITION (not a gate change) ---
2026-07-08 | TRUST LAYER added (Noam authorized: flag-layer MVP, cost envelope <=$0.10/doc for trust configs; accuracy gate + $0.08 v0 ceiling UNCHANGED). New surfaces: (a) pipeline core RELOCATED tests->app/services/transcription/two_phase/ (pipeline/prompts/parsing/keys/corrector/instrument) with suite shims — one definition, production runs the same code the suite measures; suite tests green post-move (169). (b) PipelineConfig gains reader_model_keys + reader_image_max_px; runner registers ONE ADAPTER PER MODEL KEY (aliased) — the old vendor-keyed dict silently last-write-wins when two same-vendor models are configured (latent bug, never bit v0 which has 1 model/vendor). (c) NEW flag instrument: app flagging.py (token-diff disagreement spans, severity by reader-vote count, brace lint, answer anchoring) + app page_provenance.py (deterministic line-vote page attribution) + suite flag_metrics.py (error/critical flag recall, burden, missed-critical details vs raw GT) — SEPARATE from scoring.py; gate untouched. (d) config v1_trust.json = v0 + readers [haiku-4.5, 4o-mini, flash-lite]. Rationale + experiment evidence (union crit-recall 0.924 on authoritative-run labels; self-consistency 0.127 falsified; self-audit falsified; judge suppression falsified) in session artifacts + memory. din p1: Noam adjudicated GT FAITHFUL (SchoolHobbies was crossed out; transcribing it = crossed-out-ink-inclusion error class) — din p1 labels are REAL errors, included in flag metrics.
2026-07-08 | v1_trust (P1 gemini-3.1-pro + readers haiku-4.5/4o-mini/flash-lite + P2 nano, ppc=3, correction=off) | mode=per_doc repeats=1 fixtures=omer_gelber | FIRST live trust run | e2e ratio 0.986, gate FAIL (op 0.985 — the known != flip, UNCHANGED by trust layer: readers never touch draft text) | TRUST: labels 11 (crit 8), covered 8 (crit 5), crit_recall 0.625 — misses = the 3 known correlated normalizations (countSport join + 2x paren-add); the == flip IS flagged | flags 84 (27 high / 53 med / 4 info), lint 0 | cost $0.0877 (trust ceiling $0.10 PASS) | 119s, parse_fail 0 | NOTE: per-doc recall on omer skews low (few, correlated errors); 5-doc run = the meaningful aggregate.

--- INSTRUMENT ADDITION (not a gate change) ---
2026-07-08 | TRUST LAYER added (Noam authorized: pivot to flag-for-review + $0.10 trust-cost envelope; accuracy gate/scoring/check_goal UNTOUCHED). Pipeline core RELOCATED tests->app/services/transcription/two_phase/ (pipeline/prompts/parsing/keys/instrument/corrector; suite keeps re-export shims; one definition shared with production; registry stays suite-side via resolver injection). NEW: app flagging.py+page_provenance.py (pure: cross-reader token-diff flags, vote-tier severity, brace lint, answer anchoring, line-vote page provenance), suite flag_metrics.py (labels=P1-vs-rawGT diffs; error/critical recall, burden, missed-critical), config v1_trust (readers=haiku-4.5+4o-mini+flash-lite), runner reader orchestration + trust aggregates + summary block, RunRecord.trust. FIXED latent bug: make_default_pipeline keyed providers by VENDOR -> two same-vendor models silently shared one adapter (last-write-wins); now per-model-key aliased adapters (pipeline.AliasedModel). Repaired 3 rotten tests exposed by genai SDK now installed (typo'd nano key, stale t1.2 prompt assertion, stale moran [?] fixture check). Evidence basis: scratchpad experiments 2026-07-08 (union crit-recall 0.924 on authoritative baseline; self-consistency 0.127 + self-audit + judge-suppression FALSIFIED; provenance 30/30). din p1 ruling (Noam): GT faithful — SchoolHobbies was CROSSED OUT; its transcription = real crossed-out-ink-inclusion error; din p1 back in flag labels.
2026-07-08 | v1_trust (P1 gemini-pro + readers haiku/4o-mini/flash-lite + P2 nano, ppc=3, correction=off) | mode=per_doc FIXTURE omer only, repeats=1 | first live trust run (after aliasing fix) | e2e 0.9860 fail (op != as always) | TRUST: crit 5/8 covered; missed = countSport-join + 2x ()-add (the known correlated tail); flags 84 (H27/M53/I4) | cost $0.0877 (trust ceiling PASS) | 119s | parse_fail 0
2026-07-08 | v1_trust | mode=per_doc ALL 5 fixtures, repeats=1, din p1 INCLUDED in labels | GOAL(trust): critical_recall 0.860 (86/100), error_recall 0.875 | flags/doc 83.6 (H32/M46.8/I4.8), lint/doc 0.8 | missed_crit 14 = correlated tail (}-drops, ()-adds, joins, chamel/Getch/sumNotSportive) + dan reader-coverage loss from haiku MAX_TOKENS truncation p4-6 (parse_fail 2, degraded per-unit as designed; dan cost $0.17) | cost avg $0.0989/doc (trust ceiling $0.10 PASS; accuracy $0.08 gate FAIL as expected for trust config) | median 93s | moran e2e still PASS with trust layer riding | NEXT: (a) reader token budget fix (haiku truncation), (b) k>=5 stability run, (c) reader_image_max_px cost sweep, (d) teacher-facing burden tuning (H32/doc)
2026-07-08 | v1_trust (P1 gemini-3.1-pro + readers haiku-4.5/4o-mini/flash-lite + P2 nano, ppc=3, correction=off) | mode=per_doc repeats=1 ALL 5 fixtures (din p1 INCLUDED in flag labels per Noam's crossed-out ruling) -> results/20260708_180655_v1_trust | FIRST full-set live trust run | TRUST: err_recall 0.875, CRIT_recall 0.860 (107/128 labels covered; 89/103 critical), missed_crit 14 = the correlated classes (paren-add x3, join x2, dropped-} x2, shared letter-level misreads chamel/GetChl/sumNo, dropped Hebrew comments x4 — comment-drop kind-classification is a tuning item) | flags/doc 83.6 (32 high / 47 med / 5 info), lint/doc 0.8 | cost $0.0989/doc — trust ceiling $0.10 PASS (dan $0.17 outlier: 2 READER truncations max_tokens/length; baseline coverage 1.0 — reader-failure isolation held; reader token-cap = tuning item) | accuracy gate + e2e ratios consistent with v0 behavior (readers never touch draft text) | n=1 rep CAVEAT: k>=5 confirmation pending before locking trust-gate thresholds | NEXT: (a) k=5 trust run, (b) reader_image_max_px cost sweep (target <=$0.08 all-in), (c) comment-drop kind fix, (d) reader p1_max_tokens bump.
2026-07-09 | v1_trust k=5 e2e (25 records) -> results/20260709_154456_v1_trust | TRUST CONFIRMATION: crit-flag recall 0.902 (0.934 after comment-kind fix), OPERATOR CLASS 100% covered (0 missed in 25 records), stable correlated misses = 5 spans (2 paren-add, 1 word-drop, 2 comment-kind-bug), unflagged-risk ~2 spans/doc | ACC unchanged: moran 5/5 PASS, others 0/5 (perception wall, by design) | cost $0.0896/doc trust-ceiling PASS | burden 37 warn/doc = the weak axis (R3 re-tier) | validity: din rep1 e2e INVALID (nano length-truncation, known mode, R4), 3 reader truncations (isolation held, R2), latency stats invalid (machine hibernated mid-run) | full analysis: TRUST_Eval_Analysis.md in the run dir | NEXT: R1 comment-kind fix -> R3 burden re-tier -> R5 image-px cost sweep; R6 trust-gate calibration = Noam's

--- TRUST-LAYER CALIBRATION (offline policy lab, 2026-07-09; NO gate change) ---
2026-07-09 | POLICY LAB (4 rounds, zero-API on day-1 persisted reader pages; policies FIT on the authoritative gemini rep and VALIDATED on an independent fresh rep) + 3 live reader probes @1400px (~$0.75) | FINDINGS: (a) vote ladder replicates: P(real|k readers disagree)=0.11/0.36/0.68; (b) flash-silent downgrade FALSIFIED (flash is silent exactly on gemini-family-shared errors — getisSortive class); (c) gemini-rerun-as-reader FALSIFIED twice (+$0.028 for ~nothing over the union); (d) gpt-4o-as-reader FALSIFIED (union crit-coverage craters to 0.71: verbosity length-truncations + gemini-like priors; $0.125/doc); (e) READERS @1400px are BETTER + cheaper: haiku+4om@1400+flash any-tier crit coverage 0.932-0.946 (vs 0.920-0.924 @2000) at $0.054/doc readers (vs 0.066); (f) warn-tier precision is information-capped ~0.45-0.55 with these signals — every extra warn-tier critical costs ~2 warnings. | CHANGES (flagging.py severity + configs; accuracy gate/scoring untouched): R1 comment-kind rule (hebrew-bearing spans w/o code signal -> info tier; matches scorer's comment-stripping semantics); R3 tier "V3": WARN = operator-MULTISET dispute (any vote count; opWARN 5/5 both baselines) OR identifier-multiset dispute with consensus-or-unanimity; R2 reader_max_tokens=8000 (dan reader truncations); R4 P2 'length' truncation now gets ONE re-request (nano reasoning tokens are stochastic; P1 stays no-retry) + p2_max_tokens 16000->24000; R5 reader_image_max_px 2000->1400. | OFFLINE PREDICTION (implemented rule, drift-checked vs lab): any-crit 0.93-0.95, warn/doc ~20 (was 31-37), warn-precision ~0.52, op-class warn coverage 5/5, cost ~$0.085/doc. k=5 live confirmation launched.
2026-07-10 | v1_trust CALIBRATED k=5 (25 rec) -> results/20260710_021723_v1_trust | BURDEN HALVED, COVERAGE UP: warns/doc 37.3->20.0 (false warns ~19->~10, warn prec 0.482), any-tier crit recall 0.902->0.919, OPERATOR CLASS 0 missed in 25 records (100% any-tier, warn-tier by construction), unflagged-crit ~1.4/doc | stable correlated wall down 14->5 spans (3 paren-add + moran line-order [GT check R9] + 1 word-drop); comment-drop class eliminated from labels (R1) | ACC unchanged: moran 4/5 (1 ratio knife-edge), din bimodal 0.64x3 = P1 STILL transcribes crossed-out SchoolHobbies -> P2 routes blob (R8 = dominant accuracy artifact) | cost $0.0936 PASS (leak: 7 reader truncations, all isolated, ~$0.01 -> R7 reader ppc 2) | 0 e2e-invalid reps (R4 worked) | runner now transport-resilient (2 network-storm run-kills before; VENDOR-CAP lesson: reader_max_tokens*ppc must stay under 4o-mini's 16384) | falsified this cycle: gpt-4o reader, rerun-reader x2, flash-silent filter; warn precision info-capped 0.45-0.55 with disagreement-only signals | full analysis: TRUST_Eval_Analysis.md in run dir | R10 trust-gate proposal (op=1.0 + unflagged<=3/doc + warns<=20 + cost<=0.10): THIS RUN PASSES ALL DIMENSIONS
2026-07-10 | GT FIX (Noam): moran p3 counter declarations — models were RIGHT (two paired lines sum+count per category); raw GT had four lines in transposed order. Fixed in raw_benchmarks. Effect: moran's stable countSportive<->sumNotS missed-critical pair dissolves; correlated wall = 3 paren-adds + 1 word-drop.
2026-07-10 | P1 PROMPT EXPERIMENT t1.3/t1.3b (crossed-out WHOLE-BLOCK reinforcement, targeting din p1) | probes: din p1_only k=1..2 x3 (~$0.15) | RESULT: KILL CRITERIA FIRED TWICE — t1.3: block omitted 2/3 reps BUT p5 regressed 0.962->0.908 SYSTEMATICALLY (3/3; over-omission — the 'check every block' + 'diagonal/vertical lines' wording matches din p5's margin ruling); t1.3b (guarded wording, explicit never-omit-unstruck): block STILL transcribed (rep A p1=0.619), p5 0.922 | REVERTED to t1.2 VERBATIM (body+version verified with negative assertions) | CONCLUSION: the prompt surface is EXHAUSTED for strike detection (t1.2's rule is the best point); din p1's crossed-out block is a MODEL-level perception limitation — candidate future fixes: CV strike-mask preprocessing, or model escalation (STOP-list, Noam's) | LESSON (instrument): gemini implicit caching returns IDENTICAL completions for identical requests within minutes — rapid-fire k>1 same-input probes are NOT independent samples; space probes or vary input.
--- MODEL CHANGE (not a run; owner decision, the fired §17.8 escalation trigger's follow-through) ---
2026-08-07 | P2 segmentor nano -> **gpt-5.6-luna** (registry +gpt-5.6-luna @$0.2/$1.2, AS_OF bumped 2026-08-07; v0.json p2_model_key + p2_max_tokens 16000->24000 per the 2026-06-27 "bundle the max_tokens truncation fix with whichever model config is chosen" intent; prod PROD_CONFIG switched too, engine version two_phase/v3_p2-luna, nano kept as revert target). ⚠ COMPARABILITY: every prior P2/e2e number is nano — first luna runs are a re-baseline, not a delta. v1_trust.json deliberately UNCHANGED (nano) so the trust-layer eval identity is preserved; a luna+trust config is its own decision. Field evidence motivating the test: nano's skip-collapse renumbering (49f9a2e1, segmentation_mismatch shipped same day). Suggested first read: p2_only --repeats 5 (cheap tier) vs the nano baselines, watching coverage, mis-keying, and the new marker-mismatch rate.
2026-08-11 | addendum (still not a run): PipelineConfig gains **p2_reasoning_effort** (OpenAI reasoning models; plumbed vlm_provider→adapters→run_phase2; P1/readers never carry it; pinned by test_p2_reasoning_effort_reaches_only_the_p2_call). v0.json + PROD_CONFIG set **"medium"** (luna's default is high) — part of the SAME luna re-baseline bundle: the first luna runs are luna@medium+24k. Unset configs (v1_trust/nano) send nothing — baseline behavior unchanged.

2026-08-11 | v0 (P2=**gpt-5.6-luna** effort=medium, 24k tok, temp OMITTED — luna 400s on temp≠1, adapter now omits temperature whenever reasoning_effort is set, pinned by test) | FIRST luna run; diff-vs-prev = the whole P2 model (re-baseline, NOT a delta) | mode=p2_only k=1 all 5 | gate 3/5 PASS (dan 1.0000, moran 1.0000, omer 0.9890; din FAIL st 0.9884, yonatan FAIL st 0.9847) | validity CLEAN (parse_fail 0, cov 1.0 everywhere, 0 missed/extra keys) | **NONE of nano's boundary-failure classes appeared**: no dump (moran 1.0 vs nano's 0.68 era), no refusal, no nested-method duplication (yonatan mc 1.0 — the fired-kill-criterion class), omer's ד.-marker correctly overridden by content | luna's ONE intrinsic defect class: unit-boundary TRIM — drops enclosing class wrapper/final `}` on 3 answers (yonatan Q1.ב+Q2.א wrappers, din 2× trailing brace) vs the draft-GT keep-wrapper convention; inconsistent (kept wrappers on omer/moran) | 3 raw-vs-draft GT disagreements surfaced where luna was faithful-to-input (din q2.ב `new`, yonatan `int string num`, `double int`) -> Noam | routing_notes now carry full auditable plans + correct orphan exclusion | $0.0031/doc, 11-16.5s/call | k=1 CAVEAT: stability unproven; luna runs at pinned default temperature (temp-0 convention inapplicable) | next = k=5 p2_only stability + wrapper-convention decision
2026-08-11 | v0 (P2=gpt-5.6-luna effort=medium; GT: 3 draft fixes applied toward raw per adjudication) | k=5 STABILITY p2_only all 5 -> results/20260811_130925_v0 | gate 0/5 docs stable (dan 4/5, omer 4/5, din 0/5, moran 0/5, yonatan 0/5; 8/25 records PASS) | validity clean (parse_fail 0) | k=1's moran 1.0000 was a LUCKY DRAW (k=5: st 0.984-0.992 every rep — §17.5 vindicated). TWO luna defect classes, 17 failing records decompose EXACTLY: (A) **key-field corruption 3/25** — junk appended to sub_question_id (dan r0: ALL SIX keys carry anchor-prose 'א…anchor לכותרת…' → cov 0.00; din r4 'איולא', yonatan r2 'אษ' → cov 0.83) — strong attribution: the P2 prompt demands a per-answer `anchor` that P2_SCHEMA (strict) FORBIDS, so the anchor leaks into the only string field available; (B) **boundary trim 14/25** — 1-2 structural chars (enclosing class wrapper / final `}`), st 0.984-0.996, stochastic per rep (moran kept the wrapper at k=1, strips it 5/5 at k=5). op=1.0 AND mc=1.0 on ALL 25 records; ZERO dump/refusal/duplication/marker-following (nano's entire family absent at k=5). GT fixes credited (din best 0.9997, yonatan best 0.9957). $0.0033/doc. NEXT (one variable): legalize `anchor`(+plan) in P2_SCHEMA — metric: class-A records 3/25 -> 0/25; kill: corruption persists ⇒ leak isn't the anchor. Then the wrapper-keeping convention (class B). st-floor calibration (are 1-2 dropped braces ship-blocking?) = Noam's.
--- P2 CONTRACT REDESIGN (owner-authorized experiment loop; model unchanged = luna@medium) ---
2026-08-11 | **SPAN CONTRACT** shipped behind PipelineConfig.p2_output_contract="spans" (two_phase/spans.py + P2_SPAN_SYSTEM; text mode = revert path): model emits line-range assignments against a CLOSED target enum; harness slices verbatim + validates the partition (one feedback re-request, then deterministic salvage). Kills k=5 class A (enum = key corruption unrepresentable) and class B (slicing = sub-line trims impossible) BY CONSTRUCTION. Smoke k=1 #1 (results/20260811_144413): 4/5 PASS, din 1.0000 (first ever), yonatan st -1 brace + orphaned preceding comment, moran 97.5s length-truncation draw (retry saved it). Iter-2 prompt extent rules (wrapper-close emphasis + preceding-comment-belongs-to-unit): smoke (results/20260811_144832) yonatan ratio 0.9957->0.9998, all else holds, no truncation.
2026-08-11 | v0 spans k=5 (results/20260811_145813) | **20/25 PASS; dan 5/5 + din 5/5 + moran 5/5 ALL at ratio 1.0000 every rep; omer 5/5** (0.9890 x5 — the intentional [?]-comment draft-GT asymmetry, stable) | yonatan 0/5: st 0.9962 x4 = EXACTLY the phantom `}` — **draft GT Q1.ב ends `    }\n}` but the class-closing `}` exists NOWHERE in raw pages 1-2** (grep-verified: every bare `}` accounted for; the student never closed schoolHobbies) — slicing cannot fabricate a char ⇒ benchmark UNREACHABLE until Noam adjudicates raw-vs-draft (4th such contradiction; prior 3 all resolved toward raw); rep3 had ONE additional missed char (st 0.9923, per-rep detail not persisted) — post-adjudication k=5 will attribute | moran rep0: 1 length-truncation draw (pf=1, 108.6s, retry PASSED — the known ~1/25 reasoning-token mode) | lat med 10.1s (vs generative ~13s), cost $0.0032/doc | NEXT: effort medium->low k=5 (one variable — truncation + latency-spike lever) in parallel with the GT ruling.
2026-08-11 | v0 spans, effort medium->**low** k=5 (results/20260811_150358, scored vs PRE-fix GT) | one variable: p2_reasoning_effort | accuracy IDENTICAL to medium (dan/din/moran 5/5 @1.0000, omer 5/5, yonatan 0/5 = phantom brace only, ALL 5 reps) + truncations 1->0, lat med 10.1->6.7s, cost $0.0032->$0.0017 | effort=low RATIFIED. | Noam adjudicated GT #4: draft yonatan Q1.ב phantom `}` REMOVED (student never closed schoolHobbies — 4/4 contradictions resolved toward raw). | (One proof-run attempt killed by a network storm outlasting the retry ladder — the documented 2026-07-09 mode; relaunched.)
2026-08-11 | **PROOF RUN — P2 BENCHMARK MET** (results/20260811_174036_v0) | v0 = luna + spans + effort=low + 24k + adjudicated GT | p2_only k=5 all fixtures: **25/25 records PASS the conjunctive gate; runner aggregate accuracy_gate_pass_all_docs=True** | dan/din/moran ratio 1.0000 on EVERY rep; omer 0.9890 x5 (the intentional [?]-comment draft-GT asymmetry = the only sub-1.0 ratios); yonatan 0.9959-1.0000 | op/st/mc = 1.0 min on all 25 records | cost $0.0029/doc, lat med 7.5s (generative-nano era: ~10-13s) | residual: ONE recovered length-truncation draw (omer rep, pf=1, 124.6s — the known stochastic reasoning-token mode, rescued by the R4 retry as designed; ~1/25 rate at effort=low) | SCOPE HONESTY: this solves P2 SEGMENTATION (p2_only). The e2e ship gate (check_goal) still carries the P1 perception wall — unchanged by this work. | Span contract ratified -> PROD_CONFIG (engine two_phase/v4_p2-spans); generative "text" contract retained as the config-flag revert path.
2026-08-15 | p1_g35_flashlite (gemini-3.5-flash-lite NEW, t1.2, dpi200, 3pg/call, 8000tok/pg, folded scorer) | model-candidate probe, registry +gemini-3.5-flash-lite @$0.30/$10.00 (NOT one-field vs any baseline) | mode=p1_only k=2 | gate FAIL (0/5 docs, 0/10 records; validity clean pf=0) | worst dan 0.9024 (mean of 2) | med 55.7s (render 66% of wall; model-time ~16s ≈3x faster than pro) | $0.0134/doc (6.0x) | VERDICT comprehension-rewriter: CW→Console.WriteLine + CR→CRC/R alterations, student-error repair (parce→parse, sumSportive/count copy-bug fixed, u→you), drops ב./ג. markers + Hebrew comments, fabricates (学ぶ, מלך המלכים, invented j-loop); mc 0.75–0.97 under the pro band; ONE strength: din crossed-out SchoolHobbies correctly omitted (p1 0.9936 vs pro ~0.62) → NOT a P1 candidate; full analysis P1_Eval_Analysis.md in run dir | CORRECTION (same day): pricing-page ש"ח cells are literal ILS (owner) — true out price $3.30/Mtok not $10; run costs were computed at $10 ⇒ true cost ∈ [$0.0045, $0.0134]/doc (token split not persisted), headroom ≥6x; registry fixed; verdict unchanged
2026-08-19 | p1_strike_check_flash (P1 gemini-3.1-pro UNCHANGED + NEW post-P1 strike-check pass: gemini-3.5-flash, sc1.3, votes=1, min_block_lines=2, 2000px) | NEW MECHANISM vs v0_p1_only (checker on/off is the only diff; configs otherwise byte-identical) | mode=p1_only PAIRED k=3 all 5 fixtures (each rep scored BEFORE and AFTER the checker on the SAME P1 output -> zero P1-variance confound) | **15/15 records, ZERO regressions on any metric** | din_ezra crossed-out SchoolHobbies block removed 3/3: ratio 0.9025->0.9807, 0.9021->0.9797, 0.9015->0.9797 (mean +0.0780) with op/st/mc delta EXACTLY 0.000000 | dan/moran/omer/yonatan: no deletions, every metric byte-identical; moran gate PASS->PASS 3/3 preserved | $0.0494/doc (P1 $0.0282 + checker $0.0212, 1.6x headroom; checker = +75% on p1_only) | checker adds median 7.8s critical path (6 concurrent 1-image calls) | KEY NEGATIVE RESULTS: (a) checker resolution reduction FALSIFIED - 0/6 detection at 1000px and 700px, strike strokes are thin lines not coarse features, 2000px required; (b) gemini-3.5-flash-LITE judge rejected - deleted 3 REAL lines on moran p2 (`return true;` + 2 comments) in 2/2 reps even with guard+votes=2; (c) sc1.2 bundled a prompt rule + code guard and regressed din recall 0/1 - separating them showed the CODE guard alone fixes the FP class while the extra prompt caution killed recall (one-variable rule, the hard way) | checker determinism: 6/6 identical ranges {17-37} on fixed input = exactly the struck block, kept Hobby class untouched | PROD UNTOUCHED (PROD_CONFIG sets no strike field -> OFF; adoption = 1 line) | offline gates: suite 130 + engine/endpoint 20 pass | full analysis results/strike_check_2026-08-19/STRIKE_CHECK_REPORT.md
2026-08-23 | PRODUCTION CHANGE (not an eval run): STRIKE-CHECK PASS ENABLED in PROD_CONFIG | p1_strike_check_model_key=gemini-3.5-flash, votes=1, min_block_lines=2, max_tokens=4000 — the exact params it was gated at (paired k=3, results/strike_check_2026-08-19/) | TWO WIRING BUGS FOUND AND FIXED ON THE WAY IN, either of which would have made the flag a no-op or worse: (1) _shared_infra() built providers only for p1/p2/reader keys, so the strike key resolved to a KeyError — and because _strike_check_pages resolves its model OUTSIDE the per-page try/except, that would have killed the ENTIRE DOCUMENT, not degraded the checker; also had to add gemini-3.5-flash to the production _MODELS map (ILS-corrected card $1.98/$11.88). (2) THE IMPORTANT ONE: production enters via trust.run_with_trust, which does NOT call run_phase1 — it drives _transcribe_pages directly. The hook lived only in run_phase1, so enabling the flag would have changed NOTHING in production while the eval suite (p1_only -> run_phase1) exercised it perfectly. Fixed structurally: perception is now ONE method, Pipeline.perceive (= P1 + strike check), called by both entry points | pinned by 3 new tests: shared_infra covers every PROD_CONFIG model key (credential-free, stubs _make_provider); PROD strike params == the gated params; and test_trust_path_runs_the_strike_check_too, which drives the real run_with_trust — VERIFIED to FAIL when trust.py is reverted to the bare _transcribe_pages call | LIVE production-path proof (din_ezra through run_with_trust + PROD_CONFIG + shared infra): strike_check 5/5 calls parsed, page 1 34->14 lines, the crossed-out SchoolHobbies block GONE, pages 2-5 untouched, 6 answers segmented; wall 52.6s = P1 $0.0259 + strike $0.0217 + P2 $0.0016 | offline gate 433 passed / 1 skipped; 910 collect; import app.main OK. One PRE-EXISTING unrelated failure: test_contract_parity[hobby_tvshow] INV-2 point-sum in a golden RUBRIC fixture (q2 criteria 44 vs declared 60) — rubric domain is unmodified in git, imports nothing I touched | REVERT = set p1_strike_check_model_key to '' (one line) | NOT YET DEPLOYED (working tree only)
2026-08-23 | v0_p1_only k=3 A/B PDF_RENDERER pymupdf vs poppler | one-field (renderer); HYPOTHESIS TEST: does the new renderer degrade page edges / drop closing brackets | gate FAIL (1/5 pass - moran 3/3) on BOTH arms; pf=0, cov=1.0 on all 30 records | **HYPOTHESIS FALSIFIED 3 independent ways**: (a) MECHANISM - MediaBox==CropBox on every page, identical page dims both backends, content bbox agrees within 1px (that 1px is inside the CamScanner watermark band) => no clipping/edge-resolution mechanism exists for a uniform rasterizer; (b) THIS RUN - structural_recall (the multiset over ';{}()[]' that a dropped brace moves) pymupdf >= poppler on 4/5 docs: dan +.0030, din +.0058, moran 0, omer +.0027, yonatan -.0013 (vs its own historical .9346-.9962 spread); (c) PRIOR k=5 A/B 2026-08-19 - better on ALL five | REAL bracket mode is ADDITION, not loss: struct_precision din .8382 / omer .9686 / yonatan .9556 vs recalls .988/.996/.992 - model INSERTS ';' and '()' the student never wrote (quoted: `new int[tv]`->`new int [tv];`, `getrate`->`getrate()`) = unauthorized-edit FIDELITY failure, prompt target not render target | missed structural tokens = 1-3 per doc out of 219-260 gold (moran zero) | INSTRUMENT: diff-line brace counting is INVALID here (P1 re-indents, so `-    }`/`+}` is the same brace: dan 13 'dropped' vs 12 'added') - use the whitespace-stripped multiset only | worst din 0.8982 driven by the crossed-out block (p1 ratio 0.6158), NOT brackets | render median 25.8s -> 1.0s (now 1.9% of wall; P1 call ~94%); poppler STALLED 2204s on one record (moran rep2), pymupdf max 1.9s | $0.0288/doc (2.8x) | NEXT: enable the strike-check pass (din -> ~0.98, already gated); do NOT revert the renderer | analysis results/20260823_154857_v0_p1_only/P1_Eval_Analysis.md
2026-08-19 | v0_p1_only + PDF RASTERIZER SWAP (poppler/pdf2image -> PyMuPDF, behind settings.pdf_renderer) | one-field A/B, configs otherwise identical | mode=p1_only INTERLEAVED k=5 both arms (50 records; each (fixture,rep) rendered by BOTH backends and run back-to-back, so arms are matched in time/machine state) | **GATE PASS - no rule violated** | render 35.26s -> 2.00s per doc (17.6x, -33.3s) | ratio: dan +0.0026, din -0.0034 (within 0.005 tol + own spread), moran +0.0042, omer +0.0012, yonatan +0.0001 | ZERO critical-recall floors regressed; FIVE improved (dan mc .875->.906, din st .971->.983, yonatan op .955->.985 st .935->.969 mc .853->.882); moran full-gate passes 2/2 -> 4/5 | VALIDITY FINDING: gate first FAILED on the BASELINE arm - moran truncated (cov=0.50, first chunk lost, MAX_TOKENS) in 3/5 poppler reps vs 0/5 pymupdf. Diagnosed + excluded per P1-playbook step 0; exclusion moves the bar AGAINST the candidate (moran baseline mean 0.7658->0.9809) and gate_eval gained a NEW guard (candidate may not contaminate more records than baseline). No threshold changed | $-neutral (local compute) | prod default flipped to pymupdf; poppler stays installed, revert = 1 env var, no redeploy | also R2: transcribe_one no longer renders the whole PDF at 72 DPI just to COUNT PAGES | full report results/pdf_render_2026-08-19/PDF_RENDER_REPORT.md
2026-08-19 | v0_p1_only + WIRE FORMAT PNG -> JPEG q90 (PipelineConfig.image_format) | PAIRED A/B (one render per rep, encoded both ways -> only compression differs) | mode=p1_only k=3 x 5 docs x 2 arms (30 records) | **GATE FAIL -> NOT SHIPPED** (dan ratio mean 0.9334 < 0.9385-0.005; yonatan st floor .9962->.9731; yonatan mc floor .8824->.8529) | prize was large and is DECLINED anyway: payload 10.03 -> 2.54 MB/doc (-75%), p1_call 19.2s -> 11.6s (-40%) | CAVEAT: k=3 not k=5 - run hit the gemini-3.1-pro DAILY quota (250 req/day) mid rep-3; a k=5 rerun could clear dan's marginal -0.0051, but a rule violation stops a change and shipping lossy compression on 'k=5 might clear it' inverts the burden of proof | code shipped INERT (image_format defaults to png); adapters now derive mime from payload bytes (vlm_provider.image_mime_for) instead of 3x hardcoded image/png, so a format switch can never mislabel the wire | rerun at k=5 when quota resets is the top follow-up
2026-08-16 | p1_g35_flash (gemini-3.5-flash NEW frontier-tier @$1.98/$11.88 ILS-corrected, t1.2, dpi200, 3pg/call, 8000tok/pg, folded scorer, timeout 600s) | one-field vs p1_g35_flashlite (model; timeout raised as completion guard only) | mode=p1_only k=2 on din/moran/omer/yonatan + dan DNF + dan ppc=1 probe | gate FAIL (0/5; 0/8 measured records) | **dan DNF: pages[1-3] chunk NEVER returns — 18 call-attempts across timeout 120/300/600s, easy chunk 9-16s every time; ppc=1 probe: all 6 pages 7-20s, doc 81.3s ⇒ 3-page dense-chunk runaway, model-level; prod (240s, ppc=3) would hard-fail** | measured docs BEAT flash-lite everywhere (din .9691 mc .917, moran .9725 mc .973, omer .9817 RATIO PASSES, yonatan .9641) and beat pro ratio on 3/4 (din +.074 — crossed-out block again handled, p1 .9958; first-ever 1.0000 pages moran p1/p3 omer p3) BUT same rewriter fidelity class: CW→C.W (yonatan), student-bug erasure again (sumSportive/count→sumNotSportive/count1), fabricated Hebrew comments, din ב./ג. markers dropped | k=2 caveat: din+omer reps byte-identical (implicit caching — effectively k=1) | $0.0256/doc (3.1x) | NOT adoptable at ppc=3 (DNF); candidate next: ppc=1 k>=2 spaced, kill = any >600s call or abbr on >=2 docs | full analysis P1_Eval_Analysis.md in run dir; prod config verified untouched
2026-07-10 | v1_trust k=1 RE-BASELINE (fixed moran GT, t1.2 restored, vendor-capped reader tokens) -> results/20260710_155034_v1_trust | cost $0.0833 (0 truncations this rep), parse_fail 0 | TRUST: any-tier crit recall 0.926, warn-tier 0.532 @ 23.2 warns/doc (prec 0.526), missed 7 = 3x paren-add (omer) + 4 wobble ({} x2, another, Getch) | ACC: moran PASSES (0.9827, GT-fix cleared its stable pair), din 24/24 crit coverage (e2e 0.64 this rep — crossed-out block, model-level, documented), others as before | FULL-STACK E2E through real HTTP API same day: signup->rubric save+compile->transcribe 200 in 131s->draft 6 answers all correctly page-attributed (conf 1.0)->9 warnings on omer (== vs != FIRST, GetArrShows drop flagged)->page-image 200. TRANSCRIPTION_ENGINE=two_phase set in backend/.env. UI: staged progress narration, evidence-ordered warnings, summary chip. MVP state: SHIPPED for live teacher testing.

---

## 2026-08-21 — Serving-surface migration: AI Studio → Vertex AI (MISSION_gemini_quota_launch_blocker)

**Variable:** serving surface ONLY. Model `gemini-3.1-pro-preview` and prompt `t1.2`
byte-identical on both arms. Zero source changes (env-var migration).

| Arm | Run dir | Surface | Mode | k |
|---|---|---|---|---|
| A (baseline) | `20260821_115501_v0_p1_only` | AI Studio | p1_only | 5 |
| V (candidate) | `20260821_122449_v0_p1_only` | Vertex | p1_only | 5 |
| C (control) | `20260821_130149_v0_p1_only` | **AI Studio again** | p1_only | 5 |
| T5 baseline | `20260821_134114_v0` | AI Studio | batch-35 | — |
| T5 candidate | `20260821_141039_v0` | Vertex | batch-35 | — |

**Result.** A-vs-V flagged 5 Q0 regressions. The control arm (A-vs-C, SAME surface,
no variable changed) flagged **3**, including one on a delta of **0.000011**. Per the
pre-registered decision rule (`PREREG_vertex_migration_2026-08-20.md`, Addendum),
`R_AC ≈ R_AV` ⇒ **Q0 at k=5 lacks the resolving power to distinguish serving
surfaces.** Same-surface noise floor measured at **0.0091** on ratio/recall metrics.

**Root cause of the contested rows on yonatan_basiuk:** a single bistable
transcription of the abbreviation `CR`, present on BOTH surfaces (altered in 2/5 A,
2/5 C, 4/5 V runs). `structural_recall` is perfectly correlated with it. On the
altered branch Vertex scores *higher* (0.9846 vs 0.9692); its worst-of-k improved.
The 2/5-vs-4/5 rate difference is not resolvable at k=5.

**No `gate_pass()` regression on any fixture.** `moran_aharon` 5/5 before and after.
`parse_failure_total` = 0 on all three arms. Cost parity: $0.02819 → $0.02867/doc.

**Latency (T5, batch of 35):** Clock 1 363.1s → **237.6s**; Clock 2 1988.7s →
**1689.7s**. Vertex: 0 timeouts, 0 429s. AI Studio: 3 timeouts. NOTE n=1 per surface;
`queue_wait` is 1569s of Clock 2's 1690s, so the binding constraint is
`PROD_MAX_CONCURRENT_PER_MODEL=5`, NOT the serving surface.

**Instrument untouched** (§17.7): scoring.py / critical_tokens.py / check_goal.sh
unmodified. Any noise band remains a PROPOSAL to the owner, not applied.


## 2026-08-23 — models_registry moved to the shared eval home (INSTRUMENT plumbing; no model, prompt, config-value, or scorer change)

**What:** `models_registry.py` is now a re-export SHIM over
`tests/eval_common/models_registry.py` — ONE registry serving BOTH eval suites
(this one + rubric_eval_suite), so a model's identity/price/tier is a single
fact and `model_key` is the cross-suite join key for per-model metrics. Three
suite-side diffs, none touching resolution of any existing key:
1. the shim itself (identical idiom to instrument.py/prompts.py; every import
   path, config, and CallRecord unchanged — pinned by
   `tests/eval_common/test_models_registry.py::test_transcription_shim_reexports_same_objects`);
2. `configs/v0_p2_correct_spec.json`: stale `"gpt-5.4-nano"` →
   `"gpt-5.4-nano-2026-03-17"` (REPAIR, not an experiment change — the old
   string was not a registry key and would KeyError at use; caught by the new
   offline dry-resolve test over both suites' configs);
3. `test_providers_and_scheduler.py::test_models_registry`: the
   cheap+frontier-per-provider assertion rescoped to the three SEED providers
   (openai/anthropic/gemini) — it was a v0 seed-set statement, not a registry
   invariant; the shared registry now also carries xai (grok-4.6, rubric-suite
   sweep model, single entry).

**Registry content change:** +grok-4.6 (xai, 2.00/6.00, cached-in omitted =
conservative upper bound). NO existing entry's key, id, price, or capability
moved; AS_OF unchanged (2026-08-15). Battery 133 passed / 1 skipped,
baseline-identical, before and after.

**Why:** the rubric suite carried identity+prices in 7 config files (split
brain) — its cost gate was silently disabled for price-less configs. Ruled in
`../rubric_eval_suite/PLAN_model_registry_normalization.md` (Noam 2026-08-23;
run AFTER the Vertex A/B above closed, per its zero-lines-changed protocol).

**For future fixture/trial work — read this once:** adding a SAME-exam fixture
is unchanged (drop raw/draft/pdf triplet by basename). A NEW-exam fixture is
blocked in TWO places: the six-key hardcode in test_ground_truth (known) AND
the runner itself — one `--exam-spec` binds the whole run and `JAVA_BAGRUT` is
hardcoded at all 4 scoring sites. The ratified lift design is BACKLOG B-30f
(per-fixture `specs/<doc_id>.json`, basename convention, `--exam-spec` as
fallback; full proposal in the plan's §9) — an instrument change to this
§17-governed suite: plan-first, owner-gated, do NOT improvise around it.
Pointers now live in TRANSCRIPTION_GT_CONVENTIONS.md §1.2 and docs.md §9/§11.


## 2026-08-28 — multi-rubric fixtures: per-fixture exam + profile (INSTRUMENT PLUMBING; no model, prompt, config-value, GT, or scorer change)

**What.** The runner no longer binds ONE exam to a run. Each fixture resolves its own
exam spec and critical-token profile; one run may span several exams and says so.

New: `exam_resolution.py` (per-doc resolution: `fixtures/<doc_id>.json` manifest →
`exams/<exam_id>.json`, else the run-level `--exam-spec` FALLBACK, else None for p1_only;
every failure loud), `profiles.py` (name → CriticalProfile; unknown key raises),
`exams/hobby_tvshow.json` (copy of `draft.json`; both kept). Changed: `runner.py`
(`resolve_fixtures(plan)` absorbs `load_spec`; `Fixture` carries its `ResolvedExam`; the 4
scoring sites take `profile=fx.profile` instead of the hardcoded `JAVA_BAGRUT`;
`RunRecord` + `results["fixtures"]` stamp exam/sha256/profile/selection_groups),
`report.py` (an `exams:` line always; an **Exam column only on a mixed run**, so every
single-exam summary keeps its historical shape), `.gitignore` (D2 — `exams/`,
`fixtures/`, `configs/`, `draft.json` un-ignored; they are the RULER a run was scored
against, and `check_goal.sh`'s default `--exam-spec` named an UNTRACKED file).

**NOT touched** (§17.7, verified by `git diff --stat`, not assumed): `scoring.py`,
`critical_tokens.py`, `normalize.py`, `keys.py`, `ground_truth.py`, `check_goal.sh`,
`check_gt_consistency.py`, `flag_metrics.py`, every GT file, every config VALUE, and all
production code under `app/`.

**Null-result proof, offline.** All five seed fixtures carry no manifest, so they take the
fallback — and it reproduces the retired `load_spec` exactly: same `ExamSpec`, same
**`to_prompt_json()` BYTES** (the actual P2 input, so the model cannot behave differently),
same `JAVA_BAGRUT` object. Pinned by
`test_seed_corpus_resolves_exactly_as_the_historical_loader_did`. This is a STRONGER claim
than the planned before/after `p2_only` k=5 and costs nothing, so no API run was spent on
a question already settled. Battery **148 passed / 1 skipped** (133 baseline + 15 new);
`app.main` imports; the sibling grading suite's cross-suite guards still green.

**Owner rulings taken (2026-08-28, Noam)** — full record in
`PLAN_multi_rubric_fixtures.md`: D1 amend B-30f to the manifest shape; D2 commit the exam
artifacts; D3 **Option A** — a question the student skipped gets its delimiter with an
EMPTY body, and the suite must support SELECTION rubrics ("answer 4 of 6"); D4 commit the
fixtures; D5 exam B is Israeli CS in C# → `JAVA_BAGRUT` unchanged; D6 measure exam B
diagnostically before admitting it to the STOP-gate partition.

**Why Option A is right under selection, and what it costs.** The span contract emits
EVERY spec target's key, filling unassigned ones with `""` (spans.py:210-214), so an empty
gold meets an empty prediction: coverage 1.0, ratio 1.0, critical clauses vacuous — and a
model that INVENTS an answer for an unanswered question scores 0.0 and raises `is_error`.
Omitting the key would have hidden exactly that invention in `extra_keys`. Cost, recorded
not designed around: an unassigned target is a `problem`, so every selection-exam document
burns the one targeted re-request and lands via deterministic salvage with routing notes.
Fixing that is D8 — a SEPARATE single-variable experiment (§17.3), not bundled.

**TWO FINDINGS, both due before any exam-B fixture lands:**
- **D7 — exam B's Q1 is UNROUTABLE, and it is a PRODUCTION gap.** Resolving the real
  artifact gives 11 keys `(1,א)(1,ב)(2,א)(2,ב)(3,א)(3,ב)(4,א)(4,ב)(5,א)(5,ב)(6,None)`,
  with rich signatures on Q2–Q6 (IsMirror, ArrangeMirror, DiceStatistics, PrintStatistics,
  TotalEarnings, TopEarners, IsSimilarWorkshop, HandleNewWorkshop) and **empty context +
  empty signatures on Q1** — because Q1 nests two levels and
  `parsing.spec_from_rubric_draft_data` reads depth 1 only. Production builds its spec
  through the same function, so any nested rubric transcribes blind TODAY. Gated:
  `test_every_in_use_exam_gives_p2_a_routing_signature` fails the moment a manifest points
  at such an exam.
- **D9 — no GT convention exists for TRACE-TABLE answers.** Exam B's Q1.א.1/Q1.ב.1 are
  trace tables ("17 cells, 0.7 each"); the whole current corpus is pure code. Two hazards:
  GT and model must agree on a shape, and `[`/`]` are structural tokens gated at recall
  1.0. Measure with one `p1_only` page first, then the OWNER writes the convention.

**Not done here:** exam-B GT (Phase 3), the D7 production fix, the D8 experiment.
`exams/bagrut_899371.json` is staged as D7 evidence but is INERT — no manifest points at
it, so no run resolves it.


## 2026-08-29 — D7 resolved (production parser fix) + D9 trace-table convention ruled

**D7 — nested rubrics were routing BLIND in production; fixed.**
`two_phase/parsing.py::_signature_from_children` (+ `first_str` lifted to module scope):
a depth-1 sub-question with no `text` of its own now composes its routing signature by
CONCATENATING its children's text, in document order. Nothing invented; a node with its
own text is never overridden. Transcription segments to depth 1, so a two-level rubric
previously handed P2 a bare letter — the omer Q2.ב⇔ג "guess the order" condition, for a
whole question, silently. PRODUCTION path: `two_phase_engine` builds its spec through this
same function, so every nested rubric was affected, not just the eval suite.
Effect on `bagrut_899371`: `Q1.א` → 600 chars naming `Check`, `Q1.ב` → 345 naming `What`,
BLIND: none, keys unchanged (11). `hobby_tvshow` is BYTE-IDENTICAL (questions,
identifiers, and `to_prompt_json()` all `==`) — the composer never fires where text exists.
Pinned by `test_nested_sub_question_composes_its_signature_from_children`. Battery 149/1.

**How we got there — and one correction worth keeping.** The owner directed a fresh
extraction of `bagrut_899371.docx` through the live pipeline (`3.10.0-fixsource`,
gpt-5.6-terra/high; 207 s, 2 retries, 59.7k/29.6k tokens) to test whether the blindness was
a stale artifact. It IS recoverable — the fresh draft carries Q1's text — but the fresh
draft was NOT landed: it flattens `q1.ב`'s nesting and reads `q1.total_points` as 40.
Composing from children on the structurally-correct ratified GT gets the same routing with
no regression, so the parser fix is the answer and re-extraction is not.

**CORRECTION (owner):** the first write-up judged that extraction by "does the raw draft
compile". That is the wrong bar — a draft is SUPPOSED to carry the teacher's errors, and
the product is capture → surface → one-click fix → teacher accepts → then it compiles (FC).
Verified: neither artifact compiles in one pass and each accepted fix opens the next
level's mismatch — that is the review cascade, not a defect.
**Compilability of a raw extraction is not an extraction-quality metric.**

**What survived the correction is narrower and sharper.** Rendering the DOCX shows
`פרק ראשון (40 נקודות)` on line 42 — a CHAPTER header — directly above `שאלה 1` on
line 44, while the exam header (line 17) states `כל שאלה - 25`. The extractor attached the
chapter's 40 to Q1. It matters because `total_points` is the grading denominator AND the
fix machinery cannot recover it: the pipeline warns "Do NOT change Q1.total_points — it is
set by the document header and is authoritative", so the `point_sum_mismatch` proposals
then drive the teacher TOWARD 40. Chapter-level point headers are a distinct confusion
class from question-level ones — a finding for the RUBRIC suite's RUNLOG, not fixed here.

**D9 — trace-table GT convention RULED** (`TRANSCRIPTION_GT_CONVENTIONS.md` §5.2a; full
measurements in `PLAN_multi_rubric_fixtures.md` D9). Bare, space-padded, fully-bounded pipe
rows; no `[TABLE]` marker; no `|---|` separator; empty cell written empty, never `||`.
Measured, not chosen: the marker injects 2 fabricated structural tokens and the separator
5 fabricated `--` (decrement) OPERATORS, both gated at recall 1.0; `|` itself is in neither
critical-token vocabulary, so the delimiters are free; a whitespace grid is disqualified
because the scorer deletes all whitespace. Cross-format gold-vs-pred measured 0.9648 for
the CLOSEST mismatched pair — under the 0.98 bar — so the GT convention must be exactly
what P1 emits, which means pinning it in the P1 PROMPT (one variable, own `p1_only` k≥5
run) rather than documenting it GT-side only.

**D9 caveat (owner) — non-uniform tables, and a LIVE frontend defect.** Sparse trace tables
(a 4×4 whose last column holds one value) are expressed as EMPTY cells, never MISSING
cells — the grid stays uniform, the content is sparse. Measured against the real detector:
written that way it renders exactly right; but if a cell is OMITTED, `buildTable` pads at
the END, so a table whose sparse column is FIRST (the common shape — `x` written once)
renders `| 1 | 5 |` as `x=1, i=5` when the ink says `i=1, arr[i]=5`. **Every value in every
sparse row lands under the wrong header, silently**, on the surface the teacher uses to
check the transcription against the scan. `detect-pipe-tables.ts` states the right
principle ("guessing where the missing cell belongs is the silent relocation the product
exists to refuse") and then end-pads, which is that guess — §3.5a's named failure, a
degradation that keeps computing. Recommended order, because reversing it regresses the
live product: (1) pin P1's prompt, (2) measure compliance, (3) then make the renderer
REFUSE a run with unequal row widths (falling back to the `<pre>` it already uses) instead
of padding. Not implemented — owner decision on urgency.


## 2026-08-29 (b) — exam-prefixed doc_ids + P1 prompt `t1.4-tables` (PROMPT CHANGE: one variable, unmeasured)

**1. doc_id is now `<exam_id>.<student>`.** The five seeds became
`hobby_tvshow.<student>` across `pdfs/`, `raw_benchmarks/`, `draft_benchmarks/`, and each
gained a `fixtures/hobby_tvshow.<student>.json` manifest naming `exams/hobby_tvshow.json`.
A bare student name stopped identifying a fixture the moment the corpus spanned two exams;
it also made every results table and RUNLOG line ambiguous. `Path.stem` strips only the
final suffix, so the dot is safe in every lookup (verified: no doc_id is split on `.`
anywhere in either suite).

Consequence, deliberate: the seeds no longer take the `--exam-spec` fallback — they resolve
through their own manifests, so `results.json` now stamps `exams/hobby_tvshow.json` instead
of `draft.json`. The equivalence guard was STRENGTHENED rather than relaxed: it now asserts
the manifest-resolved spec has the same questions, the same identifiers, and byte-identical
`to_prompt_json()` as the historical `draft.json` load. `check_goal.sh` is untouched and
still works (its `--exam-spec` is simply no longer consulted for these five).

Cross-suite: the GRADING suite keeps its own bare doc_ids (its hash pins depend on them);
the one place that reads sibling GT now maps between the namespaces via `SIBLING_DOC` in
`test_fixture_tools.py`, and the five fixture manifests' `transcription_source` provenance
paths were updated. Both suites green: 221 passed / 1 skipped.

**2. P1 prompt `t1.2` -> `t1.4-tables` — the hand-drawn-table shape is PINNED.**
(t1.3/t1.3b were the burned strike-detection wordings; the number moves past them.) Until
now the prompt said NOTHING about tables, so the pipe grid a trace table arrives as was the
model's emergent convention — ragged, mixed edge pipes, no two documents alike. That is
unusable as a benchmark because the scorer compares FORMAT as well as content: two faithful
readings of one table in different shapes measured **0.9648** against a 0.98 gate.

The rule: one row per line, `| ` … ` | ` with ` | ` between cells; EVERY row carries the
same cell count as the widest; a blank cell is written EMPTY, never skipped; `||` never
occurs; no `|---|` separator; no caption/marker; never reformat ordinary lines or code
containing `|`. A four-row worked example ships inline. The pre-existing "PLAIN TEXT only:
no markdown" rule was AMENDED in the same edit to carve the table rows out explicitly —
two absolute rules that appear to contradict each other is how you get inconsistent output.

Every clause is a measured failure mode, not a preference (PLAN §D9): `|` is in neither
critical-token vocabulary so pipes cost NOTHING; a `[TABLE n: RxC]` caption injects 2
fabricated `[`/`]` structural tokens and a `|---|` separator 5 fabricated `--` (DECREMENT)
operators, both gated at recall 1.0; whitespace alignment is disqualified because the
scorer deletes all whitespace. The same-cell-count clause is a CORRECTNESS rule, not
formatting: a trace table's first column is typically written once, so later rows are short
at the FRONT, and the review surface pads at the END — rendering every value in every
sparse row under the WRONG header, silently, on the surface the teacher uses to check the
transcription against the scan.

**Cross-stack pin:** `frontend/src/utils/p1-table-contract.test.ts` reproduces the prompt's
own example verbatim and asserts the exact 4×4 grid through the real
`detect-pipe-tables` → `TranscribedAnswerView` path, plus the four negative cases (skipped
blank shifts a value under the wrong header; caption survives as stray text; unpadded `||`
refuses to render; `if (a || b)` never becomes a table). 6/6 green. Same idea as the
segmentation-check.ts ↔ segmentation_check.py fixture pin: the prompt and the renderer
cannot drift without a red test.

⚠ **UNMEASURED.** This is a prompt change and therefore a MODEL-BEHAVIOUR change (§17.10
permits it; §17.3/§17.5 govern how it is validated). It has NOT been run against any
document. Before any table-bearing fixture is authored it needs `--mode p1_only` on the
exam-B table pages at k≥5, checked for (a) compliance with the shape and (b) NO regression
on the five seed fixtures, whose pages contain no tables and must be unaffected. The
renderer's end-padding stays as-is until that measurement lands — tightening it first would
regress today's ragged-but-rendered output.

2026-09-05 | **STAGE E — browser JPEG-in-PDF repack, 3 quality arms vs champion** (UPLOAD_LATENCY_PLAN.md R4) | ONE VARIABLE: the source corpus. Same config (v0), same GT, same scorer, same k. Variants built by `frontend/scripts/build-eval-corpus.mjs` driving the REAL `src/utils/page-repack.ts` in Chromium (pdf.js render @200 DPI -> canvas.toBlob image/jpeg -> pdf-lib), because a Pillow-built corpus would measure an encoder no teacher runs | mode=p1_only **k=3** x 5 docs x 4 arms (60 records) — ⚠ **k=3 IS A DIAGNOSTIC, owner-ruled**; §17.5 wants k>=5 and `check_goal.sh` is untouched, so NOTHING here authorises a change | **VERDICTS: q95 NOT PROMISING (invalid records), q90 PROMISING (floors moved), q85 NOT PROMISING (1 doc regressed)** | analyzer: `tools/compare_repack_arms.py`, rule reused from 2026-08-19 (regression = mean strict ratio < champion − 0.005; any critical-recall floor drop is named; VALIDITY BEFORE ACCURACY — invalid records are excluded from the ratio and decide the verdict alone)

  **q95 — killed by MAX_TOKENS, not by blur.** 3 of 15 records truncated (`dan_basiuk` 2/3, `moran_aharon` 1/3), always the pages-1-3 chunk; champion had ZERO. Cost +38% ($0.0299 -> $0.0412), median latency 52s -> 71s. For THIS corpus q95 output is LARGER than the source (2.15 -> 4.06 MB), so the model got more image, thought longer, and blew `p1_max_tokens` (gemini-3 thinking tokens are spent from the same budget before the visible answer). A bigger picture is not a better one.
  **q90 — accuracy-neutral, and 3.8x FASTER.** 15/15 valid, no doc outside the ±0.005 band, cost unchanged ($0.0296). Median doc latency **52.2s -> 13.6s**. Gate-reason counts vs champion: structural_recall 15->11, method_call_recall 12->9, doc_ratio 10->9, but operator_recall 9->11 and **abbreviations_altered 0->2** (a §17.7 named rule). Two floor drops: `din_ezra` operator_recall 1.0000->0.9855, `yonatan_basiuk` structural_recall 0.9923->0.9705.
  **q85 — one clean regression.** 15/15 valid, cost unchanged, median 14.0s, four docs IMPROVED, but `yonatan_basiuk` −0.0059 breaches the tolerance. Under the reused rule that is a fail.

  **THE LATENCY FINDING, which is the durable one:** shrinking the image cuts the P1 model call ~3.7x (52s -> 14s median) at unchanged cost, on both q90 and q85. That reproduces the direction of the 2026-08-19 wire-format run (p1_call 19.2s -> 11.6s, −40%) with a much larger effect, and it is INDEPENDENT of the upload saving. It is also the strongest argument for finishing this properly.
  ⚠ **RUN-QUALITY CAVEAT:** one q90 record (`moran_aharon` rep0) hung for 12,780s — a transport stall, not a corpus property; every other q90 record was 9–74s. Medians are quoted throughout for that reason. The arm's MEAN latency (871s) is meaningless.
  ⚠ **COVERAGE LIMIT — the reason none of this is decisive.** `raw_benchmarks/` holds P1 GT for exactly 5 documents, ALL `hobby_tvshow`. The 10 bagrut PDFs have no transcription GT, so p1_only cannot score them at any k or cost. And under `chooseSmaller` (keep the smaller file) **none of the 5 scored documents would ever be repacked in production** — all 5 GROW under every quality. So a FAILURE here is strong evidence against; a PASS is weak evidence for, because the bagrut documents get the harsher perturbation (892 -> 406 KB/page) and are unmeasured. Closing this needs teacher-verified bagrut transcriptions — owner work, not a code task.
  SPEND: **$1.96** total, ~4.5h wall (inflated by the one hung call). NOT SHIPPED; `USE_CLIENT_REPACK` does not exist yet and the plan's Stage F remains conditional.

2026-09-05 **RETRACTION — the "3x faster reading" from the Stage E k=3 run was a TIME-OF-DAY ARTIFACT, not a corpus effect.** The k=5 champion re-run settles it: the SAME corpus with the SAME config measured **52.2s median at 17:21 and 11.2s median at 21:53** — a 4.7x swing with nothing changed, LARGER than the ~3x I attributed to the re-encode. Latency tracked the clock, not the images:

  | arm | window | median | p1_call_max median |
  |---|---|---|---|
  | champion k=3 | ~17:21 | 52.2s | 45.9s |
  | jpeg95 k=3 | ~17:35 | 71.1s | 68.1s |
  | jpeg90 k=3 | ~18:01 | 13.6s | 8.0s |
  | jpeg85 k=3 | ~21:39 | 14.0s | 8.2s |
  | champion k=5 | ~21:53 | 11.2s | 7.3s |

  Provider-side latency improved somewhere between 17:35 and 18:01, and every arm run after that looked fast whatever it read. Because the arms ran SEQUENTIALLY with the champion FIRST, the confound loaded entirely onto the champion and manufactured a speedup.

  **ROOT CAUSE, and the rule to take from it:** the arms were sequential, not interleaved. The 2026-08-19 run avoided exactly this by being a TRUE paired A/B — one render per repeat, encoded both ways, so the two arms shared a moment in time. This tool's own docstring noted that difference and I did not draw the consequence. **A latency comparison across sequential arms is worthless against a provider whose latency moves on its own; only accuracy survives that design.** Any future arm comparison that intends to measure TIME must interleave the arms within a repeat, or re-run the champion adjacent to each arm.

  **WHAT SURVIVES the retraction:** the ACCURACY findings (they are not time-dependent) — q95's 3 MAX_TOKENS truncations, q90/q85 validity clean, q90 method-call precision up on 3 of 5 docs, and `yonatan_basiuk` losing the `CR` abbreviation reproducibly at every quality. **WHAT DIES:** every latency claim in the 2026-09-05 Stage E entry above, and the "reading gets ~3.7x faster" conclusion drawn from it. The plan doc and BACKLOG B-31c-RESULT are corrected alongside this entry.

2026-09-05 | **WIRE FORMAT PNG -> JPEG q90, k=5 — the 2026-08-19 re-run, at the k that run was missing** | ONE VARIABLE: `PipelineConfig.image_format` (configs/v0_wirejpeg90.json; a dataclass diff against v0 shows exactly ONE differing field). Same corpus (`pdfs`), same GT, same scorer | mode=p1_only k=5 x 5 docs x 2 arms (50 records) | **GATE FAIL -> NOT SHIPPED. Same verdict as 2026-08-19, on the SAME DOCUMENT, now with k=5 behind it** | champion `20260905_221105_v0`, variant `20260905_221441_v0_wirejpeg90`, run ~3 MINUTES APART so the timing comparison is fair (see the retraction above for why that matters)

  **THE FAILURE IS STABLE, NOT NOISE — the ranges do not overlap.** `yonatan_basiuk` champion mean 0.9597 (std 0.0014, range 0.9584–0.9614) vs variant 0.9536 (std 0.0005, range 0.9530–0.9540): **−0.0061**, past the 0.005 tolerance, with five repeats each and no overlap. It also loses the `CR` abbreviation in 2 of 5 repeats where the champion loses it in 0 — a §17.7 named rule. **The same document, the same class of failure, and the same abbreviation that the CLIENT-REPACK arms lose at every quality.** Three independent experiments now agree: `yonatan_basiuk` is the document that lossy re-encoding breaks.
  Everything else was a wash: 25/25 valid (no truncations, unlike the q95 client arm), 2 docs marginally better, 2 marginally worse, cost IDENTICAL ($0.0298 both) — Gemini prices image input by resolution tiles, not by payload bytes, so a 4.2x smaller wire buys nothing on cost. Critical metrics moved ±0.004 either way.

  **THE USEFUL PART — where the time actually goes.** With the arms adjacent, per-document median 11.2s -> 8.1s, and the model call is NOT where it came from:

  | stage (median/doc) | champion | wireJPEG | delta |
  |---|---|---|---|
  | image_encode (OUR CPU) | 3.47s | 0.74s | **−2.73s** |
  | pdf_render | 1.52s | 0.95s | −0.56s |
  | p1_call_max (the model) | 7.34s | 6.53s | −0.81s |

  So ~2.7s of the ~3.1s was **our own server PNG-encoding the page**, not the model reading it. That reframes the whole thing: the encode cost is a Stage-C-class problem (our CPU), not a Stage-E-class one (model input).

  **AND THAT IS RECLAIMABLE LOSSLESSLY.** PNG's `compress_level` changes BYTES but not one PIXEL — verified by decoding and byte-comparing. Full wire path, 4-page doc, best of 3:

  | wire encoding | total ms | payload | what the model sees |
  |---|---|---|---|
  | PNG compress_level=6 (today) | 1723 | 8.0 MB | — |
  | PNG compress_level=3 | 1214 (−30%) | 8.4 MB | **pixel-identical** |
  | PNG compress_level=1 | 949 (−45%) | 11.4 MB | **pixel-identical** |
  | JPEG q90 | 525 (−70%) | 1.9 MB | DIFFERENT (and it fails) |

  A `compress_level=3` wire encode is ~30% cheaper for +5% payload and **needs no eval gate at all**, because the decoded image is bit-identical — it is not a model-input change. NOT DONE HERE (it is a new one-variable change and wants its own before/after measurement on the box that matters); filed as the follow-up.
  SPEND: $1.50 (2 arms x 25 records). Cumulative Stage E spend today: $3.46.


## 2026-09-27 — exam B LANDED: n=5 → n=10, the corpus is now multi-exam in fact

**What.** Five `bagrut_899371` fixtures registered in `ALL_FIXTURES`, so the corpus is
10 documents across 2 exams. Battery **152 passed / 1 skipped, 0 failed** — the first
fully-green state since the GT landed. Each fixture is four files on one `doc_id`:
`pdfs/`, `raw_benchmarks/`, `draft_benchmarks/`, `fixtures/<doc_id>.json`.

| doc_id | answered (of 6) | raw pages | draft keys | EMPTY by design |
|---|---|---|---|---|
| bagrut_899371.dan_basiuk | 1,2,3,4 | 6 | 11 | 3 |
| bagrut_899371.itay_katav | 1,3,4,5 | 4 | 11 | 3 |
| bagrut_899371.itay_kraft | 2,3,4,6 | 8 | 11 | 4 |
| bagrut_899371.noam_breinshtein | 1,2,3,6 | 7 | 11 | 4 |
| bagrut_899371.roni_ben_ezra | 3,4,5,6 | 4 | 11 | 4 |

Every fixture answers exactly 4 of 6, as the exam instructs. The empty bodies are the
D3 Option A ruling: an unchosen question keeps its `=== Q.. ===` delimiter with nothing
under it, so empty-gold meets empty-prediction at 1.0 while a model that INVENTS an
answer there scores 0.0 and raises `is_error`. Omitting the block would have hidden
exactly that invention in `extra_keys`.

**Division of labour, since this was a joint GT pass.** Owner-authorized and done by the
agent: adding the unanswered questions' empty blocks (all five), and removing 7 leaked
`שאלה N` question-header lines from answer bodies (3 in noam_breinshtein, 4 in
roni_ben_ezra; §4.3 — headers live in raw GT only). Header removal was WHOLE-LINE
anchored and every site was verified standalone with `cat -A` first: a `שאלה` inside
student code or a comment is CONTENT, and deleting one would be a silent repair (FC).
Verified against a pre-edit snapshot — old bodies preserved byte-for-byte (as the parser
sees them), nothing invented, raw GT untouched. Done by the owner: itay_katav's
duplicate-Q3 region, itay_kraft's page-order → key-order reorder, and itay_kraft's raw
line 4, where a `=== PAGE 1 ===` delimiter had been concatenated onto the end of a code
line — line-anchored regex, so it parsed as INK and would have been a permanent penalty
against any model that read the page correctly.

**Also fixed (mechanical, content untouched):** two filenames that made their fixtures
unresolvable — `raw_benchmarks/bagrut_899371.itay_kraft..md` (double dot, so the stem
carried a trailing `.`) and both `bagrut_899371_itay_katav.md` files (underscore where
the PDF and manifest use a dot).

**Manifest convention, for the next author.** `fixtures/<doc_id>.json` names the shared
exam artifact and carries provenance only. Two fields beyond the hobby template earn
their place on a selection exam and are DERIVED from the GT, never typed:
`answered_questions` (which four the student chose — the first thing a reader needs, and
what distinguishes blank-by-design from missing) and `raw_pages`. Re-verified against
the final GT after the owner's edits: all five still accurate. `profile` is omitted — it
defaults to `java_bagrut`, correct for an Israeli CS/C# exam (D5).

**`check_gt_consistency`: 4 of 5 clean.** The fifth is a KNOWN-BENIGN false positive,
recorded here so nobody chases it: itay_katav raw line 30 is
`public static int[] DiceStatistics(int[] arr)   3) א)` — the student wrote the
sub-question marker TRAILING the signature on the same line. Raw keeps it (all ink,
§3.3), draft drops it (§4.3), and BOTH are correct. The checker's `_HEADER_RE` is
whole-line anchored, so it cannot strip an inline marker and reports it as an interior
deletion — the inline variant of the limitation its own docstring documents. Separately,
the tool CRASHES on Windows while printing its own `✓` success line (cp1252); pre-existing,
unrelated, and `PYTHONIOENCODING=utf-8` works around it.

**⚠ n=10 MEETS `FLAG_TRUST_MIN_FIXTURES` numerically — do not over-read it.** This is the
first corpus that does, and `flag_metrics_trustworthy` will now report `True`. Two
caveats: that flag governs TRUST-LAYER (reader) configs only, which are retired in
production and measured solely via `configs/v1_trust.json`; and the corrector's own
`trustworthy` flag uses the same n while its standing precondition is n≥10 *with
deliberately-included student-spec-errors*. These fixtures carry plenty of real student
errors (`DiceStatictics`, `int.minValeu`, capital `Public`, lowercase `printStatistics`),
several of which ARE spec-identifier deviations — but whether that satisfies the
precondition is the OWNER's call (§17.7 forbids the agent concluding the spec-tier
corrector is safe), not an inference from a count.

**⚠ TWO THINGS ARE NOW DUE, and both are measurements, not code.**
1. **D6 is live.** The `/goal` STOP gate is whatever `raw_benchmarks/*.md` globs, so it is
   now 10 fixtures × k=5 — roughly 2× the wall-clock and 2× the dollar cost of the
   authoritative run, and it will very likely go RED until the model clears exam B. That
   is correct (the benchmark got harder and more honest), but the "we're done" signal is
   withdrawn from this commit onward. Quarantine, if wanted, is `GOAL_FIXTURES` — never
   an edit to `check_goal.sh`.
2. **Prompt `t1.4-tables` is still UNMEASURED, and it is now load-bearing.** Three of the
   five bagrut fixtures answered Q1, the corpus's first TRACE-TABLE question, and all six
   of their Q1 tables follow §5.2a exactly — rectangular, fully bounded, space-padded, no
   adjacent pipes (measured: widths uniform per table, `itay_katav` even writes the empty
   first cell as `|  |`). So the convention holds on real authored GT. What has NOT been
   tested is whether P1 EMITS that shape: the pin needs `--mode p1_only` at k≥5 on those
   pages, checked for compliance AND for no regression on the five hobby fixtures, whose
   pages contain no tables and must be unaffected.

**Untouched:** `scoring.py`, `critical_tokens.py`, `normalize.py`, `keys.py`,
`ground_truth.py`, `check_goal.sh`, gate thresholds. Five more bagrut PDFs sit in `pdfs/`
with no GT (`din_ezra`, `raz_cohen`, `tal_gorban`, `yael_kogen`, `yahli_cohen`) — inert.


## 2026-09-27 — MISSION_transcription_accuracy: Phase 0 (instruments) + baseline launched · spend so far ≈ $3

**Instrument corrections found (all verified, none touches the gate):**
1. **C2 — Gemini thinking tokens were never billed.** `gemini_provider` recorded
   `candidates_token_count` only; Gemini bills thinking as output. Every Gemini cost figure in
   this suite under-reported by the whole thinking spend. Fixed (`output = candidates + thoughts`),
   and `Usage.reasoning_tokens` added for reporting (OpenAI breakdown too; Anthropic's
   `output_tokens` already includes thinking).
2. **Registry prices (provider pages, not the leaderboard):** `gemini-3.5-flash` 1.98/11.88 →
   **1.50/9.00** and 3.5-flash-lite out 3.30 → **2.50** (the old values were an ILS conversion,
   ~32% high — production's STRIKE CHECK runs on 3.5-flash, so every strike-check cost was
   overstated). Added gemini-3.8-flash (**costed at LIST $1.50/$7.50**; $0.75/$3.75 is promo
   "through Dec 31 2026" — the gpt-5.6-sol rule), gpt-6-sol/luna/astra, claude-opus-5-5. AS_OF →
   2026-09-27.
3. **The C2 gate lives in runner.py (`COST_CEILING_USD = 0.08`), not in check_goal.sh**, which
   gates validity + accuracy only. Verified; the $0.08 in the docs is right.
4. `insertion_cases.json` and the new `table_parser_parity.json` were **gitignored** — un-ignored
   (same class as D2).

**New instruments (additive, self-tested: GT-vs-GT = 1.0, perturbations exact):**
`relocation.py` (production, pure §3.3 function, 25 tests), `insertion_cases.py` (§3.4 validator
on the same function), `diag_hebrew.py`, `diag_tables.py` (line-for-line mirror of the review
UI's `detectPipeTables`, cross-pinned by `table_parser_parity.json` — TS and Python assert the
same 27 cases), `diag_arrows.py`, `diagnostics.py` (runner glue), `mission_report.py`,
`hebrew_taxonomy.py`. Runner: `--concurrency`, per-record `diag` + `tokens`, per-record outputs
under `results/*/outputs/`, p2_only now applies the gold arrows (§4.4). `configs/prod.json` =
PROD_CONFIG byte-for-byte (`v0.json` lacks the strike check, so it is NOT the baseline).
Adapters: Anthropic current family routed through `output_config` (sampling params and forced
tool_choice 400 on Opus 5.5/Sonnet 5); `p1_reasoning_effort` knob (empty = byte-identical).

**§3.4 validator: ALL 3 CASES FAIL — Bet 3 and §4.4 blocked on the owner.** Evidence:
- `itay_kraft#01`: raw page 5 already has the two declarations AFTER `{` — the intended place.
  Raw was authored with the insertion pre-applied (OD-A1 says raw = physical). Draft conforms.
- `itay_katav#01`: raw AND draft carry the note inline as `// בהנחה … ב- null/אפס.` — no ⟦⟧, a
  `//` OD-A3 calls invented, and text ≠ the case (`ב-null/מאופס`). `target.line` is not a
  complete line.
- `yonatan#01`: the source `|| (answer=="n") || (answer=='N')` is in neither raw nor draft;
  both anchors differ from raw (`if ( this` vs `if (this`; `\בדיקה` vs `// בדיקה`).

**§4.2 table convention: SINGLE and followed — Bet 2 unblocked.** P1 prompt (t1.4-tables) ↔
`TRANSCRIPTION_GT_CONVENTIONS.md` §5.2a ↔ `detect-pipe-tables.ts` agree. 6 GT tables, all
rectangular, 0 ragged, 0 refused rows. No GT cell holds a literal `|`; the convention has NO
escape for one (TBL-4 refuses it; `CODE_TOKENS` rejects any `||`/`;`/brace row) — a gap,
surfaced, not invented around.

**Baseline p2_only (prod, k=3): the P2-is-solved premise holds on ONE exam.** Hobby 5/5 docs pass
on all repeats. Bagrut 2/5 — and the 3 failures are EXACTLY the 3 fixtures whose draft GT keeps
marker-only lines (`(1)`, `א) (1)`, `ב) 1)`, `א)` — 10 lines); P2 correctly drops them (§4.3)
and pays `(`/`)` at recall 1.0. Raw GT keeps the same non-canonical markers (§3.3 wants `א.`,
which P1 emits), so P1 on bagrut pays too. **GT class (e), surfaced — caps the gate on 3/10
fixtures independent of the model.** Also: omer Q1.ב draft still has the `[?]` comment the
2026-08-11 audit (F-1) ruled stale — Hebrew e2e 0.34 there, gate unaffected (comment).

**Bet-1 plumbing probe (1 fixture, P1 only, NOT the screen):** gpt-5.6-sol $0.131 and
claude-opus-5-5 $0.113 for 4 pages — dead for P1 on C2. claude-sonnet-5 input-dominated
(17.8k in / 4 pp) → dead on C2 and weakest (0.912). gemini-3.5-flash truncated (4.8k thinking
at `low`, MAX_TOKENS). gemini-3.8-flash 0.9928 / Hebrew 0.990 / $0.021 — leads. **Latency in
this window is contaminated by my own parallel uploads** (all vendors 155–230 s per 3-page chunk;
the baseline's strike-check timeouts began when the probes launched) — C3 is re-measured in
isolation for finalists.

---

## 2026-09-27 — MISSION: baseline e2e (prod, k=3) + the Hebrew PROSE view · spend ≈ $4.5 / $300

**Run:** `configs/prod.json` (= PROD_CONFIG), `per_doc`, k=3, `--concurrency 4`, 10 fixtures →
`results/20260927_153839_prod`. No variable changed: this IS the reference.

| dimension | worst doc (baseline) | notes |
|---|---|---|
| E2E gate | 0/10 docs pass all 3 repeats (moran 2/3) | bagrut caps at 0 by the marker-line GT (above) |
| P1 `doc_ratio_strict` | din_ezra 0.894 | roni 0.997 is the only bagrut P1 pass |
| E2E `doc_ratio_strict` | noam 0.905 | |
| Hebrew PROSE P1 (rep0) | yonatan 0.279 / omer 0.147 | margin comments dropped; a hallucinated clause (below) |
| Tables | noam cells 0.900; micro 0.9689 (654/675); shape 1.00 on all 3 table docs | target micro ≥0.97, worst ≥0.95 → noam |
| Arrows | 0/9 placed, 0 false | expected: nothing places without Bet 3 |
| C2 cost | $0.048/doc avg (bagrut 0.050, hobby 0.046) | PASS |
| C3 wall | p50 311 s · p95 458 s | **contaminated** (probes + 4-way concurrency); 22 strike-check 40 s timeouts |
| C4 | 0 parse failures, 0 truncations | |

**Instrument correction (validity before significance) — the Hebrew diagnostic had a blind spot,
fixed before any bet reads it.** On hobby docs the only Hebrew is often SECTION MARKERS:
din_ezra's raw GT has 30 Hebrew characters and every one is `שאלה` / `א.`. The all-Hebrew
ratio (0.24) was measuring marker formatting, not Hebrew text. Added the PROSE view
(`diag_hebrew.strip_marker_lines`: whole marker-only lines dropped on BOTH sides; a marker
followed by prose stays; 16 pinned cases) — `hebrew_p1_prose` / `hebrew_e2e_prose` beside the
unchanged all-Hebrew numbers. **The mission's Hebrew target is read on the prose view** (an
interpretation, surfaced at Checkpoint 1). din_ezra drops out of it (no prose in GT; P1 invented
`המשך בעמ 33` → scored 0.0, but that line may be real ink — see GT questions). Baseline rep0
prose: roni 0.993 · dan(b) 0.948 · hobby-dan 0.858 · itay_kraft 0.831 · moran 0.797 ·
itay_katav 0.770 · noam 0.710 · yonatan 0.279 · omer 0.147.

The baseline predates the outputs writer; its rep0 pages were rebuilt by applying each doc
report's diff to the raw GT (scratchpad `reconstruct_rep0.py`) and **verified: all 10 rebuilt
docs re-derive the recorded rep0 `hebrew_p1` ratio exactly** before any number above was used.

**Taxonomy (§4.6, rep0, prose view): 75 word-level Hebrew differences — (b) dropped/added 59 ·
(a) letter confusion 15 · (c) order 1.** The failure is DROPPED MARGIN COMMENTS far more than
misread letters: yonatan loses `// הגדרת תכונות`, `// יצירת תחביב חדש`, and reads
`// בדיקה אם מלא` as `// יכול גם מלא //`; omer's `// סופר כמה פעמים עדכן משתנה (אם לא עדכן
נחזיר false)` comes back as `// (Pule נחזיר נכון כי מקווה שזה מספיק ברור כמה ספר` — an
invented clause, i.e. a (d)-class FC failure, not a bidi reorder. This points at H-FOCUS (Bet 4:
the comment is small, off to the right, in a second script) more than at the model.

**Runner fixes:** P1 is now scored (and saved, and flag-scored) on the PHYSICAL pages whenever
relocation ran (`run.pages_before_relocation`); P2's moved pages are saved beside them as
`pages_after_relocation`. **Bet 3 wiring landed behind `p1_instructions` (default False,
byte-identical prompt + schema — pinned):** P1 reports marks → `Pipeline.apply_relocation`
(the ONE call site for eval `run()` and production `run_with_trust`) → P2. 5 fake-provider
tests. Not run against a model yet: its gold is blocked on the validator.

**Next:** Bet 1 screen launched (4 configs × 10 × k=1, `p1_only`, strike check OFF in every
arm so the model is the only variable): incumbent control, gemini-3.8-flash, gpt-6-sol,
gemini-3.5-flash at `minimal` (its `low` truncated in the probe).

---

## 2026-09-27 — OWNER: spend envelope cut $300 → **$60** · spend ≈ $4.6 committed (recorded $1.93 + ≤$1 unrecorded probe attempts + the Bet 1 screen in flight ≈ $1.6)

Surface at 80% = **$48**. Re-planned to fit (estimates from the measured $0.048/doc e2e):
| step | scope | est. |
|---|---|---|
| Bet 1 screen (running) | 4 configs × 10 × k=1, p1_only | $1.6 |
| Bet 1 finalists | top 2, p1_only k=3 | $2 |
| effort low/medium + pages_per_call 1/3 | **winner only** (was: every finalist) | $1.5 |
| winner e2e | k=3 (baseline already at k=3) | $2 |
| Bet 2 tables | the 3 table docs × k=3 | $0.5 |
| Bet 3 arrows | 3 case docs × k=3, once the validator is clean | $0.5 |
| Bet 4 focus pass | 10 × k=3, two variants (separate vs merged into strike check) | $5 |
| Bet 5 self-consistency | only if C2 room remains after Bets 1–4 | ≤$3 |
| final e2e k=5 + `check_goal.sh` | | $8 |
| C3 latency in isolation | baseline + recommended, concurrency 1 | $2 |
| **total** | | **≈ $26**, ≈ $30 margin for reruns/surprises |
Cuts vs the $300 plan: no per-finalist effort/ppc sweep; no second prompt-adaptation round;
no challenger beyond the screen's four arms.

---

## 2026-09-27 — BET 1 screen (P1 model, `p1_only`, k=1, strike check OFF in every arm) · spend ≈ $6.3 / $60

Hypothesis/kill: pre-registered in PREDICTIONS.md (B1-*). **One variable: `p1_model_key` (+ its
lowest useful thinking setting).** All four arms RESCORED from saved outputs against the GT as of
16:10 (`rescore.py`, new): the owner changed the bagrut tick spelling `v`→`✓` in raw
(dan_basiuk, noam) mid-screen, so arms had been scored by two rulers. The rescorer reproduces the
recorded score exactly on all 8 docs whose GT did not change (validity check), and moves only
the two that did. The two gemini-flash arms first died at 6/10 on a local DNS failure
(`getaddrinfo failed`, 16:07) — the runner writes nothing until the end, so ~$0.25 was lost and
both arms were rerun whole.

| arm | P1 worst / mean | P1 gates | Hebrew PROSE worst (excl. din*) / mean | tables micro | $/doc | parse/trunc |
|---|---|---|---|---|---|---|
| control gemini-3.1-pro (low) | 0.895 / 0.953 | 1/10 | 0.279 / 0.661 | 0.911 | 0.0327 | 0/0 |
| gemini-3.8-flash (low) | 0.910 / 0.955 | 0/10 | 0.455 / 0.721 | **0.169** | 0.0217 | 0/0 |
| **gemini-3.5-flash (minimal)** | **0.929 / 0.961** | 0/10 | **0.677 / 0.755** | **0.467** | 0.0245 | 0/0 |
| gpt-6-sol (low) | 0.895 / 0.944 | 0/10 | 0.000 / 0.556 | 0.849 | 0.0430 | 0/0 |

*din_ezra has NO Hebrew prose in its GT; every arm but gpt-6-sol transcribes `המשך בעמ 33`
(real ink below a struck block — a GT question) and scores 0.0 there.

**Readings.** (1) gpt-6-sol: eliminated — Hebrew worst 0.000 (omer) / 0.119 (itay_kraft), noam
table shape 0.50; its one standout is yonatan 0.866 (margin comments), which is H-FOCUS evidence,
not a P1 case. (2) The flash tables are an ADHERENCE failure, not perception: flash breaks a line
INSIDE a header cell whose ink wraps (`if:` ↵ `(arr[i] != 1 && …)`), which splits the row and
shifts every row after it (itay_katav 6/75 cells, 4 ragged rows) — exactly Bet 2's surface.
(3) The control's tables fell 0.969 → 0.911 on the NEW GT: it writes `v` for dan's ticks (20
cells) and `✓` for noam's — one mark, two spellings, by student.

**Decision:** finalists = gemini-3.5-flash@minimal and gemini-3.8-flash → k=3. No family
prompt-adaptation pass (both Gemini, the family the prompt was tuned on). 3.5-flash has ONE
usable setting: at `low` its thinking fills `p1_max_tokens` (probe: 4.8k reasoning, MAX_TOKENS)
and lifting the cap prices ~5k thinking tokens × 2 chunks at $9/M ≈ +$0.09/doc → C2 dead.
Kill criterion (no candidate beats the incumbent's worst doc on any dimension within C2): NOT
fired — 3.5-flash beats it on P1 worst and Hebrew worst at lower cost.

---

## 2026-09-27 — BET 1 finalists k=3 (`p1_only`, rescored on the 16:10 GT) · spend ≈ $5.5 / $60

| arm (k=3) | P1 worst / mean | Hebrew PROSE worst excl. din (per-run min) | tables micro | $/doc (P1 only) | parse/trunc |
|---|---|---|---|---|---|
| **gemini-3.5-flash @ minimal** | **0.928** (itay_kraft) / 0.960 | **0.606** omer (0.567) | 0.473 | 0.0220 | 0/0 |
| gemini-3.8-flash @ low | 0.909 (dan_b) / 0.955 | 0.436 omer (0.366) | 0.169 | 0.0218 | 0/0 |
| control 3.1-pro (k=1, screen) | 0.895 (din) / 0.953 | 0.279 yonatan | 0.911 | 0.0327 | 0/0 |

**Decision: Bet 1 winner = gemini-3.5-flash @ `minimal`.** Beats the incumbent's worst doc on P1
ratio (+0.033) and Hebrew prose (+0.33) at −33% P1 cost; C4 clean. **Cross-exam:** Hebrew prose
mean bagrut 0.921 / hobby 0.580 (control k=1: 0.853 / 0.470) — improves BOTH exams, but NOT every
doc: **bagrut dan_basiuk regresses 0.961 → 0.883** and hobby dan_basiuk 0.814 → 0.743 — carried
to Checkpoint 2 as a labelled regression, not averaged away. Tables: both flash arms lose shape
by splitting wrapped header cells — Bet 2's variable. C3 in this window (p50 69 s, p95 271 s) is
p1_only under 2-arm contention: NOT a C3 measurement.

Also this entry: Bet 2 built as a FLAG (`p1_table_rows`, `prompts.P1_TABLE_ROWS_RULE`), not a
P1_SYSTEM edit — the first attempt edited the prompt in place and tripped
`tests/subjects/test_prompt_identity.py`, whose rule is "a mismatch is a STOP, never a re-pin"
(measured CS numbers ride on those bytes). Reverted; production P1 stays byte-identical until the
owner rules the ship. Focus pass (Bet 4) built: `two_phase/focus.py` (pure: numbering, target
parsing, crop geometry, the skeleton-guarded splice — 18 cases) + `Pipeline._focus_pages`
(optional pass, strike-check shape and belt; 5 fake-provider wiring tests); runner saves every
reader verdict under `outputs/*.json → focus`. Runner doc-retry waits 30/60/90 s (the DNS outage).

---

## 2026-09-27 — BET 2 table adherence (winner + `p1_table_rows`, 3 table docs, k=3) · spend ≈ $5.8 / $60 (+ Bet 4 in flight ≈ $1.5)

Pre-registered (PREDICTIONS B2-*). One variable: the P1 table-row sentence pair (row = one line;
`✓`/`x`), behind a flag. Rescored on the 16:10 GT.

| doc | winner k=3 shape / cells | + Bet 2 shape / cells |
|---|---|---|
| dan_basiuk | 0.50 / 0.759 | 0.50 / 0.989 |
| itay_katav | 0.00 / 0.080 | 0.00 / 0.080 |
| noam | 0.50 / 0.533 | **1.00 / 1.000** |
| micro | 0.473 | 0.689 |

**B2-1 FALSE → the mission's kill FIRED** (shape < 100% after one revision). itay_katav: flash
STILL breaks the wrapped header cell across two lines on 3/3 repeats — the sentence aimed at that
exact defect did not take. B2-2 false (0.689). **B2-3 false on Hebrew:** noam prose 0.877 → 0.843
(outside the ±0.01 prediction) — possibly the stochastic p7 reversal, not established; reported.

**Offline evidence for a zero-cost alternative (no API spend — the same saved outputs, a pure
function, rescored):** `two_phase/table_rows.join_split_rows` re-joins a row the model broke
across lines (opens `| `, closed by a later ` |` within 3 lines, never on `||`; format only, one
space, no ink character touched — 6 pinned cases).
| outputs | shape before → after join | cells before → after |
|---|---|---|
| Bet 2 (3 docs × k=3) | 9/18 → 13/18 | 0.689 → **0.966** |
| winner k=3 (no Bet 2) | 4/12 → 6/12 | 0.476 → 0.756 |
| incumbent 3.1-pro | 6/6 → 6/6 | 0.911 → 0.911 (**no-op — no false joins**) |
Built behind `p1_join_split_table_rows` (default OFF) and SURFACED, not adopted: it is not the
mission's prescribed next step (Bet 4 crops). The 5 remaining shape misses are table-EDGE
ambiguities, not perception: dan's boxed `74` under a tick (GT spells the box `[74]` — an
undocumented notation using gated structural tokens; the model writes `74` as its own row), and
itay_katav's sub-question marker «ב) 1)» absorbed as a 6th header column (2/3 repeats).

---

## 2026-09-27 — BET 4 focus pass (winner + localize/crop/read/splice, `p1_only`, 10 × k=3) · spend ≈ $8.2 / $60 (recorded $6.90 + ≤$1.25 unrecorded)

Pre-registered (PREDICTIONS B4-*). One variable: `p1_focus_localizer_model_key` =
gemini-3.5-flash (reader = same, `minimal`). Rescored with the winner's k=3 on the post-fix GT.

| doc (Hebrew PROSE, k=3 mean) | winner | + focus |
|---|---|---|
| omer (worst) | 0.606 | **0.570** |
| yonatan | 0.760 | **0.692** |
| moran | 0.793 | 0.763 |
| itay_kraft | 0.815 | 0.806 |
| roni / noam / hobby dan | 0.978 / 0.887 / 0.743 | 0.989 / 0.908 / 0.787 |
| **$/doc (P1 only)** | 0.022 | **0.085** (roni 0.147) |

**Kill FIRED on both clauses.** Worst doc got WORSE (B4-1 false), and the reader introduced
Hebrew the student did not write — accepted splices on yonatan: `// בנאי` → «העולם בנאי ל»,
«יצירת עצם חדש» → «יצירת מצביע חדש», and `//` moved to the line END (a visual-order flip). The
skeleton guard held on code (131 refusals, 195 applied, 239 unchanged, 28 no_hebrew over 30
docs) — but it cannot judge whether HEBREW is right, and that is exactly where this reader fails.
B4-4 false: +$0.063/doc against a predicted +$0.01–0.03 (a Hebrew-dense doc is ~30 line reads).
**C2 fails at P1 alone**, so no reader/localizer tuning of this shape fits: even a perfect reader
would have to cost ≤ $0.03/doc on the densest doc. **4b (fold into the strike check) not run
yet:** same model, same page resolution as P1 — the arm H-FOCUS predicts cannot help; held for
the owner rather than spent by default.

## 2026-09-27 — OWNER-ORDERED GT FIX (Checkpoint 1 errors, confirmed) + its P2 re-check

Owner confirmed every suspected GT error except: din p1 reads «המשך צד שני»; dan `✓ [74]` is
correct (a boxed final answer); ticks already `✓` in both corpora. Applied (scratchpad
`gt_fix.py` / `gt_fix2.py` / `gt_fix3.py`, every edit asserting the reviewed line content first):
- **Bagrut RAW (§3.3)**: every question number → `שאלה N`, every letter → `א.`, each on its own
  line BEFORE the content (markers written at a code line's end moved off it); header words
  kept with the number (`שאלה 6 המשך 2`); part numbers `(1)`/`2)` verbatim WHERE WRITTEN.
  (A first pass also split part numbers onto their own line: a bare `2)` line made P2 drop noam
  Q1.א's sentence — reverted, and the rule is now written down.)
- **Bagrut DRAFT (§4.3)**: all markers removed in every position (whole lines, code-line
  tails, prose prefixes — itay_kraft's draft had them too, not only the three reported), and
  noam's standalone navigation notes («המשך עמוד קודם», «סעיף ב בצד שני», …).
- omer Q1.ב draft ← raw's reading; noam p6 raw + «תתעלמו מהריווח»; din p1 raw + «המשך צד שני».
- `TRANSCRIPTION_GT_CONVENTIONS.md`: §3.3 marker placement/part numbers/navigation notes, §5.2a
  rule 5 (`✓`/`x`, boxed value `[74]`, its token cost and the `[?]` collision).
- `check_gt_consistency.py`: raw-side exemptions widened to the conventions (continuation
  headers, part numbers, «המשך…» notes) — raw-side only, so an over-broad pattern surfaces as
  ADDED instead of hiding a draft defect. Clean on all 10 fixtures.

**P2-only (prod, k=3) after the fix — bagrut 2/5 → 4/5 docs passing every repeat**; hobby 5/5
unchanged. noam 0/3: two P2 behaviours, not GT — Q1.א's explanation sentence dropped (2/3) and a
trailing `}` dropped from Q2.ב/Q3.ב. Recorded for the P2 surface (§17.8 governs any P2 change).

---

## 2026-09-27 — OWNER-AUTHORIZED arrow-case fix (§3.4 now VALID) + winner e2e k=3 · spend ≈ $10 / $60

**Arrow-case GT fix** (owner: "authorized … extremely surgical and conservative"; scratchpad
`gt_fix4.py` / `cases_fix.py`, every edit asserting the reviewed content first):
- itay_kraft raw p5: both boxes back to PHYSICAL placement (they had been pre-applied at their
  arrow targets). New written rule (conventions §3.2): a margin box goes, as one block, right
  after the main-column line level with its first written line — box 1 after the for-body `{`,
  box 2 after `num++;` (checked on the scan). Draft unchanged (already intended placement).
- itay_katav raw p3: the boxed note back above the method, WITHOUT the invented `//` (OD-A3);
  draft: ` ⟦note⟧` on the allocation line, the starred zeroing loop moved to its `*`, the
  continuation note «שכחתי לאפס: *» dropped (mission §3.1: continuation notes are non-answer).
- yonatan raw p1: the circled fragment added where written (start of the if-line); draft: the
  fragment inside the condition before its `)`, as the case's own note says.
- `insertion_cases.json`: itay_katav#01 text `מאופס`→`אפס` (ink + both GTs); yonatan#01 anchors
  at the paren its note names; **added itay_katav#02** (asterisk) and **itay_kraft#02** (arrow).
- **Validator change (mine, surfaced):** §3.4's LOCAL insertion check does not compose with an
  attachment ending the same line (itay_katav: `…count]; ⟦note⟧` then the inserted loop) —
  insertion conformance now strips `⟦…⟧` from the draft first (attachments are orthogonal).
- `check_gt_consistency.py` now compares the draft against the raw WITH the gold cases applied
  (OD-A1); unrelocated, every moved block read as DROPPED+ADDED. Clean on all 10.
- **Validator: VALID, 5/5.** Pinned: `test_insertion_cases_valid.py`. Bet 3 unblocked.
- Surfaced, NOT applied: noam p2's framed «מוחזר - 76» — under the new `[X]` rule its GT would
  read `[מוחזר - 76]`; the owner's call.

**`[X]` in the P1 prompt:** `p1_boxed_values` flag → `prompts.P1_BOXED_VALUES_RULE`, scoped to a
framed SHORT RESULT (these scans also frame code blocks that arrows relocate). P1_SYSTEM untouched.

**Winner e2e** (`w1_flash35_e2e` = prod + P1 gemini-3.5-flash@minimal, strike check ON), k=3,
**concurrency 1**, rescored on the post-fix GT:
| | baseline prod (k=3, contaminated latency) | winner |
|---|---|---|
| E2E worst doc | noam 0.905 (old GT) | hobby dan 0.938 |
| P1 worst doc | din 0.894 | hobby dan 0.932 |
| **C3 wall** | p50 311 s · p95 458 s | **p50 32 s · p95 48 s** |
| C2 | $0.048 | $0.055 |
| C4 | 0 / 0 | 0 / 0 |
E2E gate: roni 1/3; everything else 0/3. One Vertex 429 on the strike check (noam p6, degraded
as designed): **P1 and the strike check are now the same model on one quota** — a production
item for Checkpoint 2. The baseline's E2E/Hebrew are on the pre-fix GT; a re-baseline on the
fixed GT is owed before the Checkpoint 2 before/after table.

---

## 2026-09-27 — BET 2b row-join (owner-adopted) + boxed values `[X]` (`p1_only`, k=3) · spend ≈ $10.5 / $60

**Bet 2b** (`s2b_row_join` = winner + `p1_table_rows` + `p1_join_split_table_rows`; one variable
over Bet 2: the join). 3 table docs × k=3, rescored on the current GT.
| doc | Bet 2 shape / cells | **Bet 2b** shape / cells |
|---|---|---|
| dan | 0.50 / 0.989 | 0.50 / 0.989 |
| itay_katav | 0.00 / 0.080 | **0.83 / 0.916** (P1 gate 3/3 — its first) |
| noam | 1.00 / 1.000 | 1.00 / 1.000 |
| micro | 0.689 | **0.967** (offline replay predicted 0.966) |
B2b-1 ✓ (0.967 ≥ 0.95). B2b-2 ✓ — misses are the two table-edge cases only. Tables target
(micro ≥ 0.97, worst ≥ 0.95, shape 100%) NOT met: dan shape 0.50 (the boxed 74 row), itay_katav
0.916 (absorbed «ב) 1)» column, 1/3 reps).

**Boxed values** (`sx_boxed` = Bet 2b + `p1_boxed_values`). dan + noam × k=3.
- BX-1 partial: dan table shape 0.50 → **1.00** (3/3) — the `74` no longer becomes its own row;
  the model writes `[74]` on a line UNDER the table instead of inside the cell (cell `✓` vs GT
  `✓ [74]`: 1 miss/rep). dan Hebrew prose 0.894 → 0.933.
- BX-2 ✓ as predicted: noam p2's framed result comes back bracketed, `[מותר - 76]` (also a
  misread of «מוחזר»). No spurious brackets anywhere (code `[]` unaffected).
- **UNPREDICTED:** noam p2 table, 3 cells misread IDENTICALLY on 3/3 repeats (40→10, 67→37,
  76→46) that Bet 2b read correctly — a temp-0 prompt perturbation of digit perception, not
  noise at this k. dan+noam cells micro 0.993 → 0.973.
Verdict: mixed — kept as a flag, reported to the owner with the evidence; not in the recommended
config unless the owner prefers dan's shape fix over noam's digits.

---

## 2026-09-27 — BET 3 arrow instructions (winner e2e + `p1_instructions`, 10 × k=3 `per_doc`) · spend ≈ $12.6 / $60

Pre-registered (PREDICTIONS B3-*). Arrow metric read from the RUN-TIME records (the first
rescore dropped them — `rescore.py` passed no relocations and printed 0 placed / 0 false; fixed:
the arrow block is now carried verbatim). Runner now saves P1's reported instructions
(`outputs/*.json → instructions`; `PipelineRun.p1_instructions`, both paths; never a draft field).

| | k=3 run | diagnostic repeat (4th) |
|---|---|---|
| placed | **6/15** — itay_katav#01 (attachment) + itay_kraft#02 (bottom box), 3/3 each | itay_kraft#02 only |
| false relocations | **0** over 30 document-runs | **1** — itay_katav's boxed note reported as an INSERTION and spliced into the code between the allocation and `count = 0;` |
| refused (safe) | yonatan 3/3: P1's anchors do not occur in its own text | yonatan, itay_katav#02 |

What P1 reported for the misses (the diagnostic repeat):
- **yonatan#01:** P1 reports a DIFFERENT move — `&& (answer != 'N' … && answer != 'n')` into the
  `for` condition before `; i++)` — reading the for-condition's wrapped continuation as moved
  text (listed under "NOT instructions": a connector to text already in reading order). The
  circled `||` fragment is never reported. Refused by the function (anchors absent): no harm.
- **itay_katav#02:** P1 pairs the foot «שכחתי לאפס: *» with the LONE `*` above
  `public static` (which the raw GT does not carry — ink missing from the GT, surfaced) and
  targets the gap before the method — a loop outside any method. Refused (anchors absent).
- **itay_kraft#01:** the top box is never reported.
Other effects: P1 ratio moved −0.02 on itay_katav and −0.014 on moran (B3-3 ±0.01 false); C2
$0.058 PASS; C3 at concurrency 3 p50 57 s / p95 90 s PASS; C4 clean.
**Kill clause engaged** (a false relocation) → ONE prompt revision (r1, pre-registered):
the kind is decided by what the text IS; unsure → attachment. Running now.

**Bet 3 r1 result** (10 × k=3 + itay_katav × 3 = 33 document-runs): **0 false relocations (B3r-1 ✓)**;
placement **9/21** case-repeats (itay_katav#01 5/6, itay_kraft#02 3/3, itay_kraft#01 1/3 — new;
yonatan#01 0/3, itay_katav#02 0/6) — B3r-2 ✓. One mis-anchored report refused safely.
Arrow iteration STOPS here: the remaining misses are ink-interpretation disagreements between
P1 and the cases (yonatan's target; which `*` the foot note pairs with) that belong to the
owner, and another revision would buy placement at the risk the mission ranks worst.

## 2026-09-27 — BET 5 (targeted self-consistency) — NOT RUN, by the falsification record

The mission gates Bet 5 on a justification against `flagging.py`'s record. The record rules it
out as specified: (1) same-model self-consistency resampling flagged **12.7%** of critical
errors on the golden set — it shares the model's prior, the exact blind spot; (2) the
cross-family alternative (diverse readers, 92% coverage) was RETIRED in production on 2026-08-07
because on real docs its flags were ~100% false — the click-through failure INV-6 warns about;
(3) Bet 4 just showed the failure mode on this corpus: a second read of a Hebrew line at crop
scale INVENTED Hebrew («העולם בנאי ל») rather than disagreeing usefully. A two-read disagreement
flag would re-open a surface the owner closed, with no new evidence that it has changed. Budget
is not the reason (≈ $15 of $60 spent); evidence is.

---

## 2026-09-27 — `check_goal.sh` on the RECOMMENDED config (`rec`) · k=5 · **EXIT 1 (GOAL: FAIL)** · spend ≈ $19 / $60

`rec` = prod + P1 gemini-3.5-flash@minimal + `p1_table_rows` + `p1_join_split_table_rows` +
`p1_instructions` (r1). Boxed values OFF (mixed — owner's call). `GOAL_CONFIG=rec bash
tests/transcription_eval_suit/check_goal.sh` → results/20260927_193414_rec, verbatim verdict
`VERDICT: GOAL: FAIL`. Only roni passes (3/5 repeats). Validity clean (0 parse, 0 truncation).
Dominant blockers are PERCEPTION critical-token misses (method_call / structural / operator
recall) on hobby docs — e.g. din `abbreviations_altered: ('CR',)` 5/5, yonatan method_call
0.861 5/5 — the dimension this mission did not target and that no bet moved.

| dimension (k=5) | worst doc | notes |
|---|---|---|
| E2E ratio | hobby dan 0.940 | |
| P1 ratio | hobby dan 0.933 | |
| Hebrew PROSE P1 | omer 0.471 (din 0.316: its GT prose is 1 note P1 misreads) | |
| Tables | itay_katav cells 0.819 · micro 0.935 · shape dan 0.50 / katav 0.80 / noam 1.00 | |
| Arrows | **12/25 placed · 0 false** | |
| C2 | $0.0605 avg PASS — noam $0.104 alone (over the line) | |
| C3 | p50 38 s · p95 118 s PASS (concurrency 1) | |
| C4 | 0 / 0 | |

---

## 2026-09-27 — RE-BASELINE prod on the FIXED GT (k=3, concurrency 3) + CHECKPOINT 2 · spend $18.40 recorded (+ ≤$1.25 unrecorded) / $60

**The morning baseline (15:38) is INVALID for C2 and understated for accuracy — superseded.**
Under my own parallel probes its strike check mostly timed out: 1–2 of 8 calls recorded per doc
(now 8/8), so its cost was understated and struck ink leaked (itay_katav p1). Re-baseline
(results/20260927_194738_prod) — and a second finding: the incumbent 3.1-pro P1 at `low` spent
**14.4k thinking tokens on noam** ($0.21/doc, 0 this morning) — a stochastic thinking-cost tail;
the winner at `minimal` spends 0.

| (same GT) | prod re-baseline k=3 | **rec** k=5 (`check_goal`) |
|---|---|---|
| E2E worst doc | noam 0.926 | hobby dan **0.940** |
| P1 worst doc | noam 0.924 | hobby dan **0.933** |
| Hebrew prose worst (excl. din) | yonatan 0.290 (per-run min omer 0.147) | omer **0.471** |
| Tables micro / worst / shape | 0.911 / dan 0.778 / 100% all | **0.935** / katav 0.819 / **dan 50%, katav 80%** ⚠ |
| Arrows | 0/15 | **12/25, 0 false** |
| C2 | **$0.087 FAIL** (noam 0.269) | **$0.0605 PASS** (noam 0.104) |
| C3 | p50 57 s / p95 139 s (conc 3) | p50 38 s / p95 118 s (conc 1) |
| E2E gate (all repeats) | 0 docs (roni 2/3) | 0 docs (roni 3/5) — `check_goal` EXIT 1 |
**Regressions, labeled:** table SHAPE (100% → dan 50% / itay_katav 80%; itay_katav P1 gate 3/3 →
0/5 — a C1 concern); Hebrew prose on bagrut dan 0.954→0.898, roni 0.988→0.965, hobby dan
0.846→0.736, moran 0.797→0.777; E2E ratio roni −0.009, hobby dan −0.011, moran −0.009.
Cross-exam: Hebrew prose mean bagrut 0.874→0.906, hobby 0.528→0.600 (both exams up, NOT every
doc); E2E mean bagrut 0.960→0.970, hobby 0.973→0.970 (hobby flat-to-down).

---

## 2026-09-28 — ROUND 2 (owner approved recs 1–5; envelope +$10 → cap $28.30) · spend $18.40 recorded at start

**Built (all default OFF, tests green):** `p1_strike_check_reasoning_effort` (#2);
`p1_table_reread_model_key` + `table_rows.table_blocks/replace_tables` — a page whose P1 text
holds a table is re-read by the table model and ONLY its grid blocks are swapped in, refused on a
table-count mismatch; split rows count as part of their block (#1); `p1_focus_only_missing` +
`p1_focus_reader_reasoning_effort` — the focus pass re-reads only lines where P1 wrote NO
Hebrew, with a separate reader (#5).

**#4 — where the gate's critical-token misses come from** (`code_taxonomy.py`, new, read-only;
the suite's own extractor and profile; rec k=5, 343 misses):
| kind | lost in P1 (perception) | P1 had it, answers do not |
|---|---|---|
| structural `( ) { } [ ] ;` | 125 | 64 |
| method names | 13 | 73 |
| operators | 55 | 8 |
| abbreviation `CR` | 0 | 5 |
The "answers lost it" bucket is NOT all P2: din's 5×(`CR`, `show`, `pupulathobbies`) come from
the strike check failing to delete din p1's crossed-out block (the documented model-level
limitation, 2026-07-10) — P1's text then carries a struck `populateHobbies` and P2 picks it for
Q1.ב over the real one on p2. yonatan's `||`/`==` (10×) are the arrowed fragment (Bet 3's
miss), hobby dan's `( )` 15× and omer's `getArrShows` 10× are the next reads. Conclusions: (a) the
strike check carries real accuracy — #2 must be measured on struck-ink docs, not assumed free;
(b) the biggest perception bucket is brackets, which #3a (one page per call) is the cheapest
lever on.

---

## 2026-09-28 — Round 2 CLEAN reruns, pair 1 (two processes, concurrency 1) · cap raised to $34.30 (owner)

**Why reruns:** the first round-2 attempt ran four arms at once from one laptop; the local uplink
+ resolver failed (timeouts and DNS on EVERY vendor), and the strike check silently dropped on
26/30 (R2) and 21/30 (R3a) records — those runs measured nothing and are VOID ($7.78, my
error). R1's first run was also void: the runner built adapters only for P1/P2/strike/readers,
so the table model raised a KeyError that the pass's fail-safe swallowed — fixed in the runner
AND in `two_phase_engine._shared_infra` (production had the same latent gap).
**New validity line:** `mission_report` now prints strike-check coverage (records whose strike
check ran on every nonempty page). The `rec` k=5 control is itself 43/50 — the real 429/504
rate — so arms are compared on complete records too.

**R1 table re-read (gemini-3.1-pro, 3 table docs × k=3, 9/9 complete): KILLED.** Swap applied on
9 pages, refused on 3 (table-count mismatch). Shape NOT restored (dan 0.50, itay_katav 0.50);
cells 0.893 (< rec 0.935); +$0.035/doc on table docs. The residual shape misses are not grid
drawing: (a) dan's boxed `74` — the incumbent ALSO writes it as its own row; (b) **suspected GT
error, itay_katav p1 table 2:** the ink's Sum column starts with a lone `0` above the `8` row
(crop `katav_t2.png`); BOTH models read that row on every repeat (10 rows), the GT shifts the
whole Sum column up one row (9 rows) — ~22 cells + the shape on every model. Production's
incumbent matched the GT, which suggests the GT was seeded from its output. SURFACED.

**R2 strike check `minimal` (10 × k=3, 23/30 complete): KEEP.** On complete records the
strike check costs **$0.0377 → $0.0184/doc** (0 thinking tokens vs 550–5,500); P1 ratio equal or
better on 8/10 docs, struck-ink docs din +0.004 / itay_katav +0.004; itay_kraft −0.006, noam
−0.001. Kill (a struck block leaking ≥2/3) not fired. Thin: 1–3 complete records per doc.

## 2026-09-28 — Round 2 clean reruns, pair 2 + R3b (two processes / one, concurrency 1)

**R3a one page per call (10 × k=3, 26/30 complete): KILLED.** C4 broke (3 parse failures, 3
truncations); Hebrew prose worse (moran 0.78→0.54, bagrut dan 0.90→0.83); tables 0.846;
$0.076/doc (noam $0.143).
**R5 narrow Hebrew re-read (localizer flash@minimal, reader 3.1-pro@low, only lines with NO
Hebrew in P1; 10 × k=3, 26/30 complete): SAFE, NOT ADOPTED.** 68 lines read, 18 spliced, **18/18
faithful to the ink** (16 match the GT word-for-word; the other 2 are real ink the GT lacks —
hobby dan p3 «הדפסת ממוצעים», yonatan p1 «פעולה בונה» beside `public Hobby(` — SURFACED as GT
omissions). One added `//` the student did not write (hobby dan p3). Gains: bagrut dan +0.04,
hobby dan +0.03, moran +0.02, roni +0.02; worst doc omer UNCHANGED 0.471 (its error is a
hallucinated clause on a line P1 DID write Hebrew on — out of this pass's reach by design).
Cost **+$0.043/doc** (predicted ≤ +$0.03) → C2 fails ($0.0875). Behind its flag.
**R3b P1 thinking `low` (5 docs × k=1, 4/5 complete): NO CHANGE.** 3.5-flash chose 0 thinking
tokens on 4/5 docs (yonatan 2.7k) — `low` ≈ `minimal` here; P1/Hebrew mixed within noise (omer
+0.10, itay_katav −0.09). Keep `minimal`.

**Round 2 outcome:** one keeper — **R2 (strike check `minimal`)**, −$0.019/doc, no accuracy
loss. `configs/rec2.json` = rec + R2. #4 delivered as `code_taxonomy.py` + its finding (P1
bracket/operator misses, and din's struck block masquerading as a P2 loss). R1, R3a killed; R5
safe but over cost; R3b no effect. New suspected GT errors: itay_katav p1 table 2 (Sum column
shifted one row), hobby dan p3 and yonatan p1 missing Hebrew notes.

---

## 2026-09-30 — OWNER-ORDERED GT fix (the three round-2 findings) · no API spend

Applied surgically (scratchpad `gt_fix5.py`: every edit asserts the exact reviewed lines, all
pre-flighted before any write), identical in raw and draft:
1. **itay_katav p1 table 2** — Sum column back to the ink: a lone starting `0` row, each sum on
   the row it was written on (8, 13, 17, 17, 20, 20, 20, 22); the circled final answer → `[22]`
   (owner: a circled final answer is a box). Both models had read this on every repeat.
2. **hobby dan_basiuk p3** — three `//` margin comments restored: `// מציאת ממוצעים:`,
   `// int * double = double` (owner: the student's `◦` means multiplication → `*`),
   `// הדפסת ממוצעים:`.
3. **yonatan p1** — `// פעולה בונה` beside `public Hobby(…)`, in the file's trailing style.
Conventions: §5.2a rule 5 (a circled final answer is a box); multiplication-as-`◦` → `*`.
The boxed-values prompt variant now says "BOXED or CIRCLED". Checks: 337 tests pass;
`check_gt_consistency` clean on 10/10; `insertion_cases` VALID.
**Note for the next reader:** every round-1/round-2 number on these three documents was scored
on the old GT — rescore saved outputs (`rescore.py`) before comparing.

---

## 2026-09-30 — PRODUCTION PIN = rec2 (in code; NOT committed, NOT deployed) + final trial k=2 · spend $34.27 / $34.30

**Pin (owner):** `two_phase_engine.PROD_CONFIG` now equals `configs/rec2.json` on every set field —
P1 gemini-3.5-flash@minimal, `p1_table_rows`, `p1_join_split_table_rows`, `p1_instructions`,
strike check @minimal. Engine version `two_phase/v5_p1-flash35`. Prompt-version stamp now names
every prompt variant that is on (`pipeline._prompt_base`: `t1.4-tables+rows+instr-r1`; all off =
unchanged, pinned by a test). `configs/prod.json` regenerated from the pin (old one kept as
`prod_2026-09-27.json`). 338 suite + 110 related service tests pass; `import app.main` ok.

**Final trial** (`prod` = the pin, per_doc, k=2, concurrency 1) → results/20260930_175749_prod.
All three runs compared on the CURRENT answer key (old prod + rec rescored):
| | old prod (3.1-pro) k=3 | rec k=5 | **pin trial k=2** |
|---|---|---|---|
| E2E worst / mean | 0.926 / 0.967 | 0.948 / 0.971 | **0.946 / 0.969** |
| P1 worst / mean | 0.924 / 0.968 | 0.941 / 0.966 | 0.938 / 0.966 |
| Hebrew prose worst (excl. din) / mean | 0.278 / 0.744 | 0.471 / 0.801 | 0.471 / 0.791 |
| Table cells | 0.796 | 0.909 | **0.922** |
| Arrows placed (false) | 0/15 (0) | 12/25 (0) | **6/10 (0)** |
| Gate: docs passing every run | 0 | 0 | **1 (roni 2/2)** |
| $/doc | 0.087 | 0.061 | **0.042** |
**Vertex degraded during the trial** (single process, so not the laptop): strike-check coverage
9/20; P1 calls hung to the 240 s ceiling and returned 504 (yonatan rep2 took 2,164 s with the
runner's doc re-run; omer rep2 1,269 s); wall p50 129 s / p95 516 s vs 38 s / 118 s for the same
setup on 09-27. Code-miss breakdown (142): structural 50 + operators 20 lost in P1; method names
34 + structural 26 "after P1" (incl. din's struck block). Table misses: boxed/circled answers
(`[74]`, `[22]` — boxed-values flag is OFF), itay_katav's header label / first row, one digit.

---

## 2026-09-30 — Round 3 (owner-approved: sturdier Gemini calls · code-symbol mission, P2 first · boxed answers) · envelope +$10 → cap $44.27

**#1 Sturdier Gemini calls (code, no spend).** `scheduler.py` property 3 is now KIND-AWARE, still one
layer: a 429 (fast, free, shared-pool busy) gets up to 4 attempts with exponential backoff + jitter
(~1–1.5 s, 2–3 s, 4–6 s, cap 20 s); a SLOW failure (timeout / 504) keeps exactly one retry (each
costs a whole deadline and the doc budget is built on that count) but after a WIDE jittered wait
(2–5 s) so a burst of simultaneous page failures no longer retries in lockstep (noam 09-30: four
strike 504s in one second; production: 3/21 such retries succeeded at the old ~1.2 s). The strike
check has its own deadline 60 s (was the shared 40 s) and belt 130 s, pinned ≥ 2×deadline + widest
wait. Tests: 4 new scheduler cases; identity/cancellation/budget suites unchanged-green.
Aside: `test_two_phase_engine::test_shared_infra_is_one_scheduler_per_loop` fails when run on its
own (no API keys in the process env) — pre-existing, verified on HEAD, order-dependent.

**#2 Code symbols — WHO loses them** (`code_attribution.py`, new, read-only). Line-level: P2 answers
are P1 lines verbatim (spans contract), so a miss is P2 ONLY when the P1 line matching the gold line
HAS the symbol and is absent from the answer (a pair of wrapped lines counts; a line owned by another
answer whose own gold holds it is that answer's). **Validated: exact agreement with the scorer's own
miss lists on all 70 records** (pin trial k=2 + rec k=5, rescored). Two earlier versions were wrong
and are recorded so nobody rebuilds them: region counting over-credited P2 (dan Q3.ב's
`DiceStatistics[arr]`→`(arr)` is a READING error), and omer's `if(hobbies[i] != null)` exists in
BOTH Q1.ב and Q1.ג — P1 read one copy.
| | misses | share |
|---|---|---|
| **P1 reading** | **467** | **94%** |
| P2 splitting | 28 | 6% — 3 sites |
P2 sites: noam Q1.א's prose explanation «מטרת הפעולה check…» routed to 1.ב or dropped (6/7 runs);
itay_katav Q4.ב's starred zeroing loop, orphaned at the page foot when the arrow is not applied
(3/7); bagrut dan Q2.ב's signature line under its `ב.` marker (1/7). Notable READING classes: the
model "corrects" the student — `pupulatHobbies`→`populateHobbies`, `Tv Show(`→`TvShow(`,
`DiceStatistics[arr]`→`(arr)` — i.e. FC normalizations, the biggest single lever left.

**P2 fix 1 — section adoption (deterministic, `spans.adopt_orphans`, flag): KILLED.** Paired replay
(`p2_replay.py`: P2 alone on the pin trial's saved P1 text, each output scored with and without the
rule — same model output, so the difference is the rule): P2 misses noam 12→12, itay_katav 19→19;
ratio DOWN where it fired (noam 0.948→0.929, hobby dan 0.949→0.931, bagrut dan 0.963→0.958); 0 gate
regressions; $0.13. Why: the lines P2 genuinely loses are MISROUTED (claimed by the wrong answer),
which adoption never moves by design; what P2 leaves unclaimed is mostly correctly-excluded ink (lone
part numbers, «המשך…» notes). **P2 fix 2 (running): a marker TIE-BREAKER** in the P2 prompt (flag
`p2_marker_tiebreak`; P2_SPAN_SYSTEM is sha-pinned): content stays the sole authority on any
conflict; the student's marker decides ONLY when content fits two targets equally (noam's sentence
fits 1.א `Check` and 1.ב `What`, which calls `Check`). §17.8 kill: any new boundary failure on a
previously-working doc.

**P2 fix 2 — marker TIE-BREAKER (`p2_marker_tiebreak`): KEEP.** Replay on the pin trial's saved P1
text (same inputs, 60 P2 calls per arm, $0.13 each; `p2_replay.py --compare prod p2tb`):
P2 splitting misses **31 → 18 (−42%)** — noam 12→6, itay_katav 19→12; ratio noam 0.948→0.960,
itay_katav 0.969→0.971; every other document identical, no document worse on any measure →
§17.8 kill NOT fired. Flips no gate (P1 reading dominates those docs). Section adoption code
REMOVED (killed rule; `SliceResult.owned` + `trace.p2_owned` kept for future replays).

**#3 Boxed / circled final answers — prompt iteration** (`p1_boxed_rule`, `boxed_check.py` new:
per-page number-sequence alignment vs the answer key + bracket accounting; the fair test is an
error in ≥2 of 4 variant runs and 0 of 4 control runs, because P1 is not deterministic):
| phrasing | systematic NEW number errors | brackets correct / spurious | other |
|---|---|---|---|
| v1 (original) | noam p2 table 40→10, 67→37, 76→46 (3/3, 09-27) | — | FAILS |
| **v2** (owner's wording: only when CERTAIN a single number is framed/circled as the final answer; "never changes how you read") | **0 digit changes** (one loop-structure variant on noam p4 in 2/4, not a digit; inconclusive at n=4) | **5/8** / noam's framed «מוחזר - 76» bracketed as `[76] - מוחזר` 4/4 (word order REVERSED) | mean number errors 4.7 vs control 5.6 |
| v3 (v2 + frame must hold nothing but the number) | dan p1 «לא 0» → «ללא 1» + an invented `3`, 2/2 runs | 2/4 / 0 | dan's boxed 74 LOST 2/2 → FAILS |
**Choice: v2.** Lesson recorded: at temperature 0 ANY added sentence can shift unrelated readings
(v1, v3) — a phrasing is only trusted after the all-10-document check (running: rec3).
**Harness:** `runner --isolate-failures` (OFF by default so check_goal keeps crash semantics):
tonight a single document that exhausted 4 attempts on Vertex 504s killed a whole run (bx_v3a).

**Final confirmation (running): `rec3` = pin + p2_marker_tiebreak + boxed v2**, per_doc k=2, all
10, concurrency 1, isolated failures. Note: `configs/prod.json` had been generated BEFORE the
strike deadline fields existed — a first launch would have tested the old 40 s; caught, stopped,
regenerated. Spend: $35.33 + rec3 (~$1) of cap $44.27.

## 2026-10-03 — round 3 confirmed and PINNED (code only; not committed, not deployed)

**Confirmation run** `results/20261003_001409_rec3` (rec3 = rec2 pin + `p2_marker_tiebreak` + boxed
v2, with the round-3 sturdier calls), per_doc k=2, all 10, vs the pin trial
`results/20260930_175749_prod` (same k, same answer key):
| | pin trial | rec3 |
|---|---|---|
| end-to-end ratio, worst doc | 0.946 | 0.950 (hobby dan) |
| end-to-end ratio, mean | 0.969 | 0.971 |
| gate passes (runs) | 2/20 | 1/20 (roni only, both arms) |
| code symbols lost by P2 splitting | 8 | **2** (noam Q1.א only) |
| code symbols lost by P1 reading | 134 | 132 |
| table cells exact | 0.922 | 0.911 |
| strike-check coverage | — | 20/20 |
| $/doc | 0.042 | 0.047 |
| latency p50 / p95 | 129 s / 516 s | **63 s / 204 s** |
Attribution validated against the scorer: exact agreement on all 40 records. Boxed check
(`boxed_check --control=<pin trial>`): number errors 77 → 82 over 20 records, every new one a
single-run event except bagrut dan p3's added marker «2» (2/2, a section marker, not a changed
digit); noam p2's extra «1» is the control's own error class (control 2×, rec3 1×). Brackets:
dan's boxed 74 **2/2**, itay_katav's circled 22 **0/2**, noam's framed «מוחזר - 76» bracketed with
its word order reversed `[76] - מוחזר` **2/2** (counted spurious: the key has no brackets there —
owner ruling open). Arrows 6/10 → 4/10 and Hebrew-prose worst (omer 0.471 → 0.379, a different
hallucination per run) move inside k=2 noise; din's Hebrew-prose 0.32 is identical in both arms
(its one Hebrew line). Latency: part of the p95 drop is the round-3 retry/strike change, part is
whatever Vertex's shared pool was doing that evening — not separable at k=2.

**Pinned** (`two_phase_engine.PROD_CONFIG`, engine `two_phase/v6_boxed-p2tie`, prompt stamp
`t1.4-tables+rows+boxed+instr-r1+p2tie`): `p1_boxed_values=True`, `p2_marker_tiebreak=True`.
Losing variants REMOVED: the v1 / v3 boxed wordings, `P1_BOXED_RULES`, `p1_boxed_rule` and the
`bx_v*` configs — exactly one boxed rule exists (`prompts.P1_BOXED_VALUES_RULE`). `configs/prod.json`
regenerated from PROD_CONFIG (rec3.json now equals it). Tests: suite + subjects + budget 350 passed;
transcription service tests 93 passed; `import app.main` clean.
Spend: $36.54 of cap $44.27.
