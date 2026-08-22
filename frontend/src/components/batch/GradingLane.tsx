/**
 * D9 — the grading lane: subordinate one-liner while transcription decisions
 * remain (AM2 copy, no CTA); once every transcription is terminal it becomes
 * the prominent next-stage card with the CTA that reveals the grade-review
 * section (the completed tab's own stage).
 */
import { ZoneCard } from '@/components/batch/ZoneCard';
import { LANE_COMPLETED, LANE_CTA, LANE_SUBORDINATE } from '@/copy/batch';

export function GradingLane({
    variant,
    draftCount,
    gradingCount,
    onOpenGrades,
}: {
    variant: 'subordinate' | 'completed';
    draftCount: number;
    gradingCount: number;
    onOpenGrades: () => void;
}) {
    if (variant === 'subordinate') {
        if (draftCount === 0 && gradingCount === 0) return null; // degrade by omission
        return (
            <ZoneCard testId="grading-lane" title={
                <span className="flex items-center gap-3 text-[13.5px] font-normal text-batch-muted">
                    🎓 <span><b className="font-semibold text-batch-ink">בדיקת ציונים</b>{' '}
                    {LANE_SUBORDINATE(draftCount).replace('בדיקת ציונים · ', '· ')}</span>
                </span>
            } />
        );
    }
    // E1 (closeout, owner-ruled): the SAME zero-guard its subordinate sibling
    // has always had. Without it the completed lane rendered
    // "ויוי בודקת את המבחנים — 0 כבר נבדקו, 0 בעבודה" plus a CTA: a
    // present-tense claim about work that is not happening. Degrade by
    // omission — the hero stands alone.
    if (draftCount === 0 && gradingCount === 0) return null;

    return (
        <ZoneCard
            testId="grading-lane"
            className="!border-[#CBE4F3] bg-gradient-to-b from-[#F3F9FD] to-white"
            title={
                <span className="flex items-center gap-3 text-[15px]">
                    🎓 <span><b>בדיקת ציונים</b> · {LANE_COMPLETED(draftCount, gradingCount)}</span>
                </span>
            }
            actions={
                <button
                    onClick={onOpenGrades}
                    className="rounded-[10px] bg-primary-500 px-4 py-2 font-semibold text-white hover:brightness-95"
                    data-testid="lane-open-grades"
                >
                    {LANE_CTA}
                </button>
            }
        />
    );
}
