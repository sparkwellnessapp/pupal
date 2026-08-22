/**
 * R1 — reason anchors (pure, zero-mock-tested): each rail chip resolves to
 * the FIRST relevant card in the RENDERED order, the student picker, or a
 * missing target (the chip no-ops with a shake — never scrolls nowhere).
 *
 * Chips are ENTRY-FROZEN (past-tense framing — no live re-verification in
 * v1); anchors read CURRENT text where the rule says so (`unparseable`,
 * `missing_answers`), so a card the teacher already fixed resolves to
 * {kind:'missing'} — the truthful outcome for a stale chip.
 *
 * `orderAnswersPageFirst` is THE rendered order — extracted here so the
 * surface and the anchors can never disagree about "first".
 */
import { answerTargetId } from '@/utils/review-flags'
import {
  expectedEmptyKeys,
  type AnswerSpaceSelectionGroup,
} from '@/utils/selection-expectation'

export interface AnchorAnswer {
  question_number: number
  sub_question_id: string | null
  answer_text: string
  confidence: number
  page_numbers: number[]
}

export type ReasonAnchor =
  | { kind: 'card'; key: string }
  | { kind: 'student' }
  | { kind: 'missing' }

export interface AnchoredReason {
  reason: string
  anchor: ReasonAnchor
}

/** The surface's card order: first page, then question, then sub-question;
 *  unattributed (empty) answers sink to the bottom. */
export function orderAnswersPageFirst<T extends AnchorAnswer>(answers: T[]): T[] {
  return [...answers].sort((a, b) => {
    const pa = a.page_numbers[0] ?? Number.MAX_SAFE_INTEGER
    const pb = b.page_numbers[0] ?? Number.MAX_SAFE_INTEGER
    if (pa !== pb) return pa - pb
    if (a.question_number !== b.question_number) return a.question_number - b.question_number
    return (a.sub_question_id ?? '').localeCompare(b.sub_question_id ?? '')
  })
}

interface AnchorItem {
  draft: {
    answers: AnchorAnswer[]
    annotations: Array<{ annotation_type?: string; target_id?: string } | unknown>
  }
  flag_verdict: { reasons: string[] }
}

const LOW_CONFIDENCE_THRESHOLD = 0.8

export function reasonAnchors(
  item: AnchorItem,
  currentTextByKey: Record<string, string>,
  selectionGroups: AnswerSpaceSelectionGroup[] | undefined | null,
): AnchoredReason[] {
  const ordered = orderAnswersPageFirst(item.draft.answers)
  const keys = new Set(ordered.map((a) => answerTargetId(a)))
  const currentText = (a: AnchorAnswer) =>
    currentTextByKey[answerTargetId(a)] ?? a.answer_text

  const cardOrMissing = (a: AnchorAnswer | undefined): ReasonAnchor =>
    a ? { kind: 'card', key: answerTargetId(a) } : { kind: 'missing' }

  const annotationAnchor = (type: string): ReasonAnchor => {
    for (const ann of item.draft.annotations) {
      const a = ann as { annotation_type?: string; target_id?: string }
      if (a.annotation_type === type && a.target_id && keys.has(a.target_id)) {
        return { kind: 'card', key: a.target_id }
      }
    }
    return { kind: 'missing' }
  }

  return item.flag_verdict.reasons.map((reason): AnchoredReason => {
    switch (reason) {
      case 'student_unassigned':
      case 'student_unmatched':
        return { reason, anchor: { kind: 'student' } }

      case 'code_lint':
      case 'segmentation_mismatch':
        return { reason, anchor: annotationAnchor(reason) }

      case 'unparseable':
        return {
          reason,
          anchor: cardOrMissing(ordered.find((a) => currentText(a).includes('[?]'))),
        }

      case 'missing_answers': {
        const expected = expectedEmptyKeys(
          ordered.map((a) => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id,
            text: currentText(a),
          })),
          selectionGroups ?? [],
        )
        return {
          reason,
          anchor: cardOrMissing(ordered.find(
            (a) => currentText(a).trim() === '' && !expected.has(answerTargetId(a)),
          )),
        }
      }

      case 'low_confidence':
        return {
          reason,
          anchor: cardOrMissing(
            ordered.find((a) => a.confidence < LOW_CONFIDENCE_THRESHOLD),
          ),
        }

      default:
        // Legacy/unknown reasons (grounding_retry, low_logprob_span…): the
        // chip renders, the anchor is honestly absent.
        return { reason, anchor: { kind: 'missing' } }
    }
  })
}
