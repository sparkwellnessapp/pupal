import { describe, expect, it } from 'vitest';

import {
    activeCheckId,
    activeTarget,
    markRangesFor,
    markRangesForAll,
    segmentsForLine,
    resolveHighlight,
    spansForChecks,
    type HighlightableCheck,
    type HighlightSource,
    type HighlightSpan,
    type LineRange,
} from './evidence-highlight';

/**
 * The highlight core, tested DIRECTLY.
 *
 * Until S1 this module had no suite of its own — it was exercised only through
 * `grade-review-pure.test.ts` (which drives `resolveHighlight`) and the
 * AnswerBlock render test. That was survivable while the answer to "what is
 * lit" was one quote. It is not survivable now: the criterion-level button
 * unions several spans, and the merge is where a plural matcher goes wrong
 * silently — an overlap that swallows text, an ordering that makes
 * `segmentsForLine`'s monotonic cursor skip characters, a fuzzy span quietly
 * promoted to exact.
 */

const ANSWER = [
    'private string hobbyName ;',        // line 0
    'private bool isSportive ;',         // line 1
    'public string getName() { return name; }',   // line 2
].join('\n');

const span = (quote: string, kind: HighlightSpan['kind'] = 'exact'): HighlightSpan =>
    ({ quote, kind });

/** Ranges on one line, in emitted order. */
const onLine = (ranges: LineRange[], line: number) =>
    ranges.filter((r) => r.line === line).map(({ start, end, kind }) => ({ start, end, kind }));

describe('markRangesForAll — the union', () => {
    it('is byte-for-byte the single-quote result for ONE span', () => {
        // The property the whole plural refactor rests on: the per-check path
        // is the one-element case, so it cannot have changed behaviour.
        for (const quote of ['hobbyName', 'isSportive', 'return name;']) {
            expect(markRangesForAll(ANSWER, [span(quote)]))
                .toEqual(markRangesFor(ANSWER, quote));
        }
    });

    it('lights spans on different lines independently', () => {
        const ranges = markRangesForAll(ANSWER, [span('hobbyName'), span('isSportive')]);
        expect(ranges.map((r) => r.line)).toEqual([0, 1]);
        expect(onLine(ranges, 0)).toEqual([{ start: 15, end: 24, kind: 'exact' }]);
        expect(onLine(ranges, 1)).toEqual([{ start: 13, end: 23, kind: 'exact' }]);
    });

    it('collapses two checks quoting the SAME text into one span', () => {
        // The union's span count is not the check count, deliberately.
        const ranges = markRangesForAll(ANSWER, [span('hobbyName'), span('hobbyName')]);
        expect(ranges).toEqual(markRangesForAll(ANSWER, [span('hobbyName')]));
    });

    it('merges overlapping spans of the SAME kind into one run', () => {
        const ranges = markRangesForAll(ANSWER, [
            span('private string'),      // [0,14)
            span('string hobbyName'),    // [8,24)
        ]);
        expect(onLine(ranges, 0)).toEqual([{ start: 0, end: 24, kind: 'exact' }]);
    });

    it('gives each character the STRONGEST claim that covers it', () => {
        // Overlapping exact + fuzzy. The intersection is genuinely verbatim, so
        // it reads exact; the fuzzy span's own tail must STAY fuzzy — merging
        // the pair wholesale would promote an approximate citation to a
        // verbatim one, and the dashed underline exists to deny exactly that.
        const ranges = markRangesForAll(ANSWER, [
            span('private string', 'exact'),        // [0,14)
            span('string hobbyName', 'fuzzy'),      // [8,24)
        ]);
        expect(onLine(ranges, 0)).toEqual([
            { start: 0, end: 14, kind: 'exact' },
            { start: 14, end: 24, kind: 'fuzzy' },
        ]);
    });

    it('is order-independent — the same set of spans paints the same picture', () => {
        const a = markRangesForAll(ANSWER, [
            span('private string', 'exact'), span('string hobbyName', 'fuzzy')]);
        const b = markRangesForAll(ANSWER, [
            span('string hobbyName', 'fuzzy'), span('private string', 'exact')]);
        expect(b).toEqual(a);
    });

    it('carries a multi-line span, and its neighbours, intact', () => {
        const ranges = markRangesForAll(ANSWER, [
            span('hobbyName ;\nprivate bool'), span('return name;')]);
        expect(ranges.map((r) => r.line)).toEqual([0, 1, 2]);
    });

    it('drops an unplaceable quote WITHOUT losing the ones that placed', () => {
        // The invented-credit case inside a union: it contributes nothing and
        // takes nothing down with it.
        const ranges = markRangesForAll(ANSWER, [
            span('nothing like this appears anywhere'), span('hobbyName')]);
        expect(ranges).toEqual(markRangesForAll(ANSWER, [span('hobbyName')]));
    });

    it('paints nothing for an empty span list or an empty answer', () => {
        expect(markRangesForAll(ANSWER, [])).toEqual([]);
        expect(markRangesForAll('', [span('hobbyName')])).toEqual([]);
    });

    it('emits ranges SORTED and NON-OVERLAPPING — segmentsForLine depends on it', () => {
        const ranges = markRangesForAll(ANSWER, [
            span('private string'), span('string hobbyName', 'fuzzy'),
            span('isSportive'), span('return name;'), span('hobbyName'),
        ]);
        const byLine = new Map<number, LineRange[]>();
        for (const r of ranges) byLine.set(r.line, [...(byLine.get(r.line) ?? []), r]);
        for (const [, group] of byLine) {
            for (let i = 0; i < group.length; i += 1) {
                expect(group[i].end).toBeGreaterThan(group[i].start);
                if (i > 0) expect(group[i].start).toBeGreaterThanOrEqual(group[i - 1].end);
            }
        }
    });
});

describe('segmentsForLine over a union', () => {
    const line = ANSWER.split('\n')[0];

    it('reconstructs the line EXACTLY — no character invented or dropped', () => {
        // The failure this guards is silent: an overlap or a bad order makes
        // the cursor skip, and text simply vanishes from the answer on screen.
        const ranges = markRangesForAll(ANSWER, [
            span('private string'), span('string hobbyName', 'fuzzy')])
            .filter((r) => r.line === 0);
        expect(segmentsForLine(line, ranges).map((s) => s.text).join('')).toBe(line);
    });

    it('labels each segment with its own kind', () => {
        const ranges = markRangesForAll(ANSWER, [
            span('private string', 'exact'), span('string hobbyName', 'fuzzy')])
            .filter((r) => r.line === 0);
        expect(segmentsForLine(line, ranges).map((s) => [s.marked, s.kind])).toEqual([
            [true, 'exact'],
            [true, 'fuzzy'],
            [false, null],
        ]);
    });

    it('sorts defensively, so hand-built out-of-order ranges lose nothing', () => {
        const out = segmentsForLine('abcdef', [
            { line: 0, start: 4, end: 6, kind: 'exact' },
            { line: 0, start: 0, end: 2, kind: 'fuzzy' },
        ]);
        expect(out.map((s) => s.text).join('')).toBe('abcdef');
        expect(out.map((s) => s.kind)).toEqual(['fuzzy', null, 'exact']);
    });
});

describe('spansForChecks — what a criterion may light', () => {
    it('takes every check that would offer its own quote button', () => {
        expect(spansForChecks([
            { check_id: 'a', quote: 'hobbyName', quote_status: 'exact' },
            { check_id: 'b', quote: 'isSportive', quote_status: 'fuzzy' },
        ])).toEqual([
            { quote: 'hobbyName', kind: 'exact' },
            { quote: 'isSportive', kind: 'fuzzy' },
        ]);
    });

    it('refuses not_found, an absent status, and a missing quote', () => {
        // Same rule that denies those checks a button of their own. A criterion
        // that lit a not_found span would manufacture the very evidence the
        // flag exists to report as missing.
        expect(spansForChecks([
            { check_id: 'a', quote: 'invented', quote_status: 'not_found' },
            { check_id: 'b', quote: 'no status', quote_status: null },
            { check_id: 'c', quote: null, quote_status: 'exact' },
            { check_id: 'd', quote: '', quote_status: 'exact' },
        ])).toEqual([]);
    });
});

describe('resolveHighlight — the pin union [S2]', () => {
    const CHECKS: HighlightableCheck[] = [
        { check_id: 'c1.k1', terminalId: 'c1', quote: 'hobbyName', quote_status: 'exact' },
        { check_id: 'c1.k2', terminalId: 'c1', quote: 'isSportive', quote_status: 'fuzzy' },
        // Invented credit: belongs to c1, contributes nothing to c1's union.
        { check_id: 'c1.k3', terminalId: 'c1', quote: 'never written', quote_status: 'not_found' },
        { check_id: 'c2.k1', terminalId: 'c2', quote: 'return name;', quote_status: 'exact' },
    ];
    const byId = new Map(CHECKS.map((c) => [c.check_id, c]));
    const scope = new Set(CHECKS.map((c) => c.check_id));
    const source = (over: Partial<HighlightSource> = {}): HighlightSource =>
        ({ hover: null, pin: null, focus: null, ...over });
    const criterion = (id: string) => ({ kind: 'criterion' as const, id });
    const check = (id: string) => ({ kind: 'check' as const, id });

    it('lights EXACTLY what its own rows would light — the whole point', () => {
        // The user-facing promise, stated as an identity rather than a hope:
        // the criterion's union is the concatenation of its checks' own pins.
        const union = resolveHighlight(source({ pin: criterion('c1') }), byId, scope);
        const perCheck = ['c1.k1', 'c1.k2', 'c1.k3'].flatMap((id) =>
            resolveHighlight(source({ pin: check(id) }), byId, scope).spans);
        expect(union.spans).toEqual(perCheck);
    });

    it('ignores checks belonging to a DIFFERENT criterion in the same scope', () => {
        const lit = resolveHighlight(source({ pin: criterion('c1') }), byId, scope);
        expect(lit.spans.map((s) => s.quote)).toEqual(['hobbyName', 'isSportive']);
        expect(lit.spans.map((s) => s.quote)).not.toContain('return name;');
    });

    it('paints nothing when the criterion belongs to another scope', () => {
        // The same guard the check branch has, for the same reason: repeated
        // text must not make question 2 light question 1's answer.
        const elsewhere = new Set(['c2.k1']);
        expect(resolveHighlight(source({ pin: criterion('c1') }), byId, elsewhere).spans)
            .toEqual([]);
    });

    it('paints nothing for a criterion whose every quote was not_found', () => {
        const invented = new Map([['x.k1', {
            check_id: 'x.k1', terminalId: 'x', quote: 'never written',
            quote_status: 'not_found',
        } as HighlightableCheck]]);
        expect(resolveHighlight(
            source({ pin: criterion('x') }), invented, new Set(['x.k1'])).spans).toEqual([]);
    });

    it('draws a criterion pin as PINNED, and not while the mouse is elsewhere', () => {
        expect(resolveHighlight(source({ pin: criterion('c1') }), byId, scope).pinned)
            .toBe(true);
        // Hover is the most momentary intent and outranks the pin, so the
        // persistent underline must not flicker on beneath the mouse.
        const hovered = resolveHighlight(
            source({ hover: 'c2.k1', pin: criterion('c1') }), byId, scope);
        expect(hovered.pinned).toBe(false);
        expect(hovered.spans.map((s) => s.quote)).toEqual(['return name;']);
    });

    it('falls back to FOCUS when the criterion pin is released (Esc)', () => {
        const lit = resolveHighlight(source({ pin: null, focus: 'c2.k1' }), byId, scope);
        expect(lit.spans.map((s) => s.quote)).toEqual(['return name;']);
        expect(lit.pinned).toBe(false);
    });

    it('activeTarget keeps the precedence: hover, then pin, then focus', () => {
        expect(activeTarget(source({ hover: 'h', pin: criterion('c1'), focus: 'f' })))
            .toEqual(check('h'));
        expect(activeTarget(source({ pin: criterion('c1'), focus: 'f' })))
            .toEqual(criterion('c1'));
        expect(activeTarget(source({ focus: 'f' }))).toEqual(check('f'));
        expect(activeTarget(source())).toBeNull();
    });

    it('activeCheckId reports NO check while a criterion is pinned', () => {
        // Callers that mean "which ROW is lit" must not be handed a terminal id.
        expect(activeCheckId(source({ pin: criterion('c1') }))).toBeNull();
        expect(activeCheckId(source({ pin: check('c1.k1') }))).toBe('c1.k1');
    });
});

describe('the kind is a ceiling, never a floor [S1 review]', () => {
    it('paints an exact-certified quote FUZZY when this render could only place it approximately', () => {
        // The wire text has drifted from what was graded: the server said
        // exact, the client cannot find it verbatim, the fuzzy window can.
        // Painting solid teal here would claim a precision this render does
        // not have. `bestFuzzyWindow` needs a decent overlap, so the drift is a
        // single changed word.
        const drifted = 'private string hobbyTitle ;';
        const ranges = markRangesFor(drifted, 'private string hobbyName', 'exact');
        expect(ranges.length).toBeGreaterThan(0);
        expect(ranges.every((r) => r.kind === 'fuzzy')).toBe(true);
    });

    it('keeps a fuzzy-certified quote FUZZY even when found verbatim', () => {
        // Upgrading would claim a precision the server never certified.
        const ranges = markRangesFor(ANSWER, 'hobbyName', 'fuzzy');
        expect(onLine(ranges, 0)).toEqual([{ start: 15, end: 24, kind: 'fuzzy' }]);
    });

    it('applies the same ceiling inside a union', () => {
        const drifted = 'private string hobbyTitle ;\nprivate bool isSportive ;';
        const ranges = markRangesForAll(drifted, [
            span('private string hobbyName', 'exact'),   // drifted → fuzzy
            span('isSportive', 'exact'),                 // verbatim → exact
        ]);
        expect(onLine(ranges, 0).map((r) => r.kind)).toEqual(['fuzzy']);
        expect(onLine(ranges, 1).map((r) => r.kind)).toEqual(['exact']);
    });
});

describe('the affordance rule is ONE rule [S3 review]', () => {
    it('refuses a not_found quote even when this renderer CAN place it', () => {
        // Reachable, not hypothetical: the client's fuzzy floor (0.6) is looser
        // than the server's certification (0.85), so a quote the server rated
        // not_found can still be located here. Asking the matcher alone made
        // `canHighlight` true while the resolver refused to paint — a button
        // that landed nowhere, which is the defect `canHighlight` exists to
        // remove. `spansForChecks` is the eligibility half, and both the row
        // button and the criterion union now go through it.
        const answer = 'private string hobbyName ;';
        const quote = 'private string hobbyTitle ;';
        expect(markRangesFor(answer, quote).length).toBeGreaterThan(0);
        expect(spansForChecks([
            { check_id: 'k', quote, quote_status: 'not_found' }])).toEqual([]);
    });
});

describe('the fuzzy window lands where it should [highlight review]', () => {
    // 'private string hobbyName ;'  — offsets: private 0–6 · string 8–13 · hobbyName 15–23
    it('never swallows the first letter of the word AFTER a fuzzy span', () => {
        // A 15-character quote whose best window is [0,14] in normalised space,
        // and normalised index 14 is the collapsed space before «hobbyName».
        // That space maps back to the ORIGINAL index of the «h» after it, so
        // the untrimmed end resolved to 16 and the mark read «private string h».
        const ranges = markRangesFor('private string hobbyName ;', 'privatx strings', 'fuzzy');
        expect(ranges).toHaveLength(1);
        expect(ranges[0].end).toBe(14);                 // «private string», nothing more
        expect(ranges[0].start).toBe(0);
    });

    it('refines the coarse stride to the true best start', () => {
        // Quote of 16 characters ⇒ stride 2 ⇒ the coarse pass tries only even
        // starts. The real match begins at 3, and the character before it is a
        // LETTER («z»), not a space — so the word-boundary trim cannot rescue
        // it and only the fine pass can. (The first version of this test used
        // an «ab » prefix; the coarse miss landed on the space and the trim
        // walked it to 3, so disabling the fine pass failed nothing.)
        const ranges = markRangesFor('xyzprivate string hobbyName ;', 'privatx string h', 'fuzzy');
        expect(ranges).toHaveLength(1);
        expect(ranges[0].start).toBe(3);
    });
});

describe('precedence is PER ANSWER [highlight review]', () => {
    const A: HighlightableCheck[] = [
        { check_id: 'a.k1', terminalId: 'a', quote: 'hobbyName', quote_status: 'exact' },
    ];
    const B: HighlightableCheck[] = [
        { check_id: 'b.k1', terminalId: 'b', quote: 'return name;', quote_status: 'exact' },
    ];
    const byId = new Map([...A, ...B].map((c) => [c.check_id, c]));
    const scopeA = new Set(A.map((c) => c.check_id));
    const scopeB = new Set(B.map((c) => c.check_id));
    const source = (over: Partial<HighlightSource> = {}): HighlightSource =>
        ({ hover: null, pin: null, focus: null, ...over });

    it('a pin in one answer SURVIVES a hover in another', () => {
        // Globally resolved, the hover won everywhere and question 1's pinned
        // union went dark while the mouse rested on a row in question 2.
        const src = source({ pin: { kind: 'check', id: 'a.k1' }, hover: 'b.k1' });
        const inA = resolveHighlight(src, byId, scopeA);
        const inB = resolveHighlight(src, byId, scopeB);
        expect(inA.spans.map((s) => s.quote)).toEqual(['hobbyName']);
        expect(inA.pinned).toBe(true);                  // still the pin's own mark
        expect(inB.spans.map((s) => s.quote)).toEqual(['return name;']);
        expect(inB.pinned).toBe(false);                 // a hover, transient
    });

    it('a focus in one answer lights it even while another answer holds the pin', () => {
        const src = source({ pin: { kind: 'criterion', id: 'a' }, focus: 'b.k1' });
        expect(resolveHighlight(src, byId, scopeA).pinned).toBe(true);
        const inB = resolveHighlight(src, byId, scopeB);
        expect(inB.spans.map((s) => s.quote)).toEqual(['return name;']);
        expect(inB.pinned).toBe(false);
    });

    it('within ONE answer, hover still outranks the pin — and is never drawn as pinned', () => {
        const src = source({ pin: { kind: 'check', id: 'a.k1' }, hover: 'a.k1' });
        const inA = resolveHighlight(src, byId, scopeA);
        expect(inA.spans.map((s) => s.quote)).toEqual(['hobbyName']);
        expect(inA.pinned).toBe(false);
    });

    it('activeTarget honours the membership it is given', () => {
        const src = source({ hover: 'b.k1', pin: { kind: 'check', id: 'a.k1' } });
        const onlyA = (t: { id: string }) => t.id.startsWith('a');
        expect(activeTarget(src, onlyA)).toBe(src.pin);  // by reference
        expect(activeTarget(src)).toEqual({ kind: 'check', id: 'b.k1' });
    });
});
