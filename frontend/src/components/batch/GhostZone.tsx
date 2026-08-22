/**
 * D7 — the transcribing ghosts: one honest row per in-flight document (B3
 * active_jobs), spinner + state copy + ticking elapsed (running only —
 * queued shows none; NO fabricated ETA, ever). Collapses beyond 4.
 */
'use client';

import { useEffect, useState } from 'react';

import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    GHOST_MORE_QUEUED,
    GHOST_QUEUED,
    GHOST_RUNNING,
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

export function GhostZone({ jobs }: { jobs: ActiveJobItem[] }) {
    const anyRunning = jobs.some((j) => j.state === 'running');
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        if (!anyRunning) return;
        const t = setInterval(() => setNow(new Date()), 1000);
        return () => clearInterval(t);
    }, [anyRunning]);

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
                {visible.map((j, i) => (
                    <div
                        key={`${j.filename ?? ''}-${i}`}
                        className="relative flex flex-wrap items-center gap-3.5 overflow-hidden border-b border-batch-line-soft px-5 py-2.5 last:border-b-0"
                        data-testid="ghost-row"
                    >
                        <div
                            className="pointer-events-none absolute inset-0 motion-safe:animate-shimmer"
                            style={SHIMMER_STYLE}
                        />
                        <span className="h-[15px] w-[15px] flex-none motion-safe:animate-spin rounded-full border-2 border-[#C6D8F7] border-t-batch-blue" />
                        <span className="min-w-[180px] flex-1 font-medium text-batch-muted">
                            {j.filename ?? NO_FILENAME}
                        </span>
                        <span className="text-[12.5px] text-batch-muted">
                            {j.state === 'running' ? GHOST_RUNNING : GHOST_QUEUED}
                        </span>
                        {j.state === 'running' && j.started_at && (
                            <span className="font-mono text-[11.5px] text-batch-blue-ink" dir="ltr">
                                {formatElapsed(j.started_at, now)}
                            </span>
                        )}
                    </div>
                ))}
                {hidden > 0 && (
                    <div className="px-5 py-2.5 text-center text-[12.5px] text-batch-faint">
                        {GHOST_MORE_QUEUED(hidden)}
                    </div>
                )}
            </div>
        </ZoneCard>
    );
}
