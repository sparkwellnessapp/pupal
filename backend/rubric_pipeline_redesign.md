# Rubric Pipeline Architectural Redesign — Agent Instruction Manual

**Purpose**: This document gives you the complete context needed to write and execute a world-class implementation plan for transforming Vivi's DOCX rubric extraction pipeline. Read it fully before writing any code or plan.

**Your deliverable**: A detailed implementation plan covering both the architectural redesign (Sections I–III) and the enhancement layer transformation (Section IV). After approval, you will execute that plan.

---

## Crucial Principles & Insights

Before diving into specifics, internalize these. They are the foundation of every design decision in this document.

### Principle 1: The Abstract Pipeline Sequence

The complete rubric extraction flow, at the highest level of abstraction, is:

```
Upload rubric DOCX
    → Parse and annotate the content (deterministic)
    → LLM receives rendered content, understands the overall rubric and each
      object's identity, builds a normalized rubric_draft (semantic)
    → rubric_draft is passed to the LLM enhancement layer which executes
      the ontological chain of actions and builds the complete rubric_draft (semantic)
    → rubric_draft is parsed and displayed to the teacher in RubricEditor.tsx
    → Teacher reviews, approves or edits however she wants, clicks save
    → Rubric is saved and ready for grading
```

Every implementation decision should serve this sequence. If a piece of code doesn't clearly map to one of these steps, question whether it should exist.

### Principle 2: LLM Leads, Deterministic Code Verifies

The LLM is the semantic authority. It understands Hebrew, distinguishes tasks from definitions, grasps pedagogical intent, and can build complete structured representations from text. Deterministic code handles only deterministic problems: parsing table cells into numbers, validating point sums, constructing typed objects.

**Never let dumb pattern-matching code override or reconstruct what a smart LLM already understood correctly.** If you find yourself writing code that reconstructs information the LLM already had, you're going the wrong direction.

### Principle 3: What Sub-Questions Are

Whenever sub-questions exist in an exam, it should be expected that:
- Each **sub-question** is a **direct question or task for the student to answer** — it contains action verbs like "כתבו" (write), "הגדירו" (define), "חשבו" (calculate), "הדפיסו" (print).
- The **question body** (context_text) is generally the "story" — property/parameter definitions, background context about the problem, class structure descriptions, etc.
- Property definition lists (e.g., "arrEmployees – מערך חד-ממדי של עובדים") are **context, not sub-questions**, even when they appear as DOCX list items.

This distinction is trivial for an LLM but impossible for regex/list-detection patterns. The classification system prompt must make this principle explicit.

### Principle 4: Clean Rendered Content Enables Great LLM Classification

An LLM can do an excellent job building a normalized rubric JSON as long as:
1. **The rendered content it receives has clear, simple annotations for every object's identity** — `[TABLE #N: ...]`, `[SQ: X]` (sub-question hint; next line has original א./סעיף א), `[EXAMPLE_SOLUTION]`, `QUESTION N (pts)` section headers. Code is plain text (no [CODE_BLOCK]).
2. **The annotations are not noisy** — no element IDs, no formatting metadata, no confidence scores. Just clean semantic markers that help the LLM orient itself.
3. **The prompt gives clear, detailed instructions and principles** — what to extract, what the output schema means, what the semantic distinctions are (context vs sub-question, rubric table vs trace table).

The renderer's job is to produce text that is **easy for an LLM to read and understand**, with just enough structural markers to identify object types. Nothing more.

### Principle 5: The Element-ID Grounding System Is Architectural Debt

The current pipeline sends text to the LLM, gets back abstract structure (no text), then spends ~400 lines of code trying to link that abstract structure back to document paragraphs via element IDs — only to read the `.text` property of those paragraphs, which is the same text the LLM already read.

This round-trip exists because the pipeline was designed in an era of lower LLM trust: "let the LLM classify structure, but use deterministic code to extract content." In 2026, with models that can perfectly parse Hebrew exam documents, this indirection is pure cost. The LLM should output the content directly.

### Principle 6: The Correct Ontological Chain for Enhancement

The criterion enhancement must follow this chain, in this exact order:

1. **Understand and Complete** — What knowledge/skills does this question test? Are there missing criteria? Create any missing ones (text only).
2. **Evaluate and Rebalance** — Given the question's purpose, reassign point distribution across ALL criteria based on relative importance to measuring what the question was designed to measure.
3. **Generate Reduction Rules** — For each criterion, does it have multiple binary aspects? If yes, break into reduction rules. If no, single binary rule.
4. **Define Scoring Levels** — For each rule, determine: is this binary (pass/fail) or does it have meaningful intermediate states? If multi-level, define graduated levels with specific condition_hints that serve as grading instructions for the TestGrader agent.

Steps 1-2 require a holistic view of the question. Steps 3-4 are per-criterion. This means the enhancement architecture must be question-level-first, then criterion-level — not the current per-criterion-in-isolation approach.

---

## Section I: Problem Statement

### What Broke

We uploaded a real Hebrew CS exam DOCX with 3 questions. Question 2 has 7 sub-questions (א-ז) split across two OOP classes (Employee and Department). The pipeline produced three categories of bugs:

**Bug A — Wrong sub-question text assignment.** Q2.א displayed "arrEmployees – מערך חד-ממדי של עובדים (Employee)" — a class property definition, not a sub-question. The correct text is "כתבו את כותרת המחלקה ואת התכונות שלה."

**Bug B — Scrambled sub-question identity.** Sub-questions ה, ו, ז (which belong to the Department section) were assigned to IDs א, ב, ג because the annotator restarted its Hebrew letter counter on each new DOCX list group.

**Bug C — Criteria duplication.** The 6 rubric table rows were extracted as direct question-level criteria (correctly enhanced with 27 reduction rules), and then 7 synthetic placeholder criteria ("מענה על סעיף X") were generated for each sub-question. Result: 13 criteria for a 50-point question — the real ones orphaned at the wrong level, the sub-questions filled with garbage.

### Why the Fixes Keep Compounding

Bug A required a composite-key fix in the sub-question lookup. Bug B required snippet-based verification during linking. Bug C required a distribution heuristic to move criteria from question level to sub-question level. Each fix added complexity to a fundamentally broken grounding system. We were patching symptoms of the architectural debt described in Principle 5.

---

## Section II: Root Cause — The Grounding Round-Trip

### The Current Data Flow

```
DOCX bytes
    │
    ▼
Parser ──→ DocxDocument tree (paragraphs with element IDs, tables, shapes)
    │
    ▼
Annotator ──→ Labels on each element (QUESTION_HEADER, SUB_QUESTION, CODE_BLOCK, etc.)
    │              Uses regex patterns + DOCX list_info for sub-question detection
    │              ⚠️ Cannot distinguish property-definition lists from sub-question lists
    │
    ▼
Renderer ──→ Flat text for LLM (strips annotation labels, preserves raw text + table markdown)
    │              Only uses annotations for question-header section separators
    │
    ▼
LLM Classifier ──→ ClassificationResponse (question boundaries, sub-question snippets,
    │                   table types) — PERFECT semantic understanding, but NO element IDs
    │
    ▼
_populate_question_elements() ──→ Walks document, reads ANNOTATOR labels (not LLM output),
    │                                 assigns element IDs to questions/sub-questions
    │                                 ⚠️ Trusts annotator blindly, ignores LLM text snippets
    │                                 ⚠️ This is where all three bugs originate
    │
    ▼
Transformer ──→ Uses element IDs to read paragraph text back from document tree
                    Every ID lookup ends at .text — reconstructing what the LLM already read
```

### Why the LLM Got It Right Despite the Annotator Being Wrong

This is the key insight that unlocks the entire redesign:

The renderer does NOT pass the annotator's labels to the LLM. It passes the **raw paragraph text** in document order. The `_render_paragraph` function (renderer.py) just returns `para.text.strip()` — no annotation labels attached. The LLM reads clean Hebrew text, understands semantically what each paragraph is, and classifies perfectly.

The annotator's errors don't corrupt the LLM's input because the renderer strips labels. But the annotator's errors DO corrupt the linking step (`_populate_question_elements`) because that function reads the annotator's labels — not the LLM's output — to decide which paragraph is which sub-question.

### The Fatal Overwrite Mechanism

The annotator's list-based sub-question detection walks DOCX list items and assigns Hebrew letters sequentially (א, ב, ג...). When it encounters a new DOCX list group (different `list_id`), it **resets the counter to 0**. In our test document, Q2 had three DOCX lists:

- List A (sub-questions א-ד): Correctly labeled
- List B (Department property definitions): **Incorrectly labeled as sub-questions א, ב** (counter reset)
- List C (sub-questions ה-ז): **Incorrectly labeled as א, ב, ג** (counter reset again)

Then `_populate_question_elements` walks the document sequentially and **overwrites** each sub-question's header every time it sees a matching annotation. The property definition "arrEmployees" gets temporarily assigned as Q2.א's header. Then list C's first item overwrites it again — assigning sub-question ה's text to the ID א.

Everything is scrambled because the pipeline trusts annotation labels over the LLM's correct semantic understanding.

---

## Section III: The Redesign — LLM-First Classification

### 3.1 Enhanced Renderer

The renderer outputs flat text with `[TABLE #N]` headers and `[EXAMPLE_SOLUTION]...[/EXAMPLE_SOLUTION]` for explicitly labeled solutions. Code and body text are emitted as plain text (no `[CODE_BLOCK]` markers); the classifier puts all content in full_text. Sub-question hints are emitted as `[SQ: X]` followed by the **same paragraph line** so the original indicators (א., סעיף א) remain visible.

```
[EXAMPLE_SOLUTION]
public static boolean isValid(int[] arr) { ... }
[/EXAMPLE_SOLUTION]
```

**Important**: Sub-question annotations produce a `[SQ: X]` hint line, but the next line is always the full paragraph text (including א./סעיף א) so the classifier sees the original indicators. The LLM performs all semantic interpretation.

Per Principle 4: the rendered content has clear, simple annotations (`[TABLE #N]`, `[SQ: X]`, `[EXAMPLE_SOLUTION]`, `QUESTION N` section separators). Code is plain text.

### 3.2 New LLM Classification Schema

Replace `ClassificationResponse` with a schema that outputs the **complete semantic structure**, not abstract pointers:

```python
class SubQuestionDraft(BaseModel):
    id: str                          # "א", "ב", etc.
    full_text: str                   # Complete sub-question text as the LLM sees it
    points: float

class QuestionDraft(BaseModel):
    question_number: int
    points: float
    context_text: str                # Question setup/stem — the "story", property definitions,
                                     # background context (NOT sub-question text)
    sub_questions: List[SubQuestionDraft]
    # All question content (including code) is in context_text/full_text; no code_blocks.
    example_solution: Optional[str]  # Only when explicitly labeled (e.g. "פתרון לדוגמה")
    has_sub_questions: bool
    confidence: float
    reasoning: str

class TableRowMapping(BaseModel):
    table_index: int                 # From [TABLE #N]
    table_type: str                  # RUBRIC_TABLE, TRACE_TABLE, etc.
    belongs_to_question: int
    # Maps table row indices to sub-question IDs.
    # Tells the transformer which rubric table row is which sub-question's criterion.
    # null when question has no sub-questions (criteria are direct question-level).
    row_to_sub_question: Optional[Dict[str, str]] = None

class RubricDraftResponse(BaseModel):
    questions: List[QuestionDraft]
    table_mappings: List[TableRowMapping]
```

**Key design decisions:**
- `full_text` instead of `text_snippet` — the LLM outputs complete sub-question text, eliminating the need to reconstruct it from element IDs (Principle 5)
- `context_text` on questions — explicitly separated from sub-question text, per Principle 3
- All content (including code) in `full_text`/context; `example_solution` only when explicitly labeled (Principle 4)
- `row_to_sub_question` — the LLM maps rubric table rows to sub-questions semantically, eliminating the point-matching distribution heuristic (Principle 2: LLM leads)

### 3.3 Updated Classification System Prompt

The system prompt must be updated to clearly instruct the LLM on:

1. **Output complete text, not snippets.** Every sub-question's `full_text` must contain the complete task text. Every question's `context_text` must contain the full problem setup.

2. **The context vs sub-question distinction (Principle 3).** Sub-questions are explicit tasks for the student (action verbs: "כתבו", "הגדירו", "חשבו", "הדפיסו"). Everything else in the question body — class definitions, property lists, parameter descriptions, background information — is `context_text`. Property lists like "arrEmployees – מערך חד-ממדי" are NEVER sub-questions.

3. **Table row mapping.** When a rubric table belongs to a question with sub-questions, map each data row (not the header row) to the sub-question it grades. Use semantic matching (the criterion description references the sub-question's task). If a row doesn't clearly map to any sub-question, leave it unmapped (it stays as a direct question-level criterion).

4. **Full text and solution.** Put all question content (including code) in full_text. Put content in `example_solution` only when the document explicitly labels it (e.g. "פתרון לדוגמה"); otherwise leave null.

### 3.4 Simplified Transformer

The transformer no longer needs to ground anything. Per Principle 1, its role in the abstract pipeline is: receive the rubric_draft, pass it through enhancement, build ontology types. Specifically:

1. **Receive** `RubricDraftResponse` from the LLM — already has all text content
2. **Parse rubric tables** deterministically using `_extract_criteria_from_table_basic()` — cell text → description + points (this is reliable and stays)
3. **Assign criteria to sub-questions** using `row_to_sub_question` mapping from the LLM — no heuristic needed
4. **Send criteria + question context to enhancement** — redesigned per Section IV
5. **Build ontology types** — unchanged

### 3.5 Fuzzy Verification (Belt-and-Suspenders)

After the LLM outputs `full_text` for each sub-question and `context_text` for each question, run a lightweight fuzzy check against the rendered document text to confirm the LLM didn't hallucinate content that doesn't exist in the document. This is **verification, not grounding** — a much simpler problem than the current linking machinery.

Implementation: check that the key content words from each `full_text` appear somewhere in the rendered document text. If a sub-question's text has very low word overlap with the rendered document, flag it for review but don't block the pipeline.

Per Principle 2: the LLM leads (provides the structure), deterministic code verifies (confirms the text exists in the source document).

### 3.6 What Gets Deleted

```
DELETED (no longer needed in the classification → transformer path):
├── _populate_question_elements()           # The entire grounding function
├── _extract_question_text()                # LLM provides context_text directly
├── _extract_sub_question_text()            # LLM provides full_text directly
├── _extract_code_blocks()                  # Removed; all content in full_text
├── _extract_example_solution()             # LLM extracts from [EXAMPLE_SOLUTION]
├── _distribute_criteria_to_sub_questions() # Replaced by row_to_sub_question mapping
├── SubQuestionStructure.text_snippet       # full_text replaces this
├── SubQuestionStructure.header_element_id  # No element IDs needed
├── SubQuestionStructure.text_elements      # No element IDs needed
├── QuestionStructure.header_element_id     # No element IDs needed
├── QuestionStructure.text_elements         # No element IDs needed
└── Composite-key sub-question lookup       # No annotation-based linking needed

KEPT (still valuable):
├── Parser (DOCX → tree)                   # Always needed for table cell parsing
├── Annotator                              # For renderer: EXAMPLE_SOLUTION, QUESTION_HEADER,
│                                          #   SUB_QUESTION (original א./סעיף א preserved in output)
├── Renderer                               # Enhanced with semantic markers
├── table_index_to_id mapping              # Deterministic, used for table cell parsing
├── _extract_criteria_from_table_basic()   # Deterministic table row parsing — reliable
├── Criterion enhancement LLM calls        # Redesigned (see Section IV)
├── Ontology type construction             # Unchanged
└── Validation                             # Unchanged
```

### 3.7 Migration Safety

The current pipeline works for questions WITHOUT sub-questions (Q1 in our test). The redesign must not break this case. When `has_sub_questions` is false, the LLM outputs `context_text` as the full question text, `sub_questions` is empty, and `row_to_sub_question` is null — criteria stay at question level. Verify this case explicitly.

---

## Section IV: Enhancement Layer Redesign

### The Current Problem

The current enhancement pipeline (`rubric_service.py::enhance_criterion_with_rules`) operates on each criterion independently. It receives a raw criterion dict with `criterion_description` and `total_points`, then asks an LLM to generate `reduction_rules` for it. This has three problems:

1. **No question context.** The enhancer doesn't know what the question is testing. It generates generic rules based on the criterion description alone, with no understanding of the question's pedagogical purpose.

2. **No holistic view.** Each criterion is enhanced in isolation. There's no step that evaluates whether the *set* of criteria actually covers the question's primary knowledge/skills, or whether the point distribution reflects relative importance.

3. **Wrong ontological order.** The current pipeline extracts criteria from the table → enhances each one independently → builds the ontology. But the correct chain of reasoning is: understand the question's purpose → evaluate criteria coverage → fix point distribution → THEN generate reduction rules. (Principle 6.)

### The Correct Ontological Chain (Principle 6)

For each question in the rubric, the enhancement must proceed in this exact order:

**Step 1 — Understand and Complete.** Read the question text (context_text + sub-question texts), the extracted criteria, and their point weights. Identify the primary knowledge/skills the question was designed to test. Then evaluate: are there missing criteria, especially ones that refer to the question's core purpose? If yes, create the missing criterion descriptions (text only, no rules yet).

**Step 2 — Evaluate and Rebalance.** Read ALL criteria (original + newly created) and evaluate each against the question's purpose. Reassign point distribution based on relative importance. The governing principle: **the most important criteria are those that measure the aspects of the student's answer that directly address the question's purpose.** A criterion testing a core skill (e.g., correct algorithm logic) should carry more weight than one testing style (e.g., variable naming).

**Step 3 — Generate Reduction Rules.** For each criterion (now with finalized points), ask: "Does this criterion have multiple binary aspects that the answer needs to get right?" If yes, break it into reduction rules and assign point distribution (rule points must sum to criterion points). If no (the criterion is atomic), create a single binary rule.

### Where "Question Purpose" Comes From

The question's purpose — the primary knowledge/skills it was designed to test — is derived from a combination of signals, in order of specificity:

1. **The test's title** — reflects the sub-subject matter being tested (e.g., "בוחן לולאות For" tells you this test is about For loops). This sets the broad domain.
2. **The question text itself** — context_text + sub-question texts reveal what specific skills are being exercised within that domain.

Together, these two signals give the enhancement LLM enough context to reason about question purpose for the current implementation.

**Future addition (not in scope for this plan, but design for it):** We will add a frontend flow layer that presents each extracted question to the teacher with the prompt: "What are the most important skills/knowledge you want to test with this question?" and an input field. The teacher's direct response will be injected into the enhancement layer's context as a third signal. At that point, the enhancement agent will have the complete hierarchical picture for determining relative importance of criteria:

```
Test title       → broad subject domain (e.g., "For loops")
Question text    → specific skills exercised (e.g., "nested loop with array traversal")
Teacher's input  → explicit pedagogical intent (e.g., "I care most about correct loop bounds")
```

For now, design the enhancement prompts so that `question_purpose` is a field that the LLM infers from signals 1 and 2. Later, when we add signal 3, we'll inject the teacher's input as an override/refinement of the inferred purpose — the prompt structure should make this easy to add without restructuring.

### Implementation Shape

This is a **two-LLM-call architecture per question** (not per criterion):

**Call 1 — Question-Level Analysis (Steps 1 + 2):**

Input:
- Test title (the broad subject context)
- Question context_text
- Sub-question texts (all)
- Extracted criteria with original points from the rubric table
- Example solution (if available)
- Programming language

Output:
- `question_purpose`: What knowledge/skills this question tests
- `criteria`: Complete list (original + added), each with:
  - `description`: Criterion text
  - `points`: Rebalanced point value
  - `importance_reasoning`: Why this weight
  - `is_new`: Whether this criterion was added by the LLM
  - `belongs_to_sub_question`: Optional sub-question ID

Validation: Σ criteria points must equal question total_points.

**Call 2 — Criterion-Level Rules (Step 3):**

This can be parallelized across criteria within a question. For each criterion:

Input:
- Criterion description and finalized points
- Question purpose (from Call 1)
- Sub-question text (if criterion belongs to a sub-question)

Output:
- `reduction_rules`: List of binary-aspect rules with points

Validation: Σ rule points must equal criterion points. (This validation already exists in `EnhancedCriterion`.)

### What Changes from Current Enhancement

The current flow sends each raw criterion to `enhance_criterion_with_rules` independently. The new flow:

1. **Groups criteria by question** (not individual processing)
2. **Adds a question-level analysis call** before criterion-level enhancement
3. **Passes question purpose** as context to each criterion enhancement call
4. **Can add/remove/rebalance criteria** before generating rules
5. **Criterion enhancement calls receive richer context** (question purpose + sub-question text)

### Backward Compatibility

The rubric-generator page also calls enhancement functions. The new enhancement should work for both the DOCX pipeline and the rubric generator. The entry point receives a list of criteria + question context, and returns enhanced criteria with rules. If no question context is available (rubric generator path), skip Steps 1-2 and go directly to Step 3 (current behavior as fallback).

---

## Section V: Implementation Task Outline

### Phase 1: Enhanced Renderer (Small, Low Risk)

Emit `[EXAMPLE_SOLUTION]...[/EXAMPLE_SOLUTION]` for explicitly labeled solutions. Code and body text are plain (no [CODE_BLOCK]). Sub-question lines: emit `[SQ: X]` then the full paragraph so א./סעיף א remain visible. Verify the rendered output for the test DOCX looks correct.

### Phase 2: New Classification Schema + Prompt (Core Change)

Replace `ClassificationResponse` with `RubricDraftResponse`. Update the classification system prompt to instruct complete text extraction, context vs sub-question distinction (Principle 3), and table row mapping. Update `_classify_with_llm` to use the new schema. Wire the LLM response into the new data flow.

### Phase 3: Simplified Transformer (Major Deletion)

Rewrite the transformer's main loop to consume `RubricDraftResponse` directly. Delete the grounding functions, text extraction functions, and distribution logic. Keep `_extract_criteria_from_table_basic()` for deterministic table parsing. Use `row_to_sub_question` for criteria assignment. Add fuzzy verification of LLM-output text against rendered document.

### Phase 4: Enhancement Layer Redesign
Implement the two-call architecture per Principle 6: question-level analysis (Steps 1+2) → criterion-level rules and scoring levels (Steps 3+4). Create the new prompt for question purpose analysis, criteria completeness, and point rebalancing. Create the criterion-level prompt that generates rules with appropriate scoring types and specific condition_hints. Wire into the transformer's enhancement flow.

### Phase 5: End-to-End Verification
Re-upload the same test DOCX. Verify:

Q2 sub-questions have correct text (not property definitions)
Q2 criteria are distributed to correct sub-questions (via LLM row mapping)
Q2 criteria are enhanced with specific, purpose-driven reduction rules
Q1 (no sub-questions) still works correctly
Q3 still works correctly
Total points sum correctly across all levels
No criteria duplication
Enhancement reflects the question's pedagogical purpose
Point rebalancing produces sensible weights

### What NOT to Build

❌ Don't preserve _populate_question_elements as a fallback — clean break from architectural debt
❌ Don't keep element IDs on QuestionStructure/SubQuestionStructure — they are the source of complexity
❌ Don't keep the point-matching distribution heuristic as primary path — the LLM's row mapping replaces it (keep only as emergency fallback)
❌ Don't keep per-criterion independent enhancement without question context — the ontological chain (Principle 6) is strictly better
❌ Don't add sub-question annotations to the rendered text — the LLM performs all semantic interpretation of what is and isn't a sub-question

### Risk Mitigation

- The current pipeline works for the rubric-generator page (non-DOCX path). Don't break that path. The enhancement redesign should be backward-compatible: if no question context is provided, fall back to current per-criterion enhancement.
- The LLM may occasionally produce imperfect `row_to_sub_question` mappings. The fuzzy verification layer catches this. If mapping fails validation, fall back to sequential assignment by points (the distribution heuristic, kept as emergency fallback only).
- Test with at least 3 different DOCX rubrics before declaring the redesign complete.

---

## Quick Reference: The 6 Principles

| # | Principle | One-Liner |
|---|-----------|-----------|
| 1 | Abstract Pipeline Sequence | Parse → LLM builds draft → Enhancement → Display → Teacher review |
| 2 | LLM Leads, Code Verifies | Never let pattern-matching override what the LLM understood correctly |
| 3 | Sub-Questions Are Tasks | Sub-questions = student tasks; question body = context/setup/definitions |
| 4 | Clean Annotations Enable Great Classification | Simple, non-noisy markers + clear prompt instructions = excellent LLM output |
| 5 | Element IDs Are Architectural Debt | The grounding round-trip reconstructs information the LLM already had |
| 6 | Ontological Enhancement Chain | Understand & Complete → Evaluate & Rebalance → Generate Rules → Define Scoring Levels |