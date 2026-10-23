/**
 * P2 — dashboard selectors (framework-free, zero-mock-tested):
 * D3 selectHeadline (§3.2 precedence, strings via C1) · D2 barSegments ·
 * D6 chip counters · D7 elapsed formatter · D12 poll cadence · D10
 * completion trigger. Components stay thin; every rule lives here.
 */
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
  /** Transcriptions that PASSED the gate. Read as `?? 0`: a fixture that
   *  predates the accounting below has none, and that reads as zero. */
  approved_transcription?: number
  grading: number
  /** Graded rows awaiting her signature. Read as `?? 0` where absent. */
  draft?: number
  approved: number
  /** Graded rows whose grade failed. Read as `?? 0` where absent. */
  failed?: number
  transcription_failed: number
  total: number
}

/**
 * Transcriptions she has ACCEPTED that the grader has not yet claimed — the
 * window between the gate and the first `graded_tests` row reaching `pending`.
 *
 * THE GAP, NEVER THE RAW TALLY. `approved_transcription` counts every
 * transcription that ever passed the gate and never goes back down, so a
 * batch signed an hour ago still reports all of them. Read directly, that
 * number said «ויוי בודקת» over a finished batch on the dashboard (the stale
 * chip `batch-stage.ts` exists to close) and — found 2026-09-19, live on three
 * of the reporting teacher's own batches — «N מבחנים ממתינים לך» in the LIST
 * over every batch whose every grade was signed, with a mini bar that summed
 * past the batch. The list had re-derived the same quantity from the raw
 * tally; the fixture that would have caught it omitted the field entirely.
 *
 * ONE definition, consumed by both surfaces, so they cannot disagree again.
 */
export function awaitingGraderCount(rollup: RollupLike): number {
  const gradedRows = rollup.grading + (rollup.draft ?? 0) + rollup.approved + (rollup.failed ?? 0)
  return Math.max(0, (rollup.approved_transcription ?? 0) - gradedRows)
}

/** The upload stage as ONE number, read the same way by every consumer here.
 *  Files on the wire — not yet ours, and certainly not "transcribing". */
export function uploadingCount(rollup: RollupLike): number {
  return rollup.uploading ?? 0
}

/**
 * Documents the rollup cannot place in ANY stage — and there must be none.
 *
 * On a consistent snapshot the rollup's parts account for its denominator
 * exactly: every declared file is either still on the wire (`uploading`), dead
 * on the wire (`not_received`), or landed as a job — and every job is queued or
 * running (`transcribing`), failed (`transcription_failed`), or completed into
 * a transcription that is either awaiting her (`transcribed`) or past the gate
 * (`approved_transcription`). So `total − Σ(parts)` is zero, always.
 *
 * ── WHEN IT IS NOT ZERO, THE SNAPSHOT IS TORN — and the client used to read
 * that as "done". The server composes its rollup from several statements, each
 * under its own READ COMMITTED snapshot; a document landing between two of
 * them showed up as a completed job with no transcription row. That rollup —
 * `total 1 · transcribing 0 · transcribed 0` — is indistinguishable, count by
 * count, from "the one document already passed the gate": `completionReached`
 * said true, polling stopped, the stepper jumped to «הורדה» over «הושלם», and a
 * single-test batch froze on a screen that was never true (2026-09-19). The
 * server now orders its reads so that particular tear cannot happen; THIS is
 * the rule that no tear, present or future, can be read as completion
 * (CLAUDE.md §3.5a: a degradation that keeps computing is the dangerous kind).
 *
 * The honest reading of a document the rollup cannot place is that it is
 * still MOVING — Vivi is working — so it keeps the poll alive and keeps the
 * stage on Vivi's side. Never negative: a legacy batch whose rows outnumber
 * its stored count has nothing unaccounted, only an old denominator.
 */
export function unaccountedCount(rollup: RollupLike): number {
  const placed = uploadingCount(rollup)
    + (rollup.not_received ?? 0)
    + rollup.transcribing
    + rollup.transcription_failed
    + rollup.transcribed
    + (rollup.approved_transcription ?? 0)
  return Math.max(0, rollup.total - placed)
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
// D3's headline is GONE (§5.1B).
//
// `selectHeadline` said the same KIND of thing as the turn line — "here is what
// is happening and what you can do" — derived separately, rendered two lines
// apart. Whichever she read first, the other was redundant at best and
// contradicting at worst. The turn line (`batch-stage.ts::deriveBatchStage`) is
// now the only sentence of its kind on the page, and it is derived from the
// same value as the chip and the stepper, so the three cannot drift.
//
// The identity clause the headline carried is not lost: `IdentityWave` states
// it in its own title and sub-line, beside the pills it is about.
// ---------------------------------------------------------------------------

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
    // …and a document the rollup cannot PLACE is not "done" either. The three
    // zeros above infer "every document passed the gate" from ABSENCE, and a
    // torn server snapshot — a completed job whose transcription row is not
    // yet visible — produces exactly those zeros over a document that has
    // passed nothing. This is the clause that turns absence back into "still
    // moving" (see `unaccountedCount`); without it the poll stopped and the
    // dashboard froze on «הושלם» over one unreviewed paper.
    unaccountedCount(r) === 0 &&
    (batch.active_jobs ?? []).length === 0
  )
}

/**
 * §5.1F — the flow's ONE celebration fires here, and nowhere else.
 *
 * `completionReached` above is TRANSCRIPTION completion: it was what triggered
 * the green-check hero, four steps before the flow ends. The end state is every
 * graded test SIGNED, which is the only moment the teacher is actually done.
 *
 * `approved` is the count of approved graded tests and `total` the batch's
 * denominator, so a batch with one document still in transcription can never
 * satisfy this — which is the property that makes it safe to celebrate on.
 */
export function signOffReached(batch: BatchLike & { rollup: RollupLike }): boolean {
  const r = batch.rollup
  return r.total > 0 && r.approved >= r.total
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
