/**
 * D7 — the transcribing ghosts: one honest row per in-flight document (B3
 * active_jobs), spinner + state copy + ticking elapsed (running only —
 * queued shows none; NO fabricated ETA, ever). Collapses beyond 4.
 *
 * [2026-09-10] A ghost can now END. Before this, a document whose worker had
 * overrun or been orphaned spun here forever with the same reassuring
 * «קוראת עמוד אחר עמוד…», and it was the only row on the dashboard with no
 * identifier and therefore no action. It gets both — but ONLY on the server's
 * word (`retryable`, computed from the same LIV-1 rule the reaper uses). This
 * component never decides that a spinner has been going "too long": a
 * client-side threshold would be a guess, and guessing here means telling a
 * teacher her document is broken while it is quietly finishing.
 */
'use client';

import { useEffect, useState } from 'react';

import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    GHOST_MORE_QUEUED,
    GHOST_QUEUED,
    GHOST_RETRY,
    GHOST_RUNNING,
    GHOST_STUCK,
    GHOST_STUCK_HINT,
    NO_FILENAME,
    ZONE_GHOSTS_SUB,
    ZONE_GHOSTS_TITLE,
} from '@/copy/batch';
import { formatElapsed } from '@/utils/batch-dashboard';
import type { ActiveJobItem } from '@/types/batch';

const VISIBLE = 4;

const SHIMMER_STYLE: React.CSSProperties = {
    backgroundImage:
        'linear-gradient(90deg, transparent 0%, rgba(141,180,245,.09) 50%, transparent 100%)',
    backgroundSize: '200% 100%',
};

export function GhostZone({
    jobs,
    onRetry,
    retryBusy,
}: {
    jobs: ActiveJobItem[];
    /** Optional: the single-test surface passes no retry, and then a stuck
     *  ghost simply renders its honest label without an action. */
    onRetry?: (jobId: string) => void;
    retryBusy?: ReadonlySet<string>;
}) {
    // The clock only needs to tick for rows that show one, and a stuck row
    // shows none — so a dashboard whose only ghost has overrun stops
    // re-rendering every second instead of animating a number nobody reads.
    const anyTicking = jobs.some((j) => j.state === 'running' && !j.retryable);
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        if (!anyTicking) return;
        const t = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(t);
    }, [anyTicking]);

    if (jobs.length === 0) return null;
    const visible = jobs.slice(0, VISIBLE);
    const hidden = jobs.length - visible.length;

    return (
        <ZoneCard
            testId="zone-ghosts"
            dotClass="bg-batch-blue"
            title={ZONE_GHOSTS_TITLE(jobs.length)}
            sub={ZONE_GHOSTS_SUB}
        >
            <div className="border-t border-batch-line-soft">
                {visible.map((j) => {
                    const stuck = Boolean(j.retryable);
                    return (
                        <div
                            key={j.job_id}
                            className="relative flex flex-wrap items-center gap-3.5 overflow-hidden border-b border-batch-line-soft px-5 py-2.5 last:border-b-0"
                            data-testid="ghost-row"
                            data-stuck={stuck ? 'true' : undefined}
                        >
                            {!stuck && (
                                <div
                                    className="pointer-events-none absolute inset-0 motion-safe:animate-shimmer"
                                    style={SHIMMER_STYLE}
                                />
                            )}
                            {stuck ? (
                                <span className="h-[15px] w-[15px] flex-none rounded-full border-2 border-batch-amber-line bg-batch-amber-soft" />
                            ) : (
                                <span className="h-[15px] w-[15px] flex-none motion-safe:animate-spin rounded-full border-2 border-[#C6D8F7] border-t-batch-blue" />
                            )}
                            <span className="min-w-[180px] flex-1 font-medium text-batch-muted">
                                {j.filename ?? NO_FILENAME}
                            </span>
                            <span className="text-[12.5px] text-batch-muted">
                                {stuck
                                    ? GHOST_STUCK
                                    : j.state === 'running'
                                        ? GHOST_RUNNING
                                        : GHOST_QUEUED}
                            </span>
                            {/* The elapsed clock is suppressed once the row is
                                known dead: a number still counting up next to
                                «לוקח יותר מדי זמן» would say the work goes on. */}
                            {!stuck && j.state === 'running' && j.started_at && (
                                <span
                                    className="font-mono text-[11.5px] text-batch-blue-ink"
                                    dir="ltr"
                                >
                                    {formatElapsed(j.started_at, now)}
                                </span>
                            )}
                            {stuck && onRetry && (
                                <button
                                    onClick={() => onRetry(j.job_id)}
                                    disabled={retryBusy?.has(j.job_id)}
                                    className="rounded-[10px] border-[1.5px] border-batch-amber-line px-3 py-1.5 text-[12.5px] font-semibold text-batch-amber-ink hover:bg-white disabled:opacity-45"
                                    data-testid="retry-stuck-ghost-button"
                                >
                                    {GHOST_RETRY}
                                </button>
                            )}
                            {stuck && (
                                <span className="w-full text-[12px] text-batch-faint">
                                    {GHOST_STUCK_HINT}
                                </span>
                            )}
                        </div>
                    );
                })}
                {hidden > 0 && (
                    <div className="px-5 py-2.5 text-center text-[12.5px] text-batch-faint">
                        {GHOST_MORE_QUEUED(hidden)}
                    </div>
                )}
            </div>
        </ZoneCard>
    );
}
