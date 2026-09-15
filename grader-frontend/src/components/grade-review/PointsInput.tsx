'use client';

import { useEffect, useRef, useState } from 'react';

import type { NumericPolicy } from '@/lib/pricing';
import { formatPoints } from '@/utils/points-display';
import {
    gridStepLabel, validateTypedAmount, type PointsEntryReason,
} from '@/utils/points-entry';
import {
    RV_POINTS_EDIT_TITLE,
    RV_POINTS_NEGATIVE,
    RV_POINTS_NOT_A_NUMBER,
    RV_POINTS_OFF_GRID,
    RV_POINTS_OVER_MAX_CHECK,
    RV_POINTS_OVER_MAX_CRITERION,
    RV_POINTS_TYPED_TITLE,
} from '@/copy/grade-review';

/**
 * [OD-R2] The points-granted figure, EDITABLE — on a check row and on the
 * criterion row (owner ruling 2026-09-13, reversing R-2's «no numeric input
 * anywhere in this module»).
 *
 * At rest it is the same number the surface always showed; a click (or Enter
 * on the focused row) turns it into a field. The amount she types is a
 * DECISION fed to the one pricer, not a second arithmetic — see
 * `lib/pricing.ts` and `verdict-cycle.ts` for the two rules that keep the
 * glyph and the number from ever disagreeing.
 *
 * ── THE REFUSAL IS LIVE (OD-4 a, owner ruling) ────────────────────────────
 * Every keystroke is checked against the row's ceiling and the rubric's grid.
 * An amount the server would refuse shows its reason at once, beside the
 * field — «לא ניתן להעניק X נקודות לקריטריון עם מקסימום Y נקודות» — and
 * cannot be committed while it stands: Enter does nothing, blur discards it.
 * Nothing is ever snapped to fit; the number is hers to correct.
 */

/** A criterion's total or a credit check's award. A tariff row has no field:
 *  a deduction is yes/no (ruling 2026-09-13) and is decided by its toggle. */
export type PointsTarget = 'criterion' | 'check';

export interface PointsInputProps {
    target: PointsTarget;
    /** The amount to EDIT. */
    value: string;
    /** What the resting figure reads, when it differs from `value`. */
    display?: string;
    max: string;
    policy: NumericPolicy;
    /** She typed this number herself. */
    typed: boolean;
    /** Red ink: she decided something different from Vivi — a verdict or a number. */
    overridden: boolean;
    readOnly?: boolean;
    editing: boolean;
    onEditingChange: (editing: boolean) => void;
    onCommit: (amount: string) => void;
    size?: 'row' | 'crit';
}

function message(
    reason: Exclude<PointsEntryReason, 'empty'>,
    target: PointsTarget,
    typedText: string,
    max: string,
    policy: NumericPolicy,
): string {
    const x = typedText.trim();
    switch (reason) {
        case 'over_max':
            return target === 'criterion'
                ? RV_POINTS_OVER_MAX_CRITERION(x, formatPoints(max))
                : RV_POINTS_OVER_MAX_CHECK(x, formatPoints(max));
        case 'off_grid':
            return RV_POINTS_OFF_GRID(x, gridStepLabel(policy));
        case 'negative':
            return RV_POINTS_NEGATIVE(x);
        case 'not_a_number':
        default:
            return RV_POINTS_NOT_A_NUMBER;
    }
}

export function PointsInput({
    target, value, display, max, policy, typed, overridden, readOnly = false,
    editing, onEditingChange, onCommit, size = 'row',
}: PointsInputProps) {
    const inputRef = useRef<HTMLInputElement | null>(null);
    const [text, setText] = useState(() => formatPoints(value));

    // Taking focus is an EVENT (entering edit mode), not a consequence of
    // rendering — the same rule the modal follows. The seed is re-read on
    // every entry so a stale draft from an abandoned edit never resurfaces.
    useEffect(() => {
        if (!editing) return;
        setText(formatPoints(value));
        const input = inputRef.current;
        if (input) {
            input.focus();
            input.select();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [editing]);

    // Her decision is TURQUOISE (ruling 2026-09-13); red means ✗ now.
    const numberTone = overridden ? 'font-medium text-primary-700' : 'text-grade-pencil';
    const numberSize = size === 'crit' ? 'text-gr-crit' : 'text-gr-num';
    const resting = (
        <>
            {formatPoints(display ?? value)}
            <small className={size === 'crit' ? 'text-gr-meta text-grade-pencil-2' : 'text-gr-sm text-grade-pencil-2'}>
                {' '}/ {formatPoints(max)}
            </small>
        </>
    );

    if (readOnly) {
        return (
            <span
                data-points-target={target}
                data-points-typed={typed ? 'true' : 'false'}
                className={`${numberSize} font-light leading-none ${numberTone}`}
            >
                {resting}
            </span>
        );
    }

    if (!editing) {
        return (
            <button
                type="button"
                title={typed ? RV_POINTS_TYPED_TITLE : RV_POINTS_EDIT_TITLE}
                data-points-target={target}
                data-points-typed={typed ? 'true' : 'false'}
                data-points-editing="false"
                onClick={(event) => { event.stopPropagation(); onEditingChange(true); }}
                className={[
                    'rounded-grade-ctl px-1 -mx-1 text-left font-light leading-none',
                    'transition-colors hover:bg-primary-50 focus-visible:outline-none',
                    'focus-visible:ring-2 focus-visible:ring-primary-300',
                    numberSize, numberTone,
                    typed ? 'underline decoration-dotted underline-offset-4' : '',
                ].join(' ')}
            >
                {resting}
            </button>
        );
    }

    const verdict = validateTypedAmount(text, max, policy);
    const reason = verdict.ok || verdict.reason === 'empty' ? null : verdict.reason;

    const close = () => onEditingChange(false);
    const commit = () => {
        if (!verdict.ok) return false;
        if (verdict.value !== value) onCommit(verdict.value);
        close();
        return true;
    };

    return (
        <span
            className="relative inline-flex items-baseline"
            data-points-target={target}
            data-points-editing="true"
            // The row beneath focuses on click and the keymap acts on keys;
            // neither has business inside a field she is typing in.
            onClick={(event) => event.stopPropagation()}
            onMouseDown={(event) => event.stopPropagation()}
        >
            <input
                ref={inputRef}
                dir="ltr"
                type="text"
                inputMode="decimal"
                value={text}
                aria-invalid={reason !== null}
                aria-label={RV_POINTS_EDIT_TITLE}
                data-points-input={target}
                onChange={(event) => setText(event.target.value)}
                onKeyDown={(event) => {
                    if (event.key === 'Enter') {
                        event.preventDefault();
                        event.stopPropagation();
                        commit();                    // refused input stays open
                    } else if (event.key === 'Escape') {
                        event.preventDefault();
                        event.stopPropagation();
                        close();
                    }
                }}
                // Leaving the field commits a valid change and discards an
                // invalid one — a refused number is never written anywhere.
                onBlur={() => { if (!commit()) close(); }}
                className={[
                    'w-[3.6rem] rounded-grade-ctl border bg-grade-card px-1 py-0.5 text-left',
                    'font-light leading-none outline-none [font-variant-numeric:tabular-nums]',
                    numberSize, numberTone,
                    reason ? 'border-grade-red' : 'border-grade-line focus:border-primary-500',
                ].join(' ')}
            />
            <small className={size === 'crit' ? 'text-gr-meta text-grade-pencil-2' : 'text-gr-sm text-grade-pencil-2'}>
                {' '}/ {formatPoints(max)}
            </small>
            {reason ? (
                <span
                    role="alert"
                    dir="rtl"
                    data-points-error={reason}
                    className="absolute end-0 top-full z-20 mt-1.5 w-64 rounded-grade border
                        border-grade-red-line bg-grade-card px-3 py-2 text-start text-gr-meta
                        font-normal leading-snug text-grade-red shadow-lg"
                >
                    {message(reason, target, text, max, policy)}
                </span>
            ) : null}
        </span>
    );
}
