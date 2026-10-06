# EVAL_ANALYSIS — the v5 production-pin baseline (Track B, Oct 6)

**Run:** `20261006-172751_trackb-sonnet5-v54_rescore`. It is the merge of `20261006-171126` and `20261006-172639`; a network outage invalidated two trials of the first, re-run in the second.
- **Configuration:** grader-v5.4 + Sonnet 5, on the D-13 re-routed compiled plans.
- **Fixtures:** 12 (hobby 5, bagrut 7), k=2, 24/24 trials valid, expressibility guard report-only. Spend $4.26.
- SCREENING (k=2).

## 1 · Verdict

**KILLED on its own bars: the production pin fails K2 and K4 on the 12-fixture set.** It is the comparator for v6's K3, G-Z and cost, not a candidate. This is bagrut's first graded run under any configuration.

## 2 · Gates and kills

Glossary:
- **K1:** zero GT stays zero (no false credit).
- **K2:** a GT-partial cell graded full.
- **K4:** the widest swing of one student's total across repeats.
- **K3 / GA-2:** share of criteria within the rubric's precision.
- **G-Z:** a GT-partial cell graded zero.

| gate | target | this run | earlier (hobby only, Aug 30–31, k=2–3) | verdict |
|---|---|---|---|---|
| K1 | 100% | 62/62 | 31/32–45/48 | PASS |
| K2 | ≤ 2.4% | **20/196 = 10.2%** | 0–3% of 98–147 | **KILLED** |
| K4 | ≤ 8.25 | **10.25** | 2.25–4.75 | **KILLED** |
| K3 (GA-2) | ≥ 0.85 | **0.693** | 0.855–0.861 | ✗ |
| G-Z | — (≤ baseline, for v6) | **62/196 = 31.6%** | 25–30% | the bar v6 must not exceed |
| GA-5 spread | ≤ 3.0 | 10.25 | — | ✗ |
| cost per test | $0.10 target | **$0.1774** | $0.156–0.160 | over |

The trend is not like-for-like: the earlier runs were hobby only. Bagrut is new, and it is where every number moved.

## 3 · Where points go (top regressions, in points per test)

1. **Credit refused for an unverified quote** («ראיה לא אומתה»): the model cites a span the validator cannot find, and the pricer withholds the credit. yael `q1.א.1.c0` 12→0, roni `q5.א.c1` 4→0, yahli `q3.ב.c4` 4→0.
2. **One defect fails a whole binary criterion:** din (bagrut) `q4.ב.c7` 5→0, raz `q6.c8` 3→0.
3. **A strict null-check reading:** hobby `q2.ב.c3.s3`, 5→3 on dan, moran and omer alike — the same plan decision every time.
4. **Over-credit on a full-looking answer:** itay `q6.c8` 4→8 (the K2 class).
5. **Instability:** yael's total 63.5 ↔ 73.75 across two repeats (K4).

## 4 · The twelve students (GT → AI per trial; biggest miss)

| student | GT | AI r0, r1 | biggest miss |
|---|---|---|---|
| bagrut din | 91.5 | 58.00, 64.25 | `q4.ב.c7` 5→0: «בדיקה על str[g] … ולא על arr[i]» |
| bagrut itay | 79.5 | 62.75, 62.00 | `q6.c8` 4→8 |
| bagrut noam | 83.75 | 79.50, 77.25 | `q2.ב.c4` 3→1 |
| bagrut raz | 82.25 | 68.00, 69.25 | `q6.c8` 3→0 |
| bagrut roni | 94.0 | 72.50, 71.25 | `q5.א.c1` 4→0 (unverified quote) |
| bagrut yael | 91.0 | 63.50, 73.75 | `q1.א.1.c0` 12→0 (unverified quote) |
| bagrut yahli | 70.5 | 54.75, 59.75 | `q3.ב.c4` 4→0 (unverified quote) |
| hobby dan | 84.0 | 73.50, 71.50 | `q2.ב.c3.s3` 5→3 |
| hobby din | 55.5 | 45.75, 43.25 | `q2.ב.c4.s3` 3→0.75 |
| hobby moran | 92 | 82.00, 84.50 | `q2.ב.c3.s3` 5→3 |
| hobby omer | 89.0 | 83.50, 82.50 | `q2.ב.c3.s3` 5→3 |
| hobby yonatan | 92.5 | 79.25, 80.75 | `q2.ב.c3.s0` 2→0 |

Every student is under-graded: by 5 to 33 points, median about 12.

## 5 · Best working theory

**v5's loss is zero-inflation.** All-or-nothing checks, and a credit gate that withholds a whole criterion when one cited span fails to verify, turn partial answers into zeros. G-Z is 31.6%, and the totals sit below GT for all 12 students.

The bagrut rubric magnifies it: large criteria (12 points), and long code answers where an exact span is harder to cite.

Confidence: **medium** (k=2; the per-student pattern is uniform).

## 6 · Recommended next

- **Primary:** the v6 CS eval, already running. v6 replaces binary checks with the planner's options and partials. Its evidence gate refuses only the claimed option, never the whole criterion. The prediction (P-v6-2) is that G-Z does not rise; the hope is that it falls.
- **Alternative:** none for v5. Tuning v5 is not on this PR's path.
- What separates them is v6's G-Z and K3 against this table.
