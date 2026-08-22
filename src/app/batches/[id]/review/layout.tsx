'use client';

/**
 * The review segment's layout — mounts once per route ENTRY and survives
 * sibling [transcriptionId] navigations, which is what makes the Δ10 frozen
 * cursor real (pages remount per param value; layouts don't — see
 * BatchReviewContext for the rider-a finding that forced this).
 */

import { useParams } from 'next/navigation';
import type { ReactNode } from 'react';

import { BatchReviewProvider } from '@/components/batch-review/BatchReviewContext';

export default function BatchReviewLayout({ children }: { children: ReactNode }) {
    const params = useParams<{ id: string }>();
    return <BatchReviewProvider batchId={params.id}>{children}</BatchReviewProvider>;
}
