'use client';

import { useState, useEffect, useCallback } from 'react';
import {
    Users,
    BookOpen,
    Plus,
    Pencil,
    Trash2,
    Loader2,
    AlertCircle,
    X,
    Check,
    GraduationCap,
    UserPlus,
} from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { StudentPicker } from '@/components/StudentPicker';
import {
    listStudents,
    listClasses,
    getClassDetail,
    createStudent,
    updateStudent,
    deleteStudent,
    createClass,
    updateClass,
    deleteClass,
    addStudentToClass,
    removeStudentFromClass,
    listSubjectMatters,
    ClassroomConflictError,
} from '@/lib/api';
import type {
    StudentResponse,
    ClassResponse,
    ClassDetailResponse,
    SubjectMatterOption,
} from '@/types/classroom';

// ---------------------------------------------------------------------------
// Shared helpers
// ---------------------------------------------------------------------------

function InlineError({ message, onClose }: { message: string; onClose?: () => void }) {
    return (
        <div className="flex items-center gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            <AlertCircle size={16} className="shrink-0" />
            <span className="flex-1">{message}</span>
            {onClose && (
                <button onClick={onClose} className="text-red-400 hover:text-red-600">
                    <X size={14} />
                </button>
            )}
        </div>
    );
}

function ConfirmDialog({
    title,
    body,
    confirmLabel,
    onConfirm,
    onCancel,
    loading,
    error,
}: {
    title: string;
    body: string;
    confirmLabel: string;
    onConfirm: () => void;
    onCancel: () => void;
    loading?: boolean;
    error?: string | null;
}) {
    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full">
                <h3 className="font-semibold text-gray-900 mb-2 text-right">{title}</h3>
                <p className="text-gray-600 text-sm mb-4 text-right">{body}</p>
                {error && <InlineError message={error} />}
                <div className="flex gap-3 justify-end mt-4">
                    <button
                        onClick={onCancel}
                        disabled={loading}
                        className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50"
                    >
                        ביטול
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={loading}
                        className="px-4 py-2 text-sm bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 flex items-center gap-2"
                    >
                        {loading && <Loader2 size={14} className="animate-spin" />}
                        {confirmLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Students tab
// ---------------------------------------------------------------------------

function StudentsTab() {
    const [students, setStudents] = useState<StudentResponse[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Create modal
    const [showCreate, setShowCreate] = useState(false);
    const [createName, setCreateName] = useState('');
    const [createNotes, setCreateNotes] = useState('');
    const [createError, setCreateError] = useState<string | null>(null);
    const [createLoading, setCreateLoading] = useState(false);

    // Edit modal
    const [editStudent, setEditStudent] = useState<StudentResponse | null>(null);
    const [editName, setEditName] = useState('');
    const [editNotes, setEditNotes] = useState('');
    const [editError, setEditError] = useState<string | null>(null);
    const [editLoading, setEditLoading] = useState(false);

    // Delete confirm
    const [deleteTarget, setDeleteTarget] = useState<StudentResponse | null>(null);
    const [deleteLoading, setDeleteLoading] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const r = await listStudents();
            setStudents(r.students);
        } catch {
            setError('שגיאה בטעינת התלמידים');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        if (!createName.trim()) return;
        setCreateLoading(true);
        setCreateError(null);
        try {
            const s = await createStudent({ full_name: createName.trim(), notes: createNotes.trim() || undefined });
            setStudents(prev => [...prev, s].sort((a, b) => a.full_name.localeCompare(b.full_name, 'he')));
            setShowCreate(false);
            setCreateName('');
            setCreateNotes('');
        } catch (err) {
            setCreateError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה ביצירת התלמיד');
        } finally {
            setCreateLoading(false);
        }
    };

    const handleEdit = async () => {
        if (!editStudent || !editName.trim()) return;
        setEditLoading(true);
        setEditError(null);
        try {
            const updated = await updateStudent(editStudent.id, {
                full_name: editName.trim(),
                notes: editNotes.trim() || undefined,
            });
            setStudents(prev => prev.map(s => s.id === updated.id ? updated : s));
            setEditStudent(null);
        } catch (err) {
            setEditError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה בעדכון התלמיד');
        } finally {
            setEditLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleteLoading(true);
        setDeleteError(null);
        try {
            await deleteStudent(deleteTarget.id);
            setStudents(prev => prev.filter(s => s.id !== deleteTarget.id));
            setDeleteTarget(null);
        } catch (err) {
            setDeleteError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה במחיקת התלמיד');
        } finally {
            setDeleteLoading(false);
        }
    };

    if (loading) return (
        <div className="flex justify-center py-16">
            <Loader2 className="animate-spin text-primary-500" size={32} />
        </div>
    );

    if (error) return <InlineError message={error} />;

    return (
        <div>
            <div className="flex items-center justify-between mb-4">
                <span className="text-sm text-gray-500">{students.length} תלמידים</span>
                <button
                    onClick={() => { setShowCreate(true); setCreateName(''); setCreateNotes(''); setCreateError(null); }}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors text-sm font-medium"
                >
                    <Plus size={16} />
                    תלמיד חדש
                </button>
            </div>

            {students.length === 0 ? (
                <div className="text-center py-16 text-gray-400">
                    <Users size={48} className="mx-auto mb-3 opacity-30" />
                    <p className="text-lg font-medium mb-1">אין תלמידים עדיין</p>
                    <p className="text-sm">לחץ על "תלמיד חדש" להוספת תלמיד</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {students.map(s => (
                        <div key={s.id} className="bg-white rounded-xl border border-surface-200 px-5 py-4 flex items-center gap-4">
                            <div className="w-9 h-9 rounded-full bg-primary-100 flex items-center justify-center shrink-0">
                                <Users size={16} className="text-primary-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-gray-900 truncate">{s.full_name}</p>
                                {s.notes && <p className="text-xs text-gray-500 truncate">{s.notes}</p>}
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => { setEditStudent(s); setEditName(s.full_name); setEditNotes(s.notes ?? ''); setEditError(null); }}
                                    className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                    title="עריכה"
                                >
                                    <Pencil size={16} />
                                </button>
                                <button
                                    onClick={() => { setDeleteTarget(s); setDeleteError(null); }}
                                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                    title="מחיקה"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Create modal */}
            {showCreate && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-4">
                            <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
                            <h2 className="font-semibold text-gray-900">הוספת תלמיד</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שם מלא *</label>
                                <input
                                    type="text"
                                    value={createName}
                                    onChange={e => setCreateName(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleCreate()}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    placeholder="שם התלמיד"
                                    dir="rtl"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">הערות</label>
                                <textarea
                                    value={createNotes}
                                    onChange={e => setCreateNotes(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right resize-none"
                                    rows={2}
                                    placeholder="הערות אופציונליות"
                                    dir="rtl"
                                />
                            </div>
                            {createError && <InlineError message={createError} onClose={() => setCreateError(null)} />}
                        </div>
                        <div className="flex gap-3 justify-start mt-5">
                            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50">ביטול</button>
                            <button
                                onClick={handleCreate}
                                disabled={createLoading || !createName.trim()}
                                className="px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
                            >
                                {createLoading && <Loader2 size={14} className="animate-spin" />}
                                הוסף
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit modal */}
            {editStudent && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-4">
                            <button onClick={() => setEditStudent(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
                            <h2 className="font-semibold text-gray-900">עריכת תלמיד</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שם מלא *</label>
                                <input
                                    type="text"
                                    value={editName}
                                    onChange={e => setEditName(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleEdit()}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    dir="rtl"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">הערות</label>
                                <textarea
                                    value={editNotes}
                                    onChange={e => setEditNotes(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right resize-none"
                                    rows={2}
                                    dir="rtl"
                                />
                            </div>
                            {editError && <InlineError message={editError} onClose={() => setEditError(null)} />}
                        </div>
                        <div className="flex gap-3 justify-start mt-5">
                            <button onClick={() => setEditStudent(null)} className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50">ביטול</button>
                            <button
                                onClick={handleEdit}
                                disabled={editLoading || !editName.trim()}
                                className="px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
                            >
                                {editLoading && <Loader2 size={14} className="animate-spin" />}
                                שמור
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete confirm */}
            {deleteTarget && (
                <ConfirmDialog
                    title="מחיקת תלמיד"
                    body={`האם למחוק את "${deleteTarget.full_name}"? פעולה זו אינה הפיכה.`}
                    confirmLabel="מחק"
                    onConfirm={handleDelete}
                    onCancel={() => setDeleteTarget(null)}
                    loading={deleteLoading}
                    error={deleteError}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Manage students modal (for a specific class)
// ---------------------------------------------------------------------------

function ManageStudentsModal({
    classItem,
    onClose,
}: {
    classItem: ClassResponse;
    onClose: () => void;
}) {
    const [classDetail, setClassDetail] = useState<ClassDetailResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [addingId, setAddingId] = useState<string | null>(null);
    const [removingId, setRemovingId] = useState<string | null>(null);
    const [actionError, setActionError] = useState<string | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        try {
            const d = await getClassDetail(classItem.id);
            setClassDetail(d);
        } catch {
            setError('שגיאה בטעינת פרטי הכיתה');
        } finally {
            setLoading(false);
        }
    }, [classItem.id]);

    useEffect(() => { load(); }, [load]);

    const handleAdd = async (studentId: string) => {
        setAddingId(studentId);
        setActionError(null);
        try {
            await addStudentToClass(classItem.id, studentId);
            await load();
        } catch (err) {
            setActionError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה בהוספת התלמיד');
        } finally {
            setAddingId(null);
        }
    };

    const handleRemove = async (studentId: string) => {
        setRemovingId(studentId);
        setActionError(null);
        try {
            await removeStudentFromClass(classItem.id, studentId);
            await load();
        } catch {
            setActionError('שגיאה בהסרת התלמיד');
        } finally {
            setRemovingId(null);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl p-6 max-w-lg w-full max-h-[80vh] flex flex-col">
                <div className="flex items-center justify-between mb-4 shrink-0">
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
                    <h2 className="font-semibold text-gray-900">ניהול תלמידים — {classItem.name}</h2>
                </div>

                {loading ? (
                    <div className="flex justify-center py-8"><Loader2 className="animate-spin text-primary-500" size={28} /></div>
                ) : error ? (
                    <InlineError message={error} />
                ) : (
                    <div className="flex-1 overflow-y-auto space-y-4">
                        {/* Add student */}
                        <div>
                            <p className="text-sm font-medium text-gray-700 mb-2 text-right">הוסף תלמיד לכיתה</p>
                            <StudentPicker
                                value={null}
                                onChange={handleAdd}
                                placeholder="חפש או צור תלמיד..."
                            />
                            {addingId && (
                                <div className="flex items-center gap-2 mt-2 text-sm text-gray-500">
                                    <Loader2 size={14} className="animate-spin" /> מוסיף...
                                </div>
                            )}
                        </div>

                        {actionError && <InlineError message={actionError} onClose={() => setActionError(null)} />}

                        {/* Current members */}
                        <div>
                            <p className="text-sm font-medium text-gray-700 mb-2 text-right">
                                תלמידים בכיתה ({classDetail?.students.length ?? 0})
                            </p>
                            {classDetail?.students.length === 0 ? (
                                <p className="text-sm text-gray-400 text-right">אין תלמידים בכיתה עדיין</p>
                            ) : (
                                <div className="space-y-1">
                                    {classDetail?.students.map(s => (
                                        <div key={s.id} className="flex items-center gap-3 px-3 py-2 bg-surface-50 rounded-lg">
                                            <button
                                                onClick={() => handleRemove(s.id)}
                                                disabled={removingId === s.id}
                                                className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                                                title="הסר מהכיתה"
                                            >
                                                {removingId === s.id
                                                    ? <Loader2 size={14} className="animate-spin" />
                                                    : <X size={14} />
                                                }
                                            </button>
                                            <span className="text-sm text-gray-800 flex-1 text-right">{s.full_name}</span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Classes tab
// ---------------------------------------------------------------------------

function ClassesTab() {
    const [classes, setClasses] = useState<ClassResponse[]>([]);
    const [subjectMatters, setSubjectMatters] = useState<SubjectMatterOption[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [showCreate, setShowCreate] = useState(false);
    const [createName, setCreateName] = useState('');
    const [createSubject, setCreateSubject] = useState<number | ''>('');
    const [createYear, setCreateYear] = useState('');
    const [createError, setCreateError] = useState<string | null>(null);
    const [createLoading, setCreateLoading] = useState(false);

    const [editClass, setEditClass] = useState<ClassResponse | null>(null);
    const [editName, setEditName] = useState('');
    const [editSubject, setEditSubject] = useState<number | ''>('');
    const [editYear, setEditYear] = useState('');
    const [editError, setEditError] = useState<string | null>(null);
    const [editLoading, setEditLoading] = useState(false);

    const [deleteTarget, setDeleteTarget] = useState<ClassResponse | null>(null);
    const [deleteLoading, setDeleteLoading] = useState(false);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const [manageClass, setManageClass] = useState<ClassResponse | null>(null);

    const load = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const [classesRes, subjectsRes] = await Promise.all([listClasses(), listSubjectMatters()]);
            setClasses(classesRes.classes);
            setSubjectMatters(subjectsRes);
        } catch {
            setError('שגיאה בטעינת הכיתות');
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => { load(); }, [load]);

    const handleCreate = async () => {
        if (!createName.trim()) return;
        setCreateLoading(true);
        setCreateError(null);
        try {
            const c = await createClass({
                name: createName.trim(),
                subject_matter_id: createSubject !== '' ? createSubject : undefined,
                school_year: createYear.trim() || undefined,
            });
            setClasses(prev => [...prev, c].sort((a, b) => a.name.localeCompare(b.name, 'he')));
            setShowCreate(false);
            setCreateName(''); setCreateSubject(''); setCreateYear('');
        } catch (err) {
            setCreateError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה ביצירת הכיתה');
        } finally {
            setCreateLoading(false);
        }
    };

    const handleEdit = async () => {
        if (!editClass || !editName.trim()) return;
        setEditLoading(true);
        setEditError(null);
        try {
            const updated = await updateClass(editClass.id, {
                name: editName.trim(),
                subject_matter_id: editSubject !== '' ? editSubject : null,
                school_year: editYear.trim() || undefined,
            });
            setClasses(prev => prev.map(c => c.id === updated.id ? updated : c));
            setEditClass(null);
        } catch (err) {
            setEditError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה בעדכון הכיתה');
        } finally {
            setEditLoading(false);
        }
    };

    const handleDelete = async () => {
        if (!deleteTarget) return;
        setDeleteLoading(true);
        setDeleteError(null);
        try {
            await deleteClass(deleteTarget.id);
            setClasses(prev => prev.filter(c => c.id !== deleteTarget.id));
            setDeleteTarget(null);
        } catch (err) {
            setDeleteError(err instanceof ClassroomConflictError ? err.detail : 'שגיאה במחיקת הכיתה');
        } finally {
            setDeleteLoading(false);
        }
    };

    if (loading) return (
        <div className="flex justify-center py-16">
            <Loader2 className="animate-spin text-primary-500" size={32} />
        </div>
    );

    if (error) return <InlineError message={error} />;

    const SubjectSelect = ({ value, onChange }: { value: number | ''; onChange: (v: number | '') => void }) => (
        <select
            value={value}
            onChange={e => onChange(e.target.value === '' ? '' : parseInt(e.target.value))}
            className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right bg-white"
            dir="rtl"
        >
            <option value="">ללא מקצוע</option>
            {subjectMatters.map(sm => (
                <option key={sm.id} value={sm.id}>{sm.name_he}</option>
            ))}
        </select>
    );

    return (
        <div>
            <div className="flex items-center justify-between mb-4">
                <span className="text-sm text-gray-500">{classes.length} הכיתות</span>
                <button
                    onClick={() => { setShowCreate(true); setCreateName(''); setCreateSubject(''); setCreateYear(''); setCreateError(null); }}
                    className="flex items-center gap-2 px-4 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors text-sm font-medium"
                >
                    <Plus size={16} />
                    כיתה חדשה
                </button>
            </div>

            {classes.length === 0 ? (
                <div className="text-center py-16 text-gray-400">
                    <GraduationCap size={48} className="mx-auto mb-3 opacity-30" />
                    <p className="text-lg font-medium mb-1">אין כיתות עדיין</p>
                    <p className="text-sm">לחץ על "כיתה חדשה" להוספת כיתה</p>
                </div>
            ) : (
                <div className="space-y-2">
                    {classes.map(c => (
                        <div key={c.id} className="bg-white rounded-xl border border-surface-200 px-5 py-4 flex items-center gap-4">
                            <div className="w-9 h-9 rounded-lg bg-primary-100 flex items-center justify-center shrink-0">
                                <GraduationCap size={16} className="text-primary-600" />
                            </div>
                            <div className="flex-1 min-w-0">
                                <p className="font-medium text-gray-900 truncate">{c.name}</p>
                                <div className="flex items-center gap-3 mt-0.5">
                                    {c.subject_matter_name && (
                                        <span className="text-xs text-gray-500">{c.subject_matter_name}</span>
                                    )}
                                    {c.school_year && (
                                        <span className="text-xs text-gray-500">{c.school_year}</span>
                                    )}
                                    <span className="text-xs text-gray-500">{c.student_count} תלמידים</span>
                                </div>
                            </div>
                            <div className="flex items-center gap-2">
                                <button
                                    onClick={() => setManageClass(c)}
                                    className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                    title="ניהול תלמידים"
                                >
                                    <UserPlus size={16} />
                                </button>
                                <button
                                    onClick={() => { setEditClass(c); setEditName(c.name); setEditSubject(c.subject_matter_id ?? ''); setEditYear(c.school_year ?? ''); setEditError(null); }}
                                    className="p-2 text-gray-400 hover:text-primary-600 hover:bg-primary-50 rounded-lg transition-colors"
                                    title="עריכה"
                                >
                                    <Pencil size={16} />
                                </button>
                                <button
                                    onClick={() => { setDeleteTarget(c); setDeleteError(null); }}
                                    className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                                    title="מחיקה"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Create modal */}
            {showCreate && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-4">
                            <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
                            <h2 className="font-semibold text-gray-900">הוספת כיתה</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שם הכיתה *</label>
                                <input
                                    type="text"
                                    value={createName}
                                    onChange={e => setCreateName(e.target.value)}
                                    onKeyDown={e => e.key === 'Enter' && handleCreate()}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    placeholder="לדוגמה: י׳1"
                                    dir="rtl"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">מקצוע</label>
                                <SubjectSelect value={createSubject} onChange={setCreateSubject} />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שנת לימודים</label>
                                <input
                                    type="text"
                                    value={createYear}
                                    onChange={e => setCreateYear(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    placeholder="לדוגמה: 2024-2025"
                                    dir="rtl"
                                />
                            </div>
                            {createError && <InlineError message={createError} onClose={() => setCreateError(null)} />}
                        </div>
                        <div className="flex gap-3 justify-start mt-5">
                            <button onClick={() => setShowCreate(false)} className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50">ביטול</button>
                            <button
                                onClick={handleCreate}
                                disabled={createLoading || !createName.trim()}
                                className="px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
                            >
                                {createLoading && <Loader2 size={14} className="animate-spin" />}
                                הוסף
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit modal */}
            {editClass && (
                <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
                    <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full">
                        <div className="flex items-center justify-between mb-4">
                            <button onClick={() => setEditClass(null)} className="text-gray-400 hover:text-gray-600"><X size={20} /></button>
                            <h2 className="font-semibold text-gray-900">עריכת כיתה</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שם הכיתה *</label>
                                <input
                                    type="text"
                                    value={editName}
                                    onChange={e => setEditName(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    dir="rtl"
                                    autoFocus
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">מקצוע</label>
                                <SubjectSelect value={editSubject} onChange={setEditSubject} />
                            </div>
                            <div>
                                <label className="block text-sm font-medium text-gray-700 mb-1 text-right">שנת לימודים</label>
                                <input
                                    type="text"
                                    value={editYear}
                                    onChange={e => setEditYear(e.target.value)}
                                    className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                    dir="rtl"
                                />
                            </div>
                            {editError && <InlineError message={editError} onClose={() => setEditError(null)} />}
                        </div>
                        <div className="flex gap-3 justify-start mt-5">
                            <button onClick={() => setEditClass(null)} className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50">ביטול</button>
                            <button
                                onClick={handleEdit}
                                disabled={editLoading || !editName.trim()}
                                className="px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
                            >
                                {editLoading && <Loader2 size={14} className="animate-spin" />}
                                שמור
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Delete confirm */}
            {deleteTarget && (
                <ConfirmDialog
                    title="מחיקת כיתה"
                    body={`האם למחוק את "${deleteTarget.name}"? פעולה זו אינה הפיכה.`}
                    confirmLabel="מחק"
                    onConfirm={handleDelete}
                    onCancel={() => setDeleteTarget(null)}
                    loading={deleteLoading}
                    error={deleteError}
                />
            )}

            {/* Manage students modal */}
            {manageClass && (
                <ManageStudentsModal
                    classItem={manageClass}
                    onClose={() => { setManageClass(null); load(); }}
                />
            )}
        </div>
    );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

type Tab = 'students' | 'classes';

export default function MyClassroomPage() {
    const [activeTab, setActiveTab] = useState<Tab>('students');

    return (
        <SidebarLayout>
            <div className="max-w-4xl mx-auto" dir="rtl">
                {/* Page header */}
                <div className="mb-6">
                    <div className="flex items-center gap-3 mb-1">
                        <div className="w-10 h-10 rounded-xl bg-primary-100 flex items-center justify-center">
                            <GraduationCap size={22} className="text-primary-600" />
                        </div>
                        <h1 className="text-2xl font-bold text-gray-900">הכיתות שלי</h1>
                    </div>
                    <p className="text-gray-500 text-sm mr-13">ניהול תלמידים וכיתות</p>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 mb-6 bg-surface-100 rounded-xl p-1 w-fit">
                    <button
                        onClick={() => setActiveTab('students')}
                        className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                            activeTab === 'students'
                                ? 'bg-white text-primary-700 shadow-sm'
                                : 'text-gray-600 hover:text-gray-900'
                        }`}
                    >
                        <Users size={16} />
                        תלמידים
                    </button>
                    <button
                        onClick={() => setActiveTab('classes')}
                        className={`flex items-center gap-2 px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                            activeTab === 'classes'
                                ? 'bg-white text-primary-700 shadow-sm'
                                : 'text-gray-600 hover:text-gray-900'
                        }`}
                    >
                        <GraduationCap size={16} />
                        כיתות
                    </button>
                </div>

                {/* Tab content */}
                {activeTab === 'students' ? <StudentsTab /> : <ClassesTab />}
            </div>
        </SidebarLayout>
    );
}
