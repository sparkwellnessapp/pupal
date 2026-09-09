'use client';

import { useEffect, useRef, useState } from 'react';
import { MoreHorizontal } from 'lucide-react';

import {
    RV_MANUAL_EDIT, RV_MANUAL_EDIT_HINT, RV_MORE_ACTIONS, RV_REGRADE,
    RV_REGRADE_HINT, RV_RETRY, RV_RETRY_HINT,
} from '@/copy/grade-review';

/**
 * The revision affordances, kept reachable (spec §2).
 *
 * "Existing GradedTestReviewPanel is replaced by ScopeSection+children; keep
 * its revision affordances (regrade / manual_edit / retry) reachable from the
 * review top bar's overflow, UNCHANGED." Replacing a surface must not quietly
 * delete the ways out of it: each of these extends the immutable chain
 * (LCY-2), and losing them would strand a failed grade or an approved test she
 * needs to reopen.
 *
 * They live in an OVERFLOW, not on the bar, because none of them is part of
 * reviewing — they are what she reaches for when reviewing is not the answer.
 *
 * Each is offered only where the chain permits it, so the menu never presents
 * an action the server will refuse:
 *   regrade      approved + leaf + STALE contract
 *   manual_edit  approved + leaf (any staleness)
 *   retry        failed + leaf
 */

export interface RevisionMenuProps {
    status: 'pending' | 'grading' | 'draft' | 'approved' | 'failed' | string;
    /** The rubric moved on since this grade — only then is a regrade offered. */
    contractStale: boolean;
    busy?: boolean;
    onRegrade: () => void;
    onManualEdit: () => void;
    onRetry: () => void;
}

export function RevisionMenu({
    status, contractStale, busy = false, onRegrade, onManualEdit, onRetry,
}: RevisionMenuProps) {
    const [open, setOpen] = useState(false);
    const ref = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!open) return;
        const onDocument = (event: MouseEvent) => {
            if (!ref.current?.contains(event.target as Node)) setOpen(false);
        };
        const onKey = (event: KeyboardEvent) => {
            // Esc closes the menu and stops there — the surface's own Esc
            // (release the pinned quote) must not also fire underneath it.
            if (event.key === 'Escape') { event.stopPropagation(); setOpen(false); }
        };
        document.addEventListener('mousedown', onDocument);
        document.addEventListener('keydown', onKey, true);
        return () => {
            document.removeEventListener('mousedown', onDocument);
            document.removeEventListener('keydown', onKey, true);
        };
    }, [open]);

    const actions = [
        status === 'approved' && contractStale
            && { key: 'regrade', label: RV_REGRADE, hint: RV_REGRADE_HINT, run: onRegrade },
        status === 'approved'
            && { key: 'manual', label: RV_MANUAL_EDIT, hint: RV_MANUAL_EDIT_HINT, run: onManualEdit },
        status === 'failed'
            && { key: 'retry', label: RV_RETRY, hint: RV_RETRY_HINT, run: onRetry },
    ].filter(Boolean) as { key: string; label: string; hint: string; run: () => void }[];

    // Nothing this chain permits — so no button at all. An overflow that opens
    // onto an empty list is a promise the surface cannot keep.
    if (actions.length === 0) return null;

    return (
        <div className="relative" ref={ref} data-revision-menu>
            <button
                type="button"
                aria-label={RV_MORE_ACTIONS}
                aria-haspopup="menu"
                aria-expanded={open}
                title={RV_MORE_ACTIONS}
                disabled={busy}
                onClick={() => setOpen((v) => !v)}
                className="grid h-verdict w-verdict place-items-center rounded-grade-ctl
                    border border-grade-line bg-grade-card text-grade-ink-2
                    hover:border-grade-pencil-2 disabled:opacity-40"
            >
                <MoreHorizontal size={16} />
            </button>

            {open ? (
                <div
                    role="menu"
                    className="absolute end-0 top-full z-50 mt-1 w-64 overflow-hidden
                        rounded-grade-ctl border border-grade-line bg-grade-card shadow-grade"
                >
                    {actions.map((action) => (
                        <button
                            key={action.key}
                            type="button"
                            role="menuitem"
                            data-revision-action={action.key}
                            onClick={() => { setOpen(false); action.run(); }}
                            className="block w-full px-3.5 py-2.5 text-start hover:bg-grade-bar"
                        >
                            <span className="block text-gr-body text-grade-ink">
                                {action.label}
                            </span>
                            <span className="block text-gr-meta text-grade-pencil">
                                {action.hint}
                            </span>
                        </button>
                    ))}
                </div>
            ) : null}
        </div>
    );
}
