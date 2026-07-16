# Vivi Grading API Guide for Frontend Engineers

**Version:** 1.0  
**Last Updated:** 2026-02-04  
**Base URL:** `/api/v0`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Rubric Lifecycle](#rubric-lifecycle)
4. [Grading Flow](#grading-flow)
5. [Session Management](#session-management)
6. [Data Types Reference](#data-types-reference)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Overview

### Two Rubric Formats

Vivi supports two rubric formats:

| Format | Description | Grading Engine |
|--------|-------------|----------------|
| **Legacy** | Original JSON format | `GradingAgent` |
| **Ontology** | New structured format with contracts | `TestGraderAgent` |

**Key Difference:** Ontology rubrics require **compilation** before grading.

### Rubric Lifecycle (Ontology)

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Extract    │  →   │    Draft     │  →   │   Contract   │
│  (DOCX/PDF)  │      │  (Editable)  │      │   (Frozen)   │
└──────────────┘      └──────────────┘      └──────────────┘
                            │                      │
                      Teacher edits          Ready to grade
                            │                      │
                            └──────── Compile ─────┘
```

---

## Authentication

All endpoints require authentication via JWT token:

```http
Authorization: Bearer <jwt_token>
```

---

## Rubric Lifecycle

### 1. Extract Rubric from Document

#### DOCX Extraction (Recommended)

```http
POST /grading/extract_rubric_docx
Content-Type: multipart/form-data

file: <rubric.docx>
name: "מבחן בגרות תשפ״ו"
subject: "computer_science"
locale: "he-IL"
use_llm_classification: true
```

**Response (200 OK):**
```json
{
  "schema_version": "2.0",
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "rubric_name": "מבחן בגרות תשפ״ו",
  "subject": "computer_science",
  "total_points": "100",
  "questions": [
    {
      "question_id": "q1",
      "question_type": "coding_task",
      "question_text": "כתוב מחלקה בשם Plane...",
      "total_points": "40",
      "criteria": [
        {
          "criterion_id": "q1.c0",
          "description": "הגדרת מחלקה Plane עם שדות פרטיים",
          "points": "10",
          "rules": [
            {
              "rule_id": "q1.c0.r0",
              "description": "הגדרת המחלקה",
              "max_points": "5",
              "scoring_type": "binary",
              "levels": [
                {"level_id": "fail", "points": "0", "condition_hint": "לא הוגדרה מחלקה"},
                {"level_id": "pass", "points": "5", "condition_hint": "מחלקה הוגדרה נכון"}
              ]
            }
          ]
        }
      ]
    }
  ],
  "annotations": [
    {
      "id": "narrowness_issue:q1.c0",
      "annotation_type": "narrowness_issue",
      "severity": "warning",
      "message": "Criterion not linked to skill target"
    }
  ]
}
```

**TypeScript Type:**
```typescript
interface ExtractRubricResponse {
  schema_version: string;
  rubric_id: string;
  rubric_name: string;
  subject: string;
  total_points: string; // Decimal as string
  questions: Question[];
  annotations: Annotation[];
  extraction_metadata?: Record<string, any>;
}
```

---

### 2. Save Rubric Draft

After extraction, save to database:

```http
POST /rubrics/save_ontology_draft
Content-Type: application/json

{
  "name": "מבחן בגרות תשפ״ו",
  "description": "מבחן לכיתה י׳2",
  "draft": { /* ExtractRubricResponse from above */ }
}
```

**Response (201 Created):**
```json
{
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "מבחן בגרות תשפ״ו",
  "is_ontology_format": true,
  "is_compiled": false,
  "needs_recompilation": false,
  "created_at": "2026-02-04T10:00:00Z"
}
```

---

### 3. Update Draft (After Teacher Edits)

```http
PUT /rubrics/{rubric_id}/draft
Content-Type: application/json

{
  "draft": { /* Updated ExtractRubricResponse */ }
}
```

**Response (200 OK):**
```json
{
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "updated_at": "2026-02-04T10:05:00Z",
  "needs_recompilation": true
}
```

---

### 4. Compile Rubric (Required Before Grading)

```http
POST /rubrics/{rubric_id}/compile
Content-Type: application/json

{
  "acknowledged_warning_ids": []
}
```

**Response - Warnings Need Acknowledgment (200):**
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

**Frontend Action:** Show warnings dialog, let teacher acknowledge.

**Retry with acknowledgments:**
```http
POST /rubrics/{rubric_id}/compile
Content-Type: application/json

{
  "acknowledged_warning_ids": ["narrowness_issue:q1.c0"]
}
```

**Response - Success (200):**
```json
{
  "status": "compiled",
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "contract_version": "abc123-def456",
  "compiled_at": "2026-02-04T10:10:00Z",
  "is_compiled": true,
  "stats": {
    "total_questions": 3,
    "total_criteria": 12,
    "total_rules": 24
  }
}
```

**Response - Compilation Error (400):**
```json
{
  "status": "compilation_error",
  "errors": [
    {
      "id": "grounding_issue:q1",
      "type": "grounding_issue",
      "severity": "error",
      "message": "Question 1: Criteria sum (35) differs from declared total (40)",
      "target_id": "q1"
    }
  ]
}
```

**Frontend Action:** Show errors, user must fix draft before compiling.

---

### 5. Get Rubric Details

```http
GET /rubrics/{rubric_id}?include_draft=true&include_contract=false
```

**Response (200):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "מבחן בגרות תשפ״ו",
  "format": "ontology",
  "is_compiled": true,
  "needs_recompilation": false,
  "contract_version": "abc123-def456",
  "last_compiled_at": "2026-02-04T10:10:00Z",
  "stats": {
    "total_points": 100,
    "total_questions": 3,
    "total_criteria": 12
  },
  "draft_json": { /* if include_draft=true */ }
}
```

---

### 6. List Rubrics

```http
GET /rubrics?format=ontology&compiled_only=true
```

**Response (200):**
```json
{
  "rubrics": [
    {
      "id": "uuid",
      "name": "מבחן בגרות תשפ״ו",
      "format": "ontology",
      "is_compiled": true,
      "total_points": 100,
      "created_at": "2026-02-04T10:00:00Z"
    }
  ],
  "total": 15,
  "ontology_count": 8,
  "legacy_count": 7
}
```

---

## Grading Flow

### Single Student Grading

#### Using Ontology Agent (Recommended)

```http
POST /grading/grade_ontology
Content-Type: application/json

{
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "student_name": "יעל כהן",
  "filename": "yael_cohen.pdf",
  "answers": [
    {
      "question_id": "q1",
      "content": "public class Plane {\n  private String id;\n  ...",
      "content_type": "code"
    }
  ]
}
```

**Response (200):**
```json
{
  "session_id": "sess-123",
  "status": "completed",
  "student_name": "יעל כהן",
  "total_points_earned": "85",
  "total_points_possible": "100",
  "percentage": 85.0,
  "grading_duration_ms": 12500,
  "llm_calls_count": 12,
  "warnings": [],
  "flagged_outcomes": [
    {
      "question_id": "q2",
      "criterion_id": "q2.c1",
      "reason": "fuzzy_match",
      "message": "Quote required fuzzy matching"
    }
  ],
  "graded_test_draft": {
    "draft_id": "draft-456",
    "question_outcomes": [
      {
        "question_id": "q1",
        "points_earned": "35",
        "points_possible": "40",
        "criterion_outcomes": [
          {
            "criterion_id": "q1.c0",
            "points_earned": "10",
            "points_possible": "10",
            "reasoning_summary": "התלמיד הגדיר את המחלקה בצורה נכונה עם כל השדות הנדרשים.",
            "rule_outcomes": [
              {
                "rule_id": "q1.c0.r0",
                "selected_level_id": "pass",
                "points_awarded": "5",
                "evidence_claim": {
                  "claim_type": "presence",
                  "claim_statement": "מחלקה Plane הוגדרה עם השדות הנדרשים",
                  "answer_quotations": [
                    {
                      "quote_text": "public class Plane {\n  private String id;",
                      "validation_status": "exact"
                    }
                  ]
                }
              }
            ]
          }
        ]
      }
    ]
  }
}
```

**TypeScript Types:**
```typescript
interface OntologyGradeRequest {
  rubric_id: string;
  student_name: string;
  filename?: string;
  answers: StudentAnswer[];
}

interface StudentAnswer {
  question_id: string;
  content: string;
  content_type?: 'text' | 'code' | 'image_transcription';
}

interface OntologyGradeResponse {
  session_id: string;
  status: 'completed' | 'failed';
  student_name: string;
  total_points_earned: string;
  total_points_possible: string;
  percentage: number;
  grading_duration_ms: number;
  llm_calls_count: number;
  warnings: string[];
  flagged_outcomes: FlaggedOutcome[];
  graded_test_draft: GradedTestDraft;
}

interface FlaggedOutcome {
  rule_id?: string;
  criterion_id?: string;
  question_id?: string;
  reason: 'no_answer' | 'quote_not_found' | 'low_confidence' | 'fuzzy_match' | 'max_retries_exceeded';
  message?: string;
}
```

---

### Batch Grading

```http
POST /grading/grade_ontology_batch
Content-Type: application/json

{
  "rubric_id": "550e8400-e29b-41d4-a716-446655440000",
  "batch_name": "כיתה י׳2 - מבחן 1",
  "class_id": "10-2",
  "students": [
    {
      "student_name": "יעל כהן",
      "filename": "yael_cohen.pdf",
      "answers": [...]
    },
    {
      "student_name": "דני לוי",
      "filename": "dani_levy.pdf", 
      "answers": [...]
    }
  ]
}
```

**Response (202 Accepted):**
```json
{
  "batch_id": "batch-789",
  "status": "processing",
  "contract_version": "abc123-def456",
  "total_students": 25,
  "progress_url": "/api/v0/grading/batches/batch-789/progress"
}
```

**Poll for progress:**
```http
GET /grading/batches/{batch_id}/progress
```

**Response (200):**
```json
{
  "batch_id": "batch-789",
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
      "session_id": "sess-001",
      "student_name": "יעל כהן",
      "status": "completed",
      "score": "85/100",
      "percentage": 85.0,
      "flagged_count": 2
    },
    {
      "session_id": "sess-002",
      "student_name": "דני לוי",
      "status": "grading",
      "progress_percentage": 50.0
    }
  ]
}
```

---

## Session Management

### Get Session Details

```http
GET /grading/sessions/{session_id}
```

**Response (200):**
```json
{
  "session_id": "sess-123",
  "status": "completed",
  "student_name": "יעל כהן",
  "rubric_id": "uuid",
  "contract_version": "abc123",
  "created_at": "2026-02-04T10:15:00Z",
  "completed_at": "2026-02-04T10:15:12Z",
  "progress": {
    "total_questions": 3,
    "total_criteria": 12,
    "completed_criteria": 12,
    "current_question_idx": 3,
    "progress_percentage": 100.0
  },
  "metrics": {
    "llm_calls_count": 12,
    "total_llm_latency_ms": 8500,
    "total_rules_evaluated": 24,
    "rules_with_valid_quotes": 22,
    "rules_flagged_for_review": 2
  },
  "graded_test_draft": { /* if completed */ }
}
```

---

## Data Types Reference

### Question

```typescript
interface Question {
  question_id: string;
  question_type: 'short_answer' | 'coding_task' | 'trace_table' | 'computation' | 'proof' | 'essay';
  question_text?: string;
  total_points: string; // Decimal as string, e.g., "40"
  criteria: Criterion[];
}
```

### Criterion

```typescript
interface Criterion {
  criterion_id: string;
  index: number;
  description: string;
  points: string; // Decimal as string
  skill_targets: string[]; // Skill IDs like "cs.loops.for"
  requirements: string[];
  measurability_status: 'measurable' | 'partially_measurable' | 'not_measurable';
  rules: ReductionRule[];
}
```

### ReductionRule

```typescript
interface ReductionRule {
  rule_id: string;
  index: number;
  description: string;
  max_points: string; // Decimal as string
  scoring_type: 'binary' | 'discrete_levels';
  rule_kind: 'structure_ast' | 'execution_tests' | 'text_alignment' | 'presence_check' | 'reasoning_quality' | 'numeric_accuracy';
  levels: ScoringLevel[];
  depends_on: string[]; // Rule IDs for double-counting prevention
}
```

### ScoringLevel

```typescript
interface ScoringLevel {
  level_id: string;
  level_order: number;
  points: string; // Decimal as string
  condition_hint: string;
}
```

### Annotation

```typescript
interface Annotation {
  id: string;
  annotation_type: 'grounding_issue' | 'narrowness_issue' | 'clarity_issue' | 'review_flag' | 'merge_proposal';
  severity: 'error' | 'warning' | 'info';
  message: string;
  target_id?: string;
}
```

### GradedTestDraft

```typescript
interface GradedTestDraft {
  draft_id: string;
  session_id: string;
  rubric_contract_id: string;
  contract_version: string;
  student_name: string;
  filename?: string;
  
  question_outcomes: QuestionOutcome[];
  total_points_earned: string;
  total_points_possible: string;
  
  status: 'draft' | 'pending_review' | 'approved';
  graded_at: string; // ISO timestamp
  grading_duration_ms: number;
  model_version: string;
  llm_calls_count: number;
  
  warnings: string[];
  flagged_outcomes: FlaggedOutcome[];
}
```

### QuestionOutcome

```typescript
interface QuestionOutcome {
  question_id: string;
  points_earned: string;
  points_possible: string;
  criterion_outcomes: CriterionOutcome[];
}
```

### CriterionOutcome

```typescript
interface CriterionOutcome {
  criterion_id: string;
  points_earned: string;
  points_possible: string;
  reasoning_summary?: string; // Hebrew, 2-4 sentences
  needs_review: boolean;
  rule_outcomes: RuleOutcome[];
}
```

### RuleOutcome

```typescript
interface RuleOutcome {
  rule_id: string;
  selected_level_id: string;
  points_awarded: string;
  evidence_claim: EvidenceClaim;
  needs_review: boolean;
  review_reason?: string;
}
```

### EvidenceClaim

```typescript
interface EvidenceClaim {
  claim_id: string;
  claim_type: 'presence' | 'correctness' | 'coverage' | 'constraint' | 'quality';
  claim_statement: string; // Hebrew, max 200 chars
  matched_level_id: string;
  answer_quotations: AnswerQuotation[];
  confidence_level?: 'high' | 'medium' | 'low';
}
```

### AnswerQuotation

```typescript
interface AnswerQuotation {
  quote_text: string; // Exact quote from student answer
  position_hint?: string;
  validation_status?: 'exact' | 'fuzzy' | 'not_found';
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| 200 | Success | Request completed |
| 201 | Created | Resource created |
| 202 | Accepted | Async operation started (batch) |
| 400 | Bad Request | Validation error, compilation error |
| 401 | Unauthorized | Missing/invalid auth |
| 403 | Forbidden | No access to resource |
| 404 | Not Found | Rubric/session not found |
| 409 | Conflict | Contract version mismatch |
| 500 | Server Error | Unexpected error |

### Error Response Format

```json
{
  "detail": "Human-readable error message",
  "error_code": "RUBRIC_NOT_COMPILED",
  "errors": [
    {
      "field": "rubric_id",
      "message": "Rubric must be compiled before grading"
    }
  ]
}
```

### Common Errors

#### Rubric Not Compiled
```json
{
  "detail": "Rubric must be compiled before grading. Call POST /rubrics/{id}/compile",
  "error_code": "RUBRIC_NOT_COMPILED"
}
```
**Action:** Show compilation dialog.

#### Contract Version Mismatch
```json
{
  "detail": "Contract was recompiled since batch started. Cannot continue.",
  "error_code": "CONTRACT_VERSION_MISMATCH"
}
```
**Action:** Warn user, offer to restart batch with new version.

#### Compilation Error
```json
{
  "status": "compilation_error",
  "errors": [...]
}
```
**Action:** Show errors in rubric editor, user must fix.

---

## Best Practices

### 1. Always Check `is_compiled` Before Grading

```typescript
async function gradeStudent(rubricId: string, student: StudentData) {
  const rubric = await api.getRubric(rubricId);
  
  if (!rubric.is_compiled) {
    // Show "Compile Required" dialog
    return showCompileDialog(rubricId);
  }
  
  if (rubric.needs_recompilation) {
    // Warn user about stale contract
    const proceed = await confirmStaleContract();
    if (!proceed) return;
  }
  
  return api.gradeOntology({ rubric_id: rubricId, ... });
}
```

### 2. Handle Warnings During Compilation

```typescript
async function compileRubric(rubricId: string) {
  let response = await api.compileRubric(rubricId, { acknowledged_warning_ids: [] });
  
  if (response.status === 'warnings_require_acknowledgment') {
    // Show warnings to teacher
    const acknowledged = await showWarningsDialog(response.warnings);
    
    if (acknowledged.length > 0) {
      response = await api.compileRubric(rubricId, { 
        acknowledged_warning_ids: acknowledged.map(w => w.id) 
      });
    }
  }
  
  return response;
}
```

### 3. Poll Batch Progress

```typescript
async function watchBatchProgress(batchId: string, onProgress: (p: BatchProgress) => void) {
  const pollInterval = 2000; // 2 seconds
  
  while (true) {
    const progress = await api.getBatchProgress(batchId);
    onProgress(progress);
    
    if (progress.status === 'completed' || progress.status === 'failed') {
      break;
    }
    
    await sleep(pollInterval);
  }
}
```

### 4. Display Flagged Outcomes

Flagged outcomes need teacher review. Show them prominently:

```typescript
function renderGradedTest(draft: GradedTestDraft) {
  const needsReview = draft.flagged_outcomes.length > 0;
  
  return (
    <div className={needsReview ? 'needs-review' : ''}>
      {needsReview && (
        <Banner type="warning">
          {draft.flagged_outcomes.length} items need your review
        </Banner>
      )}
      
      {draft.question_outcomes.map(qo => (
        <QuestionResult 
          key={qo.question_id}
          outcome={qo}
          flagged={draft.flagged_outcomes.filter(f => f.question_id === qo.question_id)}
        />
      ))}
    </div>
  );
}
```

### 5. Use Decimal Strings Correctly

All point values are strings (for decimal precision). Convert for display:

```typescript
function formatPoints(points: string): string {
  const num = parseFloat(points);
  return num % 1 === 0 ? num.toString() : num.toFixed(2);
}

// Display: "85/100" not "85.00/100.00"
<span>{formatPoints(outcome.points_earned)}/{formatPoints(outcome.points_possible)}</span>
```

---

## Endpoint Summary

### Rubric Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/grading/extract_rubric_docx` | Extract from DOCX |
| POST | `/rubrics/save_ontology_draft` | Save draft |
| PUT | `/rubrics/{id}/draft` | Update draft |
| POST | `/rubrics/{id}/compile` | Compile to contract |
| GET | `/rubrics/{id}` | Get rubric details |
| GET | `/rubrics` | List rubrics |

### Grading

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/grading/grade_ontology` | Grade single student |
| POST | `/grading/grade_ontology_batch` | Grade batch |
| GET | `/grading/batches/{id}/progress` | Batch progress |

### Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/grading/sessions/{id}` | Session details |
| POST | `/grading/sessions/{id}/resume` | Resume session |
| DELETE | `/grading/sessions/{id}` | Cancel session |

---

## Changelog

- **v1.0** (2026-02-04): Initial release with ontology support

