# Math transcription and rendering — plan v2

**Status (2026-10-28): APPROVED, Phases 0–3 BUILT and switched off.** Owner rulings: OD-M2 (the
second reading — nothing he drew is lost or changed), OD-M8, OD-M9, OD-M11. Built under the
plan's recommendations for OD-M1, M3, M4, M5, M6, M7, M10 (the owner said "start implementing";
each is a default to confirm, not a ruling). OD-M12 (the scorer beside the instrument) is NOT
built. Every production change waits behind two env vars that ship empty:
`TRANSCRIPTION_P1_VARIANT=latex1` and `TRANSCRIPTION_FIGURE_MODEL_KEY`. Flip them only when the
Phase 1 gate (§7) is green on teacher-ratified ground truth. Measurements after approval:
`docs/math-rendering/probe-v3/README.md`. What was built, and the new open decisions OD-M13–M16,
are in §10 at the end.

**Goal, restated after review.** A math teacher sees her student's mathematics at the review
screens exactly as he wrote it, and can check, at a glance, every value Vivi read from it
before Vivi grades it. Nothing he wrote is lost, changed, or silently "fixed".

---

## 0. What changed from v1, in one paragraph

v1 measured the wrong ink (the teacher's key, not a student), on a model production does not
run, called a consistent notation rewrite "exact", and judged its own correctness. The review
caught all four. Re-measured properly, the picture is better than v1 claimed in one place and
worse in another: on student pages the production model keeps the student's notation
perfectly and writes clean LaTeX, but vision models are known to silently correct students'
arithmetic, a model reports a drawing "complete" while missing an unlabelled asymptote ten
times out of ten, and unisolated math on an RTL page reverses coordinate pairs. So v2 ships
equations first, shows figures as **the student's own ink with Vivi's reading pinned onto it**
rather than as a redraw, and puts error preservation at the top of the measurement.

---

## 1. Evidence

All runs used the student pages of the two Math fixtures (4-unit p07–p12, 3-unit p07–p10),
k = 5, and **production's exact P1**: `origin/main`'s `prompts.py` loaded verbatim, model
`gemini-3.1-pro-preview`. A second arm ran the pending flash pin that exists only on the WIP
branch. Total spend for both probes: $1.56.

**Equations (P1 transcription, 25 draws per arm)**

| measure | production pro, linear | production pro, LaTeX | flash pin, LaTeX |
|---|---|---|---|
| student's notation kept (√e ×8, e^½ ×1, 1/e ×3, e^-1 ×1 on p11) | 5/5 exact | 5/5 exact | 4/5 (one draw dropped a line) |
| LaTeX spans that KaTeX parses | — | **588 / 588** | 408 / 408 |
| Hebrew inside a math span | — | 0 | 0 |
| delimiters respected | — | yes | **no** on p07: bare `\begin{aligned}` blocks |
| one written line = one line | yes | yes | **no**: separate lines merged into `aligned` |
| Hebrew prose faithful | yes | yes | **no**: wrote "הפרש הסדרה קטן ב-10" where the ink says "התשלום החודשי קטן ב-10 ש"ח" |

**Figures (revised prompt, 5 pages)**

| measure | flash | pro |
|---|---|---|
| p11 traps (drawing says `1/e` and `√e`; the computation beside it says `e^-1` and `e^½`) | 10/10 as drawn | 10/10 as drawn |
| 3-unit sketch says `a=3.6`, the givens say `a=4.8` | kept `3.6`, 5/5 | — |
| pink asymptote tagged as other-colour ink | 5/5 | 5/5 |
| **second sketch's unlabelled asymptote** | **missed 5/5** | **missed 5/5** |
| that figure self-reported as | "complete" | "complete" |
| anchor lands on the label it names | yes, within a grid square or two | yes |
| cost per figure page | $0.008 | $0.009 |

**Rendering, in a real Chromium, on the student's own lines**

| | result |
|---|---|
| KaTeX inheriting `dir="rtl"` | **semantically wrong**: `(1/e, 0)` renders as `(0, 1/e)`; cases brace flips; `S₁₀ = 1.875 S₅` scrambles |
| KaTeX inside `<bdi dir="ltr">` | correct on every line |
| native MathML (Temml) | correct order without isolation; stretchy `cases` brace broken without Latin Modern |
| Hebrew inside `\text{}` | **reversed in all three engines** (`מ"ר` → `ר"מ`) |
| MathLive `<math-field>` in an RTL page | correct; an edit round-trips LaTeX byte-identically |

**Pink ink census.** The 3-unit pages carry pink in the right margin: teacher grading. The
4-unit student pages carry **no pink at all** except one vertical band: the asymptote on p10.

**Literature that changed the plan.**
- *When VLMs "Fix" Students* (EMNLP 2026, 15 VLMs on handwritten student solutions): 42–66% of
  samples contained at least one silently corrected student error; stronger models do it more;
  an "transcribe exactly, including errors" prompt helped by only about 4 points.
- Gemini localisation on documents is coarse in the literature (box IoU ≈ 14% on ExStrucTiny);
  our anchors did better on these pages, but label-level, not stroke-level.
- VGBench: models are weakest at low-level SVG. CDM (CVPR 2025) is the standard formula metric
  but needs a full TeX Live and ImageMagick, and a 2026 follow-up shows it is position-blind.

---

## 2. Verdicts on the review

The review was right more often than v1 was. It was not right everywhere.

| # | Review claim | Verdict | Evidence |
|---|---|---|---|
| 1 | v1 probed the teacher's key, not a student | **True** | p15/p16 are the key's CamScanner pages |
| 2 | The model rewrote notation | **True on the key, false on students.** On p16 it took `e^-1` from the computation instead of the drawing's `1/e`. On the student trap page, 0 drift in 20 transcription draws (4 arms × 5) and in 20 figure-trap readings | §1 |
| 3 | Agreement measures variance, not correctness | **True, and shown twice**: the key's rewrite and the missed asymptote were both perfectly stable | §1 |
| 4 | v1 used a stale model | **True for production.** `origin/main` runs `gemini-3.1-pro`; the flash pin is on an undeployed WIP branch | `two_phase_engine.py` on main |
| 5 | 95% interval on 2 of 3 is about 9–99% | **True** (Clopper–Pearson 9.4–99.2%) | arithmetic |
| 6 | "Identical graph" is unsatisfiable by a redraw | **True.** Only the ink is identical | §3 |
| 7 | The pink asymptote may be the teacher's | **Not supported.** The 4-unit paper has no teacher grading in pink anywhere; the review borrowed the 3-unit teacher's colour. It is at least as likely the student's own pen | pink census |
| 8 | Strip teacher ink from fixtures by colour mask | **Rejected.** On this paper it would delete the student's asymptote. Colour is not provenance | pink census |
| 9 | KaTeX inherits RTL and garbles | **True, and worse than stated**: it reverses coordinate pairs | render test |
| 10 | Hebrew stays outside math spans | **True**: Hebrew in `\text{}` reverses in every engine, and production P1 already complies (0 of 588) | render test, probe |
| 11 | RTL in math editors is uneven | **Not for MathLive on our test**: correct render and byte-identical round-trip. A caret bug is reported upstream; a teacher must try it | MathLive test |
| 12 | Use CDM to score structure | **Rejected as the gate.** Heavy toolchain and position-blind. Canonical-token matching is the gate; CDM stays an optional offline check | literature |
| 13 | Doc-ratio is blind to a wrong digit | **True** by arithmetic: one digit in 200 characters leaves 0.995 | — |
| 14 | Overwritten digits: `23.259` corrected to `23.25` | **Wrong example.** The student's own perimeter, 66.518 = 2 × 23.259 + 20, shows he used 23.259. Writing 23.25 would break his arithmetic. The convention point stands | 3-unit p08 |
| 15 | Sign tables are missing from v1 | **True.** Production pro already renders them as a table with the student's arrows as `\searrow \cup \nearrow` | probe |
| 16 | Geometry is not "nearly free" | **True**, including the `a=3.6` / `a=4.8` inconsistency, which the reader keeps | probe |
| 17 | Drawings carry about 8 of 100 points | **Roughly**: 8–12 on the 4-unit paper depending on question choice (Q4ז is also a sketch), 0 on the 3-unit | the key's weights |
| 18 | Remove the `grader-frontend/` duplication | **Wrong.** It is the deploy mirror, overwritten by robocopy and never hand-edited (CLAUDE.md §10). Edit `frontend/` only | CLAUDE.md |
| 19 | Add a new `TranscriptionProfile` type | **Principle accepted, type rejected.** `SubjectProfile` already carries an unused `modalities` field; a second profile concept breaks one-concept-one-place. Extend the existing one | registry on main |
| 20 | Editing the math fragment does not change the stamp | **True.** The stamp is `base + "+mathematics"` with no fragment version | registry on main |
| 21 | Gate deductions on a `complete` flag | **Refined.** The model called a figure "complete" while missing its asymptote 10/10. Self-reported completeness cannot gate a deduction | probe |
| 22 | Remove the separate localise call to save cost | **Moot.** The figure pass is already one call per figure page that both localises and reads | probe |

**Two things neither document had.** The over-correction risk in §1, which is the most
dangerous failure for grading. And cancellation marks: the student strikes `a₁` on both sides
of an equation, which is mathematics, not crossed-out work, and production's strike-check pass
deletes lines it believes are struck.

---

## 3. The target: the ink is the identical graph

Only the student's ink is identical to what he drew, and it is already on the review screen.
What the teacher cannot see today is **what Vivi understood from it**, and that is what the
grader will consume.

So the deliverable for every drawing is the **crop of his ink, with Vivi's reading pinned onto
it**: a small chip on each mark Vivi read (`min (√e, −2.25)`, `x = 2`, `1/e`), and beside it a
list of those readings, each editable. A misread sits on the very mark it came from, so she
sees it without comparing two pictures. Nothing is drawn that he did not draw, so nothing is
drawn wrong. The probe shows the anchors are accurate enough for this.

A clean schematic redraw stays possible (§7, Phase 4), but only if a test shows it helps a
teacher catch errors faster. **This is an open decision for you** (OD-M2), because it answers
your original wording: did "the actual identical graph" mean the screen should look like his
drawing, or that nothing he drew is lost or changed? This plan assumes the second, and the ink
already delivers the first.

---

## 4. Equations

**Notation.** Under the math profile, P1 writes every piece of mathematics in LaTeX between
`\(` and `\)`, in the student's own form. Production pro already does this cleanly (§1).

**Conventions, written before any ground truth** (`TRANSCRIPTION_GT_CONVENTIONS.md` v2):

1. The student's form is answer content: `\sqrt{e}` is not `e^{1/2}`, `\frac{1}{e}` is not
   `e^{-1}`, an exact value is not its decimal.
2. Hebrew words and units stay outside the spans.
3. One written line is one transcribed line. `cases` is allowed for a brace system; `aligned`,
   `align` and `gather` are not, because they merge lines and break P2's line-based slicing.
4. A framed final answer is `\boxed{...}` inside the span. Under the math profile this replaces
   the CS convention `[74]`, because square brackets are mathematical content here (`[3, ∞)`).
5. Cancellation slashes are `\cancel{...}`, kept; they are not crossed-out work.
6. Overwritten digits: the final legible digit, and when in doubt the student's own downstream
   arithmetic decides (the 23.259 case).
7. Sign-table arrows: `\nearrow`, `\searrow`, `\cup`, `\cap`.
8. A figure line keeps today's form with an id: `[איור 1: …]`.

**Equivalence is typographic only**: `\frac` = `\dfrac`, `\left(` = `(`, spacing, redundant
braces. Never mathematical equivalence. One canonicaliser, in Python, used by both the eval
suite and the grader's quote check.

**Validation after P1, pure and deterministic.** Every span must parse; no LaTeX command may
appear outside a span; no forbidden environment. A violation becomes an INFO annotation and the
span shows as raw text with a marker. It never drops text. It becomes a triage reason only
after its false-flag rate is measured, because `code_lint` taught us what a check that fires on
most documents does to trust. (`code_lint` itself counts LaTeX braces and must be gated to the
code modality.)

**Rendering.** One `MathText` component, used on every surface that shows answer text: the
transcription review, grade review and its evidence quotes, the explainer's lines. KaTeX
inside `<bdi dir="ltr">`, code-split so CS and English pages load nothing. Pinned by a
Playwright bounding-box test whose vector is the reversed coordinate pair. A span that fails to
render shows raw with a marker.

**The PDF the student receives** is rendered by PyMuPDF and cannot run KaTeX. In v1 it gets a
deterministic LaTeX-to-Unicode linearisation (`√e`, `e²`, `1/e`) for any math in feedback text.

**Editing.** Teachers do not edit LaTeX. Rendered view; click an equation and a MathLive field
opens for that span only, lazy-loaded (227 KB gzipped). Prose is edited as text. A span is
written back only if she changed it, which keeps "viewing is not commitment". A span must parse
in both KaTeX and MathLive, pinned by a shared test corpus, so what renders is what edits. A
spike decides the line editor's mechanics, and a teacher tries it before it ships.

**Evidence highlighting** is character-offset based. A quote that touches part of a rendered
span highlights the whole span.

**Tables.** Sign tables and proportion tables go through the existing hand-drawn table lens,
with LaTeX cells.

---

## 5. Figures

**The figure pass.** Triggered only on a page whose P1 text contains a figure line, so its cost
follows the figures. One call per such page returns, for each drawing, its box and a flat list
of features: `kind`, `as_written` (LaTeX, copied from the drawing), `point` [y, x], `ink`
(primary or other), `uncertain`. Flat, because union types in structured output differ across
providers. Validated with Pydantic after the call. It is an optional pass under the transcription
budget, beside the strike check: any failure leaves the caption line standing.

**The rule that fixed drift:** copy each label from the drawing, never from the computation
beside it, even when it is the same number written another way.

**Data.** The answer string stays the only truth and keeps the `[איור 1: …]` line. Figures ride
on the Draft answer as a typed list, are editable at the transcription gate, and freeze into the
Contract at `/grade`, together with the page reference so the crop can be shown later. New named
compile invariant, **FIG-1**: every figure line maps to exactly one figure and every figure to
one line.

**Review.** The crop of the ink with chips at the anchors, and the feature list beside it: hover
a row to light its chip, edit or delete a row, add a missed feature, mark one "not the student's
ink". Other-colour ink is shown with a marker, never dropped.

**Grading, with no change to the grader.** At gradable compile, each figure line expands into one
deterministic text line per reviewed feature, for example `איור 1 · אסימפטוטה אנכית: \(x=2\)`.
The grader quotes those lines, the existing quote validator finds them, and EVD-1 records that
text as what was graded. On the grade review screen a quote on such a line lights its chip on the
ink. This is "show your work" for a drawing, built from parts that already exist.

**Absence is not evidence.** A model can miss what is drawn and still call the figure complete.
So any deduction on a check in a scope that contains a figure raises a review marker, a new
look-count reason beside the existing six, until figure recall is proven on fixtures. The marker
sends her to the ink; it never blocks approval.

---

## 6. The top risk: silently corrected arithmetic

If the student writes `2 × 3 = 5` and the transcription says `6`, the grader awards a point
he did not earn and nothing on the screen shows it. The literature says this happens often,
that stronger models do it more, and that prompting barely helps. Our fixtures have no seeded
errors yet, so we do not know our rate.

1. **Measure it first.** A seeded-error set: at least 30 deliberate errors across at least 10
   pages (a wrong digit, sign, exponent; a value inconsistent with the givens), written by hand.
   Preservation must be 100% on the typed fixtures and is reported per error type.
2. **Only if that fails**, a structural defence rather than another prompt: re-read each number
   from a crop with no surrounding equation, so there is nothing for the model to "fix" toward.
   The focus pass already has this shape, and its guard can be narrowed to allow digit changes
   only.

---

## 7. Phases and gates

Each phase ships only when its gate is green. Implementation branches from `origin/main`: this
working tree is a WIP branch 210 commits behind production.

**Phase 0 — conventions, fixtures, instrument.**
- Write the v2 conventions (§4).
- Fixtures: the two student papers here, one class set of ungraded scans, and the seeded-error
  set.
- Ground truth: the agent pre-fills a draft and a math teacher ratifies it line by line. The
  ratification is the ground truth. (The agent's own count on p12 was wrong; the models were
  right.)
- A `MATH_V1` scorer profile beside the instrument, exact on numbers, signs, relations, function
  names and scope (exponent, subscript, numerator, radicand). This touches the eval suite's
  instrument territory, so it needs your sign-off.
- The typographic canonicaliser.

**Phase 1 — equations and tables.** The adoption win, and a prerequisite for figures, whose
labels are equations.
- `SubjectProfile` gains `notation` and `figure_kinds`, and a fragment version that joins the
  prompt-version stamp.
- The LaTeX fragment, the validator, `code_lint` gated to code, and the strike check tested on
  cancellations.
- `MathText` on every surface, the Unicode linearisation for the PDF, MathLive span editing, and
  quote canonicalisation.

**Phase 2 — the crop reaches the reviewer.** Page references through the Contract and
gradable test, so every surface can show the ink behind an answer. Useful on its own.

**Phase 3 — figures as checkable readings.** The figure pass, FIG-1, the overlay and feature
list, the feature editor, compile-time expansion for the grader, and the absence marker.

**Phase 4 — schematic redraw, conditional.** A seeded-error test with a math teacher: overlay
only, redraw only, and both. Build the redraw only if it raises the catch rate or cuts time. If
built: place features at their detected positions (his scale, not an invented one), interpolate
with a monotone cubic so no extremum appears that he did not mark, and keep the drawability gate.

**Phase 5 — over-correction defence, conditional** on Phase 0's measurement (§6).

**Gates**

| claim | measured as | passes at | kills it |
|---|---|---|---|
| student errors survive | seeded-error set | 100% typed; reported per type for handwriting | any silent correction |
| numbers survive | `MATH_V1`, per answer | 1.0 | any wrong digit, sign or decimal point |
| notation survives | value equal, form changed | 0 | any normalisation |
| structure survives | canonical-token match | ≥ 0.95 per answer | wrong scope in an exponent, fraction or radicand |
| spans parse | renderer's parser | ≥ 99%, failures visible | a silent drop |
| figure features read | recall on student sketches, incl. unlabelled lines | ≥ 90% | — |
| nothing invented | features with no ink | 0 | any invented asymptote, point or extremum |
| teacher time | seconds and edits per math page vs CS | at or below CS | above CS |
| CS untouched | P1 prompt hash and outputs on CS fixtures | byte-identical | any change |
| cost | per math document | your ruling (OD-M9) | above it |

The teacher-time row answers to the north star. Perfect recall that takes longer to review
than reading the ink fails, whatever the other rows say.

---

## 8. Open decisions

| ID | Decision | Recommendation |
|---|---|---|
| OD-M1 | How math mode is switched on | Extend `SubjectProfile` with capabilities (`notation`, `figure_kinds`); the frontend keys on them, never on the subject string |
| OD-M2 | What "identical graph" means; the v1 figure surface | Nothing lost or changed: ink plus pinned reading. Redraw only after the test |
| OD-M3 | When two notations count as the same | Typographic only; form is answer content |
| OD-M4 | Other-colour ink | Tag and show with a marker; never drop; colour is not provenance; no colour masks |
| OD-M5 | Deducting in a scope with a figure | Always a review marker, until figure recall is proven |
| OD-M6 | How teachers fix equations | MathLive per span, after a spike and a teacher trial |
| OD-M7 | Figure-line integrity | Named compile invariant FIG-1 |
| OD-M8 | P1 model for math | Production pro. The flash pin broke delimiters, merged lines and paraphrased Hebrew under LaTeX. If CS moves to flash, math keeps pro through a per-profile model key |
| OD-M9 | Cost per math document | About $0.10–0.12, estimated from measured per-page costs (P1 pro with LaTeX $0.011/page, figure pass $0.009 per figure page) for a six-page paper, vs the CS eval gate of $0.08. Rule a math ceiling, then measure it on the class set |
| OD-M10 | Math in the student's PDF | Unicode linearisation in v1 |
| OD-M11 | Who authors ground truth | Agent pre-fills, math teacher ratifies |
| OD-M12 | `MATH_V1` scorer beside the instrument | Approve; it is instrument territory under §17.7 |

---

## 9. What this plan cannot claim yet

1. No accuracy number for students' handwriting at scale: two papers from one school.
2. No measured rate of silently corrected arithmetic on our pipeline. The literature says it is
   the most common VLM failure on student math.
3. Figure recall is unknown beyond these pages, and the one measured miss (an unlabelled
   asymptote) was invisible to the model's own completeness flag.
4. No teacher has tried MathLive editing, the overlay, or any of this on a real batch.
5. The pink asymptote's provenance is unknown. The design does not need to know it, which is
   the point of OD-M4.

---

## 10. What is built (2026-10-28) and what is newly open

**Built, tested, switched off.**

| piece | where | switch |
|---|---|---|
| Conventions v2, written before any ground truth | `docs/math-rendering/TRANSCRIPTION_GT_CONVENTIONS_MATH.md` | — |
| Seeded-error spec (what to write by hand) | `docs/math-rendering/SEEDED_ERRORS_SPEC.md` | — |
| Spans, validator, typographic canonicaliser, PDF linearisation | `backend/app/services/math_notation/` | pure |
| `latex1` P1 variant = fragment + **1 page per call** (probe v3 §3) | `subjects/profiles/mathematics`, `PipelineConfig.p1_variant` | `TRANSCRIPTION_P1_VARIANT` |
| One INFO `math_notation` annotation per answer; `code_lint` only under `code` | `two_phase_engine` | inert without spans |
| Quote check compares math typographically | `agents/grader/validator.py` | identity without spans |
| Student PDF: math linearised and LTR-embedded | `returned_exam._escape` | identity without spans |
| One contract builder; contracts carry pages + figures (A-4 closed) | `services/transcription_contract.py` | — |
| Figure pass (optional, budgeted, never edits text) | `two_phase/figure_pass.py`, `Pipeline.read_figures` | `TRANSCRIPTION_FIGURE_MODEL_KEY` |
| **FIG-1 FigureLineIntegrity** on the Contract type | `services/figures.py`, `TranscriptionContractAnswer` | — |
| Readings expanded into quotable lines for the grader (EVD-1 records them) | `gradable_compiler` | identity without figures |
| `figure_deduction` look marker + a v6 notice beside the answer | `look_count.py`, `look-count.ts`, `review-markers.ts`, `GradeReviewSurfaceV6` | needs a figure line |
| `MathText` (KaTeX in `<bdi dir=ltr>`, code-split), `ProseMath`, the `math` answer mode | `frontend/src/components/math/` | `hasMathNotation(subject)` |
| Transcription gate: click a formula → MathLive, click a line → text | `MathAnswerEditor` | answers with spans |
| Figure card: the student's ink cropped, readings pinned, editable | `FigureCard` + controller plumbing | answers with figures |
| Coordinate-order guard, Δ14 and splice pins | `e2e/math-review.spec.ts` | — |

**FIG-1 as built is one-directional**, a refinement of §5's wording: every frozen figure sits on
exactly one figure line, but a line may have no figure. §5 makes the figure pass optional, and a
bijection would have made an optional pass block approval. An unread drawing is shown as such.

**Newly open**

| ID | Decision | Recommendation |
|---|---|---|
| OD-M13 | The strike check deleted two **unstruck** lines holding a student's error, 1 in 5 draws (probe v3 §7). It runs on CS too | Measure it on the seeded-error set before the math flip; if it repeats, require two agreeing votes for any deletion under the math profile |
| OD-M14 | A framed answer that mixes Hebrew and math (`השטח גדל ב- 56.25%`): conventions 2 and 4 conflict | Frame the math only, Hebrew outside: `השטח גדל ב- \(\boxed{56.25\%}\)`, recording the frame on the math it encloses. A teacher should rule |
| OD-M15 | Prompt iteration on dense pages redistributes failures (probe v3 §5) | Stop prompting; measure the shipped fragment against ratified ground truth. If the gate fails on Hebrew prose or drawing lines, that is a model decision for you, not another prompt |
| OD-M16 | Production's 3-pages-per-call P1 misread the student's Hebrew on a dense math page 5/5 | Math runs 1 page per call inside `latex1`. Whether CS should be re-checked at 1 page per call is yours |

**What the owner provides next:** the math teacher's ratification of the pre-filled ground
truth (OD-M11), the handwritten seeded-error pages (`SEEDED_ERRORS_SPEC.md`), and rulings on
OD-M12–M16.
