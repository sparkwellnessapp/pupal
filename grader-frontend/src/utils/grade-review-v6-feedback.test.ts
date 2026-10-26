import { describe, expect, it } from 'vitest';

import { loadV6Fixture } from '@/mocks/grade_review/v6Fixture';
import { buildV6ReviewModel, overlayFromWire, v6Feedback } from './grade-review-v6-model';

/**
 * The student's feedback on the v6 surface — every state the card can be in,
 * and the one rule that decides it (`v6Feedback`), driven by the real v6
 * fixture where the whole model is involved.
 */

const fx = loadV6Fixture();
const base = { vivi: '', hers: undefined, stale: false, rewriting: false, failed: false,
    canWrite: true, offered: null };

describe('v6Feedback — one rule for every feedback card', () => {
    it("Vivi's text is fresh, or stale once her decisions moved it", () => {
        expect(v6Feedback({ ...base, vivi: 'טקסט' }).state).toBe('fresh');
        expect(v6Feedback({ ...base, vivi: 'טקסט', stale: true }).state).toBe('stale');
    });

    it('her words are never stale, and an emptied box is HER «no feedback»', () => {
        const hers = v6Feedback({ ...base, vivi: 'טקסט', stale: true, hers: 'שלי' });
        expect(hers).toMatchObject({ state: 'fresh', teacherEdited: true, text: 'שלי' });
        expect(v6Feedback({ ...base, vivi: 'טקסט', hers: '' }).state).toBe('blank');
        expect(v6Feedback({ ...base, vivi: 'טקסט', hers: '   ' }).state).toBe('blank');
    });

    it('missing text says why — Vivi failed, or nothing was ever written', () => {
        expect(v6Feedback({ ...base, failed: true })).toMatchObject({ state: 'absent', absentReason: 'failed' });
        expect(v6Feedback(base)).toMatchObject({ state: 'absent', absentReason: 'not_written' });
    });

    it('a rewrite in flight reads as updating, whatever was there', () => {
        expect(v6Feedback({ ...base, vivi: 'טקסט', stale: true, rewriting: true }).state).toBe('updating');
        expect(v6Feedback({ ...base, rewriting: true }).state).toBe('updating');
        // …but never over her words
        expect(v6Feedback({ ...base, hers: 'שלי', rewriting: true }).state).toBe('fresh');
    });
});

describe('buildV6ReviewModel — feedback on every question the student gets', () => {
    const build = (review: object, draft: object = fx.draft, extra: object = {}) => buildV6ReviewModel({
        review: { ...fx.base, ...review } as typeof fx.base,
        draft: draft as typeof fx.draft,
        overlay: overlayFromWire(fx.base.overlay),
        ...extra,
    });
    const scopeIds = (model: ReturnType<typeof build>) =>
        model.scopes.filter((s) => s.counted).map((s) => s.scopeId);

    it('with no feedback at all, every counted question still has a card — and the bar counts them', () => {
        const model = build({ feedback: null });
        const counted = model.scopes.filter((s) => s.counted);
        expect(counted.length).toBeGreaterThan(0);
        for (const s of counted) expect(s.feedback?.state).toBe('absent');
        expect(model.feedbackMissing).toBe(counted.length);
        expect(model.summary.state).toBe('absent');
    });

    it('a failed grade-time write says so, on the question and on the summary', () => {
        const failed = { ...fx.draft, annotations: [
            ...(fx.draft.annotations ?? []),
            { severity: 'info', annotation_type: 'feedback_unavailable', message: 'x', target_id: '' }] };
        const model = build({ feedback: null }, failed);
        const llm = model.scopes.find((s) => s.counted && s.gradedBy === 'llm');
        expect(llm?.feedback?.absentReason).toBe('failed');
        expect(model.summary.absentReason).toBe('failed');
    });

    it("the server's stale list marks Vivi's text, a rewrite marks it updating, an offer rides beside hers", () => {
        const ids = scopeIds(build({}));
        const [first, second] = ids;
        const feedback = {
            scopes: Object.fromEntries(ids.map((id) => [id, { text: `משוב ${id}`, basis_hash: 'h' }])),
            summary: { text: 'סיכום', basis_hash: '' }, model_version: 'm', prompt_version: 'p',
        };
        const model = build({ feedback, stale_feedback_scope_ids: [first, second] }, fx.draft, {
            rewriting: new Set([second]),
            feedbackOverrides: { summary: 'הסיכום שלי' },
            offers: { summary: 'נוסח חדש' },
        });
        const of = (id: string) => model.scopes.find((s) => s.scopeId === id)?.feedback;
        expect(of(first)?.state).toBe('stale');
        expect(of(second)?.state).toBe('updating');
        expect(model.summary).toMatchObject({ state: 'fresh', teacherEdited: true, offered: 'נוסח חדש' });
        expect(model.feedbackMissing).toBe(0);
    });

    it('a question excluded by a selection gets no card — the student never sees it', () => {
        const model = build({});
        for (const s of model.scopes.filter((x) => !x.counted)) expect(s.feedback).toBeNull();
    });
});
