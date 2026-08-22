/**
 * segmentation-check — LIVE marker↔key mismatch detection (2026-08-07).
 *
 * Mirror of backend app/services/transcription/segmentation_check.py — the
 * SAME conservative grammar, cross-pinned by tests sharing fixture strings
 * (change a rule in one, change it in both + both test files).
 *
 * Why a client mirror exists (the Δ6 exception, deliberately): the backend
 * annotation is static, but the teacher MOVES text between containers to fix
 * a mislabel — after a swap, static annotations describe the wrong content.
 * Recomputing against the CURRENT editor text keeps banners and proposals
 * truthful through a whole reassignment chain, exactly like `[?]` flags
 * tracking live content (Δ7). The backend annotation remains the triage
 * signal and the permanent record.
 *
 * The assigned key is the GRADING route; detection never remaps anything —
 * it feeds the banner + the proposed swap the teacher confirms.
 */

// Hebrew ordinals א..י — the same vocabulary the backend keys module speaks.
const HEB = 'אבגדהוזחטי'
const MAX_MARKER_LEN = 12

const Q_WORD = new RegExp(`^שאלה\\s*(\\d{1,2})\\s*[:.]?$`)
const LETTER_PAREN_DIGIT = new RegExp(`^([${HEB}])\\)\\s*(\\d{1,2})$`)
const DIGIT_PAREN_LETTER = new RegExp(`^(\\d{1,2})\\s*\\(\\s*([${HEB}])$`)
const SUB_ONLY = new RegExp(`^([${HEB}])\\s*[).:]$`)

export interface DeclaredMarker {
  question: number | null
  sub: string | null
}

export interface AnswerKey {
  question_number: number
  sub_question_id: string | null
}

export interface SegmentationMismatch {
  /** What the student's leading ink declares. */
  declaredQuestion: number
  /** Existing draft key to swap with, or null when no target exists:
   *  (declared, same sub) → (declared, declared sub) → bare (declared, null). */
  proposedTarget: AnswerKey | null
}

function parseMarkerLine(line: string): DeclaredMarker | null {
  const s = line.trim()
  if (!s || s.length > MAX_MARKER_LEN) return null
  let m = Q_WORD.exec(s)
  if (m) return { question: parseInt(m[1], 10), sub: null }
  m = LETTER_PAREN_DIGIT.exec(s)
  if (m) return { question: parseInt(m[2], 10), sub: m[1] }
  m = DIGIT_PAREN_LETTER.exec(s)
  if (m) return { question: parseInt(m[1], 10), sub: m[2] }
  m = SUB_ONLY.exec(s)
  if (m) return { question: null, sub: m[1] }
  return null
}

/** The block's self-declared identity: up to the first two non-empty lines,
 *  stopping at the first non-marker line. First finding wins per field. */
export function parseLeadingMarker(text: string): DeclaredMarker {
  let question: number | null = null
  let sub: string | null = null
  let seen = 0
  for (const line of text.split('\n')) {
    if (!line.trim()) continue
    const marker = parseMarkerLine(line)
    if (marker === null) break
    question = question ?? marker.question
    sub = sub ?? marker.sub
    seen += 1
    if (seen >= 2) break
  }
  return { question, sub }
}

const sameKey = (a: AnswerKey, b: AnswerKey): boolean =>
  a.question_number === b.question_number && (a.sub_question_id ?? null) === (b.sub_question_id ?? null)

/**
 * Live mismatch for ONE answer against its current editor text.
 * `allKeys` is the draft's full (frozen) key set — proposal resolution needs it.
 */
export function detectMismatch(
  currentText: string,
  assigned: AnswerKey,
  allKeys: AnswerKey[],
): SegmentationMismatch | null {
  const marker = parseLeadingMarker(currentText)
  if (marker.question === null || marker.question === assigned.question_number) return null

  const candidates: AnswerKey[] = [
    { question_number: marker.question, sub_question_id: assigned.sub_question_id ?? null },
    { question_number: marker.question, sub_question_id: marker.sub },
    { question_number: marker.question, sub_question_id: null },
  ]
  let proposedTarget: AnswerKey | null = null
  for (const c of candidates) {
    if (allKeys.some((k) => sameKey(k, c)) && !sameKey(c, assigned)) {
      proposedTarget = c
      break
    }
  }
  return { declaredQuestion: marker.question, proposedTarget }
}

/** Display label for a key: "שאלה 3 סעיף א" / "שאלה 5". */
export function keyLabel(key: AnswerKey): string {
  return key.sub_question_id
    ? `שאלה ${key.question_number} סעיף ${key.sub_question_id}`
    : `שאלה ${key.question_number}`
}
