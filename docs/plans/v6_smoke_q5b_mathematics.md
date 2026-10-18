# grader-v6 known-answer smoke — mathematics

**Verdict: PASS** · planner `claude-opus-5.5` (planner-v6.2) · plan `a79166be1254…` · verifier Sonnet 5.5 (effort low) · no explainer (the fallback composer's lines) · k=1 · route `direct`

Cost: planner $0.0000 · grading $0.0161 (3 answers) · run `20261018-161613_v6-smoke_q5b`

| pass condition | result | |
|---|---|---|
| k1_class_events | 0 | ✅ |
| full_answer_at_full | 0 not full | ✅ |
| intended_share | 3/3 = 100.0% | ✅ |
| validator | fallback scopes 0 · rule-7 downgraded 0 | ✅ |
| all_answers_ran | 3/3 | ✅ |

Fixture: math3 (3-unit, choose 4 of 5): every graded leaf carries the teacher's own solution, so 'fully correct' is defined. math4 has parts with no content at all (q2 has no marking scheme; q4.ו and q5.ד are bare labels), where no answer can be known to be full.

Plan: 41 checks · scope origins {'planner': 16, 'repaired': 7, 'fallback': 0, 'compiled': 0}

## A3_wrong — 1/1 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q5.ב.c0` | ב. 20% | zero | 0/5.75 zero | ✅ |

## A2_partial — 1/1 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q5.ב.c0` | ב. 20% | partial | 2/5.75 partial | ✅ |

Reasoning lines and the checks behind them:

- **`q5.ב.c0`** — חסר: חישוב התשלום לפי הצעה ב' עבור מספר המשתתפים הצפוי: התשלום לכל משתתף כפול מספר המשתתפים · חסר: השוואת התשלומים ובחירת ההצעה הזולה יותר עבור מספר המשתתפים הצפוי
  - credit · חישוב התשלום לפי הצעה א' עבור מספר המשתתפים הצפוי: התשלום הקבוע ועוד התשלום לכל משתתף כפול מספר המשתתפים → **התשלום לפי הצעה א' חושב כתשלום הקבוע ועוד התשלום לכל משתתף כפול מספר המשתתפים הצפוי, והחישוב נכון** (2) · «1000 + 20 · 150 = 4000 ש"ח»
  - credit · חישוב התשלום לפי הצעה ב' עבור מספר המשתתפים הצפוי: התשלום לכל משתתף כפול מספר המשתתפים → **לא חושב התשלום לפי הצעה ב' עבור מספר המשתתפים הצפוי, או שחושב בדרך שגויה (למשל בתוספת תשלום קבוע, לפי התעריף של הצעה א', או לפי מספר משתתפים אחר)** (0) · «לא חושב תשלום להצעה ב'; רק הצעה א' מופיעה»
  - credit · השוואת התשלומים ובחירת ההצעה הזולה יותר עבור מספר המשתתפים הצפוי → **לא נבחרה הצעה, או שנבחרה ההצעה היקרה יותר, או שהבחירה אינה נשענת על השוואת התשלומים בשתי ההצעות** (0)

## A1_full — 1/1 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q5.ב.c0` | ב. 20% | full | 5.75/5.75 full | ✅ |

