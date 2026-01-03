'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import {
    BookOpen,
    Search,
    Calendar,
    MoreVertical,
    Plus,
    Loader2,
    Share2,
    Trash2,
    Edit,
    Eye,
    FileText,
    AlertCircle,
    ArrowRight,
    Save,
    X,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { RubricEditor } from '@/components/RubricEditor';
import { listRubrics, getRubric, updateRubric, RubricListItem, ExtractedQuestion } from '@/lib/api';

// Rubric Card Component
function RubricCard({
    rubric,
    onSelect,
    onView,
    onEdit,
}: {
    rubric: RubricListItem;
    onSelect: () => void;
    onView: () => void;
    onEdit: () => void;
}) {
    const [showMenu, setShowMenu] = useState(false);

    const questionCount = rubric.rubric_json?.questions?.length || 0;
    const criteriaCount = rubric.rubric_json?.questions?.reduce((acc, q) => {
        let count = q.criteria?.length || 0;
        if (q.sub_questions) {
            count += q.sub_questions.reduce((sqAcc, sq) => sqAcc + (sq.criteria?.length || 0), 0);
        }
        return acc + count;
    }, 0) || 0;

    const formatDate = (dateStr: string) => {
        const date = new Date(dateStr);
        return date.toLocaleDateString('he-IL', {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
        });
    };

    return (
        <div className="bg-white rounded-xl border border-surface-200 p-5 hover:border-primary-300 hover:shadow-lg transition-all group">
            <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary-100 flex items-center justify-center">
                        <BookOpen size={20} className="text-primary-600" />
                    </div>
                    <div>
                        <h3 className="font-semibold text-gray-900 group-hover:text-primary-700 transition-colors">
                            {rubric.name || 'מחוון ללא שם'}
                        </h3>
                        <p className="text-xs text-gray-500 flex items-center gap-1 mt-0.5">
                            <Calendar size={12} />
                            {formatDate(rubric.created_at)}
                        </p>
                    </div>
                </div>

                <div className="relative">
                    <button
                        onClick={(e) => { e.stopPropagation(); setShowMenu(!showMenu); }}
                        className="p-1.5 text-gray-400 hover:text-gray-600 hover:bg-surface-100 rounded-lg opacity-0 group-hover:opacity-100 transition-all"
                    >
                        <MoreVertical size={18} />
                    </button>

                    {showMenu && (
                        <div className="absolute left-0 top-8 w-40 bg-white rounded-lg shadow-xl border border-surface-200 py-1 z-10">
                            <button
                                onClick={() => { setShowMenu(false); onView(); }}
                                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-surface-50"
                            >
                                <Eye size={14} />
                                צפייה
                            </button>
                            <button
                                onClick={() => { setShowMenu(false); onEdit(); }}
                                className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-surface-50"
                            >
                                <Edit size={14} />
                                עריכה
                            </button>
                            <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-gray-700 hover:bg-surface-50">
                                <Share2 size={14} />
                                שיתוף
                            </button>
                            <hr className="my-1 border-surface-200" />
                            <button className="flex items-center gap-2 w-full px-3 py-2 text-sm text-red-600 hover:bg-red-50">
                                <Trash2 size={14} />
                                מחיקה
                            </button>
                        </div>
                    )}
                </div>
            </div>

            {rubric.description && (
                <p className="text-sm text-gray-600 mb-3 line-clamp-2">{rubric.description}</p>
            )}

            <div className="flex items-center gap-4 text-xs text-gray-500">
                <span className="flex items-center gap-1">
                    <FileText size={12} />
                    {questionCount} שאלות
                </span>
                <span className="flex items-center gap-1">
                    <BookOpen size={12} />
                    {criteriaCount} קריטריונים
                </span>
                <span className="font-medium text-primary-600">
                    {rubric.total_points || 0} נק׳
                </span>
            </div>

            <div className="mt-4 pt-3 border-t border-surface-100">
                <button
                    onClick={onSelect}
                    className="w-full py-2 text-sm font-medium text-primary-600 hover:text-primary-700 hover:bg-primary-50 rounded-lg transition-colors"
                >
                    בדקי מבחנים עם מחוון זה
                </button>
            </div>
        </div>
    );
}

// Main Page Component
export default function MyRubricsPage() {
    const [rubrics, setRubrics] = useState<RubricListItem[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [searchQuery, setSearchQuery] = useState('');
    const [error, setError] = useState<string | null>(null);

    // View/Edit modal state
    const [selectedRubric, setSelectedRubric] = useState<RubricListItem | null>(null);
    const [isEditing, setIsEditing] = useState(false);
    const [editedQuestions, setEditedQuestions] = useState<ExtractedQuestion[]>([]);
    const [editedName, setEditedName] = useState('');
    const [editedDescription, setEditedDescription] = useState('');
    const [isSaving, setIsSaving] = useState(false);
    const [isLoadingRubric, setIsLoadingRubric] = useState(false);

    useEffect(() => {
        const fetchRubrics = async () => {
            try {
                setIsLoading(true);
                setError(null);
                const data = await listRubrics();
                setRubrics(data);
            } catch (err) {
                console.error('Failed to fetch rubrics:', err);
                setError('שגיאה בטעינת המחוונים');
            } finally {
                setIsLoading(false);
            }
        };

        fetchRubrics();
    }, []);

    const handleViewRubric = async (rubric: RubricListItem) => {
        try {
            setIsLoadingRubric(true);
            const fullRubric = await getRubric(rubric.id);
            setSelectedRubric(fullRubric);
            setIsEditing(false);
            setEditedQuestions(fullRubric.rubric_json?.questions || []);
            setEditedName(fullRubric.name || '');
            setEditedDescription(fullRubric.description || '');
        } catch (err) {
            console.error('Failed to fetch rubric:', err);
            setError('שגיאה בטעינת המחוון');
        } finally {
            setIsLoadingRubric(false);
        }
    };

    const handleEditRubric = async (rubric: RubricListItem) => {
        try {
            setIsLoadingRubric(true);
            const fullRubric = await getRubric(rubric.id);
            setSelectedRubric(fullRubric);
            setIsEditing(true);
            setEditedQuestions(fullRubric.rubric_json?.questions || []);
            setEditedName(fullRubric.name || '');
            setEditedDescription(fullRubric.description || '');
        } catch (err) {
            console.error('Failed to fetch rubric:', err);
            setError('שגיאה בטעינת המחוון');
        } finally {
            setIsLoadingRubric(false);
        }
    };

    const handleSaveRubric = async () => {
        if (!selectedRubric) return;

        try {
            setIsSaving(true);
            const updated = await updateRubric(selectedRubric.id, {
                name: editedName,
                description: editedDescription,
                questions: editedQuestions,
            });

            // Update local state
            setRubrics(prev => prev.map(r => r.id === updated.id ? updated : r));
            setSelectedRubric(updated);
            setIsEditing(false);
        } catch (err) {
            console.error('Failed to save rubric:', err);
            setError('שגיאה בשמירת המחוון');
        } finally {
            setIsSaving(false);
        }
    };

    const handleCloseModal = () => {
        setSelectedRubric(null);
        setIsEditing(false);
    };

    const filteredRubrics = rubrics.filter(r =>
        r.name?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        r.description?.toLowerCase().includes(searchQuery.toLowerCase())
    );

    // View/Edit Modal
    if (selectedRubric) {
        return (
            <SidebarLayout>
                <div className="max-w-6xl mx-auto">
                    {/* Header */}
                    <div className="flex items-center justify-between mb-6">
                        <div className="flex items-center gap-4">
                            <button
                                onClick={handleCloseModal}
                                className="flex items-center gap-2 text-gray-500 hover:text-gray-700 transition-colors"
                            >
                                <ArrowRight size={18} />
                                חזרה לרשימה
                            </button>
                            <div className="h-6 w-px bg-gray-300" />
                            <h1 className="text-xl font-bold text-gray-900">
                                {isEditing ? 'עריכת מחוון' : 'צפייה במחוון'}
                            </h1>
                        </div>

                        <div className="flex items-center gap-3">
                            {isEditing ? (
                                <>
                                    <button
                                        onClick={() => setIsEditing(false)}
                                        className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
                                    >
                                        <X size={18} />
                                        ביטול
                                    </button>
                                    <button
                                        onClick={handleSaveRubric}
                                        disabled={isSaving}
                                        className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 transition-colors"
                                    >
                                        {isSaving ? (
                                            <Loader2 className="animate-spin" size={18} />
                                        ) : (
                                            <Save size={18} />
                                        )}
                                        שמור שינויים
                                    </button>
                                </>
                            ) : (
                                <button
                                    onClick={() => setIsEditing(true)}
                                    className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors"
                                >
                                    <Edit size={18} />
                                    ערוך מחוון
                                </button>
                            )}
                        </div>
                    </div>

                    {/* Name and Description */}
                    <div className="bg-white rounded-xl border border-surface-200 p-6 mb-6">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    שם המחוון
                                </label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        value={editedName}
                                        onChange={(e) => setEditedName(e.target.value)}
                                        className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                        placeholder="הזן שם למחוון..."
                                    />
                                ) : (
                                    <p className="text-gray-900 font-medium">{selectedRubric.name || 'ללא שם'}</p>
                                )}
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-2">
                                    תיאור
                                </label>
                                {isEditing ? (
                                    <input
                                        type="text"
                                        value={editedDescription}
                                        onChange={(e) => setEditedDescription(e.target.value)}
                                        className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
                                        placeholder="הזן תיאור..."
                                    />
                                ) : (
                                    <p className="text-gray-600">{selectedRubric.description || 'ללא תיאור'}</p>
                                )}
                            </div>
                        </div>

                        <div className="mt-4 pt-4 border-t border-surface-100 flex items-center gap-6 text-sm text-gray-500">
                            <span>סה״כ נקודות: <strong className="text-primary-600">{selectedRubric.total_points}</strong></span>
                            <span>שאלות: <strong>{editedQuestions.length}</strong></span>
                        </div>
                    </div>

                    {/* Rubric Editor */}
                    <div className="bg-white rounded-xl border border-surface-200 p-6">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4">שאלות וקריטריונים</h2>
                        {isEditing ? (
                            <RubricEditor
                                questions={editedQuestions}
                                onQuestionsChange={setEditedQuestions}
                            />
                        ) : (
                            <RubricEditor
                                questions={editedQuestions}
                                onQuestionsChange={() => { }} // Read-only
                            />
                        )}
                    </div>
                </div>
            </SidebarLayout>
        );
    }

    return (
        <SidebarLayout>
            <div className="max-w-6xl mx-auto">
                {/* Loading overlay */}
                {isLoadingRubric && (
                    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50">
                        <div className="bg-white rounded-xl p-6 flex items-center gap-3">
                            <Loader2 className="animate-spin text-primary-500" size={24} />
                            <span>טוען מחוון...</span>
                        </div>
                    </div>
                )}

                {/* Page Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900">המחוונים שלי</h1>
                        <p className="text-gray-500 mt-1">צפה ונהל את כל המחוונים שיצרת</p>
                    </div>
                    <Link
                        href="/"
                        className="inline-flex items-center gap-2 bg-primary-500 text-white px-4 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium"
                    >
                        <Plus size={18} />
                        צרי מחוון חדש
                    </Link>
                </div>

                {/* Search and Filter */}
                <div className="bg-white rounded-xl border border-surface-200 p-4 mb-6">
                    <div className="relative">
                        <Search className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400" size={18} />
                        <input
                            type="text"
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            placeholder="חפש לפי שם או תיאור..."
                            className="w-full pr-10 pl-4 py-2.5 border border-surface-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        />
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
                ) : filteredRubrics.length === 0 ? (
                    <div className="bg-white rounded-xl border border-surface-200 p-12 text-center">
                        <BookOpen className="mx-auto text-gray-300 mb-4" size={48} />
                        <h3 className="text-lg font-medium text-gray-700 mb-2">
                            {searchQuery ? 'לא נמצאו תוצאות' : 'אין מחוונים עדיין'}
                        </h3>
                        <p className="text-gray-500 mb-4">
                            {searchQuery
                                ? 'נסה לחפש במילים אחרות'
                                : 'צור את המחוון הראשון שלך כדי להתחיל לבדוק מבחנים'
                            }
                        </p>
                        {!searchQuery && (
                            <Link
                                href="/"
                                className="inline-flex items-center gap-2 bg-primary-500 text-white px-4 py-2 rounded-lg hover:bg-primary-600 transition-colors"
                            >
                                <Plus size={18} />
                                צור מחוון חדש
                            </Link>
                        )}
                    </div>
                ) : (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredRubrics.map((rubric) => (
                            <RubricCard
                                key={rubric.id}
                                rubric={rubric}
                                onSelect={() => {
                                    window.location.href = `/?rubric=${rubric.id}`;
                                }}
                                onView={() => handleViewRubric(rubric)}
                                onEdit={() => handleEditRubric(rubric)}
                            />
                        ))}
                    </div>
                )}

                {/* Stats Footer */}
                {!isLoading && filteredRubrics.length > 0 && (
                    <div className="mt-6 text-center text-sm text-gray-500">
                        מציג {filteredRubrics.length} מתוך {rubrics.length} מחוונים
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
