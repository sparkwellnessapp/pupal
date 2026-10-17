# grader-v6 — Math / English structural smoke (§6a, $0, no model)

The deterministic FALLBACK plan, the real v6 grader on a scripted model, every check set by hand to the option matching the pre-registered class, priced by THE pricer.

## mathematics

- Stage 1: 23 scopes · 31 criteria · fallback plan 31 checks.
- Fallback plan through V12–V20: clean ✅ · V21 warnings: 0.
- Components as compiled (31): `q1.א.c0` 1.75, `q1.ב.c0` 3.5, `q1.ג.c0` 3.5, `q1.ג.c1` 3.25, `q1.ג.c2` 7, `q1.ד.c0` 1.75, `q1.ה.c0` 3.25, `q2.א.c0` 2.5, `q2.ב.c0` 9.5, `q2.ג.c0` 6, `q2.ד.c0` 6, `q3.א.1.c0` 2, `q3.א.1.c1` 2, `q3.א.2.c0` 2, `q3.א.2.c1` 2, `q3.א.3.c0` 2, `q3.א.3.c1` 2, `q3.ב.1.c0` 2, `q3.ב.1.c1` 2, `q3.ב.2.c0` 2, `q3.ב.2.c1` 2, `q3.ב.3.c0` 2, `q3.ב.3.c1` 2, `q4.א.c0` 7.25, `q4.ב.c0` 3.75, `q4.ג.c0` 3.5, `q4.ד.c0` 9.5, `q5.א.c0` 5.75, `q5.ב.c0` 5.75, `q5.ג.c0` 5.5, `q5.ד.c0` 7

### A1_full

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 17 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.א.c0` | א. שטח ארגז החול הגדול: 10% | full | 1.75/1.75 full | ✅ |
| `q1.ב.c0` | ב. 20% | full | 3.5/3.5 full | ✅ |
| `q1.ג.c0` | ג. אורך צלע a 20% | full | 3.5/3.5 full | ✅ |
| `q1.ג.c1` | אורך צלע b 20% | full | 3.25/3.25 full | ✅ |
| `q1.ג.c2` | 40% | full | 7/7 full | ✅ |
| `q1.ד.c0` | ד. שטח ארגז החול לאחר ההגדלה 10% | full | 1.75/1.75 full | ✅ |
| `q1.ה.c0` | ה. 20% | full | 3.25/3.25 full | ✅ |
| `q2.א.c0` | א. 10% | full | 2.5/2.5 full | ✅ |
| `q2.ב.c0` | ב. כדי להשתמש במשפט פיתגורס, צריך לחלק את המשולש לשני משולשים ישרי זווית. נסתכל על משולש ADC: 40% | full | 9.5/9.5 full | ✅ |
| `q2.ג.c0` | ג. היקף המפרש 25% | full | 6/6 full | ✅ |
| `q2.ד.c0` | ד. שטח המפרש 25% | full | 6/6 full | ✅ |
| `q4.א.c0` | א. 30% | full | 7.25/7.25 full | ✅ |
| `q4.ב.c0` | ב. 15% | full | 3.75/3.75 full | ✅ |
| `q4.ג.c0` | ג. 15% | full | 3.5/3.5 full | ✅ |
| `q4.ד.c0` | ד. 40% | full | 9.5/9.5 full | ✅ |
| `q5.א.c0` | א. 20% | full | 5.75/5.75 full | ✅ |
| `q5.ב.c0` | ב. 20% | full | 5.75/5.75 full | ✅ |
| `q5.ג.c0` | ג. 20% | full | 5.5/5.5 full | ✅ |
| `q5.ד.c0` | ד. 25% | full | 7/7 full | ✅ |

### A2_partial

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 15 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅ · **partial NOT expressible on the fallback plan:** `q1.ג.c0`, `q1.ג.c2`, `q2.ב.c0`, `q4.ד.c0`, `q5.ב.c0`

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.א.c0` | א. שטח ארגז החול הגדול: 10% | full | 1.75/1.75 full | ✅ |
| `q1.ב.c0` | ב. 20% | zero | 0/3.5 zero | ✅ |
| `q1.ג.c0` | ג. אורך צלע a 20% | partial | 0/3.5 zero | ✅ |
| `q1.ג.c1` | אורך צלע b 20% | full | 3.25/3.25 full | ✅ |
| `q1.ג.c2` | 40% | partial | 0/7 zero | ✅ |
| `q1.ד.c0` | ד. שטח ארגז החול לאחר ההגדלה 10% | full | 1.75/1.75 full | ✅ |
| `q1.ה.c0` | ה. 20% | full | 3.25/3.25 full | ✅ |
| `q2.א.c0` | א. 10% | full | 2.5/2.5 full | ✅ |
| `q2.ב.c0` | ב. כדי להשתמש במשפט פיתגורס, צריך לחלק את המשולש לשני משולשים ישרי זווית. נסתכל על משולש ADC: 40% | partial | 0/9.5 zero | ✅ |
| `q2.ג.c0` | ג. היקף המפרש 25% | zero | 0/6 zero | ✅ |
| `q2.ד.c0` | ד. שטח המפרש 25% | full | 6/6 full | ✅ |
| `q4.א.c0` | א. 30% | full | 7.25/7.25 full | ✅ |
| `q4.ב.c0` | ב. 15% | full | 3.75/3.75 full | ✅ |
| `q4.ג.c0` | ג. 15% | zero | 0/3.5 zero | ✅ |
| `q4.ד.c0` | ד. 40% | partial | 0/9.5 zero | ✅ |
| `q5.א.c0` | א. 20% | zero | 0/5.75 zero | ✅ |
| `q5.ב.c0` | ב. 20% | partial | 0/5.75 zero | ✅ |
| `q5.ג.c0` | ג. 20% | full | 5.5/5.5 full | ✅ |
| `q5.ד.c0` | ד. 25% | zero | 0/7 zero | ✅ |

Expanded checks (the partial answer):

- `q1.א.c0` credit/binary · א. שטח ארגז החול הגדול: 10% → **קיים ותקין** (1.75)
- `q1.ב.c0` credit/binary · ב. 20% → **לא נמצא** (0)
- `q1.ג.c0` credit/binary · ג. אורך צלע a 20% → **לא נמצא** (0)
- `q1.ג.c1` credit/binary · אורך צלע b 20% → **קיים ותקין** (3.25)
- `q1.ג.c2` credit/binary · 40% → **לא נמצא** (0)
- `q1.ד.c0` credit/binary · ד. שטח ארגז החול לאחר ההגדלה 10% → **קיים ותקין** (1.75)
- `q1.ה.c0` credit/binary · ה. 20% → **קיים ותקין** (3.25)
- `q2.א.c0` credit/binary · א. 10% → **קיים ותקין** (2.5)
- `q2.ב.c0` credit/binary · ב. כדי להשתמש במשפט פיתגורס, צריך לחלק את המשולש לשני משולשים ישרי זווית. נסתכל על משולש ADC: 40% → **לא נמצא** (0)
- `q2.ג.c0` credit/binary · ג. היקף המפרש 25% → **לא נמצא** (0)
- `q2.ד.c0` credit/binary · ד. שטח המפרש 25% → **קיים ותקין** (6)
- `q4.א.c0` credit/binary · א. 30% → **קיים ותקין** (7.25)
- `q4.ב.c0` credit/binary · ב. 15% → **קיים ותקין** (3.75)
- `q4.ג.c0` credit/binary · ג. 15% → **לא נמצא** (0)
- `q4.ד.c0` credit/binary · ד. 40% → **לא נמצא** (0)
- `q5.א.c0` credit/binary · א. 20% → **לא נמצא** (0)
- `q5.ב.c0` credit/binary · ב. 20% → **לא נמצא** (0)
- `q5.ג.c0` credit/binary · ג. 20% → **קיים ותקין** (5.5)
- `q5.ד.c0` credit/binary · ד. 25% → **לא נמצא** (0)

### A3_wrong

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 13 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.א.c0` | א. שטח ארגז החול הגדול: 10% | zero | 0/1.75 zero | ✅ |
| `q1.ב.c0` | ב. 20% | zero | 0/3.5 zero | ✅ |
| `q1.ג.c0` | ג. אורך צלע a 20% | zero | 0/3.5 zero | ✅ |
| `q1.ג.c1` | אורך צלע b 20% | zero | 0/3.25 zero | ✅ |
| `q1.ג.c2` | 40% | zero | 0/7 zero | ✅ |
| `q1.ד.c0` | ד. שטח ארגז החול לאחר ההגדלה 10% | zero | 0/1.75 zero | ✅ |
| `q1.ה.c0` | ה. 20% | zero | 0/3.25 zero | ✅ |
| `q2.א.c0` | א. 10% | zero | 0/2.5 zero | ✅ |
| `q2.ב.c0` | ב. כדי להשתמש במשפט פיתגורס, צריך לחלק את המשולש לשני משולשים ישרי זווית. נסתכל על משולש ADC: 40% | zero | 0/9.5 zero | ✅ |
| `q2.ג.c0` | ג. היקף המפרש 25% | zero | 0/6 zero | ✅ |
| `q2.ד.c0` | ד. שטח המפרש 25% | zero | 0/6 zero | ✅ |
| `q4.א.c0` | א. 30% | zero | 0/7.25 zero | ✅ |
| `q4.ב.c0` | ב. 15% | zero | 0/3.75 zero | ✅ |
| `q4.ג.c0` | ג. 15% | zero | 0/3.5 zero | ✅ |
| `q4.ד.c0` | ד. 40% | zero | 0/9.5 zero | ✅ |
| `q5.א.c0` | א. 20% | zero | 0/5.75 zero | ✅ |
| `q5.ב.c0` | ב. 20% | zero | 0/5.75 zero | ✅ |
| `q5.ג.c0` | ג. 20% | zero | 0/5.5 zero | ✅ |
| `q5.ד.c0` | ד. 25% | zero | 0/7 zero | ✅ |

## english

- Stage 1: 1 scopes · 4 criteria · fallback plan 4 checks.
- Fallback plan through V12–V20: clean ✅ · V21 warnings: 0.
- `levels` from the C8-lite band ladder: `q1.c0` CORRECT 8 / PARTIALLY 5 / MINIMALLY 2 / INCORRECT 0; `q1.c1` CORRECT 10 / PARTIALLY 6 / MINIMALLY 3 / INCORRECT 0; `q1.c2` CORRECT 16 / PARTIALLY 10 / MINIMALLY 5 / INCORRECT 0; `q1.c3` CORRECT 6 / PARTIALLY 4 / MINIMALLY 2 / INCORRECT 0

### A1_full

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 1 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting d | full | 8/8 full | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances  | full | 10/10 full | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of | full | 16/16 full | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no | full | 6/6 full | ✅ |

### A2_partial

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 1 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting d | partial | 5/8 partial | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances  | partial | 6/10 partial | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of | partial | 10/16 partial | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no | partial | 4/6 partial | ✅ |

Expanded checks (the partial answer):

- `q1.c0` credit/levels · CONTENT AND ORGANIZATION CORRECT : • fully on topic • fully developed (main idea and supporting details) • all elements of task are address… → **PARTIALLY CORRECT** (5)
- `q1.c1` credit/levels · VOCABULARY CORRECT : • correct use of varied and rich vocabulary • appropriate use of instances of language chunks and phrases • correct us… → **PARTIALLY CORRECT** (6)
- `q1.c2` credit/levels · LANGUAGE USE CORRECT : • correct use of basic tenses and/or language structures • correct use of advanced language structures • correct wor… → **PARTIALLY CORRECT** (10)
- `q1.c3` credit/levels · MECHANICS CORRECT : • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on sentences PARTIALLY CORRECT : • pa… → **PARTIALLY CORRECT** (4)

### A3_blank

- verifier payload: aliases only, value-invariant ✅
- explainer payload: 0 scope input(s) built, aliases only ✅
- pricing: zero for wrong/blank ✅ · full for full ✅ · partial where expressible ✅

| criterion | her text | intended | priced | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting d | zero | 0/8 zero | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances  | zero | 0/10 zero | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of | zero | 0/16 zero | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no | zero | 0/6 zero | ✅ |

