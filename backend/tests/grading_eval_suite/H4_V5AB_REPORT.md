# [STOP H-4] — V5-A complete, V5-B plan awaiting ratification (2026-08-28)

**Spend: $0.00 of the $60 envelope.** Everything below is build + forensics; no
model was called. This is the mission's one scheduled stop (§0 H-4): ratify the
plan (with or without amendments) and the §4 loop starts at Stage 1.

---

## 1. What you are ratifying: `plans/hobby_tvshow.plan.json`

38 terminals · **75 checks** (62 required / 12 tariff / 1 note_only) ·
validator CLEAN against the corrected contract · hash-pinned to the snapshot
(`480c15cf…`) · plan_sha256 `4ce8a6bb…`.

**Read `plans/hobby_tvshow_plan_review.md`** — per-terminal, in Hebrew, every
check with its kind, points/tariff, equivalence notes, and the rubric span it
derives from. **Four open questions are at the top:**

- **Q-1 ⚠ `q2.ב.c4.s3`** — contract says 3, rubric text says «סה"כ 2 נקודות»,
  and the usage-check clause says «לא להוריד, לכתוב הערה». Authored:
  comparison carries all 3, usage-check is note_only. Alternative (comparison
  2 + usage 1) contradicts the note-don't-deduct. **Needs your ruling.**
- **Q-2** — the criterion-level max-search tariff («להוריד 3») anchored at s3,
  direction-agnostic required check so the defect charges exactly once.
- **Q-3** — six splits the rubric names but does not price (incl. the
  K2-forensics split `q1.ב.c4` → 1.5 יצירה + 1.5 תא-נכון, which prices omer's
  inverted-guard case at exactly the GT's 1.5).
- **Q-4** — two additive fields beyond the ratified schema: `partial_fraction`
  (the "50% default, plan-overridable" needs a home) and `rubric_quote`
  (traceability + anti-GT-leak audit).
- **Honesty note:** authored from contract text only, every check cites its
  span — but I have read the GT files during C2–E8 analysis and cannot claim
  blindness. Your review is the anti-leak gate.

## 2. The architecture, working (V5-A — all red-first, zero spend)

**Plan/Verify/Price is live end-to-end** behind `architecture: "v5"` configs:
the verifier model sees **point-blind** checks and emits verdicts + one
verbatim span per check (decode order: evidence → basis → verdict — the
grader-v2 lever carried forward); `pricer.py` computes every point
deterministically (met→100% · partially_met→50% · not_met→0 · tariffs once per
charge-group · note_only→annotation · credit REFUSED on any unverifiable span
— GA-1 enforced in code, loudly flagged). The mandated injected-error tests
all pass: over-sum plan, note_only-with-points, double-charged group,
fabricated-quote-on-met.

**K2 forensics (`K2_FORENSICS.md`) drove the verifier prompt.** All 18
GT-PARTIAL→AI-FULL cells in C2/E7/E8 are THREE terminals: one deterministic
blind spot (omer `q1.ב.c4`, 15/15 across three prompts — the model verified
that machinery *appears* and never traced the inverted guard), one
found-but-uncharged («לא בצורה הנכונה… עם זאת» → full credit — impossible for
a model that emits no numbers), one hallucinated presence (dan — claimed the
absent null check exists). Counters now structural: per-check evidence gating,
verdict-only output, and the behavior-tracing + absence-audit rules in the
grader-v5 prompt.

**The D6 model seam landed.** Both agents construct through
`llm_factory.build_chat_model` (OpenAI + Anthropic, PR-2 discipline via the
one `_llm_params` policy); the eval runner asserts per trial that the draft's
own model stamp equals the registry spec — stronger than the old env pin.
`GraderAgent`'s default path stays byte-identical (all pins green), and
prompt.py is restored to **grader-v3** with proof: post-revert `sut_hash` ==
E7's `2c2cb60b2175ce90` byte-for-byte (E8 was killed; v4 must not persist as
the default, and the champion×grader-v3 attribution run needs v3 runnable).

**Multi-span citations are structural now** (`evidence_quotes`, one verified
span per check): the E8 T1-STITCHED pathology cannot recur by design, and the
scorer's bar got STRICTER — a met-claim on absent ink gates even at award 0.

**Kills are mechanized.** `tools/gates.py` prints K1/K2/K4 → GA-1..7 → the
R.3 cross-tab, kills first; known-answer-validated against the E8 dir — it
reproduces the ratified record exactly (80/80 · 7/245 = 2.86% KILLED · 8.25 ·
cross-tab 72/32/7).

## 3. Roster facts needing no decision, reported per §1.7/§3

- **Google entrants: SKIPPED.** The only google-genai path on this machine
  rides Vertex on `GOOGLE_CLOUD_PROJECT` — the production transcription
  project; no separate eval key exists, so isolation cannot be positively
  established. `llm_factory` refuses the provider outright. Zero Gemini calls
  will occur.
- **xAI: excluded** per the roster default (one-line owner flip to include).
- **claude-sonnet-5 / claude-opus-5 added to the registry**, prices verified
  2026-08-28 from platform.claude.com: $2/$10/$0.20-cached and $5/$25/$0.50.
  Sonnet 5's $2/$10 is the STANDARD price (the scheduled Sept-1 rise to $3/$15
  "will not occur"). Card notes flag the Claude-4.7+ tokenizer (~30% more
  tokens for the same text — cost math uses measured usage, so comparisons
  stay honest). `ANTHROPIC_API_KEY` present; `langchain-anthropic` installed.

## 4. Stage 1 on ratification (no further gate until H-1/H-2/H-3)

k=3 screens, kills-first, EVAL_ANALYSIS.md per trial, cheap→expensive:
`haiku45-v5 → nano-v5 → luna-v5 → gpt4o-v5 (control) → sonnet5-v5 →
gpt55-medium-v5 → terra-medium-v5 → terra-high-v5 → opus5-v5` — nine configs,
ceiling $0.08 each (over-ceiling trials run for information, T1-COST-stamped).
Estimated Stage-1 spend at k=3×5 fixtures: roughly $6–12 total (gpt-4o-scale
runs cost ~$1.2 at k=3; cheap tier far less; opus/terra-high the ceiling
probes). Registered pre-spend in PREDICTIONS.md: **P1** (terra dominance,
activates), **P-S5** (your Sonnet-5 hypothesis → top-2 screen), **P-ARCH**
(v5-on-gpt-4o beats grader-v3 on K2 and GA-5 — the architecture claim itself).

**Ratification pins `plan_version` and starts the loop. Amendments welcome —
edit the plan or answer Q-1..Q-4 and I re-validate + re-render before Stage 1.**
