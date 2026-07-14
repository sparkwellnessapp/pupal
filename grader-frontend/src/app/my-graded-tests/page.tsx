'use client';

import { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
    ClipboardCheck,
    Search,
    Calendar,
    Filter,
    Loader2,
    AlertCircle,
    Eye,
    TrendingUp,
    TrendingDown,
    Minus,
    BookOpen,
    User,
    FileText,
    ArrowRight,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { GradedTestReviewPanel } from '@/components/GradedTestReviewPanel';
import {
    listGradedTests,
    getGradedTest,
    saveGradedTestDraft,
    approveGradedTest,
    regradeGradedTest,
    manualEditGradedTest,
    retryGradedTest,
} from '@/lib/api';
import type {
    GradedTestListItem,
    GradedTestDraftResponse,
    GradedTestApprovedResponse,
    GradedTestOverrides,
} from '@/types/graded_test';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parsePercent(value: string | null): number {
    if (!value) return 0;
    return parseFloat(value);
}

function ScoreBadge({ percentage }: { percentage: number }) {
    let bgColor = 'bg-green-100 text-green-700';
    let Icon = TrendingUp;
    if (percentage < 55) { bgColor = 'bg-red-100 text-red-700'; Icon = TrendingDown; }
    else if (percentage < 70) { bgColor = 'bg-amber-100 text-amber-700'; Icon = Minus; }
    return (
        <div className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium ${bgColor}`}>
            <Icon size={14} />
            <span>{Math.round(percentage)}%</span>
        </div>
    );
}

function StatusBadge({ status }: { status: string }) {
    const map: Record<string, string> = {
        draft: 'bg-blue-100 text-blue-700',
        approved: 'bg-green-100 text-green-700',
        pending: 'bg-gray-100 text-gray-500',
        grading: 'bg-amber-100 text-amber-700',
        failed: 'bg-red-100 text-red-700',
    };
    const labels: Record<string, string> = {
        draft: 'ממתין לאישור',
        approved: 'מאושר',
        pending: 'ממתין לבדיקה',
        grading: 'בודק...',
        failed: 'שגיאה',
    };
    return (
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
            {labels[status] ?? status}
        </span>
    );
}

function TestRow({
    test,
    onView,
    onRetry,
}: {
    test: GradedTestListItem;
    onView: (id: string) => void;
    onRetry?: (id: string) => void;
}) {
    const pct = parsePercent(test.percentage);
    const hasDraft = test.status === 'draft' || test.status === 'approved';
    const isFailed = test.status === 'failed';

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('he-IL', {
            year: 'numeric', month: 'short', day: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    };

    return (
        <tr className="hover:bg-surface-50 transition-colors group">
            <td className="px-4 py-3">
                <div className="flex items-center gap-3">
                    <div className="w-9 h-9 rounded-full bg-primary-100 flex items-center justify-center">
                        <User size={16} className="text-primary-600" />
                    </div>
                    <div>
                        <p className="font-medium text-gray-900">{test.student_name}</p>
                        {test.filename && (
                            <p className="text-xs text-gray-500 truncate max-w-[150px]">{test.filename}</p>
                        )}
                    </div>
                </div>
            </td>
            <td className="px-4 py-3">
                <div className="flex items-center gap-1.5 flex-wrap">
                    <StatusBadge status={test.status} />
                    {/* S10: stale badge in list */}
                    {test.rubric_contract_stale && (test.status === 'approved' || test.status === 'draft') && (
                        <span className="px-2 py-0.5 rounded-full text-xs bg-amber-100 text-amber-700">מחוון עודכן</span>
                    )}
                </div>
            </td>
            <td className="px-4 py-3">
                {test.total_score !== null && test.total_possible !== null ? (
                    <div className="text-sm">
                        <span className="font-medium text-gray-900">{test.total_score}</span>
                        <span className="text-gray-500">/{test.total_possible}</span>
                    </div>
                ) : <span className="text-gray-400 text-sm">—</span>}
            </td>
            <td className="px-4 py-3">
                {hasDraft && test.percentage !== null
                    ? <ScoreBadge percentage={pct} />
                    : <span className="text-gray-400 text-sm">—</span>
                }
            </td>
            <td className="px-4 py-3 text-sm text-gray-500">
                <div className="flex items-center gap-1">
                    <Calendar size={12} />
                    {formatDate(test.created_at)}
                </div>
            </td>
            <td className="px-4 py-3">
                {hasDraft && (
                    <button
                        onClick={() => onView(test.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors font-medium"
                    >
                        <Eye size={14} />
                        צפייה
                    </button>
                )}
                {/* S10: retry button for failed rows */}
                {isFailed && onRetry && (
                    <button
                        onClick={() => onRetry(test.id)}
                        className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-red-600 hover:text-red-700 hover:bg-red-50 rounded-lg transition-colors font-medium"
                    >
                        נסה שוב
                    </button>
                )}
            </td>
        </tr>
    );
}

function StatsCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: React.ElementType; color: string }) {
    return (
        <div className="bg-white rounded-xl border border-surface-200 p-4">
            <div className="flex items-center justify-between">
                <div>
                    <p className="text-sm text-gray-500">{label}</p>
                    <p className="text-2xl font-bold text-gray-900 mt-1">{value}</p>
                </div>
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${color}`}>
                    <Icon size={24} />
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function MyGradedTestsPage() {
    const [tests, setTests] = useState<GradedTestListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [error, setError] = useState<string | null>(null);

    // Draft-review / approved panel state
    const [viewingDetail, setViewingDetail] = useState<GradedTestDraftResponse | GradedTestApprovedResponse | null>(null);
    const [viewingTestId, setViewingTestId] = useState<string>('');
    const [viewingTranscriptionId, setViewingTranscriptionId] = useState<string>('');
    const [isLoadingView, setIsLoadingView] = useState(false);

    // S10: polling for pending/grading rows (regrade and retry create pending successors)
    const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const stopPolling = () => {
        if (pollingRef.current !== null) {
            clearInterval(pollingRef.current);
            pollingRef.current = null;
        }
    };

    const startPolling = (testId: string) => {
        stopPolling();
        pollingRef.current = setInterval(async () => {
            try {
                const detail = await getGradedTest(testId);
                if (detail.status === 'draft' || detail.status === 'approved') {
                    stopPolling();
                    const typedDetail = detail as GradedTestDraftResponse | GradedTestApprovedResponse;
                    setViewingDetail(typedDetail);
                    setViewingTestId(testId);
                    setViewingTranscriptionId(typedDetail.transcription_id);
                } else if (detail.status === 'failed') {
                    stopPolling();
                    // Show a minimal failed state — reuse the panel's failed rendering
                    // by resetting detail to null and showing an error
                    setError('הבדיקה נכשלה. ניתן לנסות שוב מרשימת המבחנים.');
                    setViewingDetail(null);
                }
            } catch {
                stopPolling();
            }
        }, 3000);
    };

    // Clean up polling on unmount
    useEffect(() => { return () => stopPolling(); }, []);

    useEffect(() => {
        const fetchTests = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const data = await listGradedTests();
                setTests(data);
            } catch (err) {
                console.error('Failed to fetch graded tests:', err);
                setError('שגיאה בטעינת המבחנים');
            } finally {
                setIsLoading(false);
            }
        };
        fetchTests();
    }, []);

    const handleViewTest = async (testId: string) => {
        try {
            setIsLoadingView(true);
            const detail = await getGradedTest(testId);
            if (detail.status === 'draft' || detail.status === 'approved') {
                const typedDetail = detail as GradedTestDraftResponse | GradedTestApprovedResponse;
                setViewingDetail(typedDetail);
                setViewingTestId(testId);
                setViewingTranscriptionId(typedDetail.transcription_id);
            }
        } catch (err) {
            console.error('Failed to fetch test details:', err);
            setError('שגיאה בטעינת פרטי המבחן');
        } finally {
            setIsLoadingView(false);
        }
    };

    const handleSaveDraft = async (overrides: GradedTestOverrides) => {
        const updated = await saveGradedTestDraft(viewingTestId, overrides);
        setViewingDetail(updated);
        // Refresh the list status badge
        const updatedList = tests.map(t =>
            t.id === viewingTestId ? { ...t, status: updated.status } : t
        );
        setTests(updatedList);
    };

    const handleApprove = async (overrides: GradedTestOverrides) => {
        const approved = await approveGradedTest(viewingTestId, overrides);
        setViewingDetail(approved);
        // Update status in the list
        const updatedList = tests.map(t =>
            t.id === viewingTestId ? {
                ...t,
                status: 'approved',
                total_score: approved.total_score,
                total_possible: approved.total_possible,
                percentage: approved.percentage,
            } : t
        );
        setTests(updatedList);
    };

    // S10: regrade — approved + stale → pending successor → poll to draft
    const handleRegrade = async () => {
        if (!viewingTestId) return;
        if (!confirm('לבדוק מחדש לפי המחוון העדכני? פעולה זו תיצור גרסה חדשה של הבדיקה.')) return;
        try {
            const result = await regradeGradedTest(viewingTestId);
            setViewingDetail(null);  // hide panel while polling
            setViewingTestId(result.graded_test_id);
            startPolling(result.graded_test_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בבדיקה מחדש');
        }
    };

    // S10: manual edit — approved → draft successor → open editable panel
    const handleManualEdit = async () => {
        if (!viewingTestId) return;
        if (!confirm('לפתוח לעריכה ידנית? תיווצר גרסה חדשה שניתן לערוך ולאשר.')) return;
        try {
            const result = await manualEditGradedTest(viewingTestId);
            await handleViewTest(result.graded_test_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בפתיחה לעריכה');
        }
    };

    // S10: retry — failed → pending successor → poll to draft
    const handleRetry = async () => {
        if (!viewingTestId) return;
        try {
            const result = await retryGradedTest(viewingTestId);
            setViewingDetail(null);
            setViewingTestId(result.graded_test_id);
            startPolling(result.graded_test_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בניסיון חוזר');
        }
    };

    // S10: retry from list row (no panel open)
    const handleRetryFromList = async (testId: string) => {
        try {
            const result = await retryGradedTest(testId);
            setViewingTestId(result.graded_test_id);
            startPolling(result.graded_test_id);
        } catch (err) {
            setError(err instanceof Error ? err.message : 'שגיאה בניסיון חוזר');
        }
    };

    const handleBack = () => {
        stopPolling();
        setViewingDetail(null);
        setViewingTestId('');
        setViewingTranscriptionId('');
    };

    // S10: show polling spinner while waiting for a regrade/retry to produce a draft
    if (!viewingDetail && viewingTestId && pollingRef.current !== null) {
        return (
            <SidebarLayout>
                <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
                    <Loader2 className="animate-spin text-primary-500" size={40} />
                    <p className="text-gray-600">הבדיקה בתהליך... הדף יתעדכן אוטומטית.</p>
                    <button onClick={handleBack} className="text-sm text-gray-500 underline">
                        חזרה לרשימה
                    </button>
                </div>
            </SidebarLayout>
        );
    }

    // Show review panel when a test is selected
    if (viewingDetail) {
        const isDraft = viewingDetail.status === 'draft';
        const isApproved = viewingDetail.status === 'approved';
        return (
            <SidebarLayout>
                <GradedTestReviewPanel
                    response={viewingDetail}
                    transcriptionId={viewingTranscriptionId}
                    onBack={handleBack}
                    editable={isDraft}
                    onSaveDraft={isDraft ? handleSaveDraft : undefined}
                    onApprove={isDraft ? handleApprove : undefined}
                    onRegrade={isApproved ? handleRegrade : undefined}
                    onManualEdit={isApproved ? handleManualEdit : undefined}
                    // retry is handled via list-row buttons (failed rows can't open the review panel)
                />
            </SidebarLayout>
        );
    }

    const filteredTests = tests.filter(t =>
        t.student_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.filename?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    const completedTests = tests.filter(t => t.status === 'draft' || t.status === 'approved');
    const avgScore = completedTests.length > 0
        ? Math.round(completedTests.reduce((acc, t) => acc + parsePercent(t.percentage), 0) / completedTests.length)
        : 0;
    const passingCount = completedTests.filter(t => parsePercent(t.percentage) >= 55).length;

    return (
        <SidebarLayout>
            <div className="max-w-6xl mx-auto">
                {isLoadingView && (
                    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl p-6 flex items-center gap-3">
                            <Loader2 className="animate-spin text-primary-500" size={24} />
                            <span>טוען פרטי מבחן...</span>
                        </div>
                    </div>
                )}

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">המבחנים שנבדקו</h1>
                        <p className="text-gray-500 mt-1">צפה בכל תוצאות הבדיקה</p>
                    </div>
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 bg-primary-500 text-white px-4 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium"
                    >
                        <ClipboardCheck size={18} />
                        בדקי מבחנים חדשים
                    </Link>
                </div>

                {!isLoading && completedTests.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                        <StatsCard label="סה״כ מבחנים" value={tests.length} icon={FileText} color="bg-primary-100 text-primary-600" />
                        <StatsCard label="ציון ממוצע" value={`${avgScore}%`} icon={TrendingUp} color="bg-green-100 text-green-600" />
                        <StatsCard label="עוברים" value={`${passingCount}/${completedTests.length}`} icon={ClipboardCheck} color="bg-amber-100 text-amber-600" />
                    </div>
                )}

                <div className="bg-white rounded-xl border border-surface-200 p-4 mb-6">
                    <div className="flex flex-col sm:flex-row gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="חפש לפי שם תלמיד או קובץ..."
                                className="w-full pr-10 pl-4 py-2.5 border border-surface-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                            />
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2.5 border border-surface-300 rounded-lg text-sm text-gray-600 hover:bg-surface-50 transition-colors">
                            <Filter size={16} />
                            סינון
                        </button>
                    </div>
                </div>

                {isLoading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="animate-spin text-primary-500" size={40} />
                    </div>
                ) : error ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                        <AlertCircle className="mx-auto text-red-500 mb-2" size={32} />
                        <p className="text-red-700">{error}</p>
                    </div>
                ) : filteredTests.length === 0 ? (
                    <div className="bg-white rounded-xl border border-surface-200 p-12 text-center">
                        <ClipboardCheck className="mx-auto text-gray-300 mb-4" size={48} />
                        <h3 className="text-lg font-medium text-gray-700 mb-2">
                            {searchQuery ? 'לא נמצאו תוצאות' : 'אין מבחנים שנבדקו'}
                        </h3>
                        <p className="text-gray-500 mb-4">
                            {searchQuery ? 'נסה לחפש במילים אחרות' : 'התחל לבדוק מבחנים כדי לראות את התוצאות כאן'}
                        </p>
                        {!searchQuery && (
                            <Link href="/" className="inline-flex items-center gap-2 bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 transition-colors">
                                <ClipboardCheck size={18} />
                                בדקי מבחנים
                            </Link>
                        )}
                    </div>
                ) : (
                    <div className="bg-white rounded-xl border border-surface-200 overflow-hidden">
                        <div className="overflow-x-auto">
                            <table className="w-full">
                                <thead className="bg-surface-50 border-b border-surface-200">
                                    <tr>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">תלמיד</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">סטטוס</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">ציון</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">אחוז</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">תאריך</th>
                                        <th className="px-4 py-3 w-24"></th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-surface-100">
                                    {filteredTests.map(test => (
                                        <TestRow
                                            key={test.id}
                                            test={test}
                                            onView={handleViewTest}
                                            onRetry={handleRetryFromList}
                                        />
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {!isLoading && filteredTests.length > 0 && (
                    <div className="mt-6 text-center text-sm text-gray-500">
                        מציג {filteredTests.length} מתוך {tests.length} מבחנים
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
