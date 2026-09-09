'use client';

import { WELCOME_BODY } from '@/copy/onboarding';

/**
 * Step 1. Prose only — no input, nothing to commit. It exists to say what Vivi
 * is and, in its second paragraph, to state the product's one non-negotiable
 * (the teacher decides) before she is asked for anything.
 */
export function WelcomeStep() {
    return (
        <div className="space-y-4 text-gray-600">
            {WELCOME_BODY.map((paragraph, i) => (
                <p
                    key={i}
                    className={
                        i === 1
                            ? 'text-base leading-relaxed font-medium text-gray-800'
                            : 'text-base leading-relaxed'
                    }
                >
                    {paragraph}
                </p>
            ))}
        </div>
    );
}
