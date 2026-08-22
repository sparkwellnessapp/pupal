'use client';

/**
 * The batches list (P5/L1) — the section's front door, rebuilt on the shared
 * batch language: C1 copy only (OD4: מקבץ, never אצווה), the F8 `SegmentBar`
 * as a legend-less mini honesty bar, one action line per row, and the rubric /
 * class names B4 has been resolving server-side while this surface dropped
 * them (census Q30: 6 of 9 rollup counters were fetched and never drawn).
 *
 * The mini bar reads `rollup.needs_eyes` (closeout/Ruling 1), so the
 * clean|needs-eyes split it draws is the SAME one the dashboard draws and the
 * same one `accept_clean` enforces — one number, three surfaces.
 */

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Loader2, AlertCircle, ClipboardCheck, Calendar } from 'lucide-react';
import { SidebarLayout } from '@/components/SidebarLayout';
import { listGradingBatches } from '@/lib/api';
import {
    BATCH_FALLBACK_NAME,
    BATCH_LOAD_ERROR,
    batchStatusLabel,
    LIST_EMPTY,
    LIST_EMPTY_CTA,
    LIST_NEW_BATCH,
    LIST_SUBTITLE,
    LIST_TITLE,
    META_RUBRIC_PREFIX,
    META_TESTS,
} from '@/copy/batch';
import { SegmentBar } from '@/components/batch/SegmentBar';
import { listActionLine, listBarSegments } from '@/utils/batch-list';
import type { BatchListItem } from '@/types/batch';

function StatusBadge({ status, transcribing }: { status: string; transcribing: number }) {
    const map: Record<string, string> = {
        in_progress: 'bg-amber-100 text-amber-700',
        completed: 'bg-green-100 text-green-700',
        partially_completed: 'bg-orange-100 text-orange-700',
        failed: 'bg-red-100 text-red-700',
        pending: 'bg-gray-100 text-gray-500',
    };
    // Labels come from the C1 copy module (F3) — one home, both surfaces.
    return (
        <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${map[status] ?? 'bg-gray-100 text-gray-500'}`}>
            {batchStatusLabel(status, { transcribing })}
        </span>
    );
}

/** The action line's hue follows its meaning: amber = she owes a decision. */
const ACTION_CLS: Record<string, string> = {
    transcribing: 'text-batch-muted',
    eyes: 'text-batch-amber-ink',
    pending: 'text-batch-muted',
    failed: 'text-batch-red-ink',
    done: 'text-batch-green-ink',
};

function BatchRow({ batch }: { batch: BatchListItem }) {
    const action = listActionLine(batch.rollup);
    const segments = listBarSegments(batch.rollup);
    const meta = [
        batch.rubric_name ? `${META_RUBRIC_PREFIX} ${batch.rubric_name}` : null,
        batch.class_name,
        META_TESTS(batch.rollup.total),
    ].filter(Boolean) as string[];

    return (
        <Link
            href={`/batches/${batch.id}`}
            data-testid="batch-row"
            className="block bg-white rounded-zone border border-batch-line px-5 py-4 hover:border-primary-300 hover:shadow-zone transition-all"
        >
            <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                    <p className="font-medium text-batch-ink truncate">
                        {batch.name ?? BATCH_FALLBACK_NAME(batch.id.slice(0, 8))}
                    </p>
                    <div className="flex items-center gap-2 mt-1 text-xs text-batch-muted flex-wrap">
                        <span className="flex items-center gap-1">
                            <Calendar size={12} />
                            {new Date(batch.created_at).toLocaleDateString('he-IL', {
                                year: 'numeric', month: 'short', day: 'numeric',
                            })}
                        </span>
                        {meta.map((m) => (
                            <span key={m} className="flex items-center gap-2">
                                <span aria-hidden="true">·</span>
                                <span className="truncate max-w-[16rem]">{m}</span>
                            </span>
                        ))}
                    </div>
                </div>
                <StatusBadge status={batch.status} transcribing={batch.rollup.transcribing} />
            </div>

            {/* L1: the mini honesty bar — same primitive as D2, legend-less. */}
            {segments.length > 0 && (
                <div className="mt-3">
                    <SegmentBar segments={segments} legend={false} compact />
                </div>
            )}

            {action && (
                <p
                    className={`mt-2 text-xs font-medium ${ACTION_CLS[action.kind] ?? 'text-batch-muted'}`}
                    data-testid="list-action-line"
                >
                    {action.text}
                </p>
            )}
        </Link>
    );
}

export default function BatchListPage() {
    const [batches, setBatches] = useState<BatchListItem[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        listGradingBatches()
            .then(r => setBatches(r.batches))
            .catch(err => setError(err instanceof Error ? err.message : BATCH_LOAD_ERROR))
            .finally(() => setLoading(false));
    }, []);

    return (
        <SidebarLayout>
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-6">
                    <div>
                        <h1 className="text-2xl font-bold text-batch-ink">{LIST_TITLE}</h1>
                        <p className="text-batch-muted mt-1">{LIST_SUBTITLE}</p>
                    </div>
                    <Link
                        href="/"
                        className="flex items-center gap-2 bg-primary-500 text-white px-4 py-2.5 rounded-lg hover:bg-primary-600 transition-colors font-medium text-sm"
                    >
                        <ClipboardCheck size={16} />
                        {LIST_NEW_BATCH}
                    </Link>
                </div>

                {loading ? (
                    <div className="flex items-center justify-center py-20">
                        <Loader2 className="animate-spin text-primary-500" size={40} />
                    </div>
                ) : error ? (
                    <div className="bg-red-50 border border-red-200 rounded-xl p-6 text-center">
                        <AlertCircle className="mx-auto text-red-500 mb-2" size={32} />
                        <p className="text-red-700">{error}</p>
                    </div>
                ) : batches.length === 0 ? (
                    <div
                        className="bg-white rounded-zone border border-batch-line p-12 text-center"
                        data-testid="list-empty"
                    >
                        <ClipboardCheck className="mx-auto text-batch-faint mb-4" size={48} />
                        <h3 className="text-lg font-medium text-batch-ink mb-2">{LIST_EMPTY}</h3>
                        <Link href="/" className="text-primary-600 hover:underline text-sm">
                            {LIST_EMPTY_CTA}
                        </Link>
                    </div>
                ) : (
                    <div className="space-y-3">
                        {batches.map(batch => <BatchRow key={batch.id} batch={batch} />)}
                    </div>
                )}
            </div>
        </SidebarLayout>
    );
}
