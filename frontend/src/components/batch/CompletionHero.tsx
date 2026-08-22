/**
 * D10 — the completion hero (peak-end): this page's success metric is every
 * TRANSCRIPTION approved — grades are the next stage's story. Stats are only
 * what is honestly derivable; everything else degrades by omission (the
 * mockup's bulk-vs-manual split and activity ledger are deliberately absent
 * — spec-over-mockup, see the P2 reconciliation table).
 */
import { ZoneCard } from '@/components/batch/ZoneCard';
import {
    HERO_DURATION,
    HERO_STAT_APPROVED,
    HERO_STAT_STUDENTS,
    HERO_TITLE,
} from '@/copy/batch';

export function CompletionHero({
    total,
    approvedTranscriptions,
    durationMinutes,
    sessionCreatedStudents,
}: {
    total: number;
    approvedTranscriptions: number;
    durationMinutes: number | null;
    sessionCreatedStudents: number;
}) {
    return (
        <ZoneCard testId="completion-hero" title="">
            <div className="px-6 pb-8 pt-4 text-center">
                <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-full bg-batch-green text-3xl text-white motion-safe:animate-check-pop">
                    ✓
                </div>
                <h2 className="mb-1.5 text-2xl font-bold text-batch-ink">{HERO_TITLE(total)}</h2>
                {durationMinutes !== null && (
                    <div className="text-batch-muted">{HERO_DURATION(durationMinutes)}</div>
                )}
                <div className="mt-4 flex flex-wrap justify-center gap-7">
                    <div className="text-center">
                        <b className="block text-[22px] font-bold text-batch-ink">
                            {approvedTranscriptions}
                        </b>
                        <span className="text-[12.5px] text-batch-muted">{HERO_STAT_APPROVED}</span>
                    </div>
                    {sessionCreatedStudents > 0 && (
                        <div className="text-center">
                            <b className="block text-[22px] font-bold text-batch-ink">
                                {sessionCreatedStudents}
                            </b>
                            <span className="text-[12.5px] text-batch-muted">
                                {HERO_STAT_STUDENTS}
                            </span>
                        </div>
                    )}
                </div>
            </div>
        </ZoneCard>
    );
}
