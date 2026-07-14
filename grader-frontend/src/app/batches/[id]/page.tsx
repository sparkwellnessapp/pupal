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
import { StudentPicker } from '@/components/StudentPicker';
import { TranscriptionReviewPanel } from '@/components/TranscriptionReviewPanel';
import { GradedTestReviewPanel } from '@/components/GradedTestReviewPanel';
import {
    getBatch,
    listBatches,
    acceptCleanTranscriptions,
    acceptOneTranscription,
    saveGradedTestDraft,
    approveGradedTest,
    getGradedTest,
} from '@/lib/api';
import type {
    BatchDetailResponse,
    BatchTranscriptionItem,
    BatchRollup,
    AcceptCleanItem,
    GradeAnswerInputItem,
    FLAG_REASON_LABELS,
} from '@/types/batch';
import { FLAG_REASON_LABELS as LABELS } from '@/types/batch';
import type { GradedTestDraftResponse, GradedTestApprovedResponse, GradedTestOverrides } from '@/types/graded_test';
import type { GradeAnswerInput } from '@/types/transcription';

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
// Individual flagged-test review card
// ---------------------------------------------------------------------------
function FlaggedTestCard({
    item,
    onAccept,
}: {
    item: BatchTranscriptionItem;
    onAccept: (transcriptionId: string, studentId: string, answers: GradeAnswerInputItem[]) => Promise<void>;
}) {
    const [expanded, setExpanded] = useState(false);
    const [studentId, setStudentId] = useState<string>(item.matched_student_id ?? '');
    const [accepting, setAccepting] = useState(false);
    const [answers, setAnswers] = useState<GradeAnswerInputItem[]>(
        item.draft.answers.map(a => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id ?? null,
            answer_text: a.answer_text,
        }))
    );

    const handleAccept = async () => {
        if (!studentId) return;
        setAccepting(true);
        try {
            await onAccept(String(item.transcription_id), studentId, answers);
        } finally {
            setAccepting(false);
        }
    };

    if (item.transcription_status === 'approved') {
        return (
            <div className="px-4 py-3 bg-green-50 border border-green-200 rounded-xl flex items-center gap-2 text-sm text-green-700">
                <CheckCircle2 size={16} className="shrink-0" />
                {item.filename ?? 'ללא שם'} — אושר
            </div>
        );
    }

    return (
        <div className="border border-amber-300 rounded-xl overflow-hidden">
            <div
                className="flex items-center justify-between px-4 py-3 bg-amber-50 cursor-pointer"
                onClick={() => setExpanded(v => !v)}
            >
                <div className="flex items-center gap-2">
                    <AlertTriangle size={16} className="text-amber-600 shrink-0" />
                    <span className="font-medium text-sm text-gray-800">{item.filename ?? 'ללא שם'}</span>
                </div>
                <div className="flex items-center gap-1 flex-wrap">
                    {item.flag_verdict.reasons.map(r => (
                        <span key={r} className="px-2 py-0.5 bg-amber-100 text-amber-700 rounded-full text-xs">
                            {(LABELS as Record<string, string>)[r] ?? r}
                        </span>
                    ))}
                </div>
            </div>

            {expanded && (
                <div className="p-4 space-y-4">
                    {/* Student assignment */}
                    <div>
                        <label className="block text-xs text-gray-500 mb-1">שיוך תלמיד</label>
                        <StudentPicker value={studentId || null} onChange={setStudentId} />
                    </div>

                    {/* Answer review — editable textareas */}
                    <div className="space-y-2">
                        {answers.map((ans, i) => (
                            <div key={i} className="space-y-1">
                                <label className="text-xs text-gray-500">
                                    שאלה {ans.question_number}{ans.sub_question_id ? `  (${ans.sub_question_id})` : ''}
                                </label>
                                <textarea
                                    value={ans.answer_text}
                                    onChange={e => {
                                        const updated = [...answers];
                                        updated[i] = { ...updated[i], answer_text: e.target.value };
                                        setAnswers(updated);
                                    }}
                                    rows={3}
                                    className="w-full border border-surface-300 rounded-lg px-3 py-2 text-sm resize-y font-mono"
                                    dir="ltr"
                                />
                            </div>
                        ))}
                    </div>

                    <button
                        onClick={handleAccept}
                        disabled={!studentId || accepting}
                        className="w-full flex items-center justify-center gap-2 bg-primary-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-primary-700 disabled:opacity-50 transition-colors"
                    >
                        {accepting ? <Loader2 size={14} className="animate-spin" /> : <CheckCircle2 size={14} />}
                        אשר תמלול
                    </button>
                </div>
            )}
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
            const items: AcceptCleanItem[] = cleanItems
                .filter(i => i.matched_student_id && i.transcription_status === 'transcribed')
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

    const pendingClean = cleanItems.filter(i => i.transcription_status === 'transcribed');

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
                                {i.filename ?? 'ללא שם'} → {i.matched_student_name ?? '—'}
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

    const clean = batch.transcriptions.filter(
        t => !t.flag_verdict.review_needed && t.transcription_status === 'transcribed'
    );
    const flagged = batch.transcriptions.filter(
        t => t.flag_verdict.review_needed && t.transcription_status === 'transcribed'
    );
    const allReviewed = batch.transcriptions.every(t => t.transcription_status === 'approved');

    const handleAcceptOne = async (transcriptionId: string, studentId: string, answers: GradeAnswerInputItem[]) => {
        await acceptOneTranscription(batchId, transcriptionId, studentId, answers as GradeAnswerInput[]);
        await refresh();
    };

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

                {/* Transcription review phase */}
                {!allReviewed && (
                    <div className="space-y-4">
                        <h2 className="font-semibold text-gray-800">סקירת תמלולים</h2>

                        {batch.rollup.transcribing > 0 && (
                            <div className="flex items-center gap-2 text-sm text-gray-600 px-4 py-3 bg-blue-50 rounded-xl border border-blue-200">
                                <Loader2 size={16} className="animate-spin text-blue-500" />
                                {batch.rollup.transcribing} מבחנים עדיין בתהליך תמלול...
                            </div>
                        )}

                        {clean.length > 0 && (
                            <CleanTestsPanel
                                cleanItems={clean}
                                batchId={batchId}
                                onAccepted={refresh}
                            />
                        )}

                        {flagged.length > 0 && (
                            <div className="space-y-3">
                                <p className="text-sm font-medium text-amber-700">
                                    {flagged.length} מבחנים דורשים בדיקה פרטנית:
                                </p>
                                {flagged.map(item => (
                                    <FlaggedTestCard
                                        key={String(item.transcription_id)}
                                        item={item}
                                        onAccept={handleAcceptOne}
                                    />
                                ))}
                            </div>
                        )}
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
