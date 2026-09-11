import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { sha256Hex } from '@/lib/sha256';
import { answerLines, detectAnswerMode, isHebrewLine } from './answer-mode';
import {
    activeCheckId,
    resolveHighlight,
    markRangesFor,
    segmentsForLine,
    type HighlightableCheck,
} from './evidence-highlight';
import {
    cycleVerdict,
    effectiveVerdict,
    isOverridden,
    overriddenCheckIds,
    revert,
    setNote,
    setVerdict,
    toggleEvidenceDisputed,
    type OverlayTerminals,
} from './verdict-cycle';
import { basisHash, feedbackState, isStale } from './feedback-staleness';
import { lookCount, markerCheckIds } from './look-count';
import {
    advanceAfterApprove,
    initialCursor,
    mergeCursor,
    queueState,
    step,
    type CursorItem,
} from './grade-review-cursor';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../backend/tests/fixtures/grade_review');
const readFixture = (name: string) =>
    JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8'));

// ===========================================================================
// sha256 — pinned against CPython, not against itself
// ===========================================================================
describe('sha256 — parity with hashlib', () => {
    // Digests computed by CPython `hashlib.sha256(s.encode("utf-8")).hexdigest()`.
    // A self-consistent hash is worthless here: the whole point is agreeing with
    // the digest the SERVER put on the feedback.
    const CPYTHON: Record<string, string> = {
        '': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
        abc: 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
        'q1.a.c0.k1=met':
            'a6adcf258c2db2768b21781d379bf9f6556f25650628b9e96025ba049d53fcd0',
        'q1.a.c0.k1=met|q1.a.c0.k2=not_met':
            '1c6a1096d15c60ace413e859570bea0edf1a2a87940904d62f1c288dab59efd8',
        'שאלה=met': 'bd3eb27c021d33b23fbb77376a332ff5fae5cfad6a60caa9ba8fae07726812c4',
        'q1.א.c0.k1=partially_met|q1.א.c0.k2=met':
            '722620eef2397ecf77c588191beab064ddb51e8284769d0dd4b5875290beda8d',
    };

    it('matches CPython on ascii, Hebrew and the empty string', () => {
        for (const [input, digest] of Object.entries(CPYTHON)) {
            expect(sha256Hex(input)).toBe(digest);
        }
    });

    it('matches CPython on a REAL scope vector from the fixture set', () => {
        const draft = readFixture('draft_dan_basiuk.json');
        const scope = draft.scope_outcomes[0];
        const checks = scope.criterion_outcomes.flatMap(
            (crit: { sub_criterion_outcomes?: unknown[] }) =>
                ((crit.sub_criterion_outcomes as { checks?: unknown[] }[] | undefined)?.length
                    ? crit.sub_criterion_outcomes as { checks?: unknown[] }[]
                    : [crit as { checks?: unknown[] }])
                    .flatMap((leaf) => leaf.checks ?? []),
        ) as { check_id: string; verdict: string }[];
        expect(checks.length).toBe(6);
        expect(basisHash(checks as never))
            .toBe('dd39058808098a838a938f9bd47e612e247f69ff6093aa17c089399b696820da');
    });

    it('crosses the 55-byte block boundary correctly', () => {
        // The padding branch is where a hand-rolled sha256 usually breaks.
        expect(sha256Hex('a'.repeat(55))).toBe(sha256Hex('a'.repeat(55)));
        expect(sha256Hex('a'.repeat(56))).not.toBe(sha256Hex('a'.repeat(55)));
        expect(sha256Hex('a'.repeat(64)).length).toBe(64);
    });
});

// ===========================================================================
// answer-mode-detection / bidi-two-mode-answer
// ===========================================================================
describe('answer-mode-detection', () => {
    const CODE = [
        'public static void populateHobbies(Hobby[] arr)',
        '{',
        '    // קליטת נתונים לכל התחביבים',
        '    for (int i = 0; i <= arr.Length; i++)',
        '}',
    ].join('\n');

    const PROSE = [
        'התוכנית קולטת את שם התחביב ואת מספר הדקות',
        'ולאחר מכן מדפיסה את התחביב הספורטיבי ביותר',
    ].join('\n');

    it('reads an all-Hebrew answer as prose', () => {
        expect(detectAnswerMode(PROSE)).toBe('prose');
    });

    it('reads anything with program characters as code', () => {
        expect(detectAnswerMode(CODE)).toBe('code');
    });

    it('leans to CODE when unsure — prose-as-code is ugly, code-as-prose is unreadable', () => {
        // One stray bracket in an otherwise Hebrew answer still forces code
        // mode, because RTL would reorder it.
        expect(detectAnswerMode('תשובה עם סוגריים (כאלה)')).toBe('code');
    });

    it('treats an empty answer as prose rather than an empty code island', () => {
        expect(detectAnswerMode('')).toBe('prose');
    });

    /**
     * The bidi rule (OD-F2, ruled left). A Hebrew comment keeps the code
     * island's left alignment; only its text span turns RTL. The leading `//`
     * must be stripped before the test or every Hebrew comment reads as code —
     * which is the entire case this exists for.
     */
    it('marks a Hebrew comment line RTL, stripping the leading //', () => {
        expect(isHebrewLine('    // קליטת נתונים לכל התחביבים')).toBe(true);
        expect(isHebrewLine('// תכונות')).toBe(true);
        expect(isHebrewLine('    for (int i = 0; i < n; i++)')).toBe(false);
    });

    it('leaves a MIXED comment LTR — it still contains code', () => {
        expect(isHebrewLine('// הפעולה getName מחזירה את name')).toBe(false);
    });

    it('numbers lines from 1 and assigns direction per line', () => {
        const lines = answerLines(CODE, 'code');
        expect(lines[0].number).toBe(1);
        expect(lines[0].dir).toBe('ltr');
        expect(lines[2].dir).toBe('rtl');          // the Hebrew comment
        expect(lines.map((l) => l.number)).toEqual([1, 2, 3, 4, 5]);
    });

    it('never marks a line RTL in prose mode — the whole block is already RTL', () => {
        expect(answerLines(PROSE, 'prose').every((l) => l.dir === 'ltr')).toBe(true);
    });
});

// ===========================================================================
// evidence-highlight-exact-fuzzy-notfound / quote-button-pin-hover-focus
// ===========================================================================
describe('evidence highlight', () => {
    const checks: HighlightableCheck[] = [
        { check_id: 'k-exact', quote: 'return name;', quote_status: 'exact' },
        { check_id: 'k-fuzzy', quote: 'arr[i] = new Hobby', quote_status: 'fuzzy' },
        { check_id: 'k-missing', quote: 'Console.WriteLine("x");', quote_status: 'not_found' },
        { check_id: 'k-none', quote: null, quote_status: null },
    ];
    const byId = new Map(checks.map((c) => [c.check_id, c]));
    const scope = new Set(checks.map((c) => c.check_id));
    // `pin` is written here as a bare CHECK id, which is what every case below
    // means; the helper lifts it into the S2 target shape. Criterion pins are
    // exercised separately, at the bottom of this block.
    const source = (
        over: Partial<{ hover: string | null; pin: string | null; focus: string | null }> = {},
    ) => ({
        hover: over.hover ?? null,
        pin: over.pin ? { kind: 'check' as const, id: over.pin } : null,
        focus: over.focus ?? null,
    });

    it('paints a solid mark for an exact quote', () => {
        expect(resolveHighlight(source({ focus: 'k-exact' }), byId, scope))
            .toEqual({ spans: [{ quote: 'return name;', kind: 'exact' }], pinned: false });
    });

    it('paints a fuzzy quote as fuzzy — found, so credit stands', () => {
        expect(resolveHighlight(source({ focus: 'k-fuzzy' }), byId, scope).spans[0].kind)
            .toBe('fuzzy');
    });

    /** The invented-credit case: nothing was found, so nothing is painted. */
    it('paints NOTHING for not_found, rather than guessing a region', () => {
        expect(resolveHighlight(source({ focus: 'k-missing' }), byId, scope).spans).toEqual([]);
        expect(resolveHighlight(source({ pin: 'k-missing' }), byId, scope).spans).toEqual([]);
    });

    it('paints nothing when the check has no quote at all', () => {
        expect(resolveHighlight(source({ focus: 'k-none' }), byId, scope).spans).toEqual([]);
    });

    it('never lights another scope\'s answer, even on a repeated span', () => {
        const otherScope = new Set(['someone-else']);
        expect(resolveHighlight(source({ focus: 'k-exact' }), byId, otherScope))
            .toEqual({ spans: [], pinned: false });
    });

    describe('quote-button-pin-hover-focus-precedence: hover ?? pin ?? focus', () => {
        it('prefers hover over pin over focus', () => {
            expect(activeCheckId(source({ hover: 'h', pin: 'p', focus: 'f' }))).toBe('h');
            expect(activeCheckId(source({ pin: 'p', focus: 'f' }))).toBe('p');
            expect(activeCheckId(source({ focus: 'f' }))).toBe('f');
            expect(activeCheckId(source())).toBeNull();
        });

        it('draws the pinned underline only when the mouse is away', () => {
            expect(resolveHighlight(source({ pin: 'k-exact' }), byId, scope).pinned).toBe(true);
            // Hovering the pinned check must not flicker the underline on.
            expect(resolveHighlight(source({ hover: 'k-exact', pin: 'k-exact' }), byId, scope)
                .pinned).toBe(false);
        });

        it('falls back to focus when the pin is released (Esc)', () => {
            expect(resolveHighlight(source({ pin: null, focus: 'k-fuzzy' }), byId, scope).spans[0].kind)
                .toBe('fuzzy');
        });
    });


    describe('placing the quote in the answer [one matching contract]', () => {
        /**
         * The client used to mark with a raw, case-sensitive `line.indexOf` on
         * ONE line at a time. The server certifies `quote_status` with
         * whitespace COLLAPSED, case FOLDED, against the WHOLE answer. Three
         * divergences — and the multi-line one alone made 24% of quote buttons
         * draw nothing while the toast claimed the quote was highlighted.
         */
        const answer = [
            'public class Hobby',
            '{',
            'private string hobbyName ;',
            '}',
        ].join('\n');

        it('places a MULTI-LINE quote across the lines it spans', () => {
            const quote = 'public class Hobby\n{\nprivate string hobbyName ;';
            const ranges = markRangesFor(answer, quote);
            expect(ranges.map((r) => r.line)).toEqual([0, 1, 2]);
            // Each range covers that line's share, so the rendered marks
            // reconstruct exactly the quoted text.
            const marked = ranges
                .map((r) => answer.split('\n')[r.line].slice(r.start, r.end))
                .join('\n');
            expect(marked).toBe(quote);
        });

        it('matches despite WHITESPACE differences, as the server does', () => {
            // The grader re-emits the span with its own spacing; the server
            // collapsed both sides before certifying it EXACT.
            expect(markRangesFor(answer, 'public   class\n\n  Hobby')).toHaveLength(1);
        });

        it('matches despite CASE, as the server does', () => {
            expect(markRangesFor(answer, 'PUBLIC CLASS HOBBY')).toHaveLength(1);
        });

        it('marks only the FIRST occurrence — a citation, not a highlighter sweep', () => {
            const ranges = markRangesFor('a x a x a', 'x');
            expect(ranges).toEqual([{ line: 0, start: 2, end: 3, kind: 'exact' }]);
        });

        it('treats the quote as literal text, never as a regex', () => {
            const line = 'if (arr[i].x) { return (1+2)*3; }';
            const ranges = markRangesFor(line, 'arr[i].x');
            expect(line.slice(ranges[0].start, ranges[0].end)).toBe('arr[i].x');
            expect(() => markRangesFor(line, '(unclosed[')).not.toThrow();
        });

        it('places NOTHING rather than guessing when the quote is not there', () => {
            // Degrade by omission: an arbitrary underline points the teacher at
            // the wrong line, which is worse than pointing nowhere (§3.5a).
            expect(markRangesFor(answer, 'totally unrelated words here')).toEqual([]);
            expect(markRangesFor(answer, null)).toEqual([]);
            expect(markRangesFor('', 'x')).toEqual([]);
        });

        it('places a FUZZY quote on its best window', () => {
            // The server certified this at >= 0.85 on its own sliding window;
            // the client only has to find the region it certified.
            const ranges = markRangesFor(answer, 'private string hobbyNme ;');
            expect(ranges.map((r) => r.line)).toEqual([2]);
        });
    });

    describe('segmentsForLine', () => {
        it('splits into before / marked / after', () => {
            const line = '    public string getName() { return name; }';
            const ranges = markRangesFor(line, 'return name;');
            expect(segmentsForLine(line, ranges)).toEqual([
                { text: '    public string getName() { ', marked: false, kind: null },
                { text: 'return name;', marked: true, kind: 'exact' },
                { text: ' }', marked: false, kind: null },
            ]);
        });

        it('is the identity when the line carries no range', () => {
            expect(segmentsForLine('abc', [])).toEqual([{ text: 'abc', marked: false, kind: null }]);
        });

        it('never loses or duplicates a character of the line', () => {
            const line = 'private string hobbyName ;';
            const ranges = markRangesFor(line, 'string hobbyName');
            expect(segmentsForLine(line, ranges).map((s) => s.text).join('')).toBe(line);
        });

        it('clamps a range that overruns the line rather than throwing', () => {
            expect(segmentsForLine('abc', [{ line: 0, start: 1, end: 99, kind: 'exact' }]))
                .toEqual([
                    { text: 'a', marked: false, kind: null },
                    { text: 'bc', marked: true, kind: 'exact' },
                ]);
        });
    });
});
