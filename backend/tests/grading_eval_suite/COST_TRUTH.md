# COST_TRUTH — the reconciliation protocol (owner-ordered, lands before Stage 1)

**Claim being defended:** every dollar figure this suite reports is computed
from provider-reported token usage × registry price cards. Four failure modes
would silently corrupt it; each has a named counter, all live as of 2026-08-28:

| Failure mode | Counter | Where |
|---|---|---|
| Wrong price card (transposed, stale, write-vs-read cache rate) | registry unit test, runs in every battery | `tests/eval_common/test_models_registry.py` — first run caught claude-sonnet-4-6's cache-READ field carrying the cache-WRITE rate (3.75 → 0.30) |
| Provider serves a different model than requested | per-trial truth-check: every `served_models` entry must match the registry `model_id` modulo date suffix, else the run HALTS | `runner._assert_draft_stamp`; served ids captured from response metadata by both agents, stamped in the draft (`served_models`) and provenance |
| Provider does not report a served id | surfaced as `<unreported-by-provider>` in provenance — never silently equated with the request | `run_grade` provenance |
| Suite arithmetic drifts from what the provider actually billed | the per-(UTC day, model) ledger, diffed against provider dashboards after each Stage | `tools/cost_truth.py` → `COST_TRUTH_LEDGER.md` |

## The reconciliation ritual (after each Stage, before the next)

1. `python -m tests.grading_eval_suite.tools.cost_truth` — regenerates the
   ledger (invalid trials INCLUDED: the provider billed them regardless).
2. Pull the same UTC day per model from: OpenAI usage dashboard · Anthropic
   console usage · GCP billing **filtered by the eval request labels** (see
   below). Enter the dashboard numbers beside the ledger rows.
3. Tokens within rounding and dollars within ~2% → reconciled; larger → STOP,
   attribute (hidden retries, unbilled cache reads, wrong card) before any
   further spend.

## Google attribution (owner ruling 2026-08-28, with the §1.7 reversal)

Vertex has no per-key split, so eval calls carry **request labels**
(`labels={"vivi-workload": "grading-eval"}` in `GenerateContentConfig`, set by
the factory's gemini adapter on every call). The GCP billing view filtered by
that label separates eval spend from production transcription — without it the
reconciliation is blind on one of three providers.

## Ledger note (owner, H-4 item 4)

Sonnet 5's verified $2/$10 projects ~$0.062/test pre-caching — inside the
$0.08 ceiling.
