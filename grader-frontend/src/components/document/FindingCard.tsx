'use client';

import { AlertCircle, Lightbulb, Check, MinusCircle } from 'lucide-react';
import type { Finding } from '@/utils/findings';
import { formatPoints } from '@/utils/rubric-display';

/**
 * PR-6 §2 — THE FINDING CARD. One card per event, speaking in Vivi's voice.
 *
 * The card is where "Vivi proposes, the teacher decides" becomes tangible, so its
 * whole job is to keep three claims separate and honest:
 *
 *   - the PRESENT-TENSE body comes only from live recomputation;
 *   - the ORIGINAL-DOCUMENT residual is framed as the past and never asserts now;
 *   - the PROPOSAL is a button she presses, never something already done.
 *
 * Nothing here vanishes. A resolved finding collapses to a ✓ with its residual; a
 * dismissed one collapses to her decision. Both stay on screen, and neither is ever
 * re-asked.
 */

interface FindingCardProps {
    finding: Finding;
    /** Teacher-facing label for the anchor ("שאלה 1 · סעיף א"), never a raw id. */
    scopeText: string;
    onApplyFix(finding: Finding): void;
    onUndoFix(finding: Finding): void;
    onDismiss(finding: Finding): void;
    onReopen(finding: Finding): void;
    onJump(finding: Finding): void;
}

const ACCENT = {
    // A blocker she must resolve — warm and serious, never alarming.
    blocking: 'border-amber-300 bg-amber-50/70',
    // A suggestion — calm, clearly a different weight of news.
    advisory: 'border-primary-200 bg-primary-50/60',
    // Settled states recede.
    settled: 'border-surface-200 bg-surface-50',
} as const;

function Settled({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
    return (
        <div className={`flex items-start gap-2 rounded-lg border px-3 py-2 text-doc-meta text-surface-600 ${ACCENT.settled}`}>
            {icon}
            <div className="min-w-0">{children}</div>
        </div>
    );
}

export function FindingCard({
    finding, scopeText, onApplyFix, onUndoFix, onDismiss, onReopen, onJump,
}: FindingCardProps) {
    const { status, variant, fix } = finding;

    // ── RESOLVED — collapsed, with the honest residual where one is true. The
    // rubric is right now; the FILE she uploaded still says what it said, and
    // pretending otherwise would be the same lie in the opposite direction.
    if (status === 'resolved') {
        return (
            <Settled icon={<Check size={15} className="flex-shrink-0 mt-0.5 text-emerald-600" />}>
                <span className="text-emerald-700">תוקן במחוון</span>
                {fix?.displayCurrentValue != null && (
                    <>
                        <span className="text-surface-400"> · </span>
                        <span>בקובץ המקורי עדיין מצוין {formatPoints(fix.displayCurrentValue)}</span>
                    </>
                )}
                <button
                    type="button"
                    onClick={() => onUndoFix(finding)}
                    className="mr-2 underline decoration-surface-300 underline-offset-2 hover:text-surface-900"
                >בטלי</button>
            </Settled>
        );
    }

    // ── DISMISSED — her judgment, recorded and respected. Distinct from resolved:
    // nothing was fixed, and the card says so without nagging.
    if (status === 'dismissed') {
        return (
            <Settled icon={<MinusCircle size={15} className="flex-shrink-0 mt-0.5 text-surface-400" />}>
                <span>נשאר כפי שהוא — לבחירתך</span>
                <button
                    type="button"
                    onClick={() => onReopen(finding)}
                    className="mr-2 underline decoration-surface-300 underline-offset-2 hover:text-surface-900"
                >החזירי את הממצא</button>
            </Settled>
        );
    }

    // ── OPEN ─────────────────────────────────────────────────────────────────
    // A live invariant violation is blocking even when no one-click fix exists
    // (a D3 SHADOW deliberately has none): the compiler will reject it, so the
    // card must not soften into a lightbulb suggestion.
    const blocking = variant === 'blocking_fix' || finding.hasLiveBlocker || finding.severity === 'error';
    return (
        <div
            data-finding-key={finding.key}
            className={`rounded-lg border px-3.5 py-3 space-y-2 ${blocking ? ACCENT.blocking : ACCENT.advisory}`}
        >
            <div className="flex items-start gap-2">
                {blocking
                    ? <AlertCircle size={16} className="flex-shrink-0 mt-0.5 text-amber-600" />
                    : <Lightbulb size={16} className="flex-shrink-0 mt-0.5 text-primary-600" />}
                <div className="min-w-0 space-y-1.5">
                    {/* PRESENT TENSE — recomputed, therefore safe to state as now. */}
                    {finding.liveMessage && (
                        <p className="text-doc-table text-surface-800">{finding.liveMessage}</p>
                    )}
                    {/* The advisory's why, already hedged to its confidence register. */}
                    {finding.explanation && (
                        <p className="text-doc-meta text-surface-600">{finding.explanation}</p>
                    )}
                    {/* PAST TENSE ONLY — the document, never a claim about the editor. */}
                    {fix?.displayCurrentValue != null && (
                        <p className="text-doc-meta text-surface-500">
                            בקובץ המקורי מצוין {formatPoints(fix.displayCurrentValue)}
                        </p>
                    )}
                    {/* D3 — a shadow points at its root instead of offering a local fix. */}
                    {finding.explainedBy && (
                        <p className="text-doc-meta text-surface-600">
                            נובע כנראה מטעות אחרת שזוהתה —
                            {' '}
                            <button
                                type="button"
                                onClick={() => onJump({ ...finding, scopeId: finding.explainedBy!.scopeId })}
                                className="underline decoration-surface-300 underline-offset-2 hover:text-surface-900"
                            >עברי לממצא המקורי</button>
                            {' '}
                            — התיקון המוצע שם פותר גם את זה.
                        </p>
                    )}
                </div>
            </div>

            <div className="flex flex-wrap items-center gap-2 pr-6">
                {fix && (
                    <button
                        type="button"
                        onClick={() => onApplyFix(finding)}
                        className={`rounded-md px-3 py-1.5 text-doc-meta font-medium transition-colors ${
                            blocking
                                ? 'bg-amber-600 text-white hover:bg-amber-700'
                                : 'bg-primary-600 text-white hover:bg-primary-700'}`}
                    >{fix.label}</button>
                )}
                {/* The manual path: navigate + highlight, then HER edits satisfy the
                    validator and the card closes on its own. */}
                <button
                    type="button"
                    onClick={() => onJump(finding)}
                    className="rounded-md px-3 py-1.5 text-doc-meta text-surface-700 hover:bg-surface-100 transition-colors"
                >{fix ? 'עדכני את הקריטריונים בעצמך' : `עברי ל${scopeText}`}</button>
                {/* «השאירי כך» is offered on ADVISORIES only. A blocking finding is a
                    live invariant violation, and the Contract compiler recomputes and
                    rejects it regardless of what the UI agrees to — offering to leave
                    it would promise something the system cannot honour. Her way past a
                    blocker is to fix it: one click, or by hand. */}
                {!blocking && (
                    <button
                        type="button"
                        onClick={() => onDismiss(finding)}
                        className="rounded-md px-3 py-1.5 text-doc-meta text-surface-500 hover:text-surface-800 hover:bg-surface-100 transition-colors"
                    >השאירי כך</button>
                )}
            </div>
        </div>
    );
}
