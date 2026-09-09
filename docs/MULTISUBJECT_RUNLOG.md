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
