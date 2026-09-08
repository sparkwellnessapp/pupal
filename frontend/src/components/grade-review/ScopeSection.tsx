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
    RV_ANSWER_NONE,
    RV_FB_TITLE,
    RV_QUESTION_TOGGLE,
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

            {scope.answer && !skipped ? (
                <AnswerBlock
                    answer={scope.answer}
                    highlight={highlight}
                    transient={highlightTransient}
                    subject={subject}
                />
            ) : (
                <p
                    data-answer-missing
                    className="mb-3.5 rounded-grade-ctl border border-grade-amber-200
                        bg-grade-amber-50 px-4 py-3 text-gr-body text-grade-amber-ink"
                >
                    <span
                        aria-hidden="true"
                        className="me-1.5 inline-block h-dot w-dot rounded-full
                            bg-grade-amber-dot relative top-px"
                    />
                    {RV_ANSWER_NONE}
                </p>
            )}

            <div>
                {scope.criteria.map((criterion) => (
                    <div
                        key={criterion.terminalId}
                        data-terminal-id={criterion.terminalId}
                        className="mb-2.5 overflow-hidden rounded-grade-ctl border border-grade-line"
                    >
                        <div className="flex items-center justify-between gap-2.5 bg-grade-bar
                            px-3.5 py-2 text-gr-body font-semibold">
                            <span>{criterion.description}</span>
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

                        {criterion.checks.length === 0 ? (
                            <p className="border-t border-grade-line-2 px-3.5 py-2.5
                                text-gr-meta text-grade-pencil">
                                {RV_SCOPE_FAILED_CHIP}
                            </p>
                        ) : criterion.checks.map((check) => (
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
                ))}
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
