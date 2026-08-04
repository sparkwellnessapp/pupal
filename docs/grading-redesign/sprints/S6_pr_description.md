# PR: S6 — `GradableTest` schema + compiler

**Sprint:** S6
**Depends on:** S1 (ORM), S4 (`TranscriptionContract`) — merged. (S5 unrelated to this sprint.)
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §2.1.B (GradableTest), §5.3 (closed-world CW-1), §8 (why GradableTest isn't persisted); the GraderAgent sprint plan (two-pass identity resolution, sub-question matching)
**Frontend lockstep:** none — `GradableTest` is an internal in-memory artifact, nothing user-facing. First backend-only sprint since S1.

---

## 1. Summary

S6 builds the **marriage object**: a pure function that takes a `GradingRubricContract` + a `TranscriptionContract` and produces the closed-world, per-question-sliced `GradableTest` that the GraderAgent (S7) will consume. No LLM, no DB writes, no endpoint, no frontend — just a schema and a deterministic compiler, exhaustively unit-tested.

S6 fixes two real defects the original pipeline had:
1. **Sub-questions silently collapsing into parents** — the old code never resolved sub-question identity; S6 matches `sub_question_id` directly so each sub-question's answer reaches its own criteria.
2. **Closed-world as a soft post-hoc warning** — S6 makes it structural: the agent receives only the criteria the compiler sliced in, so it *cannot* reference an out-of-contract criterion ID (CW-1 by construction).

S6 also includes a **small upstream fix to the rubric `ContractCompiler`** (§4) so that question-level grading context survives compilation — required for the agent to grade well, and the cleanest place to fix it.

---

## 2. What `GradableTest` is (and isn't)

Per Phase 0a §2.1.B and §8:
- **In-memory only.** No table, no ORM model, no persistence. It is a pure function of two pinned contract versions, recomputed on demand. Do NOT add a `gradable_tests` table or persist it anywhere.
- **Closed-world by construction (CW-1).** Each `GradableQuestion` carries only its own criteria. The agent literally cannot see criteria from other questions or invent IDs — the structure makes it impossible, not a runtime check.
- **Deterministic.** Same two pinned contract versions → byte-identical `GradableTest`. This is why it isn't persisted (recompute, don't cache) and why the compiler reads **only frozen contracts**, never mutable drafts (§4 explains why the ContractCompiler fix matters for this).

The compiler is the single legitimate path from `(RubricContract, TranscriptionContract)` to `GradableTest`. S7's agent accepts only a `GradableTest`.

---

## 3. Scope

### In scope
- `GradableTest` / `GradableQuestion` / supporting Pydantic schemas (in-memory types) — §5.
- `GradableTestCompiler.compile(...)` — the pure function — §6.
- Two-pass question identity resolution + direct sub-question matching — §6.2.
- Per-scope alignment status + orphan collection — §6.3.
- The upstream `ContractCompiler` fix (stop stripping question-level context) — §4.
- Exhaustive unit tests (the compiler is pure → fully testable without mocks) — §7.

### Out of scope
- **The agent.** S7. S6 produces its input, doesn't grade.
- **Persistence / endpoints.** `GradableTest` is never written; no `/grade` wiring (S8 calls the compiler).
- **Point-sum re-validation.** Per decision D1(a): the compiler validates *structure only*. The rubric's point-sum invariants (INV-R1/R2/R3) were already validated by the ContractCompiler at rubric-compile time and the contract is frozen. The gradable compiler trusts its input contracts. Its job is marriage + slicing + closed-world, not rubric re-validation.
- **Frontend.** Nothing user-facing.

---

## 4. Upstream fix — stop stripping question-level grading context

**The problem:** the rubric `ContractCompiler` (`contract_compiler.py` ~lines 116–130) currently strips `example_solution`, `trace_tables`, and `context_tables` from `Question` during compilation — they are always `None` in `rubrics.contract_json`. But these are grading inputs the agent needs:
- `example_solution` — "here's what a correct answer looks like," one of the most useful things to give an LLM grader.
- `trace_tables` / `context_tables` — for questions that reference a data table or trace, the student's answer is *uninterpretable* without them.

Note the existing asymmetry: `SubQuestion.example_solution` is NOT stripped (it survives compilation), but `Question.example_solution` is. A sub-question-bearing question keeps its model answers; a direct-criteria question loses its example solution. That asymmetry is a latent bug.

**The fix:** in `ContractCompiler`, remove `example_solution`, `trace_tables`, and `context_tables` from the `Question` strip list. Keep stripping `proposals` (genuinely editor-only) and the `SubQuestion`-level `proposals`/`title`. After the fix, `Question` retains these three fields through compilation, symmetric with how `SubQuestion.example_solution` already survives.

```python
# BEFORE (strips grading context):
clean_questions = [
    q.model_copy(update={
        "proposals": None,
        "example_solution": None,    # ← REMOVE this line
        "trace_tables": None,        # ← REMOVE this line
        "context_tables": None,      # ← REMOVE this line
        "sub_questions": [sq.model_copy(update={"proposals": None, "title": None}) ...],
    })
    for q in response.questions
]

# AFTER (keeps grading context, strips only editor-only fields):
clean_questions = [
    q.model_copy(update={
        "proposals": None,
        "sub_questions": [sq.model_copy(update={"proposals": None, "title": None}) ...],
    })
    for q in response.questions
]
```

**Why this and not "read the draft in the gradable compiler":** the alternative — having the gradable compiler source these fields from `rubrics.draft_json` — would break the reproducibility guarantee (Phase 0a §8). The draft is mutable and can drift after the contract is pinned; reading it at grade time means the same pinned `contract_version` could produce different gradable tests. Fixing it upstream keeps the gradable compiler reading **only frozen contracts**, preserving determinism. This is the architecturally correct location.

**Tests for the fix:** add a ContractCompiler test asserting a compiled `Question` retains `example_solution`/`trace_tables`/`context_tables` when the draft had them (currently they'd be `None`).

---

## 5. The `GradableTest` schemas

New file `app/schemas/gradable.py`. In-memory Pydantic types — they serialize for the agent's consumption but are never stored. **Decimal discipline throughout** (never `float`) — carry all point values as `Decimal`, matching the contract.

```
GradableCriterion:
  criterion_id: str
  description: str
  points: Decimal
  evaluation_guidance: Optional[str]        # survives compilation — grader-facing
  notes: Optional[str]                       # survives compilation
  sub_criteria: Optional[List[GradableSubCriterion]]   # flat leaf list (not recursive)

GradableSubCriterion:
  sub_criterion_id: str
  description: str
  points: Decimal

GradableScope:                               # one per gradable unit (see §6.1)
  scope_kind: Literal["direct", "sub_question"]
  # identity
  question_id: str                           # the contract Question.question_id
  sub_question_id: Optional[str]             # set when scope_kind == "sub_question"
  # the criteria the agent grades against (closed-world: ONLY these)
  criteria: List[GradableCriterion]
  points: Decimal                            # question.total_points or sub_question.points
  # grading context
  example_solution: Optional[str]            # now survives (§4) — question or sub-question level
  trace_tables: Optional[List[Dict[str, Any]]]    # question-level only; None for sub-question scopes
  context_tables: Optional[List[Dict[str, Any]]]  # question-level only
  question_text: Optional[str]
  sub_question_text: Optional[str]
  # the student's answer for this scope
  student_answer_text: Optional[str]         # None when answer_missing
  alignment: Literal["matched", "answer_missing", "scope_not_in_contract"]

GradableTest:
  schema_version: str = "1.0"
  rubric_contract_version: str               # pinned, for reproducibility/audit
  transcription_contract_version: str        # pinned
  scopes: List[GradableScope]                # the per-unit slices the agent iterates
  unmatched_transcription_answers: List[UnmatchedAnswer]   # orphans (§6.3)
  total_points: Decimal                      # Σ scope.points — sanity anchor

UnmatchedAnswer:
  question_number: int
  sub_question_id: Optional[str]
  answer_text: str
  reason: str                                # human-readable, e.g. "no contract question at position N"
```

### Note on the scope model

Rather than a nested `GradableQuestion → GradableSubQuestion` tree, S6 flattens to a **list of `GradableScope`** — one per gradable unit. A unit is either:
- a **direct-criteria question** (`scope_kind="direct"`) — the question's own criteria, or
- a **sub-question** (`scope_kind="sub_question"`) — that sub-question's criteria.

This is justified by **structure exclusivity** (research §2): a contract question has *either* direct criteria *or* sub-questions, never both. So the gradable units don't overlap, and a flat list of scopes is the natural shape — it's exactly what the agent iterates ("one LLM call per scope"). It also makes closed-world trivially visible: each scope's `criteria` list IS the closed world for that LLM call.

This flat-scope model is a deliberate design choice. If you'd prefer a nested question→sub-question tree to mirror the contract structure more literally, flag it — but the flat list maps better to the agent's per-scope iteration and to the "one call per question/sub-question" model the GraderAgent sprint describes.

---

## 6. The compiler

`app/services/gradable_compiler.py`, function `compile(rubric_contract: GradingRubricContract, transcription_contract: TranscriptionContract) -> GradableTest`. Pure: no DB, no LLM, no I/O. Deterministic.

### 6.1 Slicing into scopes

For each `Question` in the rubric contract, emit scopes per structure exclusivity:
- If the question has **direct criteria** (`question.criteria` non-empty, `sub_questions` empty): emit one `GradableScope` with `scope_kind="direct"`, carrying `question.criteria`, `question.total_points`, `question.example_solution`, `question.trace_tables`, `question.context_tables`, `question.question_text`.
- If the question has **sub-questions** (`sub_questions` non-empty, `criteria` empty): emit one `GradableScope` per sub-question with `scope_kind="sub_question"`, carrying `sub_question.criteria`, `sub_question.points`, `sub_question.example_solution`, `sub_question.text` as `sub_question_text`. (Question-level `trace_tables`/`context_tables` also attach to each sub-question scope of that question — they're question-wide context the sub-question answer may reference. Carry them through.)

Map each `Criterion` → `GradableCriterion` (including its flat `sub_criteria` → `GradableSubCriterion`). This is the closed-world set per scope.

### 6.2 Identity resolution — two-pass, both happy paths

The join key mismatch: `TranscriptionContractAnswer.question_number` is a 1-based `int`; `Question.question_id` is a `str` in one of two formats (`q{N}` from extraction, `q_{uid}` from the frontend `addQuestion`). Resolve in two passes, **neither emitting a warning** (both are normal):

- **Pass 1 (regex):** for each contract question whose `question_id` matches `^q\d+$`, parse the integer suffix and match it to the transcription answer whose `question_number` equals it.
- **Pass 2 (positional fallback):** for each contract question whose `question_id` does NOT match `^q\d+$` (e.g. `q_{uid}`), match by 0-based array index — `questions[answer.question_number - 1]`. This is the common case for teacher-edited rubrics, not an error.

Build the question_number → question mapping once, then attach each answer to its scope(s).

**Sub-question matching — direct string equality.** Within a matched sub-question-bearing question, match `answer.sub_question_id == sub_question.sub_question_id` directly. Both sides are raw strings (Hebrew letter, Latin letter, or number — *not* assumed to be any particular format). This is the fix for the sub-question-collapse defect: each sub-question scope gets *its own* answer, not the parent question's concatenated text.

A direct-criteria question's scope gets the answer whose `question_number` matched and whose `sub_question_id` is `None` (or, if the transcription has a sub_question_id for a question the contract treats as direct, that's a `scope_not_in_contract` orphan — see §6.3).

### 6.3 Alignment status + orphans

For each emitted scope, set `alignment`:
- **`matched`** — a transcription answer was found for this scope; `student_answer_text` set.
- **`answer_missing`** — the scope exists in the contract but no transcription answer matched it; `student_answer_text = None`. (Student didn't answer this question/sub-question.)

For each transcription answer that matched **no** scope:
- Collect into `unmatched_transcription_answers` as an `UnmatchedAnswer` with a human-readable `reason` (e.g. "no contract question at position 4", "sub_question 'ג' not in contract question q2"). This is **data for the teacher, not an error** — the compiler never raises on orphans. The scope's own alignment would be `scope_not_in_contract` only if we modeled it as a scope; since orphans by definition have no contract scope, they live in `unmatched_transcription_answers`, not in `scopes`. (The `scope_not_in_contract` alignment value exists for completeness but in practice orphans surface via the unmatched list — keep the enum value for the agent/UI to reason about, document that the primary orphan channel is the unmatched list.)

### 6.4 What the compiler does NOT do

- Does not validate point sums (D1(a) — trusts the frozen contract).
- Does not call the LLM or score anything.
- Does not read the draft (only the two frozen contracts — preserves reproducibility).
- Does not raise on missing answers or orphans (they're data, not errors). It raises only on genuinely malformed input (e.g. a contract that fails Pydantic validation — but that's caught at `model_validate`, before the compiler).

---

## 7. Testing

The compiler is pure → **exhaustively unit-testable with zero mocks**. This is where S6 earns its keep. Tests in `tests/services/test_gradable_compiler.py`.

### Identity resolution
1. **Pass 1 (q{N}):** contract with `question_id` `"q1"`, `"q2"`; transcription answers `question_number` 1, 2 → correct match.
2. **Pass 2 (q_{uid}):** contract with `question_id` `"q_abc"`, `"q_def"`; answers matched by position.
3. **Mixed formats:** contract with `["q1", "q_abc", "q3"]` (teacher edited) → q1 and q3 match by regex, q_abc by position. All resolve, no warning.
4. **Sub-question direct match:** sub-question-bearing question with sub-questions `"א"`, `"ב"`; answers with `sub_question_id` `"א"`, `"ב"` → each sub-question scope gets its OWN answer (the defect-fix test — assert "א"'s answer text is not concatenated with "ב"ّs).
5. **Non-Hebrew sub_question_id:** sub-questions `"a"`, `"b"` or `"1"`, `"2"` match by direct string equality.

### Alignment + orphans
6. **answer_missing:** a contract scope with no matching transcription answer → `alignment="answer_missing"`, `student_answer_text=None`.
7. **Orphan answer:** a transcription answer for `question_number` 5 when the contract has 3 questions → lands in `unmatched_transcription_answers` with a clear reason; compiler does not raise.
8. **Orphan sub-question:** answer with `sub_question_id="ג"` for a question whose contract sub-questions are only `"א"`,`"ב"` → unmatched.

### Slicing + closed-world
9. **Direct-criteria question:** scope carries exactly that question's criteria, no others (closed-world — assert the scope's criterion_ids are a subset of that question's, and disjoint from other questions').
10. **Sub-question scopes:** one scope per sub-question, each carrying only its own criteria.
11. **`sub_criteria` carried:** a criterion with flat `sub_criteria` → `GradableCriterion.sub_criteria` populated correctly.
12. **Grading context carried:** `example_solution` (question-level, post-§4-fix), `trace_tables`, `context_tables`, `evaluation_guidance`, `notes` all reach the scope.

### Discipline
13. **Decimal preserved:** all point values in the `GradableTest` are `Decimal`, never `float`.
14. **Determinism:** compiling the same two contracts twice produces equal `GradableTest`s.
15. **Pinned versions:** `GradableTest.rubric_contract_version` and `transcription_contract_version` match the inputs.

### ContractCompiler fix (§4)
16. A compiled `Question` retains `example_solution`/`trace_tables`/`context_tables` from the draft (previously stripped to `None`).

Tests 4 (sub-question separation) and 9 (closed-world slicing) are the ones that protect the two defects S6 exists to fix.

---

## 8. Acceptance criteria

- [ ] `GradableTest` schemas exist as in-memory Pydantic types; no table, no ORM, no persistence.
- [ ] Flat `GradableScope` model; one scope per direct-criteria question or per sub-question (justified by structure exclusivity).
- [ ] `compile()` is pure — no DB, no LLM, no I/O; deterministic.
- [ ] Two-pass identity resolution; both passes are happy paths (no warnings).
- [ ] Sub-question direct string matching; each sub-question scope gets its own answer (defect fixed).
- [ ] Closed-world by construction: each scope carries only its own criteria.
- [ ] Alignment status set per scope; orphans collected in `unmatched_transcription_answers`; compiler never raises on missing/orphan.
- [ ] Reads only frozen contracts, never the draft.
- [ ] No point-sum re-validation (D1(a)).
- [ ] Decimal discipline unbroken.
- [ ] ContractCompiler no longer strips `example_solution`/`trace_tables`/`context_tables` from `Question`; `proposals`/`title` still stripped.
- [ ] All tests pass; tests 4 and 9 explicitly verified; `import app.main` succeeds; `pytest --collect-only` succeeds.

---

## 9. Known follow-ups (do NOT do in this PR)

- **S7** — the GraderAgent: consumes `GradableTest`, one LLM call per scope, deterministic post-validation (quote/bounds/closed-world re-check), produces `GradedTestDraft`.
- **S8** — wires the compiler into `/grade`: loads both contracts, calls `compile()`, runs the agent, advances the `graded_tests` row `pending → grading → draft`. The compiler S6 builds is called there.
- **The `unmatched_transcription_answers` surfacing** — S8/the draft will decide how orphans are shown to the teacher. S6 just collects them.

If the flat-scope model (§5) proves awkward for the agent's iteration in S7, the alternative is a nested question→sub-question tree — but the flat list is the intended shape and maps to "one call per scope." Flag if S7 reveals a reason to nest. And if anything in the contract shapes contradicts this spec, stop and flag rather than reconciling silently.
