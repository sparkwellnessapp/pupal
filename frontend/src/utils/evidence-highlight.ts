/**
 * Which quote is lit in the answer, and how (R6).
 *
 * ── PRECEDENCE (spec §3) ───────────────────────────────────────────────────
 *     activeQuote = hover ?? pin ?? focus
 *
 * Read it as "the most momentary intent wins". Hover is what her mouse is
 * doing RIGHT NOW and beats a pin she set a second ago; a pin is a deliberate
 * act and beats mere keyboard focus; focus is where the arrows left her. Esc
 * releases the pin and the answer falls back to focus — nothing else clears it,
 * because a pin she has to re-set every time she moves the mouse is not a pin.
 *
 * ── THE THREE QUOTE STATES ─────────────────────────────────────────────────
 *   exact      solid teal mark. Vivi found the span verbatim.
 *   fuzzy      dashed amber underline + chip. Found, but the answer's text
 *              differs slightly — so it still earns credit (the pricer verifies
 *              it) and she is told the citation is approximate.
 *   not_found  NO MARK AT ALL, an amber chip, and no quote button.
 *
 * `not_found` is the one that matters. It is INVENTED CREDIT: the model claimed
 * a span that is not in the answer, and the score looks perfectly ordinary. The
 * refusal to paint anything is the point — highlighting a "best guess" region
 * would manufacture the very evidence the flag exists to say is missing, and
 * she would approve it. There is nothing to show, so nothing is shown.
 */

import type { QuoteStatus } from '@/lib/pricing';

export interface HighlightSource {
    /** hover ?? pin ?? focus — most momentary first. */
    hover: string | null;
    pin: string | null;
    focus: string | null;
}

/** The check whose evidence should be lit, by precedence. */
export function activeCheckId(source: HighlightSource): string | null {
    return source.hover ?? source.pin ?? source.focus ?? null;
}

export type HighlightKind = 'exact' | 'fuzzy' | 'none';

export interface Highlight {
    /** The verbatim span to mark, or null when nothing may be painted. */
    quote: string | null;
    kind: HighlightKind;
    /** A pinned highlight is drawn with the persistent underline. */
    pinned: boolean;
}

export const NO_HIGHLIGHT: Highlight = { quote: null, kind: 'none', pinned: false };

export interface HighlightableCheck {
    check_id: string;
    quote?: string | null;
    quote_status?: QuoteStatus | null;
}

/**
 * Resolve the highlight for one scope's answer.
 *
 * `scopeCheckIds` scopes the lookup: a check focused in question 2 must not
 * light up a span in question 1's answer just because the text happens to
 * repeat. Passing the wrong scope's ids is how the same quote gets painted in
 * two places at once.
 */
export function resolveHighlight(
    source: HighlightSource,
    checksById: ReadonlyMap<string, HighlightableCheck>,
    scopeCheckIds: ReadonlySet<string>,
): Highlight {
    const id = activeCheckId(source);
    if (id === null || !scopeCheckIds.has(id)) return NO_HIGHLIGHT;

    const check = checksById.get(id);
    if (!check || !check.quote) return NO_HIGHLIGHT;

    // Nothing was found, so nothing is painted. See the module doc.
    if (check.quote_status === 'not_found' || check.quote_status == null) {
        return NO_HIGHLIGHT;
    }

    return {
        quote: check.quote,
        kind: check.quote_status === 'fuzzy' ? 'fuzzy' : 'exact',
        // Hover is transient by definition, so a hovered check is never drawn
        // as pinned even when it IS the pinned one — otherwise the persistent
        // underline flickers on under the mouse.
        pinned: source.hover === null && source.pin === id,
    };
}



export interface QuoteSegment {
    text: string;
    marked: boolean;
}

/**
 * THE MATCHING CONTRACT, and it must stay identical to the server's.
 *
 * `validator.quote_match_status` decides `quote_status` like this:
 *
 *     norm_quote  = " ".join(quote.lower().split())
 *     norm_answer = " ".join(answer.lower().split())
 *     norm_quote in norm_answer  ->  EXACT
 *
 * — whitespace COLLAPSED (newlines included), case FOLDED, and matched against
 * the WHOLE answer. The client used to mark with a raw, case-sensitive
 * `line.indexOf(quote)` on ONE line at a time, which disagrees on all three
 * counts. Measured over 25 real graded tests: 1,420 quote buttons, of which
 * 338 (24%) drew NOTHING AT ALL — 23% of quotes span several lines, and a
 * five-line quote can never be a substring of a one-line string. The teacher
 * clicked the quote button, got a toast saying the quote was highlighted, and
 * saw no highlight. 99% of those misses match once the answer is treated as
 * one normalised string, which is what this does.
 *
 * So: normalise ONCE, locate in the whole answer, then map the hit back to
 * character ranges in the ORIGINAL text — because the answer renders line by
 * line (the code island needs its line numbers) and the marks must land inside
 * those lines.
 */

/** A marked span inside one rendered line. `end` is EXCLUSIVE. */
export interface LineRange {
    line: number;
    start: number;
    end: number;
}

interface Normalized {
    norm: string;
    /** `map[i]` = index in the ORIGINAL text of the character `norm[i]`. */
    map: number[];
}

/**
 * Lowercase + collapse whitespace runs to a single space, keeping a map back to
 * the original offsets. Mirrors Python's `" ".join(s.lower().split())`,
 * including its leading/trailing trim.
 *
 * `toLowerCase()` can LENGTHEN a character, so every produced character carries
 * the original index it came from rather than assuming a 1:1 walk — otherwise a
 * single such character would shift every later offset and slide the mark off
 * the quote.
 */
function normalizeWithMap(text: string): Normalized {
    const norm: string[] = [];
    const map: number[] = [];
    let pendingSpace = false;

    for (let i = 0; i < text.length; i += 1) {
        const ch = text[i];
        if (/\s/.test(ch)) {
            pendingSpace = true;
            continue;
        }
        if (pendingSpace && norm.length > 0) {
            norm.push(' ');
            map.push(i);
        }
        pendingSpace = false;
        for (const lowered of ch.toLowerCase()) {
            norm.push(lowered);
            map.push(i);
        }
    }
    return { norm: norm.join(''), map };
}

/** Dice coefficient over character bigrams. */
function diceSimilarity(a: string, b: string): number {
    if (a.length < 2 || b.length < 2) return a === b ? 1 : 0;
    const bigrams = new Map<string, number>();
    for (let i = 0; i < a.length - 1; i += 1) {
        const g = a.slice(i, i + 2);
        bigrams.set(g, (bigrams.get(g) ?? 0) + 1);
    }
    let shared = 0;
    for (let i = 0; i < b.length - 1; i += 1) {
        const g = b.slice(i, i + 2);
        const left = bigrams.get(g) ?? 0;
        if (left > 0) {
            bigrams.set(g, left - 1);
            shared += 1;
        }
    }
    return (2 * shared) / (a.length - 1 + b.length - 1);
}

/**
 * The floor below which a fuzzy quote is NOT painted.
 *
 * A fuzzy mark already renders as a dashed underline because the span is
 * approximate — but approximate is not the same as wrong, and underlining an
 * arbitrary region points the teacher at the wrong line, which is worse than
 * pointing nowhere (§3.5a: degrade by omission, never by substitution).
 */
const FUZZY_FLOOR = 0.6;

/**
 * The best approximate window for a FUZZY quote, or null.
 *
 * The server already certified this quote at >= 0.85 on its own sliding window
 * (`_best_substring_ratio`); this only has to LOCATE the region it certified.
 * Deliberately NOT a port of `difflib.SequenceMatcher`: that would be a second
 * scorer to keep in agreement with the first, and the verdict it recomputes is
 * one the server has already reached.
 */
function bestFuzzyWindow(normQuote: string, normAnswer: string): [number, number] | null {
    if (!normQuote || !normAnswer) return null;
    const size = Math.min(normQuote.length, normAnswer.length);
    const step = Math.max(1, Math.floor(normQuote.length / 8));
    let bestScore = 0;
    let bestAt = -1;

    for (let i = 0; i < normAnswer.length; i += step) {
        const score = diceSimilarity(normQuote, normAnswer.slice(i, i + size));
        if (score > bestScore) {
            bestScore = score;
            bestAt = i;
        }
        if (i + size >= normAnswer.length) break;
    }
    if (bestAt === -1 || bestScore < FUZZY_FLOOR) return null;
    return [bestAt, Math.min(bestAt + size, normAnswer.length) - 1];
}

/**
 * Where to paint the quote inside the answer, as per-line character ranges.
 *
 * Exact containment first (the 99% case), then the fuzzy window. Returns an
 * EMPTY array when the quote cannot be placed — the caller paints nothing,
 * which is the honest outcome.
 *
 * Only the FIRST occurrence is marked: this is a citation, not a highlighter
 * sweep.
 */
export function markRangesFor(answer: string, quote: string | null): LineRange[] {
    if (!quote || !answer) return [];

    const a = normalizeWithMap(answer);
    const q = normalizeWithMap(quote);
    if (!q.norm || !a.norm) return [];

    let from = a.norm.indexOf(q.norm);
    let to = from === -1 ? -1 : from + q.norm.length - 1;
    if (from === -1) {
        const window = bestFuzzyWindow(q.norm, a.norm);
        if (!window) return [];
        [from, to] = window;
    }

    // Back to ORIGINAL offsets. `to` is INCLUSIVE in normalised space, so the
    // exclusive original end is one past the character it names.
    const startOriginal = a.map[from];
    const endOriginal = a.map[to] + 1;

    const ranges: LineRange[] = [];
    let cursor = 0;
    answer.split('\n').forEach((line, index) => {
        const lineStart = cursor;
        const lineEnd = cursor + line.length;   // exclusive; excludes the newline
        cursor = lineEnd + 1;                   // +1 for the newline itself

        const start = Math.max(startOriginal, lineStart);
        const end = Math.min(endOriginal, lineEnd);
        if (start < end) {
            ranges.push({ line: index, start: start - lineStart, end: end - lineStart });
        }
    });
    return ranges;
}

/**
 * One line, split into marked / unmarked segments by that line's ranges.
 *
 * Takes RANGES rather than the quote: where the quote lives is decided once,
 * over the whole answer, by `markRangesFor`. A per-line matcher is exactly what
 * could not see a multi-line quote.
 */
export function segmentsForLine(line: string, ranges: readonly LineRange[]): QuoteSegment[] {
    if (ranges.length === 0) return [{ text: line, marked: false }];

    const segments: QuoteSegment[] = [];
    let cursor = 0;
    for (const range of ranges) {
        const start = Math.max(cursor, Math.min(range.start, line.length));
        const end = Math.max(start, Math.min(range.end, line.length));
        if (start > cursor) segments.push({ text: line.slice(cursor, start), marked: false });
        if (end > start) segments.push({ text: line.slice(start, end), marked: true });
        cursor = end;
    }
    if (cursor < line.length) segments.push({ text: line.slice(cursor), marked: false });
    return segments.length ? segments : [{ text: line, marked: false }];
}
