'use client';

import { READY_SUBTITLE, READY_TIPS } from '@/copy/onboarding';

/**
 * Step 5 — how to start, and the four things that make Vivi trustworthy rather
 * than merely fast. Three of the four are about the teacher's authority (review
 * before grading, approve what gets checked, every score is editable), because
 * that is the product's actual promise and the place to state it is before she
 * uses it for the first time.
 */
export function ReadyStep() {
    return (
        <div className="space-y-5">
            <p className="text-sm text-gray-500">{READY_SUBTITLE}</p>

            <ol className="space-y-4">
                {READY_TIPS.map((tip, i) => (
                    <li key={tip.title} className="flex gap-3">
                        <span
                            className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full
                                       bg-primary-100 text-sm font-semibold text-primary-700"
                            aria-hidden="true"
                        >
                            {i + 1}
                        </span>
                        <div className="space-y-0.5">
                            <p className="font-medium text-gray-900">{tip.title}</p>
                            <p className="text-sm leading-relaxed text-gray-600">{tip.body}</p>
                        </div>
                    </li>
                ))}
            </ol>
        </div>
    );
}
