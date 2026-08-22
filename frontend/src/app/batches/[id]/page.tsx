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
import {
    acceptCleanTranscriptions,
    ApiAuthError,
    approveGradedTest,
    createStudent,
    ClassroomConflictError,
    getBatch,
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
import { CleanPanel } from '@/components/batch/CleanPanel';
import { NeedsEyesQueue } from '@/components/batch/NeedsEyesQueue';
import { FailedZone } from '@/components/batch/FailedZone';
import { GradingLane } from '@/components/batch/GradingLane';
import { CompletionHero } from '@/components/batch/CompletionHero';
import { normalizeName, partitionItems } from '@/utils/batch-partition';
import { assignZones } from '@/utils/zone-assignment';
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
import { SHOW_GRADING_LANE } from '@/lib/flags';

// ---------------------------------------------------------------------------
// Grade-review section — per-test rows opening the S9 panel (pre-redesign
// machinery kept; chips migrated onto the F8 primitive)
// ---------------------------------------------------------------------------
function GradeReviewSection({ items, batchId }: { items: BatchTranscriptionItem[]; batchId: string }) {
    const [activeTestId, setActiveTestId] = useState<string | null>(null);
    const [activeDetail, setActiveDetail] = useState<GradedTestDraftResponse | GradedTestApprovedResponse | null>(null);

    const openTest = async (gtId: string) => {
        const detail = await getGradedTest(gtId);
        if (detail.status === 'draft' || detail.status === 'approved') {
            setActiveTestId(gtId);
            setActiveDetail(detail as GradedTestDraftResponse | GradedTestApprovedResponse);
        }
    };

    if (activeDetail && activeTestId) {
        const isDraft = activeDetail.status === 'draft';
        return (
            <GradedTestReviewPanel
                response={activeDetail}
                transcriptionId={activeDetail.transcription_id}
                onBack={() => { setActiveTestId(null); setActiveDetail(null); }}
                editable={isDraft}
                onSaveDraft={isDraft ? async (overrides) => {
                    const updated = await saveGradedTestDraft(activeTestId, overrides);
                    setActiveDetail(updated);
                } : undefined}
                onApprove={isDraft ? async (overrides) => {
                    const approved = await approveGradedTest(activeTestId, overrides);
                    setActiveDetail(approved);
                } : undefined}
            />
        );
    }

    const gradedItems = items.filter(i => i.graded_test_id);
    if (gradedItems.length === 0) return null;

    const hueFor = (s: string | null): ChipHue =>
        s === 'approved' ? 'green' : s === 'draft' ? 'blue' : s === 'failed' ? 'red' : 'amber';
    const labelFor = (s: string | null): string =>
        s === 'approved' ? 'מאושר' : s === 'draft' ? 'טיוטה' : s === 'failed' ? 'נכשל' : 'בבדיקה...';

    return (
        <div className="space-y-2">
            <h3 className="text-sm font-medium text-batch-ink">סקירת ציונים</h3>
            {gradedItems.map(item => (
                <div
                    key={String(item.transcription_id)}
                    className="flex items-center justify-between rounded-zone-sm border border-batch-line bg-white px-4 py-3"
                >
                    <div>
                        <p className="text-sm font-medium text-batch-ink">{item.filename ?? 'ללא שם'}</p>
                        <p className="text-xs text-batch-muted">{item.matched_student_name ?? item.student_name_suggestion ?? '—'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        {item.total_score !== null && item.total_possible !== null && (
                            <span className="text-sm font-medium text-batch-ink" dir="ltr">
                                {item.total_score}/{item.total_possible}
                            </span>
                        )}
                        <StatusChip hue={hueFor(item.graded_test_status)}>
                            {labelFor(item.graded_test_status)}
                        </StatusChip>
                        {(item.graded_test_status === 'draft' || item.graded_test_status === 'approved') && (
                            <button
                                onClick={() => openTest(String(item.graded_test_id!))}
                                className="text-xs text-primary-600 hover:underline"
                            >
                                פתח
                            </button>
                        )}
                    </div>
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
    const [uploadFailures, setUploadFailures] = useState<string[]>([]);

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
    const statusLabel = batchStatusLabel(batch.status, {
        transcribing: rollup.transcribing,
        activeJobs: activeJobs.length,
    });
    const statusHue: ChipHue =
        batch.status === 'completed' ? 'green'
        : batch.status === 'failed' ? 'red'
        : batch.status === 'in_progress' && (rollup.transcribing > 0 || activeJobs.length > 0) ? 'blue'
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
    const reviewOrder = computeReviewOrder(batch.transcriptions);
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
                        <GhostZone jobs={activeJobs} />
                        <CleanPanel
                            items={zones.cleanRows}
                            batchId={batchId}
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
                    <GradeReviewSection items={batch.transcriptions} batchId={batchId} />
                </div>
            </div>
        </SidebarLayout>
    );
}
