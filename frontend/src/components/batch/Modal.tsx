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

const SIZES = {
    md: 'max-w-md',
    lg: 'max-w-2xl',
} as const;

export function Modal({
    open,
    onClose,
    labelledBy,
    children,
    testId,
    dismissible = true,
    size = 'md',
    backdropClassName = 'bg-black/50 backdrop-blur-sm',
}: {
    open: boolean;
    onClose: () => void;
    /** id of the element serving as the dialog's accessible name. */
    labelledBy?: string;
    children: ReactNode;
    testId?: string;
    /**
     * false ⇒ neither Esc nor a backdrop click closes it. For a dialog that is
     * a WALL rather than an interruption (onboarding): there is nothing behind
     * it the teacher may reach yet, so an accidental dismissal would drop her
     * into an app she has not been introduced to. The focus trap is unaffected.
     * Defaults true, so the three pre-existing callers are unchanged.
     */
    dismissible?: boolean;
    /** Panel width. 'md' is the original and the default. */
    size?: keyof typeof SIZES;
    /**
     * Scrim classes. Defaults to the original dark scrim, which is right for a
     * dialog INTERRUPTING a surface. A dialog that IS the surface (onboarding,
     * on its own route) passes a light one instead — black/50 over Vivi's cream
     * ground renders as muddy grey rather than as a dimmed Vivi.
     */
    backdropClassName?: string;
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
                // Swallowed either way: a non-dismissible dialog must not let
                // Esc reach a background handler while it is the only surface.
                e.stopPropagation();
                if (dismissible) onClose();
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
    }, [open, onClose, dismissible]);

    if (!open) return null;

    return (
        <div
            className={`fixed inset-0 z-50 flex items-center justify-center p-4 ${backdropClassName}`}
            onClick={dismissible ? onClose : undefined}
            data-testid={testId}
        >
            <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={labelledBy}
                tabIndex={-1}
                className={`w-full ${SIZES[size]} rounded-zone border border-batch-line bg-white p-6 shadow-zone outline-none`}
                onClick={(e) => e.stopPropagation()}
            >
                {children}
            </div>
        </div>
    );
}
