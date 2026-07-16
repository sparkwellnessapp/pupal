# Ontology System Full Integration Plan

**Version:** 1.0  
**Date:** 2026-02-04  
**Author:** AI Engineering Assistant  
**Status:** IMPLEMENTATION READY

---

## Executive Summary

This document outlines a systematic plan to complete the transition from Vivi's legacy grading system to the new ontology-based architecture. The goal is to eliminate parallel code paths, enforce invariants at every layer, and provide a clean API for frontend integration.

### Core Principles

1. **Single Source of Truth**: `ontology_types.py` is the canonical type definition
2. **Two-Artifact Architecture**: Draft (editable) → Contract (frozen)
3. **Closed-World Grading**: Grader cannot invent criteria, rules, or levels
4. **Evidence-First**: Every grading decision must cite student work
5. **Graceful Degradation**: Never crash the batch, flag issues for review

---

## Phase 1: Rubric Lifecycle Endpoints

**Goal:** Complete CRUD operations for ontology rubrics with draft/contract separation.

### 1.1 Save Ontology Draft Endpoint

**File:** `app/api/v0/rubric_management.py` (new file)

```python
POST /api/v0/rubrics/save_ontology_draft
```

**Purpose:** Save an ExtractRubricResponse (from DOCX/PDF extraction or manual creation) as a draft.

**Request:**
```json
{
  "name": "מבחן ערך מוחלט",
  "description": "Optional description",
  "draft": { /* ExtractRubricResponse JSON */ }
}
```

**Response:**
```json
{
  "rubric_id": "uuid",
  "name": "מבחן ערך מוחלט",
  "is_ontology_format": true,
  "is_compiled": false,
  "needs_recompilation": false,
  "created_at": "2026-02-04T10:00:00Z"
}
```

**Implementation Tasks:**
- [ ] Create `app/api/v0/rubric_management.py`
- [ ] Add Pydantic request/response schemas to `app/schemas/rubric_management.py`
- [ ] Implement service function in `app/services/rubric_management_service.py`
- [ ] Validate `ExtractRubricResponse` structure before saving
- [ ] Set `draft_json`, clear `contract_json`, set `needs_recompilation=True`

---

### 1.2 Update Draft Endpoint

```python
PUT /api/v0/rubrics/{rubric_id}/draft
```

**Purpose:** Update the draft after teacher edits in the UI.

**Request:**
```json
{
  "draft": { /* Updated ExtractRubricResponse JSON */ },
  "edit_summary": "Added criterion for code efficiency"
}
```

**Response:**
```json
{
  "rubric_id": "uuid",
  "updated_at": "2026-02-04T10:05:00Z",
  "needs_recompilation": true,
  "previous_contract_version": "abc123" // null if never compiled
}
```

**Implementation Tasks:**
- [ ] Validate incoming draft against `ExtractRubricResponse` schema
- [ ] Set `needs_recompilation=True` if `contract_json` exists
- [ ] Log edit for audit trail
- [ ] Return warning if trying to edit after grades exist

---

### 1.3 Compile Rubric Endpoint

```python
POST /api/v0/rubrics/{rubric_id}/compile
```

**Purpose:** Compile draft to frozen contract, handling warnings.

**Request:**
```json
{
  "acknowledged_warning_ids": ["narrowness_issue:q1.c0"],
  "numeric_policy": {
    "precision": "0.25",
    "rounding_mode": "half_up",
    "sum_tolerance": "0.01"
  }
}
```

**Response (Success):**
```json
{
  "rubric_id": "uuid",
  "contract_version": "new-uuid",
  "compiled_at": "2026-02-04T10:10:00Z",
  "is_compiled": true,
  "total_questions": 3,
  "total_criteria": 12,
  "total_rules": 24
}
```

**Response (Warnings Require Acknowledgment):**
```json
{
  "status": "warnings_require_acknowledgment",
  "warnings": [
    {
      "id": "narrowness_issue:q1.c0",
      "type": "narrowness_issue",
      "severity": "warning",
      "message": "Criterion 'הגדרת מחלקה' is not linked to any skill target",
      "target_id": "q1.c0"
    }
  ]
}
```

**Response (Compilation Error):**
```json
{
  "status": "compilation_error",
  "errors": [
    {
      "id": "grounding_issue:q1",
      "type": "grounding_issue", 
      "severity": "error",
      "message": "Question 1: Criteria sum (35) differs from declared total (40) by 5",
      "target_id": "q1"
    }
  ]
}
```

**Implementation Tasks:**
- [ ] Fetch rubric, validate `draft_json` exists
- [ ] Call `ContractCompiler().compile()` with acknowledged warnings
- [ ] Handle `WarningsRequireAcknowledgment` → return 200 with warnings list
- [ ] Handle `CompilationError` → return 400 with errors list
- [ ] On success: save `contract_json`, `contract_version`, `last_compiled_at`
- [ ] Set `needs_recompilation=False`, increment `compilation_attempts`

---

### 1.4 Get Rubric Details Endpoint (Enhanced)

```python
GET /api/v0/rubrics/{rubric_id}
```

**Response:**
```json
{
  "id": "uuid",
  "name": "מבחן ערך מוחלט",
  "description": "...",
  "created_at": "...",
  "updated_at": "...",
  
  "format": "ontology",  // or "legacy"
  "is_compiled": true,
  "needs_recompilation": false,
  "contract_version": "abc123",
  "last_compiled_at": "...",
  
  "stats": {
    "total_points": 100,
    "total_questions": 3,
    "total_criteria": 12,
    "total_rules": 24
  },
  
  "draft_json": { /* if requested */ },
  "contract_json": { /* if compiled */ },
  
  // Legacy fallback
  "rubric_json": { /* if legacy format */ }
}
```

**Implementation Tasks:**
- [ ] Extend existing `get_rubric` endpoint with new fields
- [ ] Add query param `?include_draft=true&include_contract=true`
- [ ] Compute stats from draft or contract

---

### 1.5 List Rubrics Endpoint (Enhanced)

```python
GET /api/v0/rubrics
```

**Query Params:**
- `format`: `"ontology"`, `"legacy"`, `"all"` (default: all)
- `compiled_only`: `true`/`false`
- `needs_recompilation`: `true`/`false`

**Response:**
```json
{
  "rubrics": [
    {
      "id": "uuid",
      "name": "...",
      "format": "ontology",
      "is_compiled": true,
      "needs_recompilation": false,
      "total_points": 100,
      "created_at": "..."
    }
  ],
  "total": 15,
  "ontology_count": 8,
  "legacy_count": 7
}
```

---

## Phase 2: Unified Extraction Flow

**Goal:** Ensure extraction pipelines output to `draft_json` and guide users to compilation.

### 2.1 Update DOCX Extraction Flow

**File:** `app/api/v0/grading.py` - `extract_rubric_docx`

**Current Behavior:** Returns `ExtractRubricResponse` but doesn't save.

**New Behavior:**
1. Extract rubric → `ExtractRubricResponse`
2. Optionally auto-save to `draft_json` if `?auto_save=true`
3. Return extraction result with `rubric_id` if saved

**Implementation Tasks:**
- [ ] Add `auto_save: bool = Query(False)` parameter
- [ ] If `auto_save=True`, create Rubric with `draft_json`
- [ ] Return `rubric_id` in response for subsequent compilation
- [ ] Add `extraction_metadata.needs_compilation_before_grading = true`

---

### 2.2 Update PDF Extraction Flow

**File:** `app/api/v0/grading.py` - `extract_rubric`

**Current:** Returns `LegacyExtractRubricResponse`

**New:** Add conversion path to ontology format.

```python
POST /api/v0/rubrics/convert_legacy_to_ontology/{rubric_id}
```

**Implementation Tasks:**
- [ ] Create migration function `legacy_to_ontology_draft()`
- [ ] Handle structure differences (sub_questions → criteria flattening)
- [ ] Preserve original in `legacy_rubric_json_backup`
- [ ] Set `draft_json` with converted data

---

### 2.3 Unified Extraction Endpoint v3

```python
POST /api/v0/rubrics/extract
```

**Request (multipart/form-data):**
- `file`: DOCX or PDF
- `name`: Optional rubric name
- `auto_save`: boolean (default: true)
- `target_format`: `"ontology"` (default) or `"legacy"`

**Response:**
```json
{
  "rubric_id": "uuid",  // if auto_save
  "format": "ontology",
  "extraction_result": { /* ExtractRubricResponse */ },
  "next_steps": {
    "action": "compile",
    "endpoint": "/api/v0/rubrics/{rubric_id}/compile",
    "warnings_preview": ["1 criterion needs skill alignment"]
  }
}
```

---

## Phase 3: Grading System Unification

**Goal:** Merge `TestGraderAgent` and `OntologyGradingService` into a coherent system.

### 3.1 Architecture Decision: Agent-First with Service Validation

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer                             │
│  POST /api/v0/grading/grade_ontology                    │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│               TestGraderAgent (LangGraph)                │
│  - Sequential question/criterion processing              │
│  - 1 LLM call per criterion                             │
│  - ReAct quote validation loop                          │
│  - Graceful degradation (skip + flag)                   │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│           OntologyGradingService (Validator)             │
│  - Final invariant validation                            │
│  - Double-counting prevention (INV-7)                   │
│  - Closed-world enforcement (INV-3)                     │
│  - Version verification (INV-A6)                        │
└─────────────────────────────────────────────────────────┘
```

**Rationale:**
- `TestGraderAgent` handles the LLM orchestration (complex, stateful)
- `OntologyGradingService` validates the output (simple, deterministic)
- This avoids duplicating LLM logic in `OntologyGradingService`

---

### 3.2 Update `grade_ontology` Endpoint

**File:** `app/api/v0/grading.py`

**Current Issues:**
1. Doesn't create `GradingSession` record
2. Doesn't validate output with `OntologyGradingService`
3. Returns dict instead of `GradedTestDraft` model
4. Doesn't save to `GradedTest` table

**New Implementation:**

```python
@router.post("/grade_ontology")
async def grade_with_ontology_agent(
    request: OntologyGradeRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_active_user),
) -> OntologyGradeResponse:
    """
    Grade student answers using the TestGrader Agent.
    
    Flow:
    1. Validate rubric has compiled contract
    2. Create GradingSession record
    3. Run TestGraderAgent
    4. Validate output with OntologyGradingService
    5. Save GradedTestDraft to database
    6. Update GradingSession status
    """
```

**Implementation Tasks:**
- [ ] Create `GradingSession` before grading starts
- [ ] Update session `status` = "grading"
- [ ] Run agent, capture `GradedTestDraft` from state
- [ ] Call `OntologyGradingService` for final validation
- [ ] Handle validation failures → flag, don't crash
- [ ] Save to `GradedTest` with `graded_json = draft.to_legacy_format()`
- [ ] Also store full `graded_test_draft_json` in session
- [ ] Update session `status` = "completed" or "failed"
- [ ] Return proper `OntologyGradeResponse` model

---

### 3.3 Add Batch Grading Endpoint

```python
POST /api/v0/grading/grade_ontology_batch
```

**Request:**
```json
{
  "rubric_id": "uuid",
  "students": [
    {
      "student_name": "יעל כהן",
      "filename": "yael_cohen.pdf",
      "answers": [
        {"question_id": "q1", "content": "public class..."}
      ]
    }
  ],
  "batch_name": "כיתה י'2 - מבחן 1",
  "class_id": "10-2"
}
```

**Response:**
```json
{
  "batch_id": "uuid",
  "contract_version": "abc123",
  "status": "processing",
  "total_students": 25,
  "progress_url": "/api/v0/grading/batches/{batch_id}/progress"
}
```

**Implementation Tasks:**
- [ ] Create `GradingBatch` record
- [ ] Create `GradingSession` for each student
- [ ] Process in background (async task queue or background thread)
- [ ] Enforce same `contract_version` for all (INV-A6)
- [ ] Return immediately with batch_id for polling

---

### 3.4 Batch Progress Endpoint

```python
GET /api/v0/grading/batches/{batch_id}/progress
```

**Response:**
```json
{
  "batch_id": "uuid",
  "status": "in_progress",
  "total_students": 25,
  "completed": 12,
  "failed": 1,
  "in_progress": 1,
  "pending": 11,
  "progress_percentage": 52.0,
  "estimated_remaining_seconds": 180,
  "sessions": [
    {
      "session_id": "uuid",
      "student_name": "יעל כהן",
      "status": "completed",
      "score": "85/100",
      "flagged_count": 2
    }
  ]
}
```

---

### 3.5 Session Management Endpoints

```python
GET /api/v0/grading/sessions/{session_id}
```
Returns full session details including progress.

```python
POST /api/v0/grading/sessions/{session_id}/resume
```
Resume an interrupted session (status = "grading" but no recent activity).

```python
DELETE /api/v0/grading/sessions/{session_id}
```
Cancel a session (only if not completed).

---

## Phase 4: GradingSession Persistence Integration

**Goal:** Make grading sessions resumable and observable.

### 4.1 Update TestGraderAgent for Persistence

**File:** `app/agents/test_grader/graph.py`

**Current:** Agent runs in-memory, no persistence.

**New:** Add persistence callbacks.

```python
def create_grading_agent_with_persistence(
    session_id: str,
    db_callback: Callable[[GradingAgentState], Awaitable[None]]
) -> CompiledStateGraph:
    """
    Create agent with database persistence after each node.
    
    The db_callback is called after each node execution to save state.
    """
```

**Implementation Tasks:**
- [ ] Add `db_callback` parameter to agent creation
- [ ] Call callback after each node with current state
- [ ] Serialize state to `GradingSession.state_snapshot`
- [ ] Handle serialization of Decimal, datetime, etc.

---

### 4.2 Session State Serialization

**File:** `app/agents/test_grader/persistence.py` (new)

```python
def serialize_state(state: GradingAgentState) -> dict:
    """Serialize agent state for database storage."""
    
def deserialize_state(data: dict) -> GradingAgentState:
    """Restore agent state from database."""
    
async def save_session_state(
    db: AsyncSession,
    session_id: UUID,
    state: GradingAgentState
) -> None:
    """Update GradingSession with current state."""
    
async def load_session_state(
    db: AsyncSession,
    session_id: UUID
) -> Optional[GradingAgentState]:
    """Load state for resumption."""
```

---

### 4.3 Progress Update Strategy

**Approach:** Update database after each criterion completion.

```python
# In validate_response node, after accepting evaluation:
await update_session_progress(
    session_id=state["session_id"],
    completed_criteria=state["completed_criteria"],
    current_question_idx=state["current_question_idx"],
    current_criterion_idx=state["current_criterion_idx"],
)
```

**Frequency:** Every criterion (not every node) to balance freshness vs. DB load.

---

## Phase 5: Evidence Extractor Enhancement

**Goal:** Move beyond Phase 1 placeholder to real LLM-based extraction.

### 5.1 Decision: Deprecate `OntologyGradingService.grade()` for LLM Grading

The current `OntologyGradingService.grade()` uses `evidence_extractor.evaluate_rule()` which is a placeholder. Instead:

1. `TestGraderAgent` handles all LLM-based grading
2. `OntologyGradingService` becomes a validation-only service
3. `evidence_extractor.py` is deprecated for grading (keep for rule-kind routing info)

**New `OntologyGradingService` Interface:**

```python
class OntologyGradingService:
    """Validates grading outputs against ontology invariants."""
    
    def validate_draft(
        self,
        draft: GradedTestDraft,
        contract: GradingRubricContract,
    ) -> ValidationResult:
        """
        Validate a GradedTestDraft against contract invariants.
        
        Checks:
        - INV-3: Closed-world (all IDs exist in contract)
        - INV-7: Double-counting prevention
        - INV-A2: Points consistency
        - INV-A3: Evidence completeness
        """
```

**Implementation Tasks:**
- [ ] Rename `grade()` to `validate_draft()`
- [ ] Remove LLM-related code from `OntologyGradingService`
- [ ] Add `validate_draft()` call in `grade_ontology` endpoint
- [ ] Update imports and tests

---

## Phase 6: Database Migrations

### 6.1 Required SQL Migrations

**Migration 006: Add missing columns if not present**

```sql
-- Ensure all ontology columns exist (idempotent)
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS draft_json JSONB;
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS contract_json JSONB;
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS contract_version VARCHAR(50);
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS last_compiled_at TIMESTAMPTZ;
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS needs_recompilation BOOLEAN DEFAULT FALSE;
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS acknowledged_warnings JSONB DEFAULT '[]';
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS compilation_attempts INTEGER DEFAULT 0;
ALTER TABLE rubrics ADD COLUMN IF NOT EXISTS legacy_rubric_json_backup JSONB;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_rubrics_contract_version ON rubrics(contract_version);
CREATE INDEX IF NOT EXISTS idx_rubrics_needs_recompilation ON rubrics(needs_recompilation);
```

**Migration 007: Add grading_batches if not present**

```sql
CREATE TABLE IF NOT EXISTS grading_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    teacher_id UUID REFERENCES users(id) ON DELETE SET NULL,
    rubric_id UUID NOT NULL REFERENCES rubrics(id) ON DELETE CASCADE,
    contract_version VARCHAR(50) NOT NULL,
    name VARCHAR(255),
    class_id VARCHAR(100),
    status VARCHAR(30) NOT NULL DEFAULT 'created',
    total_sessions INTEGER NOT NULL DEFAULT 0,
    completed_sessions INTEGER NOT NULL DEFAULT 0,
    failed_sessions INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_grading_batches_rubric_id ON grading_batches(rubric_id);
CREATE INDEX IF NOT EXISTS idx_grading_batches_teacher_id ON grading_batches(teacher_id);
CREATE INDEX IF NOT EXISTS idx_grading_batches_status ON grading_batches(status);
```

---

## Phase 7: Legacy Compatibility

### 7.1 Dual-Path Grading Router

**File:** `app/services/grading_router.py` (new)

```python
async def grade_test(
    rubric: Rubric,
    student_test: Dict[str, Any],
    db: AsyncSession,
    user_id: UUID,
) -> GradedTestResponse:
    """
    Route to appropriate grading system based on rubric format.
    
    - Ontology format + compiled: TestGraderAgent
    - Ontology format + not compiled: Error (must compile first)
    - Legacy format: GradingAgent (legacy)
    """
    if rubric.is_ontology_format:
        if not rubric.is_compiled:
            raise HTTPException(
                status_code=400,
                detail="Rubric must be compiled before grading. Call POST /rubrics/{id}/compile"
            )
        return await grade_with_ontology(rubric, student_test, db, user_id)
    else:
        return await grade_with_legacy(rubric, student_test, db, user_id)
```

### 7.2 Update Existing Endpoints

Update `grade_tests`, `grade_handwritten_test`, `grade_with_transcription` to use the router:

```python
@router.post("/grade_tests")
async def grade_tests(...):
    rubric = await get_rubric_by_id(db, rubric_id)
    
    for test in tests:
        result = await grading_router.grade_test(rubric, test, db, user.id)
        ...
```

---

## Phase 8: Testing Strategy

### 8.1 Unit Tests

| Test File | Coverage |
|-----------|----------|
| `tests/api/test_rubric_management.py` | Save, update, compile endpoints |
| `tests/api/test_grading_ontology.py` | Single + batch grading |
| `tests/api/test_session_management.py` | Progress, resume, cancel |
| `tests/services/test_grading_router.py` | Dual-path routing |

### 8.2 Integration Tests

| Test File | Coverage |
|-----------|----------|
| `tests/integration/test_full_grading_flow.py` | Extract → Compile → Grade → Review |
| `tests/integration/test_batch_grading.py` | 10+ students batch |
| `tests/integration/test_session_recovery.py` | Interrupt + resume |

### 8.3 Adversarial Tests

From spec `evaluation_plan.adversarial_test_cases`:
- [ ] Empty student answer → should score 0, flag for review
- [ ] Hallucinated quotes → should fail validation, retry
- [ ] Invalid level_id → should reject, retry with feedback
- [ ] Contract recompiled mid-batch → should reject

---

## Phase 9: Observability & Monitoring

### 9.1 Logging Standards

```python
# Good
logger.info(f"[GradingSession:{session_id}] Criterion {criterion_id} evaluated: {points}/{max_points}")

# Bad
logger.info(f"Evaluated criterion")  # Missing context
```

### 9.2 Metrics to Track

| Metric | Type | Description |
|--------|------|-------------|
| `grading_session_duration_ms` | Histogram | Total session time |
| `grading_criterion_duration_ms` | Histogram | Per-criterion time |
| `grading_llm_calls_total` | Counter | LLM calls per session |
| `grading_retry_count` | Counter | Quote validation retries |
| `grading_flagged_outcomes` | Counter | Flagged for review |
| `compilation_success_rate` | Gauge | % successful compiles |

### 9.3 Error Alerting

- Session stuck in "grading" for > 10 minutes
- Batch failure rate > 20%
- LLM error rate > 5%

---

## Implementation Timeline

| Week | Phase | Deliverables |
|------|-------|--------------|
| 1 | Phase 1 | Rubric CRUD endpoints |
| 1 | Phase 2 | Extraction flow updates |
| 2 | Phase 3 | Grading unification |
| 2 | Phase 4 | Session persistence |
| 3 | Phase 5 | Service refactoring |
| 3 | Phase 6 | Migrations |
| 4 | Phase 7-8 | Legacy compat + tests |
| 4 | Phase 9 | Observability |

---

## File Structure After Implementation

```
app/
├── api/v0/
│   ├── grading.py                    # Updated grading endpoints
│   ├── rubric_management.py          # NEW: Rubric CRUD for ontology
│   └── session_management.py         # NEW: Session/batch endpoints
├── schemas/
│   ├── ontology_types.py             # Canonical types (unchanged)
│   ├── rubric_management.py          # NEW: Request/response schemas
│   └── grading_responses.py          # NEW: Unified grading responses
├── services/
│   ├── grading_router.py             # NEW: Route to legacy or ontology
│   ├── rubric_management_service.py  # NEW: Rubric business logic
│   ├── ontology_grading_service.py   # UPDATED: Validation only
│   ├── grading_service.py            # Legacy (unchanged)
│   └── contract_compiler.py          # Unchanged
├── agents/
│   └── test_grader/
│       ├── persistence.py            # NEW: State serialization
│       └── ...                       # Existing files
└── models/
    └── grading.py                    # Updated with relationships
```

---

## Success Criteria

| Criterion | Target | Measurement |
|-----------|--------|-------------|
| All ontology endpoints functional | 100% | Integration tests pass |
| Legacy endpoints still work | 100% | Regression tests pass |
| Grading session survives browser close | Yes | Manual test |
| Batch grading completes | < 2s/student | Performance test |
| Evidence citation rate | 100% | `rules_with_valid_quotes / total_rules` |
| Teacher agreement | > 90% | A/B test with 50 real tests |

---

# Appendix A: Frontend API Guide

See separate document: `API_GUIDE.md`

