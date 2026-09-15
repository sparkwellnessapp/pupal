/**
 * Points, as a teacher reads them.
 *
 * The pricer speaks in exact `Decimal` strings — `"4.00"`, `"7.50"`, `"0"` —
 * because that is what the server computes and freezes, and the parity vectors
 * are byte-exact on it. None of that belongs on screen: nobody writes `4.00`
 * on a test, and a column of `1.00 / 1` reads like a spreadsheet rather than a
 * mark. The mockup's own numbers are `9 / 10`, `3 / 3`, `2 / 2`.
 *
 * So the exact value travels and the DISPLAY is trimmed — trailing zeros only,
 * never rounding. `0.75` stays `0.75` because a quarter point is a real thing
 * she awards; `7.50` becomes `7.5`; `4.00` becomes `4`.
 *
 * Pure string work, no `Number` round-trip: parsing to float to re-format is
 * how `0.1 + 0.2` gets onto a screen.
 */

import { cmp, dec, sub, toString, type Dec } from '@/lib/decimal';

export function formatPoints(value: string | null | undefined): string {
    if (value == null || value === '') return '';
    const text = String(value).trim();

    // Anything unexpected (a scientific form, a stray label) is passed through
    // untouched rather than mangled — showing the raw value is honest, and
    // silently reformatting something this function does not understand is not.
    if (!/^-?\d+(\.\d+)?$/.test(text)) return text;
    if (!text.includes('.')) return text;

    const trimmed = text.replace(/0+$/, '').replace(/\.$/, '');
    // `-0.00` trims to `-0`, and a teacher reading «-0» on a check would think
    // something was subtracted. Any all-zero result is plain zero.
    if (/^-?0*$/.test(trimmed.replace('.', ''))) return '0';
    return trimmed;
}

/** «7.5 / 10» — the pair, both trimmed, in one place. */
export function formatPointsPair(awarded: string, possible: string): string {
    return `${formatPoints(awarded)} / ${formatPoints(possible)}`;
}

/**
 * §5.5 — what was LOST, trimmed for display. `null` when nothing was.
 *
 * The subtraction rides the pricer's own exact decimal (`lib/decimal.ts`), not
 * `Number`: these are the strings the server froze, and `0.1 + 0.2` reaching a
 * screen through a float round-trip is the exact failure that module exists to
 * prevent. It DERIVES nothing new — `possible` and `awarded` are already on the
 * model — so it cannot disagree with the pair rendered beside it.
 *
 * A non-numeric or negative result yields `null`: the honest response to an
 * input this function does not understand is to render no deduction, never a
 * figure it cannot stand behind.
 */
export function subtractPoints(
    possible: string | null | undefined,
    awarded: string | null | undefined,
): string | null {
    if (possible == null || awarded == null) return null;
    let diff: Dec;
    try {
        diff = sub(dec(String(possible)), dec(String(awarded)));
    } catch {
        return null;
    }
    if (cmp(diff, dec('0')) <= 0) return null;
    return formatPoints(toString(diff));
}
