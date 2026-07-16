# GT_AUDIT.md — ground-truth audit ledger

> First on-disk entry. The original GT audit (criteria/points/structure/solutions,
> 2026-07-02) predates this file and is recorded in build_benchmarks.py's builders
> and inline [FLAG] notes; this file starts the durable ledger with the PR-1 text
> addendum. Append-only from here.

---

## Addendum — GT text population (PR-1, 2026-07-06)

All 60 `question_text`/`sq.text` nodes were populated MECHANICALLY by
`tools/populate_texts.py` (preview reviewed, then `--write`); hand-editing of text
fields is banned. Source of truth for all text is the RENDERER output of the
fixture DOCX (`parser_render.render_docx_to_markdown`) — never hand-typed, never
the raw XML walk. GT must equal what a correct extraction of the render looks like.

Result: 43 nodes populated, 2 genuinely-null (bagrut q1 / q1.א — no prose in
span), 15 open items (left null; listed below).

### Conventions (§2 of the PR-1 spec — NORMATIVE, verbatim)

1. **`question_text`** = render lines from the line AFTER the question header
   (`שאלה N ...`) up to (exclusive) the first sub-question marker line, or —
   when the question has no sub-questions — up to the first boundary line.
   The question header line itself is EXCLUDED (its content is captured
   structurally in `question_number`/`total_points`).
2. **`sq.text`** = render lines from the sub-question's MARKER LINE (INCLUSIVE —
   markers like `א.` are typically inline with the task sentence; splitting them
   is unnatural, and the pipeline's own `EMPTY_SQ_TEXT` message reads
   marker-inclusive) up to the next sibling marker, first nested-part marker, or
   boundary. Nested (inner) sub-questions: identical rule one level down.
3. **Boundary set** (first hit ends the span): next `שאלה N` header; a line
   starting `מחוון`; the start of a rubric table; a color-marked solution/scoring
   line (`פתרון`/`תשובה`/`ניקוד` in red); end of document.
4. **Red ink is excluded from text spans.** Color-marked content is teacher
   answer/scoring ink and is owned elsewhere (criteria / example_solution /
   annotations). Lines that are entirely color-marked → dropped. Color-marked
   spans inside otherwise-black lines → the marked TEXT is removed, not just the
   markup (e.g., the red fill inside a question's trace-table scaffold is
   solution ink; the black scaffold is question ink — this mirrors the locked
   solution-side convention from the bagrut GT edit, approached from the other
   direction).
5. **Tables inside a question span are question content**, encoded as cell text:
   per row, non-empty cell texts joined by single spaces; rows joined by
   newlines; pipe syntax stripped (matches the encoding precedent set for the
   q1.ב.1 solution table). Fragility acknowledged: table layout is the weakest
   ratio surface; that is a reason to stay ungated, not to drop the content.
6. **`[IMAGE]` markers are kept verbatim** as rendered. (Post-population note:
   no populated span ended up containing an `[IMAGE]` marker — the only image
   blocks in question regions are hobby's solution screenshots, excluded by R1.)
7. **No prose exists for a node → `text` stays `null`** (never empty string).
   Null means "no task prose in the document"; the metric treats it as
   not-comparable, not as zero.
8. Color markup tokens (`[[color:...]]`/`[[/color]]`) are stripped with the same
   regex used in the GT solution edits. Unicode/Cf handling is the normalizer's
   job at compare time — do not pre-normalize GT content.

### Rulings (uniform, document-level; R1–R3, encoded in the tool)

- **R1 — solution label lines are boundaries regardless of ink color.** A line
  whose visible text begins with `פתרון` or `תשובה` ends the span. §2.3's "in
  red" describes the common case; ownership of solution content is content-based.
  Motivated by hobby_tvshow, which labels its image-only solutions with a BLACK
  `פתרון:` line — without R1, that label + 3–4 solution `[IMAGE]` blocks would
  leak into q1.ג / q2.ג texts. Affects: hobby q1.ג, q2.ג (both now clean).
- **R2 — struck-through spans (`~~...~~`) are removed like red ink.** Precedent:
  the locked strike-resolution convention on the criteria side (csharp Q1 6→8,
  18→20, 4→0-drop) treats struck ink as retracted. Affects: bagrut q4.ב only —
  the retracted TopEarners return-value sentence is removed; its red replacement
  sentence is excluded by convention 4; a lone black `.` line (the unstruck
  period after the struck span) remains as renderer-faithful residue. Flagged
  fragility, expected in the low ratio tail.
- **R3 — any Hebrew-letter sub-question marker line ends the running span, even
  when the label has no GT node.** The model sees the marker regardless of GT
  structure: hobby q2's render has a `ג.` task while GT (faithful to the
  mislabeled rubric table) has only א/ב. Without R3, ג's task text would be baked
  into GT ב.text — a span no prompt convention could teach. The unowned ג text
  belongs to no GT node. Deliberately NOT extended to numeric markers: digits at
  line start are routinely task list items (bagrut q5.ב's הערות `1.`/`2.`);
  numeric nested markers delimit only where GT expects a nested child.

### Open items (15 spans left null)

| Fixture | Node(s) | Reason |
|---|---|---|
| foundations_cs | q1, q1.א, q1.ב, q1.ג | Question has GT sub-questions but NO marker lines exist in the render (tasks are unmarked paragraphs; the only `סעיף` lines are inline-מחוון scoring headers, not task markers). Unresolvable under §2. |
| foundations_cs | q2 | Span (task prose → `מחוון` boundary) contains the full model-solution code as an UNLABELED black 1x1 table. §2 has no exclusion for unlabeled solution tables; populating would embed the solution in question_text. Needs a ruling (candidate: extend the boundary/exclusion set to unlabeled code-solution tables — deliberately not improvised here). |
| foundations_cs | q3, q3.א, q3.ב | Same class as q1: no task markers (`סעיף א:` at line 139 is a scoring header). |
| bagrut_899371 | q1.א.2 | The doc marks nested part (1) on the א line but has NO `(2)` marker; א.2's task line (`רשמו בקצרה מה מטרת הפעולה Check`) sits after the red scoring block, outside any resolvable span. |
| bagrut_899371 | q1.ב, q1.ב.1, q1.ב.2 | ב is a GT branch whose children have NO nested markers at all in the render. The branch's own "first nested-part marker" span end is unobservable, and assigning the whole span to the branch would lock text onto the wrong node. |
| bagrut_899371 | q3.ב, q3.ב.1, q3.ב.2 | Same class; note GT's ב.1/ב.2 nested split was itself a flagged authoring judgment (build_benchmarks [FLAG]). |

### Known GT↔prompt divergences (PR-2 must reconcile — the two-column risk)

- **Shared context between markers.** §2.2 assigns everything between two sibling
  markers to the PRECEDING sub-question; the current extraction prompt (SECTION 1)
  teaches "context between markers → question_text". Affected spans where a class
  definition/scaffold sits mid-question: employee q2.ד (Department class),
  hobby q1.א (SchoolHobbies class), hobby q2.א (TvRate class), bagrut q5.א
  (Schedule class). Until PR-2 aligns the prompt, expect these four nodes in the
  low text_ratio tail — that is measurement, not GT error.
- **Page-continuation noise** (`(המשך שאלה 2 - בעמוד הבא)` etc.) is render-real
  and included mechanically (employee q2.ד, hobby q1.א/q2.א). A model will likely
  drop it; small expected ratio dings.

### The pedagogical consistency invariant (R2 ruling, 2026-07-10)

**GT `pedagogical_mistakes` ≡ TierA(faithful draft) ∪ expected-Tier-B.**

Tier A (`_check_point_sums`, `_check_selection_normalization`) is DETERMINISTIC
over the draft. On a faithful draft its output is therefore a function of GT
itself — so GT must expect exactly that output, or the gate is un-passable by
construction (the bagrut contradiction: GT demanded ped=[] while any faithful
extraction of the teacher's 1.5+0.5-under-3 error must fire point_sum_mismatch).
A teacher point-error is intentionally reported on BOTH surfaces — the
rubric_mismatch annotation (draft review) AND the pedagogical mistake (teacher
education) — the same two-surfaces-one-event pattern as annotations+flags (§6
of CLAUDE.md).

Authoring rules:
- Tier-A expectations are TRANSCRIBED from a probe (run detect_pedagogical_mistakes
  on the round-trip faithful draft, llm=None; copy the emission verbatim into GT).
  NEVER hand-author kind/target strings — the emission's shape is the spec.
- Tier-B expectations (structural_mislabel, orphan_criterion) are the ONLY
  hand-authored entries; they encode an expected LLM judgment.
- The invariant is ENFORCED by test_fp123::test_expressibility_round_trip_all_fixtures,
  which runs the real Tier A on every fixture's faithful draft and asserts
  pedagogical_match. A new fixture whose GT violates the invariant fails the
  battery before it can burn a live run.
