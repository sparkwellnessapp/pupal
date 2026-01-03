'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
    ClipboardCheck,
    Search,
    Calendar,
    Filter,
    Loader2,
    AlertCircle,
    Download,
    Eye,
    Trash2,
    MoreVertical,
    TrendingUp,
    TrendingDown,
    Minus,
    BookOpen,
    User,
    FileText,
    X,
    ArrowRight,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { GradingResults } from '@/components/GradingResults';
import { listAllGradedTests, getGradedTestById, GradedTestListItem, GradedTestResult } from '@/lib/api';

// Score Badge Component
function ScoreBadge({ percentage }: { percentage: number }) {
    let bgColor = 'bg-green-100 text-green-700';
    let Icon = TrendingUp;

    if (percentage < 55) {
        bgColor = 'bg-red-100 text-red-700';
        Icon = TrendingDown;
    } else if (percentage < 70) {
        bgColor = 'bg-amber-100 text-amber-700';
        Icon = Minus;
    }

    return (
        <div className={`flex items-center gap-1 px-3 py-1.5 rounded-full text-sm font-medium ${bgColor}`}>
            <Icon size={14} />
            <span>{percentage}%</span>
        </div>
    );
}

// Test Row Component
function TestRow({
    test,
    onView
}: {
    test: GradedTestListItem;
    onView: (testId: string) => void;
}) {
    const [showMenu, setShowMenu] = useState(false);

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('he-IL', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
        });
    };

    const handleViewClick = () => {
        setShowMenu(false);
        onView(test.id);
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
                <div className="flex items-center gap-2 text-sm text-gray-600">
                    <BookOpen size={14} className="text-gray-400" />
                    <span className="truncate max-w-[200px]">{test.rubric_name || 'לא ידוע'}</span>
                </div>
            </td>
            <td className="px-4 py-3">
                <div className="text-sm">
                    <span className="font-medium text-gray-900">{test.total_score}</span>
                    <span className="text-gray-500">/{test.total_possible}</span>
                </div>
            </td>
            <td className="px-4 py-3">
                <ScoreBadge percentage={Math.round(test.percentage)} />
            </td>
            <td className="px-4 py-3 text-sm text-gray-500">
                <div className="flex items-center gap-1">
                    <Calendar size={12} />
                    {formatDate(test.created_at)}
                </div>
            </td>
            {/* View button - always visible */}
            <td className="px-4 py-3">
                <button
                    onClick={handleViewClick}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors font-medium"
                >
                    <Eye size={14} />
                    צפייה
                </button>
            </td>
            {/* More options menu */}
            <td className="px-4 py-3">
                <div className="relative">
                    <button
                        onClick={() => setShowMenu(!showMenu)}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-surface-100 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                    >
                        <MoreVertical size={18} />
                    </button>

                    {showMenu && (
                        <div className="absolute left-0 top-8 w-36 bg-white rounded-lg shadow-xl border border-surface-200 py-1 z-10">
                            <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-surface-50">
                                <Download size={14} />
                                הורדה
                            </button>
                            <hr className="my-1 border-surface-200" />
                            <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                                <Trash2 size={14} />
                                מחיקה
                            </button>
                        </div>
                    )}
                </div>
            </td>
        </tr>
    );
}

// Stats Card Component
function StatsCard({ label, value, icon: Icon, color }: { label: string; value: string | number; icon: any; color: string }) {
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

// Main Page Component
export default function MyGradedTestsPage() {
    const [tests, setTests] = useState<GradedTestListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [error, setError] = useState<string | null>(null);

    // View modal state
    const [viewingTest, setViewingTest] = useState<GradedTestResult | null>(null);
    const [isLoadingView, setIsLoadingView] = useState(false);

    useEffect(() => {
        const fetchTests = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const data = await listAllGradedTests();
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
            const fullTest = await getGradedTestById(testId);
            setViewingTest(fullTest);
        } catch (err) {
            console.error('Failed to fetch test details:', err);
            setError('שגיאה בטעינת פרטי המבחן');
        } finally {
            setIsLoadingView(false);
        }
    };

    const handleCloseView = () => {
        setViewingTest(null);
    };

    const filteredTests = tests.filter(t =>
        t.student_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.rubric_name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.filename?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // Calculate stats
    const avgScore = tests.length > 0
        ? Math.round(tests.reduce((acc, t) => acc + t.percentage, 0) / tests.length)
        : 0;
    const passingCount = tests.filter(t => t.percentage >= 55).length;

    // Show GradingResults when viewing a test
    if (viewingTest) {
        return (
            <SidebarLayout>
                <div className="max-w-6xl mx-auto">
                    {/* Back button header */}
                    <div className="flex items-center gap-4 mb-6">
                        <button
                            onClick={handleCloseView}
                            className="flex items-center gap-2 text-gray-500 hover:text-gray-700 transition-colors"
                        >
                            <ArrowRight size={18} />
                            חזרה לרשימה
                        </button>
                    </div>

                    {/* GradingResults component */}
                    <GradingResults
                        results={[viewingTest]}
                        stats={{ total: 1, successful: 1, failed: 0, errors: [] }}
                        onBack={handleCloseView}
                    />
                </div>
            </SidebarLayout>
        );
    }

    return (
        <SidebarLayout>
            <div className="max-w-6xl mx-auto">
                {/* Loading overlay for view */}
                {isLoadingView && (
                    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl p-6 flex items-center gap-3">
                            <Loader2 className="animate-spin text-primary-500" size={24} />
                            <span>טוען פרטי מבחן...</span>
                        </div>
                    </div>
                )}

                {/* Page Header */}
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

                {/* Stats Cards */}
                {!isLoading && tests.length > 0 && (
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
                        <StatsCard
                            label="סה״כ מבחנים"
                            value={tests.length}
                            icon={FileText}
                            color="bg-primary-100 text-primary-600"
                        />
                        <StatsCard
                            label="ציון ממוצע"
                            value={`${avgScore}%`}
                            icon={TrendingUp}
                            color="bg-green-100 text-green-600"
                        />
                        <StatsCard
                            label="עוברים"
                            value={`${passingCount}/${tests.length}`}
                            icon={ClipboardCheck}
                            color="bg-amber-100 text-amber-600"
                        />
                    </div>
                )}

                {/* Search and Filter */}
                <div className="bg-white rounded-xl border border-surface-200 p-4 mb-6">
                    <div className="flex flex-col sm:flex-row gap-3">
                        <div className="relative flex-1">
                            <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                            <input
                                type="text"
                                value={searchQuery}
                                onChange={(e) => setSearchQuery(e.target.value)}
                                placeholder="חפש לפי שם תלמיד, מחוון או קובץ..."
                                className="w-full pr-10 pl-4 py-2.5 border border-surface-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                            />
                        </div>
                        <button className="flex items-center gap-2 px-4 py-2.5 border border-surface-300 rounded-lg text-sm text-gray-600 hover:bg-surface-50 transition-colors">
                            <Filter size={16} />
                            סינון
                        </button>
                    </div>
                </div>

                {/* Content */}
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
                            {searchQuery
                                ? 'נסה לחפש במילים אחרות'
                                : 'התחל לבדוק מבחנים כדי לראות את התוצאות כאן'
                            }
                        </p>
                        {!searchQuery && (
                            <Link
                                href="/"
                                className="inline-flex items-center gap-2 bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 transition-colors"
                            >
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
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">מחוון</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">ציון</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">אחוז</th>
                                        <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wide">תאריך</th>
                                        <th className="px-4 py-3 w-20"></th>
                                        <th className="px-4 py-3 w-12"></th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-surface-100">
                                    {filteredTests.map((test) => (
                                        <TestRow
                                            key={test.id}
                                            test={test}
                                            onView={handleViewTest}
                                        />
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}

                {/* Footer Stats */}
                {!isLoading && filteredTests.length > 0 && (
                    <div className="mt-6 text-center text-sm text-gray-500">
                        מציג {filteredTests.length} מתוך {tests.length} מבחנים
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
