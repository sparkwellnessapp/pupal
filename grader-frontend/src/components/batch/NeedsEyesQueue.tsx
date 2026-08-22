/**
 * D6 — the needs-eyes queue: rows for content-flagged items, teacher-touched
 * clean items (Δ1), and unmatched-identity items. Chips say exactly WHY
 * (C1/FLAG_REASON_LABELS), with derivable counts for missing answers and
 * unclear markers. The primary starts the keyboard review walk.
 */
import Link from 'next/link';

import { StatusChip } from '@/components/batch/StatusChip';
import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    CHIP_EDITED,
    CHIP_MISSING_WITH_COUNT,
    CHIP_UNCLEAR_WITH_COUNT,
    EYES_PRIMARY,
    EYES_ROW_CTA,
    EYES_UNMATCHED_NOTE,
    flagReasonLabel,
    NO_FILENAME,
    ZONE_EYES_SUB,
    ZONE_EYES_TITLE,
} from '@/copy/batch';
import { missingAnswersCount, unclearCount } from '@/utils/batch-dashboard';
import type { AnswerSpaceSelectionGroup } from '@/utils/selection-expectation';
import type { BatchTranscriptionItem } from '@/types/batch';

function chipsFor(
    item: BatchTranscriptionItem,
    groups: AnswerSpaceSelectionGroup[],
): string[] {
    const chips: string[] = [];
    for (const r of item.flag_verdict.reasons) {
        if (r === 'student_unassigned' || r === 'student_unmatched') continue; // identity renders as the row note / wave
        if (r === 'missing_answers') {
            // Derived count 0 with a set flag = inconsistent payload; render
            // the plain label rather than a lying "· 0".
            const n = missingAnswersCount(item.draft, groups);
            chips.push(n > 0 ? CHIP_MISSING_WITH_COUNT(n) : (flagReasonLabel(r)));
        } else if (r === 'unparseable') {
            const n = unclearCount(item.draft);
            chips.push(n > 0 ? CHIP_UNCLEAR_WITH_COUNT(n) : (flagReasonLabel(r)));
        } else {
            chips.push(flagReasonLabel(r));
        }
    }
    return chips;
}

export function NeedsEyesQueue({
    rows,
    batchId,
    selectionGroups,
    firstReviewId,
    newIds,
}: {
    rows: BatchTranscriptionItem[];
    batchId: string;
    selectionGroups: AnswerSpaceSelectionGroup[];
    firstReviewId: string | null;
    newIds: ReadonlySet<string>;
}) {
    if (rows.length === 0) return null;
    return (
        <ZoneCard
            testId="zone-eyes"
            className="!border-batch-amber-line"
            dotClass="bg-batch-seg-eyes"
            title={ZONE_EYES_TITLE(rows.length)}
            sub={ZONE_EYES_SUB}
            actions={
                firstReviewId && (
                    <Link
                        href={`/batches/${batchId}/review/${firstReviewId}`}
                        className="rounded-[10px] bg-primary-500 px-4 py-2 font-semibold text-white hover:brightness-95"
                        data-testid="eyes-start-walk"
                    >
                        {EYES_PRIMARY(rows.length)}
                    </Link>
                )
            }
        >
            <div className="border-t border-batch-line-soft">
                {rows.map((it) => {
                    const id = String(it.transcription_id);
                    const unmatched = it.flag_verdict.reasons.includes('student_unmatched');
                    // ZC-1: unassigned-only items are ROWS now (they used to
                    // exist only as wave pills). Their note shows the
                    // extracted NEW name + why it still needs her.
                    const unassigned = !it.matched_student_name
                        && it.flag_verdict.reasons.includes('student_unassigned');
                    return (
                        <div
                            key={id}
                            className={`flex flex-wrap items-center gap-3.5 border-b border-batch-line-soft px-5 py-2.5 last:border-b-0 ${newIds.has(id) ? 'motion-safe:animate-fade-in bg-batch-teal-soft/40' : ''}`}
                            data-testid="eyes-row"
                        >
                            <span className="min-w-[180px] flex-1">
                                <span className="font-medium">{it.filename ?? NO_FILENAME}</span>{' '}
                                {it.matched_student_name ? (
                                    <span className="text-[12.5px] text-batch-muted">
                                        ← {it.matched_student_name}
                                    </span>
                                ) : unassigned && it.student_name_suggestion ? (
                                    <span className="text-[12.5px] text-batch-amber-ink" data-testid="eyes-unassigned-note">
                                        ← {it.student_name_suggestion} · {flagReasonLabel('student_unassigned')}
                                    </span>
                                ) : unmatched ? (
                                    <span className="text-[12.5px] text-batch-amber-ink">
                                        {EYES_UNMATCHED_NOTE}
                                    </span>
                                ) : null}
                            </span>
                            {chipsFor(it, selectionGroups).map((c) => (
                                <StatusChip key={c} hue="amber">
                                    {c}
                                </StatusChip>
                            ))}
                            {it.review != null && <StatusChip hue="blue">{CHIP_EDITED}</StatusChip>}
                            <Link
                                href={`/batches/${batchId}/review/${id}`}
                                className="rounded-[10px] bg-[#F3F0E9] px-3.5 py-1.5 font-semibold text-batch-ink hover:brightness-95"
                            >
                                {EYES_ROW_CTA}
                            </Link>
                        </div>
                    );
                })}
            </div>
        </ZoneCard>
    );
}
