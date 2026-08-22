/**
 * D5 — the clean panel: one decision over a set whose "clean" property the
 * SERVER guarantees (B1). Rows expand to an inline peek straight from the
 * already-fetched draft (zero requests); the bulk response's `skipped` is
 * surfaced verbatim — nothing is silently dropped (F4). All interactive
 * state (expansion, dimming) is keyed by transcription_id so the 3s poll's
 * payload replacement can never misattach it.
 */
import Link from 'next/link';

import { StatusChip } from '@/components/batch/StatusChip';
import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    CLEAN_OPEN_FULL,
    CLEAN_PRIMARY,
    CLEAN_ROW_META,
    CLEAN_SECONDARY,
    CLEAN_SHOW_ALL,
    EMPTY_ANSWER_MARKER,
    NO_FILENAME,
    ZONE_CLEAN_SUB,
    ZONE_CLEAN_TITLE,
} from '@/copy/batch';
import { answerTargetId } from '@/utils/review-flags';
import type { BatchTranscriptionItem } from '@/types/batch';

const COLLAPSED_ROWS = 5;
const PEEK_LINES = 6;

function keyLabelOf(a: { question_number: number; sub_question_id: string | null }): string {
    return a.sub_question_id
        ? `שאלה ${a.question_number} · סעיף ${a.sub_question_id}`
        : `שאלה ${a.question_number}`;
}

export function CleanPanel({
    items,
    batchId,
    expanded,
    onToggle,
    showAll,
    onShowAll,
    accepting,
    bulkBusy,
    onAcceptAll,
    skipNotice,
    manualReviewId,
    newIds,
}: {
    items: BatchTranscriptionItem[];
    batchId: string;
    expanded: ReadonlySet<string>;
    onToggle: (id: string) => void;
    showAll: boolean;
    onShowAll: () => void;
    /** Optimistically dimmed ids (bulk in flight), reconciled by the poll. */
    accepting: ReadonlySet<string>;
    bulkBusy: boolean;
    onAcceptAll: () => void;
    skipNotice: string | null;
    /** First clean item in cursor order — the בדיקה ידנית entry (R12/AM1). */
    manualReviewId: string | null;
    newIds: ReadonlySet<string>;
}) {
    if (items.length === 0 && !skipNotice) return null;
    const visible = showAll ? items : items.slice(0, COLLAPSED_ROWS);

    return (
        <ZoneCard
            testId="zone-clean"
            className="!border-[#CDEBE4]"
            dotClass="bg-batch-seg-clean"
            title={ZONE_CLEAN_TITLE(items.length)}
            sub={ZONE_CLEAN_SUB}
            actions={
                <>
                    {manualReviewId && (
                        <Link
                            href={`/batches/${batchId}/review/${manualReviewId}`}
                            className="rounded-[10px] border-[1.5px] border-primary-500 px-4 py-2 font-semibold text-batch-teal-ink hover:bg-batch-teal-soft"
                            data-testid="clean-manual-review"
                        >
                            {CLEAN_SECONDARY}
                        </Link>
                    )}
                    <button
                        onClick={onAcceptAll}
                        disabled={bulkBusy || items.length === 0}
                        className="rounded-[10px] bg-batch-green px-4 py-2 font-semibold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-45"
                        data-testid="clean-accept-all"
                    >
                        {CLEAN_PRIMARY(items.length)}
                    </button>
                </>
            }
        >
            {skipNotice && (
                <div
                    className="mx-5 mb-2 rounded-zone-sm border border-batch-amber-line bg-batch-amber-soft px-3.5 py-2.5 text-[13px] text-batch-amber-ink"
                    data-testid="clean-skip-notice"
                >
                    {skipNotice}
                </div>
            )}
            {items.length > 0 && (
                <div className="border-t border-batch-line-soft">
                    {visible.map((it) => {
                        const id = String(it.transcription_id);
                        const isOpen = expanded.has(id);
                        const dimmed = accepting.has(id);
                        return (
                            <div key={id} className={dimmed ? 'opacity-45' : undefined}>
                                <button
                                    onClick={() => onToggle(id)}
                                    className={`flex w-full flex-wrap items-center gap-3.5 border-b border-batch-line-soft px-5 py-2.5 text-start hover:bg-[#FBFAF6] ${newIds.has(id) ? 'motion-safe:animate-fade-in bg-batch-teal-soft/40' : ''}`}
                                    data-testid="clean-row"
                                >
                                    <span className="min-w-[180px] flex-1">
                                        <span className="font-medium">{it.filename ?? NO_FILENAME}</span>{' '}
                                        <span className="text-[12.5px] text-batch-muted">
                                            {CLEAN_ROW_META(
                                                it.matched_student_name ?? '—',
                                                it.draft.page_count,
                                                it.draft.answers.length,
                                            )}
                                        </span>
                                    </span>
                                    <span
                                        className={`flex-none text-batch-faint transition-transform ${isOpen ? 'rotate-180' : ''}`}
                                    >
                                        ▾
                                    </span>
                                </button>
                                {isOpen && (
                                    <div
                                        className="border-b border-dashed border-batch-line bg-[#FBFDFC] px-5 py-3"
                                        data-testid="clean-peek"
                                    >
                                        {it.draft.answers.map((a) => (
                                            <div
                                                key={answerTargetId(a)}
                                                className="mb-2 rounded-zone-sm border border-batch-line-soft bg-white px-3 py-2.5"
                                            >
                                                <h5 className="mb-1.5 text-[12.5px] font-medium text-batch-muted">
                                                    {keyLabelOf(a)}
                                                </h5>
                                                {a.answer_text.trim() === '' ? (
                                                    <StatusChip hue="amber" className="!text-[11.5px]">
                                                        {EMPTY_ANSWER_MARKER}
                                                    </StatusChip>
                                                ) : (
                                                    <div
                                                        className="overflow-hidden whitespace-pre-wrap font-mono text-[12.5px] leading-[1.65]"
                                                        dir="ltr"
                                                        style={{ textAlign: 'left' }}
                                                    >
                                                        {a.answer_text
                                                            .split('\n')
                                                            .slice(0, PEEK_LINES)
                                                            .join('\n')}
                                                        {a.answer_text.split('\n').length > PEEK_LINES
                                                            ? '\n…'
                                                            : ''}
                                                    </div>
                                                )}
                                            </div>
                                        ))}
                                        <div className="text-left">
                                            <Link
                                                href={`/batches/${batchId}/review/${id}`}
                                                className="text-[13px] text-batch-teal-ink hover:underline"
                                            >
                                                {CLEAN_OPEN_FULL}
                                            </Link>
                                        </div>
                                    </div>
                                )}
                            </div>
                        );
                    })}
                    {!showAll && items.length > COLLAPSED_ROWS && (
                        <button
                            onClick={onShowAll}
                            className="w-full px-5 py-2.5 text-center text-[12.5px] text-batch-faint hover:text-batch-muted"
                            data-testid="clean-show-all"
                        >
                            {CLEAN_SHOW_ALL(items.length)} ▾
                        </button>
                    )}
                </div>
            )}
        </ZoneCard>
    );
}
