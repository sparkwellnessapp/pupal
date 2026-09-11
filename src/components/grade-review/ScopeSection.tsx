'use client';

import type { ReviewScope } from '@/utils/grade-review-model';
import type { Highlight } from '@/utils/evidence-highlight';
import type { FeedbackState } from '@/utils/feedback-staleness';
import { formatPoints } from '@/utils/points-display';
import { AnswerBlock } from './AnswerBlock';
import { CheckRow } from './CheckRow';
import { FeedbackCard } from './FeedbackCard';
import {
    RV_ANSWER_LABEL,
    RV_BREAKDOWN_COUNT,
    RV_BREAKDOWN_HIDE,
    RV_BREAKDOWN_SHOW,
    RV_ANSWER_INHERITED,
    RV_ANSWER_INHERITED_ANON,
    RV_ANSWER_NONE,
    RV_ANSWER_UNAVAILABLE,
    RV_FB_TITLE,
    RV_QUESTION_TOGGLE,
    RV_QUOTE_ALL,
    RV_QUOTE_ALL_TITLE,
    RV_SCOPE_EXCLUDED,
    RV_SCOPE_FAILED,
    RV_SCOPE_FAILED_CHIP,
    RV_SCOPE_RETRY,
    RV_SHOW_SCAN,
} from '@/copy/grade-review';

/**
 * One question, in the fixed order R4 specifies:
 *
 *   title + points → ▸ השאלה (collapsed) → the answer → the checklist → feedback
 *
 * The order is not decoration. She reads the answer, then judges it against the
 * checks, then reads what the student will be told — the same sequence she
 * would follow on paper. Putting the checklist first would have her judging
 * before reading.
 *
 * OD-F3 (ruled 2026-08-31): the question is COLLAPSED, with a one-sentence
 * preview and a `…` so she can tell at a glance whether it is the question she
 * remembers — a bare «השאלה» makes her open every section to find out.
 */

export interface ScopeSectionProps {
    scope: ReviewScope;
    highlight: Highlight;
    highlightTransient: boolean;
    focusedCheckId: string | null;
    pinnedCheckId: string | null;
    openNoteCheckId: string | null;
    feedbackBusy: boolean;
    /** She wrote this text herself — never caption it as Vivi's. */
    feedbackEdited?: boolean;
    /** The rubric's subject key — decides prose-vs-code and direction of the answer (Phase 3a). */
    subject?: string | null;
    onFocusCheck: (checkId: string) => void;
    onHoverCheck: (checkId: string, hovering: boolean) => void;
    onCycle: (terminalId: string, checkId: string) => void;
    onRevert: (terminalId: string, checkId: string) => void;
    onPin: (checkId: string) => void;
    /**
     * [S3] The criterion whose union is pinned, if any. Kept separate from
     * `pinnedCheckId` rather than folded into one prop: the two are different
     * kinds of selection (one row vs. a whole box), and a single string would
     * make the caller re-encode the discriminant the pin already carries.
     */
    pinnedTerminalId?: string | null;
    /** [S3] Light every span this criterion's checks would light, at once. */
    onPinCriterion?: (terminalId: string) => void;
    /**
     * [S4] Is this criterion's breakdown open? Asked as a FUNCTION rather than
     * passed as a set, because the surface merges two sources — the once-per-
     * test opening state and her own toggles since — and resolving that here
     * would put the merge in two places.
     */
    isCriterionOpen?: (terminalId: string) => boolean;
    onToggleCriterion?: (terminalId: string) => void;
    onNoteChange: (terminalId: string, checkId: string, note: string) => void;
    onNoteClose: () => void;
    onFeedbackChange: (scopeId: string, text: string) => void;
    onFeedbackRegenerate: (scopeId: string) => void;
    /** R11 — Vivi's alternative wording, offered beside hers. */
    feedbackOffer?: string | null;
    onAcceptFeedbackOffer?: (scopeId: string) => void;
    onDismissFeedbackOffer?: (scopeId: string) => void;
    onShowScan: (scopeId: string) => void;
    onRetry?: () => void;
}

/** First sentence, capped — enough to recognise the question, never a wall. */
function preview(text: string): string {
    const firstSentence = text.split(/(?<=[.?!])\s/)[0] ?? text;
    const clipped = firstSentence.length > 90
        ? firstSentence.slice(0, 90).trimEnd()
        : firstSentence;
    if (clipped.length >= text.length) return clipped;
    // Trailing punctuation before the ellipsis reads as «Hobby....» — the
    // sentence's own full stop plus the clip marker. Drop it.
    return `${clipped.replace(/[.,;:،]+$/, '')}…`;
}

export function ScopeSection({
    scope, highlight, highlightTransient, focusedCheckId, pinnedCheckId,
    openNoteCheckId, feedbackBusy, feedbackEdited = false, subject = null,
    onFocusCheck, onHoverCheck, onCycle, onRevert, onPin, onNoteChange, onNoteClose,
    onFeedbackChange, onFeedbackRegenerate, onShowScan, onRetry,
    pinnedTerminalId = null, onPinCriterion,
    // Default OPEN: a caller that does not participate in the disclosure (a
    // test, a future embed) gets the pre-S4 surface rather than a page of
    // headers with no way to open them.
    isCriterionOpen = () => true, onToggleCriterion,
    feedbackOffer = null, onAcceptFeedbackOffer, onDismissFeedbackOffer,
}: ScopeSectionProps) {
    const failed = scope.gradedBy === 'failed';
    const skipped = scope.gradedBy === 'skipped_no_answer';
    const excluded = scope.gradedBy === 'excluded_by_selection';

    return (
        <section
            id={`scope-${scope.scopeId}`}
            data-scope-id={scope.scopeId}
            data-graded-by={scope.gradedBy}
            className={[
                'mb-4 scroll-mt-scope rounded-grade border bg-grade-card px-6 pb-5 pt-5',
                failed ? 'border-grade-red' : 'border-grade-line',
            ].join(' ')}
        >
            <header className="mb-1.5 flex items-baseline justify-between gap-3">
                <h2 className="text-gr-h2">{scope.title}</h2>
                <div
                    dir="ltr"
                    data-scope-points
                    className={[
                        'text-gr-pts [font-variant-numeric:tabular-nums] [unicode-bidi:isolate]',
                        scope.overridden ? 'font-normal text-grade-red' : 'text-grade-pencil',
                    ].join(' ')}
                >
                    {formatPoints(scope.awarded)} / {formatPoints(scope.possible)}
                </div>
            </header>

            {failed ? (
                <p className="mb-3 flex items-center gap-3 text-gr-body text-grade-red">
                    {RV_SCOPE_FAILED}
                    {onRetry ? (
                        <button
                            type="button"
                            onClick={onRetry}
                            className="text-primary-700 underline underline-offset-link"
                        >
                            {RV_SCOPE_RETRY}
                        </button>
                    ) : null}
                </p>
            ) : null}

            {excluded ? (
                <p className="mb-3 text-gr-body text-grade-pencil">{RV_SCOPE_EXCLUDED}</p>
            ) : null}

            {scope.questionText ? (
                <details className="my-1 text-gr-meta text-grade-ink-2">
                    <summary className="inline-flex cursor-pointer list-none items-center gap-1.5
                        text-grade-pencil marker:content-['']">
                        <span aria-hidden="true">▸</span>
                        {RV_QUESTION_TOGGLE}
                        <span className="text-grade-pencil-2">— {preview(scope.questionText)}</span>
                    </summary>
                    <p className="mt-1.5 rounded-grade-sm bg-grade-bar px-3 py-2.5 leading-relaxed">
                        {scope.questionText}
                    </p>
                </details>
            ) : null}

            <div className="mb-1 mt-2.5 flex items-center justify-between text-gr-label
                text-grade-pencil">
                <span>{RV_ANSWER_LABEL}</span>
                <button
                    type="button"
                    onClick={() => onShowScan(scope.scopeId)}
                    className="text-primary-700 underline underline-offset-link"
                >
                    {RV_SHOW_SCAN}
                </button>
            </div>

            {/*
              * [EVD-1] ONE switch over the server-resolved evidence. There is
              * no `scope.answer && !skipped` compound here any more: that
              * expression let a falsy answer outvote a real grade, which is how
              * a 12/12 scope with a verbatim quotation rendered «the student
              * did not answer».
              */}
            {scope.answer.kind === 'own' || scope.answer.kind === 'inherited' ? (
                <>
                    {scope.answer.kind === 'inherited' && (
                        <p
                            data-answer-inherited
                            className="mb-1.5 text-gr-meta text-grade-ink-2"
                        >
                            {scope.answer.from
                                ? RV_ANSWER_INHERITED(scope.answer.from)
                                : RV_ANSWER_INHERITED_ANON}
                        </p>
                    )}
                    <AnswerBlock
                        scopeId={scope.scopeId}
                        answer={scope.answer.text}
                        highlight={highlight}
                        transient={highlightTransient}
                        subject={subject}
                    />
                </>
            ) : (
                <p
                    data-answer-missing
                    data-answer-state={scope.answer.kind}
                    className="mb-3.5 rounded-grade-ctl border border-grade-amber-200
                        bg-grade-amber-50 px-4 py-3 text-gr-body text-grade-amber-ink"
                >
                    <span
                        aria-hidden="true"
                        className="me-1.5 inline-block h-dot w-dot rounded-full
                            bg-grade-amber-dot relative top-px"
                    />
                    {/* «missing» accuses; «unavailable» admits. Never swap them. */}
                    {scope.answer.kind === 'missing'
                        ? RV_ANSWER_NONE
                        : RV_ANSWER_UNAVAILABLE}
                </p>
            )}

            <div>
                {scope.criteria.map((criterion) => {
                    const open = isCriterionOpen(criterion.terminalId);
                    const panelId = `breakdown-${criterion.terminalId}`;
                    const pinnedHere = pinnedTerminalId === criterion.terminalId;
                    const hasBreakdown = criterion.checks.length > 0;
                    return (
                    <div
                        key={criterion.terminalId}
                        data-terminal-id={criterion.terminalId}
                        data-expanded={hasBreakdown ? (open ? 'true' : 'false') : undefined}
                        className="mb-2.5 overflow-hidden rounded-grade-ctl border border-grade-line"
                    >
                        <div className="flex items-center justify-between gap-2.5 bg-grade-bar
                            px-3.5 py-2 text-gr-body font-semibold">
                            {/*
                              * [S4] The disclosure. A real <button aria-expanded
                              * aria-controls>, not <details>: the keyboard walk
                              * (S5) has to OPEN a criterion programmatically to
                              * focus a check inside it, and `details` fights
                              * that — plus its marker cannot be styled RTL
                              * without fighting the platform too.
                              *
                              * It wraps the chevron and the description only.
                              * The quote button must stay OUTSIDE it: a button
                              * inside a button is invalid HTML, and browsers
                              * resolve it by dropping one of them.
                              */}
                            {hasBreakdown ? (
                                <button
                                    type="button"
                                    aria-expanded={open}
                                    aria-controls={panelId}
                                    aria-label={open
                                        ? RV_BREAKDOWN_HIDE(criterion.description)
                                        : RV_BREAKDOWN_SHOW(criterion.description)}
                                    data-breakdown-for={criterion.terminalId}
                                    onClick={() => onToggleCriterion?.(criterion.terminalId)}
                                    className="flex min-w-0 flex-1 items-center gap-2 text-start
                                        font-semibold text-inherit"
                                >
                                    <span
                                        aria-hidden="true"
                                        className={[
                                            'shrink-0 text-grade-pencil transition-transform',
                                            'motion-reduce:transition-none',
                                            // RTL: closed points INTO the page
                                            // (leftward); open points down.
                                            open ? 'rotate-90' : 'rotate-180',
                                        ].join(' ')}
                                    >
                                        ▸
                                    </span>
                                    <span className="min-w-0">{criterion.description}</span>
                                </button>
                            ) : (
                                <span className="min-w-0 flex-1">{criterion.description}</span>
                            )}

                            {!open && hasBreakdown && (
                                <span className="shrink-0 whitespace-nowrap text-gr-meta
                                    font-normal text-grade-pencil-2">
                                    {RV_BREAKDOWN_COUNT(criterion.checks.length)}
                                </span>
                            )}

                            {/*
                              * [S3] The criterion's own quote button: the UNION
                              * of its checks' spans. It exists on the same rule
                              * as the per-check button — only when a mark will
                              * actually be painted — but taken over the checks:
                              * one that can be highlighted is enough for the
                              * union to have something to show. A criterion
                              * whose every quote was not_found gets no button,
                              * for the reason its rows get none.
                              */}
                            {onPinCriterion && criterion.checks.some((c) => c.canHighlight) ? (
                                <button
                                    type="button"
                                    title={RV_QUOTE_ALL_TITLE}
                                    // It is a TOGGLE, and `aria-pressed` is what
                                    // a screen reader announces as its state —
                                    // the teal fill says "lit" to the eye alone.
                                    aria-pressed={pinnedHere}
                                    data-terminal-quote={criterion.terminalId}
                                    data-pinned={pinnedHere ? 'true' : 'false'}
                                    onClick={() => onPinCriterion(criterion.terminalId)}
                                    className={[
                                        'inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap',
                                        'rounded-full border py-1 pe-2.5 ps-2.5 text-gr-meta',
                                        'font-medium text-primary-700 transition-all hover:bg-primary-50',
                                        pinnedHere
                                            ? 'border-grade-teal-line bg-primary-100 opacity-100'
                                            : 'border-grade-line bg-grade-card opacity-85',
                                    ].join(' ')}
                                >
                                    <span aria-hidden="true" className="font-serif text-gr-quote
                                        leading-none text-primary-600">
                                        ❝
                                    </span>
                                    {RV_QUOTE_ALL}
                                </button>
                            ) : null}
                            <span
                                dir="ltr"
                                className={[
                                    'min-w-tariff text-left text-gr-crit font-light leading-none',
                                    '[font-variant-numeric:tabular-nums] [unicode-bidi:isolate]',
                                    criterion.overridden
                                        ? 'font-medium text-grade-red'
                                        : 'text-grade-pencil',
                                ].join(' ')}
                            >
                                {formatPoints(criterion.awarded)} / {formatPoints(criterion.possible)}
                            </span>
                        </div>

                        {!hasBreakdown ? (
                            <p className="border-t border-grade-line-2 px-3.5 py-2.5
                                text-gr-meta text-grade-pencil">
                                {RV_SCOPE_FAILED_CHIP}
                            </p>
                        ) : open ? (
                            <div id={panelId}>
                                {criterion.checks.map((check) => (
                                    <CheckRow
                                        key={check.check_id}
                                        check={check}
                                        effectiveVerdict={check.verdict}
                                        overridden={check.overridden}
                                        awarded={check.awarded}
                                        outOf={check.outOf}
                                        focused={focusedCheckId === check.check_id}
                                        pinned={pinnedCheckId === check.check_id}
                                        note={check.note}
                                        noteOpen={openNoteCheckId === check.check_id}
                                        evidenceDisputed={check.evidenceDisputed}
                                        onFocus={() => onFocusCheck(check.check_id)}
                                        onHover={(h) => onHoverCheck(check.check_id, h)}
                                        onCycle={() => onCycle(check.terminalId, check.check_id)}
                                        onRevert={() => onRevert(check.terminalId, check.check_id)}
                                        onPin={() => onPin(check.check_id)}
                                        onNoteChange={(note) =>
                                            onNoteChange(check.terminalId, check.check_id, note)}
                                        onNoteClose={onNoteClose}
                                    />
                                ))}
                            </div>
                        ) : null}
                    </div>
                    );
                })}
            </div>

            <FeedbackCard
                title={RV_FB_TITLE(scope.title)}
                text={scope.feedback.text}
                state={scope.feedback.state as FeedbackState}
                teacherEdited={feedbackEdited}
                busy={feedbackBusy}
                onChange={(text) => onFeedbackChange(scope.scopeId, text)}
                onRegenerate={() => onFeedbackRegenerate(scope.scopeId)}
                offered={feedbackOffer}
                onAcceptOffer={() => onAcceptFeedbackOffer?.(scope.scopeId)}
                onDismissOffer={() => onDismissFeedbackOffer?.(scope.scopeId)}
            />
        </section>
    );
}
