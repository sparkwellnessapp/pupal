'use client';

/**
 * Stage B — the upload lane on the batch dashboard.
 *
 * Where the teacher now watches her files arrive. Before Stage B she watched
 * them on the upload page, because the redirect waited for the last byte; the
 * queue moved into `UploadQueueProvider` and this is its surface.
 *
 * WHAT IT MUST NOT LOSE (ruling R2 — the upload page had all of this, and a
 * move that dropped any of it would be a regression dressed as a feature):
 *   * per-file progress while a transfer runs;
 *   * the server's own §3.2 Hebrew reason on a failure, verbatim;
 *   * a retry that reuses the SAME `client_file_id` (the B9 idempotency
 *     contract — a retry can never mint a second test);
 *   * and, new here, a REMOVE for a file that is not coming, which is R9's
 *     explicit half: it re-declares the batch's expected count immediately
 *     instead of leaving her to wait out the 90-minute backstop.
 *
 * It renders only for ITS OWN batch: the provider holds one queue (R10), and
 * the dashboard passes its own id, so opening a different batch shows no lane
 * rather than someone else's progress.
 *
 * The lane survives the drain when files were left behind — a batch that is
 * quietly short is exactly the silent drop U4 exists to kill, so the list stays
 * until she dismisses it.
 */

import { Check, Loader2, RefreshCw, X } from 'lucide-react';

import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    NO_FILENAME,
    UPLOAD_LANE_DISMISS,
    UPLOAD_LANE_DONE,
    UPLOAD_LANE_REMOVE,
    UPLOAD_LANE_WAITING,
    UPLOAD_RETRY,
    ZONE_UPLOAD_DONE_TITLE,
    ZONE_UPLOAD_LEFT_BEHIND,
    ZONE_UPLOAD_SUB,
    ZONE_UPLOAD_TITLE,
} from '@/copy/batch';
import { formatMB, type UploadQueueState } from '@/utils/batch-upload';

export function UploadLane({
    queue,
    onRetry,
    onRemove,
    onDismiss,
}: {
    queue: UploadQueueState;
    onRetry: (clientFileId: string) => void;
    onRemove: (clientFileId: string) => void;
    onDismiss: () => void;
}) {
    const items = queue.items;
    if (items.length === 0) return null;

    const inFlight = items.filter(
        (i) => i.state.kind === 'queued' || i.state.kind === 'uploading',
    ).length;
    const leftBehind = items.filter((i) => i.state.kind === 'failed').length;

    // Nothing moving and nothing left behind ⇒ the lane has said all it has to
    // say. Disappearing is right here: the documents themselves are now the
    // subject, and every one of them is already on the board below.
    if (inFlight === 0 && leftBehind === 0) return null;

    return (
        <ZoneCard
            testId="zone-upload"
            dotClass="bg-batch-blue"
            title={inFlight > 0 ? ZONE_UPLOAD_TITLE(inFlight) : ZONE_UPLOAD_DONE_TITLE}
            sub={inFlight > 0 ? ZONE_UPLOAD_SUB : ZONE_UPLOAD_LEFT_BEHIND(leftBehind)}
            actions={
                inFlight === 0 ? (
                    <button
                        onClick={onDismiss}
                        aria-label={UPLOAD_LANE_DISMISS}
                        data-testid="upload-lane-dismiss"
                        className="rounded-lg p-1.5 text-batch-faint hover:bg-surface-100"
                    >
                        <X size={15} />
                    </button>
                ) : undefined
            }
        >
            <div className="border-t border-batch-line-soft">
                {items.map((item) => (
                    <div
                        key={item.clientFileId}
                        data-testid="upload-lane-row"
                        data-state={item.state.kind}
                        className="flex flex-wrap items-center gap-3.5 border-b border-batch-line-soft px-5 py-2.5 last:border-b-0"
                    >
                        <span className="flex-none">
                            {item.state.kind === 'done' ? (
                                <Check size={15} className="text-batch-green" />
                            ) : item.state.kind === 'failed' ? (
                                <X size={15} className="text-batch-red" />
                            ) : item.state.kind === 'uploading' ? (
                                <Loader2 size={15} className="motion-safe:animate-spin text-batch-blue" />
                            ) : (
                                <span className="inline-block h-[15px] w-[15px] rounded-full border-2 border-batch-line" />
                            )}
                        </span>

                        <span className="min-w-[180px] flex-1 font-medium text-batch-muted">
                            {item.filename || NO_FILENAME}
                        </span>

                        {/* §3.1: sizes are LTR islands inside the RTL page. */}
                        <span className="text-[12.5px] text-batch-faint" dir="ltr">
                            {formatMB(item.size)}
                        </span>

                        {item.state.kind === 'uploading' && (
                            <span className="flex items-center gap-2">
                                <span className="h-1.5 w-24 overflow-hidden rounded-full bg-surface-200">
                                    <span
                                        className="block h-full bg-batch-blue transition-all duration-300"
                                        style={{ width: `${item.state.pct}%` }}
                                        data-testid="upload-lane-progress"
                                    />
                                </span>
                                <span className="font-mono text-[11.5px] text-batch-blue-ink" dir="ltr">
                                    {item.state.pct}%
                                </span>
                            </span>
                        )}

                        {item.state.kind === 'queued' && (
                            <span className="text-[12.5px] text-batch-muted">{UPLOAD_LANE_WAITING}</span>
                        )}

                        {item.state.kind === 'done' && (
                            <span className="text-[12.5px] text-batch-green-ink">{UPLOAD_LANE_DONE}</span>
                        )}

                        {item.state.kind === 'failed' && (
                            <span className="flex flex-wrap items-center gap-2.5">
                                {/* The server's own reason, verbatim — the same
                                    §3.2 vocabulary the upload page showed. */}
                                <span
                                    className="text-[12.5px] text-batch-red-ink"
                                    data-testid="upload-lane-reason"
                                >
                                    {item.state.reason}
                                </span>
                                {item.state.retryable && (
                                    <button
                                        onClick={() => onRetry(item.clientFileId)}
                                        data-testid="upload-lane-retry"
                                        className="inline-flex items-center gap-1 rounded-lg border border-batch-line px-2 py-1 text-[12.5px] text-batch-ink hover:bg-surface-100"
                                    >
                                        <RefreshCw size={12} /> {UPLOAD_RETRY}
                                    </button>
                                )}
                                <button
                                    onClick={() => onRemove(item.clientFileId)}
                                    data-testid="upload-lane-remove"
                                    className="rounded-lg px-2 py-1 text-[12.5px] text-batch-faint hover:bg-surface-100"
                                >
                                    {UPLOAD_LANE_REMOVE}
                                </button>
                            </span>
                        )}
                    </div>
                ))}
            </div>
        </ZoneCard>
    );
}
