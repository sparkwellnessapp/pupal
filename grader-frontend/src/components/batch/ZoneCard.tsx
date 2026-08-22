/**
 * F8 — a dashboard zone: mockup's .zone.card + .zone-head anatomy (colored
 * dot · title · sub · actions slot · body). One shell for the identity wave,
 * clean panel, needs-eyes queue, ghosts, failed zone, and grading lane.
 */
import type { ReactNode } from 'react';

export function ZoneCard({
    dotClass,
    title,
    sub,
    actions,
    children,
    className = '',
    testId,
}: {
    dotClass?: string;
    title: ReactNode;
    sub?: ReactNode;
    actions?: ReactNode;
    children?: ReactNode;
    className?: string;
    testId?: string;
}) {
    return (
        <section
            data-testid={testId}
            className={`rounded-zone border border-batch-line bg-white shadow-zone ${className}`}
        >
            <div className="flex flex-wrap items-center justify-between gap-3.5 px-5 pb-3 pt-4">
                <div>
                    <div className="flex items-center gap-2.5 text-[16.5px] font-semibold text-batch-ink">
                        {dotClass && (
                            <span className={`h-2 w-2 rounded-full ${dotClass}`} />
                        )}
                        {title}
                    </div>
                    {sub && (
                        <div className="mt-0.5 text-[13px] text-batch-muted">{sub}</div>
                    )}
                </div>
                {actions && (
                    <div className="flex flex-wrap items-center gap-2.5">{actions}</div>
                )}
            </div>
            {children}
        </section>
    );
}
