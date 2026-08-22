/**
 * F8 — the ONE chip primitive for the batch surfaces (dashboard, list,
 * review, upload). Kills the three parallel chip implementations the census
 * found (Q34). Rubric-domain chips are deliberately NOT migrated.
 * Styling follows the mockup's .chip recipe over the batch token set.
 */
import type { ReactNode } from 'react';

export type ChipHue = 'amber' | 'blue' | 'green' | 'red' | 'teal' | 'neutral';

const HUES: Record<ChipHue, string> = {
    amber: 'bg-batch-amber-soft text-batch-amber-ink',
    blue: 'bg-batch-blue-soft text-batch-blue-ink',
    green: 'bg-batch-green-soft text-batch-green-ink',
    red: 'bg-batch-red-soft text-batch-red-ink',
    teal: 'bg-batch-teal-soft text-batch-teal-ink',
    neutral: 'bg-surface-100 text-batch-muted',
};

export function StatusChip({
    hue,
    children,
    className = '',
    ...rest
}: {
    hue: ChipHue;
    children: ReactNode;
    className?: string;
} & React.HTMLAttributes<HTMLSpanElement>) {
    return (
        <span
            className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${HUES[hue]} ${className}`}
            {...rest}
        >
            {children}
        </span>
    );
}
