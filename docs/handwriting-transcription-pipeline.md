# Handwriting Transcription Pipeline — Technical Documentation

> **Scope:** Everything that happens from the moment a teacher uploads a student PDF on the
> Transcription screen until the `TranscriptionDraft` is rendered in
> `TranscriptionReviewPanel.tsx` and the teacher can submit for grading.
>
> **Key files:**
> | Layer | File |
> |---|---|
> | API endpoint | `backend/app/api/v0/transcription.py` |
> | Pipeline orchestrator | `backend/app/services/transcribe_one.py` |
> | VLM transcription engine | `backend/app/services/handwriting_transcription_service.py` |
> | Draft builder (adapter) | `backend/app/services/transcription_adapter.py` |
> | Domain schemas | `backend/app/schemas/transcription.py` |
> | Frontend types | `frontend/src/types/transcription.ts` |
> | Review UI | `frontend/src/components/TranscriptionReviewPanel.tsx` |

---

## 1. Overview — Pipeline at a glance

```
Teacher uploads PDF
        │
        ▼
POST /api/v0/transcriptions/transcribe
  │ Auth + ownership + rubric-compiled guard
  │
  ▼
transcribe_one()               ← background-safe orchestrator
  │
  ├── HandwritingTranscriptionService.transcribe_pdf()
  │     │
  │     ├── pdf_to_images()       PDF → [PIL.Image] at 200 DPI
  │     │
  │     └── _transcribe_all_pages()
  │           │
  │           ├── [parallel] _transcribe_page_grounded()   × N pages
  │           │       ├── VLM call (GROUNDED_SYSTEM_PROMPT + GROUNDED_TRANSCRIPTION_PROMPT)
  │           │       │   with logprobs (OpenAI only)
  │           │       ├── _parse_json()
  │           │       ├── _verify_consistency()
  │           │       └── (retry) _retry_with_forced_grounding()
  │           │
  │           └── _merge_grounded_results()  → TranscriptionResult
  │
  ├── pdf_to_images() at 72 DPI  (page count only)
  ├── gcs.upload_bytes()         persist PDF to GCS
  ├── build_transcription_draft()  TranscriptionResult → TranscriptionDraft
  └── INSERT transcriptions row
        │
        ▼
  returns transcription_id
        │
        ▼
API reloads row, returns TranscribeResponse { transcription_id, draft }
        │
        ▼
TranscriptionReviewPanel.tsx
  ├── renders answers (editable)
  ├── renders annotation banners
  ├── lazy-loads per-page thumbnails (GET /{id}/pages/{n})
  └── teacher submits → POST /grade
```

---

## 2. Step 1 — HTTP request arrives at `POST /transcribe`

**File:** `backend/app/api/v0/transcription.py` · `transcribe()` handler

### 2.1 Guards (run in request context)

| Check | Error | Reason |
|---|---|---|
| `Depends(get_current_user)` | 401 | All domain endpoints require auth |
| `get_owned_or_404(db, Rubric, rubric_id, current_user.id)` | 404 | Cross-tenant isolation — 404, not 403 |
| `rubric.is_compiled` | 400 | Only a compiled rubric (i.e. a Contract) can be graded against |
| `file.filename.endswith(".pdf")` | 400 | VLM pipeline is PDF-only |
| `pdf_bytes` non-empty | 400 | Guard against empty upload |

### 2.2 Delegation

Once guards pass, the handler calls `transcribe_one()` and then reloads the
persisted row to build the response:

```python
transcription_id = await transcribe_one(
    pdf_bytes=pdf_bytes,
    filename=file.filename,
    rubric_id=rubric_id,
    user_id=current_user.id,
    batch_id=None,               # None = single-test mode
)
# reload from DB (transcribe_one commits its own session)
transcription = await db.get(Transcription, UUID(transcription_id))
draft = TranscriptionDraft.model_validate(transcription.draft_json)
return TranscribeResponse(transcription_id=transcription_id, draft=draft)
```

The heavy work (VLM calls, GCS, DB write) runs inside `transcribe_one`'s own
`AsyncSession`, making the function safe to enqueue as a background task for
the batch path (`batch_id` set) without capturing the request-scoped session.

---

## 3. Step 2 — `transcribe_one()` orchestrates the full pipeline

**File:** `backend/app/services/transcribe_one.py`

`transcribe_one` owns the end-to-end lifecycle for one PDF:

```
1. Open a new AsyncSession (independent of the request session)
2. Fetch the Rubric row to confirm it exists
3. Build the VLM provider from settings
4. Call HandwritingTranscriptionService.transcribe_pdf()   [blocking → threadpool]
5. Compute page_count at 72 DPI                             [blocking → threadpool]
6. Upload the raw PDF to GCS
7. Call build_transcription_draft()  → TranscriptionDraft
8. INSERT Transcription row, commit
9. Return transcription_id
```

### 3.1 VLM provider selection

```python
provider = get_vlm_provider(
    settings.transcription_vlm_provider,    # e.g. "async_openai"
    **({"model": settings.transcription_vlm_model}
       if settings.transcription_vlm_model else {}),
)
```

`get_vlm_provider()` is a factory in `handwriting_transcription_service.py`
returning one of: `OpenAIProvider`, `AsyncOpenAIProvider`, `AnthropicProvider`,
`GoogleProvider`. The `AsyncOpenAIProvider` is preferred for production — its
native async client allows `asyncio.wait_for()` to truly cancel an in-flight
HTTP request rather than just abandoning a thread.

### 3.2 Running blocking I/O in the thread pool

FastAPI's event loop must not block on CPU-intensive or synchronous-I/O
operations. Both the VLM call (synchronous SDK) and `pdf_to_images` (PIL +
poppler) are wrapped with `run_in_threadpool`:

```python
result = await run_in_threadpool(
    service.transcribe_pdf,
    pdf_bytes,
    filename or "upload.pdf",
)
```

### 3.3 GCS storage

The original PDF is stored durably before any grading happens. The path
convention is:

```
transcriptions/{user_id}/{uuid4}.pdf
```

The `gcs_uri` (`gs://bucket/path`) and `gcs_object_path` are stored on the
`Transcription` row to support the on-demand page-thumbnail API (§7).

### 3.4 The `Transcription` row

```python
Transcription(
    user_id=user_id,
    rubric_id=rubric_id,
    batch_id=batch_id,          # None for single-test
    student_id=None,            # filled at /grade
    student_name=None,          # filled at /grade
    gcs_uri=gcs_uri,
    gcs_bucket=...,
    gcs_object_path=object_path,
    filename=filename,
    draft_json=draft.model_dump(mode="json"),
    contract_json=None,         # filled at /grade
    status="transcribed",
)
```

The `draft_json` JSONB column stores the complete `TranscriptionDraft` (§5).
`contract_json` is filled only after teacher approval at `POST /grade`.

---

## 4. Step 3 — `HandwritingTranscriptionService` runs the VLM

**File:** `backend/app/services/handwriting_transcription_service.py`

### 4.1 PDF → images

```python
images = pdf_to_images(pdf_bytes, dpi=200)          # poppler via pdf2image
images_b64 = [image_to_base64(img) for img in images]
```

`image_to_base64()` applies `enhance_for_transcription()` before encoding:

| Enhancement step | Parameter | Purpose |
|---|---|---|
| `ImageOps.autocontrast(cutoff=1)` | — | Stretch histogram, improve dynamic range |
| `ImageEnhance.Contrast` | `1.4×` | Make dark handwriting stand out |
| `ImageEnhance.Sharpness` | `1.3×` | Sharper character edges |
| `ImageEnhance.Brightness` | `1.05×` | Push background toward white |

Images are capped at `max_size=2000` px on the longest dimension (LANCZOS
resampling) before base64 encoding. Higher resolution is kept here than in the
preview service because transcription accuracy is sensitive to image quality.

### 4.2 Parallel per-page transcription (`_transcribe_all_pages`)

```python
with ThreadPoolExecutor(max_workers=min(len(images_b64), 5)) as executor:
    page_results = list(executor.map(process_page, enumerate(images_b64)))
```

Up to 5 pages are transcribed concurrently. Each page is an independent VLM
call — there is no inter-page context sharing at this stage (merging happens in
§4.5). Parallelism reduces wall-clock latency from `O(N)` to `O(⌈N/5⌉)` for a
5-page exam.

### 4.3 Single-page grounded transcription (`_transcribe_page_grounded`)

Each page goes through a **two-phase structured prompt**:

#### Phase 1 — Visual grounding (forces identification before transcription)

The VLM is asked to fill `visual_grounding` first:
```json
{
  "visual_grounding": {
    "class_name": "exact word written after 'class'",
    "method_names": ["..."],
    "field_names": ["..."],
    "approximate_lines": 42
  }
}
```

This prevents confabulation: by committing to what is *physically visible*
before copying code, the model cannot silently substitute a "logically expected"
class name for what the student actually wrote.

#### Phase 2 — Character-level transcription

The prompt then requires `transcription.answers[]` where each answer's
`answer_text` *must* match the `visual_grounding.class_name`. Key rules enforced
in the system prompt (`GROUNDED_SYSTEM_PROMPT`):

- Transcribe bugs as written — `if (x = 5)` stays `if (x = 5)`
- Use `[?]` for illegible characters — never guess
- Preserve exact indentation and blank lines
- Do not include Hebrew section headers (`שאלה 1`, `סעיף א`) in `answer_text`

#### Logprobs (OpenAI provider only)

If the provider exposes `transcribe_images_with_logprobs()`, the call also
returns per-token logprobs. A **sliding-window span-min** is computed:

```python
@staticmethod
def _compute_min_span_logprob(token_logprobs, window=5):
    return min(
        min(token_logprobs[i: i + window])
        for i in range(len(token_logprobs) - window + 1)
    )
```

The span-min captures the worst contiguous 5-token window — a more sensitive
signal for local hallucination than the average logprob. The value is stored on
the result dict as `_min_span_logprob` and later promoted to each
`TranscribedAnswer.min_span_logprob`.

### 4.4 Consistency verification and retry

After parsing, `_verify_consistency()` cross-checks the two phases:

| Check | Condition | Action |
|---|---|---|
| Class name | `class X` in transcription ≠ `visual_grounding.class_name` | mismatch |
| Method coverage | < 50% of identified methods appear in code | mismatch |
| Field coverage | < 50% of identified fields appear in code | mismatch |
| LHS hallucination | `this.X` where `X` not in identified fields | mismatch |
| RHS hallucination | `this.X = Y` where `Y` not in fields/params/literals | mismatch |

On mismatch, `_retry_with_forced_grounding()` issues a **second VLM call** at
`temperature=0.0` with the identified class name injected explicitly into the
prompt, anchoring the retry to the grounding pass.

The retry is flagged: `result["_needed_grounding_retry"] = True` → this
propagates to `TranscribedAnswer.needed_grounding_retry` → becomes a
`vlm_uncertainty` annotation (§5.2).

### 4.5 Merging page results (`_merge_grounded_results`)

Answers from different pages for the same `(question_number, sub_question_id)`
are concatenated. The final `TranscribedAnswer` per question captures:

| Field | Value |
|---|---|
| `answer_text` | `"\n".join(parts)` across all pages |
| `confidence` | `min(confidences)` — most conservative |
| `page_numbers` | sorted union of contributing pages |
| `needed_grounding_retry` | `any(parts)` |
| `min_span_logprob` | `min(span_mins)` — worst-case across pages |

The output is a `TranscriptionResult`:
```python
@dataclass
class TranscriptionResult:
    student_name: str        # extracted from page or from filename
    filename: str
    answers: List[TranscribedAnswer]
```

---

## 5. Step 4 — `build_transcription_draft()` converts signals to the domain schema

**File:** `backend/app/services/transcription_adapter.py`

This is a **pure function** — no I/O, no side effects. It translates the
service's output (`TranscriptionResult`) into the domain schema
(`TranscriptionDraft`) and derives teacher-facing annotations from the
service's signals.

### 5.1 Answer mapping

```python
TranscriptionDraftAnswer(
    question_number=ans.question_number,
    sub_question_id=ans.sub_question_id,
    answer_text=ans.answer_text,
    confidence=ans.confidence,
    page_numbers=ans.page_numbers,
)
```

### 5.2 Annotation derivation

| Signal | Annotation type | Severity | Message |
|---|---|---|---|
| `[?]` in `answer_text` | `vlm_unparseable` | WARNING | "חלקים מהתשובה לא היו קריאים בתמלול" |
| `needed_grounding_retry=True` | `vlm_uncertainty` | WARNING | "התמלול של שאלה זו דרש אימות נוסף — מומלץ לבדוק מול המקור" |
| `confidence < 0.7` (and no retry flag) | `vlm_uncertainty` | INFO | "רמת ביטחון נמוכה בתמלול" |
| `min_span_logprob < settings.logprob_span_threshold` | `vlm_low_logprob` | WARNING | "זוהתה אי-ודאות בתמלול — מומלץ לבדוק מול המקור" |
| `student_name` is falsy | `student_name_missing` | INFO | "לא זוהה שם תלמיד — נא לבחור תלמיד" |

The logprob annotation is scoped to `target_id="transcription"` (global banner).
Answer-level annotations are scoped to `target_id="q{n}"` or `"q{n}.{sub}"`.

### 5.3 `TranscriptionDraft` schema

```python
class TranscriptionDraft(BaseModel):
    schema_version: str = "1.0"
    student_name_suggestion: Optional[str]     # VLM guess — hint only
    page_count: int
    answers: List[TranscriptionDraftAnswer]
    annotations: List[TranscriptionAnnotation]
    model_version: Optional[str]               # "provider/model"
    transcription_duration_ms: Optional[int]
```

This schema is stored verbatim in `transcriptions.draft_json` (JSONB) and is
**immutable after INSERT** — it is a historical record of what the VLM produced
before any teacher edits.

---

## 6. Step 5 — Response serialization

Back in `transcription.py`, the API handler reloads the committed row and
returns:

```python
# Backend Pydantic model
class TranscribeResponse(BaseModel):
    transcription_id: str
    draft: TranscriptionDraft
```

The frontend mirrors this shape:

```typescript
// frontend/src/types/transcription.ts
export interface TranscribeResponse {
    transcription_id: string;
    draft: TranscriptionDraft;
}
```

The `TranscriptionDraft` → `TranscribeResponse` journey is:

```
TranscriptionResult (dataclass, service layer)
    └─► build_transcription_draft()  (adapter)
            └─► TranscriptionDraft (Pydantic, persisted as JSONB)
                    └─► TranscribeResponse (API response model, serialized to JSON)
                            └─► TranscribeResponse (TypeScript interface, browser)
```

---

## 7. Step 6 — On-demand page thumbnails

**Endpoint:** `GET /api/v0/transcriptions/{transcription_id}/pages/{page_number}`

The review panel does **not** receive page images in the initial response.
Images are fetched lazily as the teacher navigates between pages. This keeps the
initial response small and avoids rendering pages the teacher may never visit.

```python
@router.get("/{transcription_id}/pages/{page_number}")
async def get_transcription_page(...) -> TranscriptionPageResponse:
    # 1. Ownership guard
    # 2. Range check from draft_json.page_count (no GCS needed)
    # 3. Download PDF from GCS
    # 4. Render requested page at PAGE_RENDER_DPI = 150
    # 5. Return base64 thumbnail
```

The render DPI here (`150`) is lower than the transcription DPI (`200`) because
display thumbnails do not need the same fidelity as OCR input.

```typescript
export interface TranscriptionPageResponse {
    page_number: number;
    thumbnail_base64: string;
}
```

---

## 8. Step 7 — `TranscriptionReviewPanel.tsx` renders the draft

**File:** `frontend/src/components/TranscriptionReviewPanel.tsx`

### 8.1 Layout

The panel is a full-viewport two-pane layout:

```
┌──────────────────────────────────────────────────────────────┐
│  Header: back button │ mobile tab switcher │ page count       │
├───────────────────────────────┬──────────────────────────────┤
│  Answers pane (right in RTL)  │  Source pane (left in RTL)   │
│                               │                              │
│  Global annotation banners    │  ◄ prev  עמוד 1 / 3  next ► │
│                               │                              │
│  Student picker               │  [page image]                │
│    └─ name suggestion hint    │                              │
│                               │                              │
│  Per-answer cards:            │                              │
│    question label + page ref  │                              │
│    per-answer annotations     │                              │
│    editable textarea          │                              │
│                               │                              │
│  [Back]   [שלח לבדיקה]       │                              │
└───────────────────────────────┴──────────────────────────────┘
```

On mobile, the two panes become tabs ("תשובות" / "מקור").

### 8.2 State

```typescript
const [editedAnswers, setEditedAnswers] =
    useState<Record<string, string>>(
        Object.fromEntries(draft.answers.map(a => [answerKey(a), a.answer_text]))
    );
const [studentId, setStudentId] = useState<string | null>(null);
const [selectedPage, setSelectedPage] = useState<number>(
    () => draft.answers[0]?.page_numbers?.[0] ?? 1
);
const [pageCache, setPageCache] = useState<Record<number, string>>({});
```

`answerKey` produces stable string keys for the edited-answers map:
- No sub-question: `"q1"`, `"q2"`, …
- With sub-question: `"q1.א"`, `"q1.ב"`, …

The initial page is set to the first page referenced by the first answer, so the
source view opens pre-scrolled to where the student started writing.

### 8.3 Lazy page loading

```typescript
const fetchPage = useCallback(async (pageNumber: number) => {
    if (pageCache[pageNumber]) {
        setSelectedPage(pageNumber);
        return;                            // cache hit — no network call
    }
    setLoadingPage(true);
    const result = await getTranscriptionPage(transcription_id, pageNumber);
    setPageCache(prev => ({ ...prev, [pageNumber]: result.thumbnail_base64 }));
    setSelectedPage(pageNumber);
}, [pageCache, transcription_id, draft.page_count]);

// Load page 1 on mount
useEffect(() => { void fetchPage(selectedPage); }, []);
```

The page cache is component-local (not persisted). Each unique page is fetched
at most once per session. Clicking a page-number button on an answer card calls
`fetchPage(a.page_numbers[0])`, scrolling the source view to that answer's
origin page.

### 8.4 Annotation rendering

```typescript
const globalAnnotations = draft.annotations.filter(
    ann => ann.target_id === 'transcription'
);
const annotationsFor = (key: string) =>
    draft.annotations.filter(ann => ann.target_id === key);
```

Global annotations (e.g. `vlm_low_logprob`, `student_name_missing`) render as
a stack of `<AnnotationBanner>` components above the student picker.
Per-answer annotations render inside the answer card, between the question
header and the editable textarea. The `AnnotationBanner` applies severity-based
colour classes:

| Severity | CSS classes |
|---|---|
| `error` | `bg-red-50 border-red-300 text-red-800` |
| `warning` | `bg-amber-50 border-amber-300 text-amber-800` |
| `info` | `bg-blue-50 border-blue-300 text-blue-700` |

### 8.5 Submit flow

The "שלח לבדיקה" button is disabled until a student is selected. On click:

```typescript
const handleSubmit = async () => {
    if (!studentId) return;
    const answers: GradeAnswerInput[] = draft.answers.map(a => ({
        question_number: a.question_number,
        sub_question_id: a.sub_question_id,
        answer_text: editedAnswers[answerKey(a)] ?? a.answer_text,
    }));
    await onSubmit(answers, studentId);  // → POST /grade
};
```

The submitted `answers` array reflects any teacher edits made in the textareas.
The teacher's edited text (not the original VLM output) becomes the
`TranscriptionContract` — the frozen input to the grading agent.

---

## 9. Data flow summary — types across layers

```
bytes (PDF)
    │  pdf_to_images() @ 200 DPI + enhance_for_transcription()
    ▼
List[PIL.Image]
    │  image_to_base64()
    ▼
List[str]  (base64 PNG)
    │  VLM call (GROUNDED_SYSTEM_PROMPT + GROUNDED_TRANSCRIPTION_PROMPT)
    ▼
str  (raw JSON response from VLM)
    │  _parse_json() → _verify_consistency() → (optional retry)
    ▼
Dict[str, Any]  { visual_grounding: {...}, transcription: {...} }
    │  _merge_grounded_results()
    ▼
TranscriptionResult (dataclass)
    │  build_transcription_draft()
    ▼
TranscriptionDraft (Pydantic, frozen in JSONB)
    │  HTTP JSON response
    ▼
TranscriptionDraft (TypeScript interface)
    │  TranscriptionReviewPanel props
    ▼
Rendered review UI + teacher edits
    │  handleSubmit() → onSubmit(answers, studentId)
    ▼
GradeAnswerInput[]  →  POST /grade  →  TranscriptionContract (frozen)
```

---

## 10. Error paths

| Stage | Failure | Behaviour |
|---|---|---|
| File upload | Empty file / not PDF | 400 from the API handler — never reaches VLM |
| Rubric | Not owned / not compiled | 404 / 400 from the API handler |
| VLM call | Provider error / timeout | `transcribe_one` propagates; handler returns 502 "שגיאה בתמלול — נסה שנית" |
| JSON parse failure | VLM returned non-JSON | `_parse_json` returns `{}` → page contributes no answers; logged at ERROR |
| Consistency mismatch | Class name / method drift | One retry at temperature 0 → if still mismatched, `needed_grounding_retry=True` annotation is emitted |
| GCS upload | Network / permission failure | `transcribe_one` raises; handler returns 502 |
| Page thumbnail fetch | GCS error | 502 from the page endpoint; UI shows Hebrew error message, teacher can retry page navigation |
| Submit without student | — | Submit button is disabled; `handleSubmit` returns early if `studentId` is null |

---

## 11. Configuration knobs

All settings live in `app/config.py` / backend `.env`:

| Setting | Default | Effect |
|---|---|---|
| `TRANSCRIPTION_VLM_PROVIDER` | `"openai"` | Which `VLMProvider` class to instantiate |
| `TRANSCRIPTION_VLM_MODEL` | (provider default) | Model name passed to the provider |
| `LOGPROB_SPAN_THRESHOLD` | (configured value) | `min_span_logprob` below this → `vlm_low_logprob` annotation |
| `PAGE_RENDER_DPI` | `150` | DPI for page-thumbnail rendering (display only) |
| Transcription DPI | `200` (hardcoded in service) | DPI for VLM input images |
| `max_workers` | `min(pages, 5)` | Thread pool size for parallel page transcription |

---

## 12. Extension points

- **New VLM provider:** implement `VLMProvider` ABC (`transcribe_images` +
  `name`). Register in `get_vlm_provider()`. For logprob-based confidence, also
  implement `transcribe_images_with_logprobs()`.
- **Page-mapping mode:** pass `question_mappings: List[QuestionMapping]` to
  `transcribe_pdf()` to use `_transcribe_with_mappings()` instead of the
  auto-detect flow. This sends specific pages to the VLM per question rather
  than all pages at once.
- **Annotation types:** add a new `Literal` value to `annotation_type` in both
  `backend/app/schemas/transcription.py` and
  `frontend/src/types/transcription.ts`. Emit the annotation in
  `transcription_adapter.py`. The `AnnotationBanner` component renders any
  annotation type without modification.
