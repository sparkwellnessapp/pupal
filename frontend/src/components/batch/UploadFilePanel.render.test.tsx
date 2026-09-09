import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { UploadFilePanel } from './UploadFilePanel';

/**
 * U2 render pins (SSR): the §3.2 dropzone copy, LTR MB size islands, and the
 * advisory dup chip. The interactive halves (filter-with-reason, truncation
 * notice) are pure-logic-tested in batch-upload.test.ts and journey-tested in
 * Playwright (W5).
 *
 * [Stage B / R3] The U3 row-state pins that used to live here are RE-HOMED to
 * `UploadLane.render.test.tsx`, not dropped (the §4.4a precedent): progress %,
 * the done tick, the server's failure reason verbatim, and retry-only-where-a-
 * retry-can-heal are all asserted there. They moved because the surface moved —
 * the queue is no longer owned by this page, and the teacher watches it on the
 * dashboard while the transfers run.
 */

const pdf = (name: string, bytes: number) =>
    new File([new Uint8Array(bytes)], name, { type: 'application/pdf' });

function render(files: File[]) {
    return renderToStaticMarkup(
        <UploadFilePanel files={files} onFilesChange={() => {}} />,
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

    it('locks every affordance while a create is in flight', () => {
        // `disabled` is now the ONLY thing that locks the panel — the queue no
        // longer lives here to do it.
        const html = renderToStaticMarkup(
            <UploadFilePanel files={[pdf('a.pdf', 100)]} onFilesChange={() => {}} disabled />,
        );
        expect(html).not.toContain('data-testid="clear-all"');
        expect(html).not.toContain('aria-label="הסרת');
    });
});
