# E8 REPORT — grader-v4, "deduction size is set by the rubric" (2026-08-27)

**Run** `20260827-203313_gpt-4o` · k=5 × 5 · **$1.98** · one variable (rule 4).
**Provenance:** `grader-v4` · `sut_hash: ca642409227a86ad` (E7: `grader-v3` / `2c2cb60b2175ce90`) · `prior_context: False`. `prompt.py` verified the only dirty grader-path file.
**All rates PROVISIONAL** (n=5, one exam).

---

## 1. KILL CRITERIA — first

| # | Criterion | Bar | E8 | Verdict |
|---|---|---|---|---|
| **K1** | GT-ZERO → AI-ZERO | 80/80 | **80/80** | **PASS** |
| **K2** | GT-PARTIAL → AI-FULL | ≤ 2.0% | **2.9% (7/245)** | **✗ FAIL** |
| **K3** | `within_precision_rate` | > 0.7232 | **0.7400** | **PASS** |
| **K4** | max `ai_total_spread` | ≤ 14.00, corpus max falls | **8.25** (from 14.00) | **PASS** |

> ## **K2 FAILED. By its own pre-registered criterion, E8 is killed.**
>
> Rule 4's leniency floor — *"a component that is present but imperfect earns
> partial credit, not zero"* and *"award that share of points_possible"* — pushed
> two additional GT-PARTIAL terminals to full credit. This is the K2 tripwire
> doing exactly what it was written to do: catching over-forgiveness *before* it
> could be sold as an accuracy win by the metrics that improved.

Validity: **25/25 valid**, 0 re-runs, parse-rate 0 (**R6 not triggered**), cost $0.079/test (under ceiling).
Tier-1: **19/25** — taxonomy `{T1-STITCHED: 9}`, a **3× increase** (see §4).

## 2. E8 predictions scored

| Prediction | E7 | E8 | Verdict |
|---|---|---|---|
| GT-PARTIAL→AI-ZERO falls to **≤55** | 72 | **72** | **FALSIFIED** — no movement whatsoever |
| GT-FULL→AI-ZERO falls to **≤22** | 28 | **32** | **FALSIFIED** — worsened |
| mean signed Δ improves by **≥0.10** | −0.2782 | **−0.2574** (improved **0.0208**) | **FALSIFIED** |
| `within_precision` improves on 0.7232 | 0.7232 | **0.7400** | **CONFIRMED** |
| max spread falls below **14.00** | 14.00 | **8.25** | **CONFIRMED** |
| `q2.ב.c4.s3` moves for the first time | −34.50 | **−23.50** | **CONFIRMED** |

**The central E8 thesis — that magnitude authority reverses zero-inflation — is falsified.** Zero cells did not come back: 22 recovered, **26 new**, net **+4 more zero cells**. What rule 4 *did* deliver is variance control and the tariff fix.

## 3. The four checks

**(a) `q2.ב.c4.s3` MOVED — and for exactly the right reason.** −34.50 → **−23.50**. omer went `1.5–3.0` → **3.00 ×5**; moran → **3.00 ×4**. The reasoning cites the instruction verbatim:

> moran r0: *"לפי ההנחיות, **אין להוריד נקודות על כך, אלא רק לציין זאת**"*
> omer r0: *"יש לציין זאת כהערה"*

**Rule 4(a) is a clean, unambiguous success** — the model now reads a named tariff and obeys it, including the note-don't-deduct instruction it had been overriding since C2. din stays at 0 (wrong-target, outside rule 4's scope, correctly).

**(b) The E7 zeros did NOT come back.** 180 zero cells in E7 → 22 recovered, 158 unchanged, **26 newly created**. Net **+4**. The anti-zero-inflation sentence did not do its job.

**(c) dan's spread FELL, decisively.** 14.00 → **8.25**; yonatan 7.25 → **2.00**; din 7.75 → 6.00. moran (1.50→1.75) and omer (2.50→3.00) rose trivially. **Corpus max 14.00 → 8.25** — K4's strongest signal, and the E7 regression I failed to surface is now repaired. dan's totals are still spread across 67.50–75.75, crossing the 75 boundary.

**(d) Redistribution AGAIN — and larger than E7's.** 11 terminals worsened for **−33.25** of new harshness (E7: −24.50). One previously-clean terminal became harsh (`q1.ב.c7`, 0 → −1.00). `q2.ג.c0.s3` nearly doubled: **−15.00 → −29.50**.

> ### The redistribution rule FIRES.
> Per the standing condition: *"If E8 also redistributes, the rule fires and the
> model seam (D6 → the registered Terra prior, P1) becomes the evidence-based
> next move."* E8 redistributed **more** than E7. Two successive prompt clauses,
> each with a named mechanism, each moving failure rather than eliminating it —
> that is the prompt-surface-exhaustion signature the rule exists to detect.

## 4. §R qualitative read

**The T1-STITCHED explosion, 3 → 9, is the run's second finding.** Concentrated in five cells: `omer/q1.ב.c3` ×3, `dan/q1.ג.c1` ×2, `dan/q1.ג.c7` ×2, `moran/q1.ג.c6` ×1, `moran/q1.ג.c7` ×1. Rule 4 tells the model to reason about *which components are present* — and it is now assembling multi-component citations to evidence that reasoning, stitching non-contiguous lines together. **The instruction that improved the tariff reasoning is the same one degrading citation integrity.** This is the strongest evidence yet for the step-3 multi-span design input recorded at the DL-2 split: the model needs to cite several spans because its reasoning genuinely spans several places, and the single-quote contract forces it to fabricate contiguity.

**Shippable trials — reported as CANCELLATION per the new PLAYBOOK rule.** All four are omer, all four fired `compensating_error`; `edit_burden` 3–4. `shippable_grade_rate` is unchanged at 0.16 and is **not** evidence of terminal correctness.

**Rule 4 compliance is real but partial.** Where the rubric names a tariff, the model now obeys it (check a). Where it does not, clause (c) — *"judge how much of the work is present and award that share"* — is itself a discretionary judgment, and it produced both the K2 over-forgiveness and the −33.25 redistribution.

## 5. Tier-2 / Tier-3

| Metric | E7 | E8 |
|---|---|---|
| `within_precision_rate` | 0.7232 | **0.7400** |
| `exact_rate` | 0.7137 | **0.7316** |
| `terminal_mae` | 0.3118 | **0.2942** |
| mean signed Δ | −0.2782 | −0.2574 |
| direction census | 20 / 252 / 678 | 22 / **233** / **695** |
| `boundary_flip_rate` | 0.52 | **0.44** |
| calibration ECE | 0.2156 | **0.1987** |
| **instability — how many** | 30.0% | 35.3% ⚠ |
| **instability — how far (max spread)** | 14.00 | **8.25** ✅ |
| E5 inverted | 0.5% | **0.3%** |
| E5 GT-tie→AI-split | 20.5% | **15.3%** |
| E5 directional agreement | 98.6% | **99.3%** |

Both instability measures reported, per the new rule — and they **diverge**: more terminals move, but the totals move much less. Per-fixture: din +2.5, moran +1.0, yonatan +0.75, dan −0.5, omer −0.5.

## 6. Verdict

**E8 is killed by K2 and must not be adopted as it stands.** That is the pre-registered rule working, and it is worth more than the metric gains it prevented us from banking: `within_precision`, `exact_rate`, MAE, ECE, boundary-flip and all three E5 measures improved, and K4 repaired the variance regression — but 2.9% > 2.0% on GT-PARTIAL→AI-FULL means rule 4 buys accuracy partly by giving away credit the teacher withheld.

**Two structural findings for step 3, surfaced not acted on:**

1. **The redistribution rule has fired.** Rule 3 and rule 4 each fixed their target and each moved failure elsewhere (−24.50, then −33.25). The prompt surface looks exhausted for this defect family. Per the standing condition, **the model seam (D6) and the registered Terra prior (P1) are now the evidence-based next move** — and note the earlier judgment that "this is a standards failure, not a capability failure" is what E8 was testing; two failed clauses is evidence against it.
2. **The single-quote contract is now actively harmful.** T1-STITCHED tripled because better component reasoning demands multi-span citation. The multi-span design input is no longer speculative.

**Recommended sequence — owner's call, nothing done:** either (a) narrow rule 4(c) to remove the discretionary share-judgment and re-run as E9, or (b) accept prompt-surface exhaustion and move to D6/Terra. **I have not chosen.**

**No GT amended · no thresholds pre-registered · no model change · `app/` limited to the owner-installed `prompt.py` clause.**
