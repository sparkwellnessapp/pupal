# C2 BASELINE — ABORTED BY BILLING (2026-08-26)

**Run:** `results/20260826-172246_gpt-4o` · **0/25 valid trials** · **$0.00 spent**
**Steps 1 and 2 completed successfully. Step 3 produced no data.**

---

## Steps 1–2 — DONE

### Step 1 — R1 anchor stamped

`authored_at: "2026-08-26"` in all five GT files. Commit `22118ce`, five files,
`authored_at` only (`git diff`: 5× `+`, 5× `−`, nothing else).

**Schema note (form chosen deliberately):** I tested both forms first. The
date-only form parses and compares correctly; **the tz-aware form
`2026-08-26T00:00:00+03:00` raises `TypeError: can't compare offset-naive and
offset-aware datetimes`** inside `assert_blind_sequencing`, because the run-dir
timestamp it compares against is naive — the exact naive/aware trap CLAUDE.md
documents. Date-only gives identical local-midnight semantics, so your safe
direction held (proven in §4 below).

| Check | Result |
|---|---|
| (a) totality 38/38 · bounds · 0.25 grid · D5 pin · M1 provenance | **all five PASS** |
| (b) corpus pin | din 55.5 · dan 84.0 · omer 89.0 · moran 92 · yonatan 92.5 — **unchanged** |
| (c) `assert_blind_sequencing` | **PERMITTED for all five — Phase-B exit condition MET** |

Both disclosed items ratified and noted (dan/din placeholder re-stamp; corpus pin as standing guard).

### Step 2 — P2 registered

Committed verbatim to `PREDICTIONS.md` (`9a0d396`) **before** any spend, falsifiers intact.

---

## Step 3 — the baseline could not run

### Tier 0 — validity (the whole result)

| | |
|---|---|
| Trials | 25 |
| **Valid** | **0** |
| Invalid | **25** (all: transport failure across all 6 scopes) |
| Scope failures | **150 / 150**, every one `RateLimitError` |
| Tokens consumed | **0 in / 0 out** |
| **Actual spend** | **$0.00** — no call reached the model; the ~$1 budget is unspent |
| D7 re-runs | 25/25 fired, none helped (condition is permanent) |
| Wall-bound hits | 0 |
| Parse failures | 0 — **R6 escalation not triggered** |

**Root cause, from the provider payload stored in every draft:**

```
Error code: 429 - {'error': {'message': 'You have no credits remaining.
Add credits to continue using the API at
https://platform.openai.com/settings/organization/billing/.',
'type': 'insufficient_quota'}}
```

**The OpenAI account is out of credits.** This is a billing state, not an
engineering fault.

### What I am NOT reporting, and why

There is no measurement. Reporting a worst test, terminal tables, Tier-2
distributions, calibration, or quote-status data would be fabrication.

**P2 is UNSCORED** — not confirmed, not falsified, not indeterminate. It stands
registered and untouched, ready to be scored against the re-run. Marking its
predictions "indeterminate" would misrepresent a billing outage as evidence
about the grader.

Tier-1 tripwires are **vacuous** here — no graded terminal existed to trip them.

---

## What this run did prove

**The instrument works under total provider failure.** On its first contact
with reality it: classified the failures as transport (not parse), invalidated
every trial, **counted** them, excluded them from aggregates, wrote complete
artifacts and drafts, stamped provenance correctly — and reported **0/0 rather
than inventing numbers**. Validity-before-significance did its entire job.

**Field confirmation of G-3** (recorded, not actioned — `app/` is fenced,
PR-7 owns it). CLAUDE.md predicts precisely this: *"`insufficient_quota` — a
permanent billing 429 — is retried as if transient."* It arrives as
`openai.RateLimitError`, which sits in `GraderAgent.TRANSIENT_EXCEPTIONS`, so
the agent retried every scope once before failing. Cost of the
mis-classification: **25 wasted trial re-runs = 150 additional doomed calls**,
~12 s per trial. Free in dollars only because the account was already at zero —
on a *rate-limited* account it would have doubled the spend. This is the
baseline attempt's one genuine finding, and it is a step-3 input, not a v0 fix.

**R1 survived the failed run** — verified after it: the drafts
(`20260826-172246`) postdate `authored_at` midnight, so grade mode is still
**permitted for all five**. The local-midnight stamping choice is what
preserved this; a same-day-afternoon anchor would have blocked the re-run.

---

## STOP — one owner action

**Add credits to the OpenAI account**, then re-run the identical command:

```bash
python -m tests.grading_eval_suite.runner --config gpt-4o --mode grade -k 5
```

No code, config, GT, or prediction change is needed or permitted for the
re-run — its single variable is *"credits exist"*. Everything else is staged
and verified: guards green, corpus pinned, P2 registered pre-run, R1
permitting, provenance correct.

On completion I will deliver the full PLAYBOOK analysis in order — validity →
worst test → ≥2 hand-read terminal tables (din's Q2.ב + a high-scorer's scope)
→ Tier-1 → Tier-2 with **signed** Δ → Tier-3 → R6 check — every rate stamped
PROVISIONAL, and P2 scored line by line as CONFIRMED / FALSIFIED /
INDETERMINATE with the number beside each.

**Ledger:** `22118ce` (authored_at) · `9a0d396` (P2) · `b026ce9` (RUNLOG entry
for the aborted run).
