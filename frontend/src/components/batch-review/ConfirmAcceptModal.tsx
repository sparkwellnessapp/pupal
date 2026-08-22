'use client';

/**
 * The accept confirmation modal — the v0.5 ConfirmationModal repurposed for
 * per-item accept (plan §7 copy table: the accept is the point of no return;
 * OD-6: an empty transcription is acceptable behind an explicit warning).
 *
 * R9 (P3): rebuilt on the F8 Modal primitive — role="dialog", aria-modal,
 * focus trap, Esc closes, initial focus on the primary (data-autofocus), and
 * capture-phase key suppression so R3's page keymap never sees in-modal keys.
 * Enter therefore confirms: the focused primary button receives it natively.
 */

import { AlertTriangle, CheckCircle2, X } from 'lucide-react';

import { Modal } from '@/components/batch/Modal';
import { lowConfidenceCount } from '@/utils/hebrew-plural';

export function ConfirmAcceptModal({
    isOpen,
    onConfirm,
    onCancel,
    lowConfidence,
    hasUncertain,
    isEmpty,
    confirming,
}: {
    isOpen: boolean;
    onConfirm: () => void;
    onCancel: () => void;
    lowConfidence: number;
    hasUncertain: boolean;
    isEmpty: boolean;
    confirming: boolean;
}) {
    const warnings: string[] = [];
    if (isEmpty) warnings.push('התמלול ריק — המבחן יישלח לבדיקה ללא תשובות');
    if (lowConfidence > 0) warnings.push(lowConfidenceCount(lowConfidence));
    if (hasUncertain) warnings.push('יש תווים לא ברורים [?] שכדאי לבדוק');

    return (
        <Modal
            open={isOpen}
            onClose={onCancel}
            labelledBy="confirm-accept-title"
            testId="confirm-accept-modal"
        >
            {/* relative wrapper: the Modal panel itself is not positioned,
                so the close X anchors here, not to the fixed overlay. */}
            <div className="relative">
            <button
                onClick={onCancel}
                aria-label="סגירה"
                className="absolute -top-2 -left-2 p-1 text-gray-400 hover:text-gray-600"
            >
                <X size={20} />
            </button>

            <div className="text-center">
                <div className="mx-auto w-12 h-12 bg-primary-100 rounded-full flex items-center justify-center mb-4">
                    <CheckCircle2 className="text-primary-600" size={24} />
                </div>
                <h3 id="confirm-accept-title" className="text-lg font-semibold text-gray-900 mb-2">
                    לאשר את התמלול?
                </h3>

                {warnings.length > 0 ? (
                    <div className="mb-4 p-3 bg-amber-50 border border-amber-200 rounded-lg text-right">
                        <div className="flex items-start gap-2 text-amber-700 text-sm">
                            <AlertTriangle size={16} className="flex-shrink-0 mt-0.5" />
                            <div className="space-y-1">
                                {warnings.map((w) => <p key={w}>{w}</p>)}
                            </div>
                        </div>
                    </div>
                ) : (
                    <p className="text-gray-600 mb-4">אישור התמלול ישלח את המבחן לבדיקה</p>
                )}

                <div className="flex gap-3 justify-center">
                    <button
                        onClick={onCancel}
                        disabled={confirming}
                        className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                        ביטול
                    </button>
                    <button
                        onClick={onConfirm}
                        disabled={confirming}
                        data-autofocus
                        data-testid="confirm-accept-primary"
                        className="px-4 py-2 text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-60 transition-colors"
                    >
                        {confirming ? 'מאשר…' : 'אישור תמלול'}
                    </button>
                </div>
            </div>
            </div>
        </Modal>
    );
}
