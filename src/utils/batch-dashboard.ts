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
  HEADLINE_UPLOADING,
} from '@/copy/batch'
import type { Partition } from '@/utils/batch-partition'
import { isIdentityPending } from './zone-assignment'
import { answerTargetId } from '@/utils/review-flags'
import {
  expectedEmptyKeys,
  type AnswerSpaceSelectionGroup,
} from '@/utils/selection-expectation'

export interface RollupLike {
  /** [Stage A] Declared files that have not landed yet.
   *
   *  OPTIONAL, and read everywhere as `?? 0`. Absent is not a guess and not a
   *  degradation: a server that does not send this field has no notion of a
   *  declared count, so the number of outstanding declared files on it really
   *  is zero. That also makes the deploy window safe in both orders — Vercel
   *  and Cloud Run ship to different targets and neither waits for the other. */
  uploading?: number
  /** [Stage A] Declared, never arrived, past the backstop TTL. Dead, not moving. */
  not_received?: number
  transcribing: number
  transcribed: number
  grading: number
  approved: number
  transcription_failed: number
  total: number
}

/** The upload stage as ONE number, read the same way by every consumer here.
 *  Files on the wire — not yet ours, and certainly not "transcribing". */
export function uploadingCount(rollup: RollupLike): number {
  return rollup.uploading ?? 0
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
  const pendingN = p.identityOnly.filter(isIdentityPending).length
  const eyes = p.contentFlagged.length + (p.identityOnly.length - pendingN)
    + p.touchedClean.length
  const clean = p.clean.length + pendingN
  if (eyes > 0 || clean > 0) {
    const clauses: string[] = []
    if (eyes > 0) clauses.push(HEADLINE_NEEDS_EYES(eyes))
    if (clean > 0) clauses.push(HEADLINE_CLEAN_READY(clean))
    return clauses.join(HEADLINE_CLAUSE_SEP)
  }

  // 3. Only the arrival tail remains. Transcription first — those documents are
  //    further along, and she is closer to being able to act on them. Uploading
  //    ranks BELOW everything she can already do something about: files on the
  //    wire ask nothing of her.
  if (rollup.transcribing > 0) {
    return HEADLINE_LAST_TRANSCRIBING(rollup.transcribing)
  }
  if (uploadingCount(rollup) > 0) {
    return HEADLINE_UPLOADING(uploadingCount(rollup))
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

export type BarSegmentKind =
  | 'approved' | 'clean' | 'eyes' | 'uploading' | 'moving' | 'failed'
  | 'not_received'

export interface BarSegment {
  kind: BarSegmentKind
  count: number
}

export function barSegments(p: Partition, rollup: RollupLike): BarSegment[] {
  // ZC-1 v2 (owner refinement 2026-08-23): identity-pending items count as
  // CLEAN — their home — not amber. One arithmetic with assignZones, pinned
  // by the parity test in zone-assignment.test.ts.
  const pending = p.identityOnly.filter(isIdentityPending).length
  const eyes = p.contentFlagged.length + (p.identityOnly.length - pending)
    + p.touchedClean.length
  const all: BarSegment[] = [
    { kind: 'approved', count: p.approved.length },
    { kind: 'clean', count: p.clean.length + pending },
    { kind: 'eyes', count: eyes },
    // [Stage A] The upload stage sits BEFORE transcription, and it is its own
    // segment rather than folded into `moving`: those files are not being read
    // by anything yet, and a bar that merged them would say the machine is
    // working on documents it has never seen.
    { kind: 'uploading', count: uploadingCount(rollup) },
    { kind: 'moving', count: rollup.transcribing },
    { kind: 'failed', count: rollup.transcription_failed },
    // `not_received` is dead, but it is NOT a failure and gets its own segment.
    // Folding it into «נכשל» made two surfaces contradict each other about the
    // same fact — the list says «לא הגיעו … אפשר להעלות אותם שוב» while the
    // dashboard said «נכשל» — and pointed her at a FailedZone that is empty,
    // because a file that never arrived has no job row, no filename and no
    // retry. Nothing was transcribed and nothing broke: the file is still on
    // her machine.
    { kind: 'not_received', count: rollup.not_received ?? 0 },
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
    // [Stage A] Files still on the wire are the FIRST thing that makes a batch
    // incomplete. Without this clause a ten-file batch whose first file has not
    // landed reads total>0, transcribing 0, transcribed 0, no active jobs — and
    // fires the completion hero over an upload that has barely started.
    uploadingCount(r) === 0 &&
    // …and a batch whose declared files NEVER arrived is not complete either.
    // This clause is what stops the worst version of the same lie: after the
    // 90-minute backstop an abandoned ten-file batch reads uploading 0 with
    // everything else 0, so without it the green ✓ hero renders
    // «כל 10 המבחנים אושרו» over a batch that received nothing — three lines
    // under a red «נכשל» status chip. Before Stage A that was unreachable,
    // because `total` was COUNT(jobs) and the `total > 0` guard held. Making
    // `total` the declared count is what opened it, so closing it belongs here.
    (r.not_received ?? 0) === 0 &&
    r.transcribing === 0 &&
    r.transcribed === 0 &&
    (batch.active_jobs ?? []).length === 0
  )
}

/** 3s while transcription decisions are pending (D10 trigger false); 5s while
 * only grading moves; null = stop polling. */
export function pollCadenceMs(batch: BatchLike): number | null {
  if (!completionReached(batch)) {
    // [Stage B] An EMPTY batch has nothing to wait for, and `completionReached`
    // will never say otherwise because of its `total > 0` guard. That state is
    // newly reachable: if every selected file is rejected 422, the client
    // re-declares `expected = 0`, so `total` is 0 — and before Stage B she
    // never landed on this page at all, because the continue button required
    // at least one landed file. Left alone the dashboard polls a dead batch
    // every 3 seconds forever.
    const nothingInFlight = batch.rollup.total === 0
      && uploadingCount(batch.rollup) === 0
      && (batch.active_jobs ?? []).length === 0
    return nothingInFlight ? null : 3000
  }
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
