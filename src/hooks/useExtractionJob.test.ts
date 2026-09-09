/**
 * The extraction poll's TERMINAL EDGE — pinned.
 *
 * Live bug (2026-09-01): a completed job stays completed, so every re-attach
 * re-observed it and re-fired `onComplete`. The page's onComplete re-applies the
 * extraction result, which resets the questions, empties the undo stack, drops the
 * dirty flag and sends the teacher back to the arrival card — so a teacher two
 * minutes into her review lost the review. The trigger that exposed it was a
 * dev-mode Fast Refresh (React DEV treats a hot-reloaded component's hook deps as
 * changed, so the hook's effect re-ran `start()`), but resume, crash-stash restore
 * and retry re-attach the same way in production.
 *
 * The environment here is `node` (no jsdom in this repo), so the hook itself is not
 * mounted; what is pinned is the pure decision the hook delegates to.
 */

import { describe, it, expect } from 'vitest';

import type { ExtractionJobStatus } from '@/lib/api';
import { isTerminal, isNewTerminal } from './useExtractionJob';

const JOB = 'eff70a67-0c9b-4b1a-9243-24734901ca46';

function status(patch: Partial<ExtractionJobStatus> = {}): ExtractionJobStatus {
    return {
        job_id: JOB,
        status: 'completed',
        progress_stage: 'complete',
        progress_detail: null,
        stale: false,
        error_message: null,
        has_result: true,
        source_filename: 'rubric.docx',
        created_at: '2026-09-01T16:44:25Z',
        started_at: '2026-09-01T16:44:28Z',
        finished_at: '2026-09-01T16:48:06Z',
        elapsed_seconds: 217,
        ...patch,
    };
}

describe('isTerminal', () => {
    it('is true for completed, failed, and a stale active job', () => {
        expect(isTerminal(status({ status: 'completed' }))).toBe(true);
        expect(isTerminal(status({ status: 'failed' }))).toBe(true);
        expect(isTerminal(status({ status: 'extracting', stale: true }))).toBe(true);
    });

    it('is false while the job is genuinely running', () => {
        expect(isTerminal(status({ status: 'queued' }))).toBe(false);
        expect(isTerminal(status({ status: 'extracting' }))).toBe(false);
    });
});

describe('isNewTerminal — completion is an edge, not a level', () => {
    it('delivers the first terminal observation', () => {
        expect(isNewTerminal(status(), null)).toBe(true);
    });

    it('REFUSES a second observation of the same finished job', () => {
        // This is the whole bug: re-attaching to a completed job must not re-fire
        // onComplete, because onComplete overwrites the teacher's review.
        expect(isNewTerminal(status(), JOB)).toBe(false);
    });

    it('refuses repeatedly — a re-attach loop stays silent', () => {
        const delivered = JOB;
        for (let i = 0; i < 5; i++) {
            expect(isNewTerminal(status(), delivered)).toBe(false);
        }
    });

    it('delivers a DIFFERENT job even while another one is marked', () => {
        const other = '11111111-2222-3333-4444-555555555555';
        expect(isNewTerminal(status({ job_id: other }), JOB)).toBe(true);
    });

    it('never delivers a non-terminal status', () => {
        expect(isNewTerminal(status({ status: 'extracting' }), null)).toBe(false);
        expect(isNewTerminal(status({ status: 'queued' }), null)).toBe(false);
    });

    it('delivers a failed job once, then refuses (retry is the caller\'s move)', () => {
        expect(isNewTerminal(status({ status: 'failed' }), null)).toBe(true);
        expect(isNewTerminal(status({ status: 'failed' }), JOB)).toBe(false);
    });

    it('re-arms once the job is observed OUTSIDE terminal — the /retry path', () => {
        // The hook clears its marker on any non-terminal read of the same id, so a
        // re-queued job's next completion is a new edge. Modelled here as the
        // caller passing null again after that clear.
        expect(isNewTerminal(status({ status: 'queued', has_result: false }), JOB)).toBe(false);
        expect(isNewTerminal(status(), null)).toBe(true);
    });
});
