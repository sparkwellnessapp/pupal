import { readdirSync, readFileSync, statSync } from 'fs';
import { join } from 'path';

import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import { DASH_DOWNLOAD, DASH_DOWNLOAD_PREPARING } from '@/copy/grade-review';
import type { GradedItem } from '@/utils/grade-dashboard';
import { DownloadAllButton } from './DownloadAllButton';
import { GradeDashboard } from './GradeDashboard';
import { SignedCompletion } from './SignedCompletion';

/**
 * DL-1 / DL-4 / DL-5 — the download-all button, rendered.
 *
 * The click guard and the always-terminates rule are behaviour and live in
 * `zip-download.test.ts`; this pins what she SEES in each state, and that both
 * sites that offer the ZIP render the same button with the same label.
 */

const text = (html: string) => html.replace(/<[^>]+>/g, '');
const button = (html: string) => html.match(/<button[^>]*data-download[^>]*>/)?.[0] ?? '';

describe('DownloadAllButton', () => {
    it('idle: the owner-ruled label, no spinner, not busy', () => {
        const html = renderToStaticMarkup(<DownloadAllButton busy={false} onClick={() => undefined} />);
        expect(DASH_DOWNLOAD).toBe('הורדת כל הבדיקות שאושרו');
        expect(text(html)).toContain(DASH_DOWNLOAD);
        expect(html).not.toContain('animate-spin');
        expect(button(html)).toContain('aria-busy="false"');
        expect(button(html)).not.toContain('aria-disabled');
        // The live region exists BEFORE it has anything to say — a region
        // inserted together with its text is not reliably announced.
        expect(html).toMatch(/aria-live="polite"[^>]*><\/span>/);
    });

    it('in flight: spinner, aria-busy, a disabled look, and an announcement', () => {
        const html = renderToStaticMarkup(<DownloadAllButton busy onClick={() => undefined} />);
        expect(html).toContain('animate-spin');
        expect(button(html)).toContain('aria-busy="true"');
        expect(button(html)).toContain('aria-disabled="true"');
        expect(button(html)).toContain('opacity-60');
        // DL-5: the label is unchanged while working.
        expect(text(html)).toContain(DASH_DOWNLOAD);
        expect(html).toMatch(new RegExp(`aria-live="polite"[^>]*>${DASH_DOWNLOAD_PREPARING}</span>`));
    });

    it('DL-5: the spinner occupies a slot that is there in both states', () => {
        const slot = /<span[^>]*data-download-slot[^>]*class="([^"]*)"/;
        const idle = renderToStaticMarkup(<DownloadAllButton busy={false} onClick={() => undefined} />);
        const busy = renderToStaticMarkup(<DownloadAllButton busy onClick={() => undefined} />);
        expect(idle.match(slot)?.[1]).toBeTruthy();
        expect(idle.match(slot)?.[1]).toBe(busy.match(slot)?.[1]);
        expect(idle.match(slot)?.[1]).toMatch(/\bw-4\b/);
    });
});

const approved = (id: string): GradedItem => ({
    graded_test_id: id, student_name: 'דנה', status: 'approved',
});

describe('both sites render the same button', () => {
    it('the dashboard header (mid-session) shows the spinner while in flight', () => {
        const html = renderToStaticMarkup(
            <GradeDashboard
                items={[approved('a'), { graded_test_id: 'b', student_name: 'נועה', status: 'draft' }]}
                auditStatus="disabled"
                eta={null}
                onOpenReview={() => undefined}
                onOpenPreview={() => undefined}
                onRetry={() => undefined}
                onContinue={() => undefined}
                onDownload={() => undefined}
                downloading
            />,
        );
        expect(button(html)).toContain('aria-busy="true"');
        expect(html).toContain('animate-spin');
    });

    it('the signed-completion card shows the spinner while in flight', () => {
        const html = renderToStaticMarkup(
            <SignedCompletion
                approved={2}
                failed={0}
                durationMinutes={null}
                heroItem={null}
                onOpenPreview={() => undefined}
                onDownload={() => undefined}
                downloading
                failuresLine={null}
            />,
        );
        expect(button(html)).toContain('aria-busy="true"');
        expect(text(html)).toContain(DASH_DOWNLOAD);
    });
});

describe('DL-4 OneLabel', () => {
    it('the old label appears nowhere in frontend/src', () => {
        const OLD = 'הורדת כל המבחנים החתומים';
        const root = join(__dirname, '..', '..');
        const offenders: string[] = [];
        const walk = (dir: string) => {
            for (const name of readdirSync(dir)) {
                const path = join(dir, name);
                if (statSync(path).isDirectory()) walk(path);
                else if (/\.(tsx?|mjs|js)$/.test(name) && !path.endsWith('DownloadAllButton.render.test.tsx')
                    && readFileSync(path, 'utf8').includes(OLD)) offenders.push(path);
            }
        };
        walk(root);
        expect(offenders).toEqual([]);
    });
});
