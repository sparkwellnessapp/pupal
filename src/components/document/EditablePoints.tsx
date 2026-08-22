'use client';

import { useEffect, useRef, useState } from 'react';
import { safeParseFloat } from '@/utils/rubric-transform';
import { formatPoints } from '@/utils/rubric-display';

/**
 * EditablePoints (PR-5 S2) — the points chip.
 *
 * At rest it's a ledger number (`tabular-nums`, E-3), not an input box. Click (or
 * focus + Enter/Space) opens a number input in place. Coercion goes through the
 * existing `safeParseFloat` (parse) and `formatPoints` (display) — NEVER raw
 * `parseFloat`/`toFixed`, which is how the Decimal type-lie white-screened review.
 *
 *   - commit on blur or Enter; Enter also fires `onEnterCommit` so a table can
 *     advance focus down the points column (E-5 keyboard flow);
 *   - Escape cancels and restores;
 *   - `changed` toggles the cascade-glow class (E-3) — the CSS lives in globals.css
 *     and collapses to instant under `prefers-reduced-motion`.
 */

/**
 * Coerce a raw input string to a valid, non-negative points number — the ONE
 * coercion path (never raw parseFloat). Exported so the string-wire seatbelt cases
 * are unit-tested without a DOM. `safeParseFloat` already handles the Decimal
 * string ("12.0" → 12) and garbage (→ 0); we only add the ≥0 clamp the editor
 * requires.
 */
export function coercePointsInput(raw: string | number): number {
    const n = safeParseFloat(raw);
    return n < 0 ? 0 : n;
}

interface EditablePointsProps {
    value: number;
    onCommit: (next: number) => void;
    /** Accessible name, e.g. "ניקוד סעיף א — לחצי לעריכה". Required (a11y default). */
    ariaLabel: string;
    /** Fired after an Enter-commit so the owner can move focus to the next row. */
    onEnterCommit?: () => void;
    /** Read-only render (e.g. a parent's cascaded sum — teacher edits leaves). */
    readOnly?: boolean;
    /** E-3: this chip's value just changed via cascade → glow. */
    changed?: boolean;
    className?: string;
}

export function EditablePoints({
    value,
    onCommit,
    ariaLabel,
    onEnterCommit,
    readOnly = false,
    changed = false,
    className = '',
}: EditablePointsProps) {
    const [editing, setEditing] = useState(false);
    const ref = useRef<HTMLInputElement>(null);

    useEffect(() => {
        if (editing && ref.current) {
            ref.current.focus();
            ref.current.select();
        }
    }, [editing]);

    const startEdit = () => { if (!readOnly) setEditing(true); };

    const commit = (raw: string): number => {
        setEditing(false);
        const clamped = coercePointsInput(raw);
        if (clamped !== value) onCommit(clamped);
        return clamped;
    };

    const base = `inline-block min-w-[2.5rem] text-center tabular-nums rounded px-1.5 py-0.5 ${changed ? 'points-cascade-glow' : ''}`;

    if (editing) {
        return (
            <input
                ref={ref}
                type="number"
                min={0}
                step={0.25}
                defaultValue={value}
                dir="ltr"
                aria-label={ariaLabel}
                onBlur={(e) => commit(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        commit((e.target as HTMLInputElement).value);
                        onEnterCommit?.();
                    } else if (e.key === 'Escape') {
                        e.preventDefault();
                        (e.target as HTMLInputElement).value = String(value);
                        setEditing(false);
                    }
                }}
                className={`w-16 text-center tabular-nums bg-white border border-primary-300 rounded px-1.5 py-0.5 outline-none focus:ring-2 focus:ring-primary-200 ${className}`}
            />
        );
    }

    if (readOnly) {
        return <span className={`${base} text-surface-700 ${className}`} aria-label={ariaLabel}>{formatPoints(value)}</span>;
    }

    return (
        <button
            type="button"
            onClick={startEdit}
            aria-label={ariaLabel}
            className={`${base} font-medium text-surface-800 hover:bg-primary-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-200 transition-colors ${className}`}
        >
            {formatPoints(value)}
        </button>
    );
}
