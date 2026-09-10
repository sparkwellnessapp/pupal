'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

import {
    attentionLine, downloadSummary, etaText, rollupOf, sessionSummary, stepsLine,
    type BatchEta, type DownloadSummary, type GradedItem,
} from '@/utils/grade-dashboard';

/** The server's answer to «what will the ZIP hold». */
export interface ManifestLike {
    // Optional, as the GENERATED wire type declares them: a manifest field the
    // server omits is an empty bucket, not a missing manifest.
    included?: readonly { graded_test_id?: string }[] | null;
    excluded_not_approved?: readonly { graded_test_id?: string }[] | null;
    excluded_unavailable?: readonly { graded_test_id?: string }[] | null;
}
import {
    DASH_ATTENTION_MARKERS, DASH_ATTENTION_OPEN, DASH_ATTENTION_PREFIX,
    DASH_CONTINUE, DASH_DONE_BANNER, DASH_DONE_WITH_FAILURES, DASH_DOWNLOAD,
    DASH_DOWNLOAD_ALL, DASH_ETA_LANDING, DASH_ETA_REMAINING, DASH_ETA_UNKNOWN,
    DASH_STEP_APPROVE, DASH_STEP_AUDIT, DASH_STEP_AUDIT_DONE, DASH_STEP_GRADING,
    DASH_SUB, DASH_TITLE,
} from '@/copy/grade-review';
import { DownloadModal } from './DownloadModal';
import { Pile } from './Pile';

/**
 * לוח המקבץ — the grade-review dashboard (spec §4.1, D1–D10).
 *
 * It answers three questions and nothing else: **how far along is this batch,
 * which test needs me most, and which one am I looking at.** Everything the
 * mockup deliberately stripped stays stripped — no counts row (the pile already
 * shows it), no legend (the captions say it), no percentage bar.
 *
 * ── ONE ATTENTION SLOT ───────────────────────────────────────────────────
 * D3 gives it three variants and a priority, not three stacked banners. A
 * dashboard with four things shouting is a dashboard she learns to skim, and
 * the thing worth shouting about is always exactly one: the test that most
 * needs her, or the fact that she is finished.
 *
 * The audit banner would outrank the worst test; it is deferred (R-1), so
 * `audit_status: "disabled"` renders TWO steps and no audit surface anywhere.
 */

export interface GradeDashboardProps {
    items: readonly GradedItem[];
    /**
     * The BATCH's test count — the denominator for every "k of N".
     *
     * `graded_tests` only carries rows for tests whose transcription she has
     * accepted, so counting the feed against itself would report «נחתו 2 מתוך 2»
     * and «הכול מוכן» on a ten-document batch with eight still ungraded.
     */
    batchTotal?: number | null;
    auditStatus: string;
    eta: BatchEta | null;
    /**
     * Header sub-line parts (D1: rubric · class · count).
     *
     * OMITTED in the app, and that is a deliberate deviation from the spec:
     * §4.1 D1 assumes the grade dashboard OWNS its page, but here it is a
     * section of the batch page, whose own header already says the rubric, the
     * class and the count two hundred pixels above. Repeating them makes the
     * page look like two dashboards stacked. The section names the PHASE; the
     * page names the batch.
     */
    subtitle?: (string | null | undefined)[];
    startedAt?: string | null;
    completedAt?: string | null;
    onOpenReview: (item: GradedItem) => void;
    onOpenPreview: (item: GradedItem) => void;
    onRetry: (item: GradedItem) => void;
    onContinue: (item: GradedItem) => void;
    onDownload: () => void;
    /**
     * D9: «DownloadModal from the manifest». Fetched when the modal opens; the
     * feed-derived count paints first and is REPLACED by the server's answer.
     * If the manifest fails, the feed count stands and the modal says so via
     * `data-download-source="feed"` — a display path degrades, it does not
     * refuse (§3.5a). The download itself is server-side approved-only either
     * way; the manifest only changes what she is TOLD before clicking.
     */
    loadManifest?: () => Promise<ManifestLike>;
    /** Failed tests she has already sent back to grading this session (D6). */
    retriedIds?: ReadonlySet<string>;
}

export function GradeDashboard({
    items, batchTotal, auditStatus, eta, subtitle, startedAt, completedAt,
    onOpenReview, onOpenPreview, onRetry, onContinue, onDownload, loadManifest,
    retriedIds,
}: GradeDashboardProps) {
    const [downloadOpen, setDownloadOpen] = useState(false);
    const [manifestSummary, setManifestSummary] = useState<DownloadSummary | null>(null);
    // Refs, so the manifest effect keys on the modal OPENING and nothing else.
    // The dashboard polls; a dependency on `items` or on the caller's function
    // identity re-ran the fetch on every tick, flipping the modal back to the
    // feed count each time and — on a slow link — never letting the manifest land.
    const loadManifestRef = useRef(loadManifest);
    loadManifestRef.current = loadManifest;
    const itemsRef = useRef(items);
    itemsRef.current = items;

    const rollup = useMemo(() => rollupOf(items, batchTotal), [items, batchTotal]);
    const steps = useMemo(() => stepsLine(rollup, auditStatus, {
        grading: DASH_STEP_GRADING,
        audit: DASH_STEP_AUDIT,
        auditDone: DASH_STEP_AUDIT_DONE,
        approve: DASH_STEP_APPROVE,
    }), [rollup, auditStatus]);
    const attention = useMemo(
        () => attentionLine(items, batchTotal), [items, batchTotal]);
    const summary = useMemo(
        () => downloadSummary(items), [items]);
    const session = useMemo(
        () => sessionSummary(items, startedAt, completedAt), [items, startedAt, completedAt]);

    const complete = attention.kind === 'done';

    useEffect(() => {
        const load = loadManifestRef.current;
        if (!downloadOpen || !load) return;
        let cancelled = false;
        setManifestSummary(null);
        load()
            .then((manifest) => {
                if (cancelled) return;
                // The server files FAILED tests under `excluded_not_approved`
                // (`returned_exam.py` — a failed row is a non-approved leaf).
                // The modal names them apart, because the remedy differs
                // (retry, not review), so they are SPLIT here by id against the
                // feed rather than counted twice — once as "not approved" and
                // once as "failed" — which is what the first version did.
                const failedIds = new Set(itemsRef.current
                    .filter((i) => i.status === 'failed').map((i) => i.graded_test_id));
                const notApproved = manifest.excluded_not_approved ?? [];
                const failed = notApproved.filter(
                    (m) => m.graded_test_id && failedIds.has(m.graded_test_id)).length;
                setManifestSummary({
                    included: manifest.included?.length ?? 0,
                    excludedNotApproved: notApproved.length - failed,
                    excludedUnavailable: manifest.excluded_unavailable?.length ?? 0,
                    excludedFailed: failed,
                });
            })
            .catch(() => { /* the feed-derived summary stands; see the prop doc */ });
        return () => { cancelled = true; };
    }, [downloadOpen]);
    /**
     * The ETA answers "when will there be something to review". Once every test
     * has landed there is nothing left to wait for, and the server keeps
     * returning a `remaining` estimate regardless — so a stale «עוד כ-2 דקות»
     * would sit on the screen for the rest of the session.
     */
    const gradingDone = steps[0]?.state === 'done';
    // The first landed, unapproved test — where «המשיכי» goes when nothing is
    // shouting for attention.
    const firstReviewable = items.find((i) => i.status === 'draft');
    const eta_ = complete || gradingDone ? null : etaText(eta, {
        firstLanding: DASH_ETA_LANDING,
        remaining: DASH_ETA_REMAINING,
        unknown: DASH_ETA_UNKNOWN,
    });

    return (
        <section data-grade-dashboard className="font-assistant">
            {/* D1 */}
            <header className="mb-4 flex flex-wrap items-start justify-between gap-5">
                <div>
                    <h2 className="text-gr-h1 text-grade-ink">{DASH_TITLE}</h2>
                    {subtitle && subtitle.filter(Boolean).length > 0 ? (
                        <p className="mt-0.5 text-gr-body text-grade-pencil">
                            {DASH_SUB(subtitle)}
                        </p>
                    ) : null}
                </div>
                <div className="flex flex-wrap justify-end gap-2.5">
                    <button
                        type="button"
                        data-download
                        onClick={() => setDownloadOpen(true)}
                        className={[
                            'inline-flex items-center gap-2 rounded-grade-ctl border px-4 py-2',
                            'text-gr-body font-medium transition-colors',
                            complete
                                ? 'border-primary-600 bg-primary-600 text-white hover:bg-primary-700'
                                : 'border-grade-line bg-grade-card text-grade-ink hover:border-grade-pencil-2',
                        ].join(' ')}
                    >
                        {complete
                            ? DASH_DOWNLOAD_ALL(summary.included)
                            : (
                                <>
                                    {DASH_DOWNLOAD}
                                    <span className="rounded-full border border-grade-line
                                        bg-grade-bar px-2 text-gr-chip text-grade-ink-2">
                                        {summary.included}
                                    </span>
                                </>
                            )}
                    </button>
                    {!complete && firstReviewable ? (
                        <button
                            type="button"
                            data-continue
                            onClick={() => onContinue(firstReviewable)}
                            className="inline-flex items-center gap-2 rounded-grade-ctl
                                border border-primary-600 bg-primary-600 px-4 py-2
                                text-gr-body font-medium text-white hover:bg-primary-700"
                        >
                            {DASH_CONTINUE}
                            <span aria-hidden="true">←</span>
                        </button>
                    ) : null}
                </div>
            </header>

            {/* D2 */}
            <div className="flex flex-wrap items-center gap-3.5 text-gr-body
                text-grade-pencil-2">
                {steps.map((step, i) => (
                    <span key={step.key} className="flex items-center gap-3.5">
                        {i > 0 ? (
                            <span aria-hidden="true" className="h-px w-7 bg-grade-line" />
                        ) : null}
                        <span
                            data-step={step.key}
                            data-step-state={step.state}
                            className={[
                                'flex items-center gap-2',
                                // done and active were rendering IDENTICALLY, so
                                // the line could not say where she is. Done is
                                // quieter than the step she is standing on.
                                step.state === 'active'
                                    ? 'font-semibold text-primary-700'
                                    : step.state === 'done'
                                        ? 'font-medium text-primary-700/80'
                                        : '',
                            ].join(' ')}
                        >
                            <i
                                aria-hidden="true"
                                className={[
                                    'inline-block h-2 w-2 rounded-full bg-current',
                                    step.state === 'active'
                                        ? 'motion-safe:animate-step-pulse' : '',
                                ].join(' ')}
                            />
                            {step.label}
                        </span>
                    </span>
                ))}
            </div>
            {eta_ ? (
                <p data-eta className="mb-5 mt-2 text-gr-body text-grade-ink-2">{eta_}</p>
            ) : <div className="mb-3.5" />}

            {/* D3 — one slot */}
            {attention.kind === 'done' ? (
                <div
                    data-attention="done"
                    className="mb-5 flex items-center justify-between gap-3 rounded-grade-ctl
                        border border-grade-teal-line bg-primary-50 px-4 py-2.5
                        text-gr-body text-primary-700"
                >
                    <span>
                        {DASH_DONE_BANNER(session.approved, session.minutes)}
                        {session.failed > 0
                            ? ` ${DASH_DONE_WITH_FAILURES(session.failed)}` : ''}
                    </span>
                </div>
            ) : attention.kind === 'worst' && attention.item ? (
                <div
                    data-attention="worst"
                    className="mb-5 flex items-center justify-between gap-3 rounded-grade-ctl
                        border border-grade-amber-200 bg-grade-amber-50 px-4 py-2.5
                        text-gr-body text-grade-amber-ink"
                >
                    <span>
                        <span aria-hidden="true" className="me-1.5 inline-block h-dot w-dot
                            rounded-full bg-grade-amber-dot relative top-px" />
                        {DASH_ATTENTION_PREFIX}{' '}
                        <b>{attention.item.student_name}</b>
                        {' — '}
                        {DASH_ATTENTION_MARKERS(attention.markers ?? 0)}
                    </span>
                    <button
                        type="button"
                        onClick={() => onOpenReview(attention.item!)}
                        className="shrink-0 underline underline-offset-link"
                    >
                        {DASH_ATTENTION_OPEN}
                    </button>
                </div>
            ) : null}

            {/* D6 */}
            <Pile
                items={items}
                retriedIds={retriedIds}
                onOpenReview={onOpenReview}
                onOpenPreview={onOpenPreview}
                onRetry={onRetry}
            />

            {/* D9 */}
            {downloadOpen ? (
                <DownloadModal
                    summary={manifestSummary ?? summary}
                    source={manifestSummary ? 'manifest' : 'feed'}
                    onConfirm={() => { setDownloadOpen(false); onDownload(); }}
                    onClose={() => setDownloadOpen(false)}
                />
            ) : null}
        </section>
    );
}
