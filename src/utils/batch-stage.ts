/**
 * THE batch stage, as ONE pure function (grading-flow clarity pass §5.1).
 *
 * ── WHY THIS FILE EXISTS ──────────────────────────────────────────────────
 * The header chip used to be derived by `batchStatusLabel`, which knew about
 * uploading and transcribing and NOTHING about the grading half of the rollup.
 * So the moment every transcription was approved and Vivi started grading, the
 * chip kept saying «ממתין להחלטות» — "waiting on your decisions" — over a batch
 * that was waiting on US. It was not a polling gap and not a server lag: it was
 * a derivation that could not see half its own subject.
 *
 * The fix is the §9 precedent applied to display state: two derivations of the
 * same fact cannot stay in agreement, so there is now exactly one. The chip,
 * the turn line and the stepper are three renderings of a SINGLE value computed
 * here, from the server payload alone. No component-local state, no second
 * opinion, nothing to go stale.
 *
 * ── THE PRECEDENCE RULE (OD-7, ruled) ─────────────────────────────────────
 * If anything is teacher-actionable, that is the stage — otherwise the
 * Vivi-work stage. The chip answers one question, «is there something for me to
 * do», and the turn line carries the nuance ("Vivi is still reading four ·
 * you can start approving the six that are ready").
 *
 * Between the two teacher-actionable stages, TRANSCRIPTION APPROVAL outranks
 * SIGNING: it is earlier in the flow and it is the one that unblocks Vivi, so a
 * teacher who does it first keeps the pipeline full.
 *
 * ── THE ETA IS THE GRADING ETA, AND ONLY THAT ─────────────────────────────
 * `BatchDetailResponse.eta` is built by `_build_graded_feed` from graded-test
 * landings and a grader latency profile (PR-G8 §1.5). There is NO transcription
 * ETA anywhere on the wire. So the transcription rows below carry no «עוד כ-N
 * דקות» clause: the spec allows omitting it when there is none, and borrowing
 * the grading figure would be a confident guess about the one thing she is
 * waiting on (§3.5a — degrade by omission, never by substitution).
 */

import {
    CHIP_DONE, CHIP_FAILED, CHIP_GRADING, CHIP_TRANSCRIBING, CHIP_UPLOADING,
    CHIP_PARTIAL, CHIP_WAITING_APPROVAL, CHIP_WAITING_SIGNATURE,
    TURN_ALL_FAILED, TURN_PARTIAL,
    TURN_ALL_SIGNED, TURN_GRADED_UNSIGNED, TURN_GRADING_NONE_READY,
    TURN_GRADING_SOME_READY, TURN_TRANSCRIBED_ALL, TURN_TRANSCRIBED_NEEDS_LOOK,
    TURN_TRANSCRIBING_MIXED, TURN_TRANSCRIBING_ONLY, TURN_UPLOADING,
} from '@/copy/batch'
import { etaMinutes, type BatchEta } from './grade-dashboard'

/** The six steps of §5.1A, in flow order. */
export type BatchStep =
    | 'upload' | 'transcribe' | 'approve_transcriptions'
    | 'grade' | 'sign' | 'download'

export const BATCH_STEPS: readonly BatchStep[] = [
    'upload', 'transcribe', 'approve_transcriptions', 'grade', 'sign', 'download',
] as const

export type ChipKey =
    | 'uploading' | 'transcribing' | 'awaiting_approval'
    | 'grading' | 'awaiting_signature' | 'done'
    /**
     * Some documents died and the rest are finished. NOT in §5.1C's chip list,
     * and added because that list's own rule forces it: «שגיאה (only if a
     * whole-batch failure state exists; per-item failures are shown on the item,
     * not the chip)». `partially_completed` is the server's word for a batch
     * that mostly worked, so «שגיאה» would libel it and «הושלם» would hide the
     * losses — and the first version of this module did BOTH at once, pairing a
     * «שגיאה» chip with a «סיימת» turn line on the same header.
     */
    | 'partial'
    | 'failed'

export type ChipTone = 'blue' | 'amber' | 'green' | 'red'

export interface StageChip {
    key: ChipKey
    label: string
    tone: ChipTone
}

export interface BatchStage {
    step: BatchStep
    chip: StageChip
    /** The one sentence she must read. `null` only when there is no turn to
     *  announce (an empty batch, or one the server has already called dead). */
    turnLine: string | null
}

/** Everything this function is allowed to look at. */
export interface StageRollup {
    uploading?: number
    not_received?: number
    transcribing: number
    transcribed: number
    /** The flagged-or-touched subset of `transcribed`. `null` = not computable
     *  for this batch, and then the «דורשים מבט» clause is OMITTED rather than
     *  guessed (the `needs_eyes` degradation, CLAUDE.md §3.5a). */
    needs_eyes?: number | null
    approved_transcription: number
    grading: number
    draft: number
    approved: number
    failed: number
    transcription_failed: number
    total: number
}

export interface StageBatch {
    /** The SERVER's aggregate verdict (`_derive_batch_status`). Terminal values
     *  are taken as given; `in_progress` is what this module refines. */
    status: string
    rollup: StageRollup
    active_jobs?: readonly { state?: string }[] | null
    eta?: BatchEta | null
}

const CHIPS: Record<ChipKey, StageChip> = {
    uploading: { key: 'uploading', label: CHIP_UPLOADING, tone: 'blue' },
    transcribing: { key: 'transcribing', label: CHIP_TRANSCRIBING, tone: 'blue' },
    awaiting_approval: {
        key: 'awaiting_approval', label: CHIP_WAITING_APPROVAL, tone: 'amber',
    },
    grading: { key: 'grading', label: CHIP_GRADING, tone: 'blue' },
    awaiting_signature: {
        key: 'awaiting_signature', label: CHIP_WAITING_SIGNATURE, tone: 'amber',
    },
    done: { key: 'done', label: CHIP_DONE, tone: 'green' },
    partial: { key: 'partial', label: CHIP_PARTIAL, tone: 'amber' },
    failed: { key: 'failed', label: CHIP_FAILED, tone: 'red' },
}

const STEP_OF: Record<ChipKey, BatchStep> = {
    uploading: 'upload',
    transcribing: 'transcribe',
    awaiting_approval: 'approve_transcriptions',
    grading: 'grade',
    awaiting_signature: 'sign',
    done: 'download',
    partial: 'download',
    // A whole-batch failure leaves her nowhere useful to stand; the stepper
    // shows the stage the work died in, which is transcription in every case
    // `_derive_batch_status` can reach 'failed' from.
    failed: 'transcribe',
}

function movingOf(b: StageBatch): number {
    return b.rollup.transcribing + (b.active_jobs ?? []).length
}

/**
 * The one derivation. Pure: same payload in, same {step, chip, turnLine} out.
 *
 * The cascade below IS the §5.1B table read top-down, with the teacher-
 * actionable rows lifted above the Vivi-work rows per OD-7.
 */
export function deriveBatchStage(batch: StageBatch): BatchStage {
    const r = batch.rollup
    const uploading = r.uploading ?? 0
    const moving = movingOf(batch)

    // A whole-batch failure is the server's word, not ours to re-litigate.
    // Per-item failures are shown on the item and never reach the chip (§5.1C).
    if (batch.status === 'failed') {
        return {
            step: STEP_OF.failed,
            chip: CHIPS.failed,
            // A turn line, not `null`. The chip says something broke; only this
            // says whether she can do anything about it, and a screen with a red
            // chip and no sentence is the one place she is most stuck.
            turnLine: TURN_ALL_FAILED(r.transcription_failed + (r.not_received ?? 0)),
        }
    }

    // ── teacher-actionable: transcriptions awaiting her approval ──
    if (r.transcribed > 0) {
        // Clamped to the population it is a SUBSET of. The server computes it
        // from the same verdict, so they agree today; the clamp is what stops a
        // future disagreement from rendering «5 לאישור, 7 דורשים מבט», which
        // reads as a batch that contains more problems than tests.
        const needsLook = r.needs_eyes == null
            ? null
            : Math.min(r.needs_eyes, r.transcribed)
        const turnLine = (uploading > 0 || moving > 0)
            ? TURN_TRANSCRIBING_MIXED(moving + uploading, r.transcribed)
            : (needsLook !== null && needsLook > 0)
                ? TURN_TRANSCRIBED_NEEDS_LOOK(r.transcribed, needsLook)
                : TURN_TRANSCRIBED_ALL(r.transcribed)
        return {
            step: STEP_OF.awaiting_approval,
            chip: CHIPS.awaiting_approval,
            turnLine,
        }
    }

    // ── teacher-actionable: graded drafts awaiting her signature ──
    if (r.draft > 0) {
        return {
            step: STEP_OF.awaiting_signature,
            chip: CHIPS.awaiting_signature,
            turnLine: r.grading > 0
                ? TURN_GRADING_SOME_READY(r.draft, r.total)
                : TURN_GRADED_UNSIGNED(r.draft),
        }
    }

    // ── Vivi work: reading handwriting ──
    if (moving > 0) {
        return {
            step: STEP_OF.transcribing,
            chip: CHIPS.transcribing,
            turnLine: TURN_TRANSCRIBING_ONLY,
        }
    }

    // ── everything signed ──
    //
    // ABOVE the Vivi-work states, and it has to be. `approved_transcription`
    // counts transcriptions that PASSED THE GATE and never goes back down, so a
    // fully-signed batch still reports three of them — which is why the grading
    // branch below reads the GAP between accepted transcriptions and graded
    // rows rather than the raw count. Checked here as well as computed there,
    // because "she is finished" is the one state that must not be reachable
    // from a counter that only goes up.
    if (r.total > 0 && r.approved >= r.total) {
        return {
            step: STEP_OF.done,
            chip: CHIPS.done,
            turnLine: TURN_ALL_SIGNED(r.approved),
        }
    }

    // ── Vivi work: files still climbing the wire ──
    //
    // BELOW transcribing and ABOVE grading, and the asymmetry is deliberate.
    // Uploading and transcribing are two halves of ONE arrival wave — a file
    // that landed is being read while its siblings arrive — so naming the
    // reading names the further-along half of the same process (the Stage-A
    // precedent this preserves). GRADING is the other side of the transcription
    // gate, and a batch whose files are still 9-of-10 on the wire is not
    // honestly "in the grading stage" because one paper made it all the way
    // through: the chip would be true about that paper and wrong about the
    // batch, and an upload is the one stage that can stall silently.
    if (uploading > 0) {
        return {
            step: STEP_OF.uploading,
            chip: CHIPS.uploading,
            turnLine: TURN_UPLOADING,
        }
    }

    // ── Vivi work: grading ──
    //
    // The second clause is the GAP, not the raw count. A transcription she has
    // just accepted is queued for the grader before any `graded_tests` row
    // reaches 'pending', and reporting that window as "nothing is happening" is
    // the stale chip in a smaller costume — but `approved_transcription` is a
    // gate-passed tally that never decreases, so reading it directly would
    // report «ויוי בודקת» over a batch whose every grade was signed an hour ago.
    const gradedRows = r.grading + r.draft + r.approved + r.failed
    const awaitingGrader = Math.max(0, r.approved_transcription - gradedRows)
    if (r.grading > 0 || awaitingGrader > 0) {
        return {
            step: STEP_OF.grading,
            chip: CHIPS.grading,
            turnLine: TURN_GRADING_NONE_READY(etaMinutes(batch.eta ?? null)),
        }
    }

    // ── terminal, with losses ──
    //
    // `partially_completed`: some documents died, everything that survived is
    // signed. It is neither «הושלם» (which hides the hole) nor «שגיאה» (which
    // libels a batch that mostly worked), and the first version of this
    // fallback managed to be wrong in both directions at once — a «שגיאה» chip
    // over a «סיימת» turn line. One chip, one sentence, both naming the same
    // two facts.
    const dead = r.transcription_failed + r.failed + (r.not_received ?? 0)
    if (r.approved > 0 && dead > 0) {
        return {
            step: STEP_OF.partial,
            chip: CHIPS.partial,
            turnLine: TURN_PARTIAL(r.approved, dead),
        }
    }

    // Nothing in flight, nothing owed, nothing signed — an empty batch, or one
    // whose documents all died without the server calling the whole batch
    // failed. There is no turn to announce, and inventing one would be worse.
    return {
        step: STEP_OF.done,
        chip: dead > 0 ? CHIPS.failed : CHIPS.done,
        turnLine: dead > 0 ? TURN_ALL_FAILED(dead) : null,
    }
}

/** `done` for every step before the current one, `active` for it, else `todo`. */
export type StepState = 'done' | 'active' | 'todo'

export function stepStates(current: BatchStep): Record<BatchStep, StepState> {
    const at = BATCH_STEPS.indexOf(current)
    const out = {} as Record<BatchStep, StepState>
    BATCH_STEPS.forEach((step, i) => {
        out[step] = i < at ? 'done' : i === at ? 'active' : 'todo'
    })
    return out
}
