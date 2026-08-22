'use client';

import { useState, type ReactNode } from 'react';
import { ChevronLeft, ChevronDown } from 'lucide-react';

/**
 * A chevron + label disclosure (PR-5 S2, census D10). Used by solution blocks and
 * criterion breakdown rows.
 *
 * THE ONE RULE that kills the empty-expander noise class: the chevron (and the
 * whole toggle affordance) renders ONLY when there is content to reveal. A
 * disclosure with no children is just its label — no chevron pointing at nothing.
 *
 * RTL note: "expand" points inline-start (ChevronLeft in RTL) at rest, rotating to
 * ChevronDown when open.
 */

interface DisclosureRowProps {
    label: ReactNode;
    /** The revealed content. When null/false/undefined, NO chevron renders (D10). */
    children?: ReactNode;
    defaultOpen?: boolean;
    /** Accessible name for the toggle (e.g. "פתרון לדוגמה"). */
    toggleLabel?: string;
    className?: string;
}

export function DisclosureRow({ label, children, defaultOpen = false, toggleLabel, className = '' }: DisclosureRowProps) {
    const hasContent = children !== null && children !== undefined && children !== false;
    const [open, setOpen] = useState(defaultOpen);

    if (!hasContent) {
        // No content ⇒ label only, never an expander with nothing inside.
        return <div className={className} dir="rtl">{label}</div>;
    }

    return (
        <div className={className} dir="rtl">
            <button
                type="button"
                onClick={() => setOpen((o) => !o)}
                aria-expanded={open}
                aria-label={toggleLabel}
                className="flex items-center gap-1.5 text-sm text-surface-600 hover:text-surface-900 transition-colors"
            >
                {open
                    ? <ChevronDown size={15} className="flex-shrink-0" />
                    : <ChevronLeft size={15} className="flex-shrink-0" />}
                <span>{label}</span>
            </button>
            {open ? <div className="mt-2">{children}</div> : null}
        </div>
    );
}
