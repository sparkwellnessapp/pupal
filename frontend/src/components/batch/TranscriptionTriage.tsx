'use client';

/**
 * §5.3C — the triaged grid: the transcription gate as a stack of papers.
 *
 * It replaces two row-lists (`CleanPanel`'s expandable text rows and
 * `NeedsEyesQueue`'s chip rows). The rows were dense and correct and told her
 * nothing she could recognise: a teacher holding thirty papers identifies them
 * by LOOKING at them, and every row on the old surface was a filename. The
 * page-1 thumbnail is not decoration — it is how she knows whose test this is
 * before the student name has been resolved at all.
 *
 * ── NEEDS-A-LOOK COMES FIRST, ALWAYS ──────────────────────────────────────
 * The section that owes her judgement is rendered above the one she can clear
 * in a single click. Ordering the cheap action first would train the click and
 * leave the flagged documents below the fold on a thirty-paper evening.
 *
 * ── THIS COMPONENT DOES NOT TRIAGE ────────────────────────────────────────
 * Section membership arrives already decided (`assignZones`, from the server's
 * own verdict). The reason lines and the completeness sentence are SENTENCES
 * about that decision, never a second opinion on it — a client that re-sorted
 * here would be the two-derivations failure the stage model exists to end.
 */

import Link from 'next/link';

import { ZoneCard } from '@/components/batch/ZoneCard';
import { usePageThumbnails } from '@/components/grade-review/usePageThumbnails';
import {
    CLEAN_CARD_BADGE, CLEAN_PENDING_STUDENTS, CLEAN_PRIMARY, CLEAN_SECONDARY,
    flagReasonLabel,
    CLEAN_SHOW_ALL, EYES_PRIMARY, EYES_ROW_CTA, EYES_UNIDENTIFIED,
    NO_FILENAME, ZONE_CLEAN_SUB, ZONE_CLEAN_TITLE, ZONE_EYES_SUB, ZONE_EYES_TITLE,
} from '@/copy/batch';
import { deriveCompleteness } from '@/utils/transcription-completeness';
import { reasonLinesFor } from '@/utils/triage-reason';
import { isIdentityPending } from '@/utils/zone-assignment';
import type { AnswerSpaceSelectionGroup } from '@/types/transcription';
import type { BatchTranscriptionItem } from '@/types/batch';

const COLLAPSED_CARDS = 12;

/** What a card needs, independent of which section it is in. */
function CardShell({
    item, href, testId, caption, footer, fresh, dimmed, registerThumb, thumbUrl,
}: {
    item: BatchTranscriptionItem;
    href: string;
    testId: string;
    /** The line(s) under the name — a reason rail or the completeness sentence. */
    caption: React.ReactNode;
    footer: React.ReactNode;
    fresh: boolean;
    dimmed: boolean;
    registerThumb: (el: Element | null, path: string | null) => void;
    thumbUrl: string | null;
}) {
    const name = item.matched_student_name
        ?? item.student_name_suggestion
        ?? item.filename
        ?? NO_FILENAME;
    const unidentified = !item.matched_student_name && !item.student_name_suggestion;

    return (
        <Link
            href={href}
            data-testid={testId}
            className={[
                'group block rounded-zone-sm border border-batch-line bg-white p-2.5',
                'transition-all hover:border-primary-300 hover:shadow-zone',
                fresh ? 'motion-safe:animate-fade-in bg-batch-teal-soft/40' : '',
                dimmed ? 'opacity-45' : '',
            ].join(' ')}
        >
            <div
                ref={(el) => registerThumb(el, item.page1_image_url ?? null)}
                className="relative mb-2 aspect-[1/1.32] overflow-hidden rounded border
                    border-batch-line-soft bg-surface-50"
            >
                {thumbUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                        src={thumbUrl}
                        alt=""
                        className="absolute inset-0 h-full w-full object-cover object-top"
                    />
                ) : null}
            </div>
            {/* §5.3C — the student's name, or the FILENAME marked as
                unidentified. The filename is kept rather than replaced: until
                she says who this is, it is the only handle she has on the
                paper, and «לא זוהה» alone on three cards is three cards she
                cannot tell apart. */}
            <p
                className={[
                    'truncate text-[13.5px] font-medium',
                    unidentified ? 'text-batch-amber-ink' : 'text-batch-ink',
                ].join(' ')}
                title={name}
            >
                {name}
                {unidentified && (
                    <span className="ms-1.5 rounded-full bg-batch-amber-soft px-1.5
                        py-0.5 text-[10.5px] font-normal text-batch-amber-ink">
                        {EYES_UNIDENTIFIED}
                    </span>
                )}
            </p>
            {caption}
            {footer}
        </Link>
    );
}

export interface TranscriptionTriageProps {
    eyesRows: BatchTranscriptionItem[];
    cleanRows: BatchTranscriptionItem[];
    batchId: string;
    selectionGroups: AnswerSpaceSelectionGroup[];
    /** First stop of the keyboard review walk. */
    firstReviewId: string | null;
    /** The clean transcription «הצגת תמלול אחד לדוגמה» opens. */
    sampleCleanId: string | null;
    /** ZC-1 v2: the bulk POST's real payload — identity-pending cards are in
     *  this section but the server would refuse them, so the button never
     *  claims them. */
    acceptableCount: number;
    pendingCount: number;
    accepting: ReadonlySet<string>;
    bulkBusy: boolean;
    onAcceptAll: () => void;
    skipNotice: string | null;
    showAll: boolean;
    onShowAll: () => void;
    newIds: ReadonlySet<string>;
    /** On her first batch the sample sits BESIDE the primary; later it is a
     *  quieter text link, because by then she knows what a transcription is. */
    isFirstBatch: boolean;
}

export function TranscriptionTriage(props: TranscriptionTriageProps) {
    const {
        eyesRows, cleanRows, batchId, selectionGroups, firstReviewId, sampleCleanId,
        acceptableCount, pendingCount, accepting, bulkBusy, onAcceptAll,
        skipNotice, showAll, onShowAll, newIds, isFirstBatch,
    } = props;
    // ONE thumbnail cache across both sections: the page polls, and a per-card
    // fetch would re-allocate a blob per card per tick.
    const { register, urlFor } = usePageThumbnails();

    const visibleClean = showAll ? cleanRows : cleanRows.slice(0, COLLAPSED_CARDS);

    return (
        <>
            {/* ── section 1 · needs a look, FIRST ───────────────────────── */}
            {eyesRows.length > 0 && (
                <ZoneCard
                    testId="zone-eyes"
                    className="!border-batch-amber-line"
                    dotClass="bg-batch-seg-eyes"
                    title={ZONE_EYES_TITLE(eyesRows.length)}
                    sub={ZONE_EYES_SUB}
                    actions={
                        firstReviewId && (
                            <Link
                                href={`/batches/${batchId}/review/${firstReviewId}`}
                                className="rounded-[10px] bg-primary-500 px-4 py-2 font-semibold text-white hover:brightness-95"
                                data-testid="eyes-start-walk"
                            >
                                {EYES_PRIMARY(eyesRows.length)}
                            </Link>
                        )
                    }
                >
                    <div className="grid grid-cols-2 gap-3 border-t border-batch-line-soft px-5 py-4
                        sm:grid-cols-3 lg:grid-cols-[repeat(auto-fill,minmax(150px,1fr))]">
                        {eyesRows.map((item) => {
                            const id = String(item.transcription_id);
                            const lines = reasonLinesFor(item, selectionGroups);
                            return (
                                <CardShell
                                    key={id}
                                    item={item}
                                    testId="eyes-row"
                                    href={`/batches/${batchId}/review/${id}`}
                                    fresh={newIds.has(id)}
                                    dimmed={false}
                                    registerThumb={register}
                                    thumbUrl={urlFor(item.page1_image_url)}
                                    caption={
                                        lines.length > 0 ? (
                                            <p
                                                className="mt-0.5 text-[12px] leading-snug text-batch-amber-ink"
                                                data-testid="eyes-reason"
                                            >
                                                {lines.join(' · ')}
                                            </p>
                                        ) : null
                                    }
                                    footer={
                                        <span className="mt-1.5 inline-block rounded-[8px] bg-[#F3F0E9]
                                            px-2.5 py-1 text-[12px] font-semibold text-batch-ink
                                            group-hover:brightness-95">
                                            {EYES_ROW_CTA}
                                        </span>
                                    }
                                />
                            );
                        })}
                    </div>
                </ZoneCard>
            )}

            {/* ── section 2 · read with full confidence ─────────────────── */}
            {(cleanRows.length > 0 || skipNotice) && (
                <ZoneCard
                    testId="zone-clean"
                    className="!border-[#CDEBE4]"
                    dotClass="bg-batch-seg-clean"
                    title={ZONE_CLEAN_TITLE(cleanRows.length)}
                    sub={ZONE_CLEAN_SUB}
                    actions={
                        <>
                            {sampleCleanId && (
                                <Link
                                    href={`/batches/${batchId}/review/${sampleCleanId}`}
                                    className={isFirstBatch
                                        ? 'rounded-[10px] border-[1.5px] border-primary-500 px-4 py-2 font-semibold text-batch-teal-ink hover:bg-batch-teal-soft'
                                        : 'px-1 py-2 text-[13px] text-batch-teal-ink hover:underline'}
                                    data-testid="clean-manual-review"
                                >
                                    {CLEAN_SECONDARY}
                                </Link>
                            )}
                            <button
                                onClick={onAcceptAll}
                                disabled={bulkBusy || acceptableCount === 0}
                                className="rounded-[10px] bg-batch-green px-4 py-2 font-semibold text-white hover:brightness-95 disabled:cursor-not-allowed disabled:opacity-45"
                                data-testid="clean-accept-all"
                            >
                                {CLEAN_PRIMARY(acceptableCount)}
                            </button>
                        </>
                    }
                >
                    {pendingCount > 0 && (
                        <div
                            className="mx-5 mb-2 rounded-zone-sm border border-batch-teal-soft bg-batch-teal-soft/50 px-3.5 py-2.5 text-[13px] text-batch-teal-ink"
                            data-testid="clean-pending-note"
                        >
                            {CLEAN_PENDING_STUDENTS(pendingCount)}
                        </div>
                    )}
                    {skipNotice && (
                        <div
                            className="mx-5 mb-2 rounded-zone-sm border border-batch-amber-line bg-batch-amber-soft px-3.5 py-2.5 text-[13px] text-batch-amber-ink"
                            data-testid="clean-skip-notice"
                        >
                            {skipNotice}
                        </div>
                    )}
                    {cleanRows.length > 0 && (
                        <>
                            <div className="grid grid-cols-2 gap-3 border-t border-batch-line-soft px-5 py-4
                                sm:grid-cols-3 lg:grid-cols-[repeat(auto-fill,minmax(150px,1fr))]">
                                {visibleClean.map((item) => {
                                    const id = String(item.transcription_id);
                                    const { sentence } = deriveCompleteness(
                                        item.draft.answers.map((x) => ({
                                            question_number: x.question_number,
                                            sub_question_id: x.sub_question_id,
                                            text: x.answer_text,
                                        })),
                                        selectionGroups,
                                    );
                                    return (
                                        <CardShell
                                            key={id}
                                            item={item}
                                            testId="clean-row"
                                            href={`/batches/${batchId}/review/${id}`}
                                            fresh={newIds.has(id)}
                                            dimmed={accepting.has(id)}
                                            registerThumb={register}
                                            thumbUrl={urlFor(item.page1_image_url)}
                                            caption={
                                                sentence ? (
                                                    <p
                                                        className="mt-0.5 text-[12px] leading-snug text-batch-muted"
                                                        data-testid="clean-completeness"
                                                    >
                                                        {sentence}
                                                    </p>
                                                ) : null
                                            }
                                            footer={
                                                // ZC-1 v2: an identity-pending card lives HERE but
                                                // the server would refuse it, so its badge says why
                                                // rather than claiming «מוכן לאישור». The section
                                                // note counts them; the card says WHICH — with
                                                // twelve cards, a count alone sends her hunting.
                                                isIdentityPending(item) ? (
                                                    <span className="mt-1.5 inline-block rounded-full
                                                        bg-batch-amber-soft px-2.5 py-0.5 text-[11.5px]
                                                        font-medium text-batch-amber-ink"
                                                        data-testid="clean-pending-badge">
                                                        {flagReasonLabel('student_unassigned')}
                                                    </span>
                                                ) : (
                                                    <span className="mt-1.5 inline-block rounded-full
                                                        bg-batch-green-soft px-2.5 py-0.5 text-[11.5px]
                                                        font-medium text-batch-green-ink">
                                                        {CLEAN_CARD_BADGE}
                                                    </span>
                                                )
                                            }
                                        />
                                    );
                                })}
                            </div>
                            {!showAll && cleanRows.length > COLLAPSED_CARDS && (
                                <button
                                    onClick={onShowAll}
                                    className="w-full px-5 pb-3 text-center text-[12.5px] text-batch-faint hover:text-batch-muted"
                                    data-testid="clean-show-all"
                                >
                                    {CLEAN_SHOW_ALL(cleanRows.length)} ▾
                                </button>
                            )}
                        </>
                    )}
                </ZoneCard>
            )}
        </>
    );
}
