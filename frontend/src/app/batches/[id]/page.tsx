'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import {
    Loader2,
    AlertCircle,
    CheckCircle2,
    RefreshCw,
    Users,
    ArrowRight,
    AlertTriangle,
    ClipboardCheck,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { GradedTestReviewPanel } from '@/components/GradedTestReviewPanel';
import {
    getBatch,
    acceptCleanTranscriptions,
    saveGradedTestDraft,
    approveGradedTest,
    getGradedTest,
} from '@/lib/api';
import type {
    BatchDetailResponse,
    BatchTranscriptionItem,
    BatchRollup,
    AcceptCleanItem,
} from '@/types/batch';
import { FLAG_REASON_LABELS as LABELS } from '@/types/batch';
import type { GradedTestDraftResponse, GradedTestApprovedResponse, GradedTestOverrides } from '@/types/graded_test';
import { untranscribedResidue } from '@/utils/batch-residue';
import { editedExcludedCount, untranscribedFilesCount } from '@/utils/hebrew-plural';

const POLL_INTERVAL_MS = 3000;

// ---------------------------------------------------------------------------
// Roll-up progress bar
// ---------------------------------------------------------------------------
function RollupBar({ rollup }: { rollup: BatchRollup }) {
    const pct = rollup.total > 0
        ? Math.round((rollup.approved / rollup.total) * 100)
        : 0;
    return (
        <div className="bg-white rounded-xl border border-surface-200 p-4">
            <div className="flex justify-between text-sm text-gray-600 mb-2">
                <span>התקדמות</span>
                <span>{rollup.approved}/{rollup.total} מאושרים</span>
            </div>
            <div className="w-full bg-surface-100 rounded-full h-2">
                <div
                    className="bg-green-500 h-2 rounded-full transition-all duration-500"
                    style={{ width: `${pct}%` }}
                />
            </div>
            <div className="mt-3 grid grid-cols-4 gap-2 text-xs text-center">
                {rollup.transcribing > 0 && <Chip label={`${rollup.transcribing} מתמלל`} color="blue" />}
                {rollup.transcribed > 0 && <Chip label={`${rollup.transcribed} ממתין לבדיקה`} color="amber" />}
                {rollup.grading > 0 && <Chip label={`${rollup.grading} בבדיקה`} color="purple" />}
                {rollup.draft > 0 && <Chip label={`${rollup.draft} טיוטה`} color="blue" />}
                {rollup.approved > 0 && <Chip label={`${rollup.approved} מאושר`} color="green" />}
                {rollup.failed > 0 && <Chip label={`${rollup.failed} נכשל`} color="red" />}
            </div>
        </div>
    );
}

function Chip({ label, color }: { label: string; color: string }) {
    const colors: Record<string, string> = {
        blue: 'bg-blue-100 text-blue-700',
        amber: 'bg-amber-100 text-amber-700',
        purple: 'bg-purple-100 text-purple-700',
        green: 'bg-green-100 text-green-700',
        red: 'bg-red-100 text-red-700',
    };
    return (
        <span className={`px-2 py-1 rounded-full font-medium ${colors[color] ?? 'bg-gray-100 text-gray-700'}`}>
            {label}
        </span>
    );
}

// ---------------------------------------------------------------------------
// Per-test summary row — the review itself happens in the full-screen route
// (/batches/[id]/review/[transcriptionId]); the blind inline editor is gone.
// ---------------------------------------------------------------------------
function TestSummaryRow({ item, batchId }: { item: BatchTranscriptionItem; batchId: string }) {
    const reviewHref = `/batches/${batchId}/review/${String(item.transcription_id)}`;

    if (item.transcription_status === 'approved') {
        return (
            <div className="px-4 py-3 bg-green-50 border border-green-200 rounded-xl flex items-center justify-between gap-2 text-sm text-green-700">
                <span className="flex items-center gap-2">
                    <CheckCircle2 size={16} className="shrink-0" />
                    {item.filename ?? 'ללא שם'} — אושר
                </span>
                <Link href={reviewHref} className="text-green-700 underline text-xs shrink-0">
                    צפייה
                </Link>
            </div>
        );
    }

    return (
        <div className="flex items-center justify-between gap-3 px-4 py-3 bg-amber-50 border border-amber-300 rounded-xl">
            <div className="flex items-center gap-2 flex-wrap min-w-0">
                <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                <span className="font-medium text-sm text-gray-800">{item.filename ?? 'ללא שם'}</span>
                {item.flag_verdict.reasons.map(r => (
                    <span key={r} className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs">
                        {(LABELS as Record<string, string>)[r] ?? r}
                    </span>
                ))}
                {item.review && (
                    <span className="px-2 py-0.5 bg-blue-100 text-blue-700 rounded-full text-xs">
                        נערך ידנית
                    </span>
                )}
            </div>
            <Link
                href={reviewHref}
                className="shrink-0 bg-primary-600 text-white px-3 py-1.5 rounded-lg text-sm font-medium hover:bg-primary-700 transition-colors"
            >
                פתיחה לבדיקה
            </Link>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Clean-tests panel
// ---------------------------------------------------------------------------
function CleanTestsPanel({
    cleanItems,
    batchId,
    onAccepted,
}: {
    /** UNTOUCHED clean items only — teacher-edited ones (Δ1) are the caller's
     *  problem and go through individual accept in the review route. */
    cleanItems: BatchTranscriptionItem[];
    batchId: string;
    onAccepted: () => void;
}) {
    const [accepting, setAccepting] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleAcceptAll = async () => {
        setAccepting(true);
        setError(null);
        try {
            // Δ1 client filter (cosmetic — the server enforces the exclusion):
            // a saved review overlay means teacher-touched ⇒ not "clean".
            const items: AcceptCleanItem[] = cleanItems
                .filter(i => i.matched_student_id && i.transcription_status === 'transcribed' && !i.review)
                .map(i => ({
                    transcription_id: String(i.transcription_id),
                    student_id: i.matched_student_id!,
                }));
            if (items.length === 0) return;
            await acceptCleanTranscriptions(batchId, items);
            onAccepted();
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה');
        } finally {
            setAccepting(false);
        }
    };

    const pendingClean = cleanItems.filter(i => i.transcription_status === 'transcribed' && !i.review);

    if (pendingClean.length === 0) return null;

    return (
        <div className="bg-green-50 border border-green-300 rounded-xl p-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="font-medium text-green-800 text-sm">
                        {pendingClean.length} תמלולים נקיים — מוכנים לאישור בבת-אחת
                    </p>
                    <div className="mt-1 space-y-0.5">
                        {pendingClean.slice(0, 5).map(i => (
                            <p key={String(i.transcription_id)} className="text-xs text-green-700">
                                <Link
                                    href={`/batches/${batchId}/review/${String(i.transcription_id)}`}
                                    className="underline hover:text-green-900"
                                >
                                    {i.filename ?? 'ללא שם'}
                                </Link>
                                {' '}→ {i.matched_student_name ?? '—'}
                            </p>
                        ))}
                        {pendingClean.length > 5 && (
                            <p className="text-xs text-green-600">ועוד {pendingClean.length - 5}...</p>
                        )}
                    </div>
                </div>
                <button
                    onClick={handleAcceptAll}
                    disabled={accepting}
                    className="flex items-center gap-1.5 bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-50 transition-colors shrink-0 mr-4"
                >
                    {accepting ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                    אשר את כולם ({pendingClean.length})
                </button>
            </div>
            {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Grade-review section — per-test rows linking to S9 panel
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

    return (
        <div className="space-y-2">
            <h3 className="font-medium text-gray-800 text-sm">סקירת ציונים</h3>
            {gradedItems.map(item => (
                <div
                    key={String(item.transcription_id)}
                    className="flex items-center justify-between px-4 py-3 bg-white border border-surface-200 rounded-xl"
                >
                    <div>
                        <p className="text-sm font-medium text-gray-800">{item.filename ?? 'ללא שם'}</p>
                        <p className="text-xs text-gray-500">{item.matched_student_name ?? item.student_name_suggestion ?? '—'}</p>
                    </div>
                    <div className="flex items-center gap-3">
                        {item.total_score !== null && item.total_possible !== null && (
                            <span className="text-sm font-medium text-gray-700">
                                {item.total_score}/{item.total_possible}
                            </span>
                        )}
                        <Chip
                            label={
                                item.graded_test_status === 'approved' ? 'מאושר' :
                                item.graded_test_status === 'draft' ? 'טיוטה' :
                                item.graded_test_status === 'failed' ? 'נכשל' : 'בבדיקה...'
                            }
                            color={
                                item.graded_test_status === 'approved' ? 'green' :
                                item.graded_test_status === 'draft' ? 'blue' :
                                item.graded_test_status === 'failed' ? 'red' : 'amber'
                            }
                        />
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
    const batchId = params?.id as string;

    const [batch, setBatch] = useState<BatchDetailResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const refresh = useCallback(async () => {
        try {
            const data = await getBatch(batchId);
            setBatch(data);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בטעינת האצווה');
        }
    }, [batchId]);

    useEffect(() => {
        setLoading(true);
        refresh().finally(() => setLoading(false));
    }, [refresh]);

    // Auto-poll while in-progress
    useEffect(() => {
        if (!batch) return;
        const inProgress = batch.status === 'in_progress';
        if (inProgress && !pollingRef.current) {
            pollingRef.current = setInterval(refresh, POLL_INTERVAL_MS);
        } else if (!inProgress && pollingRef.current) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
        return () => {
            if (pollingRef.current) { clearInterval(pollingRef.current); pollingRef.current = null; }
        };
    }, [batch?.status, refresh]);

    if (loading) {
        return (
            <SidebarLayout>
                <div className="flex items-center justify-center min-h-[60vh]">
                    <Loader2 className="animate-spin text-primary-500" size={40} />
                </div>
            </SidebarLayout>
        );
    }

    if (error || !batch) {
        return (
            <SidebarLayout>
                <div className="max-w-xl mx-auto mt-12 p-6 bg-red-50 border border-red-200 rounded-xl text-center">
                    <AlertCircle className="mx-auto text-red-500 mb-2" size={32} />
                    <p className="text-red-700">{error ?? 'אצווה לא נמצאה'}</p>
                    <Link href="/" className="mt-4 inline-block text-sm text-primary-600 underline">חזרה</Link>
                </div>
            </SidebarLayout>
        );
    }

    const pending = batch.transcriptions.filter(t => t.transcription_status === 'transcribed');
    // Δ1: a saved review overlay means teacher-touched ⇒ needs individual accept,
    // even when the flag verdict called it clean.
    const untouchedClean = pending.filter(t => !t.flag_verdict.review_needed && !t.review);
    const touchedClean = pending.filter(t => !t.flag_verdict.review_needed && t.review);
    const flagged = pending.filter(t => t.flag_verdict.review_needed);
    const individualRows = [...flagged, ...touchedClean];

    // The gate counts ROWS ONLY (phantom never-transcribed items are the
    // residue line's job, never reviewable) — and an empty batch is not "done".
    const allReviewed = batch.transcriptions.length > 0
        && batch.transcriptions.every(t => t.transcription_status === 'approved');

    // Δ15: progress-based un-transcribed residue.
    const residue = untranscribedResidue({
        testCount: batch.rollup.total,
        batchCreatedAt: batch.created_at,
        itemCreatedAts: batch.transcriptions.map(t => t.created_at),
        now: Date.now(),
    });

    return (
        <SidebarLayout>
            <div className="max-w-4xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <Link href="/batches" className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1 mb-1">
                            <ArrowRight size={14} /> כל האצוות
                        </Link>
                        <h1 className="text-xl font-bold text-gray-900">
                            {batch.name ?? `אצווה ${batchId.slice(0, 8)}`}
                        </h1>
                        <p className="text-sm text-gray-500">{batch.rollup.total} מבחנים · {batch.status}</p>
                    </div>
                    <button onClick={refresh} className="p-2 rounded-lg hover:bg-surface-100 text-gray-500">
                        <RefreshCw size={18} />
                    </button>
                </div>

                {/* Roll-up */}
                <RollupBar rollup={batch.rollup} />

                {/* In-flight transcription / Δ15 residue — honest, mutually exclusive */}
                {batch.rollup.transcribing > 0 && !residue.visible && (
                    <div className="flex items-center gap-2 text-sm text-gray-600 px-4 py-3 bg-blue-50 rounded-xl border border-blue-200">
                        <Loader2 size={16} className="animate-spin text-blue-500" />
                        {batch.rollup.transcribing} מבחנים עדיין בתהליך תמלול...
                    </div>
                )}
                {residue.visible && (
                    <div className="flex items-center gap-2 text-sm text-amber-800 px-4 py-3 bg-amber-50 rounded-xl border border-amber-300">
                        <AlertTriangle size={16} className="text-amber-600" />
                        {untranscribedFilesCount(residue.missing)}
                    </div>
                )}

                {/* Transcription review phase */}
                {!allReviewed && batch.transcriptions.length > 0 && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-gray-800">סקירת תמלולים</h2>

                        {untouchedClean.length > 0 && (
                            <CleanTestsPanel
                                cleanItems={untouchedClean}
                                batchId={batchId}
                                onAccepted={refresh}
                            />
                        )}

                        {touchedClean.length > 0 && (
                            <p className="text-sm text-blue-700">
                                {editedExcludedCount(touchedClean.length)}
                            </p>
                        )}

                        {individualRows.length > 0 && (
                            <div className="space-y-3">
                                <p className="text-sm font-medium text-amber-700">
                                    {individualRows.length} מבחנים דורשים בדיקה פרטנית:
                                </p>
                                {individualRows.map(item => (
                                    <TestSummaryRow
                                        key={String(item.transcription_id)}
                                        item={item}
                                        batchId={batchId}
                                    />
                                ))}
                            </div>
                        )}
                    </div>
                )}

                {/* Transcription phase complete (grading may still be running) */}
                {allReviewed && (batch.rollup.grading > 0 || batch.rollup.draft > 0) && (
                    <div className="px-4 py-3 bg-green-50 border border-green-200 rounded-xl flex items-center gap-2 text-sm text-green-700">
                        <CheckCircle2 size={16} />
                        כל התמלולים אושרו — המבחנים נשלחו לבדיקה
                    </div>
                )}

                {/* Grade review phase */}
                {batch.transcriptions.some(t => t.graded_test_id) && (
                    <GradeReviewSection items={batch.transcriptions} batchId={batchId} />
                )}

                {allReviewed && batch.rollup.grading === 0 && batch.rollup.draft === 0 && batch.rollup.approved === batch.rollup.total && (
                    <div className="px-4 py-3 bg-green-50 border border-green-300 rounded-xl flex items-center gap-2 text-green-800">
                        <ClipboardCheck size={18} />
                        כל המבחנים אושרו!
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
