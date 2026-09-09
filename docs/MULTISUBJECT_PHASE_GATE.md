# MULTISUBJECT_PHASE_GATE — the multi-subject beta, phase by phase

Governs: `vivi-multisubject-execution-plan.md` (Noam's rulings, APPROVED 2026-09-08).
Branch `perf/rubric-extraction-latency`. Every run is in `docs/MULTISUBJECT_RUNLOG.md`; every
deferred piece is in `docs/ALPHA_BACKLOG.md`; the phase checklist is
`docs/MULTISUBJECT_TRACKER.md`.

**The one-sentence claim.** A teacher can upload a Mathematics or English rubric — DOCX or PDF,
typed or handwritten — review it, save it, and grade against it, with the subject as an explicit
input she chooses and never something a model guesses.

**The one-sentence caveat.** Nothing about the *quality* of a Math or English grade was measured,
because no ground truth for either exists yet.

---

## Phase 0 — Regression lock

**Before:** CS was the only subject, and nothing recorded what "unchanged" would mean.
**After:** six sha256 prompt pins, the zero-spend gates, and three spend baselines on record.

| gate | result |
|---|---|
| backend pytest (main) | 1475 passed / 2 skipped / 9 failed — 8 are a cp1252 locale artefact (green under `PYTHONUTF8=1`, identical at HEAD), 1 was a timing artefact of adding migration 027 mid-run |
| transcription suite | 152 passed |
| prompt pins | 6/6 |
| vitest | 73 files / 1083 passed |
| tsc · copy gate | exit 0 · PASS |
| Playwright | **VOID** — see below |
| rubric eval k=1 | 4/5 |
| transcription `check_goal.sh` k=5 | GOAL FAIL — the standing baseline, unchanged by this work |
| A3 grading k=5 | **BLOCKED** by the runner's pre-spend expressibility guard (the compiled hobby plan cannot express `din_ezra` q2.א.c0 = 4). Recorded, not worked around |

**The Playwright baseline was void and this matters.** The suite hardcodes port 3100 with
`reuseExistingServer`, and port 3100 was held by a different Next app the owner had running. All
168 failures drove the wrong application. There is therefore **no Phase 0 e2e baseline** — the
comparison used throughout is a re-run on a free port.

**Spend:** $0.18 (A1/A2 wording) + the rubric-eval and check_goal runs.

---

## Phase 1 — The seam

**Before:** prompts, pipelines and the grader were CS by construction; `subject` existed nowhere.
**After:** `app/subjects/` — a registry of frozen profiles, each a key plus fragments (extraction,
P1, verifier), its valid question types, its P2 keywords and one behaviour flag. `subject` is a
column (migration 027, applied to Vivi-Test), a required form field at upload, and **never model
output** (D-10): it was removed from the extraction schema outright.

The CS prompts are **byte-identical**, and that is enforced rather than asserted: six sha256 pins
taken BEFORE any edit, re-read after the seam from the assembled CS output. Prompt versions now
stamp `<base>+<profile>` (D-16) — `t1.4-tables+mathematics`, `grader-v5.4+english`.

**Tests:** pins 6/6 · registry 16 · reader separation (the transcription engine can never import
`rubric_read`) · API seam 6 · extraction-job seam 7 · grader v5 +3 · 256 agent/service tests
unchanged.

---

## Phase 2 — Math ingestion

**Before:** a rubric was a DOCX with a text layer. A scanned or handwritten one produced nothing.
**After:** `render_source` picks the stage — the deterministic renderer when the DOCX has text,
otherwise `rubric-read/rr1.0` over page images, and **any PDF** is rasterized into the same stage
(D-8). The reader shares P1's provider, scheduler and encode pool but is a separate prompt with a
separate name, and a test forbids the student path from importing it (§4.6).

`rescale_to_exam` maps a Math rubric's written percentages onto the exam's real total on the 0.25
grid. **It never invents a denominator**: the total is the exam's own 100.

**The real document changed this phase's design.** The recorded run
(`snapshots/2026-09-09_multisubject-math4/`) found three defects, all mine:

1. **An unscored question crashed the extraction.** The teacher's file scores four of five
   questions; q2 has no marking scheme. `gt=0` on the schema turned her omission into an opaque
   error with no draft and nothing to fix. Now `ge=0` with a validator that spends no retry on it.
2. **The post-pass was silently reconciling her arithmetic.** Largest remainder forces children to
   sum to the parent by construction — which would have erased q3's sections summing to 105% and
   q4.ד's 39% declared over steps summing 34%. Faithful capture binds deterministic code exactly
   as it binds the model. Inconsistent weights are now kept, flagged, and block compile.
3. **An off-grid total produced off-grid points** (33.33 → an 11.33 share). The denominator is
   snapped once, the written value kept, the change named.

**Result on the real 4-unit document:** total **100**, shares **33.5 / 33.25 / 33.25 / 33.25 /
33.25**, `SelectionGroup` choose 3 of 5, every criterion on the grid, prompt
`3.10.0-fixsource+mathematics`, 0 retries. The draft does **not** compile — five of her nodes
disagree with themselves — and after the one move the rubric gate exists for, the Contract
compiles at **total 100.00**. That is the kill criterion, met the honest way.

**Tests:** 24 rescale (known answers, the real q4.ד and q2 shapes, off-grid total, idempotence) +
2 pipeline-level + 16 image-render.
**Spend:** render $0.147 (16 pages, paid once, replayed) + ~$0.15 extraction (15,668 in / 9,915
out at $2/$12 per Mtok) + two failed attempts.

---

## Phase 3 — Frontend

**Before:** an answer was code or prose by a heuristic over its text, always LTR.
**After:** `answerRenderPlan(answer, subject)` — english → prose LTR, mathematics → prose RTL, CS →
the existing heuristic byte-identical. The subject threads through both review surfaces and the
batch dashboard, and is fetched **non-gating**: a failed rubric fetch leaves direction as it is
rather than blocking a review on a decoration. The picker sits above the drop zone, pre-filled
from her onboarding when she teaches exactly one subject; in the metadata editor it is immutable,
because the server answers a change with 409.

The bidi standing rule is untouched: these remain pure `dir` islands, and
`unicode-bidi: plaintext` — recorded in `CLAUDE.md` as empirically falsified — was not
reintroduced.

**Tests:** vitest 73 files / **1089** passed (+6). Playwright on a free port: **161 passed, 1
failed**, and that one is stale by exactly one click against the §6 save gate from `f45b47e`,
proven by driving the journey twice (first click → the advisory prompt and no POST; second →
the mocked 400 and `INV-2` on screen). Left untouched: it is another PR's test.

---

## Phase 4 — Bands

**Before:** a band ladder would have been extracted as four criteria, or as one criterion worth
the sum of its bands.
**After:** one criterion at the top band, every band quoted verbatim in the description
(ALPHA-GAP A-1 — discrete levels are alpha).

**The 4b evidence gate fired.** Compiling the ministry contract through PLAN COMPILER v2 showed
each ladder becoming **three `required` slots**: C5 read the band values as components, saw
8+5+2+0 = 15 > 8, and reconciled them to 5/2/1. A student would have needed CORRECT *and*
PARTIALLY CORRECT *and* MINIMALLY CORRECT to earn full marks, with INCORRECT (0) named as
something to earn. **The plan is the grade**, so this was not cosmetic. C8-lite — the third early
return beside C3 that the execution plan specifies — now keeps a ladder whole.

**Result on the PUBLIC-MINISTRY F/G rubric:** 4 criteria at **8 / 10 / 16 / 6 = 40**, compile OK,
`short_answer`, every band present in every description, `rescale_to_exam` correctly absent.
**Kill check:** the A0 compiled-plan guard did **not** move — 110 plan-compiler tests pass.

**Tests:** 10 band tests (including four near-misses and a CS component list that still splits) +
4 English-profile tests.
**Spend:** $0.038 (9,106 in / 1,654 out).

---

## Phase 5 — Smoke, index, report

**The smoke gate, leg by leg.** What the plan asked for, and what actually ran.

| leg | asked | result |
|---|---|---|
| CS gates byte-identical | prompt pins + A0 guard unchanged | **PASS** — 6/6 pins on the assembled CS output, A0 compiled-plan guard green (46 tests) |
| **full backend suite** | no regression vs Phase 0 | **1583 passed / 2 skipped / 1 failed**, clean run. The one failure is a flaky heartbeat-timing test (6 of 7 isolated runs pass, the seventh a connection error) on a path no commit in this work touches. It found 6 REAL regressions first — see the fifth objection |
| transcription suite | matches Phase 0 (152) | **PASS** — 152 passed, 1 skipped |
| CS rubric eval | matches the Phase 0 baseline (4/5) | **PASS, and identical** — 4/5, with the SAME fixture failing for the SAME three reasons (`point_exactness=0.979<1`, `annotation_mismatch`, `pedagogical_mismatch`) and every structural metric unchanged to four decimals. Re-run because the extraction schema changed; `results/20260909-104242_gpt-5.6-terra-high` |
| Math loop, **DOCX** | render → extract → rescale → compile at 100 | **PASS** — total 100, shares 33.5/33.25×4, choose 3 of 5; compile blocked at 5 nodes where her own weights disagree, and **OK total=100.00** after the rubric-gate fix |
| Math loop, **PDF** | the same document through the PDF path | **PASS** — `stage=image_read source=pdf`, 16 pages, 0 failed, $0.147; identical shares and total; **OK total=100.00** after the fix. Independent draw, so a slightly different set of her inconsistencies surfaced (7 nodes) |
| the teacher's `10%` visible | her written weight kept in each criterion description | **PASS** — e.g. `15% נגזרת`, `הצבה 10%`, carried verbatim |
| English booklet | non-`coding_task` + compiles | **HALF** — extraction PASSES (`short_answer`, prompt `3.10.0-fixsource+english`, q1 60 + q2 40 = 100, `rescale_to_exam` correctly absent, 1 retry). Compile is **BLOCKED**, and for an honest reason: q2 is the WRITING task, and this booklet does not contain its rubric — that is the ministry band table, a SEPARATE document. `ZERO_CRITERIA` on q2 is the correct reading of the file. Merging a second file by item number is **ALPHA-GAP A-9** (D-14 ii), so this is a known gap meeting a real document, not a defect |
| English band rubric | ministry F/G → 4 criteria 8/10/16/6 = 40 | **PASS** — compile OK at 40, `short_answer`, every band verbatim |
| **Band probe, pinned** (4a) | the OMML probe's band table → 10/6/4 deterministically | **PASS** — 3 criteria at **10 / 6 / 4**, total 20, compile OK, `short_answer`, 0 retries; and `omml_seen == omml_rendered == 1` on the same document (**P-3**). Pinned in two halves: the render is checked live, the extraction against a recorded snapshot |
| **P-11b** grid-snap drift | max per-criterion drift ≤ 0.25 on a real fixture | **PASS at 0.1725** on the 4-unit document — measured by capturing both sides of the post-pass, not asserted |
| **Math, 3-unit** (the cap rule) | choose-4-of-5 from «answer any, capped at 100» | **PASS, and it corrected the plan** — image stage fired on a second document (180 text chars, 10 images → 10 pages read, 0 failed, $0.0897); `choose_k` **4** of 5 from the Hebrew cap sentence; total **96**, not the 100 the plan predicted, because the paper prints **24 points per question** («לכל שאלה 24 נקודות»), so ⌊100/24⌋ = 4 and 4 × 24 = 96. The extraction is faithful; the plan's 25-per-question assumption was wrong. Compile blocked at 3 of her nodes, **OK total=96** after the fix |
| P-10 grading ceiling, P-6, P-4 | answer keys graded, misspellings and paragraphs survive P1+P2 | **NOT RUN** — see below |
| `grep ALPHA-GAP` | returns every §6 site | **PASS** — 47 notes |

**The off-grid fix earned its place on a real run.** The PDF draft's question totals were
33.333333…, summing to **99.99999999989998**. Before Phase 2's amendment that would have produced
shares off the 0.25 grid; the denominator is snapped once to 100, the written value kept in the
stamp, and the change named to the teacher.

**What the English half actually shows.** Two English documents were run. The one that carries its
own rubric (the ministry band table) extracts and compiles cleanly at 40. The one that does not
(a bagrut booklet) extracts correctly and then refuses to compile, naming the question whose
criteria are missing. Both behaviours are right; together they say the English path needs the
second-file merge (A-9) before a teacher can grade a full bagrut from her own files alone.

**P-11b nearly reported a false failure, and the diagnostic was the thing that was wrong.**
The first measurement on the real document came back **0.97** against a 0.25 bound. Splitting it by
node showed why: `max_criterion_drift` divided by the sum of the teacher's written weights, while
the post-pass divides by her DECLARED weight wherever the two disagree. So on q4.ד — 34 % of steps
under a declared 39 % — the diagnostic was adding her missing 5 % to what is supposed to be a
rounding measure. Fixed to mirror `split_written`'s branch; the true rounding drift is **0.1725**,
and her gap keeps its own channel (a `rubric_mismatch` annotation that blocks compile). The
temptation here was to widen the bound; the bound was right and the ruler was bent.

**Three legs did not run, and none of them silently.** The founder's handwritten Math page and
English paragraph were never provided, so `fixtures/smoke/` does not exist and P-6 (misspellings
survive) and P-4 (paragraphs survive) are untested — they are transcription claims and there is
nothing to transcribe. The SYNTHETIC-DERIVED answer-key variants were not built, so P-10 (the
grading ceiling with `grader-v5.4+english`) was not measured.

---

## Three adversarial objections

**1. "You proved the Math loop on a document you also used to design the fix. That is circular."**

Partly fair, and worth stating precisely. The 4-unit document drove three code changes, so it
cannot also be evidence that those changes generalize. What it *does* establish is narrower and
still worth something: the arithmetic is exact (24 known-answer tests, none of which depend on the
document), the invariants hold by construction rather than by tolerance, and the failure mode on a
real teacher's real inconsistency is **refuse and explain**, not silently repair. The generalizing
evidence does not exist and is not claimed. The honest reading: this is one worked example, and
the second Math document (the 3-unit file, with its different selection rule) has **not** been run
through extraction.

**2. "Flattening a band ladder means the grader can award 5.5 out of a 6-point ladder — a mark the
teacher's rubric does not define. You have invented a score."**

This is the strongest objection to Phase 4 and it is not fully answerable. The mitigation is that
the ministry's own instructions say *"Markers can give in-between grades e.g. 7 pts"*, so
between-band marks are already sanctioned by the authority that wrote the rubric — the flattened
path matches what the document tells markers to do, rather than contradicting it. But that is a
defence of this *particular* rubric, not of flattening in general. A school rubric that means its
bands strictly would be graded wrongly, quietly, and the teacher would have to catch it at the
grading gate. That is why A-1 is the first entry in the alpha backlog and why the ladder text is
kept verbatim in the description: she can at least *see* the bands she is overriding.

**3. "You changed a prompt fragment mid-run, then reported the result of the run that worked. That
is selecting your own evidence."**

Accurate as stated, and the RUNLOG records all four attempts including the two that crashed and
the one that ran on the wrong model. The F-1 change was not tuning toward a better number: the
first wording told the model to put 0 on an unscored *question*, which the schema rejects
outright, so every run with it fails identically — it was a wording bug, not an underperforming
variant. The distinction matters and is the reason attempt 2's gpt-4o result (1 question of 5) is
reported rather than buried: it is the single most misleading number produced all day, and it came
from a script-level mistake, not from the model or the fragment.

**4. (unprompted) "The e2e attribution rests on a diagnostic you deleted."**

True. The diagnostic spec was temporary and is gone; what survives is the causal chain, which is
checkable without it: `attemptSaveRubric` returns early while `openAdvisoryCount > 0 &&
!advisoryPromptShown`, that code is at HEAD from `f45b47e`, the employee fixture is the only
golden with an advisory, and the observation was that the first click produced no POST at all.
Anyone can re-derive it in five minutes; nobody should have to take my word for it.

**5. (unprompted) "You called four phases green while six tests were red."**

Correct, and it is the process failure of this run. Phases 1–4 were gated on the touched test
files, not the suite. The full backend run at the end found **six** tests this work had broken:
three in `test_transport_budget.py` still patching `render_docx_to_markdown` (the render seam moved
to the stats-returning twin, so the real DOCX parser stayed in the path and the fixture's magic
bytes died as `BadZipFile`), and three in `test_extraction_jobs.py` submitting without the now
required `subject` field, so FastAPI answered 422 before any file check ran and a file-magic test
was silently asserting form validation.

Neither is a product defect — the endpoint and pipeline behave correctly, and the frontend always
sends the subject. But the first group is the SAME defect I had already fixed once in
`test_extraction_job_seam.py` during Phase 1: I repaired one instance and never grepped for the
others. The rule that would have caught it is cheap and is now written down: **after moving a
seam, grep every patch target that names the old one, and run the full suite before calling a
phase green.** Fixed in `0bcb038`; the suite is re-running to confirm.

---

## What this beta cannot claim

1. **No Math or English grade has been measured against a teacher's marks.** There is no ground
   truth for either subject. The grader's accuracy on them is unknown — not "probably fine",
   unknown.
2. **No Math or English transcription has been measured.** The P1 fragments (linear notation, the
   `[איור: …]` line, misspellings preserved) were written blind and have never been scored. The
   transcription eval suite still has exactly one scorer profile and it is CS (A-7).
3. **The A3 grading number was never obtained.** It was blocked by the expressibility guard before
   this work began and is still blocked. Nothing here improved or regressed it.
4. **The rubric paths are proven on two documents per subject**, one of which (the ministry
   rubric) was authored for this purpose from a public PDF. That is a demonstration, not a corpus.
5. **The 3-unit Math exam can never reach the total its own instructions promise**, and Vivi does
   not tell the teacher so. The paper says each of 5 questions is worth 24 and that a student may
   answer freely up to a cap of 100 — but ⌊100/24⌋ = 4, so the most anyone can earn is 96. The
   extraction is faithful and the rubric compiles at 96; the *pedagogical* contradiction in her
   instructions is surfaced nowhere. (It was found by running the document, which is why the run
   was worth doing.)
6. **A band ladder is graded as one criterion, not as bands** (A-1), and a Math answer is
   transcribed as linear text, not as mathematics (A-2). Both are visible to the teacher and both
   are deferred by decision.
7. **The Playwright suite has one red spec** and the frontend's tracked tree at HEAD does not
   build without files that were untracked when this work started. Neither is caused by this work;
   both are recorded rather than fixed.
8. **Production still needs migration 027.** It was applied to Vivi-Test only. Without it every
   rubric read fails on a missing column.
