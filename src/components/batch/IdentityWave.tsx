/**
 * D4 — the identity wave: Vivi read the students' names off the handwriting;
 * the teacher fixes spelling in place and creates them all. Creation only
 * adds students to her roster — convergence (items turning clean) is the
 * next poll's job, never an optimistic verdict flip.
 *
 * Dumb component: pill values/statuses live in the PAGE keyed by normalized
 * name (the 3s-poll race-proofing rule) — a payload replacement can never
 * reset an in-flight pill.
 */
import Link from 'next/link';

import { StatusChip } from '@/components/batch/StatusChip';
import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    WAVE_FOOTNOTE,
    WAVE_PILL_CONFLICT,
    WAVE_PRIMARY,
    WAVE_UNMATCHED_PILL,
    ZONE_WAVE_SUB,
    ZONE_WAVE_TITLE,
    NO_FILENAME,
} from '@/copy/batch';

export type PillStatus = 'idle' | 'creating' | 'done' | 'conflict' | 'error';

export interface PillView {
    /** Stable key = normalized first-seen name. */
    key: string;
    value: string;
    status: PillStatus;
    files: string[];
}

export function IdentityWave({
    pills,
    unmatched,
    batchId,
    bulkBusy,
    onEditPill,
    onCreatePill,
    onBulkCreate,
}: {
    pills: PillView[];
    unmatched: Array<{ transcription_id: string; filename: string | null }>;
    batchId: string;
    bulkBusy: boolean;
    onEditPill: (key: string, value: string) => void;
    onCreatePill: (key: string) => void;
    onBulkCreate: () => void;
}) {
    const pending = pills.filter((p) => p.status === 'idle' || p.status === 'error');
    return (
        <ZoneCard
            testId="zone-identity-wave"
            className="border-[1.5px] !border-primary-500 bg-gradient-to-b from-[#F2FBF9] to-white"
            dotClass="bg-primary-500"
            title={ZONE_WAVE_TITLE(pills.length)}
            sub={ZONE_WAVE_SUB}
            actions={
                <button
                    onClick={onBulkCreate}
                    disabled={bulkBusy || pending.length === 0}
                    className="rounded-[10px] bg-primary-500 px-4 py-2 font-semibold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-45"
                    data-testid="wave-bulk-create"
                >
                    {WAVE_PRIMARY(pending.length)}
                </button>
            }
        >
            <div className="flex flex-wrap gap-2 px-5 pb-4 pt-1.5">
                {pills.map((p) => (
                    <span
                        key={p.key}
                        data-testid={`pill-${p.key}`}
                        data-status={p.status}
                        className={`inline-flex items-center gap-2 rounded-full border px-2 py-1.5 text-sm ${
                            p.status === 'done'
                                ? 'border-batch-green bg-batch-green-soft'
                                : p.status === 'conflict'
                                  ? 'border-batch-line bg-batch-green-soft'
                                  : p.status === 'error'
                                    ? 'border-batch-red bg-batch-red-soft'
                                    : 'border-batch-line bg-white'
                        }`}
                    >
                        <input
                            value={p.value}
                            onChange={(e) => onEditPill(p.key, e.target.value)}
                            disabled={p.status === 'done' || p.status === 'conflict' || p.status === 'creating'}
                            aria-label={p.files.length ? p.files.join(', ') : NO_FILENAME}
                            className="min-w-[60px] max-w-[180px] border-b-[1.5px] border-dashed border-[#BFD8D3] bg-transparent px-0.5 outline-none focus:border-primary-500 focus:bg-batch-teal-soft disabled:border-transparent"
                            style={{ width: `${Math.max(4, p.value.length + 1)}ch` }}
                        />
                        {p.status === 'conflict' ? (
                            <StatusChip hue="green" className="!text-[10.5px]">
                                {WAVE_PILL_CONFLICT}
                            </StatusChip>
                        ) : (
                            <button
                                onClick={() => onCreatePill(p.key)}
                                disabled={
                                    p.status === 'done' || p.status === 'creating' ||
                                    p.value.trim() === ''
                                }
                                title="יצירה"
                                className={`grid h-6 w-6 place-items-center rounded-full text-[13px] font-bold ${
                                    p.status === 'done'
                                        ? 'bg-batch-green text-white'
                                        : 'bg-batch-teal-soft text-batch-teal-ink hover:bg-primary-500 hover:text-white'
                                } disabled:cursor-not-allowed disabled:opacity-60`}
                            >
                                {p.status === 'creating' ? '…' : '✓'}
                            </button>
                        )}
                    </span>
                ))}
                {unmatched.map((u) => (
                    <Link
                        key={u.transcription_id}
                        href={`/batches/${batchId}/review/${u.transcription_id}`}
                        className="inline-flex items-center rounded-full border border-dashed border-batch-line px-3 py-1.5 text-sm text-batch-muted hover:border-primary-500 hover:text-batch-teal-ink"
                        data-testid="pill-unmatched"
                    >
                        {WAVE_UNMATCHED_PILL(u.filename ?? NO_FILENAME)}
                    </Link>
                ))}
            </div>
            <div className="px-5 pb-4 text-xs text-batch-muted">{WAVE_FOOTNOTE}</div>
        </ZoneCard>
    );
}
