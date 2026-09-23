/**
 * `deriveBatchStage` — ONE fixture per row of §5.1B and §5.1C, plus the mixed
 * states, with ZERO mocks. The payload shape is the batch detail response's
 * own, so these fixtures are the same thing the page feeds it.
 *
 * The test that matters most is `the stale chip`: it is the defect this module
 * exists to close, written as an executable claim rather than a comment.
 */
import { describe, expect, it } from 'vitest'

import { BATCH_STEPS, deriveBatchStage, stepStates, type StageBatch, type StageRollup } from './batch-stage'
import {
    CHIP_DONE, CHIP_FAILED, CHIP_GRADING, CHIP_TRANSCRIBING, CHIP_UPLOADING,
    CHIP_WAITING_APPROVAL, CHIP_WAITING_SIGNATURE,
} from '@/copy/batch'

const EMPTY: StageRollup = {
    uploading: 0,
    not_received: 0,
    transcribing: 0,
    transcribed: 0,
    needs_eyes: 0,
    approved_transcription: 0,
    grading: 0,
    draft: 0,
    approved: 0,
    failed: 0,
    transcription_failed: 0,
    total: 0,
}

/**
 * A rollup as the WIRE produces it: its parts account for its total.
 *
 * `uploading + not_received + transcribing + transcription_failed + transcribed
 * + approved_transcription === total`, always, on a consistent server snapshot —
 * every declared file is on the wire, dead on the wire, or a job; every job is
 * queued/running, failed, or completed into a transcription that is awaiting
 * her or past the gate. In particular a GRADED document has a gate-passed
 * transcription behind it, so `approved_transcription` is never below
 * `grading + draft + approved + failed`.
 *
 * The fixtures below carry that field for exactly that reason. They used to
 * omit it (nothing read it), and a rollup that omits it describes a batch that
 * cannot exist — which is the one shape `deriveBatchStage` now refuses to call
 * done: a document the rollup cannot place is read as still MOVING (see the
 * torn-snapshot test at the end of §5.1B). The only fixture that violates the
 * identity on purpose is that one, and it is written out by hand.
 */
function batch(rollup: Partial<StageRollup>, extra: Partial<StageBatch> = {}): StageBatch {
    return {
        status: 'in_progress',
        rollup: { ...EMPTY, ...rollup },
        ...extra,
    }
}

describe('§5.1C — the chip is a pure function of server state', () => {
    it('all items uploading → בהעלאה', () => {
        const s = deriveBatchStage(batch({ uploading: 10, total: 10 }))
        expect(s.chip.label).toBe(CHIP_UPLOADING)
        expect(s.chip.key).toBe('uploading')
        expect(s.step).toBe('upload')
    })

    it('transcribing, nothing ready → ויוי קוראת את כתב היד', () => {
        const s = deriveBatchStage(batch({ transcribing: 4, total: 4 }))
        expect(s.chip.label).toBe(CHIP_TRANSCRIBING)
        expect(s.step).toBe('transcribe')
    })

    it('active jobs alone count as transcribing (the rollup can lag a tick)', () => {
        const s = deriveBatchStage(
            batch({ total: 3 }, { active_jobs: [{ state: 'running' }, { state: 'queued' }] }))
        expect(s.chip.label).toBe(CHIP_TRANSCRIBING)
    })

    it('transcriptions awaiting approval → ממתין לאישור שלך', () => {
        const s = deriveBatchStage(batch({ transcribed: 6, needs_eyes: 0, total: 6 }))
        expect(s.chip.label).toBe(CHIP_WAITING_APPROVAL)
        expect(s.step).toBe('approve_transcriptions')
    })

    it('grading with nothing landed → ויוי בודקת', () => {
        const s = deriveBatchStage(batch({ grading: 5, approved_transcription: 5, total: 5 }))
        expect(s.chip.label).toBe(CHIP_GRADING)
        expect(s.step).toBe('grade')
    })

    it('accepted but not yet claimed by the grader is STILL ויוי בודקת', () => {
        // The window between accept and the first `graded_tests` row reaching
        // 'pending'. Reporting it as "nothing is happening" is the stale chip
        // in a smaller costume.
        const s = deriveBatchStage(batch({ approved_transcription: 3, total: 3 }))
        expect(s.chip.label).toBe(CHIP_GRADING)
    })

    it('a FULLY SIGNED batch is הושלם, never ויוי בודקת', () => {
        // Caught by the screenshot matrix. `approved_transcription` is a
        // gate-passed tally that never decreases, so reading it as "queued for
        // grading" reported «ויוי בודקת» over a batch signed an hour ago —
        // under a green celebration card saying she had finished.
        const s = deriveBatchStage(batch({
            approved_transcription: 3, approved: 3, total: 3,
        }, { status: 'completed' }))
        expect(s.chip.label).toBe(CHIP_DONE)
        expect(s.step).toBe('download')
        expect(s.turnLine).toBe('סיימת · 3 מבחנים חתומים')
    })

    it('a PARTIALLY signed batch still reports the grading that is left', () => {
        const s = deriveBatchStage(batch({
            approved_transcription: 5, grading: 2, approved: 3, total: 5,
        }))
        expect(s.chip.label).toBe(CHIP_GRADING)
    })

    it('graded drafts awaiting signature → ממתין לחתימה שלך', () => {
        const s = deriveBatchStage(batch({ approved_transcription: 4, draft: 4, total: 4 }))
        expect(s.chip.label).toBe(CHIP_WAITING_SIGNATURE)
        expect(s.step).toBe('sign')
    })

    it('everything signed → הושלם', () => {
        const s = deriveBatchStage(
            batch({ approved_transcription: 7, approved: 7, total: 7 }, { status: 'completed' }))
        expect(s.chip.label).toBe(CHIP_DONE)
        expect(s.step).toBe('download')
    })

    it('a whole-batch failure → שגיאה, WITH a turn line', () => {
        // It used to announce no turn at all. A red chip over an empty header
        // is the screen a teacher is most stuck on: the chip says something
        // broke, and only the sentence says whether she can do anything.
        const s = deriveBatchStage(
            batch({ transcription_failed: 3, total: 3 }, { status: 'failed' }))
        expect(s.chip.label).toBe(CHIP_FAILED)
        expect(s.turnLine).toBe('לא הצלחנו לקרוא את המבחנים — אפשר לנסות שוב')
    })

    it('PARTIALLY completed is neither הושלם nor שגיאה, and says both facts', () => {
        // The first version paired a «שגיאה» chip with a «סיימת» turn
        // line on the same header — wrong in both directions at once.
        const s = deriveBatchStage(batch({
            approved: 27, transcription_failed: 3, approved_transcription: 27, total: 30,
        }, { status: 'partially_completed' }))
        expect(s.chip.key).toBe('partial')
        expect(s.turnLine).toBe('סיימת · 27 מבחנים חתומים · 3 מבחנים לא נקראו')
    })

    it('declared files that never arrived count as losses, not as a clean finish', () => {
        const s = deriveBatchStage(batch({
            approved: 8, not_received: 2, approved_transcription: 8, total: 10,
        }, { status: 'partially_completed' }))
        expect(s.chip.key).toBe('partial')
        expect(s.turnLine).toContain('2 מבחנים לא נקראו')
    })

    it('THE STALE CHIP: grading never reports "waiting on your decisions"', () => {
        // The exact screenshot-5 payload: every transcription accepted, Vivi
        // grading, nothing landed. The old derivation said «ממתין להחלטות».
        const s = deriveBatchStage(batch({
            approved_transcription: 6, grading: 6, total: 6,
        }))
        expect(s.chip.label).toBe(CHIP_GRADING)
        expect(s.chip.label).not.toBe(CHIP_WAITING_APPROVAL)
        expect(s.turnLine).not.toContain('תורך')
    })
})

describe('§5.1B — the turn line, one row at a time', () => {
    it('all uploading', () => {
        expect(deriveBatchStage(batch({ uploading: 4, total: 4 })).turnLine)
            .toBe('עכשיו: המבחנים בהעלאה')
    })

    it('transcribing, none ready — no ETA clause, because no transcription ETA exists', () => {
        const s = deriveBatchStage(batch({ transcribing: 4, total: 4 }))
        expect(s.turnLine).toBe('עכשיו: ויוי קוראת את כתב היד')
        expect(s.turnLine).not.toContain('כ-')
    })

    it('some ready while others are still being read', () => {
        expect(deriveBatchStage(batch({
            transcribing: 4, transcribed: 6, needs_eyes: 0, total: 10,
        })).turnLine).toBe('ויוי עדיין קוראת 4 מבחנים · אפשר להתחיל לאשר את 6 שכבר מוכנים')
    })

    it('the mixed row counts uploads as still-being-read work too', () => {
        expect(deriveBatchStage(batch({
            uploading: 2, transcribing: 1, transcribed: 3, total: 6,
        })).turnLine).toBe('ויוי עדיין קוראת 3 מבחנים · אפשר להתחיל לאשר את 3 שכבר מוכנים')
    })

    it('all transcribed, none flagged', () => {
        expect(deriveBatchStage(batch({
            transcribed: 9, needs_eyes: 0, total: 9,
        })).turnLine).toBe('תורך: 9 מבחנים לאישור')
    })

    it('all transcribed, some flagged', () => {
        expect(deriveBatchStage(batch({
            transcribed: 9, needs_eyes: 3, total: 9,
        })).turnLine).toBe('תורך: 9 מבחנים לאישור, 3 מבחנים דורשים מבט')
    })

    it('a single flagged test reads «דורש», not «דורשים»', () => {
        expect(deriveBatchStage(batch({
            transcribed: 4, needs_eyes: 1, total: 4,
        })).turnLine).toBe('תורך: 4 מבחנים לאישור, מבחן אחד דורש מבט')
    })

    it('needs_eyes null (not computable) OMITS the clause, never guesses it', () => {
        expect(deriveBatchStage(batch({
            transcribed: 5, needs_eyes: null, total: 5,
        })).turnLine).toBe('תורך: 5 מבחנים לאישור')
    })

    it('grading, nothing ready, with an ETA', () => {
        expect(deriveBatchStage(batch(
            { approved_transcription: 8, grading: 8, total: 8 },
            { eta: { kind: 'first_landing', seconds: 150 } },
        )).turnLine).toBe('עכשיו: ויוי בודקת · הראשון יהיה מוכן בעוד כ-3 דקות')
    })

    it('grading, nothing ready, ETA unknown → the clause is dropped', () => {
        expect(deriveBatchStage(batch(
            { approved_transcription: 8, grading: 8, total: 8 },
            { eta: { kind: 'unknown', seconds: null } },
        )).turnLine).toBe('עכשיו: ויוי בודקת')
    })

    it('grading with some landed', () => {
        expect(deriveBatchStage(batch({
            approved_transcription: 30, grading: 18, draft: 12, total: 30,
        })).turnLine).toBe('ויוי בודקת · 12 מתוך 30 מוכנים לאישור וחתימה שלך')
    })

    it('all graded, none signed', () => {
        expect(deriveBatchStage(batch({ approved_transcription: 5, draft: 5, total: 5 })).turnLine)
            .toBe('תורך: 5 מבחנים בדוקים מחכים לאישור וחתימה')
    })

    it('all graded, exactly one left', () => {
        expect(deriveBatchStage(batch({
            approved_transcription: 5, draft: 1, approved: 4, total: 5,
        })).turnLine)
            .toBe('תורך: מבחן אחד בדוק מחכה לאישור וחתימה')
    })

    it('all signed', () => {
        expect(deriveBatchStage(batch(
            { approved_transcription: 30, approved: 30, total: 30 },
            { status: 'completed' })).turnLine)
            .toBe('סיימת · 30 מבחנים חתומים')
    })

    it('a batch of one, signed', () => {
        expect(deriveBatchStage(batch(
            { approved_transcription: 1, approved: 1, total: 1 },
            { status: 'completed' })).turnLine)
            .toBe('סיימת · מבחן אחד חתום')
    })

    it('an empty batch announces no turn at all', () => {
        expect(deriveBatchStage(batch({})).turnLine).toBeNull()
    })

    it('THE TORN SNAPSHOT: a document the rollup cannot place is MOVING, never הושלם', () => {
        // 2026-09-19, a single-test batch. The server built its rollup from
        // several statements, each under its own snapshot, and the document
        // landed between two of them: a completed job, no transcription row
        // yet. Every count reads zero over a real paper — the exact shape of
        // an EMPTY batch, one row up — and this fell through to «הורדה» /
        // «הושלם» / no turn line while the poll stopped on the same zeros.
        //
        // Written by hand, not through `batch()`: this is the one rollup that
        // is SUPPOSED to violate the accounting identity.
        const torn: StageBatch = {
            status: 'in_progress',
            rollup: { ...EMPTY, total: 1 },
            active_jobs: [],
        }
        const s = deriveBatchStage(torn)
        expect(s.step).toBe('transcribe')
        expect(s.chip.label).toBe(CHIP_TRANSCRIBING)
        expect(s.turnLine).toBe('עכשיו: ויוי קוראת את כתב היד')
        // …and the honest case that LOOKS identical is still told apart by
        // its total: nothing declared, nothing owed, nothing moving.
        expect(deriveBatchStage(batch({})).step).toBe('download')
    })
})

describe('mixed states — the precedence rule (OD-7)', () => {
    it('transcription approval outranks signing when both are owed', () => {
        // Six accepted and graded while four still await the transcription
        // gate. She is pointed at the gate that unblocks Vivi.
        const s = deriveBatchStage(batch({
            transcribed: 4, needs_eyes: 1, approved_transcription: 6, draft: 6, total: 10,
        }))
        expect(s.chip.key).toBe('awaiting_approval')
        expect(s.turnLine).toBe('תורך: 4 מבחנים לאישור, מבחן אחד דורש מבט')
    })

    it('anything teacher-actionable outranks Vivi work', () => {
        const s = deriveBatchStage(batch({
            transcribing: 20, transcribed: 2, grading: 5, draft: 3, total: 30,
        }))
        expect(s.chip.key).toBe('awaiting_approval')
    })

    it('a signature owed outranks grading still running', () => {
        const s = deriveBatchStage(batch({ grading: 18, draft: 12, total: 30 }))
        expect(s.chip.key).toBe('awaiting_signature')
        expect(s.step).toBe('sign')
    })

    it('UPLOADING outranks grading — one paper through does not make it the stage', () => {
        // The real shape the screenshot matrix caught: nine files still on the
        // wire, one already accepted and queued for the grader. Reporting
        // «ויוי בודקת» here is true about ONE paper and wrong about the
        // batch — and an upload is the one stage that can stall silently.
        const s = deriveBatchStage(batch({
            uploading: 9, approved_transcription: 1, total: 10,
        }))
        expect(s.chip.key).toBe('uploading')
        expect(s.turnLine).toBe('עכשיו: המבחנים בהעלאה')
    })

    it('reading outranks uploading — the further-along fact is the useful one', () => {
        const s = deriveBatchStage(batch({ uploading: 6, transcribing: 4, total: 10 }))
        expect(s.chip.key).toBe('transcribing')
    })

    it('the n=30 walkthrough state: 3 flagged / 27 clean, 12 graded, 5 signed', () => {
        const s = deriveBatchStage(batch({
            transcribed: 30, needs_eyes: 3, grading: 18, draft: 7, approved: 5, total: 30,
        }))
        expect(s.chip.key).toBe('awaiting_approval')
        expect(s.turnLine).toBe('תורך: 30 מבחנים לאישור, 3 מבחנים דורשים מבט')
    })
})

describe('stepStates', () => {
    it('marks everything before the current step done and everything after todo', () => {
        const states = stepStates('grade')
        expect(states.upload).toBe('done')
        expect(states.transcribe).toBe('done')
        expect(states.approve_transcriptions).toBe('done')
        expect(states.grade).toBe('active')
        expect(states.sign).toBe('todo')
        expect(states.download).toBe('todo')
    })

    it('covers every step exactly once, in flow order', () => {
        expect(BATCH_STEPS).toHaveLength(6)
        expect(new Set(BATCH_STEPS).size).toBe(6)
        expect(Object.keys(stepStates('upload')).sort()).toEqual([...BATCH_STEPS].sort())
    })
})
