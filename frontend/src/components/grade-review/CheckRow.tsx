'use client';

import { useEffect, useRef } from 'react';

import type { Verdict } from '@/lib/pricing';
import { hasQuoteButton, type HighlightableCheck } from '@/utils/evidence-highlight';
import { formatPoints } from '@/utils/points-display';
import { VerdictButton, VERDICT_GLYPH } from './VerdictButton';
import {
    RV_CHIP_DISPUTED,
    RV_CHIP_FUZZY,
    RV_CHIP_NOT_FOUND,
    RV_COUNTED_OF,
    RV_NOTE_PLACEHOLDER,
    RV_ORIG_MINE,
    RV_ORIG_PREFIX,
    RV_ORIG_REVERT,
    RV_QUOTE,
    RV_QUOTE_TITLE,
} from '@/copy/grade-review';

/**
 * One check — the atomic thing she judges (R7).
 *
 * Grid `32px 1fr auto 52px`: verdict · text · quote button · tariff. The tariff
 * column is fixed so every number on the surface lines up in one rule down the
 * page; a ragged right edge is what makes a long checklist unscannable.
 *
 * WHAT IS DELIBERATELY ABSENT: the model's numeric confidence (OD5 — never
 * rendered, it invites her to manage the AI instead of reading the answer), the
 * model's prose reasoning (v5 has none; the check text plus `basis_he` IS the
 * reasoning), and any audit chip (reserved out of v1 by ruling R-8 — built when
 * the audit spec lands, not shipped dark).
 */

export interface CheckRowCheck extends HighlightableCheck {
    check_id: string;
    text: string;
    kind: 'required' | 'tariff' | 'note_only' | 'counted';
    /** The model's one-line Hebrew basis, rendered small under the text. */
    basis_he?: string;
    /**
     * VIVI'S verdict — the proposal, never overwritten.
     *
     * Named `aiVerdict`, not `verdict`: the model type carries BOTH (the
     * effective one arrives as the `effectiveVerdict` prop) and a bare
     * `verdict` here silently resolved to the EFFECTIVE value, so the
     * "הצעת ויוי" line struck through the teacher's own decision and claimed
     * it was Vivi's. Provenance is the one thing this row must not get wrong.
     */
    aiVerdict: Verdict;
    /** What that proposal was worth. */
    aiAwarded?: string;
    points?: string | null;
    tariff?: string | null;
    /** Counted checks: how many of the N uniform units were right. */
    unit_count?: number | null;
    units_correct?: number | null;
}

export interface CheckRowProps {
    check: CheckRowCheck;
    /** After the overlay. */
    effectiveVerdict: Verdict;
    overridden: boolean;
    /** The pricer's award for this check, and what it is out of. */
    awarded: string;
    outOf: string;
    focused: boolean;
    pinned: boolean;
    note: string | null;
    noteOpen: boolean;
    evidenceDisputed: boolean;
    onFocus: () => void;
    onHover: (hovering: boolean) => void;
    onCycle: () => void;
    onRevert: () => void;
    onPin: () => void;
    onNoteChange: (note: string) => void;
    onNoteClose: () => void;
}

export function CheckRow({
    check, effectiveVerdict, overridden, awarded, outOf, focused, pinned,
    note, noteOpen, evidenceDisputed,
    onFocus, onHover, onCycle, onRevert, onPin, onNoteChange, onNoteClose,
}: CheckRowProps) {
    const noteRef = useRef<HTMLInputElement | null>(null);

    useEffect(() => {
        if (noteOpen) noteRef.current?.focus();
    }, [noteOpen]);

    const chips = [
        check.quote_status === 'not_found'
            && { key: 'not_found', tone: 'look' as const, label: RV_CHIP_NOT_FOUND },
        check.quote_status === 'fuzzy'
            && { key: 'fuzzy', tone: 'look' as const, label: RV_CHIP_FUZZY },
        evidenceDisputed
            && { key: 'disputed', tone: 'red' as const, label: RV_CHIP_DISPUTED },
    ].filter(Boolean) as { key: string; tone: 'look' | 'red'; label: string }[];

    return (
        <div
            data-check-id={check.check_id}
            data-focused={focused ? 'true' : 'false'}
            data-overridden={overridden ? 'true' : 'false'}
            tabIndex={-1}
            onClick={onFocus}
            onMouseEnter={() => onHover(true)}
            onMouseLeave={() => onHover(false)}
            className={[
                'relative grid grid-cols-[32px_1fr_auto_52px] items-center gap-3',
                'border-t border-grade-line-2 px-3.5 py-2.5 outline-none transition-colors',
                focused
                    ? 'bg-primary-50 before:absolute before:inset-y-0 before:start-0'
                      + ' before:w-focus-rail before:bg-primary-600 before:content-[""]'
                    : 'hover:bg-grade-paper',
            ].join(' ')}
        >
            <VerdictButton
                verdict={effectiveVerdict}
                overridden={overridden}
                onCycle={onCycle}
            />

            <div className="self-start text-gr-body leading-snug">
                {check.text}
                {check.basis_he ? (
                    <span className="mt-0.5 block text-gr-meta text-grade-ink-2">
                        {check.basis_he}
                    </span>
                ) : null}

                {overridden ? (
                    <div className="mt-1.5 text-gr-label text-grade-pencil">
                        {RV_ORIG_PREFIX}{' '}
                        <s className="text-grade-pencil">
                            {VERDICT_GLYPH[check.aiVerdict]}
                            {check.aiAwarded == null
                                ? null
                                : ` · ${formatPoints(check.aiAwarded)}`}
                        </s>{' '}
                        → {RV_ORIG_MINE} ·{' '}
                        <button
                            type="button"
                            onClick={(e) => { e.stopPropagation(); onRevert(); }}
                            className="text-primary-700 underline underline-offset-link"
                        >
                            {RV_ORIG_REVERT}
                        </button>
                    </div>
                ) : null}

                {chips.length ? (
                    <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
                        {chips.map((chip) => (
                            <span
                                key={chip.key}
                                data-chip={chip.key}
                                className={[
                                    'whitespace-nowrap rounded-full border px-2.5 py-0.5 text-gr-chip',
                                    chip.tone === 'red'
                                        ? 'border-grade-red-line bg-grade-red-100 text-grade-red'
                                        : 'border-grade-amber-200 bg-grade-amber-100 text-grade-amber',
                                ].join(' ')}
                            >
                                <span
                                    aria-hidden="true"
                                    className={[
                                        'me-1.5 inline-block h-dot w-dot rounded-full relative top-px',
                                        chip.tone === 'red' ? 'bg-grade-red' : 'bg-grade-amber-dot',
                                    ].join(' ')}
                                />
                                {chip.label}
                            </span>
                        ))}
                    </div>
                ) : null}

                {noteOpen ? (
                    <div className="mt-1.5 border-s-2 border-grade-red ps-2 text-gr-body">
                        <input
                            ref={noteRef}
                            defaultValue={note ?? ''}
                            placeholder={RV_NOTE_PLACEHOLDER}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                                e.stopPropagation();
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    onNoteChange((e.target as HTMLInputElement).value);
                                }
                                if (e.key === 'Escape') onNoteClose();
                            }}
                            onBlur={(e) => onNoteChange(e.target.value)}
                            className="w-full border-0 border-b border-grade-line bg-transparent
                                py-0.5 outline-none"
                        />
                    </div>
                ) : note ? (
                    <div className="mt-1.5 border-s-2 border-grade-red ps-2 text-gr-body
                        text-grade-ink-2">
                        {note}
                    </div>
                ) : null}
                {check.kind === 'counted' && check.unit_count != null && check.units_correct != null ? (
                    <div className="mt-1 text-gr-meta text-grade-ink-2" data-testid="counted-of">
                        {RV_COUNTED_OF(check.units_correct, check.unit_count)}
                    </div>
                ) : null}
            </div>

            {hasQuoteButton(check) ? (
                <button
                    type="button"
                    title={RV_QUOTE_TITLE}
                    data-pinned={pinned ? 'true' : 'false'}
                    onClick={(e) => { e.stopPropagation(); onPin(); }}
                    className={[
                        'inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border',
                        'py-1 pe-2.5 ps-2.5 text-gr-meta font-medium text-primary-700',
                        'transition-all hover:bg-primary-50',
                        pinned
                            ? 'border-grade-teal-line bg-primary-100 opacity-100'
                            : 'border-grade-line bg-grade-card opacity-85',
                    ].join(' ')}
                >
                    <span aria-hidden="true" className="font-serif text-gr-quote leading-none
                        text-primary-600">
                        ❝
                    </span>
                    {RV_QUOTE}
                </button>
            ) : (
                <span />
            )}

            <div
                dir="ltr"
                className={[
                    'self-start pt-2 text-left text-gr-num font-light leading-none',
                    '[unicode-bidi:isolate] [font-variant-numeric:tabular-nums]',
                    overridden ? 'font-medium text-grade-red' : 'text-grade-pencil',
                ].join(' ')}
            >
                {formatPoints(awarded)}
                <small className="text-gr-sm text-grade-pencil-2">
                    {' '}/ {formatPoints(outOf)}
                </small>
            </div>
        </div>
    );
}
