/**
 * D8 — the failed zone: honest per-document failure cards (net_verdict
 * guidance kept verbatim from the pre-redesign card), one-click retry for
 * Cloud-Tasks jobs (job_id present), raw error as a muted LTR mono line.
 */
import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    FAILED_GUIDE_LEGACY,
    FAILED_GUIDE_NET,
    FAILED_GUIDE_RETRYABLE,
    FAILED_RETRY,
    FAILED_TITLE,
    NO_FILENAME,
} from '@/copy/batch';
import type { TranscriptionFailureItem } from '@/types/batch';

function guidance(f: TranscriptionFailureItem): string {
    if (f.net_verdict === 'local-no-internet' || f.net_verdict === 'local-dns') {
        return FAILED_GUIDE_NET;
    }
    return f.job_id ? FAILED_GUIDE_RETRYABLE : FAILED_GUIDE_LEGACY;
}

export function FailedZone({
    failures,
    onRetry,
    retryBusy,
}: {
    failures: TranscriptionFailureItem[];
    onRetry: (jobId: string) => void;
    retryBusy: ReadonlySet<string>;
}) {
    if (failures.length === 0) return null;
    return (
        <div className="space-y-3" data-testid="zone-failed">
            {failures.map((f, i) => (
                <ZoneCard
                    key={`${f.filename ?? NO_FILENAME}-${f.at}-${i}`}
                    className="!border-batch-red-line !bg-batch-red-soft"
                    dotClass="bg-batch-seg-failed"
                    title={
                        <span className="text-batch-red-ink">
                            {FAILED_TITLE(f.filename ?? NO_FILENAME)}
                        </span>
                    }
                    sub={
                        <span className="text-batch-red-ink">
                            {guidance(f)}
                            <span
                                className="mt-1 block break-all font-mono text-xs opacity-75"
                                dir="ltr"
                                style={{ textAlign: 'left' }}
                            >
                                {f.error}
                            </span>
                        </span>
                    }
                    actions={
                        f.job_id && (
                            <button
                                onClick={() => onRetry(f.job_id as string)}
                                disabled={retryBusy.has(f.job_id as string)}
                                className="rounded-[10px] border-[1.5px] border-batch-red px-4 py-2 font-semibold text-batch-red-ink hover:bg-white disabled:opacity-45"
                                data-testid="retry-job-button"
                            >
                                {FAILED_RETRY}
                            </button>
                        )
                    }
                />
            ))}
        </div>
    );
}
