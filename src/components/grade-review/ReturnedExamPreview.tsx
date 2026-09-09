'use client';

import { useCallback, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/lib/api';

import {
    PV_APPLY_ALL, PV_APPLY_ALL_DONE, PV_APPLY_ALL_FAILED, PV_DOWNLOAD,
    PV_DOWNLOAD_FAILED, PV_DOWNLOAD_PREPARING, PV_EDIT, PV_HINT_APPENDIX,
    PV_HINT_SCAN, PV_HINT_STAMP, PV_HINT_STAMP_AUTO, PV_REAPPROVE, PV_STALE, PV_STAMP_SAVED,
    PV_STAMP_SAVE_FAILED, PV_STRIP_APPENDIX, PV_STRIP_SCAN, PV_SUB, PV_TITLE,
    PV_TOGGLE_FAILED, PV_TOGGLE_OFF, PV_TOGGLE_ON,
} from '@/copy/grade-review';
import {
    buildAppendix, formatSignedAt, formatSignedDate, isReturnedExamStale,
    pageStrip, paginateAppendix, stampBox,
    type GradedTestContract, type StampPosition,
} from '@/utils/returned-exam';
import { formatPoints } from '@/utils/points-display';
import { AppendixPage } from './AppendixPage';
import { BreakdownToggle } from './BreakdownToggle';
import { StampDrag } from './StampDrag';
import { StampSvg } from './StampSvg';

/**
 * P1–P8 — המבחן המוחזר.
 *
 * The screen exists so that what she signs is what the student receives. Every
 * decision here is per-artefact except one, the breakdown toggle, which is
 * per-batch and says so in its (i).
 *
 * ── WHY CONFIRMATIONS ARE TOASTS AND THE STALE BANNER IS NOT ─────────────
 * Every confirmation here is an EVENT — saved, applied, still rendering — and
 * an inline strip for those pushed the page down a row on every drag, which the
 * visual gate caught immediately: the artefact she is aiming at moves while she
 * aims at it. The stale banner stays inline because it is not an event but a
 * standing fact about the document below it, and it must not be dismissable by
 * ignoring it. This is also the app's own convention (§ error surface).
 *
 * ── THE ONE STATE THAT IS NOT LOCAL ──────────────────────────────────────
 * `stamp_position` and `appendix_include_criteria` live on the server, and the
 * optimistic value is kept ONLY until the write answers. A failed PATCH rolls
 * the switch back and says so — a control that looks like it took effect but
 * did not is how a batch of thirty gets the wrong appendix.
 */

export interface ReturnedExamPreviewProps {
    studentName: string;
    examName: string;
    className?: string | null;
    teacherName?: string | null;
    /** The ISO instant from the wire. Formatted HERE — a raw timestamp reached
     *  both the header and the student's feedback page before the visual gate
     *  caught it, so the component owns the conversion and nobody can forget. */
    signedAt?: string | null;
    version?: number | null;
    contract: GradedTestContract;
    /** Page images of the student's own scan, already resolved to blob URLs. */
    scanPages: (string | null)[];
    stampPosition: StampPosition | null;
    includeCriteria: boolean;
    /** `returned_exam_state` from the batch feed (P8). */
    returnedExamState?: string | null;
    /**
     * Whether the two BATCH-wide controls may appear. False when the page was
     * reached without a batch id: the breakdown toggle and «apply to all» both
     * write to a batch, and one we had to guess is worse than one absent.
     */
    batchScoped?: boolean;

    onStampCommit: (next: StampPosition) => Promise<void>;
    /** Takes the position EXPLICITLY: the parent's copy is one render behind
     *  the drag, and propagating a stale stamp to thirty exams is silent. */
    onApplyStampToBatch: (position: StampPosition) => Promise<void>;
    onIncludeCriteriaChange: (next: boolean) => Promise<void>;
    onEditReview: () => void;
    /** Resolves false when the server answered 202 — still rendering. */
    onDownload: () => Promise<boolean>;
    onReapprove: () => void;
}

/** The server's own Hebrew when it sent one (§6), ours otherwise. */
function serverOr(err: unknown, fallback: string): string {
    return err instanceof ApiError && err.detail ? err.detail : fallback;
}

export function ReturnedExamPreview(props: ReturnedExamPreviewProps) {
    const {
        studentName, examName, className, teacherName, signedAt, version,
        contract, scanPages, stampPosition, includeCriteria, returnedExamState,
        batchScoped = true, onStampCommit, onApplyStampToBatch, onIncludeCriteriaChange,
        onEditReview, onDownload, onReapprove,
    } = props;

    const pageRef = useRef<HTMLDivElement | null>(null);
    const [current, setCurrent] = useState(0);
    const [pendingToggle, setPendingToggle] = useState(false);
    const [optimisticCriteria, setOptimisticCriteria] = useState<boolean | null>(null);
    const [optimisticStamp, setOptimisticStamp] = useState<StampPosition | null>(null);
    /** P3: the «apply to all» link appears only AFTER she has moved it — the
     *  offer to propagate a position only makes sense once one was chosen. */
    const [moved, setMoved] = useState(false);

    const effectiveCriteria = optimisticCriteria ?? includeCriteria;
    const effectiveStamp = optimisticStamp ?? stampPosition;

    const appendix = useMemo(
        () => buildAppendix(contract, effectiveCriteria), [contract, effectiveCriteria]);
    const appendixPages = useMemo(() => paginateAppendix(appendix), [appendix]);
    const strip = useMemo(
        () => pageStrip(scanPages.length, appendixPages.length),
        [scanPages.length, appendixPages.length]);

    // Turning the breakdown off can shrink the appendix under a selected index.
    // Clamping lands her on the LAST page rather than teleporting her back to
    // scan page 1, which is the nearest thing to where she was looking.
    const entry = strip[Math.min(current, strip.length - 1)] ?? strip[0];
    const score = formatPoints(appendix.total);

    const handleStampCommit = useCallback(async (next: StampPosition) => {
        setOptimisticStamp(next);
        try {
            await onStampCommit(next);
            // ONLY on success. «Apply to all» propagates a position batch-wide;
            // offering it after a save that failed would spread the corner the
            // picker guessed, under the banner of a choice she made.
            setMoved(true);
            toast.success(PV_STAMP_SAVED);
        } catch (err) {
            // Roll back to the server's value: a stamp that snapped somewhere
            // and did NOT save must not keep sitting there looking saved.
            setOptimisticStamp(null);
            toast.error(serverOr(err, PV_STAMP_SAVE_FAILED));
        }
    }, [onStampCommit]);

    const handleToggle = useCallback(async (next: boolean) => {
        setOptimisticCriteria(next);
        setPendingToggle(true);
        try {
            await onIncludeCriteriaChange(next);
            toast.success(next ? PV_TOGGLE_ON : PV_TOGGLE_OFF);
        } catch (err) {
            setOptimisticCriteria(null);
            toast.error(serverOr(err, PV_TOGGLE_FAILED));
        } finally {
            setPendingToggle(false);
        }
    }, [onIncludeCriteriaChange]);

    const handleApplyAll = useCallback(async () => {
        if (!effectiveStamp) return;
        try {
            await onApplyStampToBatch(effectiveStamp);
            toast.success(PV_APPLY_ALL_DONE);
        } catch (err) {
            toast.error(serverOr(err, PV_APPLY_ALL_FAILED));
        }
    }, [effectiveStamp, onApplyStampToBatch]);

    const handleDownload = useCallback(async () => {
        try {
            const ready = await onDownload();
            if (!ready) toast(PV_DOWNLOAD_PREPARING);
        } catch (err) {
            toast.error(serverOr(err, PV_DOWNLOAD_FAILED));
        }
    }, [onDownload]);

    const stale = isReturnedExamStale(returnedExamState);

    return (
        <div data-returned-exam className="mx-auto max-w-review px-4 py-6">
            {/* ── P1 · header + toolbar ─────────────────────────────────── */}
            <div className="mb-appx-foot flex flex-wrap items-center justify-between gap-4">
                <div>
                    <h1 className="text-gr-pv-h1 text-grade-ink">
                        {PV_TITLE(studentName)}
                    </h1>
                    <div className="text-gr-rtl text-grade-pencil">
                        {PV_SUB(scanPages.length, appendixPages.length,
                            formatSignedAt(signedAt), version ?? null)}
                    </div>
                </div>

                <div className="flex flex-wrap items-center gap-2.5">
                    {batchScoped ? (
                        <BreakdownToggle
                            checked={effectiveCriteria}
                            pending={pendingToggle}
                            onChange={handleToggle}
                        />
                    ) : null}
                    {/* Batch-scoped like the toggle, and for a harder reason:
                        `manual_edit` EXTENDS THE CHAIN irreversibly, and the
                        review route it must land on lives under /batches/. With
                        no batch this button would fork the chain and strand her
                        on a draft with no way forward. */}
                    {batchScoped ? (
                    <button
                        type="button"
                        data-edit-review
                        onClick={onEditReview}
                        className="inline-flex items-center gap-2 rounded-grade-ctl border
                            border-grade-line bg-grade-card px-4 py-2.5 text-gr-body
                            font-medium text-grade-ink hover:border-grade-pencil-2"
                    >
                        {PV_EDIT}
                    </button>
                    ) : null}
                    {/* Never disabled (P1): a 202 means "not yet", and the button
                        explains that instead of going dead in her hand. */}
                    <button
                        type="button"
                        data-download-pdf
                        onClick={handleDownload}
                        className="inline-flex items-center gap-2 rounded-grade-ctl border
                            border-primary-600 bg-primary-600 px-4 py-2.5 text-gr-body
                            font-medium text-white hover:bg-primary-700"
                    >
                        {PV_DOWNLOAD}
                    </button>
                </div>
            </div>

            {/* ── P8 · stale ────────────────────────────────────────────── */}
            {stale ? (
                <div data-stale-banner className="mb-4 flex items-center justify-between gap-3
                    rounded-grade-ctl border border-grade-amber-200 bg-grade-amber-50 px-4
                    py-2.5 text-gr-rtl text-grade-amber-ink">
                    <span>{PV_STALE(version ?? 1)}</span>
                    <button
                        type="button"
                        data-reapprove
                        onClick={onReapprove}
                        className="rounded-grade-ctl border border-grade-line bg-grade-card
                            px-4 py-2 text-gr-body font-medium text-grade-ink
                            hover:border-grade-pencil-2"
                    >
                        {PV_REAPPROVE}
                    </button>
                </div>
            ) : null}

            {/* ── P2 · strip + page ─────────────────────────────────────── */}
            <div className="grid items-start gap-6 md:grid-cols-[118px_1fr]">
                <div data-page-strip className="flex flex-row flex-wrap gap-strip-gap
                    md:sticky md:top-16 md:flex-col md:flex-nowrap">
                    {strip.map((item, index) => (
                        <button
                            key={`${item.kind}-${item.number}`}
                            type="button"
                            data-strip-page={index}
                            data-strip-kind={item.kind}
                            aria-current={index === current}
                            onClick={() => setCurrent(index)}
                            className={[
                                'relative flex aspect-[1/1.41] w-strip-thumb items-end justify-center',
                                'overflow-hidden rounded-grade-sm border border-grade-line p-1',
                                'text-gr-sm text-grade-pencil md:w-full',
                                item.kind === 'appendix' ? 'bg-grade-card' : 'bg-grade-paper',
                                index === current
                                    ? 'outline outline-2 outline-offset-1 outline-primary-600'
                                    : '',
                            ].join(' ')}
                        >
                            {item.kind === 'scan' && scanPages[item.number - 1] ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={scanPages[item.number - 1] as string}
                                    alt=""
                                    className="absolute inset-0 h-full w-full object-cover"
                                />
                            ) : null}
                            {item.kind === 'appendix' ? (
                                <span aria-hidden className="absolute inset-x-2.5 inset-y-3.5"
                                    style={{
                                        background: 'repeating-linear-gradient(to bottom,'
                                            + '#F1EEE7 0 1px, transparent 1px 7px)',
                                    }} />
                            ) : null}
                            {item.kind === 'scan' && item.number === 1 ? (
                                <StampSvg score={score} size={34}
                                    className="absolute left-0.5 top-px" />
                            ) : null}
                            <span className="relative rounded-sm bg-grade-paper/90 px-1.5">
                                {item.kind === 'scan'
                                    ? PV_STRIP_SCAN(item.number)
                                    : PV_STRIP_APPENDIX(item.number)}
                            </span>
                        </button>
                    ))}
                </div>

                <div>
                    {entry?.kind === 'scan' ? (
                        <div
                            ref={pageRef}
                            data-page-view="scan"
                            className="relative mx-auto aspect-[1/1.41] w-full max-w-page
                                overflow-hidden rounded border border-grade-line
                                bg-grade-paper shadow-grade"
                        >
                            {scanPages[entry.number - 1] ? (
                                // eslint-disable-next-line @next/next/no-img-element
                                <img
                                    src={scanPages[entry.number - 1] as string}
                                    alt=""
                                    className="absolute inset-0 h-full w-full object-contain"
                                />
                            ) : null}
                            {/* P3 — the stamp lives on page 1 and nowhere else. */}
                            {entry.number === 1 ? (
                                <StampDrag
                                    position={effectiveStamp}
                                    score={score}
                                    onCommit={handleStampCommit}
                                    pageRef={pageRef}
                                />
                            ) : null}
                        </div>
                    ) : entry ? (
                        <AppendixPage
                            appendix={appendix}
                            page={appendixPages[entry.number - 1]}
                            pageNumber={entry.number}
                            pageCount={appendixPages.length}
                            examName={examName}
                            studentName={studentName}
                            className={className}
                            signedDate={formatSignedDate(signedAt)}
                            teacherName={teacherName}
                        />
                    ) : null}

                    <div data-page-hint className="mt-2.5 text-center text-gr-label
                        text-grade-pencil">
                        {entry?.kind === 'appendix' ? PV_HINT_APPENDIX
                            : entry?.number === 1 ? (
                                <>
                                    {/* Nothing stored → the PDF's corner is the
                                        backend picker's, not on the wire; say so
                                        rather than claim Vivi chose THIS corner. */}
                                    {effectiveStamp ? PV_HINT_STAMP : PV_HINT_STAMP_AUTO}
                                    {moved && batchScoped ? (
                                        <>
                                            {' · '}
                                            <button
                                                type="button"
                                                data-apply-all
                                                onClick={handleApplyAll}
                                                className="text-primary-700 underline
                                                    underline-offset-link"
                                            >
                                                {PV_APPLY_ALL}
                                            </button>
                                        </>
                                    ) : null}
                                </>
                            ) : PV_HINT_SCAN(entry?.number ?? 1)}
                    </div>
                </div>
            </div>
        </div>
    );
}

/** Re-exported so a test can assert the resting box without a browser. */
export { stampBox };
