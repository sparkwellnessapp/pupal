'use client';

import { useEffect, useRef } from 'react';

import type { DownloadSummary } from '@/utils/grade-dashboard';
import {
    DL_BODY_ALL, DL_BODY_PARTIAL, DL_CANCEL, DL_CONFIRM, DL_FAILED, DL_NAMING,
    DL_NOTHING, DL_STALE, DL_TITLE,
} from '@/copy/grade-review';

/**
 * The download confirmation (D9) — approved-only, and it SAYS SO BEFORE IT
 * DOES ANYTHING.
 *
 * This modal exists for one sentence: «יורדו רק המבחנים שאישרת וחתמת». A
 * teacher who clicks download on a thirty-test batch and receives a ZIP of
 * eleven has been quietly lied to at the moment she trusted the product most.
 * The exclusions are named and counted here, before the click that matters,
 * not discovered afterwards in a folder.
 *
 * Stale exams are called out separately from unapproved ones because the fix
 * differs: an unapproved test needs reviewing, a stale one needs re-signing.
 * Collapsing them into one number would tell her to do the wrong thing.
 */

export interface DownloadModalProps {
    summary: DownloadSummary;
    /** Where the numbers came from: the server's manifest, or the feed while
     *  the manifest is still loading (or failed — a display path degrades). */
    source?: 'manifest' | 'feed';
    onConfirm: () => void;
    onClose: () => void;
}

export function DownloadModal({
    summary, source = 'feed', onConfirm, onClose,
}: DownloadModalProps) {
    const confirmRef = useRef<HTMLButtonElement | null>(null);

    useEffect(() => {
        confirmRef.current?.focus();
        const onKey = (event: KeyboardEvent) => {
            // Captured, so the dashboard's own key handling never runs behind
            // an open modal.
            if (event.key === 'Escape') { event.stopPropagation(); onClose(); }
        };
        document.addEventListener('keydown', onKey, true);
        return () => document.removeEventListener('keydown', onKey, true);
    }, [onClose]);

    const nothing = summary.included === 0;
    const excluded = summary.excludedNotApproved;

    return (
        <div
            data-download-modal
            data-download-source={source}
            role="dialog"
            aria-modal="true"
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
            className="fixed inset-0 z-[90] grid place-items-center bg-grade-ink/35 px-4"
        >
            <div className="w-full max-w-modal rounded-modal bg-grade-card px-6 py-6
                shadow-grade">
                <h3 className="text-gr-h2 text-grade-ink">{DL_TITLE(summary.included)}</h3>

                <p className="mt-2 text-gr-body text-grade-ink-2">
                    {nothing ? DL_NOTHING
                        : excluded > 0 ? DL_BODY_PARTIAL(excluded)
                            : DL_BODY_ALL}
                </p>

                {summary.excludedFailed > 0 ? (
                    <p data-failed-line className="mt-2 text-gr-meta text-grade-pencil">
                        {DL_FAILED(summary.excludedFailed)}
                    </p>
                ) : null}

                {summary.excludedStale > 0 ? (
                    <p data-stale-line className="mt-2 rounded-grade-ctl border
                        border-grade-amber-200 bg-grade-amber-50 px-3 py-2 text-gr-meta
                        text-grade-amber-ink">
                        {DL_STALE(summary.excludedStale)}
                    </p>
                ) : null}

                {nothing ? null : (
                    <p className="mt-2 text-gr-meta text-grade-pencil">{DL_NAMING}</p>
                )}

                <div className="mt-5 flex gap-2.5">
                    {nothing ? null : (
                        <button
                            ref={confirmRef}
                            type="button"
                            data-download-confirm
                            onClick={onConfirm}
                            className="rounded-grade-ctl border border-primary-600
                                bg-primary-600 px-4 py-2 text-gr-body font-medium text-white
                                hover:bg-primary-700"
                        >
                            {DL_CONFIRM(summary.included)}
                        </button>
                    )}
                    <button
                        type="button"
                        onClick={onClose}
                        className="rounded-grade-ctl border border-grade-line bg-grade-card
                            px-4 py-2 text-gr-body text-grade-ink hover:border-grade-pencil-2"
                    >
                        {DL_CANCEL}
                    </button>
                </div>
            </div>
        </div>
    );
}
