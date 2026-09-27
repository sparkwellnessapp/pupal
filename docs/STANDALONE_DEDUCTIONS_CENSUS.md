# STANDALONE DEDUCTIONS CENSUS — Track C (census only) → STOP

**Status: STOP. Awaiting an owner ruling on TC-1 … TC-8 (§1).** No design beyond the direction the ruling asked for.
**Ruling being executed** (`docs/GRADER_V6_CENSUS.md:148`): *"Track C — standalone deduction lines. Separate worktree, separate PR, census first; STOP before design. Trace the four lost bagrut lines; propose extraction keeping them as a scope-level field (never as 0-point criteria); list the ontology and rubric-gold changes this needs, for an owner ruling. v6.1 then wires them in as markers with scope candidates."*
**Base:** `origin/main` @ `2e8e6a0`, read in a clean worktree. Paths are repo-relative.
**Untracked artefacts** (gitignored, read in place in the shared working tree, marked **(untracked)**): `backend/tests/rubric_eval_suite/results/**` and `backend/tests/grading_eval_suite/compiled_rubric_bagrut.json` (`backend/.gitignore:164`).
**Method:** zero production code, zero spend, no model calls, no production reads. DOCX files were opened with python-docx. Block positions are written `body[N]`: the 0-based index among the block-level children of `<w:body>`, with `rR cC pP` for row, cell and paragraph inside a table. The markdown renders were scanned with regexes for the deduction verbs and the worded amounts. Every recorded prediction was string-scanned, all fields. Line numbers of the markdowns match the renders the recent runs saved (for example `results/20260909-104242_gpt-5.6-terra-high/predictions/bagrut_899371_render.md:27,88,96,355` **(untracked)**).

---

## 1. Verdict and the decisions needed

**Verdict.** The census's C-3 (b) holds, and it is one line short. In the five-fixture rubric regression set, **five** standalone deduction lines never reach a Draft, a gold file or a contract. Four are in bagrut, as C-3 said. The fifth is new: `employee_course_select1.md:166`, a question-level «להוריד 20% מניקוד השאלה (7)» row with empty point cells. A sixth line of the same kind sits in an English exam booklet outside the runner. None of the six is emitted anywhere, in any field, in any recorded prediction: **0 of 69** bagrut predictions over 37 runs, prompt versions `3.2.0` to `3.10.0`, and **0 of 58** employee predictions over 32 runs.

The loss is **by design at two layers, and the cleaner is only a backstop**:
1. The prompt gives these lines no role. Its role list has four sinks (`pipeline.py:634-638`), and it says in so many words that a standalone deduction line "is neither a criterion nor text" (`:775`, again at `:847`). The exam-wide line is also caught by the furniture rule (`:666`).
2. The extraction schema has no field that could hold one (`pipeline.py:459-575`).

A points-free field on `Question`, on `SubQuestion` (any depth, branch nodes included) and at rubric level cannot move INV-1..4. Every invariant sums only `criteria`, `sub_questions`, `sub_criteria` and `total_points` (`contract_compiler.py:255-256, 308, 331, 372`; `ontology_types.py:1183-1195`).

The real costs of the change are elsewhere:
- a new extraction prompt-and-schema package, which needs a re-baseline;
- a gold and scorer change, which starts a new `suite_hash` epoch;
- the rubric-gate UI, because the teacher must see these lines and be able to edit them;
- one honesty gap if Track C lands before v6.1 consumes the field.

| # | Question | Options | Recommendation |
|---|---|---|---|
| **TC-1** | **Field shape** | (a) `deduction_lines: List[DeductionLine]`, where `DeductionLine = {line_id, uid, text}`. `text` is verbatim, and the amount stays inside it. (b) (a) plus a verbatim `stated_amount: str`. (c) (a) plus a model-parsed `amount: Decimal`. | **(a).** It has no points field, so it can never be priced or summed as a criterion. The amount is parsed downstream by the **one** existing parser (C1 `scan_deductions`, `plan_compiler/compile.py:226-276`). A second copy of the amount would drift from the text once she edits it (§0.4). `uid` follows the P-0 precedent (`ontology_types.py:433-445`), because v6.1 markers will reference lines durably. |
| **TC-2** | **Placement, and which classes** | (a) Class B goes on `Question` and `SubQuestion` at **any depth, including branch nodes**. Class C goes on the rubric (Draft **and** Contract). (b) Leaves only. (c) B only; class C stays furniture. | **(a).** Under (b), employee L166 (question-level, and q3 has sub-questions) would be forced onto a guessed leaf, which is a silent relocation (FC, `CLAUDE.md:49`). Under (c), an FC loss is kept. |
| **TC-3** | **Contract before v6.1** | (a) The Contract carries the field. Graders ignore it until v6.1, and the rubric gate says so. (b) Draft only: stripped at compile (like `proposals`, `contract_compiler.py:173-181`) until v6.1. (c) Track C deploys only together with v6.1. | **(a)**, with honest copy («נרשם; לא מוחל אוטומטית עדיין»). She can already apply the amount herself at the grading gate (OD-R2 typed amounts). Under (b), every contract compiled in the interval must be recompiled for v6.1 to see its lines. |
| **TC-4** | **Class D**: the student-facing «…יגרור הורדת ניקוד» inside question text (6 lines, §3). | (a) It stays in question text only. (b) It is also copied into the new field. | **(a).** It is question specification (splitting rule, `pipeline.py:654-658`), and one line lives in one field. `compile.py:939-941` already scans `SubQuestion.text`, so under (b) v6.1 would read the line twice. |
| **TC-5** | **Package and spend** | A new `EXTRACTION_PROMPT_VERSION` (`pipeline.py:624`), a `PIPELINE_VERSION` bump for the schema change (`:79`; the sha pin does not cover the schema), the sha re-pin, and a k=3, all-5 re-baseline on the production pin **and** on the rollback model (`CLAUDE.md:605`, package rule). | **Approve, with kill criteria registered first:** no gate regression on any fixture, bagrut q1.א.2's TOTAL-LABEL behaviour watched in particular (§6 R-5), and the new metric reported. Estimate from recorded runs: terra-high k=1, all-5 cost **$0.465** (`results/20260909-104242…/results.json` **(untracked)**, so k=3 ≈ $1.40), and gpt-5.5 k=3, all-5 cost **$3.283** (`results/20260824-124427_prod_gpt55/results.json` **(untracked)**). Total ≈ **$4.7**. |
| **TC-6** | **Gold and scorer** | The gold gains 5 lines: bagrut q1.א.1, q1.א.2, q2.ב and rubric level; employee q3. The scorer gains `deduction_line_recall` / `_precision` (scope-matched, text at `TEXT_TAU`). (a) Ungated diagnostic for the first baseline, promoted to the gate by a later ruling. (b) Gated at once. | **(a).** Also rule that the scope of employee L166 is **q3** (the question), as written: «מניקוד השאלה», and it names operations from several sub-questions (§6 R-2). The three fixtures with no B/C line become the false-positive guard. |
| **TC-7** | **Grading-eval contracts** (`compiled_rubric_bagrut.json` **(untracked)**, committed by Track B per D-5; `hobby_tvshow_corrected.contract.json`) | (a) Untouched by Track C. They gain lines only in v6.1, under its ruling. (b) Updated in Track C. | **(a).** Their content hash keys the plan (`plan_store.py:46-57`), so touching them moves every grading number that Track B is baselining now. |
| **TC-8** | **Scope of the concept** | (a) Deduction lines only, of either polarity (`deduction_lines`). (b) Broaden to all standalone grading guidance. Bagrut `:40`, «הערה: בכל שאלה שנדרשת בה קליטה, אין צורך לבדוק את תקינות הקלט», is lost the same way and is in neither gold nor contract. | **(a) now.** The evidence and the ruling are about deductions. Record `:40` as the next candidate rather than widening the concept on one example. |

**Findings the brief did not anticipate** (each is evidenced in §2 to §5):
- **F-1:** A fifth lost line exists: employee `:166`, question-level, with a percentage amount.
- **F-2:** The prompt uses a lost line as its own example of something **not** to emit. `pipeline.py:844` quotes bagrut `:96` («אם כתבו הפוך… להוריד 0.5»). The 3.8.0 TOTAL-LABEL fix relies on this line being skipped (`rubric_eval_suite/RUNLOG.md:1766-1779`).
- **F-3:** The render destroys L27's sentence boundary. In the DOCX, cell paragraphs 1 and 4–5 are separate. In the render they are joined with a space, «…או להפך יש לכתוב במחברת…» (`parser_render.py:455-466`).
- **F-4:** The plan compiler's scope-level scan reads attributes that scope nodes do not have. `compile.py:939-941` reads `text`, `notes` and `evaluation_guidance` off a `Question` or `SubQuestion`. `Question` has no `text` (its field is `question_text`, `ontology_types.py:582`). Neither type has `notes` or `evaluation_guidance`: those are `Criterion` fields (`:449, :474`). So for a direct-criteria question the scope text is always empty. The scan also visits **leaves only** (`plan_compiler/stage0.py:46-68`). This is reported and not fixed; it matters to v6.1.
- **F-5:** The sha pin covers the prompt text only (`tests/subjects/test_prompt_identity.py:21`). The structured-output schema (`pipeline.py:1160`) is also model input and is not pinned.
- **F-6:** Raw (pre-cleaner) model output was never retained for any bagrut run. The July traces are `retain=on_failure`, and the one failing run failed at transport, with no `raw_response` (`results/20260725-183907_gpt-5.5/traces/bagrut_899371_r0.jsonl` **(untracked)**). Whether a model ever emitted one of these lines as a 0-point criterion, which the cleaner then removed, is therefore **unknown**.

---

## 2. T-1 — The four lost bagrut lines, traced end to end

Source: `backend/tests/rubric_eval_suite/fixtures/bagrut_899371.docx`. Render: `markdowns/bagrut_899371.md`. Gold: `benchmarks/bagrut_899371.json`. Eval contract: `grading_eval_suite/compiled_rubric_bagrut.json` **(untracked)**.

| Stage | **L27**: exam-wide, no-deduct | **L88**: q1.א.1, −2 | **L96**: q1.א.2, −0.5 | **L355**: q2.ב, −«נקודה» |
|---|---|---|---|---|
| **DOCX** | Instructions table `body[13]`, `r8 c0 p1`. The cell is merged across 3 columns. Paragraph 1 is «הערה: לא יורדו נקודות אם תכתבו בתוכניות אות גדולה במקום אות קטנה או להפך». Paragraphs 4–5 are the draft-page rules («יש לכתוב במחברת הבחינה בלבד…»). | Red prose paragraph `body[49]`: «אם לא סיימו את טבלת המעקב אחרי שהתקבל הערך true והמשיכו אותה עד הסוף של המערך, זה מראה על חוסר הבנה של טבלת מעקב - להוריד 2 נקודות». | Red prose paragraph `body[53]`: «אם כתבו הפוך: שהוא מתחלק ב-x אך המעקב והערך המוחזר נכון להוריד 0.5». | q2 rubric table `body[180]` (17×2), row 15: «אם החזירו את arr או את מערך העזר יש להוריד נקודה.», with the points cell `''`. It is the only data row in the table without a «סעיף ב:» prefix. Row 14 is `q2.ב.c5` (2), and row 16 is «סה"כ סעיף ב: 13 נקודות». |
| **Render** (`parser_render.py`) | `bagrut_899371.md:27`: one table row. The cell's paragraphs are joined with a space (`_analyze_cell` `:455-462`, `_clean` `:463-466`), so the line runs straight on into the draft rules. | `:88`, inside `[[color:EE0000]]`. It sits after the trace-table label `:86` («…סה"כ 12 נקודות…») and before part (2)'s task `:90`. | `:96`, red. It sits between the label «ניקוד: 3 נקודות» (`:94`) and the components 1.5 (`:98`) and 0.5 (`:100`). | `:355`: `\| אם החזירו את arr או את מערך העזר יש להוריד נקודה. \|  \|`. |
| **Prompt rule that routes it** | Furniture: "the instructions block (הנחיות …)" (`pipeline.py:664-666`). Also "deduction … NOT a scored criterion, and NOT question text" (`:775`). The role list has no fifth sink (`:634-638`). | `:775` ("a standalone deduction line is neither a criterion nor text"). `:847` (SECTION 7: "is NOT a criterion — do not emit it as one"). | `:775` and `:847`. `:844` **quotes this line** as an intervening line that is "not criteria and not separators". | `:775` and `:847`. `:731` also applies: "SKIP section-header rows with empty points cells". |
| **Extraction schema slot** | None. `RubricExtraction` holds `document_title`, `total_points`, `questions` and `selection_groups` only (`pipeline.py:558-575`). | None. `InnerSubQuestionExtraction` holds `text`, `points`, `example_solution` and `criteria` (`:459-485`). | None (same type, `:459-485`). | None. `SubQuestionExtraction` (`:488-515`). |
| **If emitted as a criterion anyway** | n/a (no scope). | At 2 points, q1.א.1 would read 12 + 2 ≠ 12 declared, a false `rubric_mismatch`. At 0 points (allowed by `CriterionExtraction.points ge=0`, `:448`) it is removed at `:1301`. | The same failure mode on q1.א.2. | The points cell is empty, so the row has 0 points and is removed at `:1301`. |
| **Cleaner** | n/a | Backstop only: `_clean_extraction` drops `points ≤ 0` (`pipeline.py:1259-1301`; filters at `:1285`, `:1301`). | Same. | Same. |
| **Build and ontology** | `_build_response` builds nodes by **named** fields only (`:1880-1912, 1950`). `Criterion.points` is `gt=0` (`ontology_types.py:448`; the brief cited `:445`, and at `2e8e6a0` it is `:448`). | Same. | Same. | Same. |
| **Gold** | Absent. | Absent. q1.א.1 holds `c0` only (`bagrut_899371.json:29-51`). | Absent (`:53` onward). | Absent. q2.ב holds `c0`…`c5` (`:276-358`). |
| **Contract** **(untracked)** | Absent. | Absent. Only `q1.א.1.c0`, 12 (`compiled_rubric_bagrut.json:33`). | Absent. `c0` 1.5 and `c1` 1.5 (`:57` onward). | Absent. `c0`…`c5` (`c5` at `:341-342`). |
| **Recorded runs** **(untracked)** | 0/69 | 0/69 | 0/69 | 0/69 |
| **Where it is lost** | **Prompt rule** (furniture), and there is **no schema slot** at rubric level. | **Prompt rule**, and **no schema slot**. The cleaner is a backstop only. | **Prompt rule**, and **no schema slot**. The line is the prompt's own negative example. | **Prompt rule** (twice), and **no schema slot**. The cleaner and the `gt=0` bound are backstops. |

**The recorded-runs row in detail.**
- **Bagrut:** 69 predictions over 37 runs, prompt versions `3.2.0-textconv` … `3.10.0-fixsource`. Models: gpt-5.5, grok-4.6 and the gpt-5.6 family. Among them are `20260824-124427_prod_gpt55` (gpt-5.5 @ `3.9.0-blockend`, k=3) and `20260909-104242_gpt-5.6-terra-high` (terra @ `3.10.0-fixsource`).
- **Employee:** 58 predictions over 32 runs.
- **Method:** every string field of each Draft was scanned for distinctive substrings («אות גדולה», «לא סיימו את טבלת», «כתבו הפוך», «החזירו את arr», «מניקוד השאלה (7)»). No line was folded into a neighbouring criterion, into question or sub-question text, into `notes` or `evaluation_guidance`, or into anything else.
- **Caveat:** a prediction is saved **after** the cleaner, so a 0-point emission would be invisible here (F-6).

---

## 3. T-2 — Inventory over every fixture

**Scan.** Verbs: להוריד, יורדו, ירדו, הורדת, הורדה, מינוס, לקנוס, קנס; also יורד, תורד, להפחית, יופחת, הפחתת. Worded amounts: נקודה, חצי נקודה, שתי נקודות, שלוש נקודות. No-deduct polarity: לא להוריד, לא יורדו. A second pass for verb-less deduction phrasing (פחות, לא לתת, ניכוי, ללא ניקוד, «(-N»), found nothing that is a deduction.

**Classes.** **A**: inside a criterion row (reaches the contract as text). **B**: a standalone row or line under a scope (lost). **C**: an exam-wide instruction (lost). **D**: other. Every D hit is a student-facing warning inside question body text, which reaches the contract as text.

### 3a. Lost lines (classes B and C)

| File:line | Scope | Verbatim | Amount as written | Class | In gold? |
|---|---|---|---|---|---|
| `bagrut_899371.md:27` | exam | «הערה: לא יורדו נקודות אם תכתבו בתוכניות אות גדולה במקום אות קטנה או להפך» | none (no-deduct) | **C** | no |
| `bagrut_899371.md:88` | q1.א.1 (leaf) | «…זה מראה על חוסר הבנה של טבלת מעקב - להוריד 2 נקודות» | 2 | **B** | no |
| `bagrut_899371.md:96` | q1.א.2 (leaf) | «אם כתבו הפוך: שהוא מתחלק ב-x אך המעקב והערך המוחזר נכון להוריד 0.5» | 0.5 | **B** | no |
| `bagrut_899371.md:355` | q2.ב (leaf) | «אם החזירו את arr או את מערך העזר יש להוריד נקודה.» | «נקודה» (worded) | **B** | no |
| `employee_course_select1.md:166` | **q3 (branch; sub-questions א–ה)** | «אי־שימוש בפעולות (בנאי, GetNumStudents GetHours / GetIsMandatory) --> להוריד 20% מניקוד השאלה (7)» | «20% מניקוד השאלה (7)» | **B** | no (`employee_course_select1.json:282` onward) |
| `fixtures/English_rubircs-solutions/1/016584-HEB-1500-1645.docx`, `body[91]` (also `2/`) | exam | «הערה: על כתיב שגוי יופחתו נקודות מן הציון.» | none (deduct) | **C** | no gold: the runner pairs fixtures non-recursively (`runner.py:71-81`; `fixtures/MANIFEST.md:28-30`) |

**No hits:** `English…/3/`, `…/public/`, both `Math_rubrics/*.docx`, `probes/omml_bands_probe.docx` and `foundations_cs`.

### 3b. Lines that reach the contract (classes A and D)

| File:line | Scope (gold) | Phrase (short) | Amount(s) | Class |
|---|---|---|---|---|
| bagrut `:528` | q3.א.c4 | «…לא להוריד כלום (לא ביקשנו פתרון עם מערך מונים)» | none (no-deduct) | A |
| bagrut `:533` | q3.ב.c2 | «…לא להוריד כלום (חוסר יעילות)» | none (no-deduct) | A |
| bagrut `:658` | q4.ב.c4 | «(לקנוס פעם אחת אם לא בדקו אם arr[i]!=null…)» | amountless | A |
| bagrut `:661` | q4.ב.c7 | «להוריד רק פעם אחת» · «אם טעו פה,להוריד 3 רק פעם 1» | amountless · 3 | A |
| bagrut `:876` | q5.א.c0 | «כל טעות פה להוריד 1» | 1 | A |
| bagrut `:881` | q5.ב.c2 | «…ששונה מ-Null , להוריד 2» · «…גבולות הלולאה להוריד 1» | 2 · 1 | A |
| bagrut `:883` | q5.ב.c4 (SetPeople) | «…להוריד 2, … להוריד 3 … להוריד 2» | 2 · 3 · 2 | A |
| bagrut `:1030` | q6.c0 | «כל טעות להוריד 1» | 1 | A |
| bagrut `:1036` | q6.c6 | «אם הדפיסו את הכמות להוריד 2 (או 1?)» | 2 (or 1?) | A |
| employee `:40` | q1.c0 | «אם שכחו static להוריד 0.5» | 0.5 | A |
| employee `:41` | q1.c1 | «חריגה מהמערך להוריד 2 (15%)» · «לולאה אינסופית: להוריד הכל» | 2 · «הכל» | A |
| employee `:44` | q1.c4 | «…להוריד1–2 נקודות» | 1–2 (range) | A |
| employee `:114` | q2.ד.c0 | «אם לא כתבו static להוריד 1 נקודה» | 1 | A |
| employee `:117` | q2.ז.c0 | 8 phrases: 0.5 · 0.5 · «כל ה- 8%» · 2 · 2 · 1 · «20% מניקוד השאלה (-10)» · «20% (10 נק')» | mixed | A |
| employee `:162` | q3.ב.c0 | «…להוריד הכל» | «הכל» | A |
| employee `:163` | q3.ג.c0 | «…להוריד 0.5 (=1.5%)» | 0.5 | A |
| employee `:164` | q3.ד.c0 | «(אם לא שמו במקום הנכון להוריד 4)» | 4 | A |
| employee `:165` | q3.ה.c0 | «…Get להוריד2 (4%)» · «אחרת להוריד 2» | 2 · 2 | A |
| hobby `:104` | q1.ב.c6 | «…האם יש עדיין מקום להוריד 1» | 1 | A |
| hobby `:109` | q1.ג.c3 | «…שונה מ-null להוריד 1» | 1 | A |
| hobby `:112` | q1.ג.c6 | «…להוריד 1» · «…להוריד 0.5» · «…להוריד 0.5 (רק פעם אחת)» | 1 · 0.5 · 0.5 | A |
| hobby `:113` | q1.ג.c7 | the same three phrases | 1 · 0.5 · 0.5 | A |
| hobby `:191` | q2.ב.c3.s0 | three phrases | 0.5 · 1 · 0.5 | A |
| hobby `:194` | q2.ב.c3.s2 | «…לתכונה chl להוריד 1» | 1 | A |
| hobby `:195` | q2.ב.c3.s3 | «…במקום GetRate להוריד 1» | 1 | A |
| hobby `:196` | q2.ב.c4 (parent row) | «אם חיפשו את המקסימום אך הלוגיקה בסדר להוריד 3» | 3 | A |
| hobby `:202` | q2.ב.c4.s3 | «- לא להוריד, לכתוב הערה» | none (note) | A |
| hobby `:212` | q2.ב.c6.s2 | «…בלי getter להוריד 1» | 1 | A |
| csharp `:247` | q2.ו text | «אי-שימוש בפעולות פנימיות וחיצוניות יגרור הורדת ניקוד.» | unquantified | D |
| employee `:106` | q2.ז text | the same sentence | unquantified | D |
| employee `:156` | q3.ה text | the same sentence | unquantified | D |
| hobby `:83` | q1.ג text | «אי שימוש בפעולות פנימיות יגרור הורדת ניקוד.» | unquantified | D |
| hobby `:161` | q2.ב text | «…אי שימוש במערך צוברים יגרור הורדת ניקוד.» | unquantified | D |
| hobby `:166` | q2.ב text in gold (the corrected contract splits it out as q2.ג) | «אי שימוש בפעולות פנימיות וחיצוניות יגרור הורדת ניקוד.» | unquantified | D |

**The brief's hobby question answered.** The hobby contract's «אי שימוש … יגרור הורדת ניקוד» (`grading_eval_suite/benchmarks/contracts/hobby_tvshow_corrected.contract.json:172` q1.ג, `:332` q2.ב, `:478` q2.ג) is **class D, not class B**. It is a requirement stated to the student in the question body, and it reaches the contract as `sub_question.text` under the splitting rule (`pipeline.py:654-658`). It carries no amount. It already sits in the text that `compile.py:939-941` scans. Today no C1 pattern matches «הורדת» (`plan_gen/prompt.py:42-66`). Once AM-G1 adds that pattern, the hit has no amount, so `compile.py:943` skips it.

**Totals.** In the regression set: A = 28 lines, D = 6 lines, B = 4, C = 1, so **5 lost**. Outside it: 1 more (C, English).

---

## 4. T-3 — The proposal (a direction, not an implementation)

**Shape (TC-1 a).** One new ontology type, in `ontology_types.py` and nowhere else:

```
DeductionLine            # a standalone deduction / no-deduction line, verbatim
  line_id: str           # positional path id, e.g. "q2.ב.d0" (mirrors the criterion_id convention)
  uid: Optional[str]     # server-minted stable identity (P-0), for v6.1's durable references
  text: str              # the teacher's line VERBATIM (ink markers stripped), amount words included
                         # NO points field, NO amount field
```

**Placement (TC-2 a):**
- `Question.deduction_lines: List[DeductionLine] = []`.
- `SubQuestion.deduction_lines: List[DeductionLine] = []`, at any depth. Branch nodes are allowed; the field is orthogonal to criteria XOR sub_questions.
- `ExtractRubricResponse.deduction_lines` and `GradingRubricContract.deduction_lines` for exam-wide lines.

**Extraction.**
- The prompt gains a **fifth role** next to `pipeline.py:634-638`: *STANDALONE DEDUCTION GUIDANCE → `deduction_lines` of the scope whose scoring block it sits in, or of the rubric when it is exam-wide; verbatim; either polarity; never a criterion; never moved into a neighbouring criterion's description.*
- The parenthetical at `:775` and the lines at `:847` and `:844` are rewritten to point at that role.
- `:666` gains an exception: deduction guidance inside the instructions block is not furniture.
- `:731` gains a carve-out: a deduction row with an empty points cell is not a section header.

**Class mapping:**

| Class | Where it goes | Instances |
|---|---|---|
| **B** | The scope's `deduction_lines` | bagrut `:88` → q1.א.1; `:96` → q1.א.2; `:355` → q2.ב; employee `:166` → **q3** |
| **C** | The rubric-level `deduction_lines` | bagrut `:27`; English `body[91]` |
| **A** | Unchanged: stays in the criterion description, where C1 already reads it (`compile.py:226-276`) | the 28 lines of §3b |
| **D** | Unchanged: stays in question text (TC-4) | the 6 lines of §3b |

**FC.**
- The text is verbatim.
- The amount stays as written, inside the text. «נקודה» is not rewritten as `1`, and «20% מניקוד השאלה (7)» is not normalised.
- Nothing is reconciled against point sums: the lines carry no points, so there is nothing to reconcile.
- The teacher sees every line at the rubric gate and can edit or delete it. She is the authority, and a line she cannot see is a line she cannot correct.

**Invariants unaffected by construction:**
- INV-1..4 sum only `criteria`, `sub_questions`, `sub_criteria` and `total_points` (§1).
- StructureExclusivity checks only `criteria` and `sub_questions` (`ontology_types.py:1057-1085`).
- CW-1 is untouched: `GradableScope.criteria` is built by named fields (`gradable_compiler.py:146, 244`), so a deduction line is not a terminal.
- VER-2 is unchanged.

**Subject-agnostic (§3.3):**
- The field and the routing rule live in the base prompt and the base ontology.
- The subject fragments are only appended (`pipeline.py:1118-1128`; `subjects/registry.py:63`).
- The one non-CS instance found is English (§3a).

---

## 5. T-4 — Change list for the ruling

| # | Where | Change | Why |
|---|---|---|---|
| **Ontology** | | | |
| 1 | `app/schemas/ontology_types.py`, near `Criterion` (`:424`) | New `DeductionLine` type. | The single source of truth (§8); no fork elsewhere. |
| 2 | `ontology_types.py:490-563` (`SubQuestion`) and `:567-647` (`Question`) | Add `deduction_lines: List[DeductionLine] = []`. | Class B, at any depth. The Contract reuses `Question` (`:1043`), so the field flows into the contract unless it is stripped. |
| 3 | `ontology_types.py:901-948` (`ExtractRubricResponse`) and `:1017-1052` (`GradingRubricContract`) | Rubric-level `deduction_lines`. | Class C. The Contract is frozen (`:1054`), so the field must be set at construction. |
| 4 | `app/services/contract_compiler.py:173-209` | Do **not** strip the Q/SQ field. Propagate the rubric-level field next to `selection_groups` (`:208`). Mint `uid`s beside `ensure_uids` (`:113`; `services/criterion_identity.py:49-62`). | TC-3 (a). A backfill of stable identity on first compile, as P-0 does. |
| 5 | INV-1..4, INV-6, StructureExclusivity | **No change.** | They never read the field (§1, §4). |
| **Extraction** | | | |
| 6 | `app/services/docx_v3/pipeline.py:459-485`, `:488-515`, `:518-545`, `:558-575` | Add `deduction_lines: List[str]` to `InnerSubQuestionExtraction`, `SubQuestionExtraction`, `QuestionExtraction` and `RubricExtraction`. | The schema slot that does not exist today (T-1). |
| 7 | `pipeline.py:634-638, 666, 731, 775, 844, 847` | Prompt rules, as in §4. | The routing that drops the lines today. |
| 8 | `pipeline.py:1880-1912, 1950` (`_build_response`) | Map the lists to `DeductionLine` with positional `line_id`s. | Nodes are built by named fields; without this the lines would be dropped at build. |
| 9 | `pipeline.py:1259-1301` (`_clean_extraction`) | **No change.** | The lines carry no points. |
| 10 | `pipeline.py:624` (+ its version-comment block), `:79`; `tests/subjects/test_prompt_identity.py:21` | `EXTRACTION_PROMPT_VERSION` bump, `PIPELINE_VERSION` bump, sha re-pin. | An extraction is a function of (prompt, pipeline, model). The schema is model input but is not sha-pinned (F-5). |
| 11 | Package re-baseline (`CLAUDE.md:605`) | k=3, all-5, on terra-high and gpt-5.5. | TC-5. |
| 12 | `app/services/docx_v3/rescale_to_exam.py:1-40` (Math) | **No change.** The text stays as written. | FC. Recorded as risk R-7 for v6.1. |
| **Rubric-eval gold and scorer** | | | |
| 13 | `tests/rubric_eval_suite/benchmarks/bagrut_899371.json` | Add the lines: `:88` → q1.א.1 (`:29`), `:96` → q1.א.2 (`:53`), `:355` → q2.ב (`:276`), `:27` → rubric level. | The gold must encode faithful capture. Gold is a type-valid `ExtractRubricResponse` (`RUBRIC_EVAL_PLAYBOOK.md:67-86`). |
| 14 | `benchmarks/employee_course_select1.json:282` (q3) | Add `:166` at q3. | F-1, TC-6. |
| 15 | `benchmarks/{csharp_plane_combine, foundations_cs, hobby_tvshow}.json` | **No change** (empty lists by default). | They become the false-positive guard. |
| 16 | `tests/rubric_eval_suite/scoring.py:685-880`; `schemas.py:76` (`RubricScore`); `test_scoring.py:93,115` | A new scope-matched `deduction_line_recall` / `_precision` (text fuzzy at `TEXT_TAU`, `scoring.py:48`), with known-answer tests. | No metric sees these lines today. |
| 17 | `tests/rubric_eval_suite/gates.py:25-80` | Nothing at first (TC-6 a). Later, a gate line by ruling. | A gate must not be armed before a baseline shows the target is reachable. |
| 18 | `runner.py:84-100` (`suite_hash`), `:111-112` (gold load) | No code change. **The gold and the ontology must land together.** | A gold edit starts a new comparability epoch. `ExtractRubricResponse` sets no `extra` policy, so Pydantic's default *ignore* would silently drop a gold field the ontology does not know. |
| **API and wire** | | | |
| 19 | `app/schemas/rubric_management.py:105, 152, 385-392`; `app/schemas/rubric_extraction_jobs.py:53` | **No change**: the draft, contract and result travel as `Dict[str, Any]`. | There is no hand mirror of `Question` here. `AnnotationSchema` (`:54`) is untouched because no new annotation is added. |
| 20 | `frontend/src/lib/api-types.ts` (`npm run gen:api`) | Regenerate. | `ExtractRubricResponse` is a `response_model` in `app/api/v0/grading.py:111, 240`. CI drift job: `.github/workflows/api-types-drift.yml`. |
| **Frontend (rubric gate)** | | | |
| 21 | `frontend/src/lib/ontology-types.ts:163-202`; `lib/api.ts:292-300` | Add the optional field to the hand-written mirrors. | These are the wire types the codec imports (`utils/rubric-transform.ts:44-48`). |
| 22 | `utils/rubric-transform.ts:92-101` (`MODELED_*_KEYS`), `:143-197`, `:285-315`; `types/rubric.ts:75-136` | Promote the key to **MODELED**, and hydrate and dehydrate it by name. | If it only stays carried (`_carry`), it round-trips but is invisible and cannot be edited. |
| 23 | `utils/rubric-editor-ops.ts`, `utils/rubric-history.ts` | `*AtPath` ops to edit and delete a line, pure and by reference. | Undo relies on structural sharing (§11). |
| 24 | `components/RubricDocument.tsx:408-457` (`SubQuestionSection`), `:464-541` (`QuestionSection`), `:544` onward (`DocumentHeader`) | Render the lines at their scope, and the exam-wide lines in the header, with the TC-3 status copy. | The teacher must see them at the rubric gate. |
| 25 | `app/page.tsx:440-450` (hydrate), `:897-915` (save envelope) | Read and send the rubric-level field. | This envelope is built **by name**, so a rubric-level field is otherwise dropped. `app/my-rubrics/page.tsx:383-388` spreads `loadedDraft` and needs nothing. |
| 26 | `utils/rubric-transform.test.ts:91-96` | Nothing for Q/SQ: once the gold carries lines, the golden round-trip covers them. Add one round-trip test for the rubric-level field. | The golden suite round-trips `questions` only. |
| 27 | `components/RubricEditor.tsx` (rollback; `lib/flags.ts:10` has the mirror live) | Carry only. | The rollback target stays round-trip safe through `_carry`. |
| **Consumers: v6.1, not Track C** | | | |
| 28 | `app/agents/plan_compiler/compile.py:939-952` | v6.1 reads `deduction_lines` and emits markers with `candidate_anchors` = the scope's terminals (`PR_grader_v6_options.md:424`). | F-4: the current read uses attribute names the scope nodes do not have, and it visits leaves only, so a branch-level line (employee q3) needs a candidate set spanning the branch. |
| 29 | `app/services/gradable_compiler.py:146, 244` | **No change in Track C.** | The v5 grader's input stays byte-identical, and grader-v5.4 is a pinned package. |
| 30 | `app/services/plan_store.py:46-57`; `rubric_management_service.py:253, 399, 539` | **No code change.** | Contracts are dumped with their defaults, so a recompile after Track C adds `deduction_lines` keys, gives a new content hash, and costs one plan rebuild per recompiled rubric (≤ `PLAN_BUILD_ENVELOPE_USD`). Stored contracts keep their hash. Omitting the key when it is empty would avoid the churn; that is a sub-choice under TC-3. |
| 31 | `grading_eval_suite/compiled_rubric_bagrut.json` **(untracked)**, `…/hobby_tvshow_corrected.contract.json` | **No change** (TC-7). | They are Track B's measurement base. |

---

## 6. Open questions and risks

| # | Risk or question | Evidence | Note |
|---|---|---|---|
| R-1 | **Verbatim capture of L27 depends on the model.** The render has already joined the line with the draft-page rules, and there is no delimiter left. | `parser_render.py:455-466`; DOCX `body[13]` `r8 c0` paragraphs 1 and 4–5 | A render change (keeping paragraph breaks in cells) would touch every table in every fixture. That is not proposed. Measure it with fuzzy text match. |
| R-2 | **The scope can be ambiguous.** Employee `:166` sits at the end of q3's single table and names operations used in א/ב (constructor) and ה (getters). Its amount is «מניקוד השאלה». | `employee_course_select1.md:158-167` | Recommended: q3, as written (TC-6). The other four B lines are unambiguous: each sits inside one scope's scoring block. |
| R-3 | **Amounts take four forms.** Numeric (2, 0.5), worded («נקודה»), a percentage of the question with an absolute in parentheses («20% … (7)»), or none. | §3a | C1 matches none of the worded or percentage forms today (`plan_gen/prompt.py:48-57`). AM-G1 adds the worded forms (`PR_grader_v6_options.md` §2.5). The percentage form is a v6.1 question. |
| R-4 | **Polarity.** An exam-wide *no-deduct* line (L27) is guidance, not a charge. | §3a | v6.1 must decide how guidance with no price reaches the verifier. Track C only captures it. |
| R-5 | **The prompt change touches a known-fragile clause.** `:844`'s intervening-lines rule is the 3.8.0 fix for terra emitting «ניקוד: 3 נקודות» as a phantom criterion at q1.א.2, and the intervening line there **is** L96. | `rubric_eval_suite/RUNLOG.md:1766-1779` | This is the TC-5 kill criterion. |
| R-6 | **An honesty gap** between Track C and v6.1: she would see a line that grading ignores. | TC-3 | Copy says so. Alternative: TC-3 (c). |
| R-7 | **Math scale.** An amount in the text is on the teacher's per-question 100 scale, while the points are rescaled to the exam. | `rescale_to_exam.py:5-9` | v6.1 must not read a Math amount as exam-scale. |
| R-8 | **Plan-hash churn** on recompile. | Item 30 | One-time, bounded cost. |
| R-9 | **Thin evidence.** 5 lines over 2 exams sits at the playbook's "provisional" bar. | `RUBRIC_EVAL_PLAYBOOK.md:27` | Recall on n=5 is coarse. That is a reason to keep the metric ungated first. |
| R-10 | **Prevalence in production is unknown.** | — | It would need the AM-G10 read-only role (census Appendix D). |
| R-11 | **The concept overlaps with ALPHA_BACKLOG A-9**, "Deductions as first-class objects with their own overrides". | `docs/ALPHA_BACKLOG.md:28` | One concept, one place: A-9 should build on `DeductionLine`, not on a parallel type. That needs a line in the ruling. |
| R-12 | **Raw pre-cleaner output was never retained** (F-6). | — | Any future re-baseline should retain the raw output for bagrut and employee (`--trace`), so the 0-point path can be observed directly. |

*STOP. Nothing beyond the proposal's direction is designed here. Track C's implementation plan waits on TC-1 … TC-8.*
