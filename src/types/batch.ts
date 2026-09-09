/**
 * TypeScript mirrors of S11 batch grading backend schemas.
 * All Decimal-valued fields (scores) are serialized as strings by the backend.
 */

import type { AnswerSpaceSelectionGroup, TranscriptionDraft } from './transcription'
import type { components } from '../lib/api-types'

// ---------------------------------------------------------------------------
// Shared sub-types
// ---------------------------------------------------------------------------

/** Flag triage result for a single transcription. */
export interface FlagVerdictResponse {
  review_needed: boolean
  /** Subset of: "unparseable" | "grounding_retry" | "low_confidence" | "low_logprob_span"
   *  | "missing_answers" | "segmentation_mismatch"
   *  | "student_unassigned" | "student_unmatched"
   *  (NOT "code_lint" — retired as a triage reason 2026-09-06; it survives as
   *  an INFO annotation rendered by review-flags.ts as an answer-level badge.) */
  reasons: string[]
}

/** Per-test item in the batch detail / transcription-review payload. */
export interface BatchTranscriptionItem {
  transcription_id: string
  filename: string | null
  transcription_status: 'transcribed' | 'approved'
  /** Row insert time (ISO) — drives the Δ15 progress-based residue horizon. */
  created_at: string
  draft: TranscriptionDraft
  /** Teacher review overlay (review_json), if saved — GENERATED wire type (OD-9). */
  review: components['schemas']['TranscriptionReview'] | null
  student_name_suggestion: string | null
  matched_student_id: string | null     // pre-computed normalized-exact match
  matched_student_name: string | null
  flag_verdict: FlagVerdictResponse
  /** B6: the FROZEN contract's answers — present only when approved; the
   *  read-only review hydrates from these, never from the draft. */
  approved_answers?: GradeAnswerInputItem[] | null
  // Populated once a GradedTest row exists:
  graded_test_id: string | null
  graded_test_status: string | null
  total_score: string | null
  total_possible: string | null
}

/** One in-flight document (B3) — feeds the dashboard's transcribing ghosts. */
export interface ActiveJobItem {
  filename: string | null
  state: 'queued' | 'running'
  created_at: string
  started_at: string | null
  attempt_count: number
}

/** Live pipeline counts — derived at query time, never stored. */
export interface BatchRollup {
  /** [Stage A, migration 025] The UPLOAD stage, one step before `transcribing`:
   *  files she declared that have not landed yet. 0 for every legacy batch
   *  (no declaration) and for every batch created by a client that predates
   *  the declaration — which is what makes this field additive. */
  uploading: number
  /** [Stage A, R9] Declared, never arrived, and the batch has been silent past
   *  the backstop TTL. Counted as DEAD so the batch reaches a terminal status
   *  instead of an eternal "in progress" when she closes the tab mid-upload.
   *  Mutually exclusive with `uploading`. */
  not_received: number
  transcribing: number           // VLM calls in-flight
  transcribed: number            // awaiting transcription review
  /** Ruling 1: the flagged-or-touched subset of `transcribed` — exactly
   *  what accept_clean refuses. `transcribed - needs_eyes` is the
   *  bulk-acceptable remainder.
   *  NULL = not computable for this batch (corrupt rubric contract). The
   *  display degrades by OMISSION: render the coarser merged truth for that
   *  row, never a confidently wrong number. */
  needs_eyes: number | null
  approved_transcription: number // queued for grading
  grading: number                // pending/grading
  draft: number                  // awaiting grade review
  approved: number               // fully approved
  failed: number
  /** Ledgered transcription failures (migration 015) — dead, not in flight. */
  transcription_failed: number
  total: number
}

/** One failed batch document. Cloud Tasks batches source these from failed
 *  TranscriptionJob rows (job_id present ⇒ one-click retry, no re-upload);
 *  legacy pre-016 batches from the read-only ledger (job_id null). */
export interface TranscriptionFailureItem {
  filename: string | null
  error: string
  at: string
  net_verdict: string | null
  job_id?: string | null
}

// ---------------------------------------------------------------------------
// Response shapes
// ---------------------------------------------------------------------------

export interface BatchDetailResponse {
  id: string
  name: string | null
  rubric_id: string
  class_id: string | null
  /** B4: display names, resolved server-side. */
  rubric_name?: string | null
  class_name?: string | null
  status: string
  started_at: string | null
  completed_at: string | null
  created_at: string
  rollup: BatchRollup
  transcriptions: BatchTranscriptionItem[]
  /** B3: queued/running documents in doc_priority order (post-reap). */
  active_jobs?: ActiveJobItem[]
  /** Rubric selection groups in answer space (batch-level; [] when
   *  selection-free). The review surface collapses expected-empty containers. */
  selection_groups?: AnswerSpaceSelectionGroup[]
  /**
   * S12 grade-review feed (spec §1.5). Typed HERE rather than cast at the call
   * site: an `as unknown as {...}` in the dashboard hid the fact that these had
   * never been added, so a wire rename would have made the whole section vanish
   * with a green typecheck and no error anywhere.
   */
  graded_tests?: BatchGradedItem[]
  eta?: BatchEta | null
  audit_status?: string
  appendix_include_criteria?: boolean
  stamp_position_default?: { corner?: string | null; x?: number | null; y?: number | null } | null
  /** Durable per-document failure records — rendered as failed cards
   *  instead of an eternal "מתמלל" spinner. */
  transcription_failures?: TranscriptionFailureItem[]
}

export interface BatchListItem {
  id: string
  name: string | null
  rubric_id: string
  class_id: string | null
  /** B4: display names (batch-fetched server-side). */
  rubric_name?: string | null
  class_name?: string | null
  status: string
  created_at: string
  rollup: BatchRollup
}

export interface BatchCreateResponse {
  batch_id: string
  test_count: number
}

// ---------------------------------------------------------------------------
// Request types (for API client)
// ---------------------------------------------------------------------------

export interface AcceptCleanItem {
  transcription_id: string
  student_id: string
}

export interface GradeAnswerInputItem {
  question_number: number
  sub_question_id: string | null
  answer_text: string
}

// ---------------------------------------------------------------------------
// Flag reason labels (for UI display)
// ---------------------------------------------------------------------------

export const FLAG_REASON_LABELS: Record<string, string> = {
  unparseable: 'תוכן לא קריא',
  grounding_retry: 'חוסר עקביות בזיהוי',
  low_confidence: 'ביטחון נמוך בתמלול',
  low_logprob_span: 'אי-ודאות לשונית',
  missing_answers: 'תשובות חסרות',
  segmentation_mismatch: 'חשד לשיוך שגוי',
  // Two distinct student facts (2026-08-12, owner-ruled copy): a name WAS
  // extracted but no such student exists yet vs. no name found at all.
  student_unassigned: 'תלמיד חדש - טרם נוצר',
  student_unmatched: 'שם תלמיד לא זוהה',
}

/** One graded test on the batch feed (spec §1.5). */
export interface BatchGradedItem {
  graded_test_id: string
  student_id?: string | null
  student_name?: string | null
  status: string
  version?: number
  landed_at?: string | null
  opened_at?: string | null
  total_awarded?: string | null
  /** null = NOT computable (an unparseable draft), never zero. */
  look_count?: number | null
  audit_touched?: string
  returned_exam_state?: string
  /** Relative path — usable only through the api seam (see fetchPageImageObjectUrl). */
  page1_image_url?: string | null
}

/** How long until she can start reviewing (spec §1.5). */
export interface BatchEta {
  kind: 'first_landing' | 'remaining' | 'unknown' | string
  seconds?: number | null
}
