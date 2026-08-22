import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import type { UploadItemState } from '@/utils/batch-upload';
import { UploadFilePanel } from './UploadFilePanel';

/**
 * U2/U3 render pins (SSR): the §3.2 dropzone copy, LTR MB size islands, the
 * advisory dup chip, and the three U3 row states. The interactive halves
 * (filter-with-reason, truncation notice, retry) are pure-logic-tested in
 * batch-upload.test.ts and journey-tested in Playwright (W5).
 */

const pdf = (name: string, bytes: number) =>
    new File([new Uint8Array(bytes)], name, { type: 'application/pdf' });

function render(files: File[], uploadStates?: ReadonlyMap<number, UploadItemState>) {
    return renderToStaticMarkup(
        <UploadFilePanel
            files={files}
            onFilesChange={() => {}}
            uploadStates={uploadStates ?? null}
            onRetry={() => {}}
        />,
    );
}

describe('UploadFilePanel — U2 render', () => {
    it('renders the §3.2 dropzone line and LTR MB sizes', () => {
        const html = render([pdf('a.pdf', 3.2 * 1024 * 1024)]);
        expect(html).toContain('גררי לכאן קבצי PDF או לחצי לבחירה (עד 50 קבצים)');
        expect(html).toContain('3.2 MB');
        expect(html).toContain('dir="ltr"');
        expect(html).toContain('קובץ אחד');           // AM3 aggregate singular
        expect(html).toContain('נקי הכל');            // U2, feminine (OD5)
    });

    it('marks later (name, size) duplicates with the advisory chip', () => {
        const html = render([pdf('a.pdf', 100), pdf('b.pdf', 200), pdf('a.pdf', 100)]);
        const chips = html.match(/data-testid="dup-chip"/g) ?? [];
        expect(chips).toHaveLength(1);
        expect(html).toContain('כפילות אפשרית — שם וגודל זהים');
    });

    it('U3 row states: uploading %, done ✓, failed reason + retry', () => {
        const states = new Map<number, UploadItemState>([
            [0, { kind: 'uploading', pct: 42 }],
            [1, { kind: 'done', jobId: 'j1' }],
            [2, { kind: 'failed', reason: 'קובץ ריק', retryable: false }],
            [3, { kind: 'failed', reason: 'ההעלאה נקטעה', retryable: true }],
        ]);
        const html = render(
            [pdf('a.pdf', 100), pdf('b.pdf', 100), pdf('c.pdf', 100), pdf('d.pdf', 100)],
            states,
        );
        expect(html).toContain('data-testid="row-uploading"');
        expect(html).toContain('42%');
        expect(html).toContain('data-testid="row-done"');
        const failed = html.match(/data-testid="row-failed"/g) ?? [];
        expect(failed).toHaveLength(2);
        expect(html).toContain('קובץ ריק');
        // Retry renders ONLY on the retryable failure (a 422 is terminal).
        const retries = html.match(/data-testid="row-retry"/g) ?? [];
        expect(retries).toHaveLength(1);
        // Locked while uploading: no clear-all, no per-row remove.
        expect(html).not.toContain('data-testid="clear-all"');
        expect(html).not.toContain('aria-label="הסרת');
    });
});
