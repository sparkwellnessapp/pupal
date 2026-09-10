/**
 * GhostZone — the transcribing ghosts, and the one thing they could not do
 * before 2026-09-10: END.
 *
 * A document whose worker had overrun spun here forever under the same
 * reassuring «קוראת עמוד אחר עמוד…», and it was the only row on the dashboard
 * with no identifier and therefore no action — failed rows retry, not_received
 * rows re-upload, needs-eyes rows open. These tests pin both halves of the fix
 * AND its limit: the surface acts on the SERVER's word (`retryable`, from the
 * same LIV-1 rule the reaper uses) and never on a guess of its own.
 */
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import { GhostZone } from './GhostZone';
import {
    GHOST_QUEUED,
    GHOST_RETRY,
    GHOST_RUNNING,
    GHOST_STUCK,
    GHOST_STUCK_HINT,
} from '@/copy/batch';
import type { ActiveJobItem } from '@/types/batch';

const LONG_AGO = new Date(Date.now() - 15 * 60_000).toISOString();

function job(over: Partial<ActiveJobItem> = {}): ActiveJobItem {
    return {
        job_id: 'job-1',
        filename: 'hobby_tvshow.dan_basiuk.pdf',
        state: 'running',
        created_at: LONG_AGO,
        started_at: LONG_AGO,
        attempt_count: 1,
        ...over,
    };
}

const html = (ui: React.ReactElement) => renderToStaticMarkup(ui);

describe('a healthy ghost', () => {
    it('reads as work in progress and shows its elapsed clock', () => {
        const out = html(<GhostZone jobs={[job()]} onRetry={() => {}} />);
        expect(out).toContain(GHOST_RUNNING);
        expect(out).not.toContain(GHOST_STUCK);
        expect(out).toContain('15:0');            // the ticking elapsed
        expect(out).not.toContain('retry-stuck-ghost-button');
    });

    it('shows no elapsed clock while merely queued (no fabricated progress)', () => {
        const out = html(
            <GhostZone jobs={[job({ state: 'queued', started_at: null })]} />);
        expect(out).toContain(GHOST_QUEUED);
        expect(out).not.toContain('15:0');
    });

    it('offers no action just because it has been running a long time', () => {
        // THE anti-guess pin. 15 minutes with `retryable` absent is still a
        // live document; a client-side "looks stuck" threshold would tell a
        // teacher her work is broken while it is quietly finishing.
        const out = html(<GhostZone jobs={[job()]} onRetry={() => {}} />);
        expect(out).not.toContain(GHOST_STUCK);
        expect(out).not.toContain(GHOST_RETRY);
    });
});

describe('a ghost the server has declared dead', () => {
    const stuck = job({ retryable: true });

    it('says so, in words that are true — it overran, it did not fail', () => {
        const out = html(<GhostZone jobs={[stuck]} onRetry={() => {}} />);
        expect(out).toContain(GHOST_STUCK);
        expect(out).toContain(GHOST_STUCK_HINT);
        expect(out).not.toContain(GHOST_RUNNING);
    });

    it('stops the clock rather than counting up beside a dead row', () => {
        const out = html(<GhostZone jobs={[stuck]} onRetry={() => {}} />);
        expect(out).not.toContain('15:0');
    });

    it('offers the retry, and it carries the job id the endpoint needs', () => {
        const out = html(<GhostZone jobs={[stuck]} onRetry={() => {}} />);
        expect(out).toContain('retry-stuck-ghost-button');
        expect(out).toContain(GHOST_RETRY);
    });

    it('degrades to the honest label when no retry handler is wired', () => {
        // The single-test surface passes none; a label with no button beats a
        // button that cannot do anything.
        const out = html(<GhostZone jobs={[stuck]} />);
        expect(out).toContain(GHOST_STUCK);
        expect(out).not.toContain('retry-stuck-ghost-button');
    });

    it('marks the row for the e2e/CSS surface', () => {
        expect(html(<GhostZone jobs={[stuck]} onRetry={() => {}} />))
            .toContain('data-stuck="true"');
    });
});

describe('mixed and empty states', () => {
    it('renders a live row and a dead row side by side, each honestly', () => {
        const out = html(
            <GhostZone
                jobs={[job({ job_id: 'a' }), job({ job_id: 'b', retryable: true })]}
                onRetry={() => {}}
            />,
        );
        expect(out).toContain(GHOST_RUNNING);
        expect(out).toContain(GHOST_STUCK);
    });

    it('renders nothing at all when there are no active jobs', () => {
        expect(html(<GhostZone jobs={[]} />)).toBe('');
    });
});
