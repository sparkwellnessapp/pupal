import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { sha256Hex } from '@/lib/sha256';
import { answerLines, detectAnswerMode, isHebrewLine } from './answer-mode';
import {
    activeCheckId,
    hasQuoteButton,
    resolveHighlight,
    splitLineByQuote,
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
    const source = (
        over: Partial<{ hover: string | null; pin: string | null; focus: string | null }> = {},
    ) => ({
        hover: over.hover ?? null, pin: over.pin ?? null, focus: over.focus ?? null,
    });

    it('paints a solid mark for an exact quote', () => {
        expect(resolveHighlight(source({ focus: 'k-exact' }), byId, scope))
            .toEqual({ quote: 'return name;', kind: 'exact', pinned: false });
    });

    it('paints a fuzzy quote as fuzzy — found, so credit stands', () => {
        expect(resolveHighlight(source({ focus: 'k-fuzzy' }), byId, scope).kind).toBe('fuzzy');
    });

    /** The invented-credit case: nothing was found, so nothing is painted. */
    it('paints NOTHING for not_found, rather than guessing a region', () => {
        expect(resolveHighlight(source({ focus: 'k-missing' }), byId, scope).quote).toBeNull();
        expect(resolveHighlight(source({ pin: 'k-missing' }), byId, scope).kind).toBe('none');
    });

    it('paints nothing when the check has no quote at all', () => {
        expect(resolveHighlight(source({ focus: 'k-none' }), byId, scope).quote).toBeNull();
    });

    it('never lights another scope\'s answer, even on a repeated span', () => {
        const otherScope = new Set(['someone-else']);
        expect(resolveHighlight(source({ focus: 'k-exact' }), byId, otherScope))
            .toEqual({ quote: null, kind: 'none', pinned: false });
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
            expect(resolveHighlight(source({ pin: null, focus: 'k-fuzzy' }), byId, scope).kind)
                .toBe('fuzzy');
        });
    });

    describe('the quote button', () => {
        it('exists for exact and fuzzy, never for not_found or no quote', () => {
            expect(hasQuoteButton(checks[0])).toBe(true);
            expect(hasQuoteButton(checks[1])).toBe(true);
            expect(hasQuoteButton(checks[2])).toBe(false);
            expect(hasQuoteButton(checks[3])).toBe(false);
        });
    });

    describe('splitting a line', () => {
        it('splits into before / marked / after', () => {
            expect(splitLineByQuote('    public string getName() { return name; }', 'return name;'))
                .toEqual([
                    { text: '    public string getName() { ', marked: false },
                    { text: 'return name;', marked: true },
                    { text: ' }', marked: false },
                ]);
        });

        it('marks only the FIRST occurrence — a citation, not a highlighter sweep', () => {
            const parts = splitLineByQuote('a x a x a', 'x');
            expect(parts.filter((p) => p.marked).length).toBe(1);
            expect(parts.map((p) => p.text).join('')).toBe('a x a x a');
        });

        it('treats the quote as literal text, never as a regex', () => {
            // Student code is full of ( [ . \ — a pattern built from it would
            // throw or match the wrong thing.
            const line = 'if (arr[i].x) { return (1+2)*3; }';
            const quote = 'arr[i].x';
            expect(splitLineByQuote(line, quote).find((p) => p.marked)?.text).toBe(quote);
            expect(() => splitLineByQuote(line, '(unclosed[')).not.toThrow();
            expect(splitLineByQuote(line, '(unclosed[')).toEqual([{ text: line, marked: false }]);
        });

        it('is the identity when there is no quote', () => {
            expect(splitLineByQuote('abc', null)).toEqual([{ text: 'abc', marked: false }]);
        });
    });
});

// ===========================================================================
// verdict-cycle-order / revert-clears-override-and-note
// ===========================================================================
describe('verdict cycle and the overlay', () => {
    const T = 'q1.א.c0';
    const K = 'q1.א.c0.k1';
    const at = () => '2026-08-31T12:00:00.000Z';
    const empty: OverlayTerminals = {};

    it('cycles ✗ → ½ → ✓ → ✗', () => {
        let overlay = cycleVerdict(empty, T, K, 'not_met', at);
        expect(effectiveVerdict(overlay, T, K, 'not_met')).toBe('partially_met');
        overlay = cycleVerdict(overlay, T, K, 'not_met', at);
        expect(effectiveVerdict(overlay, T, K, 'not_met')).toBe('met');
        overlay = cycleVerdict(overlay, T, K, 'not_met', at);
        expect(effectiveVerdict(overlay, T, K, 'not_met')).toBe('not_met');
    });

    it('cycles from the EFFECTIVE verdict, not from Vivi\'s', () => {
        // Starting at met, one press must land on not_met — not on
        // partially_met, which is what cycling from the AI value would give.
        const overlay = cycleVerdict(empty, T, K, 'met', at);
        expect(effectiveVerdict(overlay, T, K, 'met')).toBe('not_met');
    });

    it('marks an override only when it DIFFERS from Vivi', () => {
        const differing = setVerdict(empty, T, K, 'met', 'not_met', at);
        expect(isOverridden(differing, T, K, 'not_met')).toBe(true);
    });

    /**
     * THE bug this rule exists for (found in the F2 code review).
     *
     * `overriddenCheckIds` is what tells the pricer to skip EVIDENCE GATING.
     * Cycling all the way round — ✗ → ½ → ✓ → ✗ — used to leave a record whose
     * verdict matched Vivi's, so the check stayed "decided by the teacher" and
     * was CREDITED even though its citation was `not_found`: points the grader
     * had refused, awarded silently, with no red ring because the verdict
     * agreed. Three presses of Space is an entirely ordinary thing to do.
     */
    it('drops a record that cycles back to agreeing with Vivi', () => {
        let overlay = cycleVerdict(empty, T, K, 'not_met', at);   // → ½
        overlay = cycleVerdict(overlay, T, K, 'not_met', at);     // → ✓
        expect(overriddenCheckIds(overlay).has(K)).toBe(true);

        overlay = cycleVerdict(overlay, T, K, 'not_met', at);     // → ✗, agreeing
        expect(overlay[T]).toBeUndefined();
        expect(overriddenCheckIds(overlay).has(K)).toBe(false);
        expect(isOverridden(overlay, T, K, 'not_met')).toBe(false);
    });

    it('KEEPS a record that agrees on the verdict but carries a note', () => {
        // She looked, decided Vivi was right, and wrote down why. That is a
        // decision, and it must survive.
        let overlay = setNote(empty, T, K, 'בדקתי מול הסריקה', 'met', at);
        overlay = setVerdict(overlay, T, K, 'met', 'met', at);
        expect(overlay[T]).toHaveLength(1);
        expect(overlay[T][0].teacher_comment).toBe('בדקתי מול הסריקה');
    });

    it('reverting clears the verdict, the note AND the dispute together', () => {
        let overlay = cycleVerdict(empty, T, K, 'not_met', at);
        overlay = setNote(overlay, T, K, 'לא הוגן', 'not_met', at);
        overlay = toggleEvidenceDisputed(overlay, T, K, 'not_met', at);
        expect(overlay[T]).toHaveLength(1);
        expect(overlay[T][0].teacher_comment).toBe('לא הוגן');

        overlay = revert(overlay, T, K);
        // The terminal key goes too — an empty list is not a decision.
        expect(overlay[T]).toBeUndefined();
        expect(effectiveVerdict(overlay, T, K, 'not_met')).toBe('not_met');
    });

    it('never mutates the overlay it is given', () => {
        const before = JSON.stringify(empty);
        cycleVerdict(empty, T, K, 'met', at);
        expect(JSON.stringify(empty)).toBe(before);
    });

    it('keeps a note when the verdict cycles again', () => {
        let overlay = setNote(empty, T, K, 'הערה', 'not_met', at);
        overlay = cycleVerdict(overlay, T, K, 'not_met', at);
        expect(overlay[T][0].teacher_comment).toBe('הערה');
    });

    it('lets a note stand alone, at Vivi\'s verdict', () => {
        const overlay = setNote(empty, T, K, 'בדקתי, משאירה', 'met', at);
        expect(overlay[T][0].verdict).toBe('met');
        expect(isOverridden(overlay, T, K, 'met')).toBe(false);
    });

    it('drops a record that stops saying anything', () => {
        let overlay = setNote(empty, T, K, 'זמני', 'met', at);
        overlay = setNote(overlay, T, K, '   ', 'met', at);   // cleared
        expect(overlay[T]).toBeUndefined();
    });

    it('toggles evidence_disputed on and off', () => {
        let overlay = toggleEvidenceDisputed(empty, T, K, 'met', at);
        expect(overlay[T][0].evidence_disputed).toBe(true);
        overlay = toggleEvidenceDisputed(overlay, T, K, 'met', at);
        expect(overlay[T]).toBeUndefined();          // nothing left to say
    });

    it('collects every decided check id for the pricer', () => {
        let overlay = cycleVerdict(empty, T, K, 'not_met', at);
        overlay = cycleVerdict(overlay, 'q2.c0', 'q2.c0.k1', 'met', at);
        expect([...overriddenCheckIds(overlay)].sort()).toEqual(['q1.א.c0.k1', 'q2.c0.k1']);
    });
});

// ===========================================================================
// feedback-stale-derived-from-basis-hash / feedback-absent-state-offers-write
// ===========================================================================
describe('feedback staleness', () => {
    const checks = [
        { check_id: 'k1', verdict: 'met' as const },
        { check_id: 'k2', verdict: 'not_met' as const },
    ];
    const fresh = { text: 'משוב', basis_hash: basisHash(checks) };

    it('is fresh while the verdict vector is unchanged', () => {
        expect(isStale(fresh, checks)).toBe(false);
    });

    it('goes stale the moment a verdict moves', () => {
        const moved = [checks[0], { check_id: 'k2', verdict: 'met' as const }];
        expect(isStale(fresh, moved)).toBe(true);
    });

    it('treats ORDER as part of the basis', () => {
        expect(isStale(fresh, [checks[1], checks[0]])).toBe(true);
    });

    it('ignores points and quotes — they are not the basis (OD-G4.1)', () => {
        // Same verdicts, entirely different point/quote data: not stale.
        const decorated = checks.map((c) => ({ ...c, points: '99', quote: 'x' }));
        expect(isStale(fresh, decorated)).toBe(false);
    });

    it('is NEVER stale when no basis was claimed', () => {
        // An amber "rewrite me" on text that has no idea what it described is a
        // warning she cannot act on — the INV-6 click-through lesson.
        expect(isStale({ text: 'משוב' }, checks)).toBe(false);
        expect(isStale(null, checks)).toBe(false);
    });

    describe('the three card states', () => {
        it('offers WRITING when feedback is absent — never an error page', () => {
            expect(feedbackState(null, checks)).toBe('absent');
            expect(feedbackState({ text: '' }, checks)).toBe('absent');
        });

        it('reports stale when the verdicts moved', () => {
            const moved = [checks[0], { check_id: 'k2', verdict: 'met' as const }];
            expect(feedbackState(fresh, moved)).toBe('stale');
        });

        it('never calls the TEACHER\'s own words stale', () => {
            const moved = [checks[0], { check_id: 'k2', verdict: 'met' as const }];
            expect(feedbackState(fresh, moved, true)).toBe('fresh');
        });
    });
});

// ===========================================================================
// look-count-matches-backend-definition
// ===========================================================================
describe('look-count', () => {
    it('counts the invented-credit case — the one it exists for', () => {
        expect(lookCount({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    checks: [
                        { check_id: 'k1', quote_status: 'exact' },
                        { check_id: 'k2', quote_status: 'not_found' },
                    ],
                }],
            }],
        })).toBe(1);
    });

    it('counts fuzzy too, and once per distinct marker', () => {
        expect(lookCount({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    flags: [{ reason: 'bounds_clamped' }, { reason: 'bounds_clamped' }],
                    checks: [{ check_id: 'k1', quote_status: 'fuzzy' }],
                }],
            }],
        })).toBe(2);
    });

    it('counts a skipped or failed scope once', () => {
        expect(lookCount({
            scope_outcomes: [
                { question_id: 'q1', graded_by: 'skipped_no_answer' },
                { question_id: 'q2', graded_by: 'failed' },
            ],
        })).toBe(2);
    });

    it('never counts a scope excluded by selection — it was never owed', () => {
        expect(lookCount({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'excluded_by_selection',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    checks: [{ check_id: 'k1', quote_status: 'not_found' }],
                }],
            }],
        })).toBe(0);
    });

    it('does not double-count a v5 leaf via its legacy quote flag', () => {
        expect(lookCount({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    flags: [{ reason: 'quote_not_found' }],
                    checks: [{ check_id: 'k1', quote_status: 'not_found' }],
                }],
            }],
        })).toBe(1);
    });

    it('still counts the legacy flag on a v3 leaf that has no checks', () => {
        expect(lookCount({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{ criterion_id: 'c0', flags: [{ reason: 'quote_not_found' }] }],
            }],
        })).toBe(1);
    });

    /**
     * `look-count-matches-backend-definition`, as a PARITY TABLE rather than a
     * guess. Every number below was produced by running
     * `app/services/look_count.py::look_count` over that exact fixture — the
     * dashboard shows the server's figure and the open test shows this one, so
     * a disagreement is two numbers for one fact on the same screen.
     *
     * (The first draft of this test asserted 0 for dan_basiuk on the reasoning
     * that the cohort quoted exactly everywhere. The backend says 1 — there is
     * a clamped terminal in it — and the backend was right.)
     */
    it('matches the backend number on every published fixture', () => {
        const BACKEND: Record<string, number> = {
            dan_basiuk: 1,
            din_ezra: 3,
            moran_aharon: 0,
            omer_gelber: 0,
            yonatan_basiuk: 2,
            SYNTHETIC_edge_cases: 4,
        };
        for (const [name, expected] of Object.entries(BACKEND)) {
            expect(lookCount(readFixture(`draft_${name}.json`)), name).toBe(expected);
        }
    });

    it('walks exactly the unvalidated-evidence markers, in document order', () => {
        // `F` jumps between these. The synthetic draft carries one not_found
        // and one fuzzy; the observed drafts carry none.
        expect(markerCheckIds(readFixture('draft_SYNTHETIC_edge_cases.json')))
            .toEqual(['q1.א.c0.k1', 'q1.א.c0.k2']);
        expect(markerCheckIds(readFixture('draft_dan_basiuk.json'))).toEqual([]);
    });
});

// ===========================================================================
// next-skips-unlanded-never-waits
// ===========================================================================
describe('grade-review cursor', () => {
    const item = (id: string, status: CursorItem['status']): CursorItem =>
        ({ graded_test_id: id, status, student_name: id });

    const cursor = initialCursor([
        item('a', 'draft'),
        item('b', 'grading'),      // still being graded — stepped over
        item('c', 'draft'),
        item('d', 'approved'),     // already signed — not reviewable
        item('e', 'draft'),
    ]);

    it('skips what has not landed and never waits', () => {
        expect(step(cursor, 'a', 'next')).toBe('c');
        expect(step(cursor, 'c', 'next')).toBe('e');   // 'd' is approved
    });

    it('walks backwards the same way', () => {
        expect(step(cursor, 'e', 'prev')).toBe('c');
        expect(step(cursor, 'c', 'prev')).toBe('a');
        expect(step(cursor, 'a', 'prev')).toBeNull();
    });

    it('does NOT wrap — the end is the WaitCard\'s cue', () => {
        expect(step(cursor, 'e', 'next')).toBeNull();
    });

    it('comes BACK for tests it skipped, after approve', () => {
        // 'b' finished grading while she worked forward.
        const later = mergeCursor(cursor, [item('b', 'draft')]);
        expect(advanceAfterApprove(later, 'e')).toBe('c');
        expect(advanceAfterApprove(later, 'c')).toBe('e');
    });

    it('appends late arrivals and NEVER reorders the prefix (OD2)', () => {
        const later = mergeCursor(cursor, [item('b', 'draft'), item('z', 'draft')]);
        expect(later.order).toEqual(['a', 'b', 'c', 'd', 'e', 'z']);
        expect(later.byId.b.status).toBe('draft');
    });

    it('reports the queue: who is next, who is grading, how many skipped', () => {
        const q = queueState(cursor, 'a');
        expect(q.nextLanded?.graded_test_id).toBe('c');
        expect(q.grading.map((i) => i.graded_test_id)).toEqual(['b']);
        expect(q.skipped).toBe(1);          // 'e' — reviewable but not next
        expect(q.exhausted).toBe(false);
    });

    it('reports exhausted when nothing landed is left', () => {
        const only = initialCursor([item('a', 'draft'), item('b', 'grading')]);
        expect(queueState(only, 'a').exhausted).toBe(true);
        expect(queueState(only, 'a').grading).toHaveLength(1);
    });

    it('returns null for an id that is not in the cursor', () => {
        expect(step(cursor, 'ghost', 'next')).toBeNull();
    });
});

// ---------------------------------------------------------------------------
// Multisubject Phase 3a (2026-09-08): the SUBJECT decides the render plan.
// The CS heuristic is untouched; english/mathematics never run it.
// ---------------------------------------------------------------------------
import { answerRenderPlan } from './answer-mode';

describe('answer-render-plan-by-subject', () => {
    const ESSAY = 'The 3 reasons are simple.\nFirst, it costs 20 dollars.';
    const MATH = 'x^2 - 1 = (x-1)(x+1)\nלכן x = 1';

    it('english is prose LTR even with digits and Latin letters', () => {
        expect(answerRenderPlan(ESSAY, 'english')).toEqual({ mode: 'prose', dir: 'ltr' });
    });
    it('mathematics is prose RTL (linear notation rides the bidi algorithm)', () => {
        expect(answerRenderPlan(MATH, 'mathematics')).toEqual({ mode: 'prose', dir: 'rtl' });
    });
    it('computer_science keeps the heuristic byte-for-byte', () => {
        expect(answerRenderPlan(ESSAY, 'computer_science')).toEqual({ mode: 'code', dir: 'ltr' });
        expect(answerRenderPlan('שלום עולם', 'computer_science')).toEqual({ mode: 'prose', dir: 'rtl' });
    });
    it('an absent subject (pre-seam row) falls back to the CS heuristic', () => {
        expect(answerRenderPlan(ESSAY, undefined).mode).toBe('code');
        expect(answerRenderPlan(ESSAY, null).mode).toBe('code');
    });
});
