/**
 * F8/D2 — the honesty bar: one proportional segment per live state, with a
 * counted legend. Consumed by the dashboard (D2) and, mini, by the list
 * rows (L1). Segment order and hues follow the mockup (RTL start→:
 * approved · clean · eyes · moving[shimmer] · failed); zero-count segments
 * never render (barSegments already drops them); total 0 → nothing at all.
 * The shimmer runs under `motion-safe:` only — prefers-reduced-motion kills
 * it (D2 requirement, asserted by computed-style in Playwright).
 */
import type { BarSegment } from '@/utils/batch-dashboard';
import { SEGMENT_LABELS } from '@/copy/batch';

const SEG_BG: Record<BarSegment['kind'], string> = {
    approved: 'bg-batch-green',
    clean: 'bg-batch-seg-clean',
    eyes: 'bg-batch-seg-eyes',
    moving: 'bg-batch-seg-moving motion-safe:animate-shimmer',
    failed: 'bg-batch-seg-failed',
};

const SWATCH_BG: Record<BarSegment['kind'], string> = {
    approved: 'bg-batch-green',
    clean: 'bg-batch-seg-clean',
    eyes: 'bg-batch-seg-eyes',
    moving: 'bg-batch-seg-moving',
    failed: 'bg-batch-seg-failed',
};

const SHIMMER_STYLE: React.CSSProperties = {
    backgroundImage:
        'linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,.5) 50%, rgba(255,255,255,0) 100%)',
    backgroundSize: '200% 100%',
};

export function SegmentBar({
    segments,
    legend = true,
    compact = false,
}: {
    segments: BarSegment[];
    /** Hide for the list page's mini bar (L1). */
    legend?: boolean;
    compact?: boolean;
}) {
    const total = segments.reduce((n, s) => n + s.count, 0);
    if (total === 0) return null;

    return (
        <div data-testid="segment-bar">
            <div
                className={`flex ${compact ? 'h-2' : 'h-3.5'} gap-0.5 overflow-hidden rounded-full bg-batch-line-soft`}
            >
                {segments.map((s) => (
                    <div
                        key={s.kind}
                        data-kind={s.kind}
                        className={`h-full min-w-[6px] ${SEG_BG[s.kind]}`}
                        style={{
                            width: `${(s.count / total) * 100}%`,
                            ...(s.kind === 'moving' ? SHIMMER_STYLE : {}),
                        }}
                    />
                ))}
            </div>
            {legend && (
                <div className="mt-2 flex flex-wrap gap-4 text-xs text-batch-muted">
                    {segments.map((s) => (
                        <span key={s.kind} className="inline-flex items-center gap-1.5">
                            <span
                                className={`inline-block h-2 w-2 rounded-sm ${SWATCH_BG[s.kind]}`}
                            />
                            <b className="font-semibold text-batch-ink">{s.count}</b>{' '}
                            {SEGMENT_LABELS[s.kind]}
                        </span>
                    ))}
                </div>
            )}
        </div>
    );
}
