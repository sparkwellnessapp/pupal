'use client';

/**
 * §5.3B — three lines, on her FIRST batch only.
 *
 * It answers the question the transcription stage begs and no screen was
 * answering: why is a machine typing out my students' work, and what is my part
 * in it. The third line is the load-bearing one — the marks exist so the grade
 * lands on what the student actually wrote.
 *
 * ── WHY A SERVER FACT AND NOT localStorage ──────────────────────────────
 * "First batch" is a fact about her ACCOUNT, so it is read from the server
 * (`BatchDetailResponse.is_first_batch`). Browser storage would show the
 * explanation again on her school desktop and hide it on a cleared cache.
 * Storage is used for exactly one thing: whether she has DISMISSED it in this
 * session, which is a per-tab convenience and nothing more. A storage failure
 * leaves the panel open, which is the harmless direction.
 */

import { useEffect, useState } from 'react';

import { EXPLAINER_DISMISS, EXPLAINER_LINES } from '@/copy/batch';

const dismissKey = (batchId: string) => `vivi-explainer-dismissed:${batchId}`;

export function FirstBatchExplainer({ batchId }: { batchId: string }) {
    const [dismissed, setDismissed] = useState(false);

    // Read after mount, never during render: the server render has no
    // sessionStorage, and reading one during render makes the two disagree.
    useEffect(() => {
        try {
            if (sessionStorage.getItem(dismissKey(batchId)) === '1') setDismissed(true);
        } catch { /* storage unavailable → the panel stays open */ }
    }, [batchId]);

    if (dismissed) return null;

    const dismiss = () => {
        setDismissed(true);
        try { sessionStorage.setItem(dismissKey(batchId), '1'); } catch { /* no-op */ }
    };

    return (
        <div
            data-testid="first-batch-explainer"
            className="rounded-zone border border-batch-teal-soft bg-batch-teal-soft/40 px-5 py-4"
        >
            <ul className="space-y-1 text-[14px] leading-relaxed text-batch-ink">
                {EXPLAINER_LINES.map((line) => (
                    <li key={line}>{line}</li>
                ))}
            </ul>
            <button
                type="button"
                onClick={dismiss}
                className="mt-2.5 text-[13px] font-semibold text-batch-teal-ink hover:underline"
                data-testid="explainer-dismiss"
            >
                {EXPLAINER_DISMISS}
            </button>
        </div>
    );
}
