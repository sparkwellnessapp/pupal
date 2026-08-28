# K2 FORENSICS — every GT-PARTIAL→AI-FULL cell in C2/E7/E8 (mission §5-F, 2026-08-28)

**Purpose:** feed the grader-v5 verifier's absence-audit wording. Zero spend; read-only
over cached results + drafts. Extractor: gates-era script over `results.json` + `drafts/`
(GT-PARTIAL = 0 < gt < possible; AI-FULL = ai == possible; excluded/ungradable rows skipped).

## The census — 18 cells, THREE terminals. Concentrated, not scattered.

| Terminal | C2 | E7 | E8 | gt/possible | Stability |
|---|---|---|---|---|---|
| `omer/q1.ב.c4` | 5/5 | 5/5 | 5/5 | 1.5 / 3 | **deterministic** — survives three prompt versions unchanged |
| `yonatan/q2.ב.c4.s1` | 1/5 | 0 | 1/5 | 0.5 / 1 | stochastic flicker |
| `dan/q2.ג.c0.s3` | 0 | 0 | 1/5 | 6 / 8 | stochastic, E8-new (rule 4's leniency floor) |

15 of 18 cells are ONE terminal. K2 is not diffuse over-generosity — it is one blind spot
plus noise. All 18 cells carry `quote_status=exact`: the evidence cited is real ink; the
failure is in what the model concluded from it.

## Case classification (defect-unfound vs defect-undercharged)

### 1. `omer/q1.ב.c4` — defect-UNFOUND: presence-verification instead of behavior-tracing
Criterion: *«יצירה של עצם חדש מטיפוס Hobby בתא המתאים במערך (hobbies[countHobbies])»* (3 pts).
GT note: the surrounding guard is INVERTED (`if(hobbies[i] != null)` enters OCCUPIED cells) —
object creation and array-assignment are correct, **the cell is the wrong one ⇒ half**.
Model, all 15 cells (representative, C2 r0): *«הסטודנט יוצר אובייקט חדש מסוג Hobby ומכניס
אותו למערך במקום המתאים, כפי שנדרש»*. It verified that the right-looking machinery APPEARS
and never traced whether the write lands in the right cell under the inverted guard.
**The model never saw the defect, three prompts running.** No instruction about deduction
size can fix a defect that is never found — which is why E8 (magnitude authority) moved
nothing here.

### 2. `yonatan/q2.ב.c4.s1` — BOTH classes, one per run
- C2 r1 (unfound): *«ואתחולו לערך הראשון במערך הצוברים, שזה נכון»* — it is NOT correct:
  initialized with a RATING VALUE where an INDEX is required (GT note: the function then
  returns 0 on every input). Wrong-value-of-the-right-shape misread as correct.
- E8 r0 (**undercharged — the model wrote the defect down and paid full anyway**):
  *«אך לא בצורה הנכונה כפי שנדרש בדוגמה. עם זאת, הכוונה הכללית נשמרת»* → 1.0/1.0.
  A points-emitting model can notice a defect and then decline to price it. A
  verdict-emitting model cannot: "לא בצורה הנכונה" IS the verdict.

### 3. `dan/q2.ג.c0.s3` — defect-UNFOUND, absence variant: HALLUCINATED PRESENCE
Criterion itemizes its own components: null check (2) + channel match (2) + isOn (2) +
print name (2). GT: 6/8, note *«null check absent (−2)»*. Model, E8 r4: *«בדק אם התוכנית
אינה null…»* — **asserts presence of the exact component that is absent**, then credits it.
The claim rides on `quote_status=exact` for the OTHER components' ink.

## What this buys the grader-v5 verifier (the absence-audit wording, F→V5-A)

1. **Per-check evidence gating kills case 3 structurally.** `met`/`partially_met` require a
   verbatim span showing THAT component. A "null check present" check with no quotable null
   comparison cannot be met; the deterministic pricer refuses credit on an unverifiable
   span (flagged `evidence_unverified`, priced as not_met — never silent).
2. **Verdict-only output kills case 2's E8 variant structurally.** The model that writes
   "not done correctly" has already emitted `not_met`/`partially_met`; there is no award
   field with which to forgive it. The pricer owns magnitude.
3. **Case 1 needs PROMPT language + PLAN decomposition, not just structure:**
   - Plan: split "creates the object in the appropriate cell" into (a) object creation with
     correct arguments, (b) the write lands in the CORRECT cell / free-slot semantics —
     the defect gets its own check instead of hiding inside a compound requirement.
   - Prompt (the absence audit): *verify what the written code DOES, not what machinery
     appears. For each check, trace the actual behavior against the requirement — the
     right-looking line inside an inverted guard writes the wrong cell and is not met.
     Before returning `met`, confirm the traced behavior; before returning `not_met`,
     state in `basis_he` what you searched for and where.* (The behavioural test of the
     E7 clause, applied in BOTH directions: don't punish form when behavior is right —
     and don't credit form when behavior is wrong.)

**Validation of the architecture from the teacher's own arithmetic:** `dan/q2.ג.c0.s3` is
graded by the teacher exactly as `Σ itemized components − the absent one` (8−2=6). The
rubric's own itemization IS the plan for such terminals; V5-B should decompose them verbatim.
