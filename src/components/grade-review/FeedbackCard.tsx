'use client';

import { useEffect, useRef } from 'react';

import type { FeedbackState } from '@/utils/feedback-staleness';
import { MathLines, useMathNotation } from '@/components/math/MathNotationContext';
import { hasMath } from '@/utils/math-spans';
import {
    RV_FB_ABSENT,
    RV_FB_EDITED,
    RV_FB_FRESH,
    RV_FB_OFFERED_KEEP,
    RV_FB_OFFERED_TITLE,
    RV_FB_OFFERED_USE,
    RV_FB_REWRITE,
    RV_FB_STALE,
    RV_FB_WRITE,
} from '@/copy/grade-review';
import { V6_FB_ASK_VIVI, V6_FB_RETRY, V6_FB_UPDATING, V6_FB_WRITE } from '@/copy/grade-review-v6';

/**
 * The student's feedback for one scope, or for the whole test (R11).
 *
 * THREE STATES, and the third is the one that gets built wrong:
 *
 *   fresh   «נכתב על ידי ויוי לפי הניקוד · ניתן לעריכה»
 *   stale   amber — the verdicts moved after this was written, with a
 *           «כתיבה מחדש» action. Derived from `basis_hash`, never a stored
 *           flag: when the verdicts move the text says so by construction.
 *   absent  `feedback = null` is a FIRST-CLASS WIRE STATE, not an error. The
 *           feedback call can fail while the grade itself lands — review-first,
 *           never guess — so the card says «לא נכתב משוב» and offers to write
 *           one. An error page here would hide a perfectly reviewable grade
 *           behind a failure in a different subsystem.
 *
 * [v6] Two more, both on the grader-v6 surface only:
 *
 *   updating  Vivi is rewriting it (the surface does that on its own when her
 *             decisions made the text stale). The box stays editable: if she
 *             types, her words win and the rewrite is only offered.
 *   blank     SHE emptied it: no feedback goes out for this target, by choice.
 *             The box stays open — a card that vanished while she cleared it was
 *             the old behaviour — with «בקשי נוסח מויוי» as the way back.
 *
 * And on v6 an absent card offers BOTH ways forward when it can (`onWrite`):
 * «כתבי משוב» opens an empty box of her own, «נסי שוב» asks Vivi again.
 *
 * OD-F5 (ruled): a plain auto-growing textarea, not `contenteditable` — no
 * paste-HTML surprises, and it is what a screen reader expects of an editor.
 */

export interface FeedbackCardProps {
    title: string;
    text: string;
    state: FeedbackState;
    /** She has edited this text herself — never call her own words stale. */
    teacherEdited: boolean;
    busy?: boolean;
    onChange: (text: string) => void;
    onRegenerate: () => void;
    /**
     * R11: a regeneration that would overwrite HER words is OFFERED, not
     * applied. The server says so itself (`offered_only`), and the offer has to
     * be a real affordance she can compare and choose from — Vivi proposes, the
     * teacher decides. A toast would make her decide from memory, against text
     * that has already vanished.
     */
    offered?: string | null;
    onAcceptOffer?: () => void;
    onDismissOffer?: () => void;
    /** [v6] Opens an empty box of hers. Given ⇒ an absent card offers «כתבי משוב». */
    onWrite?: () => void;
    /** [v6] Vivi can write this target — «נסי שוב» / «בקשי נוסח מויוי» are offered. */
    canAskVivi?: boolean;
    /** [v6] What the header says when there is no text (why it is missing). */
    absentLabel?: string;
    /** [v6] What the header says when she emptied it. */
    blankLabel?: string;
    /** [v6] The box was just opened by «כתבי משוב» — take the caret. */
    focusOnMount?: boolean;
    /** Signed: she reads it, she cannot change it. */
    readOnly?: boolean;
}

const linkClass = 'text-primary-700 underline underline-offset-link disabled:opacity-50';

export function FeedbackCard({
    title, text, state, teacherEdited, busy = false, onChange, onRegenerate,
    offered = null, onAcceptOffer, onDismissOffer,
    onWrite, canAskVivi = true, absentLabel, blankLabel, readOnly = false, focusOnMount = false,
}: FeedbackCardProps) {
    const areaRef = useRef<HTMLTextAreaElement | null>(null);
    const math = useMathNotation();

    // Auto-height: the box shows the whole paragraph rather than making her
    // scroll a four-line window to read what her student will read.
    useEffect(() => {
        const area = areaRef.current;
        if (!area) return;
        area.style.height = 'auto';
        area.style.height = `${area.scrollHeight}px`;
    }, [text]);

    const stale = state === 'stale';
    const quiet = state === 'absent' || state === 'blank';

    let header: React.ReactNode;
    if (state === 'absent') {
        header = onWrite ? (
            <>
                {absentLabel ?? RV_FB_ABSENT}
                {!readOnly ? (
                    <>
                        {' · '}
                        <button type="button" data-feedback-write onClick={onWrite} className={linkClass}>
                            {V6_FB_WRITE}
                        </button>
                        {canAskVivi ? (
                            <>
                                {' · '}
                                <button type="button" data-feedback-retry disabled={busy}
                                    onClick={onRegenerate} className={linkClass}>
                                    {V6_FB_RETRY}
                                </button>
                            </>
                        ) : null}
                    </>
                ) : null}
            </>
        ) : (
            <>
                {RV_FB_ABSENT} ·{' '}
                <button type="button" disabled={busy} onClick={onRegenerate} className={linkClass}>
                    {RV_FB_WRITE}
                </button>
            </>
        );
    } else if (state === 'blank') {
        header = (
            <>
                {blankLabel}
                {!readOnly && canAskVivi ? (
                    <>
                        {' · '}
                        <button type="button" data-feedback-ask disabled={busy}
                            onClick={onRegenerate} className={linkClass}>
                            {V6_FB_ASK_VIVI}
                        </button>
                    </>
                ) : null}
            </>
        );
    } else if (state === 'updating') {
        header = <span data-feedback-updating>{V6_FB_UPDATING}</span>;
    } else if (stale) {
        header = (
            <>
                {RV_FB_STALE}
                {!readOnly ? (
                    <>
                        {' · '}
                        <button type="button" disabled={busy} onClick={onRegenerate}
                            className="underline underline-offset-link disabled:opacity-50">
                            {RV_FB_REWRITE}
                        </button>
                    </>
                ) : null}
            </>
        );
    } else {
        header = teacherEdited ? RV_FB_EDITED : RV_FB_FRESH;
    }

    return (
        <div
            data-feedback-state={state}
            className={[
                'mt-3.5 rounded-grade-ctl border bg-grade-card',
                stale ? 'border-grade-amber-200' : 'border-grade-line',
            ].join(' ')}
        >
            <div
                className={[
                    'flex items-center justify-between gap-2.5 border-b border-grade-line-2',
                    'px-3.5 py-2 text-gr-meta',
                    stale ? 'bg-grade-amber-50 text-grade-amber-ink' : 'text-grade-ink-2',
                ].join(' ')}
            >
                <span className="font-semibold">{title}</span>
                <span className={quiet ? 'text-grade-pencil' : undefined}>{header}</span>
            </div>

            {state === 'absent' ? null : (
                <textarea
                    ref={areaRef}
                    value={text}
                    spellCheck={false}
                    rows={1}
                    readOnly={readOnly}
                    autoFocus={focusOnMount && !readOnly}
                    aria-label={title}
                    onChange={(e) => onChange(e.target.value)}
                    onKeyDown={(e) => e.stopPropagation()}
                    className={[
                        'block min-h-fb-min w-full resize-none bg-transparent px-3.5 py-3',
                        'text-gr-prose outline-none focus:shadow-[inset_0_0_0_2px_theme(colors.primary.100)]',
                        state === 'updating' ? 'text-grade-pencil' : '',
                    ].join(' ')}
                />
            )}

            {/* Under a math subject the textarea holds the SOURCE of each formula; the
                student receives it typeset (and linearised in the PDF). This preview is
                what she will read, so the teacher never has to read LaTeX to approve it. */}
            {math && state !== 'absent' && hasMath(text) ? (
                <p
                    data-feedback-preview
                    dir="rtl"
                    className="border-t border-dashed border-grade-line-2 px-3.5 py-2.5
                        text-gr-prose text-grade-ink-2"
                >
                    <MathLines text={text} />
                </p>
            ) : null}

            {offered ? (
                <div
                    data-feedback-offer
                    className="m-3.5 mt-0 rounded-grade-ctl border border-grade-violet-line
                        bg-grade-violet-50 p-3"
                >
                    <p className="text-gr-meta text-grade-violet-ink">
                        {RV_FB_OFFERED_TITLE}
                    </p>
                    <p className="mt-1.5 whitespace-pre-wrap text-gr-prose text-grade-ink">
                        <MathLines text={offered} />
                    </p>
                    <div className="mt-2.5 flex flex-wrap gap-2.5">
                        <button
                            type="button"
                            onClick={onAcceptOffer}
                            className="rounded-grade-ctl border border-primary-600
                                bg-primary-600 px-3 py-1.5 text-gr-meta font-medium text-white
                                hover:bg-primary-700"
                        >
                            {RV_FB_OFFERED_USE}
                        </button>
                        <button
                            type="button"
                            onClick={onDismissOffer}
                            className="rounded-grade-ctl border border-grade-line
                                bg-grade-card px-3 py-1.5 text-gr-meta text-grade-ink-2
                                hover:border-grade-pencil-2"
                        >
                            {RV_FB_OFFERED_KEEP}
                        </button>
                    </div>
                </div>
            ) : null}
        </div>
    );
}
