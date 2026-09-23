'use client';

/**
 * The student purge's dialog (Part B §15) — the Delete artboard of
 * vivi-student-profile-mockup/: title · the body with the count in bold · the
 * labelled name input · «ביטול» / «מחיקה לצמיתות», the primary disabled until
 * the name is typed. Structure and copy from the artboard, tokens from the app.
 *
 * The case is the SERVER's (the purge preview), never guessed here. On
 * success the caller is told — the roster drops the card; the profile goes
 * back to the roster first (§15). A partial purge (objects left in the ledger)
 * reads the same to her: the ledger is the operator's to retry, not hers.
 */

import { useEffect, useId, useRef, useState } from 'react';
import { Loader2, X } from 'lucide-react';
import { toast } from 'sonner';

import {
    CL_PURGE_BLOCKED,
    CL_PURGE_CANCEL,
    CL_PURGE_CLOSE,
    CL_PURGE_CONFIRM,
    CL_PURGE_CONFIRM_PLAIN,
    CL_PURGE_DATA_ONLY,
    CL_PURGE_DONE,
    CL_PURGE_LOAD_FAILED,
    CL_PURGE_NOTHING,
    CL_PURGE_REFUSED,
    CL_PURGE_SIGNED_COUNT,
    CL_PURGE_SIGNED_LEAD,
    CL_PURGE_SIGNED_TAIL,
    CL_PURGE_TITLE,
    CL_PURGE_TYPE_NAME,
} from '@/copy/classroom';
import {
    ClassroomConflictError,
    GRADING_IN_PROGRESS,
    PURGE_REFUSED,
    PurgePreview,
    PurgeReport,
    deleteStudent,
    getStudentPurgePreview,
} from '@/lib/api';
import { canConfirmPurge, needsTypedName, PurgeCase } from '@/utils/purge-dialog';

import { InlineError } from './ConfirmDialog';

function conflictMessage(err: unknown, name: string): string | null {
    if (!(err instanceof ClassroomConflictError)) return null;
    if (err.detail === GRADING_IN_PROGRESS) return CL_PURGE_BLOCKED(name);
    if (err.detail === PURGE_REFUSED) return CL_PURGE_REFUSED(name);
    return err.detail;
}

export function StudentDeleteDialog({
    student,
    onCancel,
    onDeleted,
}: {
    student: { id: string; full_name: string };
    onCancel: () => void;
    onDeleted: (report: PurgeReport) => void;
}) {
    const [preview, setPreview] = useState<PurgePreview | null>(null);
    const [typed, setTyped] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const inputRef = useRef<HTMLInputElement>(null);
    const titleId = useId();
    const inputId = useId();
    const name = student.full_name;

    useEffect(() => {
        let alive = true;
        getStudentPurgePreview(student.id)
            .then((p) => {
                if (!alive) return;
                setPreview(p);
                if (p.blockers > 0) setError(CL_PURGE_BLOCKED(name));
            })
            .catch((err) => { if (alive) setError(conflictMessage(err, name) ?? CL_PURGE_LOAD_FAILED); });
        return () => { alive = false; };
    }, [student.id, name]);

    useEffect(() => {
        if (preview && needsTypedName(preview.case as PurgeCase)) inputRef.current?.focus();
    }, [preview]);

    useEffect(() => {
        const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && !busy) onCancel(); };
        window.addEventListener('keydown', onKey);
        return () => window.removeEventListener('keydown', onKey);
    }, [busy, onCancel]);

    const purgeCase = (preview?.case ?? 'nothing') as PurgeCase;
    const typedNeeded = preview ? needsTypedName(purgeCase) : false;
    const enabled = !!preview && !busy && canConfirmPurge(purgeCase, typed, name, preview.blockers);

    const onConfirm = async () => {
        if (!enabled) return;
        setBusy(true);
        setError(null);
        try {
            const report = await deleteStudent(student.id);
            toast.success(CL_PURGE_DONE);
            onDeleted(report);
        } catch (err) {
            setError(conflictMessage(err, name) ?? 'שגיאה במחיקת התלמיד/ה');
            setBusy(false);
        }
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-gray-900/40 p-4" dir="rtl">
            <section
                role="dialog"
                aria-modal="true"
                aria-labelledby={titleId}
                data-student-delete-dialog
                className="flex w-full max-w-[520px] flex-col gap-4 rounded-2xl bg-white px-7 pb-6 pt-7 shadow-2xl"
            >
                <div className="flex items-start justify-between gap-3">
                    <h2 id={titleId} className="text-2xl font-bold leading-tight text-gray-900">
                        {CL_PURGE_TITLE(name)}
                    </h2>
                    <button
                        type="button"
                        aria-label={CL_PURGE_CLOSE}
                        onClick={onCancel}
                        disabled={busy}
                        className="-mt-2 -ml-2 flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-gray-500 hover:bg-surface-100"
                    >
                        <X size={20} />
                    </button>
                </div>

                {!preview && !error ? (
                    <div className="flex justify-center py-4">
                        <Loader2 className="animate-spin text-primary-500" size={24} />
                    </div>
                ) : null}

                {preview ? (
                    <p className="text-base leading-relaxed text-gray-700" data-purge-case={purgeCase}>
                        {purgeCase === 'signed_tests' ? (
                            <>
                                {CL_PURGE_SIGNED_LEAD}
                                <strong className="font-semibold text-gray-900">
                                    {CL_PURGE_SIGNED_COUNT(preview.signed_tests_count)}
                                </strong>
                                {CL_PURGE_SIGNED_TAIL}
                            </>
                        ) : purgeCase === 'data_only' ? CL_PURGE_DATA_ONLY : CL_PURGE_NOTHING}
                    </p>
                ) : null}

                {typedNeeded ? (
                    <div className="flex flex-col gap-2">
                        <label htmlFor={inputId} className="text-sm text-gray-700">{CL_PURGE_TYPE_NAME}</label>
                        <input
                            id={inputId}
                            ref={inputRef}
                            type="text"
                            value={typed}
                            placeholder={name}
                            autoComplete="off"
                            disabled={busy}
                            onChange={(e) => setTyped(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') void onConfirm(); }}
                            className="h-12 rounded-xl border-[1.5px] border-primary-500 bg-white px-3.5 text-base text-gray-900 outline-none focus:ring-2 focus:ring-primary-200"
                        />
                    </div>
                ) : null}

                {error ? <InlineError message={error} /> : null}

                <div className="mt-1.5 flex justify-end gap-2.5">
                    <button
                        type="button"
                        onClick={onCancel}
                        disabled={busy}
                        className="h-[46px] rounded-xl border border-surface-300 bg-white px-5 text-[15px] text-gray-700 hover:bg-surface-50"
                    >
                        {CL_PURGE_CANCEL}
                    </button>
                    <button
                        type="button"
                        onClick={() => void onConfirm()}
                        disabled={!enabled}
                        data-purge-confirm
                        className="flex h-[46px] items-center gap-2 rounded-xl bg-red-600 px-[22px] text-[15px] font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:bg-red-200 disabled:hover:bg-red-200"
                    >
                        {busy ? <Loader2 size={14} className="animate-spin" /> : null}
                        {typedNeeded || !preview ? CL_PURGE_CONFIRM : CL_PURGE_CONFIRM_PLAIN}
                    </button>
                </div>
            </section>
        </div>
    );
}
