'use client';

import { PROGRESS_LABEL } from '@/copy/onboarding';

/**
 * The onboarding progress bar — turquoise, from the existing `primary` ramp
 * (primary.400 #2dd4bf → primary.600 #0d9488). No new color token: the ramp is
 * already the product's turquoise and a second definition of it would be the
 * duplicate the `grade` palette's comment warns about.
 *
 * `bg-gradient-to-l` because the document is RTL — the bar must grow from the
 * right, the direction the teacher reads.
 */
export function ProgressBar({ step, total }: { step: number; total: number }) {
    const pct = Math.max(0, Math.min(100, (step / total) * 100));

    return (
        <div
            className="h-1.5 w-full overflow-hidden rounded-full bg-surface-200"
            role="progressbar"
            aria-label={PROGRESS_LABEL}
            aria-valuenow={step}
            aria-valuemin={0}
            aria-valuemax={total}
            data-testid="onboarding-progress"
        >
            <div
                className="h-full rounded-full bg-gradient-to-l from-primary-400 to-primary-600
                           transition-[width] duration-500 ease-out motion-reduce:transition-none"
                style={{ width: `${pct}%` }}
            />
        </div>
    );
}
