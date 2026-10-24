'use client';

/**
 * StudentPicker — reusable, standalone component.
 *
 * Lets a caller select an existing student from the teacher's roster
 * or create a new one inline.  Talks only to student endpoints.
 * No transcription/grading dependencies — drop-in reusable in S4.
 */

import { useState, useEffect, useRef } from 'react';
import { Search, Plus, Loader2, AlertCircle, Check, Sparkles } from 'lucide-react';
import { listStudents, createStudent, ClassroomConflictError } from '@/lib/api';
import { nameMatchesQuery } from '@/utils/batch-partition';

/** What the picker lists and creates through. The default is the classroom
 *  API; the capture page on a phone (a capture session, which the classroom
 *  API rejects) injects its own (§8.3). */
export interface StudentSource {
    list(): Promise<{ id: string; full_name: string }[]>;
    /** Throw an Error whose message is the Hebrew line to show. */
    create(name: string): Promise<{ id: string; full_name: string }>;
}

const CLASSROOM_SOURCE: StudentSource = {
    list: async () => (await listStudents()).students,
    create: async (name) => {
        try {
            return await createStudent({ full_name: name });
        } catch (err) {
            throw new Error(err instanceof ClassroomConflictError ? err.detail : 'שגיאה ביצירת התלמיד');
        }
    },
};

type StudentResponse = { id: string; full_name: string };

export interface StudentPickerProps {
    value: string | null;
    onChange: (studentId: string) => void;
    placeholder?: string;
    disabled?: boolean;
    /**
     * Identity-pass hint (B-25, 2026-08-12): pre-seeds the SEARCH text so an
     * unmatched suggested name is one click away — "צור תלמיד חדש" creates
     * the student with this name and assigns immediately. Seeding is display
     * state only, never a selection (Δ14: viewing is not commitment).
     */
    suggestedName?: string | null;
    /** [036] Where to list and create — defaults to the classroom API. */
    source?: StudentSource;
    /** [036] A roster match a name reader proposed: shown FIRST, marked, one
     *  click to choose. Never selected for her (OD-S4: a human click). */
    suggestedMatch?: { id: string; name: string } | null;
    suggestedMatchLabel?: (name: string) => string;
    /** [036] A line with a spinner while the suggestion is being read. */
    detecting?: boolean;
    detectingLabel?: string;
    /** [036] Open the list on mount (the teacher capture page). */
    autoOpen?: boolean;
}

export function StudentPicker({
    value, onChange, placeholder = 'חפש תלמיד...', disabled, suggestedName,
    source = CLASSROOM_SOURCE, suggestedMatch, suggestedMatchLabel, detecting, detectingLabel, autoOpen,
}: StudentPickerProps) {
    const [students, setStudents] = useState<StudentResponse[]>([]);
    const [loadingList, setLoadingList] = useState(true);
    const [listError, setListError] = useState<string | null>(null);

    const [query, setQuery] = useState((suggestedName ?? '').trim());
    const [isOpen, setIsOpen] = useState(!!autoOpen);
    useEffect(() => { if (autoOpen) setIsOpen(true); }, [autoOpen]);

    // Reactive seeding: the identity hint can arrive AFTER mount (async batch
    // payload / payload refresh), and initial state alone misses it — observed
    // live 2026-08-12 as an empty input beside a rendered suggestion label.
    // Reseed only while the teacher hasn't typed and no student is assigned
    // (Δ14: display state only, never a selection).
    const userTypedRef = useRef(false);
    useEffect(() => {
        const name = (suggestedName ?? '').trim();
        if (name && !value && !userTypedRef.current) setQuery(name);
    }, [suggestedName, value]);

    const [showCreateInput, setShowCreateInput] = useState(false);
    const [newName, setNewName] = useState('');
    const [creating, setCreating] = useState(false);
    const [createError, setCreateError] = useState<string | null>(null);

    const containerRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Load students on mount
    useEffect(() => {
        source.list()
            .then(list => setStudents(list))
            .catch(() => setListError('שגיאה בטעינת התלמידים'))
            .finally(() => setLoadingList(false));
    }, [source]);

    // Close dropdown on outside click
    useEffect(() => {
        function handle(e: MouseEvent) {
            if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
                setIsOpen(false);
                setShowCreateInput(false);
                setCreateError(null);
            }
        }
        document.addEventListener('mousedown', handle);
        return () => document.removeEventListener('mousedown', handle);
    }, []);

    const selectedStudent = students.find(s => s.id === value) ?? null;

    // The ONE name normalization (niqqud, geresh, case, token order) — the
    // same rule the server's auto-match uses.
    const filtered = students.filter(s => nameMatchesQuery(s.full_name, query)
        && s.id !== suggestedMatch?.id);

    const handleSelect = (student: StudentResponse) => {
        onChange(student.id);
        setQuery('');
        setIsOpen(false);
        setShowCreateInput(false);
        setCreateError(null);
    };

    const createAndAssign = async (name: string): Promise<boolean> => {
        if (!name.trim()) return false;
        setCreating(true);
        setCreateError(null);
        try {
            const created = await source.create(name.trim());
            setStudents(prev => [...prev, created].sort((a, b) => a.full_name.localeCompare(b.full_name, 'he')));
            onChange(created.id);
            setNewName('');
            setQuery('');
            setShowCreateInput(false);
            setIsOpen(false);
            return true;
        } catch (err) {
            setCreateError(err instanceof Error && err.message ? err.message : 'שגיאה ביצירת התלמיד');
            return false;
        } finally {
            setCreating(false);
        }
    };

    const handleCreateSubmit = () => void createAndAssign(newName);

    // One-click create (the identity-pass UX): a name already in the search
    // field creates+assigns directly; empty query opens the name input. On a
    // create error (e.g. name conflict) fall back to the input stage so the
    // teacher can adjust.
    const handleCreateAffordance = async () => {
        if (query.trim()) {
            const ok = await createAndAssign(query);
            if (!ok) {
                setShowCreateInput(true);
                setNewName(query);
            }
        } else {
            setShowCreateInput(true);
            setNewName(query);
            setCreateError(null);
        }
    };

    return (
        <div className="relative" ref={containerRef} dir="rtl">
            {/* Trigger / search input */}
            <div
                className={`flex items-center gap-2 w-full px-4 py-2.5 border rounded-lg bg-white cursor-text
                    ${isOpen ? 'border-primary-500 ring-2 ring-primary-500/20' : 'border-surface-300 hover:border-surface-400'}
                    ${disabled ? 'opacity-50 cursor-not-allowed bg-surface-50' : ''}
                `}
                onClick={() => {
                    if (!disabled) {
                        setIsOpen(true);
                        inputRef.current?.focus();
                    }
                }}
            >
                <Search size={16} className="text-gray-400 shrink-0" />
                <input
                    ref={inputRef}
                    type="text"
                    value={isOpen ? query : (selectedStudent?.full_name ?? query)}
                    onChange={e => { userTypedRef.current = true; setQuery(e.target.value); setIsOpen(true); }}
                    onFocus={() => { if (!disabled) setIsOpen(true); }}
                    placeholder={selectedStudent ? selectedStudent.full_name : placeholder}
                    className="flex-1 outline-none text-sm bg-transparent text-right"
                    disabled={disabled}
                    readOnly={!isOpen}
                />
                {selectedStudent && !isOpen && (
                    <span className="text-primary-600 shrink-0"><Check size={14} /></span>
                )}
            </div>

            {/* Dropdown */}
            {isOpen && !disabled && (
                <div className="absolute top-full right-0 left-0 mt-1 bg-white border border-surface-200 rounded-xl shadow-xl z-40 max-h-64 overflow-y-auto">
                    {loadingList ? (
                        <div className="flex items-center justify-center py-6 gap-2 text-gray-400 text-sm">
                            <Loader2 size={16} className="animate-spin" /> טוען...
                        </div>
                    ) : listError ? (
                        <div className="flex items-center gap-2 px-4 py-3 text-red-600 text-sm">
                            <AlertCircle size={14} /> {listError}
                        </div>
                    ) : (
                        <>
                            {detecting && (
                                <div className="flex items-center gap-2 px-4 py-2.5 text-sm text-gray-500" role="status">
                                    <Loader2 size={14} className="animate-spin shrink-0" />
                                    <span>{detectingLabel}</span>
                                </div>
                            )}
                            {suggestedMatch && (
                                <button
                                    onClick={() => handleSelect({ id: suggestedMatch.id, full_name: suggestedMatch.name })}
                                    className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-right bg-primary-50 text-primary-800 font-medium hover:bg-primary-100 border-b border-primary-100"
                                    data-testid="picker-suggested-match"
                                >
                                    <Sparkles size={14} className="shrink-0" />
                                    <span className="flex-1 text-right">
                                        {suggestedMatchLabel ? suggestedMatchLabel(suggestedMatch.name) : suggestedMatch.name}
                                    </span>
                                </button>
                            )}
                            {filtered.length === 0 && !showCreateInput && !suggestedMatch && (
                                <p className="px-4 py-3 text-sm text-gray-400 text-right">
                                    {query ? 'לא נמצאו תלמידים תואמים' : 'אין תלמידים עדיין'}
                                </p>
                            )}

                            {filtered.map(s => (
                                <button
                                    key={s.id}
                                    onClick={() => handleSelect(s)}
                                    className={`flex items-center gap-2 w-full px-4 py-2.5 text-sm text-right hover:bg-surface-50 transition-colors
                                        ${s.id === value ? 'text-primary-700 font-medium' : 'text-gray-800'}
                                    `}
                                >
                                    {s.id === value && <Check size={14} className="text-primary-500 shrink-0" />}
                                    <span className="flex-1 text-right">{s.full_name}</span>
                                </button>
                            ))}

                            {/* Create new affordance */}
                            {!showCreateInput ? (
                                <button
                                    onClick={() => void handleCreateAffordance()}
                                    disabled={creating}
                                    className="flex items-center gap-2 w-full px-4 py-2.5 text-sm text-primary-600 hover:bg-primary-50 border-t border-surface-100 transition-colors disabled:opacity-50"
                                >
                                    {creating ? <Loader2 size={14} className="shrink-0 animate-spin" /> : <Plus size={14} className="shrink-0" />}
                                    <span>צור תלמיד חדש{query ? ` "${query}"` : ''}</span>
                                </button>
                            ) : (
                                <div className="border-t border-surface-100 p-3 space-y-2">
                                    <input
                                        type="text"
                                        value={newName}
                                        onChange={e => setNewName(e.target.value)}
                                        onKeyDown={e => { if (e.key === 'Enter') handleCreateSubmit(); if (e.key === 'Escape') { setShowCreateInput(false); setCreateError(null); } }}
                                        placeholder="שם התלמיד"
                                        className="w-full px-3 py-2 text-sm border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                                        dir="rtl"
                                        autoFocus
                                    />
                                    {createError && (
                                        <div className="flex items-center gap-1 text-red-600 text-xs">
                                            <AlertCircle size={12} /> {createError}
                                        </div>
                                    )}
                                    <div className="flex gap-2">
                                        <button
                                            onClick={() => { setShowCreateInput(false); setCreateError(null); }}
                                            className="flex-1 py-1.5 text-xs text-gray-600 border border-surface-300 rounded-lg hover:bg-surface-50"
                                        >
                                            ביטול
                                        </button>
                                        <button
                                            onClick={handleCreateSubmit}
                                            disabled={creating || !newName.trim()}
                                            className="flex-1 py-1.5 text-xs bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center justify-center gap-1"
                                        >
                                            {creating ? <Loader2 size={12} className="animate-spin" /> : <Plus size={12} />}
                                            צור
                                        </button>
                                    </div>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}
        </div>
    );
}
