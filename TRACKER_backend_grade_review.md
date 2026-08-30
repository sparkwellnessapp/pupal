# TRACKER — Backend · Grade review module v1 (S12)

**Spec:** `PR_SPEC_backend_grade_review.md` (RATIFIED; wins over this tracker on conflict).
**Parent:** `SPEC_grade_review_v1.md` v1.1 — its rulings win over the PR spec.
**Census:** `CENSUS_B0_backend_grade_review.md` (B0 deliverable, complete).
**Protocol per item:** pre-flight census → **red test first** (paste the red output) →
implement inside the scope fence → adversarial self-review → evidence bundle in the phase
report.
**Sanity gate before every "done":** `python -c "import app.main"` · `pytest --collect-only`
· `pytest -q`.

**Scope fence:** no changes to INV-1..4, CW-1, VER-2, RGC-1, LCY-2, ANN-1 semantics;
contracts stay `frozen=True`; the agent never sees a Draft; `GradableTest` never persisted;
awarded points never point-sum-validated at approval; generated TS never hand-edited.

Statuses: `[ ]` todo · `[~]` in progress · `[x]` done (evidence in phase report) ·
`[STOP]` owner gate · `[!]` blocked on a ruling

---

## Phase B0 — census + plans → gate: plans ratified

| # | Item | Status |
|---|---|---|
| B0.1 | Census A/B/D/E/F on the record → `CENSUS_B0_backend_grade_review.md` | [x] |
| B0.2 | Plan: G1 (schema-touching) | [x] `PLANS_G1_G4_G5_…md` → [STOP] ratification |
| B0.3 | Plan: G4 (schema-touching) | [x] `PLANS_G1_G4_G5_…md` → [STOP] ratification |
| B0.4 | Plan: G5 (schema-touching) | [x] `PLANS_G1_G4_G5_…md` (R-2 count = 0) → [STOP] ratification |
| B0.5 | ~~Plan: G7~~ | [x] **DEFERRED by ruling R-1** — audit is next week's PR |
| B0.6 | Open decisions OD-B2..OD-B6 + the four census discrepancies | [STOP] owner |

**OD-B1 is CLOSED** (owner ruling 2026-08-31): gemini-3.1-pro, plan `hobby_tvshow/v3` +
`grader-v5.1`, regression-verified k=2 on 2026-08-31.

---

## Phase B1 — G1, G2, G5, G6 (+ fixtures §1.7)

Gate: fixtures diffed · all G1/G5 tests green from red · codegen committed ·
`pytest --collect-only` + `import app.main` clean.

| # | Item | Red-first tests | Status |
|---|---|---|---|
| B1.1 | **G2** — bounded grading (no schema; unblocked) | `grading-card-has-bounded-exit`, `transient-retry-once-never-on-content`, `all-scopes-failed-marks-row-failed`, `row-budget-bounds-a-hung-grade` | [x] 7 tests green from red; code UNCOMMITTED (mixed files — see below) |
| B1.2 | **G1(a)** — config-driven grader seam (the owed R-4 PR): `GRADER_MODEL_KEY` + plan/prompt pin, `grading_runner` through `llm_factory` | `production-pin-is-config-driven`, `draft-stamps-all-four-versions` | [!] B0.2 |
| B1.3 | **G1(b)** — `PricedTerminal` carries per-check rows → `TerminalOutcome.checks[]` + `quote_status` | `draft-persists-v5-checks` | [!] B0.2 |
| B1.4 | **G1(c)** — contract mirror `ContractCheck` | `contract-mirrors-checks` | [!] B0.2 |
| B1.5 | **G1(d)** — codegen; TS regenerated, drift job green | codegen diff clean | [!] B0.2 |
| B1.6 | **G1(e)** — `scripts/gen_grade_review_fixtures.py` + §1.7 fixture set | `fixtures-regenerate-clean` | [!] B0.2 |
| B1.7 | **G5** — overlay v2, `app/services/pricing.py`, `/approve` mismatch, CW-3 on `check_id`, overlay data migration | `pricer-override-composition` (12 vectors), `override-preserves-proposal-provenance`, `revert-clears-override-and-note`, `approve-rejects-pricing-mismatch`, `cw3-rejects-unknown-check-id`, `overlay-migration-wraps-lists` | [!] B0.4 |
| B1.8 | **G6** — `018_schools.sql` + `users.school_id` + `PATCH /users/me/school` | `override-attribution-joins-resolve` +2, migration applied to TEST db | [x] 3 green from red; **UNCOMMITTED — blocked by migrations 015–017** |

---

## Phase B2 — G3 (measured), G4, G8

Gate: RUNLOG entry for G3 with the prediction scored · feedback lint green on five fixtures ·
batch-feed fixtures match.

| # | Item | Red-first tests | Status |
|---|---|---|---|
| B2.1 | **G3** — `MAX_CONCURRENT_SCOPES = min(scope_count, 16)` behind a flag; measured; `latency_profile[model]` into config | `scope-concurrency-caps-at-scope-count` + RUNLOG evidence | [ ] |
| B2.2 | **G4** — `app/agents/feedback/`, `FeedbackBlock`, regenerate endpoint, contract effective text | `feedback-call-runs-after-pricing-once-per-test`, `feedback-contract-carries-effective-text`, `feedback-stale-derived-from-basis-hash`, `feedback-failure-does-not-block-draft`, `feedback-gender-neutral-lint` | [!] B0.3 |
| B2.3 | **G8** — batch feed §1.5, `opened_at` (migration 019), `look_count.py`, two-stage ETA | `eta-two-stage`, `eta-never-constant`, `look-count-includes-met-with-notfound`, `opened-at-set-once-by-owner-only`, `batch-feed-fixtures-match` | [ ] |
| B2.4 | Page-1 image cache (census E finding — recommend scoping here, owner's call) | — | [STOP] owner |

---

## Phase B3 — DEFERRED (ruling R-1, 2026-08-31)

The consistency audit is out of this PR. `audit_status` ships as the literal
`"disabled"`; no `audit_deltas` table, no `audit_edit` revision kind, no audit
columns in the migration list. Census D already established there is no audit
producer, so nothing is lost by deferring. The rows below are the design record
next week's spec starts from — **do not build them.**

## ~~Phase B3 — G7 (audit applier)~~ [DEFERRED]

Gate: applier property tests · chain tests · guard never fires on the fixture deltas.

| # | Item | Red-first tests | Status |
|---|---|---|---|
| B3.1 | Migrations 020 (`grading_batches` audit cols) + 021 (`audit_deltas`) | migration up/down | [!] B0.5 |
| B3.2 | `app/services/audit_applier.py` — pure `apply(delta, test_state) → Action` | `audit-anchor-rule-rejects-overridden-check`, `audit-apply-silent-on-unopened`, `audit-apply-marked-on-opened` | [!] B0.5 |
| B3.3 | `audit_edit` revision kind via `extend_chain()` | `audit-edit-on-approved-extends-chain-and-lifts-stamp`, `audit-edit-never-runs-agent` | [!] B0.5 |
| B3.4 | `outcome` written by `/approve` and `/draft` | `audit-outcome-derived-from-reapproval-and-override` | [!] B0.5 |

> **Census D standing note:** no audit producer exists. G7 ships the applier + table against
> fixture deltas only. The B3 gate is a fixture claim, not a production claim.

---

## Phase B4 — G9 (returned exam)

Gate: golden render diff · ZIP manifest tests · cache invalidation count correct.

| # | Item | Red-first tests | Status |
|---|---|---|---|
| B4.1 | `stamp_corner_picker` (pure) | `stamp-auto-corner-picks-min-ink` | [ ] |
| B4.2 | `render_returned_exam` — stamp + appendix (PyMuPDF per census E) | render golden-image diff, `appendix-paginates-long-feedback` | [ ] |
| B4.3 | Cache key + GCS object + `returned_exam_state` (migration 022) | `returned-exam-cache-key-covers-all-inputs` | [ ] |
| B4.4 | Manifest + approved-only ZIP | `zip-approved-only-with-manifest` | [ ] |
| B4.5 | `PATCH /batches/{id}` toggle/default + invalidation | `appendix-toggle-per-batch`, `stamp-apply-to-batch-writes-default-not-manual-overrides` | [ ] |

---

## Migrations (head is **017** — census B0, spec §4 said 016)

| # | File | Item |
|---|---|---|
| 018 | `018_schools.sql` — `schools` + `users.school_id` | G6 |
| 019 | `019_graded_tests_opened_at.sql` | G8 |
| 020 | `020_grading_batches_appendix.sql` (audit cols DROPPED — R-1) | G9 |
| ~~021~~ | ~~`audit_deltas`~~ — struck by R-1 | — |
| 022 | `022_graded_tests_returned_exam_key.sql` | G9 |
| ~~—~~ | ~~overlay JSON data migration~~ — struck: R-2 count is **0** | G5 |

Each ends with its `schema_migrations` commit token; each version added to
`EXPECTED_MIGRATIONS` in `app/database.py` (§8 CLAUDE.md).

---

## Regression gates that must stay green, untouched

`test_terminal_grade_decode_order_is_evidence_first` · `test_graded_test_contract_compiler` ·
`test_graded_test_approval` · one-leaf index tests · `test_sonnet_prompt_pin_is_v53_and_v6_is_an_artifact_not_a_pin`
· `test_payload_fidelity` · the frontend bidi/copy checks (codegen must not break them).


---

## Uncommitted-state note (2026-08-31)

G2's code is complete and green in the working tree but **deliberately not
committed**: `app/config.py`, `app/services/grading_runner.py` and
`tests/services/test_grading_runner.py` each carry substantial *other*
uncommitted work that predates this session (≈95, ≈52 and ≈47 lines
respectively). Committing G2 sweeps that work into a commit that claims to be
G2, and G2 cannot be split off cleanly — `grader.py`'s wall reads
`settings.grader_llm_timeout_s`, so a grader-only commit would not import.
Owner's call: commit together (and say so in the message), or land the other
workstream first. `CENSUS_B0_…` and `TRACKER_…` are pure docs and are committed.

**Pre-existing failure, not ours:** `test_contract_parity.py::
test_golden_drafts_compile_clean_in_one_round_trip[hobby_tvshow]` fails with
G2 stashed as well as applied — the known golden-parity drift.
