'use client';

/**
 * §5.1E — a finished stage collapses to ONE LINE.
 *
 * It used to be a full green-check card with a statistic, which is the shape of
 * an ending. Four of six steps were still ahead. A stage that is behind her
 * should take up the space of a fact, not the space of a conclusion — and it
 * stays expandable, because "which thirty did I approve" is a question she is
 * entitled to answer without leaving the page.
 */

import { useState } from 'react';
import Link from 'next/link';

import { NO_FILENAME, STRIP_COLLAPSE, STRIP_EXPAND } from '@/copy/batch';
import type { BatchTranscriptionItem } from '@/types/batch';

export function CompletedStageStrip({ label, items, batchId, testId }: {
    label: string;
    items: readonly BatchTranscriptionItem[];
    batchId: string;
    testId?: string;
}) {
    const [open, setOpen] = useState(false);

    return (
        <section
            data-testid={testId ?? 'completed-stage-strip'}
            className="rounded-zone border border-batch-line bg-white px-5 py-3"
        >
            <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-[14px] font-medium text-batch-muted">{label}</p>
                {items.length > 0 && (
                    <button
                        type="button"
                        onClick={() => setOpen((v) => !v)}
                        className="text-[13px] text-batch-teal-ink hover:underline"
                        aria-expanded={open}
                        data-testid="strip-toggle"
                    >
                        {open ? STRIP_COLLAPSE : STRIP_EXPAND}
                    </button>
                )}
            </div>
            {open && (
                <ul className="mt-2.5 grid gap-1 border-t border-batch-line-soft pt-2.5
                    sm:grid-cols-2 lg:grid-cols-3">
                    {items.map((item) => {
                        const id = String(item.transcription_id);
                        return (
                            <li key={id}>
                                <Link
                                    href={`/batches/${batchId}/review/${id}`}
                                    className="block truncate text-[13px] text-batch-muted hover:text-batch-teal-ink"
                                >
                                    {item.matched_student_name
                                        ?? item.student_name_suggestion
                                        ?? item.filename
                                        ?? NO_FILENAME}
                                </Link>
                            </li>
                        );
                    })}
                </ul>
            )}
        </section>
    );
}
