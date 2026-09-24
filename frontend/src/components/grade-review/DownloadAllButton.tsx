'use client';

import type { ReactNode } from 'react';
import { Loader2 } from 'lucide-react';

import { DASH_DOWNLOAD, DASH_DOWNLOAD_PREPARING } from '@/copy/grade-review';

/**
 * The download-all button — ONE component for both places that offer the ZIP
 * (the dashboard header mid-session, and `SignedCompletion` at the end), so the
 * label, the in-flight state and its announcement cannot drift between them.
 *
 * DL-1: while busy it shows the spinner, `aria-busy`, and a disabled look.
 * It is `aria-disabled`, not `disabled`: a native disabled button drops focus
 * and swallows the click silently, and the real guard is the controller's flag
 * anyway (`zip-download.ts`, DL-2) — this onClick check only keeps the
 * confirmation modal from reopening behind a download already under way.
 *
 * DL-5: the label does not change while working. The spinner sits in a slot
 * that is reserved in BOTH states, so the button's width never jumps.
 */
export function DownloadAllButton({ busy, onClick, className = '', children }: {
    busy: boolean;
    onClick: () => void;
    className?: string;
    /** Trailing content — the header's count chip. */
    children?: ReactNode;
}) {
    return (
        <>
            <button
                type="button"
                data-download
                aria-busy={busy}
                aria-disabled={busy || undefined}
                onClick={() => { if (!busy) onClick(); }}
                className={[
                    'inline-flex items-center gap-2',
                    className,
                    busy ? 'cursor-wait opacity-60' : '',
                ].join(' ')}
            >
                <span
                    aria-hidden="true"
                    data-download-slot
                    className="inline-flex h-4 w-4 flex-none items-center justify-center"
                >
                    {busy ? <Loader2 size={16} className="motion-safe:animate-spin" /> : null}
                </span>
                {DASH_DOWNLOAD}
                {children}
            </button>
            {/* Rendered in both states: a live region that appears together
                with its text is not reliably announced. */}
            <span role="status" aria-live="polite" className="sr-only">
                {busy ? DASH_DOWNLOAD_PREPARING : ''}
            </span>
        </>
    );
}
