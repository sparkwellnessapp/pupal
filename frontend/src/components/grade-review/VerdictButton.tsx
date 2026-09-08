'use client';

import type { Verdict } from '@/lib/pricing';
import { RV_VERDICT_TITLE } from '@/copy/grade-review';

/**
 * The verdict control (R7/R8) — ✓ / ½ / ✗, one click or Space to cycle.
 *
 * THE INK GRAMMAR, made mechanical (§0.3): teal ✓, violet ½, grey ✗ are Vivi
 * PROPOSING. The instant the teacher decides something different the glyph goes
 * TEACHER RED and gains a ring — the same red as the stamp and the total, and
 * red appears nowhere else on this surface. She can see what she has touched
 * from across the room, which is what makes a thirty-paper evening reviewable.
 *
 * There is NO numeric input anywhere in this module. She judges a requirement
 * met, half met or not met; the pricer turns that into points. Letting her type
 * a number would put two derivations of one figure on the same screen — the
 * §5 catastrophe — and would ask her to do the arithmetic Vivi exists to remove.
 */

const GLYPH: Readonly<Record<Verdict, string>> = {
    met: '✓',
    partially_met: '½',
    not_met: '✗',
};

/** Proposal colours. Overridden state overrides all three. */
const PROPOSAL_TONE: Readonly<Record<Verdict, string>> = {
    met: 'text-primary-600',
    partially_met: 'text-grade-violet',
    not_met: 'text-grade-pencil-2',
};

export interface VerdictButtonProps {
    verdict: Verdict;
    /** She decided something different from Vivi. */
    overridden: boolean;
    onCycle: () => void;
    disabled?: boolean;
}

export function VerdictButton({
    verdict, overridden, onCycle, disabled = false,
}: VerdictButtonProps) {
    return (
        <button
            type="button"
            // The control is a CYCLE, so the label says what pressing it does,
            // not what it currently shows — a screen reader hearing only "✓"
            // would have no idea it is actionable.
            aria-label={`${GLYPH[verdict]} — ${RV_VERDICT_TITLE}`}
            title={RV_VERDICT_TITLE}
            data-verdict={verdict}
            data-overridden={overridden ? 'true' : 'false'}
            disabled={disabled}
            onClick={(event) => { event.stopPropagation(); onCycle(); }}
            className={[
                'grid h-verdict w-verdict place-items-center rounded-full bg-grade-card',
                'text-gr-body font-bold leading-none transition-colors',
                'disabled:cursor-not-allowed disabled:opacity-40',
                overridden
                    ? 'border-decided border-grade-red text-grade-red ring-decided ring-grade-red-100'
                    : `border-hairline border-current ${PROPOSAL_TONE[verdict]}`,
            ].join(' ')}
        >
            {GLYPH[verdict]}
        </button>
    );
}

export { GLYPH as VERDICT_GLYPH };
