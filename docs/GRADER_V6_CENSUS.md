# GRADER V6 CENSUS — Phase 0 of `PR_grader_v6_options.md` → STOP-1

**Status: STOP-1 RULED (owner, 2026-09-27).** Census accepted. The rulings, amendments AM-G1…AM-G12 and additions A-1…A-6 are recorded in **§1a** and are authoritative; §1 below is kept as the record of what was asked. Phase 1 (Track A) and Track B are open; Track C runs separately. C-4b waits on AM-G10 (the read-only role).
*(Original status: STOP. Four STOP conditions that the spec names fired, and one of the spec's premises was false.)*
**Base:** `origin/main` @ `4f331e5` (2026-09-27), read in a clean worktree. Paths below are repo-relative. A few gitignored artefacts exist only in the shared working tree; they were read in place there and are marked **(untracked)**.
**Method:** zero code, zero spend. **No production database was read**: the permission layer refused the read-only query (C-4, and Appendix D has the SQL). Every claim cites `path:line`. Where a fact could not be established, the text says so.

---

## 0. Verdict in one paragraph

The core of v6 holds up against the evidence: options per check, `requires`, charge groups, and one pricer. The owner's SetPeople criterion is real. It is bagrut `q5.ב.c4`, it has ground truth, and the teacher's GT charges **−2 once** for a student who updated `people` through a getter (din, roni → 3/5). Today's compiled plan prices that criterion as `k1` 1 + `k2` 4 with **three ungrouped tariffs, −2 −3 −2**, so every phrase can fire at once against a 4-point component. This is the double penalty and the summed tiers of §1.1, in production code. What must be ruled before Phase 1:

1. The spec's **reduction-terminal** half has no data path. Extraction drops standalone deduction rows. It dropped a real one on this very exam (C-3 → **R-D**).
2. `basis_he` and `confidence` both have non-display consumers (C-8).
3. The **PB-1..12** precedents are ratified *ground-truth* rulings for bagrut, not v5 prompt text. Moving them "verbatim into the CS pack" would put the eval's answers into the system under test (§8 premise).
4. There is **no baseline under the production pin**, so K3 and G-Z are undefined. The cost baseline is already above G-C (C-12).
5. The legacy parity gate cannot pass as specified. v5 prices an **unverified model credit as zero at price time** and **never gates tariffs**. It rounds `counted` **half-up** and carries **typed check amounts** (OD-R2), and v6 §4 has a home for none of these (Appendix A).

---

## 1. What the owner must rule (each has a recommendation)

Grouped by the phase they block. **"Approve all recommendations"** is a valid single reply. Each item is also argued in its census section.

### Blocks Phase 1: these change the types and the pricer

| # | Question | Recommendation |
|---|---|---|
| **Q-1** | **C-3 = R-D for standalone lines (STOP).** There is no path by which a standalone deduction row reaches a contract. The one real instance, bagrut q2.ב «אם החזירו את arr או את מערך העזר יש להוריד נקודה», was dropped at extraction. The owner's own example is **R-A**, inside one criterion. | **Ship v6 on R-A only.** Remove reduction terminals (`TerminalPlan.kind="reduction"`, C8, `HomeStatus`, §10.3's ReductionRow, E3) from this PR. They cannot receive data. Open an upstream item, *"extraction drops standalone deduction lines"*. It is an **FC defect**: four of this exam's deduction lines vanish (C-3). Reduction terminals ship with that fix, under its own ruling (§2.4 forbids touching extraction here). |
| **Q-7** | **`levels` has no source.** The ontology's `INV-5` is *ContractVersionLock*, not levels, and `Criterion.levels` does not exist (ALPHA-GAP A-1). | Build the `levels` shape from **C8-lite's detected band ladder** (`compile.py:624`, text-derived and deterministic). Make no ontology change. Rename "INV-5 level" in the spec to "C8-lite band". |
| **Q-8** | **Where the evidence gate lives.** v5 refuses *model* credit on an unverified span **at price time** and lets any teacher decision through. The amber "unverified ✓" state and `evidence_confirmed` both depend on the claimed verdict staying on the record. v5 **never gates tariffs**, yet v6 §6.3 says to gate faults "identically". | Add a **PRC-1 clause**: in *Resolve*, a **model** selection of a non-default option whose `quote_status ∉ {exact, fuzzy}` resolves to the default, and an **overlay** selection is never gated. The claimed option and its quote status stay on the record. The view carries a per-check `evidence_required` flag, true for every v6 check and every legacy credit check and false for legacy faults. That flag is what keeps legacy parity. |
| **Q-9** | **OD-R2 (2026-09-13) is silently reversed.** §9.2/§10.2 give a check an option picker and nothing else. v5 lets her type an amount on a check, marks `evidence_disputed`, and keeps a comment per check (all frozen into `ContractCheck`). | Make the overlay record per check `{option_id?, amount?, comment?, evidence_disputed?}`. `amount` is allowed on credit checks only, bounded and on the grid (OD-4 a unchanged). The picker offers «ניקוד אחר…». Without this, legacy drafts that carry typed amounts fail parity. |
| **Q-10** | **`note_only` observations disappear.** The spec's mapping is `note_only` → `notes_he`, which is guidance only. v5 records the observation per student («לא להוריד, לכתוב הערה»), and hobby GT writes it for **5/5** students on `q2.ב.c4.s3`. | Add a zero-valued **`note` role**: options `none` / `observed`, both 0, never priced, excluded from V12/V13. The teacher's «לכתוב הערה» stays a fact on the paper. |
| **Q-11** | **OD-20/OD-21 folds vs V14's three dispositions.** The compiler already consumes some phrases: a «- N נק'» value marker, and a deduction equal to its own component's value. | Keep OD-20 and OD-21 as **Stage-1 rules applied before a marker exists**, as owner-ratified compiler rules. Record them in `PlanDraft` telemetry. V14 then governs only real markers. Today they fold hobby q1.ב.c6, q1.ג.c6, q1.ג.c7 and bagrut q5.א.c0, q6.c0, plus the q1.ב.2.c0 value. |
| **Q-17** | **`count` values.** V12's "values unique, strictly decreasing" contradicts `floor_to_grid(P·k/N)`, which repeats values when N is large relative to P. v5 also prices `counted` with **ROUND_HALF_UP** (E8: v5 gives 2.0 where §3.3 gives 1.75). | Exempt `count` from V12's uniqueness clause, because options are counts and the label says k/N. **Legacy** count options carry v5's half-up values as data, and **new** plans floor. One pricer and no branch; the two populations differ only in their data. |

### Blocks Phase 2

| # | Question | Recommendation |
|---|---|---|
| **Q-5** | **The PB-1..12 premise is false (STOP-grade).** They exist **only** as notes inside the seven bagrut GT files. PL-4, PL-6 and PL-7 exist nowhere. The v5 verifier prompt carries PL-9, R-1 and C-1 and nothing else. | The CS pack gets v5 verifier rules 3–5 plus rule 6's PL-9, R-1 and C-1 clauses **verbatim** (the real "proven v5 clauses"). It also gets `constitution.py`'s general clauses (PL-1, PL-2, PL-3, PL-9, PL-10, R-α, R-β, A-6, charge-once, credit-once, P-A), which were written as general policy. **No PB-\* enters any prompt**: they are class-4 exam-specific rulings (`constitution.py:91-95`), and on bagrut they are the answer key. |
| **Q-12** | **The plan store already exists** (`grading_plans`, migration 026). It is keyed by **content hash**, and OD-W4 ratified that a recompile of unchanged content reuses its plan. The spec's key `(rubric_contract_version, config_hash)` would re-plan on every save, because every compile mints a fresh UUID. | **Extend 026's table** in migration **034**: add `config_hash` and `plan_hash`, and make the partial unique `(contract_sha256, config_hash) WHERE live`. `plan_store` stays the only writer. Put `graded_tests.plan_hash` in the same migration. |
| **Q-14** | **"Thinking budget" does not exist on Sonnet 5.** `budget_tokens` returns 400. Only `thinking: {type: "adaptive"}` plus `output_config.effort` exists. Opus 5.5 (`claude-opus-5-5`, $4/$20) **rejects forced `tool_choice`**, cannot disable thinking, and defaults to effort `medium`. | Pre-register an **effort level**, not a budget: §5.5, §13.3 and §13.4's thinking-on arm. The planner uses native structured outputs (`with_structured_output(method="json_schema")`, supported by the pinned `langchain-anthropic==1.4.0`). Add an Opus 5.5 card to the registry and to `plan_compiler/models.py`. Extend `build_chat_model` with Anthropic thinking/effort and leave the verifier's parameters byte-identical. |
| **Q-18** | **The grep test and pack layout.** The real keys are `computer_science`, `mathematics` and `english`, not `"cs"`/`"math"`. About 25 literal sites already exist outside `app/subjects/`, in extraction, transcription, models and API defaults. Profiles are **modules**, not folders. | Scope the grep test to the v6 grading core (plan types, compiler stages, pricer, validators, verifier and explainer contracts) and use the real keys. Turn each `profiles/<key>.py` into a `profiles/<key>/` package with planner, verifier and explainer fragments and a precedents file. `registry.get_profile` stays the only lookup. |
| **Q-19** | **"grader-v6" is already a name.** It is a **killed** prompt from 2026-08-30 (`GRADER_V6_ARTIFACT.md`, runs `*_sonnet5-v6*`). | Keep `grader-v6.0`, since it is named in the spec, and add one line to `GRADER_V6_ARTIFACT.md` stating that the name was reused for a different architecture. |

### Blocks Phase 3 and 4

| # | Question | Recommendation |
|---|---|---|
| **Q-2** | **`basis_he` has a non-display consumer (STOP).** It is fed to the **student-feedback LLM** (`agents/feedback/prompt.py:84-85`). | Feedback reads the **selected option label** (teacher-grounded, observable), `absence_pointer_he` (the replacement for not_met's basis) and the verified quote. Bump `FEEDBACK_PROMPT_VERSION`. |
| **Q-3** | **`confidence` has non-display consumers (STOP).** They are the eval's calibration ECE (`reporting.py:173`, reported only and never gated), the eval-only cascade router (`grader_cascade.py:83`), and the legacy panel's sort order (`GradedTestReviewPanel.tsx:381-382`, v3 only). CLAUDE.md §15's *confidence-triggered verification* would lose its input. | Drop it. Park the §15 item explicitly, as "v6 has no confidence; revisit with a calibrated signal". The eval reports ECE as `n/a (v6)`. |
| **Q-13** | **A second rollout knob.** `GRADER_ARCHITECTURE ∈ {v3, v5}` already exists (`config.py:78`, `grader_selection.py:33-38`). | Use one knob, `GRADER_ARCHITECTURE ∈ {v3, v5, v6}`, default `v5`. `GRADER_STACK` would be the same concept in a second place (§0.4). |
| **Q-15** | **OD-R1 vs §15's "never retry content".** OD-R1 (2026-09-10) re-grades a failed scope **once on any exception, parse failures included** (`grader_v5.py:316-357`). | Keep OD-R1 for the v6 verifier: it is a later owner ruling, backed by evidence (graded_test e372e6f1). Fix §15's text. The explainer stays no-retry-on-content, as specified. |
| **Q-16** | **Closed-world handling.** An unknown check id is an **ERROR** annotation in v5 (`grader_v5.py:184-192`), and only `llm_failure` is teacher-resolvable (`graded_test_contract_compiler.py:143-184`), so approval is a dead end. v5 resolves duplicates silently (`:194`). | In v6, record unknown ids and duplicates as the existing **`CLOSED_WORLD_VIOLATION`** flag plus a **WARNING** annotation. They describe the model, not the student, and must never block her signature. |
| **Q-21** | **"No points in the draft" has consumers.** v5 persists `points_awarded` at every level. Readers include the runner's selection scoring (`grading_runner.py:216-226`), `app/scripts/revalidate_quotes.py` (it re-prices and rewrites), the approval gate's v3 fallback, the eval scorer (`tests/grading_eval_suite/scoring.py:84-94`) and the feedback renderer. | Phase 4 moves every reader onto `to_v6_view` → pricer. `revalidate_quotes` stays v5-only, and a v6 equivalent is a follow-up (a pure re-validation, since v6 stores no points to heal). The row columns `total_score` and `percentage` stay, written by the pricer. |
| **Q-20** | **E3 and E10 premises.** SetPeople is one criterion (R-A), P = 5, with −2/−3/−2 in two lines (the DOCX cell has 4 paragraphs). E3's "rows R1..R3" do not exist. | Rewrite E3 as a synthetic vector *only if* Q-1 keeps reduction terminals. E10 uses the **real** `q5.ב.c4` text, and its assertion is "at most one charge among the three phrases for any verifier selection". The planner's grouping decides that; the recorded output is the fixture. |

### Blocks Phase 6

| # | Question | Recommendation |
|---|---|---|
| **Q-4** | **C-4 needs production reads**, and the permission layer refused them. Three things wait on them: the v3-era **STOP condition**, the **R-C scan** (a deduction row extracted as a *positive* criterion would be R-C), and the G4 parity **snapshot**. | Authorize the read-only queries in Appendix D (they run inside a `READ ONLY` transaction), or run them yourself. |
| **Q-6** | **No baseline exists under the production pin.** A3 was blocked before spend because the compiled plan cannot express din `q2.א.c0` = 4. **Bagrut was never graded by any configuration.** The only Sonnet baselines are hobby-only, on the *hand* plan with grader-v5.3. Their cost, **$0.156–0.160 per test**, already exceeds G-C's **$0.15** hard bar before any explainer spend. | Pre-register one **baseline run**: production pin (grader-v5.4 + compiled routed+segmented plan), 12 fixtures, k=3, about $6, with the expressibility guard reporting instead of refusing *for this run only*. K3 and G-Z then have a comparator measured on the same fixtures. The owner re-confirms G-C, or rules that the explainer's cost is measured separately. |

---

## 1a. STOP-1 rulings (owner, 2026-09-27) — authoritative

Recorded verbatim in substance. Code comments and RUNLOG cite the **AM-G** and **A-** ids. The spec (`PR_grader_v6_options.md`) carries the same amendments in its new §2.5 and inline, patched in the same change set; the spec stays untracked under the owner's 2026-09-09 ruling that specs live outside the public repo (`.gitignore:44-53`).

### Blocks Phase 1

| Q | Ruling |
|---|---|
| **Q-1** | **APPROVED + AM-G1.** v6 ships on in-criterion deductions (R-A) only. **Removed:** `TerminalPlan.kind="reduction"`, C8, `CheckOption.home_terminal_id`, `HomeStatus` and every home status, §10.3 ReductionRow, E3. **Kept:** markers with `candidate_anchors`, planner anchoring (S-4) and V18, because parent-level phrases need them (hobby q2.ב.c4, −3). **Extended in this PR:** C1's patterns gain «יורדו», «ירדו», «הורדת» and worded amounts («נקודה», «חצי נקודה», «שתי נקודות», «שלוש נקודות»), red-first on a phrase list drawn from both exams' markdowns. A pattern is never widened to make a plan pass. Standalone deduction lines are **Track C**, not this PR. |
| **Q-7** | **APPROVED.** The spec is fixed: INV-5 is ContractVersionLock. Where the spec says "levels", read the **C8-lite band ladder**. |
| **Q-8** | **APPROVED + AM-G2.** The evidence gate lives in the pricer's Resolve step, with per-check `evidence_required`. New verifier rule **V-2b**: "For a fault that is an omission, quote the code where the missing element belongs." |
| **Q-9** | **APPROVED + AM-G3.** The overlay record per check is `{option_id?, amount?, comment?, evidence_disputed?}`. A typed amount on **any** check of a terminal makes that terminal's reasoning line teacher-decided, exactly like a terminal override: no explainer call. Typed amounts are part of the selection signature. |
| **Q-10** | **APPROVED.** A zero-valued `note` role. Observed notes render on expand as «הערה: {label}» and are passed to the feedback prompt. |
| **Q-11** | **APPROVED.** OD-20/OD-21 folds run as Stage-1 rules before a marker exists; V14 governs only real markers. |
| **Q-17** | **APPROVED + AM-G4.** Count is exempt from V12's uniqueness clause. **One rounding rule for every value builder, new and legacy: ROUND_HALF_UP onto the grid** (count and partial). This replaces §3.3's `floor_to_grid`. The partial-collapse rule is unchanged. |

### Blocks Phase 2

| Q | Ruling |
|---|---|
| **Q-5** | **APPROVED + AM-G5.** The CS verifier fragment = v5 verifier rules 3–5 + rule 6's PL-9, R-1 and C-1 clauses, verbatim; **no new verifier text in this PR**. `constitution.py`'s general clauses (PL-1, PL-2, PL-3, PL-9, PL-10, R-α, R-β, A-6, charge-once, credit-once, P-A) feed the **planner and the explainer only**, and `constitution.py` becomes live code (closes D-10). **No PB-\* in any prompt, ever**: `test_no_pb_rulings_in_any_prompt` greps every assembled prompt. |
| **Q-12** | **APPROVED + AM-G6.** Migration 034 extends `grading_plans` (`config_hash`, `plan_hash`) and also **drops** `idx_grading_plans_one_live_per_contract`, replacing it with a partial unique on `(contract_sha256, config_hash) WHERE live`, so v5 and v6 plans coexist during rollout. It **backfills `config_hash` on existing rows with a constant v5 key**. `PLAN_WAIT_S` (240 s) is reused; the spec's `PLAN_BUILD_TIMEOUT_S` is deleted. |
| **Q-14** | **APPROVED.** Pre-registered in PREDICTIONS.md: **planner** Sonnet 5, adaptive thinking, effort **high**; **comparison** Opus 5.5, effort **high** (same effort, fair comparison); **explainer arms (§13.4)**: Sonnet 5 without thinking; Sonnet 5 adaptive at effort **low**; Haiku 4.5. |
| **Q-18** | **APPROVED.** The grep test is scoped to the v6 grading core and uses the real keys; profiles become packages. |
| **Q-19** | **APPROVED.** `grader-v6.0` is kept; `GRADER_V6_ARTIFACT.md` gets the disambiguation line. |

### Blocks Phases 3–4

| Q | Ruling |
|---|---|
| **Q-2** | **APPROVED + AM-G7.** Feedback reads the selected option label + `absence_pointer_he` + the verified quote; bump `FEEDBACK_PROMPT_VERSION`. **After pricing and selection marking**, feedback and the explainer run **concurrently**, each under its own `asyncio.wait_for`. **D-6 fixed:** neither runs on excluded scopes. **D-7 fixed:** feedback and explainer tokens count in `total_cost_usd`. |
| **Q-3** | **APPROVED + AM-G8.** `confidence` is dropped. Self-consistency (`sc_n`) is kept: the per-check median is taken **over option values**. CLAUDE.md §15's confidence-triggered verification is parked with the note "future signal = SC disagreement, not verbalized confidence". |
| **Q-13** | **APPROVED.** One knob: `GRADER_ARCHITECTURE ∈ {v3, v5, v6}`. `GRADER_STACK` is deleted from the spec. |
| **Q-15** | **APPROVED.** OD-R1 (re-grade a failed scope once on any exception) stands for the v6 verifier; §15's text is corrected. |
| **Q-16** | **APPROVED.** Unknown ids and duplicates → `CLOSED_WORLD_VIOLATION` flag + a non-blocking annotation. *Since the census, `main` landed GATE-1 / CWV-1..6 (e760e35): the v6 verifier reuses `validator.strip_out_of_world`, which also recovers romanised ids (CWV-6), and its annotation is INFO, not WARNING (CWV-1).* |
| **Q-20** | **APPROVED + AM-G9.** E3 is dropped. **E10** uses the real `q5.ב.c4` text and the recorded planner output, and asserts: (1) for every verifier selection, at most one charge among the three phrases; (2) din/roni's plausible selection (capacity met, update present, one tier) prices **3/5**; (3) yahli (update absent) prices **0**, with every fault inactive. |
| **Q-21** | **APPROVED.** |

### Blocks Phase 6

| Q | Ruling |
|---|---|
| **Q-4** | **AMENDED → AM-G10.** The owner creates a read-only Postgres role (SELECT on `graded_tests`, `rubrics`, `grading_plans` only) and sends its URL. Appendix D runs as written inside `BEGIN READ ONLY … ROLLBACK`. The G4 parity snapshot is taken through the same role and stored **outside the repo**. **C-4b is reported before Phase 4; if it is non-zero, STOP.** |
| **Q-6** | **APPROVED + AM-G11.** The baseline runs **now**, in parallel with Phase 1 (Track B). **G-C is re-ruled:** target **$0.10 per test** (verifier + explainer, with caching, at batch-realistic cache-hit rates). G-C is **ASPIRATIONAL**: it never kills v6 and is never an open-ended loop; it is pursued only through the bounded cost ladder **AM-G12**. The $0.15 figure is retired. |

### AM-G12 — the cost ladder

- **When:** Phase 6, only after the v6 architecture eval is kill-clean.
- **Purpose:** bring cost down while quality holds or improves. Quality is never traded for cost.
- **Adoption rule:** a lever is adopted only if K1, K2 and K4 hold, and K3 and G-Z do not regress versus the v6 winning configuration at k=3.
- **Accounting, per test and per component:** verifier and explainer, cached vs uncached; feedback, from production data after D-7; planner, per rubric (amortized); the v5 baseline under the same accounting.
- **Pre-registration P-v6-7:** v6 with the chosen explainer lands ≤ $0.10 per test without CL-3..CL-5. Reason: `basis_he` alone was ~$0.10 of the v5 verifier's $0.156–0.160, and v6 moves the explanation to a cheaper model.
- **Levers, in this order**, one pre-registered trial each (a HYPOTHESIZE line in RUNLOG with the expected $ saving and why):
  - **CL-1** Explainer = the cheapest §13.4 arm that meets the ship conditions (expected: Haiku 4.5). No extra spend: it comes from §13.4.
  - **CL-2** Prompt caching: order verifier and explainer calls so a batch hits the cached prefix (rubric, question, solution, checks); measure the real hit rate on a batch-shaped run.
  - **CL-3** Self-consistency: if production runs `sc_n > 1`, one trial at `sc_n = 1`.
  - **CL-4** Verifier effort: if the production verifier uses thinking (C-1), one trial one step lower.
  - **CL-5** Cheap verifier tier: Haiku 4.5 as the verifier, k=3, kills first (its v5 K1 failure was din's wrong-target answer).
  - **CL-6** Only if no §13.4 arm qualified: one more cheap explainer arm (a Flash-tier model via the existing factory), same ship conditions, recorded payloads.
- **Stop and report when any one holds:** (a) the target is met, confirmed at k=5; (b) every lever has been tried; (c) cost-trial spend reaches **$20**. A lever is never re-run with tweaks to chase the target.
- **Report:** cost-by-component table per lever; the quality/cost frontier; the recommended configuration; if still above $0.10, what each untried or rejected lever would cost in quality and the next cost levers outside this PR (e.g. the feedback model). The owner rules on cutover.

### Additions (ruled now)

| Id | Ruling |
|---|---|
| **A-1** | D-1 is **not** reproduced in the legacy view: a legacy tariff with no verdict maps to `none`. A declared parity exception with its own test, `test_legacy_unverdicted_tariff_is_not_charged`. Every other legacy cell must match exactly. |
| **A-2** | D-3/D-4: v6 vectors (hand-written + generated) are committed and regenerate from a clean checkout. `npx vitest run` joins every phase's evidence bundle. |
| **A-3** | D-8: in Phase 4, `PATCH /draft` **merges** the overlay instead of replacing it whole. Test: a draft save preserves `stamp_position`. |
| **A-4** | GT notes O-1 and O-2: the awards are right and the notes are wrong. Fix the note text only, with an amendment note in each file. Awards untouched. |
| **A-5** | The two hand-plan-only rulings (dan q2.א.c1 −1, yonatan q2.ב.c4.s2 −0.5) are reported in expressibility as **"unwritten rulings"**, separately from planner misses. |
| **A-6** | D-2 dies with the v5 pricer. D-9 is closed by A-4. D-10 is closed by Q-5. |

### Order of work

- **Track A — v6.** Phase 1 starts now (pure; needs no production data), then Phases 2–7 as specced with the amendments above. AM-G12 runs inside Phase 6, after the architecture eval.
- **Track B — measurement, in parallel; lands before REVIEW-2.**
  1. Instrument fixes: **D-5** — commit the bagrut rubric and transcription contracts (per OD-B10, closed 2026-09-23); make `FixtureGT.awarded` Optional; the scorer skips unselected questions. `gates.py` excludes **CONTESTED** cells, encoded in GT metadata (din q2.ב.c4.s2 is the first).
  2. Baseline: production pin (grader-v5.4 + compiled plan), 12 fixtures, k=3; the expressibility guard reports instead of refusing, for this run only; cost per test under AM-G12 accounting; `EVAL_ANALYSIS.md` per the contract. Its results go into REVIEW-2 with the plan renders.
- **Track C — standalone deduction lines.** Separate worktree, separate PR, census first; STOP before design. Trace the four lost bagrut lines; propose extraction keeping them as a scope-level field (never as 0-point criteria); list the ontology and rubric-gold changes for an owner ruling. v6.1 then wires them in as markers with scope candidates.

### Inherited from `main` since the census (not new rulings — applied as standing law)

`e760e35` (2026-09-27, GATE-1 / CWV-1..6 / OD-4) changed v5 semantics the census described:
- **C-8 / Q-16:** out-of-world verdicts are now dropped at grade time by `validator.strip_out_of_world` with a **scope-level** `closed_world_violation` flag and an **INFO** annotation; romanised ids are recovered (CWV-6). Legacy ERROR annotations are skipped at approval (CWV-3). The v6 verifier uses the same function for check ids.
- **OD-4:** a check with no machine verdict is shown undecided and **blocks approval until she decides it** (`_undecided_no_verdict_checks`, gate check 6). v6 keeps this: PRC-1's default is a *display and pricing* default, never a decision, and the v6 approval gate carries OD-4 unchanged. A-1 (legacy unverdicted tariff → `none`) is consistent with it.
- **CWV-5:** no grading string may say «מודל» or name an id; the static scan now covers v6's copy (fallback composer, status lines).

---

## 1b. Open decisions raised after STOP-1 (awaiting the owner)

| # | Raised by | Question | Evidence | Recommendation |
|---|---|---|---|---|
| **Q-22** | Phase 1 (Hypothesis, 2,000 examples) | **PRC-6 cannot hold under §4.2 as written.** Two classes: **(a)** S-3 caps *each* fault at what its behavior earned, so two fault checks that `require` the same credit check can together charge twice its value and eat other credit — raising a 3.5-point behavior from absent to full drops the terminal 3.0 → 0.0; **(b)** PRC-4 keeps a group's charge by largest magnitude *before* the terminal floor, so a charge swallowed by a floor moves, when that fault is cleared, to a terminal where it bites — total 5.00 → 4.25. | Exhaustive search, 6,000 seeded cases × every legal move: **69** violations under the spec's rule (58 raise, 11 fault→none); **0** under the prototype below. Both classes pinned by strict-xfail tests (`test_prc6_two_faults_on_one_behavior`, `test_prc6_charge_group_meets_a_floor`); `prop_total_monotone` is a non-strict xfail until ruled. | **Adopt both.** **Q-22a (S-3 / PRC-3):** *a behavior's faults together never cost more than it earned* — the charges requiring one credit check are reduced, latest plan order first, until their sum ≥ −its value (this is what S-3's own sentence "attempted badly never scores below skipped" needs). **Q-22b (PRC-4):** *a group's one charge lands where it lowers the test total the most; ties to the earliest plan order* — "charged once" then means charged, never silently swallowed by a floor. E1–E10 and the largest-magnitude example price identically. Enumeration is over group members (tiny in practice); the TS mirror enumerates in the same order. |
| **Q-B1** | Track B (stopped at $0) | **The eval's plan tool is not the production pin.** `tools/segment_plan.py` compiles with the compiler default `ROUTE_MIN_POINTS = 4`; production routes at `settings.plan_route_min_points = 3` (OD-24). bagrut: the tool routes 8 monoliths, production 14; hobby: 5 vs 13 — so the committed `hobby_tvshow.routed+segmented.plan.json` (the A3 config's plan) is not the production pin either. | Track B's RUNLOG entry (2026-09-27); dry runs: bagrut P≥3 route $0.080 + segment $0.115, hobby P≥3 route $0.087 + segment $0.063 (real ≈ 2× estimate). | Make the tool read `settings.plan_route_min_points` (tests-only, one line); rebuild both exams' routed+segmented plans at P≥3 (~$0.7), keeping the old hobby artefact under a new name for A3 history; then run the baseline as ruled (~$6–8, under the $12 cap). |
| **TC-1…TC-8** | Track C | Standalone deduction lines: field shape, placement, contract-before-v6.1, class D, package + re-baseline (~$4.7), gold/scorer, grading-eval contracts, concept scope. | `docs/STANDALONE_DEDUCTIONS_CENSUS.md` §1 (a fifth lost line found: `employee_course_select1.md:166`). | As listed there. |

---

## 2. The census, item by item

### C-1 · Production grading today

- **Grader:** `PlanVerifyGrader` (grader-v5) for **every** rubric (`services/grader_selection.py:33-38, 71-110`). The rollback knob is `GRADER_ARCHITECTURE=v3` (`config.py:78`).
- **Model:** `claude-sonnet-5` via Anthropic (`config.py:79-80`). Concurrency is set by `grader_max_concurrent_scopes` = 16 in code (`config.py:104`); CLAUDE.md §12 says production ships 8 on Anthropic. The live Cloud Run environment was **not read** (unknown — would need `gcloud run services describe`, which is a production read).
- **Prompt:** `VERIFIER_PROMPT_VERSION = "grader-v5.4"` (`agents/grader/verifier_prompt.py:54`). Its sha is pinned at `tests/subjects/test_prompt_identity.py:25`.
- **Plan builder:** PLAN COMPILER v2 (`services/plan_build_runner.py`; `compile_contract` → route (Sonnet 5) → segment (Haiku 4.5) → assemble). Models are in `agents/plan_compiler/models.py:27-37`. The version is `COMPILER_VERSION = "plan-compiler/v2.0"` (`compile.py:59`), and `plan_version = "<exam>/compiled-<sha[:12]>"` (`plan_compiler/assemble.py:18, 80`).
- **Plan resolution at grade time:** `grading_runner.py:174-185` → `resolve_plan_for_grade` (`plan_build_runner.py:309`).
- **v5 checks are on the production wire (PR-G1):**
  - `Check` records are *required* whenever a `plan_version` is stamped (`schemas/graded_test_draft.py:450-481`).
  - The generated wire type carries them (`frontend/src/lib/api-types.ts:2519`).
  - The review module renders them (`components/grade-review/CheckRow.tsx:122`).
- **Student feedback (PR-G4)** runs after pricing inside the grade task (`grading_runner.py:231-234`).

### C-2 · v5 plan types and pricer

**Files and classes:**
- `agents/grader/plan_schemas.py`: `CheckKind` (`:39`), `PlanCheck` (`:50-77`), `TerminalPlan` (`:80-91`), `GradingPlan` (`:94-114`), `CheckVerdict` (`:117-139`; decode order evidence → basis → verdict → confidence → units), `ScopeVerificationResponse` (`:142-145`).
- The draft-side record is `Check` (`schemas/graded_test_draft.py:182-223`).
- The pricer runs in two layers:
  - `agents/grader/pricer.py::price_scope` (`:89-316`) builds the flags, annotations and reasoning lines.
  - The **points** always come from the shared composer `services/pricing.py::price_scope_checks_detailed` (`:112-191`), called at `pricer.py:298`. That composer is the one pricer (PR-G5).
- The TS mirror is `frontend/src/lib/pricing.ts` (C-9).

**How each construct is priced (quoted from `services/pricing.py`):**

| Construct | Rule | Where |
|---|---|---|
| `required` met | `earned += points` | `:167-168` |
| `partially_met` | `earned += points × partial_fraction` (default 0.5 per check) | `:169-170`; default at `plan_schemas.py:69` |
| evidence gate | credit only if `quote_status ∈ {exact, fuzzy}`, **or** the teacher overrode that check | `_credited` `:99-105` |
| `tariff` | fires on `not_met` **or** `partially_met` (coerced) | `_fired` `:56-58` |
| `charge_group` | scope-wide pre-pass: the **first firing** member in document order pays the **max** amount fired in the group, and the others pay 0 | `:133-145, 181-186` |
| tariff with no group | `__solo__<check_id>` | `_group` `:108-109` |
| `counted` | `points × units / unit_count`, snapped with the terminal | `:171-180`; units at `:61-75` |
| `note_only` | never moves points (an INFO annotation in `pricer.py:278-290`) | `:187` |
| terminal | `raw = earned − deducted` → clamp `[0, P]` → **ROUND_HALF_UP** onto the grid | `_snap` `:51-53`, `:188-190` |
| typed check amount (OD-R2) | replaces a required or counted check's contribution, ungated | `:159-163` |
| terminal pin (OD-R2) | replaces the whole terminal | `:149-155` |

**V1–V11 → v6:** see Appendix C. One naming collision: **v5 already has a `V12`** (the counted shape, `plan_validator.py:33-36, 224-244`), and v6 reuses the id for OptionShape. v5's V12 retires into v6's V12 count arm. Until the v5 path is deleted, v6 messages carry a `v6:` prefix.

### C-3 · Reduction lines, traced end to end → **(a) R-A · (b) R-D**

**(a) An in-criterion «להוריד N» is R-A.**
1. **Extraction** keeps it verbatim inside the criterion description: "If it is written as part of a criterion line, keep it verbatim inside that criterion's description" (`services/docx_v3/pipeline.py:775`).
2. **Contract:** it is text in `Criterion.description`.
3. **Plan:** C1 `scan_deductions` (`plan_compiler/compile.py:226-276`) turns it into a `tariff` slot on that terminal (`:756-801`). OD-21 folds it when the amount equals its component (`:786-789`); OD-20 reads a «- N נק'» with no verb as a value (`:262-269`); OD-15 infers an amountless «לקנוס» (`:775-781`).
4. **Pricer:** the tariff arm above.
5. **Draft:** a `Check(kind="tariff")`.
6. **UI:** `CheckRow` with the «הורדה» chip (`copy/grade-review.ts:191`).

**The owner's example is this branch.** SetPeople is bagrut `q5.ב.c4`, P = 5. **(untracked)** In the rubric it is `compiled_rubric_bagrut.json:829-840`; in the DOCX render it is one table cell (`tests/rubric_eval_suite/markdowns/bagrut_899371.md:883`):
> «…ועדכון נכון של התכונה people בעזרת SetPeople ו-GetPeople הבדיקת הקיבולת עצמה 1 נקודה אם לא השתמשו בפעולה הפנימית להוריד 2, אם לא השתמשו באף אחת מהן להוריד 3 אם חישבו נכון את סה"כ ולא עדכנו את התכונה (כמובן ע"י setter) להוריד 2»

The compiled skeleton turns this cell into:
- `k1` = 1 point (capacity);
- `k2` = 4 points (the unvalued remainder, `case2_unvalued_fill`);
- three tariffs, **−2 / −3 / −2**, with **no charge group** (`tests/grading_eval_suite/plans/compiled/bagrut_899371.skeleton.json:1753-1807`). The third tariff's span caught only «להוריד 2».

**(b) A standalone deduction line is R-D: it is dropped at extraction, silently.**
1. The extraction prompt says: "Deduction / penalty guidance → … NOT a scored criterion, and NOT question text … a standalone deduction line is neither a criterion nor text" (`pipeline.py:775`). The same rule appears at `:847`.
2. If the model emits it anyway, it carries 0 points and the cleaner removes 0-point rows (`_clean_extraction`, `pipeline.py:1259-1301`; filters at `:1285, :1301`). The ontology also forbids a 0-point criterion (`Criterion.points > 0`, `schemas/ontology_types.py:445`).
3. **A real instance was lost on the eval exam itself.** The bagrut DOCX has a standalone table row with an empty points cell, `| אם החזירו את arr או את מערך העזר יש להוריד נקודה. |  |` (`markdowns/bagrut_899371.md:355`), under q2.ב. It is in neither the contract nor the extraction gold.
4. Three more deduction lines were lost from the same document: `:88` (q1.א.1, −2), `:96` (q1.א.2, −0.5), and `:27` (an exam-wide "no deduction" instruction).
5. Separately, C1's patterns do not match «יורדו», «ירדו», «הורדת», or a worded amount such as «יש להוריד נקודה» (`plan_gen/prompt.py:42-66`). A standalone row would therefore be missed even if it reached the contract.

**R-B does not exist** (no terminal ever has 0 or flagged points). **R-C cannot be excluded without production data**: a deduction row that a model extracted as a *positive* criterion would be R-C. The query is in Appendix D.

**Per the spec: STOP, design nothing for (b).** → **Q-1**.

### C-4 · Legacy drafts → **incomplete: production reads refused**

- The census needs production counts of `graded_tests` by status × `prompt_version` × plan class, plus the number of unapproved v3-era drafts. The read-only query was denied by the permission layer; the SQL is in Appendix D.
- **Code-side facts:**
  - A v3-era draft is one with no `plan_version`; its terminals carry no `checks` (`graded_test_draft.py:450-481`).
  - Such drafts are priced from their **stored** award (`graded_test_contract_compiler.py:543-544, 561-562`).
  - Approved contracts do **not** record `plan_version` (`schemas/graded_test_contract.py:136-157`), so a v6 contract should add `plan_hash`.
- **The v5 → v6 mapping table** is Appendix A. Four rows cannot preserve v5 prices under §4 as written (Q-8, Q-9, Q-17, plus defect D-1 in Appendix E).

### C-5 · Plans: where they persist, and how concurrent builds are prevented

- **Table:** `grading_plans` (`migrations/026_grading_plans.sql:40-67`); ORM `models/grading_plan.py:24-48`.
- **Key:** `contract_sha256` = sha256 of the canonical contract JSON **with `contract_version` blanked** (`services/plan_store.py:46-55`, OD-W4).
- **Concurrency:**
  - The partial unique `idx_grading_plans_one_live_per_contract ON (contract_sha256) WHERE status IN ('queued','building','ready')` (`026:70-72`) decides races. A losing inserter gets the winner's row (`plan_store.py:85-103`).
  - A CAS `queued → building` claim (`:106-123`) allows taking over a stale `building` row (OD-W3).
  - A heartbeat keeps a live build fresh (`:126-131`); liveness is `plan_job_liveness`.
  - The grade path waits up to `PLAN_WAIT_S` (240 s) on a live builder (`plan_build_runner.py:315`).
- **Lifecycle:** append-only. `mark_ready` supersedes the old ready row in one transaction (`plan_store.py:134-160`).
- **Triggers:**
  - eager: three contract-writing endpoints → `kick_plan_build` (`:191-211`);
  - lazy: `resolve_plan_for_grade` (`plan_build_runner.py:309`).
- **Gap vs §5.7:** there is no `config_hash` in the key, so a compiler or prompt bump never forces a rebuild. → **Q-12**.

### C-6 · `SubjectProfile`

- **Location:** `app/subjects/registry.py:28-69`, with one **module** per subject (`app/subjects/profiles/{computer_science,english,mathematics}.py`).
- **Fields:** `key, modalities, extraction_fragment, p1_fragment, verify_fragment, p2_keywords, ontology, rescale_to_exam` (`registry.py:36-43`). The only lookup is `get_profile` (`:86-91`). The stamp rule is `prompt_version(base, profile)`: CS is unchanged, others get `+<key>` (`:94-96`).
- **Fragment assembly:** the verifier *replaces rules 3–5* with the profile's fragment (`verifier_prompt.py:185-227`). Every CS fragment is `None`, so the CS prompt is byte-identical to the baseline (`profiles/computer_science.py:128-130`).
- **Sha pins:** `tests/subjects/test_prompt_identity.py:19-27` pins EXTRACTION, P1, P2 ×2, VERIFIER (`grader-v5.4`, `840aa30b…`) and GRADER_V3. The rule there is "a mismatch is a STOP, never a re-pin" (`:8-11`).
- **Precedent clauses** already exist as data in `agents/plan_gen/constitution.py:38-95`. Nothing imports that module, and it is *dead code*. → **Q-5, Q-18**.

### C-7 · Deductions: the rubric, the markers, the cells

- **The SetPeople rubric is a fixture: bagrut `q5.ב.c4`** (C-3), and it **has GT** in 7 cells.
  - din: 3/5, «update assigns to a getter's return value — PB-3, no setter → −2»;
  - roni: 3/5, «One defect, one charge, −2»;
  - yahli: 0/5, absent;
  - four students did not select Q5 (`tests/grading_eval_suite/benchmarks/gt/bagrut_899371/*.gt.json:406`).
- **Its amounts are −2 / −3 / −2**, not the §4.5 illustration's −4 / −2 / −3.
- **Marker inventory** (Stage 1 run over both contracts, pure and zero-spend): hobby has **12 tariff markers + 1 note, 3 folded**; bagrut has **9 tariff markers + 2 notes, 2 folded, 1 value**. The full per-terminal list, and the GT cells where each fault fired, are in Appendix B. **The deduction cell set D is 26 hobby (11 unfolded + 15 folded) + 9 bagrut cells**, with folded and control cells listed separately.
- **Faults the rubric does not state.** Two hobby GT cells rest on *owner-ruled* tariffs that exist only in the hand plan: dan `q2.א.c1` −1 (`plans/hobby_tvshow.plan.json:689`) and yonatan `q2.ב.c4.s2` −0.5 (`:965`). Under D-LAW-2 the planner cannot invent them, so they will show up as expressibility misses unless a partial expresses them.
- **GT observations.** These were not edited, and both are reported for the owner:
  - **O-1:** `bagrut_899371/itay_kraft.gt.json:230-235` (q3.ב.c2) cites a −1 tariff «…בתוך הלולאה ובכל פעם מחדש להוריד 1» as "first application", but the award is **2/2**.
  - **O-2:** `bagrut_899371/din_ezra.gt.json:390-395` (q5.ב.c2) cites «אם הלולאה לא רצה על כל המערך 3 נק'» → "−3", but the award is **5/6**.
  - Neither quoted phrase appears in the contract, the DOCX render or the extraction gold. Both awards agree with the contract's text. The notes matter because G-D1 and G-D2 are scored on D.

### C-8 · v5 post-validation and the `basis_he` / `confidence` consumers

| Event | v5 handling | Where |
|---|---|---|
| unknown `check_id` | dropped, with an **ERROR** `closed_world_violation` annotation, which blocks approval (only `llm_failure` is teacher-resolvable) | `grader_v5.py:183-193`; gate `graded_test_contract_compiler.py:368-381` |
| duplicate verdict | first occurrence wins, **silently** (no flag) | `grader_v5.py:194` |
| missing verdict | recorded as `not_met` at confidence 0 with `FlagReason.UNVERIFIED_CHECK` and a WARNING `unverified_check` annotation | `pricer.py:142-159, 166-177` |
| quote validation | `quote_match_status` (an exact local-alignment DP, 0.85 bar, since 2026-09-15) → `exact` / `fuzzy` / `not_found` | `grader_v5.py:368`; `validator.py` |
| `not_found` policy | **at price time**: model credit is refused and flagged `EVIDENCE_UNVERIFIED` with a WARNING annotation. **Tariffs are not gated.** A teacher override bypasses the gate. | `pricing.py:99-105`; `pricer.py:183-200` |
| scope failure | re-graded **once on any exception** (OD-R1). A second failure yields a zero outcome that keeps its checks, built by the one pricer. | `grader_v5.py:316-357, 258-293` |
| self-consistency | `sc_n` odd; per-check median verdict | `grader_v5.py:104-106, 197-203` |

The `FlagReason`s used are `UNVERIFIED_CHECK`, `EVIDENCE_UNVERIFIED`, `TARIFF_COERCED`, `FUZZY_MATCH` and `BOUNDS_CLAMPED` (`ontology_types.py:120-133`).

**Consumers of `basis_he` — STOP:**
- the **student-feedback prompt** (`agents/feedback/prompt.py:84-85`): a non-display LLM input;
- review display (`CheckRow.tsx:205-208`);
- the reasoning line (`pricer.py:210-211`).

**Consumers of `confidence` — STOP:**
- eval calibration ECE (`tests/grading_eval_suite/reporting.py:173-187`; reported, never gated);
- the Stage-3 cascade router (`grader_cascade.py:83-84`; eval-only, since `build_grader` never builds it);
- `ScopeOutcome.min_confidence` (`graded_test_draft.py:344`), used by the legacy v3 panel's sort (`GradedTestReviewPanel.tsx:381-382`) and its «ביטחון נמוך» chip (`:216-219`);
- the new review module never reads it (`api-types.ts:2503`: "never rendered").

→ **Q-2, Q-3**.

### C-9 · Frontend

- **Review components** (`frontend/src/components/grade-review/`):
  - The criterion row is inline in `ScopeSection.tsx:147`. Its quote button is at `:432-458` and its points field (`PointsInput`) at `:469-484`.
  - The check row is `CheckRow.tsx:122`. It shows chips for tariff / `not_found` / disputed (`:135-142`) and a quote button when `canHighlight` (`:308-334`).
  - The verdict glyph is `VerdictButton.tsx:68`, with hardcoded ✓/½/✗ at `:35-41`.
- **Chip copy:** there is **no copy for full / partial / zero**, so the spec's «מלא» / «חלקי» / «לא מולא» are new strings. The deduction copy is `RV_TARIFF_MARK` «הורדה», `RV_TARIFF_NONE` «ללא הורדה», `RV_TARIFF_UP_TO`, and `RV_TARIFF_ONCE` «נספרה פעם אחת» (`copy/grade-review.ts:191-195`).
- **Highlight state machine:** `utils/grade-review-highlight-machine.ts:74-128`. It is keyed by `PinTarget = {kind: 'check' | 'criterion', id}` (`utils/evidence-highlight.ts:54-56`). The client locates the quote string itself (`:395-439`), and `canHighlight` is derived in `grade-review-model.ts:551-555`.
- **TS pricer:** `lib/pricing.ts` (`priceScopeChecksDetailed` `:321-384`). Numbers travel as decimal strings; internally they are exact BigInt `Dec` values (`lib/decimal.ts:24-218`), with `rounding_mode` required to be `half_up` (`pricing.ts:253-274`). It mirrors every rule in C-2. `evidence_confirmed` works *indirectly*: a confirmed record keeps the check id in `overriddenCheckIds`.
- **Vectors:**
  - `backend/tests/fixtures/grade_review/pricing_vectors.json` holds 190 vectors from run `20260830-205954`, generated by `backend/scripts/gen_grade_review_fixtures.py:105-129`. They cover only required, tariff and note_only; there is no `charge_group` or `counted`.
  - `pricing_vectors_typed.json` comes from `scripts/gen_typed_points_vectors.py`.
  - Consumers: `test_grade_review_fixtures.py:58-98` and `frontend/src/lib/pricing.test.ts:54-116, 466-496`.
- **Overlay:** `utils/verdict-cycle.ts:55-85`, saved by `saveGradeReviewDraft` (`lib/api.ts:2214-2223`) as `PATCH /draft {overrides, client_totals}`. The server's `pricing_mismatch` produces a toast (`page.tsx:235-237`).

### C-10 · Post-draft writers of `draft_json`

1. **The runner** (`grading_runner.py:260`) is the only writer of content.
2. **`PATCH /draft`** (`api/v0/grading.py:649-773`) **replaces `teacher_overrides` whole** (`:746`).
3. **`/approve`** (`:776-904`) replaces the overlay, freezes the contract and writes totals in one commit.
4. **`PATCH /stamp_position`** (`:966-1049`) merges only `teacher_overrides.stamp_position`, including on approved rows.
5. **`/feedback/regenerate`** (`:1243-1314`) rewrites only the `feedback` key.
6. **Batch rename with `stamp_position_default`** (`api/v0/batch_grading.py:896-997`) is the **only plain-dict writer**, and it has no status filter (`:963-971`; `returned_exam.py:528-546`).
7. **`extend_chain`** inserts a successor row (`graded_test_revision.py:28-122`). `manual_edit` copies `draft_json` verbatim.
8. **`app/scripts/revalidate_quotes.py --apply`** re-validates quotes, **re-prices points, rewrites flags, annotations and reasoning**, and rewrites totals (`:66-206`).

**Interaction with v6:**
- Writers 2–7 touch the overlay, feedback and stamp keys and never the v6 check content. That is safe provided the v6 draft keeps those keys.
- Writer 8 is v5-specific (Q-21).
- There is no row lock or version check anywhere, so last write wins.

### C-11 · PR-G4 post-pricing LLM call

- **It exists:** `agents/feedback/runner.py:22-66` `attach_feedback` → `agent.py:54-100` `FeedbackAgent.generate`.
- **Model:** `claude-sonnet-5` (`config.py:90-91`), built through `build_chat_model` with the 240 s timeout (`llm_factory.py:46, 60`) and `max_retries=0`. It is a single `ainvoke` with no retry, and it has **no `wait_for`** around it (the row budget covers grading only).
- **Failure:** `feedback=None` plus an INFO `feedback_unavailable` annotation.
- **Input:** `render_scope_for_feedback` (`prompt.py:63-87`), built from the v5 `Check` records (verdict, kind, quote_status, `basis_he`), per scope.
- **Output:** stored at `draft_json.feedback` and frozen into `contract_json.feedback` at approval.
- **For §7.8:** reuse the factory, but the explainer needs its own `asyncio.wait_for(EXPLAINER_TIMEOUT_S)`, which the feedback call lacks. Do not merge the prompts.
- **Two side notes:**
  - Feedback runs **before** the `excluded_by_selection` re-marking (`grading_runner.py:231-244`), so excluded scopes receive feedback text.
  - Feedback tokens are not in `total_cost_usd` (`:253-254`).

### C-12 · Eval suite, baselines

- **Entry point:** `tests/grading_eval_suite/runner.py:718-745`. `_load_plan` reads a plan **file**, pins its sha to the fixture, validates it, and runs the pre-spend expressibility guard (`:334-385`). The runner never touches `plan_store`.
- **Grading and scoring:** grading goes through `PlanVerifyGrader` (`:447-450`). Scoring uses `scoring.py:118-417`, with the real `score_with_selection`. The kills and the P→Z cross-tab come from `tools/gates.py:59-117` (`K2_BAR = 6/245`, `K4_BAR = 8.25`, `GA7 = 0.15/0.10`).
- **Expressibility:** `plan_expressibility.py:32-78`, used by the runner guard, `test_plan_expressibility.py`, and `test_compiled_plan_guard.py` (488 judgments).
- **GT:** per terminal, net award plus a free-text note. It has **no per-deduction cells** (`schemas.py:27-69`).
- **The bagrut eval cannot run from `main`:**
  - Its rubric contract and 7 transcription contracts are gitignored (`backend/.gitignore:164`); they exist only in the shared tree.
  - Its GT uses `awarded: null` for unselected questions, while `FixtureGT.awarded` is required (`schemas.py:30`).
- **Baselines.** All numbers below were recomputed at $0 from local run outputs with `tools/gates.py`:

| Run | Configuration | K1 | K2 | K4 | K3 (GA-2) | **GT-PARTIAL→AI-ZERO** | $/test |
|---|---|---|---|---|---|---|---|
| `20260830-130644_sonnet5-v5` (PF-1, k=3) | hand plan v5 · grader-v5.3 · hobby ×5 | 45/48 ✗¹ | 0/147 | 4.75 | 0.8596 | **44/147** | 0.1562 |
| `20260831-154421_sonnet5-v5` (k=2, dial 16) | same | 31/32 ✗¹ | 1/98 | 3.75 | 0.8605 | **25/98** | 0.1569 |
| `20260831-153958_sonnet5-v5` (k=2, dial 5) | same | 32/32 | 3/98 ✗ | 2.25 | 0.8553 | **26/98** | 0.1596 |
| `20260908-194621_sonnet5-v54-compiled` (A3) | **production pin** | — blocked before spend: din `q2.א.c0` = 4 is unreachable under the compiled plan | | | | | |
| E7 / E8 (`20260827-*_gpt-4o`) | gpt-4o, no plan | 80/80 | 2.0% / 2.9% | 14.0 / 8.25 | 0.72 / 0.74 | **72 / 72** of 245 | ~0.07 |

¹ The K1 firings are all the din `q2.ב.c4.s2` cell, which was later ruled **CONTESTED** (`RUNLOG.md:1771-1775`). `gates.py` does not exclude it.

- §2.3's "72 GT-partial→AI-zero cells" is a **gpt-4o, pre-v5** number. Under Sonnet with v5.3, P→Z is 25–30% of GT-partial cells.
- **Bagrut has no grading run under any configuration** (no `results/*/drafts` hold a bagrut draft). → **Q-6**.
- **Documents:** the RUNLOG is `tests/grading_eval_suite/RUNLOG.md` and the predictions file is `PREDICTIONS.md`. §7 of the v6 spec cites "the grader-v5 mission doc (its §13 grading constitution)", but that constitution actually lives in `MISSION_grading_eval_suite_v0.md:139-190`, marked "RECORDED, NOT AUTHORIZED". The grade-review backend and frontend specs are **not in the repository or its history**.

### C-13 · Does the signed exam show reasoning to students? **No.**

- `render_appendix_pdf` (`services/returned_exam.py:225-307`) renders per-scope **feedback** text and the summary.
- With `appendix_include_criteria` set, it also renders per-terminal description, awarded and possible (`:274-281, 611-651`).
- It never reads `ai_reasoning`, checks or `basis_he`.

So §7.8's second bullet is vacuous today. If the explainer's line were ever to reach the student, that would be a new decision.

### C-14 · Purge rule for children of `graded_tests`

- **Rule:** every FK *out of* the five student-data tables is **ON DELETE NO ACTION, never CASCADE** (`docs/PURGE_CENSUS.md:62, 89, 490, 497-499`; migration `032`).
- **Execution:** the purge deletes rows children-first in one transaction, with the student row last (`services/erasure/execute.py:70-122`).
- **For `criterion_explanations` to comply, all nine steps are required:**
  1. The FK is NO ACTION. Add the table to `FIVE` in `tests/services/erasure/test_fk_graph.py:27` so PRV-8 covers it.
  2. Add the table to `registry.PURGED_TABLES` (`registry.py:30-32`).
  3. Add a `PII_REGISTRY` entry for `text_he`, which holds quotes of student work (`:41-99`; checked by `test_pii_registry.py:21-62`).
  4. Add discovery in `plan.py`, `WHERE graded_test_id = ANY(:g)` (`:143-144, 228-234`).
  5. Add a DELETE step **before** the `graded_tests` step (`execute.py:79-87`).
  6. Add a `verify.py` `_ROWS` entry (`:61-67`). Without it, `:74` raises `KeyError`.
  7. Add seed and fixture counts (`tests/services/erasure/seed.py:345-369`).
  8. No GCS objects are involved, so no PRV-11 ruling is needed.
  9. Add rows to `docs/PURGE_CENSUS.md` §1 and §2.

**Migration numbering:** the head is **033**, so v6's migrations are **034+**.

---

## Appendix A — draft legacy mapping v5 → `DraftV6View` (for approval at STOP-1)

| v5 draft element | v6 view | Parity with `services/pricing.py` |
|---|---|---|
| `required` check, points P, `partial_fraction` f | credit check. Options: `full` = P; `p1` = P·f (always present, because v5 always admits `partially_met`); `absent` = 0. Shape: `ladder` | ✓ (V4 keeps P·f on the grid) |
| verdict met / partially_met / not_met | model option `full` / `p1` / `absent` | ✓ |
| `quote_status` on a credit check | carried. **The gate must be in the pricer, per Q-8.** | ✓ only with Q-8 |
| `tariff` T, `charge_group` g | fault check. Options: `none` 0; `f1` = −T. Same group, `requires = None`, `evidence_required = false` | ✓ only with Q-8. v6 gates faults and v5 never did. |
| tariff verdict not_met or partially_met | `f1` | ✓ |
| tariff verdict met | `none` | ✓ |
| charge-group dedup | v5: first firing member pays the max. v6: the largest capped charge; ties go to earlier plan order. | ✓ **when the amounts in a group are equal.** Compiled plans only merge equal amounts (`compile.py:862`), and parent and scope groups have one member each. Unequal groups can only come from the **hand** plan; checking that needs the production snapshot (Q-4). |
| `counted` N, `units_correct` | `count` shape `n{k}`. Values for **legacy rows** = v5's half-up snap of P·k/N | ✓ only with Q-17 (§3.3's floor would change E8-style cells) |
| counted partially_met with no units | `n0` | ✓ |
| `note_only` | `note` check (Q-10), or `notes_he` | ✓ (0 points either way) |
| missing verdict (recorded as `not_met`) | by recorded verdict: credit → `absent`; **tariff → `f1`, charged** | ✓ — this reproduces defect D-1 faithfully |
| `TeacherOverride.verdict` | overlay option, by the same map | ✓ |
| `TeacherOverride.points_awarded` (OD-R2) | **no home in §9.2** | ✗ without Q-9 |
| `evidence_confirmed` | overlay selection equal to the model's option (an overlay entry is never gated) | ✓ with Q-8 |
| `evidence_disputed`, per-check `teacher_comment` | **no home in §9.2** | display and contract only (Q-9) |
| `terminal_points` | terminal award override | ✓ |
| terminal clamp and snap | v6 floors in reverse order, and `awarded = clamp`. All legacy option values sit on the grid, so v5's snap is a no-op. | ✓ |
| v3-era draft (no checks) | no check view: display from the stored award | STOP if any is unapproved (C-4 count pending) |

## Appendix B — markers and the deduction cell set D

Stage 1 of the current compiler was run over the two contracts, pure and zero-spend. GT line numbers point at the `terminal_id`. The hobby GT is at `benchmarks/gt/<s>.gt.json`; the bagrut GT is at `benchmarks/gt/bagrut_899371/<s>.gt.json`.

**hobby_tvshow:**

| Terminal (P) | Marker (amount) | Disposition today | GT cells where the fault fired |
|---|---|---|---|
| q1.ב.c6 (2) | «הציגו … בלי לבדוק האם יש מקום» (−1) | folded (OD-21) | all 5 (1/2 each) |
| q1.ג.c3 (3) | «לולאה עד length ולא בדקו … null» (−1) | tariff | dan, din, yonatan |
| q1.ג.c6 (2) | zero-guard (−1) | folded | all 5 |
| q1.ג.c6 | math error (−0.5) | tariff | din |
| q1.ג.c6 / c7 | «לא המירו לממשי» (−0.5, once) | tariff, group `q1.ג:once:c2ce2a97` | none |
| q1.ג.c7 (2) | zero-guard (−1) | folded | all 5 |
| q1.ג.c7 | math error (−0.5) | tariff | din, yonatan |
| q2.ב.c3.s0 (3) | start at 1 (−0.5) · no getter (−1) · upper bound (−0.5) | 3 tariffs, no group | no getter: dan, din, yonatan |
| q2.ב.c3.s2 (2) | direct `chl` (−1) | tariff | none. **Control:** din 0/2 has the behavior absent, so the fault must be inactive (E1). |
| q2.ב.c3.s3 (5) | direct `rate` (−1) | tariff | none. **Control:** din 0/5 is absent. |
| q2.ב.c4 (parent) | «חיפשו את המקסימום…» (−3) | homed on s3, group `q2.ב:q2.ב.c4:d1` (OD-10/23) | none |
| q2.ב.c4.s3 (3) | «לא להוריד, לכתוב הערה» | note_only | **noted for all 5** (Q-10) |
| q2.ג.c0.s2 (3) | no getter (−1) | tariff | dan, din |
| *(no marker)* q2.ב.c4.s2 | the "symmetric start-index" tariff | — (a hand-plan ruling) | yonatan 1.5/2 |
| *(no marker)* q2.א.c1 | "Owner-ruled −1" | — (hand plan only) | dan |

**bagrut_899371 (untracked contract):**

| Terminal (P) | Marker (amount) | Disposition today | GT cells where the fault fired |
|---|---|---|---|
| q4.ב.c4 (5) | «לקנוס פעם אחת … null» (inferred −1, once) | tariff, group `q4.ב:once:2aa8e26f` | din, itay, raz, roni, yael (4/5 each) |
| q4.ב.c7 (5) | «להוריד רק פעם אחת» (inferred −1, same group) · «אם טעו פה … 3 רק פעם 1» (−3, own group) | tariffs | none. The 5 cells above are the **charge-once partners** and must **not** be charged here (G-D1). |
| q5.א.c0 (1) | «כל טעות פה להוריד 1» | folded | none |
| q5.ב.c2 (6) | «רצו עד Length ולא בדקו … Null» (−2) · «גבולות הלולאה» (−1) | 2 tariffs | din (−1; see O-2) |
| **q5.ב.c4 (5)** | «לא השתמשו בפעולה הפנימית» (−2) · «באף אחת מהן» (−3) · «חישבו נכון … ולא עדכנו» (−2) | **3 tariffs, no group** | din, roni: −2 once. **Control:** yahli 0/5 is absent. |
| q6.c0 (1) | «כל טעות להוריד 1» | folded | none |
| q6.c6 (2) | «הדפיסו את הכמות להוריד 2 (או 1?)» → −1 (Case 4) | tariff | raz |
| q3.א.c4 / q3.ב.c2 | «לא להוריד כלום …» | note_only | yahli (q3.א.c4); raz, yahli (q3.ב.c2) |

**D** is the cells in the right-hand column that come from an *unfolded* marker:
- hobby: 3 + 1 + 2 + 3 + 2 = 11 cells, plus the 15 folded cells (q1.ב.c6 ×5, q1.ג.c6 ×5, q1.ג.c7 ×5) for G-D1. **26 in total**, with the charge-once and control cells listed separately.
- bagrut: 5 + 1 + 2 + 1 = **9 cells**, plus the 5 charge-once partner cells.

G-D1 is measured over D plus the partner cells. G-D2 is measured over q2.ב.c3.s0, q5.ב.c2 and q5.ב.c4, the terminals that carry more than one marker.

**How v5 prices SetPeople today.** This is illustrative only, a plausible verdict set rather than a measured run, since bagrut was never graded. For din or roni:
- `k1` met (capacity) = 1;
- `k2` not_met (no SetPeople) = 0;
- t1 «לא השתמשו בפעולה הפנימית» fires, −2;
- t3 «ולא עדכנו את התכונה (ע"י setter)» fires, −2;
- raw = −3 → **clamped to 0**. The GT is **3**.

This is the double penalty and the summed tiers of §1.1.

## Appendix C — V1–V11 → v6

| v5 rule | Where | v6 |
|---|---|---|
| V1 Σ required == P | `plan_validator.py:266-269` | **subsumed by V13** |
| V2 on the grid | `:197-203` | **subsumed by V17** |
| V3 kind shape | `:205-264` | **subsumed by V12** (credit and fault shapes) |
| V4 partial on the grid | `:218-221` | **retired**: partials are `floor_to_grid`, and a collapse is telemetry (§3.3) |
| V5 unique ids | `:150-160` | **kept**; ids are assigned by code (§3.2), so it becomes an assertion |
| V6 totality vs contract | `:162-177` | **kept** (every contract terminal has a `TerminalPlan`) |
| V7 group stays within one scope | `:271-275` | **kept.** C6 group keys are scoped, and the planner sees one scope. Whole-test pricing would dedup across scopes, but no plan can form such a group. |
| V8 fraction in (0,1) | `:215-217` | **retired**: the closed enum `{QUARTER, HALF, THREE_QUARTERS}` |
| V9 quote grounded in its scope | `:83-125, 185-196` | **subsumed by V16** (same NFC and whitespace normalization, `_tight` `:77-80`; keep the calibrated fragment rule) |
| V10 no point text in descriptions | `:74, 181-184` | **kept**: the verifier stays point-blind (§6.1) |
| V11 every detected deduction disposed | `plan_gen/prompt.py:164-170`; an assertion in compiler v2 (`PR_plan_compiler_v2.md:97`) | **subsumed by V14** |
| V12 (v5) counted shape | `:224-244` | **subsumed by v6 V12's count arm and V13** (id collision, C-2) |

## Appendix D — read-only production SQL (NOT run: permission refused)

Run it inside `BEGIN READ ONLY; … ROLLBACK;`. A helper that enforces a read-only transaction is available on request.

```sql
-- C-4a: rows by status x stack
SELECT status, draft_json->>'prompt_version' AS prompt_version,
       CASE WHEN draft_json->>'plan_version' IS NULL THEN '(none: v3-era)'
            WHEN draft_json->>'plan_version' LIKE '%/compiled-%' THEN 'compiled'
            ELSE draft_json->>'plan_version' END AS plan_class,
       count(*)
FROM graded_tests GROUP BY 1,2,3 ORDER BY 1,2,3;

-- C-4b: the STOP condition: unapproved v3-era drafts (leaves only)
SELECT count(*) FROM graded_tests
WHERE status='draft' AND regraded_to_id IS NULL AND draft_json->>'plan_version' IS NULL;

-- C-4c: parity risk rows in unapproved drafts: typed check amounts, confirmations, disputes
SELECT count(*) FILTER (WHERE o->>'points_awarded' IS NOT NULL) AS typed_check_amounts,
       count(*) FILTER (WHERE (o->>'evidence_confirmed')::bool) AS confirmed,
       count(*) FILTER (WHERE (o->>'evidence_disputed')::bool)  AS disputed
FROM graded_tests g,
     jsonb_each(g.draft_json->'teacher_overrides'->'terminals') t,
     jsonb_array_elements(t.value) o
WHERE g.status='draft' AND g.regraded_to_id IS NULL;

-- C-3/R-C scan: criteria whose text opens like a deduction line (a row extracted as a positive criterion)
SELECT r.id, c->>'criterion_id', c->>'points', left(c->>'description', 120)
FROM rubrics r, jsonb_path_query(r.contract_json, 'lax $.**.criteria[*]') c
WHERE c->>'description' ~ '^\s*(אם\s|להוריד|יורד|הורדה|מינוס|[-–]\s*\d)';

-- C-5: plans by compiler/wording
SELECT status, compiler_version, wording_source, count(*) FROM grading_plans GROUP BY 1,2,3;
```

## Appendix E — pre-existing defects found (not v6 decisions; reported, not fixed)

| # | Defect | Evidence |
|---|---|---|
| **D-1** | **A tariff with no verdict is charged.** A missing verdict is recorded as `not_met` (`pricer.py:152`), and `not_met` on a tariff *fires* (`pricing.py:56-58`), so the student pays for a defect nothing verified. This includes every tariff in a crashed scope. v6's PRC-1 fixes it (the default is `none`). Legacy parity reproduces it (Appendix A). | `pricer.py:142-159`; `pricing.py:133-145` |
| D-2 | A fired tariff with amount 0 or None raises `KeyError` in Python, while TS returns 0 (a parity divergence). It is unreachable under V3. | `pricing.py:143-145, 186`; `pricing.ts:300, 372` |
| D-3 | `pricing_vectors_typed.json`, the synthetic draft and the `approved_*.json` fixtures are gitignored. The backend and vitest parity tests fail on a clean checkout, and no CI job runs vitest. | `backend/.gitignore:164`; `pricing.test.ts:466-467` |
| D-4 | `pricing_vectors.json` cannot be regenerated from a clean checkout: it needs `--from-run` with untracked drafts. | `gen_grade_review_fixtures.py:51-53, 190` |
| D-5 | The bagrut eval cannot run from `main`: its contracts are gitignored, and its GT nulls conflict with the `FixtureGT` schema. | C-12 |
| D-6 | Scopes later excluded by selection still receive feedback. | `grading_runner.py:231-244` |
| D-7 | Feedback tokens are not counted in `total_cost_usd`. | `grading_runner.py:253-254`; `feedback/agent.py:87-90` |
| D-8 | `PATCH /draft` replaces the overlay whole, and the review page does not send `stamp_position`. A draft save may therefore clear a stamp set on a draft row. This is inferred and not reproduced. | `grading.py:746`; `page.tsx:197-201` |
| D-9 | GT notes O-1 and O-2 contradict their awards (C-7). | — |
| D-10 | `constitution.py` is dead code: nothing imports it. | grep |
