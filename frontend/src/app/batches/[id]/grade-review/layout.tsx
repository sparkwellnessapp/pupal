'use client';

/**
 * The grade-review segment's layout — mounts once per route ENTRY and survives
 * sibling `[gradedTestId]` navigations.
 *
 * ── WHY THE PATH IS `grade-review/` AND NOT `review/` ─────────────────────
 * PR spec §2 asks for `batches/[batchId]/review/[gradedTestId]`. That route
 * CANNOT BE BUILT: `batches/[id]/review/[transcriptionId]` already exists (the
 * transcription gate), and Next refuses two different slug names at one
 * position — twice over, `[id]` vs `[batchId]` and `[transcriptionId]` vs
 * `[gradedTestId]`. Renaming the existing route would break its deep links and
 * the standing freeze guard, so the new segment takes its own name. It also
 * reads better: §6 makes תמלול and בדיקת ציונים distinct product terms, and
 * they should not share a URL. Reported as a spec bug.
 *
 * ── WHY THE CURSOR LIVES HERE ────────────────────────────────────────────
 * The App Router keys page segments by their dynamic-param VALUE, so
 * /grade-review/a → /grade-review/b REMOUNTS the page component. A page-held
 * cursor resets silently and the order recomputes from post-approval state —
 * the exact mid-review reshuffle the freeze rule forbids, proven empirically in
 * the transcription flow before its holder existed. LAYOUTS persist across
 * sibling navigations and remount on fresh entry, which is precisely the
 * lifetime the frozen cursor needs.
 */

import { useParams } from 'next/navigation';
import type { ReactNode } from 'react';

import { GradeReviewProvider } from '@/components/grade-review/GradeReviewContext';

export default function GradeReviewLayout({ children }: { children: ReactNode }) {
    const params = useParams<{ id: string }>();
    return <GradeReviewProvider batchId={params.id}>{children}</GradeReviewProvider>;
}
