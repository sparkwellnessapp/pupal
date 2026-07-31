import { describe, it, expect } from 'vitest';
import { composeFindings, acknowledgedIdsFor, advisoryScanStatus, type PedagogicalMistakeLike } from './findings';
import { recordDismissed } from './findings-ops';
import type { Annotation } from '@/lib/api';

/**
 * PR-6 A6 / B-11b — THE DRAFT ENVELOPE MUST SURVIVE AN EDIT.
 *
 * The save path REPLACES draft_json wholesale (`rubric.draft_json = draft_dict`),
 * so a field the client omits is not "left alone" — it is erased. Before PR-6 that
 * silently dropped selection_groups; after PR-6 it would have wiped every finding
 * and every decision she recorded, which is a worse failure than never showing them.
 *
 * These tests pin the SHAPE of the payload my-rubrics sends, because the bug is
 * one of omission and omission is invisible in a render test.
 */

/** The my-rubrics payload builder, isolated exactly as the page composes it. */
function buildUpdatePayload(
    loadedDraft: Record<string, unknown> | null,
    dehydratedQuestions: unknown[],
    declaredTotal: number,
) {
    return {
        ...(loadedDraft ?? {}),
        questions: dehydratedQuestions,
        total_points: declaredTotal,
        num_questions: dehydratedQuestions.length,
        num_sub_questions: 0,
        num_criteria: 0,
    };
}

const persistedDraft = (): Record<string, unknown> => ({
    questions: [{ question_id: 'q1' }],
    total_points: 100,
    selection_groups: [{ group_id: 'sg0', of_question_ids: ['q1', 'q2'], choose_k: 1 }],
    annotations: [{ id: 'rubric_mismatch:q1', annotation_type: 'rubric_mismatch', severity: 'warning', message: 'm', target_id: 'q1' }],
    pedagogical_mistakes: [{
        mistake_id: 'pts:q1', kind: 'point_sum_mismatch', target_id: 'q1',
        explanation: 'e', dismissed: true, dismissed_at: '2026-07-30T10:00:00Z',
    }],
    extraction_metadata: { advisory_scan: 'partial', advisory_scan_reason: 'tier_b_skipped_time_budget' },
    programming_language: 'csharp',
});

describe('the my-rubrics update payload preserves everything it does not own', () => {
    const out = buildUpdatePayload(persistedDraft(), [{ question_id: 'q1' }], 100);

    it.each([
        'selection_groups',        // dropping it corrupts INV-4 on a choose-k rubric
        'annotations',             // the document residual — and the ack join keys
        'pedagogical_mistakes',    // the advisories AND her recorded decisions
        'extraction_metadata',     // the advisory-scan stamp (§7 honesty on reopen)
        'programming_language',
    ])('carries %s through the edit', (key) => {
        expect(out[key]).toEqual(persistedDraft()[key]);
    });

    it('overwrites ONLY what this surface edits', () => {
        expect(out.questions).toEqual([{ question_id: 'q1' }]);
        expect(out.num_questions).toBe(1);
    });

    it('does NOT re-derive the declared total from Σ q.total_points', () => {
        // On a choose-1-of-2 rubric the offered sum is 150 and the declared is 100.
        // Re-summing silently rewrites her exam and breaks INV-4.
        const offeredSum = 150;
        expect(out.total_points).toBe(100);
        expect(out.total_points).not.toBe(offeredSum);
    });

    it('a draft with no envelope still produces a valid payload (new/empty rubric)', () => {
        const bare = buildUpdatePayload(null, [], 0);
        expect(bare.questions).toEqual([]);
        expect(bare.total_points).toBe(0);
    });
});

describe('reopen — the decision she recorded is still there, and still silences the re-ask', () => {
    const draft = persistedDraft();
    const annotations = draft.annotations as Annotation[];
    const mistakes = draft.pedagogical_mistakes as PedagogicalMistakeLike[];

    it('the dismissal survives the round trip and composes as dismissed', () => {
        const f = composeFindings(annotations, [], mistakes)[0];
        expect(f.status).toBe('dismissed');
    });

    it('and it still maps to an ack, so re-saving does not re-ask', () => {
        const f = composeFindings(annotations, [], mistakes);
        expect(acknowledgedIdsFor(f)).toEqual(['rubric_mismatch:q1']);
    });

    it('a NEW decision made on reopen lands back in the envelope that gets re-sent', () => {
        const fresh = [{ ...mistakes[0], dismissed: null, dismissed_at: null }];
        const decided = recordDismissed(fresh, 'pts:q1', () => '2026-07-31T09:00:00Z');
        const payload = buildUpdatePayload({ ...draft, pedagogical_mistakes: decided }, [], 100);
        expect((payload.pedagogical_mistakes as PedagogicalMistakeLike[])[0].dismissed).toBe(true);
        expect((payload.pedagogical_mistakes as PedagogicalMistakeLike[])[0].dismissed_at).toBe('2026-07-31T09:00:00Z');
    });

    it('§7 honesty survives too — a partial scan still reads partial weeks later', () => {
        expect(advisoryScanStatus(draft.extraction_metadata as Record<string, unknown>)).toBe('partial');
    });
});
