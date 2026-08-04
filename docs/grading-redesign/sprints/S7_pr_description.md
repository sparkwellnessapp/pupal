# PR: S7 — The GraderAgent

**Sprint:** S7
**Depends on:** S6 (`GradableTest` schema + compiler), S1 (ORM), S4 (transcription) — merged
**Foundation refs:** `docs/architecture/phase_0a_architecture.md` §2.1.C (GradedTest Draft/Contract), §3.2 (graded_test lifecycle), §10 (annotations); `GraderAgent_sprint_plan.md` Phase E (the agent design — adapted, see §2)
**Frontend lockstep:** none — S7 produces an in-memory `GradedTestDraft`. No endpoint, no persistence, no UI. S8 wires it in.

---

## 1. Summary

S7 builds the GraderAgent: a unit that consumes a `GradableTest` (S6's output) and produces a complete `GradedTestDraft` **in memory** — the AI grading outcomes, an empty `teacher_overrides` overlay, and annotations. It is the grading engine, isolated from persistence and endpoints.

The agent is **stupid-simple by design** (per the sprint plan's operating principle): one LLM call per scope, structured output, deterministic post-validation, no ReAct, no retries, no multi-step reasoning. The intelligence is in the *structure* — closed-world inputs, deterministic validation, terminal-criterion grading — not in agentic cleverness.

S7 grades scopes **in bounded parallel** (D2) with per-scope observability and exception isolation: a single scope's LLM failure degrades to a flagged zero-outcome for that scope, never a failure of the whole grade.

**S7 does NOT:** persist anything, touch the `graded_tests` row, wire `/grade`, compute row-level totals/percentage (S8 does all of that), or build any UI. Its single output is an in-memory `GradedTestDraft`.

---

## 2. Reconciling the sprint plan with what we actually built

`GraderAgent_sprint_plan.md` is the authoritative source for the *agent's design philosophy* (one call per scope, terminal-criterion grading, the three post-validations, no ReAct). But it predates our S1–S6 redesign and several of its **structural** assumptions are now wrong. S7 follows the plan's design and **ignores these stale structural assumptions**:

| Sprint plan says | Reality (what we built) | S7 follows |
|---|---|---|
| `sub_criteria` is recursive `List[ContractCriterion]` | Flat: `Criterion.sub_criteria: List[SubCriterion]`, leaf type (S6) | **Flat.** The "criterion tree" is at most two levels: a criterion, optionally with a flat list of sub-criteria. |
| `GradableTest` persisted (`gradable_test_json` column) | In-memory only, never persisted (Phase 0a §8) | **In-memory.** S7 receives it as an object; never reads/writes a column. |
| Nested `GradableQuestion → GradableSubQuestion` | Flat `List[GradableScope]` (S6) | **Flat scopes.** The agent iterates `gradable_test.scopes`. |
| `extra_notes` field | Implemented as `evaluation_guidance` + `notes` on the criterion | **`evaluation_guidance` + `notes`.** No `extra_notes`. |
| Output is `GradedTestPreview` | Standardized on `GradedTestDraft` (Phase 0a Draft/Contract) | **`GradedTestDraft`.** |
| Agent + persistence + endpoints in one sprint (Phase E+F) | Split: S7 = agent, S8 = persistence + wiring | **Agent only.** No Phase F work. |

The plan's `CriterionOutcome` is also still in its old rules-based shape (`rule_outcomes: List[RuleOutcome]`, research §1) and `EvidenceClaim.matched_level_id` references the deleted `ScoringLevel`. **S7 does not repair these dead types** — it introduces fresh outcome types in a new file (§4) and leaves the legacy types alone (a future sprint removes them when `graded_json` is dropped).

---

## 3. Scope

### In scope
- New outcome schemas: `GradedTestDraft`, `ScopeOutcome`, `CriterionOutcome` (new, flat-recursive), reusing `AnswerQuotation`/`FlaggedOutcome`/`FlagReason`/`QuoteValidationStatus` from `ontology_types.py` (§4).
- LLM I/O schemas: the per-scope request bundle + structured-output response (§5).
- The Hebrew-aware prompt (§6).
- The deterministic validator — pure function: closed-world, bounds+precision, quote validation (§7).
- The agent: `async def grade(gradable_test) -> GradedTestDraft`, bounded-parallel, observable, exception-isolating (§8).
- Two new `FlagReason` values: `UNGRADED_CRITERION`, `BOUNDS_CLAMPED` (research §7).
- Tests: validator unit tests (pure, no LLM) + agent integration test (mocked LLM) (§9).

### Out of scope
- **Persistence.** No DB, no `graded_tests` row, no `gradable_test_json`/`preview_json` columns. S8.
- **Endpoints / `/grade` wiring.** S8.
- **Row-level totals/percentage.** S8 computes `total_score`/`total_possible`/`percentage` on the row from the draft. S7 produces per-scope and per-criterion points but does not write row aggregates.
- **Repairing legacy outcome types** (`RuleOutcome`, old `CriterionOutcome`, `EvidenceClaim`). Left alone.
- **Frontend.** Nothing user-facing.
- **The `teacher_overrides` editing logic.** S7 emits an *empty* overrides overlay; the editing/approval flow is S9/S10.

---

## 4. Outcome schemas

New file `app/schemas/graded_test_draft.py`. **Decimal throughout.** These are the in-memory artifact S8 will persist into `graded_tests.draft_json`.

```
CriterionOutcome:                          # NEW — flat-recursive, not the legacy rules-based one
  criterion_id: str
  description: str                         # denormalized for display
  points_possible: Decimal
  points_awarded: Decimal                  # bounded [0, points_possible]
  reasoning: str                           # Hebrew
  confidence: float                        # 0.0–1.0, LLM self-assessed (§5.1); review-queue ordering signal
  evidence_quote: Optional[AnswerQuotation]    # reused from ontology_types; carries validation_status
  sub_criterion_outcomes: Optional[List[SubCriterionOutcome]]
                                           # present iff the contract criterion had sub_criteria
                                           # when present, this criterion's own `confidence` is the min of its children's
  flags: List[FlaggedOutcome]

SubCriterionOutcome:                       # leaf — mirrors the flat GradableSubCriterion
  sub_criterion_id: str
  description: str
  points_possible: Decimal
  points_awarded: Decimal
  reasoning: str
  confidence: float                        # 0.0–1.0, LLM self-assessed per leaf
  evidence_quote: Optional[AnswerQuotation]
  flags: List[FlaggedOutcome]

ScopeOutcome:                              # one per GradableScope (1:1 with input)
  scope_kind: Literal["direct", "sub_question"]
  question_id: str
  sub_question_id: Optional[str]
  points_possible: Decimal                 # = scope.points
  points_awarded: Decimal                  # = Σ criterion_outcomes.points_awarded
  min_confidence: float                    # min terminal confidence in this scope; cheap review-triage key
  criterion_outcomes: List[CriterionOutcome]
  flags: List[FlaggedOutcome]              # scope-level flags (e.g. NO_ANSWER, LLM call failed)
  graded_by: Literal["llm", "skipped_no_answer", "failed"]   # observability — how this scope got its outcome
  retry_count: int = 0                     # observability — 0 (first-try) or 1 (succeeded/failed after one transient retry)

GradedTestDraft:
  schema_version: str = "1.0"
  rubric_contract_version: str             # echoed from the GradableTest (audit/reproducibility)
  transcription_contract_version: str
  model_version: str                       # settings.openai_model used
  prompt_version: str                      # the grading prompt template version (§6.1) — for reproducibility/eval attribution
  scope_outcomes: List[ScopeOutcome]
  teacher_overrides: Dict[str, Any] = {}   # EMPTY at draft time (Phase 0a overlay) — S9 populates
  annotations: List[GradingAnnotation]     # diagnostic surface (§4.1)
  unmatched_transcription_answers: List[UnmatchedAnswer]  # echoed from the GradableTest for teacher visibility
  llm_calls_count: int                     # observability
  grading_duration_ms: int                 # observability
```

**Note on the flat-recursive shape:** `CriterionOutcome` can hold `sub_criterion_outcomes` (one level), mirroring the flat `GradableCriterion.sub_criteria`. A `SubCriterionOutcome` is a leaf — no further nesting. This matches S6's flat structure exactly; do not build arbitrary-depth recursion.

**`points_awarded` aggregation:**
- Leaf criterion (no sub_criteria): `points_awarded` is the LLM's value (post-validated).
- Branch criterion (has sub_criteria): `points_awarded = Σ sub_criterion_outcomes.points_awarded`. The branch criterion is NOT graded directly — its children are. (Sprint plan §"terminal-criterion grading model".)
- Scope: `points_awarded = Σ criterion_outcomes.points_awarded`.

### 4.1 Annotations (Phase 0a §10)

The draft carries a `GradingAnnotation` list — the diagnostic surface S9's approval gate reads. Reuse or define a `GradingAnnotation` consistent with the transcription annotation shape from S4 (`id`, `severity`, `target_id`, `annotation_type`, `message`, `metadata`). S7 produces annotations from validation results (§7.4). `error`-severity annotations will block approval in S9; S7 just produces them.

### 4.2 New `FlagReason` values

Add to `FlagReason` in `ontology_types.py` (research §7):
- `UNGRADED_CRITERION = "ungraded_criterion"` — a closed-world criterion the LLM didn't return a grade for.
- `BOUNDS_CLAMPED = "bounds_clamped"` — `points_awarded` was clamped to `[0, max]` in post-validation.

---

## 5. LLM I/O schemas

New file `app/agents/grader/schemas.py`. These are the structured-output contract with the LLM — passed to `with_structured_output` (§8).

```
# Input bundle (assembled by the prompt builder, not sent raw to the LLM —
# the prompt renders it; this type just organizes the data)
QuestionGradingRequest:
  scope: GradableScope            # the one scope being graded

# LLM structured output — what with_structured_output(QuestionGradingResponse) enforces
TerminalGrade:
  terminal_criterion_id: str      # the criterion_id OR sub_criterion_id being graded (a leaf)
  points_awarded: Decimal         # constrained; see §7.2
  reasoning: str                  # Hebrew
  quote_text: str                 # verbatim from the student answer; "" if no evidence
  confidence: float               # 0.0–1.0, the model's self-assessed certainty in THIS grade (§5.1)

QuestionGradingResponse:
  grades: List[TerminalGrade]     # one per terminal (leaf) criterion in the scope
```

**Terminal criteria for a scope:** walk the scope's `criteria`. For each criterion: if it has `sub_criteria`, each sub-criterion is a terminal (leaf); otherwise the criterion itself is the terminal. The LLM grades terminals. The set of terminal IDs is the **closed world** for this scope's LLM call.

**Decimal in structured output:** LangChain's `with_structured_output` over a Pydantic model with `Decimal` fields — confirm the JSON schema emits a numeric type the model accepts. If `Decimal` causes schema friction, accept the LLM value as `float`/`str` in `TerminalGrade` and convert to `Decimal` immediately on receipt (before any arithmetic). **Never do arithmetic in float** — convert at the boundary. (Flag if `with_structured_output` + `Decimal` doesn't round-trip cleanly; the fallback is str-in-schema → `Decimal()` on parse.) `confidence` stays `float` — it's a soft triage signal, not a graded quantity, so float is correct and no Decimal discipline applies to it.

### 5.1 Confidence — what it is and how it's used

Each `TerminalGrade` carries a self-assessed `confidence ∈ [0,1]`: the model's certainty in *that specific grade* (not a probability, not calibrated out of the box). The prompt instructs the model to lower it when the answer is ambiguous, the evidence is weak, the handwriting transcription looked garbled, or the criterion is hard to judge from what the student wrote.

It flows: `TerminalGrade.confidence` → the leaf outcome's `confidence` → the parent `CriterionOutcome.confidence` (= min of its sub-criteria when it's a branch) → `ScopeOutcome.min_confidence` (= min across the scope's terminals). Purpose: **order the teacher's review queue** — lowest-confidence scopes surface first. The whole architecture is human-in-the-loop; confidence is how the agent triages *where the human should look first*.

**Honest caveat (carry into the eval sprint):** raw LLM self-confidence is weakly calibrated and must not be treated as ground truth. In S7 it's used only for *ordering* (a monotonic triage hint), never to auto-accept or auto-reject a grade. Its calibration against real teacher grades, and the confidence-triggered second-pass verification, are specced in the future eval sprint (see `GraderAgent_sprint_plan.md`). S7 produces and plumbs the signal; it does not yet trust it for anything beyond sort order.

---

## 6. The prompt

New file `app/agents/grader/prompt.py`. One template, built from a `QuestionGradingRequest`.

**Style (research §4):** English system prompt with Hebrew expected in output *values* (reasoning, quotes) — matching the house `RULE_GRADING_SYSTEM_PROMPT` style, including the box-drawing (`═══`) section-header convention. Not an all-Hebrew system prompt.

**The system prompt** establishes: you are grading a high-school CS test; grade each terminal criterion independently; award `points_awarded ∈ [0, points_possible]` per terminal; provide a verbatim quote from the student's answer as evidence (Hebrew); reasoning in Hebrew; if no evidence exists for a criterion, award 0 and say so; **report a `confidence ∈ [0,1]` per terminal — lower it when the answer is ambiguous, the evidence is weak or absent, the transcribed text looks garbled, or the criterion is hard to judge from what the student wrote.**

**The user message** renders the scope:
- The question text (and sub-question text if `scope_kind == "sub_question"`).
- Pedagogical context when present: `example_solution`, `trace_tables`, `context_tables` (these now survive compilation per S6's §4 fix — use them; they're the model answer and referenced data).
- The criterion tree: for each criterion, its `description` + `evaluation_guidance` + `notes` as context; then either the criterion as a single grading unit (no sub_criteria) or each sub-criterion as a grading unit (with sub_criteria). Make the parent-vs-leaf distinction explicit so the LLM grades leaves, not parents.
- The student's answer (`student_answer_text`).
- An explicit enumeration of the terminal criterion IDs the LLM must return a grade for (reinforces closed-world; the LLM should return exactly these IDs).

**`notes` / `evaluation_guidance` as guidance:** present them as grading guidance for the relevant criterion (e.g. "consider: {evaluation_guidance}"; "{notes}"). These replace the plan's `extra_notes` concept.

Keep the prompt a pure render function (request → strings). No I/O, no LLM call — that's the agent's job. This keeps it unit-testable.

### 6.1 Prompt versioning

Define a module-level `GRADING_PROMPT_VERSION` constant in `prompt.py` (e.g. `"grader-v1"` — a simple string, bumped by hand whenever the system prompt or the rendering logic changes in a way that could affect grades). The agent stamps it into every `GradedTestDraft.prompt_version` (§4).

Why this matters (and why it's worth the two lines now): a grade is a function of `(rubric_contract_version, transcription_contract_version, model_version, prompt_version)`. Without `prompt_version` you cannot answer "which prompt produced this grade?" — which makes the future eval suite unable to attribute a quality regression to a prompt change vs. a model change. Stamping it now, before any grades exist, means every grade ever produced is attributable. Cheap insurance; expensive to retrofit.

Keep it a hand-maintained constant, not a hash of the prompt text — a human-meaningful version ("grader-v3") is more useful in eval reports than a content hash, and it lets you bump the version deliberately when a change is grade-affecting vs. cosmetic.

---

## 7. The deterministic validator

New file `app/agents/grader/validator.py`. **Pure function, no LLM calls** — this is the testable heart of correctness.

```
validate_scope_grading(
    response: QuestionGradingResponse,
    scope: GradableScope,
    numeric_policy: NumericPolicy,
) -> ValidationResult     # validated per-terminal grades + flags + annotations
```

Four deterministic checks, applied to the LLM's response for one scope:

### 7.1 Closed-world re-check (defense in depth)
The set of `terminal_criterion_id`s the LLM returned must equal the scope's terminal set:
- **Extra ID** (LLM returned a grade for an ID not in the scope) → drop it, flag `CLOSED_WORLD_VIOLATION` (scope-level), `error`-severity annotation. (This should be near-impossible — the prompt only shows in-scope IDs — but it's the defense-in-depth check that makes closed-world structural, per Phase 0a CW-3.)
- **Missing ID** (a terminal in the scope got no grade from the LLM) → award 0, flag `UNGRADED_CRITERION`, `warning` annotation.

### 7.2 Bounds & precision
For each terminal grade: clamp `points_awarded` to `[0, terminal.points]`; round to `numeric_policy.precision` (default `Decimal("0.25")` per S6 research — NOT 0.5; read it from the policy, don't hardcode). If clamping changed the value, flag `BOUNDS_CLAMPED` (`warning`). All arithmetic in `Decimal`.

### 7.3 Quote validation
For each terminal grade with a non-empty `quote_text`, validate against the scope's `student_answer_text` (research §5):
- Normalize both (case-fold, whitespace-collapse).
- **Exact substring** → `QuoteValidationStatus.EXACT`.
- Else **fuzzy**: `difflib.SequenceMatcher(None, quote, answer).ratio()` — but ratio-over-the-whole-answer is wrong for a short quote in a long answer. Use a sliding-window or best-substring-match approach: check the quote against comparable-length windows of the answer, take the best ratio. `≥ 0.85` → `QuoteValidationStatus.FUZZY`, flag `FUZZY_MATCH` (`info`).
- Else → `QuoteValidationStatus.NOT_FOUND`, flag `QUOTE_NOT_FOUND` (`warning`). The grade stands (we don't zero it — a correct grade with a bad quote is still probably correct), but it's flagged for teacher attention.
- Empty `quote_text` on a non-zero award → flag `QUOTE_NOT_FOUND` (the LLM awarded points without evidence). Empty quote on a zero award → fine, no flag.

Set `validation_status` on the `AnswerQuotation`.

**Note on fuzzy matching:** `difflib` is stdlib (no `rapidfuzz`/`Levenshtein` installed — research §5). The sliding-window best-substring match matters: a 5-word quote inside a 200-word answer scores terribly on a whole-string ratio even when it's an exact substring of a slightly-misremembered form. Implement the window search; a naive whole-answer ratio will produce false `NOT_FOUND`s. This is the one validator subtlety worth getting right.

### 7.4 Annotation production
Each flag above maps to a `GradingAnnotation` (§4.1) with the appropriate severity. Severity mapping: `CLOSED_WORLD_VIOLATION` → `error`; `UNGRADED_CRITERION`, `BOUNDS_CLAMPED`, `QUOTE_NOT_FOUND` → `warning`; `FUZZY_MATCH` → `info`. `target_id` = the criterion/sub-criterion ID (or the scope's question/sub-question for scope-level flags).

The validator is pure and returns everything (validated grades + flags + annotations); the agent assembles them into outcomes.

---

## 8. The agent

New files `app/agents/grader/grader.py` + `app/agents/grader/__init__.py`.

```
class GraderAgent:
    async def grade(self, gradable_test: GradableTest) -> GradedTestDraft
```

### 8.1 Per-scope grading

`_grade_scope(scope) -> ScopeOutcome`:
- **Skip path** — `scope.alignment == "answer_missing"` OR `scope.student_answer_text` is empty: do NOT call the LLM. Emit deterministic 0-point outcomes for every terminal in the scope, each flagged `NO_ANSWER`. `graded_by = "skipped_no_answer"`. (Decision GA-2.) An `info` annotation per scope.
- **Grade path** — otherwise: build the `QuestionGradingRequest`, render the prompt, call the LLM via `with_structured_output(QuestionGradingResponse)` (§8.3), run `validate_scope_grading` (§7), assemble `CriterionOutcome`s (aggregating sub-criterion outcomes for branch criteria), set `graded_by = "llm"`.
- **Transient-failure retry (1 attempt), then failure path** — if the LLM call raises a *transient transport error* (timeout, connection error, rate-limit 429, 5xx), retry the call **once**, for that scope only, after a short jittered backoff. If the retry succeeds, the scope grades normally (`graded_by = "llm"`, `retry_count = 1`) and is assembled into the draft exactly like any first-try success — the blip is invisible downstream. If the retry also fails — or if the original error was *non-transient* (e.g. a schema-validation/parse failure, which is deterministic and won't benefit from a retry) — fall to the failure path: emit 0-point outcomes for every terminal, flag the scope `LLM_UNCERTAINTY` with a clear message, `error`-severity annotation, `graded_by = "failed"`. **The scope failure does NOT propagate** — it degrades to a flagged, reviewable zero-outcome (see §8.2).

### 8.1.1 Retry scope and the GA-3 boundary

The retry is **surgical and transport-level**, and does **not** violate sprint-plan decision GA-3 ("no ReAct retries"). GA-3 forbids re-prompting the model to get a *better grade*; this retries an *infrastructure blip*. The distinction is the whole point:

- **Retried (transient transport failures):** timeout, connection error, rate-limit (429), 5xx. Infrastructure, not content — the same input retried once will likely succeed. Exactly **one** retry, scoped to the **single failing question/sub-question scope** — never the whole test, never the already-successful scopes. A short **jittered** backoff before the retry (jitter matters: with the semaphore at 5, a rate-limit often hits several scopes at once; un-jittered retries would collide again and re-trip the limit).
- **Never retried (content / deterministic outcomes):** a quote that doesn't validate, points out of bounds, a closed-world violation, or a schema-parse failure. At `temperature=0.0` these are deterministic — re-calling wastes money and returns the same result. They **flag**, per GA-3. A bad grade is a flag, not a retry.

Classify transient errors by the OpenAI/LangChain exception taxonomy of the installed version (e.g. `openai.APITimeoutError`, `openai.RateLimitError`, `openai.APIConnectionError`, `openai.InternalServerError`). **If the taxonomy is unclear in the installed version, flag rather than guessing** — a too-broad "retry on any `Exception`" would re-invoke on deterministic content failures, doubling cost for no benefit and blurring the GA-3 line. The retry is per-scope and independent; there is no test-level retry and no re-grading of scopes that already succeeded.

### 8.2 Bounded-parallel execution (D2)

Grade scopes concurrently with **bounded** concurrency and **exception isolation**:

```python
sem = asyncio.Semaphore(MAX_CONCURRENT_SCOPES)   # e.g. 5, matching the transcription service

async def _bounded(scope):
    async with sem:
        return await self._grade_scope(scope)   # _grade_scope catches its own LLM errors (§8.1 failure path)

results = await asyncio.gather(*(_bounded(s) for s in gradable_test.scopes),
                               return_exceptions=True)
```

Three design requirements, each non-negotiable for debuggability:

1. **Bounded concurrency.** A `Semaphore` (default 5, a module constant `MAX_CONCURRENT_SCOPES`). Unbounded `gather` over 30 scopes invites rate-limit 429s. Cap it.
2. **Exception isolation.** `return_exceptions=True`. `_grade_scope` already catches LLM errors internally and returns a failed `ScopeOutcome` (§8.1), so an exception reaching `gather` is an *unexpected* bug, not an LLM failure. Handle both: if a result is an `Exception` (escaped the per-scope handler), convert it to a failed `ScopeOutcome` for that scope with the exception detail, and log it loudly — losing one scope must never lose the other 29 results. Grading is expensive; partial results are always better than a thrown batch.
3. **Output is a total function of input.** Every scope in `gradable_test.scopes` produces exactly one `ScopeOutcome` (success, skip, or failure). `len(scope_outcomes) == len(scopes)` always. This invariant makes S8's persistence and the teacher's review predictable — there's always an outcome per scope, even if it's a flagged failure.

### 8.3 The LLM call (research §2)

Use LangChain `with_structured_output` — the V3 pipeline's proven pattern, which eliminates manual JSON parsing:

```python
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model=settings.openai_model, temperature=0.0,
                 max_tokens=8192, api_key=settings.openai_api_key)
structured = llm.with_structured_output(QuestionGradingResponse)
response: QuestionGradingResponse = await structured.ainvoke([
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=rendered_user_message),
])
```

`temperature=0.0` (grading should be as deterministic as the model allows). Construct the `llm` once per `grade()` call (or once per agent), not once per scope.

### 8.4 Observability (D2 — the explicit ask)

Grading is expensive and parallel; when something goes wrong you must be able to diagnose *which scope*, *why*, without dumping PII or full payloads. Per-scope structured logging:

- **Per scope, one structured log record:** `question_id`, `sub_question_id`, `scope_kind`, `graded_by` (llm/skipped/failed), `retry_count` (0 or 1, plus the transient exception class when a retry occurred), `duration_ms`, `terminal_count`, `flag_count` (by reason), and on failure the **exception class + message** (NOT the student answer, NOT the full LLM response). A `points_awarded`/`points_possible` summary per scope is fine.
- **Per grade, one summary record:** `rubric_contract_version`, `transcription_contract_version`, `model_version`, total `llm_calls_count`, total `grading_duration_ms`, scope counts by `graded_by`, count of scopes that needed a transient retry (and how many of those still failed), total flags by reason. (Matches the plan's logging discipline, §"Logging discipline".)
- **No logging of:** the full LLM response (log a hash + token count if useful), the student's answer text, or any PII. The reasoning/quotes live in the draft artifact, not the logs.
- Track `llm_calls_count` (= count of scopes that took the grade path; skipped and pre-failure scopes don't count) and `grading_duration_ms` (wall-clock for the whole parallel grade) onto the `GradedTestDraft`.

### 8.5 Assembly

After all scopes resolve: assemble the `GradedTestDraft` (§4) — `scope_outcomes` (one per scope, ordered to match input), empty `teacher_overrides`, all `annotations` collected from validation + skip/fail paths, `unmatched_transcription_answers` echoed from the `GradableTest`, the two observability counters, the pinned contract versions, `model_version`, and `prompt_version` (the `GRADING_PROMPT_VERSION` constant, §6.1). Propagate `confidence` up the tree: leaf → criterion (min of children for branches) → `ScopeOutcome.min_confidence` (min across the scope's terminals). Skipped scopes get `confidence = 0.0` (no grade was made; surface them for review). Failed scopes likewise `confidence = 0.0`. Return the object. **No persistence** — return it.

---

## 9. Testing

### Validator (pure — zero mocks; this is the correctness core)
`tests/agents/test_grader_validator.py`:
1. **Closed-world — extra ID** dropped + `CLOSED_WORLD_VIOLATION` flag + error annotation.
2. **Closed-world — missing ID** → 0 points + `UNGRADED_CRITERION` flag.
3. **Bounds — over max** clamped + `BOUNDS_CLAMPED`.
4. **Bounds — negative** clamped to 0 + `BOUNDS_CLAMPED`.
5. **Precision** — value rounded to `numeric_policy.precision` (use 0.25; assert a 0.3 rounds correctly).
6. **Quote — exact substring** → `EXACT`, no flag.
7. **Quote — short quote in long answer (exact substring)** → `EXACT` (the sliding-window test — proves a 5-word exact quote in a 200-word answer is NOT a false `NOT_FOUND`). **This is the critical validator test.**
8. **Quote — fuzzy** (slight misremember, ≥0.85) → `FUZZY` + `FUZZY_MATCH` flag.
9. **Quote — not found** → `NOT_FOUND` + `QUOTE_NOT_FOUND` flag; grade stands.
10. **Quote — empty on non-zero award** → `QUOTE_NOT_FOUND` flag.

### Agent (mocked LLM)
`tests/agents/test_grader_agent.py`:
11. **Skip path** — a scope with `alignment="answer_missing"` produces 0-point outcomes + `NO_ANSWER`, `graded_by="skipped_no_answer"`, and **no LLM call** (assert the mock wasn't invoked for that scope).
12. **Grade path** — a scope with an answer, mocked LLM response → outcomes with the awarded points, `graded_by="llm"`.
13. **Branch criterion aggregation** — a criterion with sub_criteria: `criterion.points_awarded == Σ sub_criterion_outcomes.points_awarded`.
14. **Failure isolation (persistent)** — mock the LLM to raise a transient error on **both the initial call and the retry** for one scope out of three; assert the other two grade successfully, the failed one is a `graded_by="failed"` zero-outcome (`retry_count==1`) with an error annotation, and `grade()` returns a complete draft (does not raise). **This is the critical parallel-design test.**
15. **Output totality** — `len(draft.scope_outcomes) == len(gradable_test.scopes)` for a mixed input (some answered, some missing, one failing).
16. **Counters** — `llm_calls_count` equals the number of grade-path scopes (not skipped, not pre-failed); `grading_duration_ms` is set.
17. **Empty overrides** — `draft.teacher_overrides == {}`.
18. **Transient retry — success on second attempt** — mock the LLM to raise a transient error (simulated timeout/rate-limit) on the first call for one scope, then return a valid response on the retry; assert that scope ends up `graded_by="llm"` with the awarded points, `retry_count==1`, and **no** failure annotation. The other scopes are unaffected. **This is the critical retry test** — it proves a transient blip recovers transparently and assembles into the draft like any success.
19. **No retry on content failure** — mock the LLM to return a response that fails closed-world or quote validation (a *content* failure, not a transport exception); assert the LLM was called **exactly once** for that scope (no retry — the validator flags it, per GA-3) and the scope is graded with the appropriate flags.
20. **Confidence propagation** — leaf confidences propagate to `CriterionOutcome.confidence` (= min of children for a branch criterion) and to `ScopeOutcome.min_confidence` (= min across terminals); a skipped/failed scope has `min_confidence == 0.0`. Assert `draft.prompt_version == GRADING_PROMPT_VERSION`.

Mock the LLM by patching `with_structured_output(...).ainvoke` to return canned `QuestionGradingResponse`s, to raise transient exceptions (tests 14, 18), or to return validation-failing content (test 19). No real OpenAI calls.

Tests 7 (sliding-window quote), 14 (persistent-failure isolation), 18 (transient retry recovery), and 19 (no-retry-on-content) are the ones that protect the subtle correctness, the parallel-design robustness, and the GA-3 boundary.

---

## 10. Acceptance criteria

- [ ] New outcome schemas (`GradedTestDraft`, `ScopeOutcome`, `CriterionOutcome`, `SubCriterionOutcome`) in their own file; Decimal throughout; flat-recursive (one level).
- [ ] Legacy outcome types (`RuleOutcome`, old `CriterionOutcome`, `EvidenceClaim`) untouched.
- [ ] `FlagReason` gains `UNGRADED_CRITERION` and `BOUNDS_CLAMPED`.
- [ ] LLM I/O schemas; structured output via `with_structured_output` (LangChain), Decimal handled at the boundary.
- [ ] Prompt is a pure render function; English instructions, Hebrew output values, `═══` headers; uses `example_solution`/`trace_tables`/`context_tables`/`evaluation_guidance`/`notes`; enumerates terminal IDs; instructs the model to report per-terminal `confidence`.
- [ ] `GRADING_PROMPT_VERSION` constant defined and stamped into `GradedTestDraft.prompt_version`.
- [ ] Per-terminal `confidence` requested in the LLM schema, carried onto each leaf outcome, propagated to `CriterionOutcome.confidence` (min of children for branches) and `ScopeOutcome.min_confidence`; skipped/failed scopes → `0.0`; used only for review-queue ordering, never to auto-accept/reject (calibration deferred to the eval sprint).
- [ ] Validator is pure: closed-world, bounds+precision (read `numeric_policy.precision`, not hardcoded), quote validation with **sliding-window** fuzzy match via `difflib`.
- [ ] Agent: skip path (no LLM call, `NO_ANSWER`), grade path, failure path (degrades to flagged zero-outcome, never propagates).
- [ ] Surgical 1-retry on **transient transport failures only** (timeout/429/5xx/connection), per-scope, jittered backoff; **non-transient and content failures are NOT retried** (GA-3); a retried-and-succeeded scope assembles identically to a first-try success; `retry_count` tracked on the outcome + telemetry.
- [ ] Bounded-parallel (`Semaphore`), `return_exceptions=True`, output is a total function of input (`len(scope_outcomes) == len(scopes)`).
- [ ] Per-scope + per-grade structured logging; no PII / full-response logging; `llm_calls_count` + `grading_duration_ms` tracked.
- [ ] Builds the **complete** in-memory `GradedTestDraft` (outcomes + empty `teacher_overrides` + annotations); **no persistence, no endpoint, no row writes** (D1).
- [ ] All tests pass; tests 7 and 14 explicitly verified; `import app.main` succeeds; `pytest --collect-only` succeeds.

---

## 11. Known follow-ups (do NOT do in this PR)

- **S8** — wires the agent into `/grade`: loads contracts → `compile()` (S6) → `GraderAgent.grade()` (S7) → persists the `GradedTestDraft` into `graded_tests.draft_json`, advances the row `pending → grading → draft`, computes row-level `total_score`/`total_possible`/`percentage`. Rebuilds the S2-stubbed read endpoints with the draft response shape. Replaces the S4 post-submit confirmation with the grading-progress → draft-review flow.
- **S9** — approval: teacher edits via `teacher_overrides`, the approval gate reads `error`-severity annotations (S7 produces them), compiles `GradedTestContract`.
- **Legacy outcome-type removal** — when `graded_json` is dropped, remove `RuleOutcome`/old `CriterionOutcome`/`EvidenceClaim`.

If `with_structured_output` + `Decimal` doesn't round-trip cleanly (§5), or if the actual `GradableScope`/`numeric_policy` access path differs from this spec, **stop and flag** rather than working around it silently. And if the parallel design surfaces an async/event-loop issue with the LangChain client, flag it — the fallback is bounded-sequential, but try bounded-parallel first per D2.
