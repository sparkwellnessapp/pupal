/**
 * TypeScript mirrors of S11 batch grading backend schemas.
 * All Decimal-valued fields (scores) are serialized as strings by the backend.
 */

import type { TranscriptionDraft } from './transcription'

// ---------------------------------------------------------------------------
// Shared sub-types
// ---------------------------------------------------------------------------

/** Flag triage result for a single transcription. */
export interface FlagVerdictResponse {
  review_needed: boolean
  /** Subset of: "unparseable" | "grounding_retry" | "low_confidence" | "low_logprob_span" | "student_unmatched" */
  reasons: string[]
}

/** Per-test item in the batch detail / transcription-review payload. */
export interface BatchTranscriptionItem {
  transcription_id: string
  filename: string | null
  transcription_status: 'transcribed' | 'approved'
  draft: TranscriptionDraft
  student_name_suggestion: string | null
  matched_student_id: string | null     // pre-computed normalized-exact match
  matched_student_name: string | null
  flag_verdict: FlagVerdictResponse
  // Populated once a GradedTest row exists:
  graded_test_id: string | null
  graded_test_status: string | null
  total_score: string | null
  total_possible: string | null
}

/** Live pipeline counts — derived at query time, never stored. */
export interface BatchRollup {
  transcribing: number           // VLM calls in-flight
  transcribed: number            // awaiting transcription review
  approved_transcription: number // queued for grading
  grading: number                // pending/grading
  draft: number                  // awaiting grade review
  approved: number               // fully approved
  failed: number
  total: number
}

// ---------------------------------------------------------------------------
// Response shapes
// ---------------------------------------------------------------------------

export interface BatchDetailResponse {
  id: string
  name: string | null
  rubric_id: string
  class_id: string | null
  status: string
  started_at: string | null
  completed_at: string | null
  created_at: string
  rollup: BatchRollup
  transcriptions: BatchTranscriptionItem[]
}

export interface BatchListItem {
  id: string
  name: string | null
  rubric_id: string
  class_id: string | null
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
  student_unmatched: 'שם תלמיד לא זוהה',
}
