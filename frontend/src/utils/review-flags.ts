/**
 * deriveReviewFlags — per-line review flags for one answer, derived
 * DETERMINISTICALLY on the client (plan Δ6 respecification + Δ7/Δ17).
 *
 * Sources, in order of trust:
 *  - `[?]` markers: recomputed LIVE against the current editor content —
 *    content-derived and cheap (Δ7).
 *  - `reader_disagreement` annotations (two-phase engine only): the span
 *    offsets in metadata (`char_start`/`char_end`) index the BASELINE PAGE
 *    TEXT, not the answer (backend flagging.py L93-94) — THEY ARE NEVER USED.
 *    The line is located by trimmed-exact match of `metadata.line_quote`
 *    against the DRAFT answer's lines. No fuzzy matching client-side — a
 *    drifting mirror of the backend's `norm_line` is the AnnotationSchema
 *    failure class. A quote that doesn't exact-match degrades to an
 *    answer-level badge (visible, never dropped).
 *  - `code_lint` and other answer-anchored annotations: always answer-level
 *    badges.
 *
 * Dissolution (Δ7, per-answer): span-derived line flags render only while the
 *  answer's editor text is IDENTICAL to the draft text, and once the shell has
 *  marked the answer dissolved they never come back — the teacher editing the
 *  flagged region IS the review the flag requested. (Δ17: the dissolved memory
 *  is session-scoped; after a refresh, flags on text that still equals the
 *  draft render again — truthful, accepted behavior.)
 */

import type { TranscriptionAnnotation } from '@/types/transcription'

export interface ReviewLineFlag {
  /** 1-based line number in the answer text. */
  line: number
  reason: string
}

export interface AnswerReviewFlags {
  lineFlags: ReviewLineFlag[]
  /** Answer-level notices (degraded spans, code_lint, …) — annotation messages. */
  badges: string[]
}

/** The annotation target id for an answer — mirrors backend answer_target. */
export function answerTargetId(a: { question_number: number; sub_question_id: string | null }): string {
  return a.sub_question_id ? `q${a.question_number}.${a.sub_question_id}` : `q${a.question_number}`
}

const UNCLEAR_REASON = 'תו לא ברור בתמלול [?]'

function readerDisagreementReason(ann: TranscriptionAnnotation): string {
  const alts = ann.metadata?.alternatives
  const altText = Array.isArray(alts) && alts.length > 0
    ? (alts as string[]).filter(Boolean).join(' / ')
    : null
  return altText
    ? `קריאה חוזרת זיהתה נוסח שונה: „${altText}”`
    : 'קריאה חוזרת זיהתה נוסח שונה בשורה זו'
}

export function deriveReviewFlags(params: {
  /** Live editor content — `[?]` flags track THIS. */
  currentText: string
  /** The immutable draft answer text — span flags anchor to THIS. */
  draftText: string
  /** Annotations already filtered to this answer's target_id. */
  annotations: TranscriptionAnnotation[]
  /** Δ7 session memory: the shell marked this answer's span flags dissolved. */
  dissolved: boolean
}): AnswerReviewFlags {
  const { currentText, draftText, annotations, dissolved } = params
  const lineFlags: ReviewLineFlag[] = []
  const badges: string[] = []

  // 1. [?] markers — live, per current content (a teacher-typed [?] flags too).
  currentText.split('\n').forEach((line, idx) => {
    if (line.includes('[?]')) lineFlags.push({ line: idx + 1, reason: UNCLEAR_REASON })
  })

  // 2. Annotation-derived flags.
  const spanFlagsActive = !dissolved && currentText === draftText
  const draftLines = draftText.split('\n').map((l) => l.trim())

  for (const ann of annotations) {
    if (ann.annotation_type === 'reader_disagreement') {
      const quote = typeof ann.metadata?.line_quote === 'string'
        ? (ann.metadata.line_quote as string).trim()
        : ''
      const lineIdx = quote ? draftLines.indexOf(quote) : -1
      if (spanFlagsActive && lineIdx !== -1) {
        lineFlags.push({ line: lineIdx + 1, reason: readerDisagreementReason(ann) })
      } else if (spanFlagsActive) {
        // Quote didn't exact-match (backend anchored fuzzily) → badge, not silence.
        badges.push(ann.message)
      }
      // Dissolved / edited: the span flag is gone entirely (Δ7) — the edit IS
      // the review. No badge either; the teacher has been to this answer.
      continue
    }
    // code_lint and any other answer-anchored annotation: answer-level badge.
    badges.push(ann.message)
  }

  lineFlags.sort((a, b) => a.line - b.line)
  return { lineFlags, badges }
}
