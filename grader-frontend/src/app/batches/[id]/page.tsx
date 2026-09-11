'use client';

/**
 * The batch dashboard (P2 redesign, D1–D12) — a live triage board that
 * converts machine output into teacher decisions at the cheapest sufficient
 * depth: chip-level (identity wave), panel-level (server-guaranteed clean
 * bulk), full review (needs-eyes walk). Zone order and styling follow the
 * approved mockup; every rendered string comes from the C1 copy module.
 *
 * State-keying rule (race-proofing the poll): ALL interactive state here is
 * keyed by transcription_id or normalized name — never array index — so the
 * payload replacement a poll performs can never clobber or misattach it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { AlertCircle, ArrowRight, Loader2, RefreshCw } from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { GradedTestReviewPanel } from '@/components/GradedTestReviewPanel';
import { GradeDashboard } from '@/components/grade-review/GradeDashboard';
import type { GradedItem } from '@/utils/grade-dashboard';
import {
    DASH_DOWNLOAD_FAILED, DASH_DOWNLOAD_STARTED, DASH_RETRY_FAILED, DASH_RETRY_STARTED,
} from '@/copy/grade-review';
import {
    ApiError, fetchReturnedExamsManifest, fetchReturnedExamsZip,
    retryGradedTest as retryGradedTestRow,
} from '@/lib/api';
import { toast } from 'sonner';
import {
    acceptCleanTranscriptions,
    ApiAuthError,
    approveGradedTest,
    createStudent,
    ClassroomConflictError,
    getBatch,
    getRubric,
    getGradedTest,
    renameBatch,
    retryBatchJob,
    saveGradedTestDraft,
} from '@/lib/api';
import type {
    BatchDetailResponse,
    BatchTranscriptionItem,
} from '@/types/batch';
import type {
    GradedTestDraftResponse,
    GradedTestApprovedResponse,
} from '@/types/graded_test';
import {
    BACK_ALL_BATCHES,
    BATCH_FALLBACK_NAME,
    BATCH_LOAD_ERROR,
    BATCH_NOT_FOUND,
    batchStatusLabel,
    DISMISS_NOTICE_LABEL,
    META_CREATED,
    META_RUBRIC_PREFIX,
    META_TESTS,
    RETRY_ERROR,
    SKIP_NOTICE,
    SKIP_REASON_FRAGMENTS,
    UPLOAD_FAILURES_NOTICE,
} from '@/copy/batch';
import { StatusChip, type ChipHue } from '@/components/batch/StatusChip';
import { SegmentBar } from '@/components/batch/SegmentBar';
import { IdentityWave, type PillView, type PillStatus } from '@/components/batch/IdentityWave';
import { GhostZone } from '@/components/batch/GhostZone';
import { UploadLane } from '@/components/batch/UploadLane';
import { useUploadQueue } from '@/contexts/UploadQueueProvider';
import { CleanPanel } from '@/components/batch/CleanPanel';
import { NeedsEyesQueue } from '@/components/batch/NeedsEyesQueue';
import { FailedZone } from '@/components/batch/FailedZone';
import { GradingLane } from '@/components/batch/GradingLane';
import { CompletionHero } from '@/components/batch/CompletionHero';
import { normalizeName, partitionItems } from '@/utils/batch-partition';
import { assignZones, isIdentityPending } from '@/utils/zone-assignment';
import {
    barSegments,
    completionReached,
    pollCadenceMs,
    relativeTimeHe,
    selectHeadline,
    sessionCompletionMinutes,
} from '@/utils/batch-dashboard';
import { computeReviewOrder } from '@/utils/batch-review-cursor';
import { takeSkipNotice, takeUploadFailures } from '@/utils/skip-notice';
import { SHOW_GRADING_LANE, USE_GRADE_REVIEW_MODULE } from '@/lib/flags';

// ---------------------------------------------------------------------------
// Grade-review section — per-test rows opening the S9 panel (pre-redesign
// machinery kept; chips migrated onto the F8 primitive)
// ---------------------------------------------------------------------------
function GradeReviewSection({ batch, batchId, onRefresh }: {
    batch: BatchDetailResponse;
    batchId: string;
    /** The page's own refetch — a retry inserts a new pending row the poll will
     *  show, but she should not have to wait a tick to see it. */
    onRefresh: () => Promise<void>;
}) {
    const router = useRouter();
    // Hooks before the early returns below.
    /** Failed tests she sent back to grading THIS session (D6, see retryTest). */
    const [retriedIds, setRetriedIds] = useState<ReadonlySet<string>>(() => new Set());
    // Stable identity: the dashboard's manifest effect must key on the modal
    // opening, not on this function being re-created by every poll re-render.
    const loadManifest = useCallback(() => fetchReturnedExamsManifest(batchId), [batchId]);

    /**
     * F1 — the grade-review dashboard (spec §4.1) replaces the pre-redesign
     * row list that opened the S9 panel inline.
     *
     * `USE_GRADE_REVIEW_MODULE` keeps the old panel one flag away: it is the
     * rollback target, exactly as RubricEditor is for the document mirror.
     */
    const items = batch.graded_tests ?? [];
    if (items.length === 0) return null;

    /**
     * The kill-switch has to DO something or it is a lie in a comment.
     *
     * When F1 replaced the row list, the old branch went with it and the flag
     * became decorative — documented as the rollback while flipping it changed
     * nothing. The pre-redesign list is restored here, minimal and unstyled,
     * because a pilot wants a way back that has been exercised, not a promise.
     */
    if (!USE_GRADE_REVIEW_MODULE) {
        return <LegacyGradeRows items={batch.transcriptions} />;
    }

    const openReview = (item: GradedItem) =>
        router.push(`/batches/${batchId}/grade-review/${item.graded_test_id}`);

    /**
     * F3. The batch id rides as a query param because the preview route lives
     * outside `/batches/` (spec §2) while two of its controls are batch-wide —
     * see that route's own doc. Passing it here is what keeps the breakdown
     * toggle and «apply to all» reachable from the front door.
     */
    const openPreview = (item: GradedItem) =>
        router.push(
            `/graded-tests/${item.graded_test_id}/returned?batch=${batchId}`);

    /**
     * D6: failed → retry. `retry` EXTENDS THE CHAIN (LCY-2) with a new pending
     * row and enqueues the grader. Since 2026-09-10 the successor CARRIES
     * `batch_id`, so it arrives in this feed on the next poll and the batch
     * heals in place — previously it landed batch-less and the student's
     * returned exam was gone from the batch download for good. Retrying from
     * here rather than from the review route: the failed shell there has
     * nothing else to offer, so the round trip was two screens for one button.
     */
    const retryTest = async (item: GradedItem) => {
        try {
            await retryGradedTestRow(item.graded_test_id);
            // Marked locally so the card stops offering the same click while
            // the refresh is in flight: the row is no longer the leaf, so a
            // second press would 409.
            setRetriedIds((prev) => new Set(prev).add(item.graded_test_id));
            toast.success(DASH_RETRY_STARTED(item.student_name || ''));
            await onRefresh();
        } catch (err) {
            // The server's own Hebrew when it has one (§6), ours otherwise.
            toast.error(err instanceof ApiError ? err.detail : DASH_RETRY_FAILED);
        }
    };

    /**
     * D8/D9: the ZIP, as bytes through the seam (Bearer-authenticated — a plain
     * link would 401). Approved-only is enforced server-side; the manifest the
     * modal read is what told her so beforehand.
     */
    const downloadZip = async () => {
        try {
            const blob = await fetchReturnedExamsZip(batchId);
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = `${batch.name ?? 'מקבץ'}_מבחנים_מוחזרים.zip`;
            anchor.click();
            // Firefox starts a blob: download asynchronously; revoking on the same
            // tick aborts it. Ten seconds is the conventional margin — the cost
            // of a URL that lives ten seconds too long is nothing.
            setTimeout(() => URL.revokeObjectURL(url), 10_000);
            toast.success(DASH_DOWNLOAD_STARTED);
        } catch (err) {
            toast.error(err instanceof ApiError ? err.detail : DASH_DOWNLOAD_FAILED);
        }
    };

    return (
        <GradeDashboard
            items={items}
            batchTotal={batch.rollup?.total ?? null}
            auditStatus={batch.audit_status ?? 'disabled'}
            eta={batch.eta ?? null}
            // No sub-line: the batch page's own header already carries the
            // rubric, the class and the count. See GradeDashboard's prop doc.

            startedAt={batch.started_at}
            completedAt={batch.completed_at}
            onOpenReview={openReview}
            onContinue={openReview}
            onOpenPreview={openPreview}
            onRetry={(item) => { void retryTest(item); }}
            onDownload={() => { void downloadZip(); }}
            loadManifest={loadManifest}
            retriedIds={retriedIds}
        />
    );
}

/** The pre-F1 row list — the rollback target for USE_GRADE_REVIEW_MODULE. */
function LegacyGradeRows({ items }: { items: BatchTranscriptionItem[] }) {
    const [activeTestId, setActiveTestId] = useState<string | null>(null);
    const [activeDetail, setActiveDetail] =
        useState<GradedTestDraftResponse | GradedTestApprovedResponse | null>(null);

    if (activeDetail && activeTestId) {
        const isDraft = activeDetail.status === 'draft';
        return (
            <GradedTestReviewPanel
                response={activeDetail}
                transcriptionId={activeDetail.transcription_id}
                onBack={() => { setActiveTestId(null); setActiveDetail(null); }}
                editable={isDraft}
                onSaveDraft={isDraft ? async (overrides) => {
                    setActiveDetail(await saveGradedTestDraft(activeTestId, overrides));
                } : undefined}
                onApprove={isDraft ? async (overrides) => {
                    setActiveDetail(await approveGradedTest(activeTestId, overrides));
                } : undefined}
            />
        );
    }

    const graded = items.filter((i) => i.graded_test_id);
    if (graded.length === 0) return null;

    return (
        <div className="space-y-2">
            <h3 className="text-sm font-medium text-batch-ink">סקירת ציונים</h3>
            {graded.map((item) => (
                <div
                    key={String(item.transcription_id)}
                    className="flex items-center justify-between rounded-zone-sm border
                        border-batch-line bg-white px-4 py-3"
                >
                    <p className="text-sm text-batch-ink">
                        {item.matched_student_name ?? item.filename ?? 'ללא שם'}
                    </p>
                    {(item.graded_test_status === 'draft'
                        || item.graded_test_status === 'approved') && (
                        <button
                            onClick={async () => {
                                const detail = await getGradedTest(String(item.graded_test_id!));
                                if (detail.status === 'draft' || detail.status === 'approved') {
                                    setActiveTestId(String(item.graded_test_id!));
                                    setActiveDetail(detail as GradedTestDraftResponse
                                        | GradedTestApprovedResponse);
                                }
                            }}
                            className="text-xs text-primary-600 hover:underline"
                        >
                            פתח
                        </button>
                    )}
                </div>
            ))}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
export default function BatchDetailPage() {
    const params = useParams();
    const router = useRouter();
    const batchId = params?.id as string;

    const [batch, setBatch] = useState<BatchDetailResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const mountedRef = useRef(true);
    const authDeadRef = useRef(false);
    // The rubric's subject key (migration 027): direction of the clean-panel
    // answer peeks (Phase 3b). Context only — a failed fetch leaves today's ltr.
    const [rubricSubject, setRubricSubject] = useState<string | null>(null);
    const rubricIdForSubject = batch?.rubric_id ?? null;
    useEffect(() => {
        if (!rubricIdForSubject) return;
        let alive = true;
        getRubric(rubricIdForSubject)
            .then((r) => { if (alive) setRubricSubject((r as { subject?: string | null }).subject ?? null); })
            .catch(() => { /* direction context only */ });
        return () => { alive = false; };
    }, [rubricIdForSubject]);

    // D4 — pill state keyed by NORMALIZED name (survives payload replacement)
    const [pillStates, setPillStates] = useState<Record<string, { value: string; status: PillStatus }>>({});
    const [bulkBusy, setBulkBusy] = useState(false);
    const [sessionCreated, setSessionCreated] = useState(0);

    // D5 — keyed by transcription_id
    const [cleanExpanded, setCleanExpanded] = useState<ReadonlySet<string>>(new Set());
    const [cleanShowAll, setCleanShowAll] = useState(false);
    const [accepting, setAccepting] = useState<ReadonlySet<string>>(new Set());
    const [cleanBulkBusy, setCleanBulkBusy] = useState(false);
    const [skipNotice, setSkipNotice] = useState<string | null>(null);
    // D1: files that never became jobs, handed over from upload.
    //
    // [Stage B] The upload page no longer WRITES this handoff — its failures
    // are live in the lane below, with a retry the notice never had. The reader
    // stays for a key written by a pre-Stage-B session in the same tab.
    const [uploadFailures, setUploadFailures] = useState<string[]>([]);

    // [Stage B] This batch's own transfers, if they are the ones in flight.
    // The provider holds ONE queue (R10), so a different batch shows no lane
    // rather than someone else's progress.
    const uploads = useUploadQueue();
    const myUploadQueue = uploads.batchId === batchId ? uploads.queue : null;

    // D8
    const [retryBusy, setRetryBusy] = useState<ReadonlySet<string>>(new Set());

    // D1 — inline rename
    const [renaming, setRenaming] = useState(false);
    const [renameValue, setRenameValue] = useState('');
    const [renameError, setRenameError] = useState<string | null>(null);

    // D7 — arriving-row highlight
    const prevIdsRef = useRef<Set<string> | null>(null);
    const [newIds, setNewIds] = useState<ReadonlySet<string>>(new Set());

    // D10 — session-computed duration
    const [completionMinutes, setCompletionMinutes] = useState<number | null>(null);

    const gradesRef = useRef<HTMLDivElement | null>(null);

    useEffect(() => {
        // StrictMode-safe: the body RE-ARMS the ref on the second mount —
        // a cleanup-only effect would leave it false forever after the
        // simulated unmount and silently discard every payload.
        mountedRef.current = true;
        return () => { mountedRef.current = false; };
    }, []);

    // R4 handoff (decision 2): the review interstitial's bulk accept hands a
    // skipped>0 notice here via the one-shot sessionStorage key — read and
    // cleared on mount so the teacher lands on the dashboard WITH the notice
    // instead of being stranded in a closed modal.
    useEffect(() => {
        const notice = takeSkipNotice(batchId);
        if (notice) setSkipNotice(notice);
        // D1: a batch cannot report files it never received — the upload
        // surface is the only place that knows they existed.
        const failed = takeUploadFailures(batchId);
        if (failed.length > 0) setUploadFailures(failed);
    }, [batchId]);

    const refresh = useCallback(async () => {
        try {
            const data = await getBatch(batchId);
            if (!mountedRef.current) return;
            setBatch(data);
            // F1: a successful poll CLEARS the error — a transient failure is
            // a banner over live content, never a sticky page-death.
            setError(null);
        } catch (err) {
            if (!mountedRef.current) return;
            if (err instanceof ApiAuthError) {
                // D12: auth is TERMINAL — stop polling, surface, go home.
                authDeadRef.current = true;
                if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
                setError(err.message);
                router.push('/');
                return;
            }
            setError(err instanceof Error ? err.message : BATCH_LOAD_ERROR);
        }
    }, [batchId, router]);

    useEffect(() => {
        setLoading(true);
        refresh().finally(() => { if (mountedRef.current) setLoading(false); });
    }, [refresh]);

    // D12 — cadence-driven polling: 3s while transcription decisions pend,
    // 5s while only grading moves, stop when nothing does.
    const cadence = batch && !authDeadRef.current ? pollCadenceMs(batch) : null;
    useEffect(() => {
        if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
        if (cadence === null) return;
        pollingRef.current = setInterval(refresh, cadence);
        return () => {
            if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
        };
    }, [cadence, refresh]);

    // D7 — highlight rows that arrived since the previous payload.
    useEffect(() => {
        if (!batch) return;
        const ids = new Set(batch.transcriptions.map(t => String(t.transcription_id)));
        const prev = prevIdsRef.current;
        prevIdsRef.current = ids;
        if (!prev) return;
        const fresh = new Set(Array.from(ids).filter(id => !prev.has(id)));
        if (fresh.size === 0) return;
        setNewIds(fresh);
        const t = setTimeout(() => { if (mountedRef.current) setNewIds(new Set()); }, 2500);
        return () => clearTimeout(t);
    }, [batch]);

    // D10 — freeze the duration the moment completion is first observed.
    // C2: only when THIS session watched it complete; a revisit omits the line
    // rather than reporting a week as minutes (see sessionCompletionMinutes).
    const sawIncompleteRef = useRef(false);
    useEffect(() => {
        if (!batch) return;
        if (!completionReached(batch)) { sawIncompleteRef.current = true; return; }
        if (completionMinutes !== null) return;
        const minutes = sessionCompletionMinutes(
            batch.created_at, Date.now(), sawIncompleteRef.current,
        );
        if (minutes !== null) setCompletionMinutes(minutes);
    }, [batch, completionMinutes]);

    const retryJob = useCallback(async (jobId: string) => {
        setRetryBusy(prev => new Set(prev).add(jobId));
        try {
            await retryBatchJob(batchId, jobId);
            await refresh();
        } catch (err) {
            // Refresh FIRST, then surface the action's message — the reverse
            // order would let the refresh's success-clear (F1) instantly wipe
            // the 409 detail the teacher needs to read.
            await refresh().catch(() => {});
            if (mountedRef.current) setError(err instanceof Error ? err.message : RETRY_ERROR);
        } finally {
            if (mountedRef.current) {
                setRetryBusy(prev => { const n = new Set(prev); n.delete(jobId); return n; });
            }
        }
    }, [batchId, refresh]);

    // ── derived (pure modules do the thinking) ──
    const partition = useMemo(
        () => partitionItems(batch?.transcriptions ?? []),
        [batch],
    );
    const activeJobs = batch?.active_jobs ?? [];
    const complete = batch ? completionReached(batch) : false;

    const pillViews: PillView[] = useMemo(
        () => partition.identityPills.map(p => {
            const key = normalizeName(p.name);
            const s = pillStates[key];
            return {
                key,
                value: s?.value ?? p.name,
                status: s?.status ?? 'idle',
                files: p.files,
            };
        }),
        [partition, pillStates],
    );

    const onEditPill = useCallback((key: string, value: string) => {
        setPillStates(prev => ({
            ...prev,
            [key]: { value, status: prev[key]?.status === 'error' ? 'idle' : (prev[key]?.status ?? 'idle') },
        }));
    }, []);

    const createOne = useCallback(async (key: string, value: string) => {
        const name = value.trim();
        if (!name) return;
        setPillStates(prev => ({ ...prev, [key]: { value, status: 'creating' } }));
        try {
            await createStudent({ full_name: name });
            if (!mountedRef.current) return;
            setPillStates(prev => ({ ...prev, [key]: { value, status: 'done' } }));
            setSessionCreated(n => n + 1);
        } catch (err) {
            if (!mountedRef.current) return;
            if (err instanceof ClassroomConflictError) {
                // The student already exists — the next poll's server match
                // resolves the item; the pill reads as settled (D4).
                setPillStates(prev => ({ ...prev, [key]: { value, status: 'conflict' } }));
            } else {
                setPillStates(prev => ({ ...prev, [key]: { value, status: 'error' } }));
            }
        }
    }, []);

    const onCreatePill = useCallback((key: string) => {
        const view = pillViews.find(p => p.key === key);
        if (view) void createOne(key, view.value);
    }, [pillViews, createOne]);

    const onBulkCreate = useCallback(async () => {
        const pending = pillViews.filter(p => p.status === 'idle' || p.status === 'error');
        if (pending.length === 0) return;
        setBulkBusy(true);
        try {
            // Sequential with concurrency 3 (D4): post each pill's CURRENT value.
            for (let i = 0; i < pending.length; i += 3) {
                await Promise.all(
                    pending.slice(i, i + 3).map(p => createOne(p.key, p.value)),
                );
            }
        } finally {
            if (mountedRef.current) setBulkBusy(false);
        }
        // Convergence is the next poll's job — no optimistic verdict flips.
    }, [pillViews, createOne]);

    const onAcceptAll = useCallback(async () => {
        if (!batch) return;
        const items = partition.clean
            .filter(i => (i as BatchTranscriptionItem).matched_student_id)
            .map(i => ({
                transcription_id: String(i.transcription_id),
                student_id: String((i as BatchTranscriptionItem).matched_student_id),
            }));
        if (items.length === 0) return;
        setCleanBulkBusy(true);
        setAccepting(new Set(items.map(i => i.transcription_id)));
        try {
            const res = await acceptCleanTranscriptions(batchId, items);
            if (!mountedRef.current) return;
            if (res.skipped.length > 0) {
                const fragments = Array.from(new Set(
                    res.skipped.map(s => SKIP_REASON_FRAGMENTS[s.skipped_reason] ?? s.skipped_reason),
                ));
                setSkipNotice(SKIP_NOTICE(res.skipped.length, fragments.join(', ')));
            } else {
                setSkipNotice(null);
            }
            await refresh();
        } catch (err) {
            await refresh().catch(() => {});
            if (mountedRef.current) setError(err instanceof Error ? err.message : BATCH_LOAD_ERROR);
        } finally {
            if (mountedRef.current) {
                setCleanBulkBusy(false);
                setAccepting(new Set());
            }
        }
    }, [batch, batchId, partition, refresh]);

    const startRename = useCallback(() => {
        if (!batch) return;
        setRenameValue(batch.name ?? BATCH_FALLBACK_NAME(batchId.slice(0, 8)));
        setRenameError(null);
        setRenaming(true);
    }, [batch, batchId]);

    const commitRename = useCallback(async () => {
        if (!batch) return;
        const next = renameValue.trim();
        setRenaming(false);
        if (!next || next === batch.name) return;
        const prevName = batch.name;
        setBatch(b => (b ? { ...b, name: next } : b));      // optimistic
        try {
            await renameBatch(batchId, next);
            setRenameError(null);
        } catch (err) {
            if (!mountedRef.current) return;
            setBatch(b => (b ? { ...b, name: prevName } : b));   // revert
            setRenameError(err instanceof Error ? err.message : BATCH_LOAD_ERROR);
        }
    }, [batch, batchId, renameValue]);

    if (loading) {
        return (
            <SidebarLayout>
                <div className="flex min-h-[60vh] items-center justify-center">
                    <Loader2 className="animate-spin text-primary-500" size={40} />
                </div>
            </SidebarLayout>
        );
    }

    // F1: the full-page error renders ONLY while no payload has ever loaded.
    if (!batch) {
        return (
            <SidebarLayout>
                <div className="mx-auto mt-12 max-w-xl rounded-zone border border-batch-red-line bg-batch-red-soft p-6 text-center">
                    <AlertCircle className="mx-auto mb-2 text-batch-red" size={32} />
                    <p className="text-batch-red-ink">{error ?? BATCH_NOT_FOUND}</p>
                    <Link href="/" className="mt-4 inline-block text-sm text-primary-600 underline">חזרה</Link>
                </div>
            </SidebarLayout>
        );
    }

    const rollup = batch.rollup;
    // [Stage A] Files still on the wire are in-flight for BOTH the label and
    // the hue: an uploading batch is 'בתמלול'-blue (work is moving) rather than
    // 'ממתין להחלטות'-amber, which would tell her something is waiting on her
    // when nothing is.
    const uploadingNow = rollup.uploading ?? 0;
    const statusLabel = batchStatusLabel(batch.status, {
        transcribing: rollup.transcribing,
        activeJobs: activeJobs.length,
        uploading: uploadingNow,
    });
    const statusHue: ChipHue =
        batch.status === 'completed' ? 'green'
        : batch.status === 'failed' ? 'red'
        : batch.status === 'in_progress'
            && (uploadingNow > 0 || rollup.transcribing > 0 || activeJobs.length > 0) ? 'blue'
        : 'amber';

    const headline = selectHeadline(partition, rollup);
    const segments = barSegments(partition, rollup);

    // ZC-1 (owner-ruled 2026-08-22): zone membership comes from ONE exhaustive
    // selector — transcribed = Σ(eyesRows) + Σ(cleanRows), enforced by
    // construction. The inline spread this replaces filtered identityOnly by
    // sub-reason, leaving student_unassigned-only items (clean content, a
    // successfully-extracted NEW name) with no row in ANY zone — visible only
    // as a wave pill, invisible to every sum.
    const zones = assignZones(batch.transcriptions as BatchTranscriptionItem[]);
    const eyesRows = zones.eyesRows;
    // ZC-1 v2/Q3 (owner-ruled): identity-pending items are CLEAN-partition
    // members of the walk — the CTA count and the walk's stops must agree.
    const walkItems = batch.transcriptions.map(t => ({
        transcription_id: String(t.transcription_id),
        flag_verdict: {
            review_needed: t.flag_verdict.review_needed
                && !isIdentityPending(t as BatchTranscriptionItem),
        },
    }));
    const reviewOrder = computeReviewOrder(walkItems);
    const firstReviewId = eyesRows.length > 0 ? reviewOrder[0] ?? null : null;
    const manualReviewId = zones.cleanRows.length > 0
        ? String(zones.cleanRows[0].transcription_id)
        : null;

    const showWave = !complete && (pillViews.length > 0 || partition.unmatchedItems.length > 0);

    return (
        <SidebarLayout>
            <div className="mx-auto max-w-4xl space-y-5">
                {/* F1: transient poll/action failures — dismissible, above live content */}
                {error && (
                    <div
                        data-testid="batch-poll-error-banner"
                        className="flex items-start justify-between gap-3 rounded-zone border border-batch-red-line bg-batch-red-soft px-4 py-3 text-sm text-batch-red-ink"
                    >
                        <span className="flex items-center gap-2">
                            <AlertCircle size={16} className="shrink-0" /> {error}
                        </span>
                        <button
                            onClick={() => setError(null)}
                            aria-label={DISMISS_NOTICE_LABEL}
                            className="font-bold text-batch-red hover:brightness-75"
                        >
                            ✕
                        </button>
                    </div>
                )}

                {/* D1 — header */}
                <div>
                    <Link href="/batches" className="inline-flex items-center gap-1.5 text-[13px] text-batch-muted hover:text-batch-teal-ink">
                        <ArrowRight size={14} /> {BACK_ALL_BATCHES}
                    </Link>
                    <div className="mt-1.5 flex flex-wrap items-baseline gap-3">
                        {renaming ? (
                            <input
                                autoFocus
                                value={renameValue}
                                onChange={e => setRenameValue(e.target.value)}
                                onBlur={() => void commitRename()}
                                onKeyDown={e => {
                                    if (e.key === 'Enter') void commitRename();
                                    if (e.key === 'Escape') setRenaming(false);
                                }}
                                className="rounded-lg border border-batch-line px-2 py-1 text-2xl font-bold tracking-tight outline-none focus:border-primary-500"
                                data-testid="rename-input"
                            />
                        ) : (
                            <h1 className="text-2xl font-bold tracking-tight text-batch-ink">
                                {batch.name ?? BATCH_FALLBACK_NAME(batchId.slice(0, 8))}
                            </h1>
                        )}
                        {!renaming && (
                            <button
                                onClick={startRename}
                                className="text-[13px] text-batch-faint hover:text-batch-teal-ink"
                                aria-label="שינוי שם המקבץ"
                                data-testid="rename-pencil"
                            >
                                ✎
                            </button>
                        )}
                        <StatusChip hue={statusHue} data-testid="batch-status-chip">{statusLabel}</StatusChip>
                        <button onClick={refresh} className="rounded-lg p-1.5 text-batch-faint hover:bg-surface-100" aria-label="רענון">
                            <RefreshCw size={15} />
                        </button>
                    </div>
                    {renameError && <p className="mt-1 text-xs text-batch-red-ink">{renameError}</p>}
                    <p className="mt-1 text-[13px] text-batch-muted">
                        {META_RUBRIC_PREFIX} {batch.rubric_name ?? '—'}
                        {batch.class_name ? ` · ${batch.class_name}` : ''}
                        {' · '}{META_TESTS(rollup.total)}
                        {' · '}{META_CREATED(relativeTimeHe(batch.created_at, new Date()))}
                    </p>

                    {/* D1 (closeout) — files that never became jobs. The batch
                        cannot know about them (jobs ARE the total), so the
                        upload surface hands their names over and the dashboard
                        says so plainly. Dismissible: it is a notice, not a
                        blocker, and the files are still on her machine. */}
                    {uploadFailures.length > 0 && (
                        <div
                            className="mt-4 flex items-start justify-between gap-3 rounded-zone border border-batch-amber-line bg-batch-amber-soft px-4 py-3"
                            data-testid="upload-failures-notice"
                        >
                            <p className="text-sm text-batch-amber-ink">
                                {UPLOAD_FAILURES_NOTICE(uploadFailures)}
                            </p>
                            <button
                                onClick={() => setUploadFailures([])}
                                aria-label={DISMISS_NOTICE_LABEL}
                                className="shrink-0 text-batch-amber-ink hover:opacity-70"
                            >
                                ✕
                            </button>
                        </div>
                    )}

                    {/* D2 — honesty bar */}
                    <div className="mt-4">
                        <SegmentBar segments={segments} />
                    </div>

                    {/* D3 — headline */}
                    {headline && !complete && (
                        <div className="mt-4 text-[18.5px] font-semibold tracking-tight text-batch-ink" data-testid="headline">
                            {headline}
                        </div>
                    )}
                </div>

                {/* [Stage B] Her files arriving. OUTSIDE the complete/
                    incomplete split on purpose: once the last file lands the
                    batch can legitimately read as complete, and a lane that
                    lived only in the incomplete branch would take the list of
                    files that were LEFT BEHIND down with it — the silent-drop
                    class U4 exists to kill. It hides itself when it has nothing
                    left to say. */}
                {myUploadQueue && (
                    <UploadLane
                        queue={myUploadQueue}
                        onRetry={uploads.retry}
                        onRemove={uploads.remove}
                        onDismiss={uploads.clear}
                    />
                )}

                {complete ? (
                    <>
                        <CompletionHero
                            total={rollup.total}
                            approvedTranscriptions={zones.approved.length}
                            durationMinutes={completionMinutes}
                            sessionCreatedStudents={sessionCreated}
                        />
                        {SHOW_GRADING_LANE && <GradingLane
                            variant="completed"
                            draftCount={rollup.draft}
                            gradingCount={rollup.grading}
                            onOpenGrades={() => gradesRef.current?.scrollIntoView({ behavior: 'smooth' })}
                        />}
                        <FailedZone failures={batch.transcription_failures ?? []} onRetry={retryJob} retryBusy={retryBusy} />
                    </>
                ) : (
                    <>
                        {showWave && (
                            <IdentityWave
                                pills={pillViews}
                                unmatched={partition.unmatchedItems.map(u => ({
                                    transcription_id: String(u.transcription_id),
                                    filename: u.filename,
                                }))}
                                batchId={batchId}
                                bulkBusy={bulkBusy}
                                onEditPill={onEditPill}
                                onCreatePill={onCreatePill}
                                onBulkCreate={onBulkCreate}
                            />
                        )}
                        <GhostZone
                            jobs={activeJobs}
                            onRetry={retryJob}
                            retryBusy={retryBusy}
                        />
                        <CleanPanel
                            items={zones.cleanRows}
                            acceptableCount={zones.cleanRows.filter(i => i.matched_student_id).length}
                            pendingCount={zones.cleanRows.filter(isIdentityPending).length}
                            batchId={batchId}
                            subject={rubricSubject}
                            expanded={cleanExpanded}
                            onToggle={id => setCleanExpanded(prev => {
                                const n = new Set(prev);
                                if (n.has(id)) n.delete(id); else n.add(id);
                                return n;
                            })}
                            showAll={cleanShowAll}
                            onShowAll={() => setCleanShowAll(true)}
                            accepting={accepting}
                            bulkBusy={cleanBulkBusy}
                            onAcceptAll={() => void onAcceptAll()}
                            skipNotice={skipNotice}
                            manualReviewId={manualReviewId}
                            newIds={newIds}
                        />
                        <NeedsEyesQueue
                            rows={eyesRows}
                            batchId={batchId}
                            selectionGroups={batch.selection_groups ?? []}
                            firstReviewId={firstReviewId}
                            newIds={newIds}
                        />
                        <FailedZone failures={batch.transcription_failures ?? []} onRetry={retryJob} retryBusy={retryBusy} />
                        {SHOW_GRADING_LANE && <GradingLane
                            variant="subordinate"
                            draftCount={rollup.draft}
                            gradingCount={rollup.grading}
                            onOpenGrades={() => gradesRef.current?.scrollIntoView({ behavior: 'smooth' })}
                        />}
                    </>
                )}

                <div ref={gradesRef}>
                    <GradeReviewSection batch={batch} batchId={batchId} onRefresh={refresh} />
                </div>
            </div>
        </SidebarLayout>
    );
}
