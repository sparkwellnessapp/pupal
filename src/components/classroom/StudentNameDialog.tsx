'use client';

import { Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { InlineError } from './ConfirmDialog';

/**
 * The student dialog — create and edit, ONE field (student-profile PR OD-3).
 *
 * `הערות` is gone from the product: the profile is a ledger of discrete
 * facts, and a free-text box on the student is precisely where a judgement
 * would accumulate. The roster and the profile both open this dialog, so the
 * field cannot quietly return on one of them.
 */
export function StudentNameDialog({
    title, submitLabel, initialName = '', loading = false, error, onSubmit, onClose, onClearError,
}: {
    title: string;
    submitLabel: string;
    initialName?: string;
    loading?: boolean;
    error?: string | null;
    onSubmit: (fullName: string) => void;
    onClose: () => void;
    onClearError?: () => void;
}) {
    const [name, setName] = useState(initialName);
    const submit = () => { if (name.trim() && !loading) onSubmit(name.trim()); };

    return (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
            <div className="bg-white rounded-xl shadow-2xl p-6 max-w-md w-full" role="dialog" aria-modal="true">
                <div className="flex items-center justify-between mb-4">
                    <button onClick={onClose} className="text-gray-400 hover:text-gray-600" aria-label="סגירה">
                        <X size={20} />
                    </button>
                    <h2 className="font-semibold text-gray-900">{title}</h2>
                </div>
                <div className="space-y-3">
                    <div>
                        <label htmlFor="student-full-name" className="block text-sm font-medium text-gray-700 mb-1 text-right">
                            שם מלא *
                        </label>
                        <input
                            id="student-full-name"
                            type="text"
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
                            className="w-full px-4 py-2.5 border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 text-right"
                            placeholder="שם התלמיד/ה"
                            dir="rtl"
                            autoFocus
                        />
                    </div>
                    {error && <InlineError message={error} onClose={onClearError} />}
                </div>
                <div className="flex gap-3 justify-start mt-5">
                    <button
                        onClick={onClose}
                        className="px-4 py-2 text-sm text-gray-700 border border-surface-300 rounded-lg hover:bg-surface-50"
                    >
                        ביטול
                    </button>
                    <button
                        onClick={submit}
                        disabled={loading || !name.trim()}
                        className="px-4 py-2 text-sm bg-primary-500 text-white rounded-lg hover:bg-primary-600 disabled:opacity-50 flex items-center gap-2"
                    >
                        {loading && <Loader2 size={14} className="animate-spin" />}
                        {submitLabel}
                    </button>
                </div>
            </div>
        </div>
    );
}
