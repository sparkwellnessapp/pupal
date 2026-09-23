'use client';

import type { CheckKind, Verdict } from '@/lib/pricing';
import {
    RV_VERDICT_TITLE, RV_VERDICT_TITLE_TARIFF, RV_VERDICT_TITLE_UNVERIFIED,
} from '@/copy/grade-review';

/**
 * The verdict control (R7/R8) — ✓ / ½ / ✗, one click or Space to cycle.
 *
 * THE INK GRAMMAR (owner ruling 2026-09-13, replacing the pencil/violet/red
 * scheme): every ✓ is GREEN, every ½ is YELLOW, every ✗ is RED — the verdict
 * itself carries its colour, so a glance down the column reads the grade. A
 * verdict SHE decided is TURQUOISE (the product's own primary) with a ring:
 * her marks stand out from Vivi's proposals across the room, and red no
 * longer means "the teacher" anywhere on this surface — it means "wrong".
 *
 * A TARIFF (a deduction, ruling 2026-09-13) is BINARY: ✓ means no deduction,
 * ✗ means deducted. There is no half state — the pricer coerces `partially_met`
 * to fired, and a ½ glyph that silently deducted the full amount was the trap
 * the ruling removed. A legacy `partially_met` on a tariff therefore RENDERS
 * as ✗, which is what it prices as; the next press takes it to ✓.
 *
 * Points on a credit row are typeable beside this control (OD-R2); a tariff
 * row is toggle-only, because a yes/no has no number to type.
 *
 * AN UNVERIFIED ✓ LOOKS UNVERIFIED (2026-09-15). When Vivi's credit verdict
 * cites a span the validator could not find, the pricer refuses the credit —
 * the row is worth 0 — and this control used to draw the same green ✓ as a
 * credited one, so a teacher read «fully correct» next to «0 / 5»
 * (graded_test a0cd07ff). It now draws amber and dashed, says why in its
 * title, and one press CONFIRMS it as hers (see `verdict-cycle.ts`).
 */

const GLYPH: Readonly<Record<Verdict, string>> = {
    // ALPHA-GAP A-1 (D-3): three verdicts, because beta has no bands to choose between. Alpha adds a
    // band picker here — she selects PARTIALLY CORRECT and the pricer takes that band's points.
    met: '✓',
    partially_met: '½',
    not_met: '✗',
};

/** The glyph a verdict shows on a row of this kind — a tariff has no ½. */
export function glyphFor(verdict: Verdict, kind: CheckKind = 'required'): string {
    if (kind === 'tariff' && verdict === 'partially_met') return GLYPH.not_met;
    return GLYPH[verdict];
}

/** Proposal colours: the verdict carries its own. */
const PROPOSAL_TONE: Readonly<Record<Verdict, string>> = {
    met: 'text-grade-green',
    partially_met: 'text-grade-yellow',
    not_met: 'text-grade-red',
};

export interface VerdictButtonProps {
    verdict: Verdict;
    /** She decided something different from Vivi. */
    overridden: boolean;
    /** A tariff row toggles between two states and never shows ½. */
    kind?: CheckKind;
    /** Vivi's credit verdict on a span she could not verify — worth 0 until confirmed. */
    unverified?: boolean;
    onCycle: () => void;
    disabled?: boolean;
}

export function VerdictButton({
    verdict, overridden, kind = 'required', unverified = false, onCycle, disabled = false,
}: VerdictButtonProps) {
    const shown = kind === 'tariff' && verdict === 'partially_met' ? 'not_met' : verdict;
    const title = unverified ? RV_VERDICT_TITLE_UNVERIFIED
        : kind === 'tariff' ? RV_VERDICT_TITLE_TARIFF : RV_VERDICT_TITLE;
    return (
        <button
            type="button"
            // The control is a CYCLE, so the label says what pressing it does,
            // not what it currently shows — a screen reader hearing only "✓"
            // would have no idea it is actionable.
            aria-label={`${GLYPH[shown]} — ${title}`}
            title={title}
            data-verdict={verdict}
            data-verdict-shown={unverified ? 'unverified' : shown}
            data-overridden={overridden ? 'true' : 'false'}
            disabled={disabled}
            onClick={(event) => { event.stopPropagation(); onCycle(); }}
            className={[
                'grid h-verdict w-verdict place-items-center rounded-full bg-grade-card',
                'text-gr-body font-bold leading-none transition-colors',
                'disabled:cursor-not-allowed disabled:opacity-40',
                overridden
                    ? 'border-decided border-primary-600 text-primary-600 ring-decided ring-primary-100'
                    : unverified
                        ? 'border-hairline border-dashed border-grade-amber-dot text-grade-amber'
                        : `border-hairline border-current ${PROPOSAL_TONE[shown]}`,
            ].join(' ')}
        >
            {GLYPH[shown]}
        </button>
    );
}

export { GLYPH as VERDICT_GLYPH };
