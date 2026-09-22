'use client';

import { AlertCircle, Loader2, X } from 'lucide-react';

/**
 * הכיתות שלי — the shared inline error and the confirm dialog, lifted out of
 * the roster page so the student profile (student-profile PR §6.2) uses the
 * SAME primitives rather than a second copy of each.
 */

export function InlineError({ message, onClose }: { message: string; onClose?: () => void }) {
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

export function ConfirmDialog({
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
            <div className="bg-white rounded-xl shadow-2xl p-6 max-w-sm w-full" role="dialog" aria-modal="true">
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
