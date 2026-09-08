# TRACKER — Multi-subject beta (English + Math)

Governs: `vivi-multisubject-execution-plan.md` (Noam's rulings, APPROVED 2026-09-08) over
`docs/MULTISUBJECT_PLAN.md` (census + design). One branch (`perf/rubric-extraction-latency`), one
commit per phase, sanity gate before each commit (`python -c "import app.main"`,
`pytest --collect-only -q`, `npx tsc --noEmit`). Runs are recorded in `docs/MULTISUBJECT_RUNLOG.md`.

Legend: ☐ not started · ◐ in progress · ☑ done · ✗ dropped (with the drop-order rule cited) · ⚠ blocked

## Phase 0 — Regression lock

| # | item | state | note |
|---|---|---|---|
| 0.1 | WIP commit of the grade-review tree (Q7) | ☑ | `4ee8a5b` — the ruled paths + the module's own route dir, copy file and pricing test. ⚠ ~60 OTHER untracked files (onboarding, auth, batch upload, migrations 022–025, backend services) remain uncommitted in-flight work; not touched |
| 0.2 | zero-spend gates recorded with commit hash | ◐ | A0 guard 8 passed; vitest 73 files / 1083 passed; tsc 0; copy gates PASS; backend pytest ×2 and Playwright still running (output piped through `tail`, arrives at completion) |
| 0.3 | background spend runs started (A3 k=5, `check_goal.sh` k=5, rubric eval k=1) | ◐ | rubric eval 4/5 (`20260908-192219`); `check_goal` GOAL FAIL = the standing baseline (`20260908_194545_v0`); **A3 BLOCKED by the runner's expressibility guard** (compiled hobby plan cannot express din q2.א.c0 = 4; OD-13 routed-miss class) — see RUNLOG |
| 0.4 | §7 predictions committed to the three PREDICTIONS.md files | ☑ | grading MS-G (P-8/P-10/P-12), rubric addendum (P-3/P-7/P-11/P-11b/P-14/P-15), transcription `PREDICTIONS.md` created in the PREREG format (P-1/P-2/P-4/P-6/P-9/P-13) |
| 0.5 | §1 corrections to MANIFEST.md §3 and the plan's A5 Math rows + §0 item 2 | ☑ | manifest §3 + header; plan §0.2 + A5 Math rows + reading paragraph |

## Phase 1 — The seam

| # | item | state | note |
|---|---|---|---|
| 1.0 | sha256 pins of every current prompt constant (`tests/subjects/test_prompt_identity.py`) — BEFORE any prompt edit | ☑ | six pins at `4ee8a5b`; the test reads the CS ASSEMBLY post-seam and still matches |
| 1.1 | `app/subjects/` registry + three profiles + `prompt_version` stamp helper (§4.3) | ☑ | fragments ≤ 6 lines each; CS = None everywhere |
| 1.2 | `ontology_types.py` `SUBJECT_PROFILES` revived, `math`→`mathematics`, coerce-and-log at compile | ☑ | `default_question_type` added; `_coerce_question_types` in `contract_compiler.py` |
| 1.3 | migration 027 `rubrics.subject` + backfill + `EXPECTED_MIGRATIONS` + `test_schema_canon` | ☑ | applied to Vivi-Test (143 rows, all CS); ⚠ production still needs 027 at deploy |
| 1.4 | extraction: assembly from profile, `subject` removed from the LLM schema and stamped after parse, valid-types fragment, F-1 fragments | ☑ (deviation) | `subject` gone from `RubricExtraction`; F-1 appended as a section. **Deviation:** the extraction schema has no `question_type` field, so a "valid types" fragment would be a rule the model cannot act on (§10) — the profile DEFAULT type is applied in code and out-of-set types are coerced at compile (Amendment 2's second half) |
| 1.5 | P1/P2: `p1_system(profile)`, `p2_system_prompt(profile)` (P2 = base for all, ALPHA-GAP A-8), F-3 fragments, F-5 keyword set from profile | ☑ | `_P1_CS_INK_RULES` block substitution with an import-time guard; `PipelineConfig.subject_key`; keyword set from the profile |
| 1.6 | verifier: `verifier_system_prompt(profile)`, `build_verifier_message(…, profile)`, F-2 fragments; kwarg through `grader_v5` ← `grader_selection` ← `grading_runner` | ☑ | rules 3–5 substitution with an import-time guard; D-16 stamp on the draft |
| 1.7 | `GradableTest.subject` from the contract | ☑ | key only; `modalities` never on the type (test) |
| 1.8 | API: required `subject` Form on submit (422 unknown); save writes the column, 409 on mismatch | ☑ | `tests/api/test_subject_seam.py` 6 passed (422 missing/unknown, 409 on change, 400 unknown at save, column↔contract agree) |
| 1.9 | frontend: `api.ts:964`, `page.tsx` draft envelope + metadata change, `gen:api` | ☑ | `lib/subjects.ts` (keys + Hebrew labels); subject pre-filled from onboarding when exactly one; `gen:api` regenerated; tsc 0 |
| 1.10 | tests listed in §5 Phase 1 green; CS pins byte-identical | ☑ | pins 6/6 on the post-seam assembly; registry 16; grader v5 +3 (stamp, prompt swap, unknown refuses); gradable +2; API seam 6; extraction-job seam 7 (patch target moved to the stats twin); 256 agents/services unchanged |

**Phase 1 deviation (recorded):** `QuestionExtraction` has no `question_type` field, so a "valid question types" fragment would be a rule the extractor cannot act on (§10 "no rules to be safe"). Implemented instead: the profile DEFAULT type in code (`_build_response`) + coerce-and-log at compile. CS keeps `coding_task` everywhere → byte-identical contracts.

## Phase 2 — Math ingestion

| # | item | state | note |
|---|---|---|---|
| 2a | `image_render.py` + `rubric-read/rr1.0` + trigger in the runner + PDF rasterize + `RenderStats` + §4.6 import guard | ☐ | |
| 2b | INV-4 k-largest evidence; `rescale_to_exam` + tests; F-1 selection wording | ☐ | |
| 2c | OMML raw text in `parser_render.py` (drop-order #1) | ☐ | |
| 2.t | real-provider snapshot of the 4-unit DOCX → pinned Contract JSON | ☐ | |

## Phase 3 — Frontend

| # | item | state | note |
|---|---|---|---|
| 3a | answer mode from subject | ☐ | never drop |
| 3b | editor direction from subject (drop-order #3) | ☐ | |
| 3c | picker: upload step, metadata editor select, LanguageSelector CS-only, `types/rubric.ts.subject` | ☐ | |

## Phase 4 — Bands (drop-order #4, both or neither)

| # | item | state | note |
|---|---|---|---|
| 4a | extraction ladder rule + probe benchmark + PUBLIC-MINISTRY fixture | ☐ | |
| 4b | C8-lite only if the compiler splits ladders (evidence first) | ☐ | |

## Phase 5 — Smoke gate, index, report

| # | item | state | note |
|---|---|---|---|
| 5.1 | smoke fixtures assembled (`fixtures/smoke/`, `derived/`) | ☐ | |
| 5.2 | gate run + `docs/MULTISUBJECT_PHASE_GATE.md` | ☐ | |
| 5.3 | `docs/ALPHA_BACKLOG.md` (A-1…A-9 + grep index) | ☐ | |
| 5.4 | ≥3 adversarial objections + "What this beta cannot claim" | ☐ | |

## Findings log (append-only)
