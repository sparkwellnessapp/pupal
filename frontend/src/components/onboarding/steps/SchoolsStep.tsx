'use client';

import { SchoolCombobox } from '@/components/onboarding/SchoolCombobox';
import type { PickedSchool } from '@/lib/onboarding';

/**
 * Step 3 — the only skippable step (D7).
 *
 * The skip affordance itself lives in the dialog footer, beside «הבא», because
 * skipping is a navigation decision and the footer is where navigation lives.
 * Skipping still COMMITS the (possibly empty) list: it is an answer — "none of
 * these yet" — not an absence, and committing it means a teacher who skips and
 * comes back is not asked to re-clear anything.
 */
export function SchoolsStep({
    picked,
    onChange,
}: {
    picked: PickedSchool[];
    onChange: (next: PickedSchool[]) => void;
}) {
    return <SchoolCombobox picked={picked} onChange={onChange} />;
}
