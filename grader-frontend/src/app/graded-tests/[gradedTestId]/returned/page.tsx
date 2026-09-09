'use client';

/**
 * המבחן המוחזר — the returned-exam preview (spec §2, §4.3).
 *
 * /graded-tests/[gradedTestId]/returned?batch=<batchId>
 *
 * ── WHY THE BATCH ID IS A QUERY PARAM AND NOT A PATH SEGMENT ─────────────
 * The spec puts this route outside `/batches/`, because an approved exam is a
 * property of the TEST, and it must stay deep-linkable from anywhere. But two
 * of its controls are per-BATCH — the breakdown toggle and «apply this stamp
 * position to the whole batch» — and the approved-test payload carries no
 * `batch_id`. Rather than invent one, the callers that know it (the dashboard's
 * pile, the review module's mini-thumb) pass it — both always do, so a
 * batch-less link is a hand-edited URL, not a product path.
 *
 * What such a link ACTUALLY shows, stated precisely because the first version
 * of this comment overclaimed: the FEEDBACK PAGES, in full. It does NOT show
 * the scan, because `page_count` is reachable only through the batch payload
 * (there is no transcription-detail endpoint), and it does not show the stamp,
 * which lives on scan page 1. The batch-wide controls and `עריכת הבדיקה` are
 * absent rather than inert. Nothing claims a page count we did not fetch — the
 * sub-line omits that clause entirely instead of printing «ללא עמודי מבחן»,
 * which would be an invented negative about a document we never asked for
 * (§3.5a: degrade by OMISSION, never by asserting a zero).
 *
 * ── WHY IT REFUSES ON A DRAFT ────────────────────────────────────────────
 * The returned exam is rendered from the frozen CONTRACT. A draft has none, so
 * there is nothing honest to preview — the page says so and offers the review,
 * which is the thing she actually needs to do next.
 */

import Link from 'next/link';
import { useParams, useRouter, useSearchParams } from 'next/navigation';
import { useCallback, useEffect, useRef, useState } from 'react';

import {
    fetchReturnedExamPdf, fetchTranscriptionPageObjectUrl, getApprovedGradedTest,
    getBatch, manualEditGradedTest, saveStampPosition,
    updateBatchReturnedExamSettings,
    type GradeReviewApprovedResponse, type StampPositionWire,
} from '@/lib/api';
import { surfaceError } from '@/lib/errorSurface';
import { ReturnedExamPreview } from '@/components/grade-review/ReturnedExamPreview';
import type { GradedTestContract } from '@/utils/returned-exam';
import {
    PV_LOADING, PV_LOAD_FAILED, PV_NOT_APPROVED_BODY, PV_NOT_APPROVED_CTA,
    PV_NOT_APPROVED_TITLE,
} from '@/copy/grade-review';
import type { BatchDetailResponse, BatchTranscriptionItem, BatchGradedItem } from '@/types/batch';

export default function ReturnedExamPage() {
    const params = useParams<{ gradedTestId: string }>();
    const search = useSearchParams();
    const router = useRouter();
    const batchId = search.get('batch');

    const [payload, setPayload] = useState<GradeReviewApprovedResponse | null>(null);
    const [batch, setBatch] = useState<BatchDetailResponse | null>(null);
    const [scanPages, setScanPages] = useState<(string | null)[]>([]);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    /** Every object URL this page minted, so unmount can revoke all of them. */
    const mintedRef = useRef<string[]>([]);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        (async () => {
            try {
                const test = await getApprovedGradedTest(params.gradedTestId);
                if (cancelled) return;
                setPayload(test);

                if (batchId) {
                    // A batch that fails to load is NOT fatal to the preview:
                    // it only costs the two batch-wide controls, and losing the
                    // whole page over them would be the larger failure.
                    try {
                        const detail = await getBatch(batchId);
                        if (!cancelled) setBatch(detail);
                    } catch {
                        if (!cancelled) setBatch(null);
                    }
                }
            } catch (err) {
                if (!cancelled) { surfaceError(err); setError(PV_LOAD_FAILED); }
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();
        return () => { cancelled = true; };
    }, [batchId, params.gradedTestId]);

    // The scan itself. Fetched after the payload because it needs the
    // transcription id, and page by page because each is its own authorized
    // byte route.
    // Depends on the two SCALARS it actually uses, never on `batch` itself:
    // toggling the breakdown calls setBatch with a new object, and listing
    // `batch` here re-ran this on every toggle — re-downloading every page and
    // orphaning the previous batch of blob URLs until unmount.
    const scanPageCount = (() => {
        const transcriptionId = payload?.transcription_id;
        if (!transcriptionId || !batch) return 0;
        return (batch.transcriptions ?? []).find(
            (t: BatchTranscriptionItem) => t.transcription_id === transcriptionId,
        )?.draft?.page_count ?? 0;
    })();

    useEffect(() => {
        const transcriptionId = payload?.transcription_id;
        if (!transcriptionId || scanPageCount <= 0) return;
        const pageCount = scanPageCount;

        let cancelled = false;
        (async () => {
            const urls = await Promise.all(
                Array.from({ length: pageCount }, (_, index) =>
                    fetchTranscriptionPageObjectUrl(transcriptionId, index + 1)
                        // A page that will not load renders as an empty page,
                        // never as a broken-image glyph — the same degrade-by-
                        // omission rule the pile thumbnails follow.
                        .catch(() => null)));
            if (cancelled) {
                urls.forEach((url) => { if (url) URL.revokeObjectURL(url); });
                return;
            }
            urls.forEach((url) => { if (url) mintedRef.current.push(url); });
            setScanPages(urls);
        })();
        return () => { cancelled = true; };
    }, [scanPageCount, payload?.transcription_id]);

    useEffect(() => () => {
        mintedRef.current.forEach((url) => URL.revokeObjectURL(url));
        mintedRef.current = [];
    }, []);

    const feedItem = (batch?.graded_tests ?? []).find(
        (t: BatchGradedItem) => t.graded_test_id === params.gradedTestId);

    const stampPosition =
        (payload?.draft?.teacher_overrides?.stamp_position as StampPositionWire | undefined)
        ?? (batch?.stamp_position_default as StampPositionWire | null | undefined)
        ?? null;

    const onStampCommit = useCallback(async (next: StampPositionWire) => {
        // The stamp's OWN endpoint (OD-1). It takes only the position — no
        // overlay snapshot — and accepts approved rows, which `PATCH …/draft`
        // never did; P3 was dead end to end until it existed. The server
        // stamps `source: "manual"` and drops the cached render.
        const saved = await saveStampPosition(params.gradedTestId, next);
        // Keep the local payload truthful so a reload-free second drag starts
        // from what the server now holds.
        setPayload((prev) => (prev?.draft
            ? {
                ...prev,
                draft: {
                    ...prev.draft,
                    teacher_overrides: {
                        ...(prev.draft.teacher_overrides ?? {}),
                        stamp_position: saved.stamp_position ?? null,
                    },
                },
            } as GradeReviewApprovedResponse
            : prev));
    }, [params.gradedTestId]);

    const onApplyStampToBatch = useCallback(async (position: StampPositionWire) => {
        if (!batchId) return;
        await updateBatchReturnedExamSettings(batchId, {
            stamp_position_default: position,
        });
    }, [batchId]);

    const onIncludeCriteriaChange = useCallback(async (next: boolean) => {
        if (!batchId) return;
        await updateBatchReturnedExamSettings(batchId, {
            appendix_include_criteria: next,
        });
        setBatch((prev: BatchDetailResponse | null) =>
            (prev ? { ...prev, appendix_include_criteria: next } : prev));
    }, [batchId]);

    const onEditReview = useCallback(() => {
        (async () => {
            try {
                // Editing a SIGNED exam extends the chain — it never mutates
                // the approved row (LCY-2). The successor is what she edits.
                const revision = await manualEditGradedTest(params.gradedTestId);
                const target = revision?.graded_test_id ?? params.gradedTestId;
                router.push(batchId
                    ? `/batches/${batchId}/grade-review/${target}`
                    : `/graded-tests/${target}/returned`);
            } catch (err) {
                surfaceError(err);
            }
        })();
    }, [batchId, params.gradedTestId, router]);

    const onDownload = useCallback(async () => {
        const result = await fetchReturnedExamPdf(params.gradedTestId);
        if (!result.ready || !result.blob) return false;
        const url = URL.createObjectURL(result.blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `${payload?.student_name ?? 'מבחן'}_מוחזר.pdf`;
        anchor.click();
        // Firefox starts a blob: download asynchronously; revoking on the same
        // tick aborts it. Ten seconds is the conventional margin — a URL that
        // lives ten seconds too long costs nothing.
        setTimeout(() => URL.revokeObjectURL(url), 10_000);
        return true;
    }, [params.gradedTestId, payload?.student_name]);

    const onReapprove = useCallback(() => {
        router.push(batchId
            ? `/batches/${batchId}/grade-review/${params.gradedTestId}`
            : `/graded-tests/${params.gradedTestId}/returned`);
    }, [batchId, params.gradedTestId, router]);

    if (loading) {
        return <p className="p-8 text-center text-gr-body text-grade-pencil">{PV_LOADING}</p>;
    }
    if (error || !payload) {
        return <p className="p-8 text-center text-gr-body text-grade-pencil">
            {error ?? PV_LOAD_FAILED}</p>;
    }
    if (payload.status !== 'approved' || !payload.contract) {
        return (
            <div data-not-approved className="mx-auto max-w-modal p-8 text-center">
                <h1 className="text-gr-h2 text-grade-ink">{PV_NOT_APPROVED_TITLE}</h1>
                <p className="mt-2 text-gr-body text-grade-ink-2">{PV_NOT_APPROVED_BODY}</p>
                {batchId ? (
                    <Link
                        href={`/batches/${batchId}/grade-review/${params.gradedTestId}`}
                        className="mt-4 inline-block rounded-grade-ctl border border-primary-600
                            bg-primary-600 px-4 py-2 text-gr-body font-medium text-white"
                    >
                        {PV_NOT_APPROVED_CTA}
                    </Link>
                ) : null}
            </div>
        );
    }

    return (
        <ReturnedExamPreview
            studentName={payload.student_name ?? ''}
            examName={batch?.rubric_name ?? batch?.name ?? ''}
            className={batch?.class_name ?? null}
            signedAt={payload.approved_at ?? null}
            version={feedItem?.version ?? 1}
            contract={payload.contract as GradedTestContract}
            scanPages={scanPages}
            stampPosition={stampPosition}
            includeCriteria={Boolean(batch?.appendix_include_criteria)}
            returnedExamState={feedItem?.returned_exam_state ?? null}
            batchScoped={Boolean(batchId)}
            onStampCommit={onStampCommit}
            onApplyStampToBatch={onApplyStampToBatch}
            onIncludeCriteriaChange={onIncludeCriteriaChange}
            onEditReview={onEditReview}
            onDownload={onDownload}
            onReapprove={onReapprove}
        />
    );
}
