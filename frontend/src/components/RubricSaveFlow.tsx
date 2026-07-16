'use client';

import { RubricAnnotation, ValidationErrorDetail, RubricSaveError } from '@/lib/api';

// =============================================================================
// RubricWarningsModal - Modal for acknowledging compilation warnings
// =============================================================================

interface RubricWarningsModalProps {
    warnings: RubricAnnotation[];
    messageHe: string;
    onAcknowledge: (warningIds: string[]) => void;
    onCancel: () => void;
    isSubmitting?: boolean;
}

/**
 * Modal for displaying compilation warnings that require acknowledgment.
 * Teacher can review and acknowledge warnings to proceed with save.
 */
export function RubricWarningsModal({
    warnings,
    messageHe,
    onAcknowledge,
    onCancel,
    isSubmitting = false,
}: RubricWarningsModalProps) {
    const handleAcknowledge = () => {
        const warningIds = warnings.map((w) => w.id);
        onAcknowledge(warningIds);
    };

    return (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
            <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[80vh] overflow-hidden flex flex-col">
                {/* Header */}
                <div className="px-6 py-4 border-b border-gray-200 bg-amber-50">
                    <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-full bg-amber-100 flex items-center justify-center">
                            <svg className="w-6 h-6 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                            </svg>
                        </div>
                        <div>
                            <h2 className="text-lg font-semibold text-gray-900">אזהרות במחוון</h2>
                            <p className="text-sm text-gray-600">{messageHe}</p>
                        </div>
                    </div>
                </div>

                {/* Warnings List */}
                <div className="flex-1 overflow-y-auto p-6">
                    <p className="text-sm text-gray-600 mb-4">
                        נמצאו {warnings.length} אזהרות. ניתן להמשיך בשמירה לאחר אישור.
                    </p>

                    <ul className="space-y-3">
                        {warnings.map((warning) => (
                            <li
                                key={warning.id}
                                className="p-4 rounded-xl bg-amber-50 border border-amber-200"
                            >
                                <div className="flex items-start gap-3">
                                    <svg className="w-5 h-5 text-amber-500 mt-0.5 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                                        <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                                    </svg>
                                    <div>
                                        <p className="text-sm text-gray-800">{warning.message}</p>
                                        {warning.target_id && (
                                            <p className="text-xs text-gray-500 mt-1">
                                                מיקום: <code className="bg-gray-100 px-1 rounded">{warning.target_id}</code>
                                            </p>
                                        )}
                                    </div>
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>

                {/* Footer */}
                <div className="px-6 py-4 border-t border-gray-200 flex gap-3 justify-end">
                    <button
                        onClick={onCancel}
                        disabled={isSubmitting}
                        className="px-4 py-2 rounded-lg font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 transition-colors disabled:opacity-50"
                    >
                        ביטול
                    </button>
                    <button
                        onClick={handleAcknowledge}
                        disabled={isSubmitting}
                        className="px-4 py-2 rounded-lg font-medium text-white bg-amber-500 hover:bg-amber-600 transition-colors disabled:opacity-50 flex items-center gap-2"
                    >
                        {isSubmitting ? (
                            <>
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                                </svg>
                                שומר...
                            </>
                        ) : (
                            <>
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                </svg>
                                אישור והמשך בשמירה
                            </>
                        )}
                    </button>
                </div>
            </div>
        </div>
    );
}


// =============================================================================
// RubricErrorDisplay - Inline error display for validation/compilation errors
// =============================================================================

interface RubricErrorDisplayProps {
    error: RubricSaveError;
    onDismiss?: () => void;
}

/**
 * Inline display for rubric validation or compilation errors.
 * Shows Hebrew message and list of specific errors.
 */
export function RubricErrorDisplay({ error, onDismiss }: RubricErrorDisplayProps) {
    const isValidation = error.errorType === 'validation_failed';
    const title = isValidation ? 'שגיאות בבדיקת המחוון' : 'שגיאות בהכנת המחוון';
    const bgColor = isValidation ? 'bg-red-50' : 'bg-orange-50';
    const borderColor = isValidation ? 'border-red-200' : 'border-orange-200';
    const iconColor = isValidation ? 'text-red-500' : 'text-orange-500';

    // Anchor-scroll (PR-4): the compile-error `location` is a full dotted path
    // ("q1.א.2"), and RubricEditor tags every node — including nested ones — with
    // `data-scope-id={path}`. So a click jumps the teacher straight to the offending
    // node. Self-contained querySelector, matching RubricEditor.scrollToScope; a
    // no-op (graceful) if the editor is not mounted on this surface.
    const jumpToNode = (loc: string) => {
        const el = document.querySelector(`[data-scope-id="${loc}"]`);
        if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };

    return (
        <div className={`rounded-xl ${bgColor} border ${borderColor} p-4 mb-4`}>
            <div className="flex items-start justify-between">
                <div className="flex items-start gap-3">
                    <svg className={`w-6 h-6 ${iconColor} flex-shrink-0 mt-0.5`} fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <div>
                        <h3 className="font-semibold text-gray-900">{title}</h3>
                        <p className="text-sm text-gray-700 mt-1">{error.messageHe}</p>
                    </div>
                </div>
                {onDismiss && (
                    <button
                        onClick={onDismiss}
                        className="text-gray-400 hover:text-gray-600 transition-colors"
                    >
                        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                )}
            </div>

            {error.errors.length > 0 && (
                <ul className="mt-3 space-y-2">
                    {error.errors.map((err, idx) => {
                        // PR-4: render the STRUCTURED compile-error payload the backend
                        // already emits (invariant / expected / actual / message_he /
                        // location), not just a flat message. The three carriers
                        // (ValidationErrorDetail | RubricAnnotation | CompileErrorDetail)
                        // are discriminated by field presence.
                        const message =
                            ('message_he' in err && err.message_he) ? err.message_he : err.message;
                        const location =
                            'location' in err ? err.location
                            : ('target_id' in err ? err.target_id : null);
                        const invariant = 'invariant' in err ? err.invariant : null;
                        const expected = 'expected' in err ? err.expected : null;
                        const actual = 'actual' in err ? err.actual : null;

                        return (
                            <li key={idx} className="text-sm text-gray-700">
                                <div className="flex items-start gap-2">
                                    <span className="text-gray-400 mt-0.5">•</span>
                                    <div className="flex-1 min-w-0">
                                        <div className="flex flex-wrap items-center gap-1.5">
                                            {invariant && (
                                                <span className="text-[11px] font-mono font-semibold bg-red-100 text-red-700 px-1.5 py-0.5 rounded">
                                                    {invariant}
                                                </span>
                                            )}
                                            <span>{message}</span>
                                        </div>
                                        {(expected !== null || actual !== null) && (
                                            <div className="text-xs text-gray-500 mt-0.5">
                                                צפוי: <span className="font-medium text-gray-700">{expected}</span>
                                                {' · '}בפועל: <span className="font-medium text-gray-700">{actual}</span>
                                            </div>
                                        )}
                                        {location && (
                                            <button
                                                type="button"
                                                onClick={() => jumpToNode(location)}
                                                className="text-xs mt-1 inline-flex items-center gap-1 text-primary-600 hover:text-primary-800 hover:underline"
                                                title="מעבר לרכיב במחוון"
                                            >
                                                <span>מעבר לרכיב</span>
                                                <code className="bg-gray-100 px-1.5 py-0.5 rounded">{location}</code>
                                            </button>
                                        )}
                                    </div>
                                </div>
                            </li>
                        );
                    })}
                </ul>
            )}
        </div>
    );
}


// =============================================================================
// useRubricSave - Hook for managing the save flow with warnings
// =============================================================================

import { useState, useCallback } from 'react';
import {
    SaveOntologyRubricRequest,
    SaveOntologyRubricSuccess,
    saveOntologyRubric,
    updateOntologyRubric,
    isWarningsResponse,
    SaveOntologyRubricWarnings,
} from '@/lib/api';

interface UseRubricSaveState {
    isLoading: boolean;
    error: RubricSaveError | null;
    warnings: SaveOntologyRubricWarnings | null;
}

interface UseRubricSaveReturn extends UseRubricSaveState {
    save: (request: SaveOntologyRubricRequest) => Promise<SaveOntologyRubricSuccess | null>;
    update: (rubricId: string, request: Omit<SaveOntologyRubricRequest, 'name'>) => Promise<SaveOntologyRubricSuccess | null>;
    acknowledgeWarnings: (warningIds: string[]) => void;
    clearError: () => void;
    clearWarnings: () => void;
}

/**
 * Hook for managing rubric save/update flow with warning acknowledgment.
 * 
 * Usage:
 * ```tsx
 * const { save, warnings, error, isLoading } = useRubricSave();
 * 
 * // Initial save
 * const result = await save({ name: 'My Rubric', draft: extractedData });
 * 
 * // If warnings returned, show modal
 * if (warnings) {
 *   // User acknowledges -> call acknowledgeWarnings(warningIds)
 * }
 * ```
 */
export function useRubricSave(): UseRubricSaveReturn {
    const [state, setState] = useState<UseRubricSaveState>({
        isLoading: false,
        error: null,
        warnings: null,
    });

    const [pendingRequest, setPendingRequest] = useState<SaveOntologyRubricRequest | null>(null);
    const [pendingRubricId, setPendingRubricId] = useState<string | null>(null);

    const save = useCallback(async (request: SaveOntologyRubricRequest): Promise<SaveOntologyRubricSuccess | null> => {
        setState({ isLoading: true, error: null, warnings: null });
        setPendingRequest(request);
        setPendingRubricId(null);

        try {
            const response = await saveOntologyRubric(request);

            if (isWarningsResponse(response)) {
                setState({ isLoading: false, error: null, warnings: response });
                return null;
            }

            setState({ isLoading: false, error: null, warnings: null });
            return response;
        } catch (err) {
            if (err instanceof RubricSaveError) {
                setState({ isLoading: false, error: err, warnings: null });
            } else {
                setState({
                    isLoading: false,
                    error: new RubricSaveError('validation_failed', (err as Error).message, []),
                    warnings: null
                });
            }
            return null;
        }
    }, []);

    const update = useCallback(async (
        rubricId: string,
        request: Omit<SaveOntologyRubricRequest, 'name'>
    ): Promise<SaveOntologyRubricSuccess | null> => {
        setState({ isLoading: true, error: null, warnings: null });
        setPendingRequest({ ...request, name: '' } as SaveOntologyRubricRequest);
        setPendingRubricId(rubricId);

        try {
            const response = await updateOntologyRubric(rubricId, request);

            if (isWarningsResponse(response)) {
                setState({ isLoading: false, error: null, warnings: response });
                return null;
            }

            setState({ isLoading: false, error: null, warnings: null });
            return response as SaveOntologyRubricSuccess;
        } catch (err) {
            if (err instanceof RubricSaveError) {
                setState({ isLoading: false, error: err, warnings: null });
            } else {
                setState({
                    isLoading: false,
                    error: new RubricSaveError('validation_failed', (err as Error).message, []),
                    warnings: null
                });
            }
            return null;
        }
    }, []);

    const acknowledgeWarnings = useCallback(async (warningIds: string[]) => {
        if (!pendingRequest) return;

        setState(prev => ({ ...prev, isLoading: true }));

        try {
            const requestWithAck = {
                ...pendingRequest,
                acknowledged_warning_ids: warningIds,
            };

            let response;
            if (pendingRubricId) {
                response = await updateOntologyRubric(pendingRubricId, requestWithAck);
            } else {
                response = await saveOntologyRubric(requestWithAck);
            }

            if (isWarningsResponse(response)) {
                // Still has warnings - shouldn't happen with acknowledgment
                setState({ isLoading: false, error: null, warnings: response });
            } else {
                setState({ isLoading: false, error: null, warnings: null });
                // Success - the caller should handle the result
            }
        } catch (err) {
            if (err instanceof RubricSaveError) {
                setState({ isLoading: false, error: err, warnings: null });
            }
        }
    }, [pendingRequest, pendingRubricId]);

    const clearError = useCallback(() => {
        setState(prev => ({ ...prev, error: null }));
    }, []);

    const clearWarnings = useCallback(() => {
        setState(prev => ({ ...prev, warnings: null }));
        setPendingRequest(null);
        setPendingRubricId(null);
    }, []);

    return {
        ...state,
        save,
        update,
        acknowledgeWarnings,
        clearError,
        clearWarnings,
    };
}
