'use client';

import Link from 'next/link';

import type { ReviewScope } from '@/utils/grade-review-model';
import type { QueueState } from '@/utils/grade-review-cursor';
import { formatPoints } from '@/utils/points-display';
import { StampSvg } from './StampSvg';
import { RevisionMenu, type RevisionMenuProps } from './RevisionMenu';
import {
    RV_APPROVE,
    RV_APPROVING,
    RV_KEYS_ALL,
    RV_KEYS_REST,
    RV_KEY_MARKER,
    RV_KEY_MOVE,
    RV_KEY_REVERT,
    RV_KEY_VERDICT,
    RV_LOOK_COUNT,
    RV_MINI_THUMB_TITLE,
    RV_NAV_HEADING,
    RV_NAV_NEXT,
    RV_NAV_PREV,
    RV_QUEUE_GRADING,
    RV_QUEUE_NEXT,
    RV_QUEUE_SEP,
    RV_QUEUE_UNLANDED,
    RV_SAVED,
    RV_SAVE_FAILED,
    RV_SAVING,
    RV_TOTAL_MINE,
    RV_TOTAL_PROPOSAL,
    RV_VBANNER_CTA,
    RV_VBANNER_MANUAL,
    RV_WAIT_ETA_UNKNOWN,
    RV_WAIT_GRADING,
    RV_WAIT_TITLE,
    RV_WAIT_TO_DASHBOARD,
} from '@/copy/grade-review';

/**
 * The frame around the checklist: top bar, queue line, scope nav, bottom bar,
 * the wait card and the version banner (R1, R2, R3, R12, R13).
 *
 * They live together because they share one thing — they are the only places
 * that speak about the test AS A WHOLE, and every one of them is a promise
 * about state she cannot otherwise see: what her total is now, who is next,
 * whether her work is saved. Splitting them across five files would let those
 * promises drift apart.
 */

// ── R1 ─────────────────────────────────────────────────────────────────────
export interface ReviewTopBarProps {
    studentName: string;
    meta: string;
    total: string;
    possible: string;
    anyOverride: boolean;
    approved: boolean;
    canPrev: boolean;
    canNext: boolean;
    onPrev: () => void;
    onNext: () => void;
    onOpenPreview: () => void;
    /**
     * Play the stamp coming down (R12). Set for one beat right after
     * `/approve` returns: the signature is the moment the grade becomes hers,
     * and it is the only animation on this surface that marks a commitment.
     */
    stampPressed?: boolean;
    /** §2 — the revision affordances, unchanged. Omitted → no overflow. */
    revision?: RevisionMenuProps;
    /**
     * R1: the mini thumb IS page 1 of her scan (an object URL, resolved by the
     * route through the authorized seam). Without it the frame was empty and
     * read as a broken image beside the student's name — the mockup's `.mini`
     * carries the page. Absent when the feed has no page image (§3.5a: an
     * empty paper frame, never a broken-image glyph).
     */
    thumbUrl?: string | null;
}

export function ReviewTopBar({
    studentName, meta, total, possible, anyOverride, approved,
    canPrev, canNext, onPrev, onNext, onOpenPreview,
    stampPressed = false, revision, thumbUrl = null,
}: ReviewTopBarProps) {
    return (
        <div className="sticky top-0 z-40 -mx-6 mb-4 border-b border-grade-line
            bg-grade-canvas/90 px-6 pb-2.5 pt-3 backdrop-blur">
            <div className="mx-auto flex max-w-review items-center justify-between gap-4">
                <button
                    type="button"
                    onClick={onPrev}
                    disabled={!canPrev}
                    className="flex min-w-nav-btn items-center justify-center gap-2
                        rounded-grade-ctl border border-grade-line bg-grade-card px-3.5 py-2
                        text-gr-body text-grade-ink-2 hover:border-grade-pencil-2
                        disabled:opacity-40"
                >
                    <span aria-hidden="true" className="text-gr-arrow leading-none">›</span>
                    {RV_NAV_PREV}
                </button>

                <div className="flex flex-1 items-center justify-center gap-3.5">
                    <button
                        type="button"
                        title={RV_MINI_THUMB_TITLE}
                        onClick={onOpenPreview}
                        className="relative h-mini-thumb w-9 flex-none overflow-hidden rounded
                            border border-grade-line bg-grade-paper"
                    >
                        {thumbUrl ? (
                            // eslint-disable-next-line @next/next/no-img-element
                            <img
                                src={thumbUrl}
                                alt=""
                                data-mini-thumb
                                className="absolute inset-0 h-full w-full object-cover object-top"
                            />
                        ) : null}
                        {approved ? (
                            <span className="absolute left-0 top-0" data-stamp>
                                <StampSvg
                                    score={formatPoints(total)}
                                    size={30}
                                    pressed={stampPressed}
                                />
                            </span>
                        ) : null}
                    </button>
                    <div>
                        <div className="text-gr-name">{studentName}</div>
                        <div className="text-gr-meta text-grade-pencil">{meta}</div>
                    </div>
                    {revision ? <RevisionMenu {...revision} /> : null}
                </div>

                <div className="min-w-total text-center">
                    <div
                        dir="ltr"
                        data-total
                        data-overridden={anyOverride ? 'true' : 'false'}
                        className={[
                            'text-gr-total [font-variant-numeric:tabular-nums]',
                            '[unicode-bidi:isolate]',
                            anyOverride ? 'font-normal text-grade-red' : 'text-grade-pencil',
                        ].join(' ')}
                    >
                        {formatPoints(total)}
                    </div>
                    <div className="mt-0.5 text-gr-chip text-grade-pencil">
                        {anyOverride
                            ? RV_TOTAL_MINE(formatPoints(possible))
                            : RV_TOTAL_PROPOSAL(formatPoints(possible))}
                    </div>
                </div>

                <button
                    type="button"
                    onClick={onNext}
                    disabled={!canNext}
                    className="flex min-w-nav-btn items-center justify-center gap-2
                        rounded-grade-ctl border border-grade-line bg-grade-card px-3.5 py-2
                        text-gr-body text-grade-ink-2 hover:border-grade-pencil-2
                        disabled:opacity-40"
                >
                    {RV_NAV_NEXT}
                    <span aria-hidden="true" className="text-gr-arrow leading-none">‹</span>
                </button>
            </div>
        </div>
    );
}

// ── R2 ─────────────────────────────────────────────────────────────────────
export function QueueLine({ queue, eta }: { queue: QueueState; eta: string | null }) {
    const parts: string[] = [];
    if (queue.nextLanded?.student_name) {
        parts.push(RV_QUEUE_NEXT(queue.nextLanded.student_name));
    }
    const grading = queue.grading[0];
    if (grading?.student_name) parts.push(RV_QUEUE_GRADING(grading.student_name, eta));
    // The one just NAMED is not also "N more still unlanded" — counting it
    // twice tells her there are more tests in flight than there are.
    const unlanded = queue.grading.length - (grading?.student_name ? 1 : 0);
    if (unlanded > 0) parts.push(RV_QUEUE_UNLANDED(unlanded));
    if (!parts.length) return null;

    return (
        <p className="mx-auto mt-2 max-w-review text-center text-gr-meta text-grade-pencil">
            {parts.join(RV_QUEUE_SEP)}
        </p>
    );
}

// ── R3 ─────────────────────────────────────────────────────────────────────
export function ScopeNav({
    scopes, markersByScope, activeScopeId, onJump,
}: {
    scopes: ReviewScope[];
    /** From `markerCountByScope` — the SAME count F walks and look_count
     *  reports. The model's own per-scope tally omitted flag markers, so the
     *  rail could show no dot on a question F would stop at twice. */
    markersByScope: Record<string, number>;
    activeScopeId: string | null;
    onJump: (scopeId: string) => void;
}) {
    return (
        <nav className="sticky top-scope-nav hidden flex-col gap-0.5 rail:flex">
            <div className="mx-2.5 mb-1.5 text-gr-chip tracking-wide text-grade-pencil">
                {RV_NAV_HEADING}
            </div>
            {scopes.map((scope) => {
                const markerCount = markersByScope[scope.scopeId] ?? 0;
                return (
                <button
                    key={scope.scopeId}
                    type="button"
                    onClick={() => onJump(scope.scopeId)}
                    data-nav-scope={scope.scopeId}
                    className={[
                        'flex items-center justify-between rounded-grade-sm px-3 py-2',
                        'text-start text-gr-meta',
                        activeScopeId === scope.scopeId
                            ? 'bg-grade-card font-semibold text-primary-700 shadow-grade'
                            : 'text-grade-ink-2 hover:bg-grade-card',
                    ].join(' ')}
                >
                    <span>
                        {scope.title}
                        {markerCount > 0 ? (
                            <span
                                aria-label={RV_LOOK_COUNT(markerCount)}
                                className="ms-1.5 inline-block h-dot w-dot rounded-full
                                    bg-grade-amber-dot relative top-px"
                            />
                        ) : null}
                    </span>
                    <span
                        dir="ltr"
                        className={[
                            'text-gr-meta [font-variant-numeric:tabular-nums]',
                            '[unicode-bidi:isolate]',
                            scope.overridden
                                ? 'font-medium text-grade-red'
                                : 'font-light text-grade-pencil',
                        ].join(' ')}
                    >
                        {formatPoints(scope.awarded)}/{formatPoints(scope.possible)}
                    </span>
                </button>
                );
            })}
        </nav>
    );
}

// ── R12 ────────────────────────────────────────────────────────────────────
export type SaveState = 'saved' | 'saving' | 'failed';

export function ReviewBottomBar({
    saveState, approving, canApprove, onApprove, onShowKeys,
}: {
    saveState: SaveState;
    approving: boolean;
    canApprove: boolean;
    onApprove: () => void;
    onShowKeys: () => void;
}) {
    return (
        <div className="fixed inset-x-0 bottom-0 z-50 border-t border-grade-line
            bg-grade-bar px-6 py-2.5">
            <div className="mx-auto flex max-w-review items-center justify-between gap-4">
                <div className="flex flex-wrap items-center gap-4 text-gr-meta text-grade-pencil">
                    <span
                        data-save-state={saveState}
                        className={saveState === 'failed'
                            ? 'text-grade-red'
                            : 'text-primary-700'}
                    >
                        {saveState === 'failed' ? RV_SAVE_FAILED
                            : saveState === 'saving' ? RV_SAVING
                                : `${RV_SAVED} ✓`}
                    </span>
                    <span className="hidden desk:inline">
                        <Kbd>↓</Kbd><Kbd>↑</Kbd> {RV_KEY_MOVE}
                    </span>
                    <span className="hidden desk:inline"><Kbd>Space</Kbd> {RV_KEY_VERDICT}</span>
                    <span className="hidden desk:inline"><Kbd>⌫</Kbd> {RV_KEY_REVERT}</span>
                    <span className="hidden desk:inline"><Kbd>F</Kbd> {RV_KEY_MARKER}</span>
                    <button
                        type="button"
                        onClick={onShowKeys}
                        title={RV_KEYS_REST}
                        className="text-primary-700 underline underline-offset-link"
                    >
                        {RV_KEYS_ALL}
                    </button>
                </div>

                <button
                    type="button"
                    onClick={onApprove}
                    disabled={!canApprove || approving}
                    className="inline-flex items-center gap-2 rounded-grade-ctl border
                        border-primary-600 bg-primary-600 px-4 py-2.5 text-gr-body
                        font-medium text-white hover:border-primary-700 hover:bg-primary-700
                        disabled:opacity-50"
                >
                    {approving ? RV_APPROVING : RV_APPROVE}
                    <kbd className="rounded border border-white/35 bg-white/20 px-1.5
                        py-px font-mono text-gr-sm">Ctrl ↵</kbd>
                </button>
            </div>
        </div>
    );
}

function Kbd({ children }: { children: React.ReactNode }) {
    return (
        <kbd className="rounded border border-b-2 border-grade-line bg-grade-card px-1.5
            py-px font-mono text-gr-chip text-grade-ink-2">
            {children}
        </kbd>
    );
}

// ── the wait card ──────────────────────────────────────────────────────────
export function WaitCard({
    gradingCount, eta, batchHref,
}: {
    gradingCount: number;
    eta: string | null;
    batchHref: string;
}) {
    return (
        <div
            data-wait-card
            className="rounded-grade border border-dashed border-grade-line bg-grade-card
                p-6 text-center text-grade-ink-2"
        >
            <p className="text-gr-h2 text-grade-ink">{RV_WAIT_TITLE}</p>
            <p className="mt-2 text-gr-body">
                {RV_WAIT_GRADING(gradingCount)}{' '}
                {/* `eta` arrives already phrased («עוד כ-2 דקות», from etaText);
                    wrapping it again read «עוד עוד כ-2 דקות». */}
                {gradingCount > 0 ? (eta ?? RV_WAIT_ETA_UNKNOWN) : null}
            </p>
            <Link
                href={batchHref}
                className="mt-3 inline-block text-primary-700 underline underline-offset-link"
            >
                {RV_WAIT_TO_DASHBOARD}
            </Link>
        </div>
    );
}

// ── R13 ────────────────────────────────────────────────────────────────────
export function VersionBanner({
    version, onJump,
}: {
    /** null = the feed did not say; the banner omits the number. */
    version: number | null;
    onJump?: () => void;
}) {
    return (
        <div
            data-version-banner
            className="mb-4 flex items-center justify-between gap-3 rounded-grade-ctl border
                border-grade-violet-line bg-grade-violet-50 px-4 py-2.5 text-gr-body
                text-grade-violet-ink"
        >
            <span>{RV_VBANNER_MANUAL(version)}</span>
            {onJump ? (
                <button
                    type="button"
                    onClick={onJump}
                    className="underline underline-offset-link"
                >
                    {RV_VBANNER_CTA}
                </button>
            ) : null}
        </div>
    );
}
