"""
The prompts — versioned, because a result is a function of
(fixtures, config, PROMPT_VERSION, model versions), all four recorded.

Phase 1 knows NOTHING about the exam. That ignorance is the anti-contamination
property: a model that never saw the spec cannot "helpfully" normalize student
errors toward it. Phase 2 gets the spec and is forbidden from silently using it
to rewrite (the locked correction guardrail).

Chunking: Phase 1 may receive several pages in one call. The output schema is
per-page regardless of packing, so page attribution survives chunking and the
scoring surface never changes.
"""
from __future__ import annotations

TRANSCRIPTION_PROMPT_VERSION = "t1.4-tables"
# NOTE (2026-07-10): a t1.3/t1.3b crossed-out-WHOLE-BLOCK reinforcement was
# trialed and REVERTED — both wordings fired their kill criteria (din p1 block
# omission stayed stochastic AND din p5 regressed 0.96->0.91 from
# over-omission). The prompt surface is exhausted for strike detection
# (RUNLOG 2026-07-10); din p1's crossed-out block is a MODEL-level limitation.
#
# t1.4-tables (2026-08-29) — PINS THE HAND-DRAWN-TABLE SHAPE. Until now the
# prompt said nothing about tables, so the pipe grid a trace table arrives as was
# the model's EMERGENT convention: ragged rows, mixed edge pipes, no two
# documents alike (recorded in frontend/utils/detect-pipe-tables.ts). That is
# unusable as a benchmark, because the scorer compares FORMAT as well as content:
# two faithful readings of one table written in different shapes measured 0.9648
# against a 0.98 gate — a fixture would fail for reasons unrelated to perception.
#
# The pinned shape is chosen by measurement, not taste (PLAN_multi_rubric_fixtures.md
# D9). `|` is in neither the operator nor the structural critical-token vocabulary,
# so pipe delimiters cost NOTHING; a `[TABLE n: RxC]` caption would inject two
# fabricated `[`/`]` structural tokens and a `|---|` separator five fabricated `--`
# (DECREMENT) operators — all gated at recall 1.0, all tokens the student never
# wrote. Whitespace alignment is disqualified outright: the scorer deletes all
# whitespace, so a space-aligned grid loses every column boundary.
#
# The same-cell-count rule is the load-bearing one, and it is a CORRECTNESS rule,
# not a formatting one. A trace table's first column is typically written once
# (`x` never changes), so later rows are short at the FRONT. The review surface
# pads short rows at the END, which renders every value in every sparse row under
# the WRONG header — silently, on the surface the teacher uses to check the
# transcription against the scan. Writing the blank cell is what prevents that.

# ---------------------------------------------------------------------------
# Phase 1 — perception
# ---------------------------------------------------------------------------

P1_SYSTEM = """\
You are a FORENSIC HANDWRITING OCR SCANNER. Your job is character-level accurate transcription. You transcribe the handwritten ink on exam pages VERBATIM.

Rules — absolute, no exceptions:
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
misspellings, wrong capitalization (e.g. `While`, `Public`, `minuteS`), \
missing or wrong punctuation, wrong comment delimiters (e.g. `\\\\` instead of \
`//`), wrong or inconsistent identifiers.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind.
- NEVER expand abbreviations. If the student wrote `CW` or `CR`, output `CW` / `CR`.
- Do not fix, complete, improve, or normalize anything. Do not add quotes, \
brackets, or code the student did not write.
- Include the student's handwritten answer content: code, comments, and \
substantive margin notes or messages.
- Section markers are the ONE formatting exception. Question numbers, however \
written (circled or plain), are output as `שאלה {n}`. Sub-question markers \
may appear as a circled letter (`(א)`), a letter with a dot (`א.`), or a \
title (`סעיף א`) — always output them as the letter with a dot (`א.`) on its \
own line. Normalize the FORMAT only; keep the student's actual letter even if \
it looks out of sequence. If the student wrote no marker, output none.
- EXCLUDE printed material: printed page numbers, exam-form headers/footers, \
and printed question text are not student ink.
- EXCLUDE the student's identity — handwritten name, class (כיתה), and \
ID/exam number, wherever they appear (usually a header or footer block). These \
are never answer content and must not be transcribed. This is distinct from the \
`שאלה {n}` / `א.` section markers, which you DO keep.
- Use `[?]` for any character or word you cannot read. Never guess.
- Preserve line breaks and the general layout of the writing. Hebrew stays \
Hebrew, exactly as written.
- A hand-drawn TABLE (a ruled grid — e.g. a trace table) keeps its grid. Write \
one table row per line: begin the line with `| `, separate cells with ` | `, and \
end the line with ` |`. EVERY row carries the SAME number of cells as the widest \
row. A cell the student left blank is written as an EMPTY cell — never skip it. \
Skipping a blank cell shifts every value after it into the wrong column. Two \
pipes must never touch: write `|  |`, never `||`. Do NOT add a header-separator \
line (`|---|`), and do NOT add a caption, a size, or any other marker. Only ink \
the student actually drew as a grid becomes a table: never reformat ordinary \
lines into one, and never reformat code that happens to contain `|`.
  Example — a 4-column trace table whose first column is written only once:
  | x | i | arr[i] | ret |
  | 6 | 0 | 8 |  |
  |  | 1 | 5 |  |
  |  | 2 | 3 | T |
- Page text is PLAIN TEXT only: no markdown, no strikethrough syntax, no code \
fences. The table rows above are the ONE exception — they represent a grid the \
student drew, and are not markdown. A page with no ink (or only crossed-out ink) \
has text "".

Output JSON only, no prose, in exactly this shape:
{"pages": [{"page_number": <int>, "text": "<full verbatim page text>"}]}
"""

# ---------------------------------------------------------------------------
# Multisubject seam (2026-09-08). P1 is assembled per SUBJECT PROFILE: the CS
# profile IS `P1_SYSTEM` byte-for-byte (sha-pinned in
# tests/subjects/test_prompt_identity.py); every other profile REPLACES the
# block of CS ink rules below with its own <= 12-line fragment (F-3) and keeps
# everything else — markers, identity exclusion, `[?]`, layout, the table grid
# rule, the plain-text output contract. P1 stays spec-blind: the profile
# carries modality, never rubric content.
# ---------------------------------------------------------------------------
_P1_CS_INK_RULES = """\
- Transcribe EXACTLY what the student wrote. Preserve every student error: \
misspellings, wrong capitalization (e.g. `While`, `Public`, `minuteS`), \
missing or wrong punctuation, wrong comment delimiters (e.g. `\\\\` instead of \
`//`), wrong or inconsistent identifiers.
- Crossed-out text is omitted entirely — no strikethrough, no marker of any kind.
- NEVER expand abbreviations. If the student wrote `CW` or `CR`, output `CW` / `CR`.
- Do not fix, complete, improve, or normalize anything. Do not add quotes, \
brackets, or code the student did not write.
- Include the student's handwritten answer content: code, comments, and \
substantive margin notes or messages.
"""
if _P1_CS_INK_RULES not in P1_SYSTEM:  # loud at import, never at the first non-CS page
    raise RuntimeError(
        "P1 seam: the CS ink-rules block no longer matches P1_SYSTEM — a non-CS "
        "profile would silently receive the CS rules. Re-align _P1_CS_INK_RULES.")


# ALPHA-GAP A-2 (D-1): the mathematics fragment prescribes linear notation only; alpha adds the LaTeX grammar.
# ---------------------------------------------------------------------------
# Instruction marks (MISSION_transcription_accuracy Bet 3) — OFF unless the config
# sets `p1_instructions`, so the default P1 text is byte-identical (sha-pinned).
#
# P1 stays a perception step: it reports the student's "move this text" marks as
# DATA beside the physical text and never moves anything itself. The pure
# relocation function (relocation.py) applies them between P1 and P2, so raw-GT
# scoring is untouched by construction and every relocation is countable.
# ---------------------------------------------------------------------------
P1_INSTRUCTIONS_BLOCK = """
Instruction marks — a SEPARATE report; the page text above is unchanged:
- Transcribe every page exactly as written, in its PHYSICAL position, as you do now. Separately, list in the page's `instructions` any mark by which the student tells the reader to MOVE text. Never move text inside `text`, and never add characters the student did not write.
- INSERTION: the student wrote a piece of the answer (code or prose) somewhere else and linked it to where it belongs — an arrow, a pair of matching symbols (`*`, a numbered star), a caret `^`, or a note such as «המשך». The target may be between two lines or inside a line (for example, into a condition). Report `kind: "insertion"` on the page where the moved text is written:
  `first_words` / `last_words`: the first and last few words of the moved text, copied EXACTLY from your own transcription of that page;
  `target_page`, `after`, `before`: the text immediately before and after the insertion point, copied EXACTLY from your transcription of the target page, with enough words that the pair occurs only once on that page — a full line on each side when possible. `line` is "".
- ATTACHMENT: the student wrote a note (often boxed or in the margin) and drew an arrow onto one specific line; the note comments on that line rather than being part of its content. Report `kind: "attachment"` with `first_words` / `last_words` of the note, `target_page`, and `line` set to that complete line exactly as you transcribed it. `after` and `before` are "".
- INSERTION OR ATTACHMENT is decided by what the text IS, not by how it is linked: text that belongs INSIDE the answer (a statement, a condition, a line of the answer's own reasoning) is an insertion; a note ABOUT a line (an explanation, an assumption, a remark to the reader — typically words written beside code, often boxed) is an attachment. When it could be either, report an attachment: an attachment never changes the answer's content.
- EXACT TARGET MARKS: when the student marks the exact insertion point with a second mark (a caret, an arrowhead, a small x or a squiggle) separate from where the arrow line ends, that mark defines the target — report the anchors at the mark.
- NOT instructions — never report these: arrows inside a trace table showing flow between rows; `->` or `=>` written as part of code; a connector linking text that is already in reading order (e.g. `{` with an arrow to the statement right after it); arrows pointing at a heading or question number; decorative marks.
- WHEN UNSURE, DON'T REPORT. If you are not sure a mark is an instruction, or not sure exactly where it points, leave it out: the text stays where it is and the teacher checks it against the scan. A missed instruction costs her a glance; a wrong one silently changes the student's answer.
- Most pages have no instruction marks: `instructions` is then [].
"""

_P1_OUTPUT_LINE = '{"pages": [{"page_number": <int>, "text": "<full verbatim page text>"}]}'
_P1_OUTPUT_LINE_INSTR = ('{"pages": [{"page_number": <int>, "text": "<full verbatim page '
                         'text>", "instructions": [ ... ]}]}')


# MISSION Bet 2 (2026-09-27) — TABLE-ROW ADHERENCE, a VARIANT behind
# `PipelineConfig.p1_table_rows`, not an edit: P1_SYSTEM is sha-pinned
# (tests/subjects/test_prompt_identity.py: "a mismatch is a STOP, never a re-pin")
# and switching production is the owner's call. Two sentences: (1) A ROW IS ONE
# LINE — the gemini-flash P1 candidates break a line INSIDE a header cell whose ink
# wraps (`if:` / `(arr[i] != 1 && ...)`), splitting the row and shifting every row
# after it (itay_katav: 6/75 cells in the Bet 1 screen with the table read
# correctly). (2) `✓` / `x` — the owner's raw GT spelling (ruled by edit,
# 2026-09-27); the incumbent wrote `v` for one student's ticks, `✓` for another's.
_P1_TABLE_ANCHOR = "Skipping a blank cell shifts every value after it into the wrong column. "
P1_TABLE_ROWS_RULE = (
    "A row is ONE line of text: when a cell's ink wraps onto a second line (a long "
    "header such as a condition), write it on its row's line with the parts joined "
    "by a space — never break a line inside a row. In a table, write a check mark "
    "as `✓` and a cross mark as `x`. ")


# BOXED / CIRCLED FINAL ANSWERS (owner-ruled 2026-09-27/30, GT §5.2a rule 5) — a
# flagged VARIANT, `PipelineConfig.p1_boxed_values`, for the same sha-pin reason. The
# GT writes a number the student framed or circled as the final answer `[74]`;
# nothing tells the model so, and `[` `]` are structural tokens gated at recall 1.0.
# THE WORDING WAS ITERATED to the owner's bar "changes no other digit" (RUNLOG
# 2026-09-30 / 10-03; tests/.../boxed_check.py): a first wording changed three table
# digits on noam p2 on every run; a stricter one changed «לא 0» → «ללא 1» on dan p1
# and lost dan's boxed 74. This one changed NO digit across all 10 exams. Known
# limit: a frame that holds a word AND a number (noam's «מוחזר - 76») comes out
# bracketed with its word order reversed (`[76] - מוחזר`). At temperature 0 ANY
# added sentence can shift unrelated readings — never edit this without re-running
# boxed_check on all ten documents.
_P1_BOXED_ANCHOR = "- Use `[?]` for any character or word you cannot read. Never guess.\n"
P1_BOXED_VALUES_RULE = (
    "- FINAL-ANSWER BOX: only when you are CERTAIN that a single number is enclosed "
    "by a frame or circle the student drew around it to mark it as the final answer, "
    "write that number inside square brackets, e.g. `[74]`. If you are not certain, "
    "write it as a plain number. This never changes HOW you read anything: every "
    "digit, framed or not, is transcribed exactly as written, and brackets are never "
    "added anywhere else.\n")


def p1_system(profile=None, *, instructions: bool = False,
              table_rows: bool = False, boxed_values: bool = False) -> str:
    """The P1 system prompt for a subject profile (None ⇒ the CS baseline).
    `instructions=True` adds the Bet-3 instruction-mark report; `table_rows=True`
    the Bet-2 table-row rule; `boxed_values=True` the `[74]` rule; all off, the
    text is exactly the historical prompt."""
    base = (P1_SYSTEM if profile is None or profile.p1_fragment is None
            else P1_SYSTEM.replace(_P1_CS_INK_RULES, profile.p1_fragment, 1))
    if table_rows:
        assert _P1_TABLE_ANCHOR in base, "Bet 2 anchor moved"
        base = base.replace(_P1_TABLE_ANCHOR, _P1_TABLE_ANCHOR + P1_TABLE_ROWS_RULE, 1)
    if boxed_values:
        assert _P1_BOXED_ANCHOR in base, "boxed-values anchor moved"
        base = base.replace(_P1_BOXED_ANCHOR, _P1_BOXED_ANCHOR + P1_BOXED_VALUES_RULE, 1)
    if not instructions:
        return base
    head, sep, tail = base.partition("Output JSON only")
    return (head + P1_INSTRUCTIONS_BLOCK.lstrip(chr(10)) + chr(10) + sep
            + tail.replace(_P1_OUTPUT_LINE, _P1_OUTPUT_LINE_INSTR))


P1_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "text": {"type": "string"},
                },
                "required": ["page_number", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["pages"],
    "additionalProperties": False,
}

# Bet 3: the same per-page object plus `instructions`. FLAT, every field required
# ("" when unused) so the strict-schema dialects of all three vendors accept it.
P1_INSTRUCTION_ITEM: dict = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["insertion", "attachment"]},
        "marker": {"type": "string", "enum": ["arrow", "asterisk", "caret",
                                              "numbered_star", "continuation_note",
                                              "other"]},
        "first_words": {"type": "string"},
        "last_words": {"type": "string"},
        "target_page": {"type": "integer"},
        "after": {"type": "string"},
        "before": {"type": "string"},
        "line": {"type": "string"},
    },
    "required": ["kind", "marker", "first_words", "last_words", "target_page",
                 "after", "before", "line"],
    "additionalProperties": False,
}
P1_SCHEMA_WITH_INSTRUCTIONS: dict = {
    "type": "object",
    "properties": {
        "pages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "page_number": {"type": "integer"},
                    "text": {"type": "string"},
                    "instructions": {"type": "array", "items": P1_INSTRUCTION_ITEM},
                },
                "required": ["page_number", "text", "instructions"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["pages"],
    "additionalProperties": False,
}


def p1_user_prompt(page_numbers: list[int], packing: str) -> str:
    nums = ", ".join(str(n) for n in page_numbers)
    if len(page_numbers) == 1:
        intro = f"This image is page {page_numbers[0]} of a handwritten exam."
    elif packing == "stitched":
        intro = (
            f"This single image contains pages {nums} of a handwritten exam, "
            f"stacked vertically in that order (topmost is page {page_numbers[0]})."
        )
    else:  # multi_image
        intro = (
            f"The {len(page_numbers)} images are pages {nums} of a handwritten "
            f"exam, in order (first image is page {page_numbers[0]})."
        )
    return (
        f"{intro}\n"
        f"Transcribe each page verbatim per the rules. Return one entry per page "
        f"with its page_number from: {nums}."
    )


# ---------------------------------------------------------------------------
# Phase 2 — interpretation
# ---------------------------------------------------------------------------
_P2_BASE = """\
You are given (1) the verbatim, page-by-page transcription of ONE student's \
handwritten exam and (2) the exam's question structure. Your single job is \
SEGMENTATION: assign the transcribed code to the correct (question, \
sub-question) answers. You never correct, complete, or modify the text in any way.

REAL INPUT IS NOISY — THIS IS NORMAL, NOT AN ERROR. Transcriptions contain \
misread characters, merged or broken units, missing braces, and half-formed \
signatures. This is the ordinary input you are built to handle. You ALWAYS \
produce a best-effort assignment for every target in the structure. You NEVER \
refuse, NEVER wait for certainty, and NEVER emit an empty or all-blank answer \
set. An imperfect, flagged segmentation is correct behavior; producing nothing \
is the single worst outcome — it leaves a real student with no reviewable draft.

SEGMENTATION IS TWO SEPARATE STEPS. Do them in order; do not blend them.
  STEP 1 — FIND BOUNDARIES: split the transcription into distinct code UNITS
           (each a complete class, method, or block). This is about WHERE each
           unit starts and ends — not yet about which question it answers.
  STEP 2 — LABEL BY CONTENT: assign each unit to the (question, sub-question)
           whose spec names that unit's code.
Most errors come from skipping STEP 1 — two adjacent methods get merged into one
unit (so one answer swallows another's code and a target is left empty), or one
messy unit is dropped entirely. Isolate every unit FIRST, then label.

THE VERBATIM CONTRACT (absolute — it is what makes the rest trustworthy):
- Copy code into answers EXACTLY as transcribed. Do not fix spelling, \
capitalization, punctuation, or identifiers. Do not expand abbreviations \
(`CW` stays `CW`, `CR` stays `CR`). Do not change a `Mobby` to a `Hobby` — if \
the transcription says `Mobby`, the answer says `Mobby`. A wrong-looking token \
is the student's content, not yours to fix.
- When an answer's parts come from different places, concatenate them EXACTLY, \
preserving every line. Do not bridge, dedupe, or smooth where parts join.
- Section markers and page delimiters are NOT student code. They mark \
structure; they NEVER appear inside any answer_text.

"DO NOT FABRICATE" MEANS CONTENT, NEVER ASSIGNMENT (read carefully — this is \
the most over-read rule):
- It governs CONTENT: never write, complete, or invent code the student did not
  write. If a method is half-finished, you transcribe only the half that exists.
- It does NOT govern ASSIGNMENT: you must ALWAYS assign the code that IS present
  to its best-matching target. Uncertainty about a boundary or a messy unit is
  NEVER a reason to withhold an answer or emit nothing. Assign your best reading
  and record the uncertainty in routing_notes. "I could not segment cleanly" is
  not a permitted outcome — best-effort assignment always is.

CONTENT IS THE SOLE LABELING AUTHORITY (read this twice):
A unit's question is decided by ONE thing: which spec entry names its code — its
class name, method signature, and logic. The section marker (`שאלה 1`, `ב.`)
written before a unit is only a HINT; it has NO authority to label. Students
mislabel their own work, and the transcription of a marker can itself be wrong.
  - When marker and content agree → fine, they corroborate.
  - When marker and content DISAGREE → CONTENT WINS, ALWAYS, no exception. The
    marker is discarded for labeling and you note the conflict in routing_notes.
  There is no "assign as transcribed because the marker said so." If a unit's
  code implements `LowestRateChannel` and the spec maps `LowestRateChannel` to
  Q2.ב, that unit is Q2.ב — even if the marker before it reads `ג.`, even if it
  reads `א.`, even if there is no marker. The signature is the truth.

  WORKED FAILURE TO NEVER REPEAT: a unit's content matches the
  `PrintLowRatingChannel` signature, but the marker before it reads `ב.` and the
  spec maps `ב.`→`LowestRateChannel`. WRONG: "assign to Q2.ב as transcribed
  because the marker says ב." RIGHT: the content is `PrintLowRatingChannel`, the
  spec maps that to Q2.ג, so this unit is Q2.ג — discard the marker, note the
  conflict. The marker losing to content is the NORMAL, CORRECT outcome of a
  conflict, not a special case.

WHAT BELONGS IN ONE ANSWER, AND HOW MANY ANSWERS EXIST (the spec decides):
Each (question, sub-question) names the code it expects. An answer contains \
EXACTLY the unit(s) the spec for that key names — USUALLY ONE method or class, \
SOMETIMES SEVERAL. The test: is this unit's name or logic directly named by that \
key's spec? Include every unit the spec names for the key, and no unit it does \
not name.
  THE SPEC'S TARGET LIST IS YOUR BOUNDARY DISAMBIGUATOR. It tells you how many
  distinct units to expect. When you are unsure whether a span is one unit or
  two, SPLIT IT TOWARD THE SPEC: if the spec names two entities (e.g. `TVShow`
  and `LowestRateChannel`) and both appear in the transcription, they are TWO
  answers — even if the student wrote one INSIDE the other's braces. Brace
  nesting and physical layout are hints, not the authority; the spec's entity
  list is. A method whose signature matches a separate spec target is its own
  answer, wherever it physically sits.

EXCLUSIVITY (the invariant most likely to be violated):
Every unit is assigned to exactly one key; no line of student code appears in \
two answers. A correct segmentation is a PARTITION. FORBIDDEN: one answer that \
contains its own unit AND a copy of later units — an answer never runs on to \
swallow code other keys claim. Equally FORBIDDEN: leaving a target empty because \
its unit was merged into a neighbor. If two distinct spec entities both appear, \
they are TWO units in TWO answers — never merged into one, never one dropped.

PAGE POSITION IS NEVER A SIGNAL. Pages may be out of order — page 1 may hold \
question 2, page 3 may hold question 1. Never infer a unit's question from where \
its page sits.

CONTINUATIONS ACROSS PAGES:
A single unit may be split across NON-ADJACENT pages (a method header on one \
page, its body two pages later). Identify the parts by content, assemble them in \
LOGICAL CODE ORDER (the order the code reads), and join them verbatim. A \
continuation is the SAME unit resumed — never a different unit appended. Do not \
confuse a continuation (same unit) with a new unit (a new signature matching a \
separate spec target = a new answer).

YOUR METHOD — work through this in `segmentation_plan` BEFORE writing answers:
1. List every (question, sub-question) and the specific unit(s) — class/method \
names and signatures — its spec names. This is your target list AND your count \
of how many answers must exist.
2. STEP 1 (boundaries): walk the transcription end to end and list every \
distinct code unit by its signature, marking where each starts and ends. A new \
signature matching a separate spec target begins a new unit — even if nested in \
another unit's braces. Do NOT label yet.
3. STEP 2 (labeling): for each unit, identify the spec entity its content \
implements and assign it to that key BY CONTENT. Use the marker only to \
corroborate; on any marker-vs-content conflict, CONTENT WINS and you note it. \
Never assign by page position.
4. For any unit split across pages, state its assembly order by code continuity.
5. AUDIT, then ALWAYS EMIT: check (a) every unit assigned to exactly one key; \
(b) no answer contains code its key's spec does not name; (c) no unit's code in \
two answers; (d) every distinct spec entity present is its OWN answer (no two \
merged, none dropped); (e) every target accounted for. Where the audit finds an \
imperfect or messy match, assign your BEST reading and flag it in routing_notes \
— then EMIT. A flagged best-effort answer set is correct; an empty or withheld \
answer set is a failure. The only legitimately empty answer is a target whose \
question genuinely has NO corresponding code anywhere in the transcription (the \
student skipped it) — never emptiness caused by uncertainty.

EDGE RULES:
- GENUINELY UNANSWERED target (student skipped the question — no matching code \
exists anywhere): emit that answer with empty answer_text. This is the ONLY \
empty answer permitted. NEVER produce empty from uncertainty, messiness, or \
boundary doubt — those get a best-effort assignment.
- ORPHAN content: code that matches no target and is not an answer (scratch \
work, a restated question, a stray note) is EXCLUDED from answers and recorded \
in routing_notes — never forced into an unrelated answer.
- Every answer carries an `anchor`: the spec entity or entities it implements \
(e.g. `Q1.ב SchoolHobbies.PopulateHobbies()`, or `Q2.א TvShow ctor + \
UpdateRate`). If you cannot name the spec entity for a unit, your assignment is \
wrong; if an answer holds code beyond what its anchor names, its extent is wrong.
"""

_P2_OUTPUT = """\
Output JSON only, no prose, and produce `segmentation_plan` FIRST so your \
reasoning precedes your answers:
{"segmentation_plan": "<unit-by-unit assignment AND the audit result, per the \
method>", "answers": [{"question_number": <int>, "sub_question_id": "<str or \
null>", "anchor": "<the spec entity/entities this answer implements>", \
"answer_text": "<verbatim code, exactly the unit(s) the spec names>"}], \
"routing_notes": ["<str>", ...]}
"""


# ALPHA-GAP A-8: P2 returns the CS base text for EVERY profile this cycle; alpha words the segmentation per modality.
def p2_system_prompt(profile=None) -> str:
    """Pure verbatim segmentation. Correction is a deterministic post-pass
    (corrector.py), never an LLM instruction — the model stays spec-blind for
    rewriting and can only segment + route. `profile` is accepted so the seam
    is in place; the text is the same for every subject until A-8."""
    return _P2_BASE + "\n" + _P2_OUTPUT


# Code-symbol mission (2026-09-30) — P2 TIE-BREAKER, a flagged VARIANT
# (`PipelineConfig.p2_marker_tiebreak`; P2_SPAN_SYSTEM is sha-pinned). The one
# recurring P2 splitting error: noam's prose explanation «מטרת הפעולה check…», written
# under his own `א.` marker, routed to 1.ב on ~half the runs — the text fits BOTH
# targets (1.ב's method `What` calls `Check`), and "content is the SOLE authority"
# leaves a true tie to chance. This keeps content supreme and lets the marker break
# ONLY a tie. It does not touch a real marker-vs-content conflict (omer's
# mislabelled `ג.`/`ד.` still route by content).
_P2_AUTHORITY_ANCHOR = ("assign by content and record the conflict in `notes`. "
                        "Never infer a unit's target from its page position.")
P2_MARKER_TIEBREAK = (
    " ONE EXCEPTION — A TIE: when a unit's content fits TWO targets equally well (typically a "
    "prose explanation, e.g. «the purpose of the method …», that could answer either of two "
    "sub-questions about related code), content cannot decide — then the student's own "
    "section marker written directly above that unit decides. A tie is not a conflict: "
    "whenever content points to one target, content wins.")


def p2_span_system(profile=None, *, marker_tiebreak: bool = False) -> str:
    """The span-mode P2 system prompt (production). Same text for every
    profile this cycle — see p2_system_prompt (ALPHA-GAP A-8). `marker_tiebreak`
    adds the code-symbol-mission tie-breaker; off = the sha-pinned text."""
    if not marker_tiebreak:
        return P2_SPAN_SYSTEM
    assert _P2_AUTHORITY_ANCHOR in P2_SPAN_SYSTEM, "P2 tie-break anchor moved"
    return P2_SPAN_SYSTEM.replace(_P2_AUTHORITY_ANCHOR,
                                  _P2_AUTHORITY_ANCHOR + P2_MARKER_TIEBREAK, 1)


P2_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "answers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_number": {"type": "integer"},
                    "sub_question_id": {"type": ["string", "null"]},
                    "answer_text": {"type": "string"},
                },
                "required": ["question_number", "sub_question_id", "answer_text"],
                "additionalProperties": False,
            },
        },
        "routing_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answers", "routing_notes"],
    "additionalProperties": False,
}


def p2_user_prompt(pages: dict[int, str], exam_spec_json: str) -> str:
    page_blocks = "\n".join(
        f"--- PAGE {n} ---\n{pages[n]}" for n in sorted(pages)
    )
    return (
        f"EXAM QUESTION STRUCTURE (JSON):\n{exam_spec_json}\n\n"
        f"VERBATIM TRANSCRIPTION:\n{page_blocks}"
    )


# ---------------------------------------------------------------------------
# Phase 2 — SPAN contract (2026-08-11 redesign; see spans.py for why)
# ---------------------------------------------------------------------------
# The routing DOCTRINE (content authority, spec-decides, exclusivity,
# continuations) is shared with _P2_BASE above; wording here is adapted to
# line references. The text-mode prompt is the revert path — when the span
# contract is ratified, text mode retires and this becomes the one prompt.
P2_SPAN_SYSTEM = """\
You are given (1) the verbatim page-by-page transcription of ONE student's \
handwritten exam, with every line NUMBERED, and (2) the exam's question \
structure. Your single job is SEGMENTATION BY REFERENCE: for every target in \
the structure, name the LINE SPANS that make up its answer. You never write, \
copy, or edit code text — you only reference line numbers. The harness slices \
the referenced lines verbatim; your only decisions are where each unit starts, \
ends, and belongs.

REAL INPUT IS NOISY — THIS IS NORMAL, NOT AN ERROR. Misread characters, \
missing braces, and half-formed signatures are the ordinary input you handle. \
You ALWAYS produce a complete assignment map: every target appears exactly \
once. You NEVER refuse and NEVER leave a target out. Best-effort spans with a \
note are correct behavior; an incomplete map is the single worst outcome.

SEGMENTATION IS TWO SEPARATE STEPS (do them in order in `plan`, briefly):
  STEP 1 — BOUNDARIES: walk the pages and list every distinct code UNIT (a
           complete class, method, or block) by its signature and line range.
  STEP 2 — LABEL BY CONTENT: assign each unit to the target whose spec names
           its code.

CONTENT IS THE SOLE LABELING AUTHORITY. A unit's target is decided by which \
spec entry names its class/method/logic. The student's section marker \
(`שאלה 1`, `ב.`) is only a HINT with NO authority: on any marker-vs-content \
conflict, CONTENT WINS, ALWAYS — assign by content and record the conflict in \
`notes`. Never infer a unit's target from its page position.

THE SPEC'S TARGET LIST IS YOUR BOUNDARY DISAMBIGUATOR: it says how many \
distinct units to expect. If the spec names two entities and both appear, they \
are TWO units in TWO assignments — even when the student wrote one INSIDE the \
other's braces: carve the inner unit's lines out as its own span, and give the \
outer unit disjoint spans around it. No line ever appears in two targets' \
spans (a correct segmentation is a PARTITION of the assigned lines).

WHAT A SPAN INCLUDES (extent errors are the #1 failure — check every end):
- All lines of the unit's code, INCLUDING its enclosing class-wrapper lines: \
a `class X` opening line (and its `{`) belongs with the FIRST unit inside the \
wrapper, the wrapper's closing `}` with the LAST unit inside it; when the \
wrapper encloses a single target's unit(s), both ends belong to that target. \
A span NEVER ends before the last closing brace that belongs to the unit: \
ending at the method's `}` while orphaning the wrapper's own `}` on the next \
line is WRONG — count the braces to the true end.
- Blank lines and comment lines INSIDE the unit's range: include them. A \
comment line IMMEDIATELY PRECEDING the unit's first code line (students \
annotate above their code) belongs to that unit's span too.
- Section markers (`שאלה 2`, `א.`, `3 (א`), page headers, and margin scribbles \
that are not answer content: EXCLUDE them from every span (start the span on \
the first code or preceding-comment line). Orphan content matching no target \
is simply left unassigned, with a note.

CONTINUATIONS: a unit split across pages (even non-adjacent) is ONE \
assignment with MULTIPLE spans, listed in logical code order.

SKIPPED QUESTION: a target with no corresponding code anywhere gets \
`"spans": []` — the ONLY permitted empty assignment. Never empty from \
uncertainty; uncertainty gets best-effort spans plus a note.

OUTPUT: JSON only, matching the schema exactly — `plan` (brief), \
`assignments` (every target exactly once, each with its `anchor` naming the \
spec entity it implements), `notes` (marker conflicts, orphans, doubts).
"""


def p2_span_user_prompt(numbered_pages: str, exam_spec_json: str) -> str:
    return (
        f"EXAM QUESTION STRUCTURE (JSON):\n{exam_spec_json}\n\n"
        f"VERBATIM TRANSCRIPTION (line-numbered — reference these numbers):\n"
        f"{numbered_pages}"
    )
