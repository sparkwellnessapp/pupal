'use client';

import { useState } from 'react';

import type { NumericPolicy } from '@/lib/pricing';
import { MathInline } from '@/components/math/MathNotationContext';
import { ProseMath } from '@/components/math/ProseMath';
import { hasMathNotation } from '@/lib/subjects';
import { answerRenderPlan } from '@/utils/answer-mode';
import { formatPoints } from '@/utils/points-display';
import { criterionQuoteSpans, type V6Charge, type V6Check, type V6Criterion } from '@/utils/grade-review-v6-model';
import { PointsInput } from './PointsInput';
import {
    RV_BREAKDOWN_COUNT, RV_BREAKDOWN_HIDE, RV_BREAKDOWN_SHOW,
} from '@/copy/grade-review';
import {
    V6_BACK_TO_VIVI, V6_CHARGE_APPLIED, V6_CHARGE_CAPPED, V6_CHARGE_FLOORED,
    V6_CHARGE_INACTIVE, V6_CHARGE_MOVED, V6_CHARGE_SUPERSEDED, V6_CHIP,
    V6_COMMENT_ADD, V6_COMMENT_CANCEL, V6_COMMENT_EDIT, V6_COMMENT_MINE,
    V6_COMMENT_PLACEHOLDER, V6_COMMENT_REMOVE, V6_COMMENT_SAVE, V6_FAULT_TAG, V6_GATED,
    V6_HER_TAG, V6_LINE_UPDATING, V6_MANUAL_CLEAR, V6_MANUAL_GRADE, V6_NOTE_PREFIX,
    V6_QUOTE_BUTTON, V6_QUOTE_NONE, V6_QUOTE_PREFIX, V6_QUOTE_TITLE, V6_UNDECIDED, V6_VIVI_TAG,
    V6_WAITING,
} from '@/copy/grade-review-v6';

/**
 * One criterion of HER rubric, as grader-v6 graded it (owner rulings 2026-10-17 §7).
 *
 * Closed, the row is the whole story at a glance: her criterion text VERBATIM,
 * the grade the one pricer gives it under her decisions, the chip, the line that
 * explains it, the words of the answer it was credited on — and, when she set
 * the grade herself, «הציון נקבע ידנית». Her note on the criterion lives on
 * the closed row too — it is written for the student and printed under the
 * question's feedback on the signed exam.
 *
 * Opened, it shows the checks the grade is made of. Each credit and each
 * deduction is a short list of what the answer might show; Vivi's pick is
 * marked as hers, and the teacher's own pick — when different — is marked as
 * the teacher's, in her turquoise (the ink grammar of 2026-09-13). A check no
 * answer came back for wears the empty amber ring of v5's no-verdict state and
 * selects nothing: the pricer's zero there is a default, not a judgement.
 *
 * Every number on it is read from the pricer through the view model; this
 * component computes none (CLAUDE.md §5).
 */

export interface CriterionRowV6Props {
    criterion: V6Criterion;
    /** The rubric's grid — what a grade set by hand is checked against. */
    policy: NumericPolicy;
    open: boolean;
    onToggle: () => void;
    readOnly?: boolean;
    /** The rubric's subject — decides how a quotation from the answer is laid out. */
    subject?: string | null;
    editingPoints?: boolean;
    onEditingPoints?: (editing: boolean) => void;
    onPin?: (amount: string) => void;
    onClearPin?: () => void;
    onChoose?: (checkId: string, optionId: string) => void;
    onWithdraw?: (checkId: string) => void;
    /** Her note on the criterion, for the student; null removes it. */
    onNote?: (text: string | null) => void;
    /** This criterion's quotations are lit in the answer. */
    lit?: boolean;
    onToggleLit?: () => void;
}

/** «−0.5», with a real minus sign; zero is plain zero. */
export function signedPoints(value: string): string {
    const text = formatPoints(value.replace(/^-/, ''));
    return value.trim().startsWith('-') && text !== '0' ? `−${text}` : text;
}

/**
 * A quote the verifier took from INSIDE a formula carries no delimiters (`f'(x)=4x`,
 * `\frac{1}{e}` — the shortest span of the answer, which QM-1 certifies). In a math answer
 * it is drawn as the formula it is part of; with any Hebrew in it, it stays text.
 */
const BARE_LATEX = /\\[A-Za-z]+|[\^_]|[=<>]/;
export function asDisplayedQuote(text: string, subject?: string | null): string {
    if (!hasMathNotation(subject) || text.includes('\\(') || /[֐-׿]/.test(text)) return text;
    return BARE_LATEX.test(text) ? `\\(${text}\\)` : text;
}

/** A quotation from the student's answer, laid out the way the answer itself is. */
function Quote({ text: raw, subject }: { text: string; subject?: string | null }) {
    const text = asDisplayedQuote(raw, subject);
    const plan = answerRenderPlan(text, subject);
    return (
        <span
            dir={plan.dir}
            className={[
                'rounded-mark bg-grade-bar px-1 [unicode-bidi:isolate]',
                plan.mode === 'code' ? 'font-mono text-gr-answer' : '',
            ].join(' ')}
        >
            {/* A quotation from a math answer is typeset like the answer it came
                from (MATH_RENDERING_PLAN §4); any other quotation is its string. */}
            <ProseMath text={text} subject={subject} />
        </span>
    );
}

function chargeText(charge: V6Charge): string | null {
    switch (charge.status) {
        case 'applied': return V6_CHARGE_APPLIED(signedPoints(charge.charged));
        case 'capped': return V6_CHARGE_CAPPED(signedPoints(charge.charged), signedPoints(charge.amount));
        case 'floored': return V6_CHARGE_FLOORED(signedPoints(charge.charged), signedPoints(charge.amount));
        case 'superseded': return V6_CHARGE_SUPERSEDED;
        // An inactive deduction whose chosen answer is «none» has nothing to say.
        case 'inactive': return charge.amount.trim().startsWith('-') ? V6_CHARGE_INACTIVE : null;
        case 'no_fault':
        default: return null;
    }
}

const CHIP_TONE: Readonly<Record<V6Criterion['chip'], string>> = {
    full: 'bg-grade-green-100 text-grade-green',
    partial: 'bg-grade-yellow-100 text-grade-yellow',
    zero: 'bg-grade-red-100 text-grade-red',
};

/** The empty amber ring — v5's no-verdict state, the same token set. */
function UndecidedRing({ label }: { label: string }) {
    return (
        <span
            role="img"
            aria-label={label}
            title={label}
            data-undecided-ring
            className="inline-block h-verdict w-verdict flex-none rounded-full border-hairline
                border-dashed border-grade-amber-dot bg-grade-card"
        />
    );
}

function NoteField({
    comment, readOnly, onSave,
}: {
    comment: string | null;
    readOnly: boolean;
    onSave: (text: string | null) => void;
}) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(comment ?? '');

    if (editing && !readOnly) {
        return (
            <div className="mt-1.5" data-comment-editor>
                <textarea
                    value={draft}
                    rows={2}
                    autoFocus
                    placeholder={V6_COMMENT_PLACEHOLDER}
                    aria-label={V6_COMMENT_PLACEHOLDER}
                    onChange={(e) => setDraft(e.target.value)}
                    className="block w-full resize-y rounded-grade-sm border border-grade-line
                        bg-grade-card px-2.5 py-1.5 text-gr-meta text-grade-ink outline-none
                        focus:border-primary-500"
                />
                <div className="mt-1.5 flex gap-3 text-gr-meta">
                    <button
                        type="button"
                        data-comment-save
                        onClick={() => { onSave(draft.trim() || null); setEditing(false); }}
                        className="font-medium text-primary-700 underline underline-offset-link"
                    >
                        {V6_COMMENT_SAVE}
                    </button>
                    <button
                        type="button"
                        onClick={() => { setDraft(comment ?? ''); setEditing(false); }}
                        className="text-grade-ink-2 underline underline-offset-link"
                    >
                        {V6_COMMENT_CANCEL}
                    </button>
                    {comment ? (
                        <button
                            type="button"
                            onClick={() => { onSave(null); setDraft(''); setEditing(false); }}
                            className="text-grade-ink-2 underline underline-offset-link"
                        >
                            {V6_COMMENT_REMOVE}
                        </button>
                    ) : null}
                </div>
            </div>
        );
    }
    if (comment) {
        return (
            <p data-her-comment className="mt-1 whitespace-pre-line text-gr-meta text-primary-700">
                <span className="font-medium">{V6_COMMENT_MINE}</span> <MathInline text={comment} />
                {!readOnly ? (
                    <>
                        {' · '}
                        <button
                            type="button"
                            onClick={() => { setDraft(comment); setEditing(true); }}
                            className="underline underline-offset-link"
                        >
                            {V6_COMMENT_EDIT}
                        </button>
                    </>
                ) : null}
            </p>
        );
    }
    if (readOnly) return null;
    return (
        <button
            type="button"
            data-comment-add
            title={V6_COMMENT_PLACEHOLDER}
            onClick={() => { setDraft(''); setEditing(true); }}
            className="mt-1 block text-gr-meta text-grade-pencil underline underline-offset-link
                hover:text-primary-700"
        >
            {V6_COMMENT_ADD}
        </button>
    );
}

function CheckBlockV6({
    check, readOnly, subject, onChoose, onWithdraw,
}: {
    check: V6Check;
    readOnly: boolean;
    subject?: string | null;
    onChoose?: (checkId: string, optionId: string) => void;
    onWithdraw?: (checkId: string) => void;
}) {
    const viviPicked = check.options.some((o) => o.vivi);
    const charge = check.charge ? chargeText(check.charge) : null;
    return (
        <div
            data-v6-check={check.checkId}
            data-role={check.role}
            data-undecided={check.undecided ? 'true' : 'false'}
            data-hers={check.herOptionId !== null ? 'true' : 'false'}
            className="border-t border-grade-line-2 px-3.5 py-2.5"
        >
            <div className="flex items-start gap-2.5">
                {check.undecided ? <UndecidedRing label={V6_UNDECIDED} /> : null}
                <div className="min-w-0 flex-1">
                    <p className="text-gr-body text-grade-ink">
                        {check.role === 'fault' ? (
                            <span className="me-1.5 rounded-full bg-grade-red-100 px-2 py-px
                                text-gr-chip text-grade-red">
                                {V6_FAULT_TAG}
                            </span>
                        ) : null}
                        {check.role === 'note' ? (
                            <span className="me-1 font-medium text-grade-ink-2">{V6_NOTE_PREFIX}</span>
                        ) : null}
                        <MathInline text={check.description} />
                    </p>

                    {check.undecided ? (
                        <p className="mt-0.5 text-gr-meta text-grade-amber-ink">{V6_UNDECIDED}</p>
                    ) : null}

                    {check.role === 'note' ? (
                        check.noteObserved && check.noteLabel ? (
                            <p data-note-observed className="mt-1 text-gr-meta text-grade-ink-2">
                                <MathInline text={check.noteLabel} />
                            </p>
                        ) : null
                    ) : (
                        <div
                            role="radiogroup"
                            aria-label={check.description}
                            className="mt-1.5 flex flex-col gap-1"
                        >
                            {check.options.map((o) => (
                                <button
                                    key={o.optionId}
                                    type="button"
                                    role="radio"
                                    aria-checked={o.effective}
                                    data-option={o.optionId}
                                    data-vivi={o.vivi ? 'true' : 'false'}
                                    data-hers={o.hers ? 'true' : 'false'}
                                    data-effective={o.effective ? 'true' : 'false'}
                                    disabled={readOnly}
                                    onClick={() => { if (!o.hers) onChoose?.(check.checkId, o.optionId); }}
                                    className={[
                                        'flex items-center gap-2 rounded-grade-sm border px-2.5 py-1.5',
                                        'text-start text-gr-meta transition-colors',
                                        'disabled:cursor-default',
                                        o.hers
                                            ? 'border-primary-600 bg-primary-50 text-grade-ink'
                                            : o.effective
                                                ? 'border-grade-line bg-grade-card text-grade-ink'
                                                : 'border-transparent text-grade-ink-2 enabled:hover:bg-grade-bar',
                                    ].join(' ')}
                                >
                                    <span
                                        aria-hidden="true"
                                        className={[
                                            'grid h-3.5 w-3.5 flex-none place-items-center rounded-full border',
                                            o.hers ? 'border-primary-600'
                                                : o.effective ? 'border-grade-ink-2' : 'border-grade-pencil-2',
                                        ].join(' ')}
                                    >
                                        {o.effective ? (
                                            <span className={[
                                                'h-1.5 w-1.5 rounded-full',
                                                o.hers ? 'bg-primary-600' : 'bg-grade-ink-2',
                                            ].join(' ')} />
                                        ) : null}
                                    </span>
                                    <span className="min-w-0 flex-1"><MathInline text={o.label} /></span>
                                    {o.vivi ? (
                                        <span data-vivi-tag className="whitespace-nowrap text-gr-sm text-grade-pencil">
                                            {V6_VIVI_TAG}
                                        </span>
                                    ) : null}
                                    {o.hers ? (
                                        <span data-her-tag className="whitespace-nowrap text-gr-sm font-medium text-primary-700">
                                            {V6_HER_TAG}
                                        </span>
                                    ) : null}
                                    <span
                                        dir="ltr"
                                        className="min-w-tariff whitespace-nowrap text-left text-gr-meta
                                            [font-variant-numeric:tabular-nums] [unicode-bidi:isolate]"
                                    >
                                        {signedPoints(o.value)}
                                    </span>
                                </button>
                            ))}
                        </div>
                    )}

                    {check.gated && check.herOptionId === null ? (
                        <p data-gated className="mt-1 text-gr-meta text-grade-amber-ink">{V6_GATED}</p>
                    ) : null}

                    {check.quote && check.role !== 'note' ? (
                        <p data-check-quote className="mt-1 text-gr-meta text-grade-ink-2">
                            {V6_QUOTE_PREFIX} <Quote text={check.quote} subject={subject} />
                        </p>
                    ) : null}

                    {charge ? (
                        <p data-charge={check.charge?.status} className="mt-1 text-gr-meta text-grade-ink-2">
                            {charge}
                        </p>
                    ) : null}
                    {check.charge?.movedFrom ? (
                        <p data-charge-moved={check.charge.movedFrom.terminalId}
                            className="mt-1 text-gr-meta text-primary-700">
                            <MathInline text={V6_CHARGE_MOVED(check.charge.movedFrom.description)} />
                        </p>
                    ) : null}

                    {check.herOptionId !== null && viviPicked && !readOnly ? (
                        <button
                            type="button"
                            data-back-to-vivi
                            onClick={() => onWithdraw?.(check.checkId)}
                            className="mt-1.5 text-gr-meta text-primary-700 underline underline-offset-link"
                        >
                            {V6_BACK_TO_VIVI}
                        </button>
                    ) : null}
                </div>
            </div>
        </div>
    );
}

export function CriterionRowV6({
    criterion, policy, open, onToggle, readOnly = false, subject = null,
    editingPoints = false, onEditingPoints, onPin, onClearPin,
    onChoose, onWithdraw, onNote, lit = false, onToggleLit,
}: CriterionRowV6Props) {
    const panelId = `v6-breakdown-${criterion.terminalId}`;
    // For a criterion she set by hand the server's composer writes exactly the
    // label's words; saying it twice on one row is noise. Anything MORE it says
    // is shown.
    const lineRepeatsLabel = criterion.pinned
        && criterion.line?.text.trim() === V6_MANUAL_GRADE;
    const hasQuotes = criterionQuoteSpans(criterion).length > 0;
    return (
        <div
            data-v6-criterion={criterion.terminalId}
            data-chip={criterion.chip}
            data-pinned={criterion.pinned ? 'true' : 'false'}
            data-expanded={open ? 'true' : 'false'}
            className="mb-2.5 overflow-hidden rounded-grade-ctl border border-grade-line"
        >
            <div
                data-terminal-row={criterion.terminalId}
                className="gr-row-scroll flex flex-wrap items-center justify-between gap-x-2.5
                    gap-y-1.5 bg-grade-bar px-3.5 py-2 text-gr-body font-semibold"
            >
                <button
                    type="button"
                    aria-expanded={open}
                    aria-controls={panelId}
                    aria-label={open
                        ? RV_BREAKDOWN_HIDE(criterion.description)
                        : RV_BREAKDOWN_SHOW(criterion.description)}
                    data-v6-toggle={criterion.terminalId}
                    onClick={onToggle}
                    className="flex min-w-0 flex-1 basis-56 items-center gap-2 text-start
                        font-semibold text-inherit"
                >
                    <span
                        aria-hidden="true"
                        className={[
                            'shrink-0 text-grade-pencil transition-transform motion-reduce:transition-none',
                            open ? 'rotate-90' : 'rotate-180',
                        ].join(' ')}
                    >
                        ▸
                    </span>
                    {/* Her words, as she wrote them — never paraphrased. */}
                    <span className="min-w-0" data-criterion-text><MathInline text={criterion.description} /></span>
                </button>

                {!open && criterion.undecidedCount > 0 ? (
                    <span
                        data-waiting={criterion.undecidedCount}
                        className="flex shrink-0 items-center gap-1.5 whitespace-nowrap text-gr-meta
                            font-normal text-grade-amber-ink"
                    >
                        <span aria-hidden="true" className="inline-block h-dot w-dot rounded-full
                            border-hairline border-dashed border-grade-amber-dot" />
                        {V6_WAITING(criterion.undecidedCount)}
                    </span>
                ) : null}

                {!open && criterion.checks.length > 0 ? (
                    <span className="shrink-0 whitespace-nowrap text-gr-meta font-normal text-grade-pencil-2">
                        {RV_BREAKDOWN_COUNT(criterion.checks.length)}
                    </span>
                ) : null}

                <span
                    data-chip-label={criterion.chip}
                    className={`shrink-0 rounded-full px-2.5 py-0.5 text-gr-chip font-medium ${
                        CHIP_TONE[criterion.chip]}`}
                >
                    {V6_CHIP[criterion.chip]}
                </span>

                <span
                    dir="ltr"
                    data-criterion-points={criterion.terminalId}
                    className="relative min-w-tariff text-left text-gr-crit font-light leading-none
                        [font-variant-numeric:tabular-nums] [unicode-bidi:isolate]"
                >
                    <PointsInput
                        target="criterion"
                        size="crit"
                        value={criterion.awarded}
                        max={criterion.possible}
                        policy={policy}
                        typed={criterion.pinned}
                        overridden={criterion.decided}
                        readOnly={readOnly}
                        editing={editingPoints}
                        onEditingChange={(editing) => onEditingPoints?.(editing)}
                        onCommit={(amount) => onPin?.(amount)}
                    />
                </span>
            </div>

            <div className="border-t border-grade-line-2 px-3.5 py-2 text-gr-meta text-grade-ink-2">
                {criterion.pinned ? (
                    <p data-manual-grade className="mb-1 text-primary-700">
                        <span className="font-medium">{V6_MANUAL_GRADE}</span>
                        {!readOnly ? (
                            <>
                                {' · '}
                                <button
                                    type="button"
                                    data-clear-manual-grade
                                    onClick={onClearPin}
                                    className="underline underline-offset-link"
                                >
                                    {V6_MANUAL_CLEAR}
                                </button>
                            </>
                        ) : null}
                    </p>
                ) : null}

                {criterion.linePending ? (
                    <p data-reasoning-line data-line-state="updating" className="text-grade-pencil">
                        {V6_LINE_UPDATING}
                    </p>
                ) : criterion.line && !lineRepeatsLabel ? (
                    <p data-reasoning-line data-line-state="ready" data-line-source={criterion.line.source}
                        className="leading-relaxed">
                        <ProseMath text={criterion.line.text} subject={subject} />
                    </p>
                ) : null}

                {onToggleLit || criterion.primaryQuote ? (
                    <p data-primary-quote={criterion.primaryQuote ? '' : undefined} className="mt-1">
                        {onToggleLit ? (
                            <button
                                type="button"
                                data-quote-button
                                title={hasQuotes ? V6_QUOTE_TITLE : V6_QUOTE_NONE}
                                aria-pressed={hasQuotes ? lit : undefined}
                                disabled={!hasQuotes}
                                onClick={onToggleLit}
                                className={`me-2 rounded-grade-ctl border px-2 py-0.5 ${
                                    !hasQuotes
                                        ? 'cursor-not-allowed border-grade-line-2 text-grade-pencil'
                                        : lit
                                            ? 'border-primary-700 bg-primary-50 text-primary-700'
                                            : 'border-primary-200 text-primary-700 hover:bg-primary-50'}`}
                            >
                                {V6_QUOTE_BUTTON}
                            </button>
                        ) : (
                            <span className="me-1">{V6_QUOTE_PREFIX}</span>
                        )}
                        {criterion.primaryQuote
                            ? <Quote text={criterion.primaryQuote} subject={subject} /> : null}
                    </p>
                ) : null}

                <NoteField
                    key={criterion.note ?? ''}
                    comment={criterion.note}
                    readOnly={readOnly || !onNote}
                    onSave={(text) => onNote?.(text)}
                />
            </div>

            {open ? (
                <div id={panelId}>
                    {criterion.checks.map((check) => (
                        <CheckBlockV6
                            key={check.checkId}
                            check={check}
                            readOnly={readOnly}
                            subject={subject}
                            onChoose={onChoose}
                            onWithdraw={onWithdraw}
                        />
                    ))}
                </div>
            ) : null}
        </div>
    );
}
