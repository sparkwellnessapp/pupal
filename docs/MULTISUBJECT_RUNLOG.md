# RUNLOG — Multi-subject beta

Append-only. Every run: what ran, at which commit, the number, and where the artefacts are.
Suite-level runs are ALSO logged in their own suite RUNLOGs by the runners; this file is the
cross-suite index for the P-4 gate.

## Phase 0 — baseline (2026-09-08)

Tree: `perf/rubric-extraction-latency`, HEAD `4ee8a5b` (= `52855ab` + the Q7 WIP commit of the
grade-review module; no product code changed between them).

### Zero-spend gates

| gate | command | result | artefact |
|---|---|---|---|
| backend pytest (main) | `pytest --ignore=tests/transcription_eval_suit -q` | **1475 passed, 2 skipped, 9 failed** in 39:54. The 9: (a) 8 × `tests/rubric_eval_suite/test_pedagogical.py` — `UnicodeDecodeError: 'charmap'` reading UTF-8 fixtures without an encoding on a cp1252 Windows locale; **environment, not code** — the same file is 8/8 green under `PYTHONUTF8=1` and fails identically at HEAD; (b) 1 × `test_schema_canon::test_expected_migrations_matches_migration_files_on_disk` — a **timing artefact**: the gate ran while migration 027 was being added (the tuple and the file landed minutes apart); green on the post-seam rerun. Both recorded here; neither is a product regression. ⚠ the run overlapped the Phase 1 edits (19:22–20:02); the number is the working tree's, not a pristine 4ee8a5b | scratch `phase0/backend_gates.log` |
| backend pytest (transcription suite) | `pytest tests/transcription_eval_suit -q` | **152 passed, 1 skipped** | same |
| A0 compiler guard | `pytest tests/grading_eval_suite/test_compiled_plan_guard.py -q` | **8 passed** (hobby 184/190, bagrut 284/298, byte-pinned) | same |
| CS prompt pins | `pytest tests/subjects/test_prompt_identity.py -q` | 6 passed (pinned at this commit; still 6 passed on the post-seam assembly) | `tests/subjects/test_prompt_identity.py` |
| vitest | `npm test` | **73 files, 1083 passed, 1 todo** | scratch `phase0/frontend_gates.log` |
| tsc | `npx tsc --noEmit` | **exit 0** | same |
| copy gate | `npm run check:copy` | **COPY GATES PASS** (inherited debt reported on 6 non-batch lines, unchanged) | same |
| Playwright | `npm run test:e2e` | running (dev server on :3100 up) — result appended when it lands | same |

### Spend runs (D-17 lifted)

| run | command | result | artefact |
|---|---|---|---|
| rubric eval k=1 | `runner --config gpt-5.6-terra-high --repeats 1` | **4/5 pass** (same pass count as the 2026-08-24 verdict's per-run 4/5; per-fixture gate in the summary) | `tests/rubric_eval_suite/results/20260908-192219_gpt-5.6-terra-high/` |
| transcription `check_goal.sh` k=5 | `bash tests/transcription_eval_suit/check_goal.sh` (config v0, exam spec draft.json) | **GOAL: FAIL** — the standing state of the transcription goal, not a regression. Per doc, k=5, byte-identical across repeats on the gated recalls: dan `doc_ratio 0.947–0.950`, `op 0.985`, `struct 0.991`, `mc 0.903`; din `doc_ratio 0.905–0.942`, `struct 0.988`, `mc 0.926`; moran `struct 0.988–0.992`, `mc 0.973` (rep4 passed); omer `op 0.985`, `struct 0.992–0.996`; yonatan `doc_ratio 0.958–0.961`, `op 0.985`, `struct 0.988`, `mc 0.889`. **This distribution is the P-4 transcription baseline**: the CS P1/P2 text is sha-pinned, so a post-seam rerun must reproduce it within P1's own repeat spread. | `tests/transcription_eval_suit/results/20260908_194545_v0/` |
| A3 grading k=5 | `compile_plan.py --exam hobby_tvshow` (A0 184/190, byte-identical) → `segment_plan.py --stage both --confirm-spend` (route $0.069, 9 calls, 1 failed `q2.א.c0`; segment $0.113, 8 calls, expressible 188/190) → `runner --config sonnet5-v54-compiled -k 5 --fixtures <5 hobby>` | **BLOCKED before spend by the runner's own guard** (owner H-4 item 3, `runner.py:374-383`): `plan 'hobby_tvshow/compiled-5cafe7d77698' cannot express din_ezra's GT — q2.א.c0 award 4 UNREACHABLE (reachable 0 / 2.5 / 5)`. Cause: the router refused `q2.א.c0` (the A2 stage's one failure), so the terminal stayed a monolith — the OD-13 routed-miss class, a plan-compiler item, not a seam item. **Consequence for P-4:** the grading gate for this beta is A0 (compiler-only, byte-pinned) + the sha-pinned CS verifier prompt; no measured CS grading number exists for the compiled-plan architecture until OD-13 closes. A hand-plan run was NOT bought: with the CS verifier bytes pinned it would measure only model noise. | `tests/grading_eval_suite/plans/compiled/hobby_tvshow.routed+segmented.{plan,wording,run}.json`; config `configs/sonnet5-v54-compiled.json` (kept for the rerun once OD-13 closes) |

---

## Phase 0 — the Playwright baseline was VOID, and the re-run (2026-09-09)

The Phase 0 e2e line above ("running… result appended when it lands") landed as
**168 failed / 9 passed**, and the failures are **infrastructure, not findings** — exactly the
signature `playwright.config.ts` documents. The config hardcodes port **3100** with
`reuseExistingServer: !CI`, and port 3100 was held by a *different* Next app the owner had
running (`C:\Users\ariel\Desktop\ViviWebsite`, PID 22192, started 14:26). Every spec drove the
wrong application. **No Phase 0 e2e baseline exists**; the Phase 0 row is corrected to VOID.

Re-run on a free port (untracked `frontend/playwright.port3101.config.ts`, same config, port
3101, its own `.next-e2e-3101`), against the working tree carrying Phase 1–3:

| run | result | artefact |
|---|---|---|
| full suite, port 3101 | **161 passed, 1 failed** (13.2m) | scratch `phase3/e2e_3101.log` |

### The one red spec is NOT this work — attributed, with evidence

`rubric-review.spec.ts:53 employee: selection header … structured 400 then clean save` times out
waiting for `INV-2` after its single save click.

Attribution (a temporary diagnostic spec drove the same journey and was deleted afterwards):

* first click → **no POST at all**; the page shows the line «המלצה אחת לא נסקרה — לשמור בכל זאת?»
* second click → `POST /save_ontology_draft`, the mocked **400** returns, and both `INV-2` and
  the Hebrew compile-rejection heading render.

The cause is `page.tsx::attemptSaveRubric`, which returns early while
`openAdvisoryCount > 0 && !advisoryPromptShown` — the §6 "soft line" save gate. It is **at HEAD**,
landed in **`f45b47e` feat(findings): PR-6 §6 save gate + §5 rail weight**, and appears in no diff
of this work. The employee fixture is the one golden that carries an advisory, which is why only
that spec is red. **The application is correct; the spec is stale by exactly one click.** The
one-line fix belongs to the findings PR, so per §4.5 (never rewrite someone else's in-flight work)
it was left untouched and is reported here instead.

Attribution could NOT be done the obvious way — a clean worktree at HEAD does not build
(`Module not found: @/contexts/UploadQueueProvider`): a large amount of the frontend is untracked
in-flight work, so HEAD's tracked tree is not a runnable app. Recorded because it makes "is this
spec red at HEAD?" unanswerable by checkout for anyone who tries later.

### Incident, self-inflicted: `frontend/node_modules` damaged and repaired

Cleaning up the temporary worktree, a `cmd //c rmdir` aimed at a `node_modules` **junction**
removed `frontend/node_modules/.bin` and 14 transitive packages from the REAL tree (`npm test`
died with a missing `vitest` binary, then `ERR_MODULE_NOT_FOUND @jridgewell/sourcemap-codec`).
Repaired with `npm rebuild` (84 bin links) + `npm install --no-audit --no-fund` ("added 14
packages, changed 1 package in 5s"); the suite is green again (below). `package.json` and
`package-lock.json` were already modified vs HEAD before this (the owner's in-flight msw work), so
any lockfile line this install touched cannot be separated from that and is flagged here rather
than claimed clean. **Do not delete a junction with `rmdir` through Git Bash path mangling.**

## Phase 2/3 — gates on the working tree (2026-09-09)

| gate | command | result |
|---|---|---|
| backend import | `python -c "import app.main"` | **OK** |
| backend collect | `pytest --collect-only -q --ignore=tests/transcription_eval_suit` | **1565 collected**, no import errors |
| targeted backend | rescale + unscored-part + extraction-job seam + `tests/subjects` + retry-policy + fp123 | **70 passed**, then **24 passed** on the rescale suite after the off-grid fix |
| vitest | `npm test` | **73 files, 1089 passed, 1 todo** (Phase 0: 1083 — +6 new subject tests) |
| tsc | `npx tsc --noEmit` | **exit 0**. ⚠ CORRECTION: it briefly reported 3 errors in the untracked `src/mocks/grade_review/handlers.ts`, and this log first blamed that file. It was wrong — the errors were a SYMPTOM of the node_modules damage recorded above (msw's type dependencies were among the packages removed). The file is byte-unchanged; after `npm install` restored the tree, tsc is clean. A missing transitive package surfaces as a type error in whatever imports it, which reads exactly like a defect in that file |
| copy gate | `npm run check:copy` | **COPY GATES PASS** |

## Phase 2.t — the real-provider snapshot of the 4-unit Math DOCX

Four attempts. Each one moved a real defect, so all four are recorded.

**Render (paid once, reused by every attempt).** `render_source` over the 16 page images:
`stage=image_read source=docx text_chars=0 images=16 pages_read=16 pages_failed=0
prompt=rubric-read/rr1.0 model=gemini-3.1-pro-preview` — **$0.1472, 36.0s read, 47.8s wall,
14,819 chars**. Artefacts: `snapshot/math4_docx/render.md` + `render_report.json`.

**P-14 (rubric-read fidelity) — PASSES by inspection of the render against the page images.**
The weights sit on the step lines they annotate: q1 `א (20%)` with `5% / 5% / 10%`; q3
`(20%) ב` with `משוואה 5% / 5% / מציאת q 10% / מציאת p 5%`; q4's summary column
`10/10/7/39/9/15/10 → 100`; q5's `7/12/38/10/18/15 → 100`. Figures came through as
`[איור: …]` lines, as F-3 specifies. Two known gaps, both faithful: **page 8 is blank** (a
grid page with almost no ink — the reader returned nothing rather than inventing) and
**q2 (vectors) has no marking scheme anywhere in the document** — see below; this is the
teacher's own omission and it is what the next three attempts collided with.

| # | what changed | outcome |
|---|---|---|
| 1 | full pipeline, provider render | **CRASH** — `RubricExtraction` rejected `points=0.0` on three q2 nodes (`gt=0`) |
| 2 | render replayed from #1 | **CRASH avoided; wrong model** — ran on the pipeline's own `gpt-4o` code default (the script bypassed the Cloud-Run env pin), extracted **1 question of 5**, mixed scales (sub-question totals on the exam scale, criteria as percentages) |
| 3 | production pin set explicitly (`gpt-5.6-terra` / high / 32000) | **CRASH** — all 5 questions extracted, but `QuestionExtraction.total_points` rejected `0.0` on q2 |
| 4 | F-1 amended: an unscored question keeps its PRINTED total, its parts read 0 | recorded below |

**What #1 and #3 actually found (a real product defect, now fixed).** A question the teacher
never scored is a FACT about her document, and the extraction schema could not carry it: `gt=0`
on the sub-question point fields turned her omission into an opaque `ExtractionError` with no
draft, no annotation and nothing for her to fix. Fixed as `ge=0` on the two sub-question levels
plus a validator change — `SQ_ZERO_CRITERIA` is retryable **only for a scored part**, because
retrying an unscored one can only tempt the model to invent criteria. CS is untouched: no CS
document carries a 0 there. Pinned by `tests/services/test_extraction_unscored_part.py`
(no crash · no retry spent · the part reaches the teacher · one exam-scale `rubric_mismatch`
naming q2 · compile BLOCKED by INV-1 until she writes the weights · her fill compiles).

**What #2 found (a self-inflicted measurement error, recorded so it is not repeated).** The
pipeline resolves its model from `os.environ` and falls through to **`gpt-4o`** — the model
`CLAUDE.md` says was never evaluated against any current prompt. Cloud Run sets the pin as
service env; a script must set it itself. Any future one-off run of `extract_rubric_from_docx`
outside the runner must export `EXTRACTION_LLM_PROVIDER/MODEL/REASONING_EFFORT/MAX_TOKENS` or it
is measuring a model nothing else uses.

**Defect found in `rescale_to_exam` by the real draft (fixed).** Attempt #2's draft declared a
total of **33.33**, and the post-pass cut a share of **11.33** from it — a point value off the
0.25 grid the whole product rounds to. The denominator is now snapped ONCE before anything is cut
from it, the written value is kept in the stamp (`exam_total_written`), a global WARNING names the
change, and `snap_shares` refuses an off-grid total outright. On a real 100 total every one of
these is a no-op. Pinned by three tests.

## Phase 4 — the ministry band rubric, and the compiler defect the probe found (2026-09-09)

**The fixture is authored, not found.** No public band rubric existed in the repo, so the Ministry
of Education Module G (16582) / F (external 16584) writing rubric, Winter 2020, was transcribed
from its own PDF text layer into a DOCX with the shape a teacher's file has (band table, four
band columns, points row beneath). Source URL and fetch date are in the snapshot MANIFEST; the
builder script is committed beside the fixture so it can be audited or rebuilt. No wording is
invented.

**4a, the recorded run** (`snapshots/2026-09-09_multisubject-ministry-fg/`): `gpt-5.6-terra`/high,
prompt `3.10.0-fixsource+english`, 26.6 s, 9,106 in / 1,654 out (**$0.038**), **0 retries**, no
warnings. Four criteria at **8 / 10 / 16 / 6 = 40**; `compile OK total=40.0`; `short_answer`;
`rescale_to_exam` absent; all four band names present in all four descriptions with their own
points. The plan's 4a target, met on the document.

**4b, the evidence gate fired.** The ruled 10-minute probe compiled that contract through PLAN
COMPILER v2 (pure algebra, no provider, no cost) and read the slots:

```
q1.c0 (8):  required 5 · required 2 · required 1
q1.c1 (10): required 6 · required 3 · required 1
q1.c2 (16): required 10 · required 5 · required 1
q1.c3 (6):  required 3 · required 2 · required 1
flags: case3_over_allocation  "stated ['8','5','2','0'] = 15 > 8 → ['5','2','1','0']"
       unvalued_component_dropped  "15 valueless segment(s)"
```

C5 read the band values as COMPONENTS of the criterion, saw they exceeded it, and reconciled them
downward. The consequence is not cosmetic: a student would have had to satisfy CORRECT *and*
PARTIALLY CORRECT *and* MINIMALLY CORRECT to earn full marks on an essay, and the bottom band
(INCORRECT, 0) was named as something to earn. Bands are ALTERNATIVES, not parts, and the plan is
the grade.

**C8-lite** (the third early return beside C3, exactly as the plan specifies): a terminal whose
text is a band ladder → ONE `required` slot at the terminal's points, wording = the ladder
verbatim, `routed=False`, flagged `band_ladder_kept_whole` with the ladder in the detail. Re-probe:
4 terminals → **4 earn slots, no splits**.

The detector is deliberately narrow, because a false positive collapses a real component list — the
same error in the other direction. Three or more labelled bands, values strictly descending, top
band == the terminal's points, bottom band 0. Ten tests cover it, including a Hebrew CS component
list that still splits and four near-misses.

**Kill check (the phase's stated kill): the A0 guard did not move.** 110 plan-compiler tests pass,
the compiled-plan guard among them.

## Phase 5 — the smoke gate (2026-09-09)

Artefacts: `snapshots/2026-09-09_multisubject-smoke/`.

| leg | result |
|---|---|
| CS prompt pins + A0 guard | **PASS** — 46 tests (pins 6/6 on the assembled CS output) |
| **Math, PDF** (D-8) | `stage=image_read source=pdf`, 16 pages, 0 failed, **$0.1473**; 15,692 in / 10,306 out, 0 retries, 344 s; total **100**, shares 33.5/33.25×4, choose 3 of 5, `computation`; compile blocked at 7 of her own nodes; **OK total=100.00** after the rubric-gate fix |
| **English booklet** | `stage=docx_text`; 26,896 in / 7,022 out, 1 retry, 108 s; q1 60 + q2 40 = **100**, `short_answer`, `rescale_to_exam` absent; compile **BLOCKED** on q2 |
| `grep ALPHA-GAP` | **47 notes** across backend and frontend |

**The PDF run is what justified the off-grid guard.** Its per-question totals came back as
33.333333…, summing to **99.99999999989998**. Snapped once to 100, the written value kept in the
stamp, the change named to the teacher. Without the Phase 2 amendment the shares themselves would
have been off the 0.25 grid.

**The English block is correct, and it names an alpha gap.** q2 of that booklet is the WRITING
task; the booklet does not contain its rubric, because that rubric is the ministry band table — a
separate document. `ZERO_CRITERIA` on q2 is the right reading of the file. Merging a second
document by item number is ALPHA-GAP A-9 (D-14 ii). Read with the ministry run, the two English
results say: the document that carries its own rubric compiles; the one whose rubric lives
elsewhere refuses and says which question is missing. A teacher cannot yet grade a full bagrut
English exam from her own two files alone.

**Legs that did not run**, stated rather than dropped: the founder's handwritten Math page and
English paragraph were never provided, so `fixtures/smoke/` does not exist and P-6 (misspellings
survive P1+P2) and P-4 (paragraph breaks survive) are untested — they are transcription claims with
nothing to transcribe. The SYNTHETIC-DERIVED answer-key variants were not built, so P-10 (the
grading ceiling with `grader-v5.4+english`) was not measured. The 3-unit Math document was never
extracted; its cap rule is implemented and unit-tested as choose-4-of-5 but has no real run.

### Spend, itemised (terra at $2.00 / $12.00 per Mtok)

| run | tokens | cost |
|---|---|---|
| 4-unit render (DOCX) | 16 pages | $0.147 |
| 4-unit extraction (attempt 4) | 15,668 / 9,915 | $0.150 |
| ministry rubric | 9,106 / 1,654 | $0.038 |
| 4-unit render (PDF) | 16 pages | $0.147 |
| 4-unit extraction (PDF) | 15,692 / 10,306 | $0.155 |
| English booklet | 26,896 / 7,022 | $0.138 |
| **subtotal, Phases 2–5 extraction/render** | | **≈ $0.78** |

Not itemised: two failed Math attempts (one on gpt-4o, one that died at the schema parse — tokens
spent, not recorded by the failing path), the Phase 0 rubric eval and `check_goal` runs, and the
Phase 5 rubric-eval re-run.

### The CS rubric eval, re-run after the schema change (2026-09-09)

The Phase 2 amendment relaxed `gt=0` to `ge=0` on two extraction fields and made
`SQ_ZERO_CRITERIA` retryable only for a scored part. Both sit on the CS path, so the CS number had
to be re-measured rather than assumed.

`runner --config gpt-5.6-terra-high --repeats 1` → `results/20260909-104242_gpt-5.6-terra-high`

| | Phase 0 (`20260908-192219`) | after (`20260909-104242`) |
|---|---|---|
| gate | **4 / 5** pass, valid 5, invalid 0 | **4 / 5** pass, valid 5, invalid 0 |
| the failing fixture's reasons | `point_exactness=0.979<1` · `annotation_mismatch` · `pedagogical_mismatch` | **identical** |
| question/criterion/sub-criterion recall + precision | 1.0 | 1.0 |
| point_exactness (worst / mean) | 0.9792 / 0.9958 | 0.9792 / 0.9958 |
| example_solution_fidelity | 1.0 | 1.0 |

Same gate, same pass set, same failure signature, same structural metrics to four decimals. The two
NON-gating text-fidelity diagnostics moved in both directions between draws
(`question_text_fidelity_min` 0.5839 → 0.8364, `subquestion_text_fidelity_min` 0.5996 → 0.2266),
which is per-draw variation at k=1 on a verbatim-text metric, not a regression signal — the gate
does not read them and no gated metric moved at all. Four transient `APIConnectionError` retries
occurred during the run and were absorbed by the transport layer.

### The 3-unit Math document — the cap rule on a real file (2026-09-09)

Run late, to retire a «cannot claim». It corrected the execution plan's own expectation.

`stage=image_read source=docx` — 180 text chars and 10 images, so the trigger fired on a SECOND
real document; 10 pages read, 0 failed, **$0.0897**. Extraction `gpt-5.6-terra`/high, prompt
`3.10.0-fixsource+mathematics`, 12,724 in / 8,680 out, **0 retries**, 325 s.

Result: one `SelectionGroup`, **choose_k = 4** of 5, label = the paper's own sentence
«מותר לכם לענות על מספר שאלות כרצונכם, אך סך הנקודות שתוכלו לצבור לא יעלה על 100»; five questions
at **24** each; total **96**; compile blocked at q1/q3/q5 (her weights), **OK total=96** after the
rubric-gate fix.

**The plan predicted «five questions of 25, choose 4, total 100». That was wrong, and the run is
right.** Page 1 of the paper states «בשאלון זה 5 שאלות - לכל שאלה 24 נקודות» — twenty-four, not
twenty-five. So ⌊100/24⌋ = 4 (F-1's cap rule, correct) and the achievable total is 4 × 24 = **96**.
The extraction read what is printed.

**A pedagogical contradiction nobody has surfaced.** The teacher's instructions promise a cap of
100 that her own point values make unreachable — a student answering every question can earn at
most 96. Vivi captures this faithfully and says nothing about it: the rubric compiles at 96 and no
annotation names the gap between 96 and the promised 100. Recorded as a «cannot claim», because it
is exactly the kind of teacher-facing finding the product exists to surface.

### The full backend suite, and the six regressions it caught (2026-09-09)

`pytest --ignore=tests/transcription_eval_suit -q` under `PYTHONUTF8=1` — 37m57s.

**1574 passed, 2 skipped, 6 failed.** The Phase 0 baseline was 1475 passed / 9 failed, where 8 of
the 9 were the cp1252 locale artefact (absent here because this run set `PYTHONUTF8=1`) and 1 was a
timing artefact. So the honest comparison is: the locale and timing failures are gone, and **six
NEW failures appeared — all caused by this work.**

| failing test | cause |
|---|---|
| `test_transport_budget.py::test_deadline_none_is_the_unbounded_eval_path` | patches `render_docx_to_markdown`; the pipeline now goes through `image_render.render_source` → `render_docx_to_markdown_with_stats`, so the real parser stayed in the path and `b"PK"` raised `BadZipFile` |
| `…::test_tier_b_skipped_when_budget_cannot_hold_it` | same |
| `…::test_validation_entry_guard_refuses_and_names_the_budget` | same |
| `test_extraction_jobs.py::test_submit_rejects_non_docx_magic` | submits without `subject` (required since D-10) → 422 from form validation before the file check |
| `…::test_submit_rejects_empty_file` | same |
| `…::test_submit_then_resubmit_reuses_active_job` | same |

Both groups are tests left behind by a seam, not product defects. The first group is the **same**
defect already fixed once in `test_extraction_job_seam.py` during Phase 1 — one instance repaired,
the rest never grepped for. Fixed in `0bcb038`; the three affected files now pass 44/44, and the
full suite is re-running to confirm the total.

`pytest tests/transcription_eval_suit` (the required second invocation): **152 passed, 1 skipped** —
identical to the Phase 0 baseline.

### Phase 4a's pinned probe, and P-11b measured on real weights (2026-09-09)

Two plan items that were still open and needed no input from Noam.

**The band probe is now a fixture and a pinned benchmark.** `omml_bands_probe.docx` had been living
in the session scratchpad — one cleanup away from gone — and is now
`tests/rubric_eval_suite/fixtures/probes/omml_bands_probe.docx`. Run through the english profile
(`gpt-5.6-terra`/high, `3.10.0-fixsource+english`, render `docx_text`, 0 retries): three criteria at
**10 / 6 / 4**, total **20**, `compile OK`, `short_answer`, and `omml_seen == omml_rendered == 1`
(**P-3** confirmed on the same document). Pinned in two halves by
`tests/subjects/test_omml_bands_probe.py`: the render is asserted live against the fixture, the
extraction against the recorded snapshot, so a change in the flattening rule surfaces as a diff.

**P-11b measured, after the diagnostic nearly lied.** `rescale_to_exam` runs inside the pipeline, so
the pre-rescale draft is normally never seen; the post-pass was intercepted to capture both sides of
the real 4-unit extraction (render replayed, so only the extraction was paid for).

First result: `max_criterion_drift` = **0.9667** against P-11b's 0.25 bound. Splitting the measure by
node showed the fault was in the ruler, not the rounding — the diagnostic divided by the Σ of the
teacher's written weights, while the post-pass divides by her DECLARED weight wherever the two
disagree. On q4.ד (steps summing 34 % under a declared 39 %) that folded her missing 5 % into a
rounding measurement. Three nodes on this document are in that state: q3.ב (written 25 vs declared
20), q4.ד (34 vs 39), q5.ג (43 vs 38).

`max_criterion_drift` now mirrors `split_written`'s branch via `_exact_shares`. **P-11b on the real
4-unit document: 0.1725 — PASS.** Her gap keeps its own channel (a per-node `rubric_mismatch` that
blocks compile), which is where it belongs. Two tests pin both arms, including one that fails if the
teacher's gap ever leaks back into the rounding measure.

The tempting move was to widen the bound. The bound was right.
