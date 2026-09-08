'use client';

import { useId, useState } from 'react';

import {
    PV_TOGGLE, PV_TOGGLE_INFO, PV_TOGGLE_INFO_LABEL,
} from '@/copy/grade-review';

/**
 * P1 — «פירוט קריטריונים בדף המשוב», with its (i).
 *
 * THE WHOLE POINT OF THE (i) IS THE FIRST SENTENCE: this switch is per BATCH,
 * reached from a per-TEST screen. A teacher who flips it while looking at דן's
 * exam changes what thirty students receive, and nothing else on this page
 * behaves that way. The explainer is §6 verbatim for that reason, and it opens
 * on hover AND focus — a keyboard user must be able to read it before deciding.
 *
 * It is a real `<button role="switch">`, not a styled div: `aria-checked` is
 * what a screen reader announces, and the mockup's bare `<span onclick>` is
 * unreachable by keyboard. The visual is the mockup's pill exactly.
 */

export interface BreakdownToggleProps {
    checked: boolean;
    onChange: (next: boolean) => void;
    /** In flight — the switch shows the value it is moving to, not a spinner. */
    pending?: boolean;
}

export function BreakdownToggle({ checked, onChange, pending = false }: BreakdownToggleProps) {
    const tipId = useId();
    const [tipOpen, setTipOpen] = useState(false);

    return (
        <span className="inline-flex items-center gap-2.5 rounded-full border
            border-grade-line bg-grade-card px-3 py-1.5 text-gr-rtl text-grade-ink-2">
            <button
                type="button"
                role="switch"
                aria-checked={checked}
                data-breakdown-toggle
                data-checked={checked ? 'on' : 'off'}
                disabled={pending}
                onClick={() => onChange(!checked)}
                className={[
                    'relative h-5 w-9 flex-none rounded-full transition-colors',
                    'focus-visible:outline focus-visible:outline-2',
                    'focus-visible:outline-offset-2 focus-visible:outline-primary-600',
                    checked ? 'bg-primary-600' : 'bg-grade-pencil-2',
                    pending ? 'cursor-wait opacity-70' : 'cursor-pointer',
                ].join(' ')}
            >
                {/* The knob. `start-0.5` + a NEGATIVE translate: the document is
                    RTL, so "on" moves the knob to the LEFT, as the mockup does. */}
                <span
                    aria-hidden
                    className={[
                        'absolute top-0.5 start-0.5 h-4 w-4 rounded-full bg-white',
                        'transition-transform motion-reduce:transition-none',
                        checked ? '-translate-x-4' : 'translate-x-0',
                    ].join(' ')}
                />
            </button>

            <span>{PV_TOGGLE}</span>

            <span
                className="relative inline-grid"
                onMouseEnter={() => setTipOpen(true)}
                onMouseLeave={() => setTipOpen(false)}
            >
                <button
                    type="button"
                    aria-label={PV_TOGGLE_INFO_LABEL}
                    aria-describedby={tipOpen ? tipId : undefined}
                    aria-expanded={tipOpen}
                    data-breakdown-info
                    onFocus={() => setTipOpen(true)}
                    onBlur={() => setTipOpen(false)}
                    onClick={() => setTipOpen((open) => !open)}
                    className="grid h-info-i w-info-i place-items-center rounded-full border
                        border-grade-pencil-2 text-gr-sm text-grade-pencil
                        focus-visible:outline focus-visible:outline-2
                        focus-visible:outline-offset-2 focus-visible:outline-primary-600"
                >
                    i
                </button>
                {tipOpen ? (
                    <span
                        id={tipId}
                        role="tooltip"
                        data-breakdown-tip
                        className="absolute top-6 start-tip-nudge z-20 w-tip rounded-grade-sm
                            border border-grade-line bg-grade-card px-3 py-2.5 text-start
                            text-gr-rtl text-grade-ink-2 shadow-grade"
                    >
                        {PV_TOGGLE_INFO}
                    </span>
                ) : null}
            </span>
        </span>
    );
}
