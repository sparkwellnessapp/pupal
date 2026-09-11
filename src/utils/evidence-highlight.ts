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

/**
 * What a deliberate click lit: one check's span, or a whole criterion's union.
 *
 * ONE PIN, EITHER KIND (owner ruling, S2). A criterion pin replaces a check pin
 * and vice versa, so "what am I looking at" always has exactly one answer — and
 * nothing is lost by the replacement, because the criterion's union already
 * contains every one of its checks' spans.
 */
export type PinTarget =
    | { readonly kind: 'check'; readonly id: string }
    | { readonly kind: 'criterion'; readonly id: string };

/**
 * hover ?? pin ?? focus — most momentary first.
 *
 * `hover` and `focus` stay CHECK ids: both are properties of a row. Only a pin
 * can name a criterion, because only a pin is a deliberate act.
 */
export interface HighlightSource {
    hover: string | null;
    pin: PinTarget | null;
    focus: string | null;
}

/**
 * What should be lit, by precedence — hover ?? pin ?? focus.
 *
 * `inScope` narrows each candidate to the answer being resolved, and that makes
 * precedence PER ANSWER: a hover in question 2 outranks a pin in question 2,
 * but has no standing over a pin in question 1, whose answer it never touches.
 * Resolved globally, this blanked every pinned answer on the page the moment
 * the mouse crossed any row anywhere — and the module header's rule, «a pin
 * she has to re-set every time she moves the mouse is not a pin», does not
 * stop applying at a scope boundary.
 *
 * When the pin wins it is returned BY REFERENCE (`source.pin` itself), which is
 * what lets `resolveHighlight` tell "the pin is what lit this" apart from "a
 * hover on the very check that is pinned" — the latter must never draw the
 * persistent underline beneath the cursor.
 */
export function activeTarget(
    source: HighlightSource,
    inScope: (target: PinTarget) => boolean = () => true,
): PinTarget | null {
    const candidates: (PinTarget | null)[] = [
        source.hover !== null ? { kind: 'check', id: source.hover } : null,
        source.pin,
        source.focus !== null ? { kind: 'check', id: source.focus } : null,
    ];
    for (const candidate of candidates) {
        if (candidate !== null && inScope(candidate)) return candidate;
    }
    return null;
}

/** The active target when it is a CHECK; null when a criterion is pinned. */
export function activeCheckId(source: HighlightSource): string | null {
    const target = activeTarget(source);
    return target !== null && target.kind === 'check' ? target.id : null;
}

/** How a span was matched. `not_found` never becomes a mark, so it is absent. */
export type MarkKind = 'exact' | 'fuzzy';

export interface HighlightSpan {
    quote: string;
    kind: MarkKind;
}

/**
 * What is lit in one answer.
 *
 * PLURAL SINCE S1. This was a single `{ quote, kind }`, which was exactly right
 * while the only thing that could light the answer was ONE check. A criterion's
 * quote button lights the union of its checks' spans, and a union of one is the
 * old behaviour — so the per-check path is unchanged by construction rather
 * than by care.
 *
 * `pinned` stays scalar: it describes the ACT (a deliberate click, drawn with
 * the persistent underline), not any individual span.
 */
export interface Highlight {
    spans: HighlightSpan[];
    pinned: boolean;
}

export const NO_HIGHLIGHT: Highlight = { spans: [], pinned: false };

export interface HighlightableCheck {
    check_id: string;
    quote?: string | null;
    quote_status?: QuoteStatus | null;
    /** Which criterion owns this check — what a criterion pin resolves through. */
    terminalId?: string;
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
    // Membership in THIS answer, for either kind: a check is here when the
    // scope lists it; a criterion is here when the scope lists any check it
    // owns. This is the guard that stops question 2 painting question 1's
    // answer because the text happens to repeat — and, passed to the
    // precedence rule, what makes that rule per answer rather than global.
    const inScope = (target: PinTarget): boolean => {
        if (target.kind === 'check') return scopeCheckIds.has(target.id);
        for (const id of scopeCheckIds) {
            if (checksById.get(id)?.terminalId === target.id) return true;
        }
        return false;
    };

    const target = activeTarget(source, inScope);
    if (target === null) return NO_HIGHLIGHT;

    // Pinned iff THE PIN is what won here — by reference, on purpose. A hover
    // on the very check that is pinned yields a different object, and must not
    // draw the persistent underline beneath the cursor (it would flicker on and
    // off as she moves between rows).
    const pinned = target === source.pin;

    const checks: HighlightableCheck[] = [];
    for (const id of scopeCheckIds) {
        const check = checksById.get(id);
        if (!check) continue;
        const owned = target.kind === 'criterion'
            ? check.terminalId === target.id
            : check.check_id === target.id;
        if (owned) checks.push(check);
    }

    // ONE rule decides what may be painted, for one check and for many: a
    // quote that was never found is not painted at all. Inlining those guards
    // here as well would be a second place for them to drift.
    const spans = spansForChecks(checks);
    return spans.length === 0 ? NO_HIGHLIGHT : { spans, pinned };
}

/**
 * The spans a set of checks would light, together — the criterion-level union.
 *
 * DERIVED FROM THE SAME CHECKS THE ROWS RENDER, and filtered by the same rule:
 * a check with no quote, or one whose quote was `not_found`, contributes
 * nothing here for precisely the reason it offers no button of its own (see the
 * module doc — painting a "best guess" for invented credit is the one thing
 * this file refuses to do). That is what makes «the criterion lights exactly
 * what its rows light» true by construction instead of by agreement.
 */
export function spansForChecks(
    checks: readonly HighlightableCheck[],
): HighlightSpan[] {
    const spans: HighlightSpan[] = [];
    for (const check of checks) {
        if (!check.quote) continue;
        if (check.quote_status === 'not_found' || check.quote_status == null) continue;
        spans.push({
            quote: check.quote,
            kind: check.quote_status === 'fuzzy' ? 'fuzzy' : 'exact',
        });
    }
    return spans;
}

export interface QuoteSegment {
    text: string;
    marked: boolean;
    /** How this segment was matched. `null` on unmarked text. */
    kind: MarkKind | null;
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
    kind: MarkKind;
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
    const last = normAnswer.length - size;             // the last full window
    const step = Math.max(1, Math.floor(normQuote.length / 8));
    const scoreAt = (i: number) => diceSimilarity(normQuote, normAnswer.slice(i, i + size));

    // COARSE: every `step`-th start. The stride keeps this linear in the answer,
    // at the price of landing up to step−1 characters off the true best.
    let bestScore = 0;
    let bestAt = -1;
    for (let i = 0; i <= last; i += step) {
        const score = scoreAt(i);
        if (score > bestScore) { bestScore = score; bestAt = i; }
    }
    if (bestAt === -1 || bestScore < FUZZY_FLOOR) return null;

    // FINE: every start within one stride of the coarse best. A dashed
    // underline that begins four characters into a word reads as sloppy, not
    // as approximate — and this costs at most 2·step further scores.
    const lo = Math.max(0, bestAt - step + 1);
    const hi = Math.min(last, bestAt + step - 1);
    for (let i = lo; i <= hi; i += 1) {
        const score = scoreAt(i);
        if (score > bestScore) { bestScore = score; bestAt = i; }
    }

    // TRIM TO WORD BOUNDARIES, in normalised space. A collapsed space maps back
    // to the ORIGINAL index of the character AFTER it (see normalizeWithMap), so
    // a window ending on a space resolved one character INTO the next word and
    // the mark swallowed its first letter. Shrinking the ends off spaces here
    // means the map is only ever consulted on a real character.
    let from = bestAt;
    let to = Math.min(bestAt + size, normAnswer.length) - 1;
    while (from < to && normAnswer[from] === ' ') from += 1;
    while (to > from && normAnswer[to] === ' ') to -= 1;
    return [from, to];
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
/**
 * The answer, normalised and line-indexed ONCE.
 *
 * A union locates each of its spans against the same answer, and the answer is
 * the expensive half (thousands of characters; the quotes are dozens). Doing
 * this per span made a criterion with N checks normalise the answer N times on
 * every repaint. Prepared once, the per-span cost is the quote alone.
 */
interface PreparedAnswer {
    norm: Normalized;
    /** Absolute offset of each line's first character; the last entry is the
     *  total length, so `[starts[i], starts[i+1] - 1)` is line i's text. */
    lineStarts: number[];
}

function prepareAnswer(answer: string): PreparedAnswer {
    const lineStarts = [0];
    for (let i = 0; i < answer.length; i += 1) {
        if (answer[i] === '\n') lineStarts.push(i + 1);
    }
    lineStarts.push(answer.length + 1);
    return { norm: normalizeWithMap(answer), lineStarts };
}

function locateQuote(
    answer: PreparedAnswer, quote: string, kind: MarkKind,
): LineRange[] {
    const a = answer.norm;
    const q = normalizeWithMap(quote);
    if (!q.norm || !a.norm) return [];

    let from = a.norm.indexOf(q.norm);
    let to = from === -1 ? -1 : from + q.norm.length - 1;
    // THE KIND IS A CEILING, NEVER A FLOOR. `kind` is the server's verdict on
    // the text it graded; HOW this render placed the span is a fact about this
    // render. A quote certified exact that can only be placed by the fuzzy
    // window — the wire text has drifted from what was graded — is painted as
    // the approximation it now is. The reverse never happens: a fuzzy verdict
    // found verbatim stays fuzzy, because upgrading would claim a precision the
    // server did not certify (§3.5a: degrade, never embellish).
    let placed: MarkKind = kind;
    if (from === -1) {
        const window = bestFuzzyWindow(q.norm, a.norm);
        if (!window) return [];
        [from, to] = window;
        placed = 'fuzzy';
    }

    // Back to ORIGINAL offsets. `to` is INCLUSIVE in normalised space, so the
    // exclusive original end is one past the character it names.
    const startOriginal = a.map[from];
    const endOriginal = a.map[to] + 1;

    const ranges: LineRange[] = [];
    const { lineStarts } = answer;
    for (let index = 0; index + 1 < lineStarts.length; index += 1) {
        const lineStart = lineStarts[index];
        const lineEnd = lineStarts[index + 1] - 1;   // exclusive; excludes the newline
        if (lineStart >= endOriginal) break;          // past the span — nothing further
        const start = Math.max(startOriginal, lineStart);
        const end = Math.min(endOriginal, lineEnd);
        if (start < end) {
            ranges.push({
                line: index, start: start - lineStart, end: end - lineStart, kind: placed,
            });
        }
    }
    return ranges;
}

/**
 * Where to paint ONE quote. The single-span case, kept as its own export
 * because it is what every per-check caller means.
 *
 * `kind` defaults to `exact` for the callers that only ask WHETHER a span can
 * be placed (`canHighlight`) — and the locator downgrades it on a fuzzy
 * placement regardless, so the default can never over-claim.
 */
export function markRangesFor(
    answer: string, quote: string | null, kind: MarkKind = 'exact',
): LineRange[] {
    if (!quote || !answer) return [];
    return locateQuote(prepareAnswer(answer), quote, kind);
}

/**
 * Where to paint SEVERAL quotes at once — the criterion-level union.
 *
 * Each span is located independently by the rule above (first occurrence only:
 * this is a citation, not a highlighter sweep), and the results are then
 * flattened into ranges that do not overlap. They must not overlap:
 * `segmentsForLine` walks them with a monotonic cursor, and two overlapping
 * ranges would silently swallow the text between them.
 *
 * WHERE SPANS COLLIDE, EACH CHARACTER TAKES THE STRONGEST CLAIM THAT COVERS IT.
 * Painting fuzzy first and exact over it means the overlap renders exact — true,
 * since an exact quote does contain that text verbatim — while the fuzzy span's
 * own tail stays fuzzy. Merging the pair wholesale into one exact range was the
 * simpler option and is the wrong direction: it would quietly upgrade an
 * approximate citation to a verbatim one, and the fuzzy styling exists to say
 * that it is not.
 *
 * Two checks quoting the same text therefore produce ONE span. The union's span
 * count is not the check count, deliberately.
 */
export function markRangesForAll(
    answer: string, spans: readonly HighlightSpan[],
): LineRange[] {
    if (!answer || spans.length === 0) return [];

    const prepared = prepareAnswer(answer);
    const located = spans.flatMap((span) =>
        span.quote ? locateQuote(prepared, span.quote, span.kind) : []);
    if (located.length === 0) return [];

    const byLine = new Map<number, LineRange[]>();
    for (const range of located) {
        const bucket = byLine.get(range.line);
        if (bucket) bucket.push(range);
        else byLine.set(range.line, [range]);
    }

    const merged: LineRange[] = [];
    for (const line of [...byLine.keys()].sort((a, b) => a - b)) {
        const ranges = byLine.get(line)!;
        const width = ranges.reduce((max, r) => Math.max(max, r.end), 0);
        // One cell per character, strongest claim wins: fuzzy laid down first,
        // exact painted over it.
        const paint: (MarkKind | null)[] = new Array(width).fill(null);
        for (const pass of ['fuzzy', 'exact'] as const) {
            for (const range of ranges) {
                if (range.kind !== pass) continue;
                for (let i = Math.max(0, range.start); i < range.end; i += 1) {
                    paint[i] = pass;
                }
            }
        }
        // Emit maximal runs of one kind.
        let at = 0;
        while (at < width) {
            const kind = paint[at];
            if (kind === null) { at += 1; continue; }
            let end = at + 1;
            while (end < width && paint[end] === kind) end += 1;
            merged.push({ line, start: at, end, kind });
            at = end;
        }
    }
    return merged;
}

/**
 * One line, split into marked / unmarked segments by that line's ranges.
 *
 * Takes RANGES rather than the quote: where the quote lives is decided once,
 * over the whole answer, by `markRangesFor`. A per-line matcher is exactly what
 * could not see a multi-line quote.
 */
export function segmentsForLine(line: string, ranges: readonly LineRange[]): QuoteSegment[] {
    if (ranges.length === 0) return [{ text: line, marked: false, kind: null }];

    const segments: QuoteSegment[] = [];
    let cursor = 0;
    // Sorted defensively: `markRangesForAll` already emits ordered runs, but a
    // caller assembling ranges by hand must not be able to swallow text between
    // two out-of-order spans.
    for (const range of [...ranges].sort((a, b) => a.start - b.start)) {
        const start = Math.max(cursor, Math.min(range.start, line.length));
        const end = Math.max(start, Math.min(range.end, line.length));
        if (start > cursor) {
            segments.push({ text: line.slice(cursor, start), marked: false, kind: null });
        }
        if (end > start) {
            segments.push({ text: line.slice(start, end), marked: true, kind: range.kind });
        }
        cursor = end;
    }
    if (cursor < line.length) {
        segments.push({ text: line.slice(cursor), marked: false, kind: null });
    }
    return segments.length ? segments : [{ text: line, marked: false, kind: null }];
}
