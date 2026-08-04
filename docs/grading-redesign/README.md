# Grading Pipeline Redesign

The transcription + grading pipeline rebuild. Replaces the old
conflated `graded_tests` with a chain of typed Draft/Contract artifacts.

## Read in this order

| Doc | What it is | Status |
|-----|-----------|--------|
| [Phase 0a — Architecture](architecture/phase_0a_architecture.md) | The lock. Artifact inventory, lifecycles, invariants, actors. Everything derives from here. | Locked |
| [Phase 0b — Deletion Manifest](migrations/phase_0b_deletion_manifest.md) | What was deleted/deprecated and why. | Executed |
| [Phase 0c — Target DDL](architecture/phase_0c_target_ddl.md) | The schema, column by column, with rationale. | Locked |
| [Phase 0d — ERD](architecture/phase_0d_erd.md) | Visual cross-check: relationships at rest. | Locked |
| [Phase 0e — DFD](architecture/phase_0e_dfd.md) | Visual cross-check: artifacts in motion. | Locked |

## Migrations

| Migration | Effect | Status |
|-----------|--------|--------|
| `007_phase_0b_cleanup.sql` | Drops 3 dead tables, 8 dead columns. | Executed |
| `008_phase_0c_new_schema.sql` | Creates 4 new tables, reshapes 2. | Executed |

## Sprints

| Sprint | Title | Status |
|--------|-------|--------|
| S0 | Cleanup (delete + deprecate) | Merged |
| S1 | [ORM models for new schema](sprints/S1_pr_description.md) | Merged |
| S2 | establish the auth + ownership pattern once, retrofit it onto the rubric endpoints, document it as the convention S3–S9 copy | Merged |
| S3 | Students + classes endpoints | Merged |
| S4 | Transcription Draft/Contract + /transcribe, /grade + PDF Write ops to GCS | Merged |
| S5 | PDF persistence to GCS | Merged |
| S6 | GradableTest schema + compiler | Merged |
| S7 | GraderAgent (one call per question/sub-question) | Merged |
| S8 | GradedTestDraft persistence + grading endpoint | Merged |
| S9 | Approval + GradedTestContract | Merged |
| S10 | Re-grade-stale + manual-edit flows | Planned |
| S11 | Batch grading: bulk PDF upload → fan-out transcribe+grade over the existing per-test pipeline (`batch_id` set), batch roll-up status | Planned |
| S12 | Bulk-GradedTestDraft review dashboard (frontend) — **own PR, depends on a short UX interview to nail down the intended design and exact page UX before any implementation** | Planned (blocked on UX interview) |

> Note: the former S11 ("folded into S2–S10 per frontend lockstep") is superseded — that frontend-lockstep work was absorbed into S2–S10 as planned, so the S11 slot is repurposed for batch grading.

> **Bulk approval (deferred, unscheduled):** approving all non-flagged `GradedTestDraft`s in a batch at once is intentionally *not* on the roadmap yet. It will only be planned and implemented once a **high unedited-approval rate** has been validated against the evals suite — i.e., once the TestGrader is demonstrably making very few grading mistakes and teachers are approving most drafts without edits. Until that bar is met against real data, bulk approval is a footgun (it would rubber-stamp an unreliable grader), not a feature.