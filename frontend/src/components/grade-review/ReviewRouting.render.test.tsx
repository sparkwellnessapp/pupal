import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { readdirSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { GradeReviewSurface } from './GradeReviewSurface';
import { GradeReviewSurfaceV6 } from './GradeReviewSurfaceV6';
import { loadV6Fixture } from '@/mocks/grade_review/v6Fixture';
import type { WireDraft } from '@/utils/grade-review-model';
import {
    buildV6ReviewModel, isV6Draft, overlayFromWire,
} from '@/utils/grade-review-v6-model';
import { emptyOverlay } from '@/utils/verdict-cycle';
import { initialCursor, queueState } from '@/utils/grade-review-cursor';
import type { NumericPolicy } from '@/lib/pricing';

/**
 * ROUTING BY plan_schema (owner rulings 2026-10-17 §7, item 1): a draft whose
 * `v6` block is "plan/v6" gets the v6 surface; EVERY other draft keeps the v5
 * surface, byte-for-byte. Three facts, each pinned here:
 *
 *   1. the predicate the page routes on says v5 for every published v5 draft,
 *      and those drafts still render v5's checklist (never the v6 surface);
 *   2. the v5 surface REFUSES a v6 draft (its envelope has no checks), so the
 *      route is load-bearing, not cosmetic — and the v6 surface renders it;
 *   3. the page actually branches on that predicate, v6 first, v5 otherwise.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../../backend/tests/fixtures/grade_review');
const POLICY: NumericPolicy = { precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01' };
const CURSOR = initialCursor([{ graded_test_id: 'a', status: 'draft', student_name: 'נועה לוי' }]);
const noop = () => undefined;

function renderV5(draft: WireDraft): string {
    return renderToStaticMarkup(
        <GradeReviewSurface
            draft={draft}
            questions={[]}
            policy={POLICY}
            overlay={emptyOverlay()}
            onOverlayChange={noop}
            feedbackOverrides={{}}
            onFeedbackChange={noop}
            onFeedbackRegenerate={noop}
            studentName="נועה לוי"
            identityMeta=""
            queue={queueState(CURSOR, 'a')}
            eta={null}
            batchHref="/batches/x"
            canPrev={false}
            canNext={false}
            onPrev={noop}
            onNext={noop}
            onOpenPreview={noop}
            onShowScan={noop}
            saveState="saved"
            onApprove={noop}
            onSaveNow={noop}
            onNotice={noop}
        />,
    );
}

describe('routing by plan_schema', () => {
    const v5Drafts = readdirSync(FIXTURES).filter((f) => /^draft_.*\.json$/.test(f));

    it.each(v5Drafts)('%s routes to v5 and still renders v5`s checklist', (name) => {
        const draft = JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8')) as WireDraft;
        expect(isV6Draft(draft)).toBe(false);
        const html = renderV5(draft);
        expect(html).toContain('data-terminal-id=');
        expect(html).not.toContain('data-no-checks');
        expect(html).not.toContain('data-review-surface="v6"');
    });

    it('a v6 draft routes to v6: v5 refuses it, the v6 surface renders it', () => {
        const fx = loadV6Fixture();
        expect(isV6Draft(fx.draft)).toBe(true);
        expect(renderV5(fx.draft)).toContain('data-no-checks');

        const model = buildV6ReviewModel({
            review: fx.base, draft: fx.draft, overlay: overlayFromWire(fx.base.overlay),
        });
        const html = renderToStaticMarkup(
            <GradeReviewSurfaceV6
                model={model}
                policy={{ precision: fx.base.content.precision, rounding_mode: 'half_up' }}
                studentName="נועה לוי"
                identityMeta=""
                queue={queueState(CURSOR, 'a')}
                eta={null}
                batchHref="/batches/x"
                canPrev={false}
                canNext={false}
                onPrev={noop}
                onNext={noop}
                onOpenPreview={noop}
                onShowScan={noop}
                saveState="saved"
                onApprove={noop}
                onSaveNow={noop}
                onNotice={noop}
                onChoose={noop}
                onWithdraw={noop}
                onNote={noop}
                onPin={noop}
                onClearPin={noop}
                onFeedbackChange={noop}
                onRewriteFeedback={noop}
                onAcceptFeedbackOffer={noop}
                onDismissFeedbackOffer={noop}
            />,
        );
        expect(html).toContain('data-review-surface="v6"');
        expect(html.match(/data-v6-criterion=/g)?.length)
            .toBe(fx.base.content.view_terminals.length);
        // the student's answer is the envelope's, per question (EVD-1)
        expect(html.match(/data-answer-for=/g)?.length).toBeGreaterThan(0);
    });

    it('the review page branches on that predicate — v6 first, v5 otherwise', () => {
        const page = readFileSync(path.resolve(
            HERE, '../../app/batches/[id]/grade-review/[gradedTestId]/page.tsx'), 'utf-8');
        expect(page).toContain('const v6 = isV6Draft(payload.draft);');
        const branch = page.indexOf('{v6 ? (');
        const v6At = page.indexOf('<GradeReviewV6', branch);
        const v5Guard = page.indexOf(') : policy ? (', v6At);
        const v5At = page.indexOf('<GradeReviewSurface', v5Guard);
        expect(branch).toBeGreaterThan(-1);
        expect(v6At).toBeGreaterThan(branch);
        expect(v5Guard).toBeGreaterThan(v6At);
        expect(v5At).toBeGreaterThan(v5Guard);
    });
});
