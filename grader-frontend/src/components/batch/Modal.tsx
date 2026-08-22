/**
 * F8/R9 — the ONE dialog primitive for the batch surfaces: role="dialog",
 * aria-modal, focus trap (Tab cycles inside), Esc closes, initial focus on
 * the element marked data-autofocus (else the panel). ConfirmAcceptModal and
 * the R4 interstitial migrate onto this (P3); the census's three parallel
 * hand-rolled modals end here.
 */
'use client';

import { useEffect, useRef, type ReactNode } from 'react';

const FOCUSABLE =
    'a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex="-1"])';

export function Modal({
    open,
    onClose,
    labelledBy,
    children,
    testId,
}: {
    open: boolean;
    onClose: () => void;
    /** id of the element serving as the dialog's accessible name. */
    labelledBy?: string;
    children: ReactNode;
    testId?: string;
}) {
    const panelRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        if (!open) return;
        const panel = panelRef.current;
        if (!panel) return;

        const initial =
            panel.querySelector<HTMLElement>('[data-autofocus]') ??
            panel.querySelector<HTMLElement>(FOCUSABLE) ??
            panel;
        initial.focus();

        const onKeyDown = (e: KeyboardEvent) => {
            if (e.key === 'Escape') {
                e.stopPropagation();
                onClose();
                return;
            }
            if (e.key !== 'Tab') return;
            const focusables = Array.from(
                panel.querySelectorAll<HTMLElement>(FOCUSABLE),
            ).filter((el) => el.offsetParent !== null || el === document.activeElement);
            if (focusables.length === 0) {
                e.preventDefault();
                return;
            }
            const first = focusables[0];
            const last = focusables[focusables.length - 1];
            const active = document.activeElement as HTMLElement | null;
            if (e.shiftKey && (active === first || !panel.contains(active))) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && (active === last || !panel.contains(active))) {
                e.preventDefault();
                first.focus();
            }
        };
        // Capture phase: background key handlers (R3's page-level keymap)
        // must never see keys while a modal is open.
        document.addEventListener('keydown', onKeyDown, true);
        return () => document.removeEventListener('keydown', onKeyDown, true);
    }, [open, onClose]);

    if (!open) return null;

    return (
        <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
            onClick={onClose}
            data-testid={testId}
        >
            <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={labelledBy}
                tabIndex={-1}
                className="w-full max-w-md rounded-zone border border-batch-line bg-white p-6 shadow-zone outline-none"
                onClick={(e) => e.stopPropagation()}
            >
                {children}
            </div>
        </div>
    );
}
