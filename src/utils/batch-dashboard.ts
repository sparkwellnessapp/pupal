/**
 * P2 — dashboard selectors (framework-free, zero-mock-tested):
 * D3 selectHeadline (§3.2 precedence, strings via C1) · D2 barSegments ·
 * D6 chip counters · D7 elapsed formatter · D12 poll cadence · D10
 * completion trigger. Components stay thin; every rule lives here.
 */
import {
  HEADLINE_ALL_APPROVED,
  HEADLINE_CLAUSE_SEP,
  HEADLINE_CLEAN_READY,
  HEADLINE_IDENTITY,
  HEADLINE_IDENTITY_TRANSCRIBING_TAIL,
  HEADLINE_LAST_TRANSCRIBING,
  HEADLINE_NEEDS_EYES,
} from '@/copy/batch'
import type { Partition } from '@/utils/batch-partition'
import { answerTargetId } from '@/utils/review-flags'
import {
  expectedEmptyKeys,
  type AnswerSpaceSelectionGroup,
} from '@/utils/selection-expectation'

export interface RollupLike {
  transcribing: number
  transcribed: number
  grading: number
  approved: number
  transcription_failed: number
  total: number
}

interface BatchLike {
  rollup: RollupLike
  active_jobs?: Array<{ state?: string }> | null
}

interface DraftLike {
  answers: Array<{
    question_number: number
    sub_question_id: string | null
    answer_text: string
  }>
}

// ---------------------------------------------------------------------------
// D3 — headline (§3.2 precedence, top-down)
// ---------------------------------------------------------------------------

export function selectHeadline(p: Partition, rollup: RollupLike): string | null {
  // 1. Identity wave: named new students take the stage.
  if (p.identityPills.length > 0) {
    const base = HEADLINE_IDENTITY(p.identityPills.length)
    return rollup.transcribing > 0
      ? base + HEADLINE_IDENTITY_TRANSCRIBING_TAIL
      : base
  }

  // 2. Steady: what's waiting on HER (honesty: touched-clean + unmatched
  //    identity items count as needing her eyes), then the clean group.
  const eyes = p.contentFlagged.length + p.identityOnly.length + p.touchedClean.length
  const clean = p.clean.length
  if (eyes > 0 || clean > 0) {
    const clauses: string[] = []
    if (eyes > 0) clauses.push(HEADLINE_NEEDS_EYES(eyes))
    if (clean > 0) clauses.push(HEADLINE_CLEAN_READY(clean))
    return clauses.join(HEADLINE_CLAUSE_SEP)
  }

  // 3. Only the transcription tail remains.
  if (rollup.transcribing > 0) {
    return HEADLINE_LAST_TRANSCRIBING(rollup.transcribing)
  }

  // 4. Everything terminal-approved.
  if (p.approved.length > 0 && rollup.total > 0) {
    return HEADLINE_ALL_APPROVED(rollup.total)
  }

  return null
}

// ---------------------------------------------------------------------------
// D2 — honesty bar segments (RTL start→: approved · clean · eyes · moving ·
// failed; zero-count segments are dropped, never rendered as slivers)
// ---------------------------------------------------------------------------

export type BarSegmentKind = 'approved' | 'clean' | 'eyes' | 'moving' | 'failed'

export interface BarSegment {
  kind: BarSegmentKind
  count: number
}

export function barSegments(p: Partition, rollup: RollupLike): BarSegment[] {
  const eyes = p.contentFlagged.length + p.identityOnly.length + p.touchedClean.length
  const all: BarSegment[] = [
    { kind: 'approved', count: p.approved.length },
    { kind: 'clean', count: p.clean.length },
    { kind: 'eyes', count: eyes },
    { kind: 'moving', count: rollup.transcribing },
    { kind: 'failed', count: rollup.transcription_failed },
  ]
  return all.filter((s) => s.count > 0)
}

// ---------------------------------------------------------------------------
// D6 — derivable chip counts
// ---------------------------------------------------------------------------

/** Empty answers NOT explained by "choose k of N" selection (mirrors the
 * server triage's expected-empty exclusion). */
export function missingAnswersCount(
  draft: DraftLike,
  groups: AnswerSpaceSelectionGroup[] | undefined | null,
): number {
  const expected = expectedEmptyKeys(
    draft.answers.map((a) => ({
      question_number: a.question_number,
      sub_question_id: a.sub_question_id,
      text: a.answer_text,
    })),
    groups,
  )
  let n = 0
  for (const a of draft.answers) {
    if (a.answer_text.trim() === '' && !expected.has(answerTargetId(a))) n += 1
  }
  return n
}

/** Total `[?]` markers across all answers. */
export function unclearCount(draft: DraftLike): number {
  let n = 0
  for (const a of draft.answers) {
    n += a.answer_text.split('[?]').length - 1
  }
  return n
}

// ---------------------------------------------------------------------------
// D7 — elapsed mm:ss (clock-skew clamped)
// ---------------------------------------------------------------------------

export function formatElapsed(startedAtIso: string, now: Date): string {
  const started = new Date(startedAtIso).getTime()
  const seconds = Math.max(0, Math.floor((now.getTime() - started) / 1000))
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// ---------------------------------------------------------------------------
// D1 — relative creation time (Hebrew, coarse on purpose)
// ---------------------------------------------------------------------------

export function relativeTimeHe(iso: string, now: Date): string {
  const minutes = Math.max(0, Math.floor((now.getTime() - new Date(iso).getTime()) / 60000))
  if (minutes < 1) return 'לפני רגע'
  if (minutes === 1) return 'לפני דקה'
  if (minutes < 60) return `לפני ${minutes} דקות`
  const hours = Math.floor(minutes / 60)
  if (hours === 1) return 'לפני שעה'
  if (hours < 24) return `לפני ${hours} שעות`
  const days = Math.floor(hours / 24)
  return days === 1 ? 'אתמול' : `לפני ${days} ימים`
}

// ---------------------------------------------------------------------------
// D10 — completion trigger · D12 — poll cadence
// ---------------------------------------------------------------------------

export function completionReached(batch: BatchLike): boolean {
  const r = batch.rollup
  return (
    r.total > 0 &&
    r.transcribing === 0 &&
    r.transcribed === 0 &&
    (batch.active_jobs ?? []).length === 0
  )
}

/** 3s while transcription decisions are pending (D10 trigger false); 5s while
 * only grading moves; null = stop polling. */
export function pollCadenceMs(batch: BatchLike): number | null {
  if (!completionReached(batch)) return 3000
  if (batch.rollup.grading > 0) return 5000
  return null
}


// ---------------------------------------------------------------------------
// C2 (closeout) — the completion hero's duration, honestly.
//
// D10 froze "minutes since created_at" the moment completion was FIRST
// OBSERVED. For a teacher who finishes the batch in one sitting that is the
// real elapsed time. For a teacher opening a week-old completed batch, her
// first observation is NOW — so the same arithmetic renders `10080 דקות` on
// the peak-end moment the hero exists to make feel good.
//
// There is no real completion timestamp to fall back on: `batches.completed_at`
// exists as a column and a payload field but is NEVER WRITTEN (verified), and
// adding one at closeout is not a closeout-shaped change. So: degrade by
// OMISSION (D10's own rule, and §3.5a's). The duration renders only when this
// session actually watched the batch complete — i.e. we observed it INCOMPLETE
// at least once first. A revisit shows the hero without a duration line, which
// is exactly what the component already supports (`durationMinutes !== null`).
// ---------------------------------------------------------------------------
export function sessionCompletionMinutes(
  createdAtIso: string,
  nowMs: number,
  observedIncompleteThisSession: boolean,
): number | null {
  if (!observedIncompleteThisSession) return null
  const created = new Date(createdAtIso).getTime()
  if (!Number.isFinite(created)) return null
  return Math.max(1, Math.round((nowMs - created) / 60000))
}
