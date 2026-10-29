/**
 * FailedZone — a failed card offers a retry only where a retry can heal.
 *
 * 2026-10-29: four documents failed against a 0-question rubric, and every card
 * offered «ניסיון חוזר» beside «look at your connection» guidance — a retry that
 * could only fail the same way. When the batch's rubric is empty the card names
 * the rubric and offers nothing to click.
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { FailedZone } from './FailedZone';
import { FAILED_GUIDE_RUBRIC_EMPTY, FAILED_RETRY } from '@/copy/batch';
import type { TranscriptionFailureItem } from '@/types/batch';

const FAILURE: TranscriptionFailureItem = {
    filename: 'exam-1.pdf',
    error: 'RubricUnusable: rubric … has no questions',
    at: '2026-10-29T10:07:12Z',
    net_verdict: null,
    job_id: 'job-1',
};

const render = (rubricEmpty?: boolean) => renderToStaticMarkup(
    <FailedZone failures={[FAILURE]} onRetry={() => {}} retryBusy={new Set()}
                rubricEmpty={rubricEmpty} />,
);

describe('FailedZone', () => {
    it('a retryable failure keeps its retry', () => {
        const html = render();
        expect(html).toContain('data-testid="retry-job-button"');
        expect(html).toContain(FAILED_RETRY);
        expect(html).not.toContain(FAILED_GUIDE_RUBRIC_EMPTY);
    });

    it('an empty rubric names the rubric and offers no retry', () => {
        const html = render(true);
        expect(html).toContain(FAILED_GUIDE_RUBRIC_EMPTY);
        expect(html).not.toContain('data-testid="retry-job-button"');
    });
});
