# grader-v6 known-answer smoke — english

**Verdict: PASS** · planner `claude-opus-5.5` (planner-v6.2) · plan `fcfd2b467c72…` · verifier Sonnet 5.5 (effort low) · no explainer (the fallback composer's lines) · k=1 · route `direct`

Cost: planner $0.0000 · grading $0.0120 (3 answers) · run `20261017-212210_v6-smoke`

| pass condition | result | |
|---|---|---|
| k1_class_events | 0 | ✅ |
| full_answer_at_full | 0 not full | ✅ |
| intended_share | 12/12 = 100.0% | ✅ |
| validator | fallback scopes 0 · rule-7 downgraded 0 | ✅ |
| english_levels | every credit a compiled `levels` check | ✅ |
| all_answers_ran | 3/3 | ✅ |

Fixture: The Ministry F/G writing rubric is the rubric of exam 016584's writing task; its contract's question text is only «WRITING». The smoke gives it that exam's own task (english_1 q2, verbatim) — the A-9 second-file merge, done by hand for this run only. No wording is invented.

Plan: 4 checks · scope origins {'planner': 0, 'repaired': 0, 'fallback': 0, 'compiled': 1}

## A3_blank — 4/4 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting details) •  | zero | 0/8 zero | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances of languag | zero | 0/10 zero | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of advanced  | zero | 0/16 zero | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on se | zero | 0/6 zero | ✅ |

## A2_partial — 4/4 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting details) •  | partial | 5/8 partial | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances of languag | partial | 6/10 partial | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of advanced  | partial | 5/16 partial | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on se | partial | 4/6 partial | ✅ |

Reasoning lines and the checks behind them:

- **`q1.c0`** — CONTENT AND ORGANIZATION CORRECT : • fully on topic • fully developed (main idea and supporting details) • all elements of task are address…: PARTIALLY CORRECT
  - credit · CONTENT AND ORGANIZATION CORRECT : • fully on topic • fully developed (main idea and supporting details) • all elements of task are address… → **PARTIALLY CORRECT** (5) · «Last summer me and my family was in Eilat and we swim in the sea, it was very hot.»
- **`q1.c1`** — VOCABULARY CORRECT : • correct use of varied and rich vocabulary • appropriate use of instances of language chunks and phrases • correct us…: PARTIALLY CORRECT
  - credit · VOCABULARY CORRECT : • correct use of varied and rich vocabulary • appropriate use of instances of language chunks and phrases • correct us… → **PARTIALLY CORRECT** (6) · «I think it is good to see the nature before it is gone.»
- **`q1.c2`** — LANGUAGE USE CORRECT : • correct use of basic tenses and/or language structures • correct use of advanced language structures • correct wor…: MINIMALLY CORRECT
  - credit · LANGUAGE USE CORRECT : • correct use of basic tenses and/or language structures • correct use of advanced language structures • correct wor… → **MINIMALLY CORRECT** (5) · «My friend go to Iceland last year and he say it was very nice»
- **`q1.c3`** — MECHANICS CORRECT : • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on sentences PARTIALLY CORRECT : • pa…: PARTIALLY CORRECT
  - credit · MECHANICS CORRECT : • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on sentences PARTIALLY CORRECT : • pa… → **PARTIALLY CORRECT** (4) · «But maybe the planes is bad for the enviroment. In the end I want to go becuase it is a la»

## A1_full — 4/4 in the intended class

| criterion | her text | intended | AI | |
|---|---|---|---|---|
| `q1.c0` | CONTENT AND ORGANIZATION CORRECT (8): • fully on topic • fully developed (main idea and supporting details) •  | full | 8/8 full | ✅ |
| `q1.c1` | VOCABULARY CORRECT (10): • correct use of varied and rich vocabulary • appropriate use of instances of languag | full | 10/10 full | ✅ |
| `q1.c2` | LANGUAGE USE CORRECT (16): • correct use of basic tenses and/or language structures • correct use of advanced  | full | 16/16 full | ✅ |
| `q1.c3` | MECHANICS CORRECT (6): • correct use of: spelling • punctuation • capitalization • paragraphing • no run-on se | full | 6/6 full | ✅ |

