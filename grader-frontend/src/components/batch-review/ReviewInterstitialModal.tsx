'use client';

/**
 * R4 — the end-of-flagged-walk interstitial, on the F8 Modal primitive (R9).
 *
 * Appears when the LAST unapproved flagged item is accepted (advanceTarget →
 * 'interstitial'): every flagged test has been reviewed; the remaining clean,
 * unapproved tests can be bulk-accepted from here (same accept_clean seam as
 * the dashboard's D5 button, skips surfaced), or the teacher returns to the
 * dashboard without accepting anything.
 *
 * The bulk-acceptable subset can be SMALLER than the remaining-clean count
 * (a touched clean has no matched_student_id pre-seed, or would be skipped
 * server-side): the body states the honest remaining count; the bulk button
 * carries the acceptable count; zero acceptable → no bulk button at all.
 */

import { CheckCircle2 } from 'lucide-react';

import { Modal } from '@/components/batch/Modal';
import {
    CLEAN_PRIMARY,
    INTERSTITIAL_BACK,
    INTERSTITIAL_BODY,
    INTERSTITIAL_TITLE,
} from '@/copy/batch';

export function ReviewInterstitialModal({
    open,
    cleansRemaining,
    bulkAcceptable,
    busy,
    error,
    onBulkAccept,
    onBackToDashboard,
    onClose,
}: {
    open: boolean;
    /** Unapproved clean items still in the batch (honest body count). */
    cleansRemaining: number;
    /** The subset the bulk button can actually send (matched student). */
    bulkAcceptable: number;
    busy: boolean;
    error: string | null;
    onBulkAccept: () => void;
    onBackToDashboard: () => void;
    onClose: () => void;
}) {
    return (
        <Modal
            open={open}
            onClose={onClose}
            labelledBy="review-interstitial-title"
            testId="review-interstitial"
        >
            <div className="text-center">
                <div className="mx-auto w-12 h-12 bg-batch-green-soft rounded-full flex items-center justify-center mb-4">
                    <CheckCircle2 className="text-batch-green" size={24} />
                </div>
                <h3 id="review-interstitial-title" className="text-lg font-semibold text-gray-900 mb-2">
                    {INTERSTITIAL_TITLE}
                </h3>
                <p className="text-gray-600 mb-4">{INTERSTITIAL_BODY(cleansRemaining)}</p>

                {error && (
                    <div className="mb-4 px-3 py-2 rounded-lg bg-red-50 border border-red-200 text-red-700 text-sm text-right">
                        {error}
                    </div>
                )}

                <div className="flex gap-3 justify-center flex-wrap">
                    <button
                        onClick={onBackToDashboard}
                        disabled={busy}
                        data-testid="interstitial-back"
                        className="px-4 py-2 text-gray-700 bg-gray-100 rounded-lg hover:bg-gray-200 transition-colors"
                    >
                        {INTERSTITIAL_BACK}
                    </button>
                    {bulkAcceptable > 0 && (
                        <button
                            onClick={onBulkAccept}
                            disabled={busy}
                            data-autofocus
                            data-testid="interstitial-bulk"
                            className="px-4 py-2 text-white bg-primary-500 rounded-lg hover:bg-primary-600 disabled:opacity-60 transition-colors"
                        >
                            {busy ? 'מאשרת…' : CLEAN_PRIMARY(bulkAcceptable)}
                        </button>
                    )}
                </div>
            </div>
        </Modal>
    );
}
