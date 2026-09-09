import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { markerCountByScope, nextMarker, reviewMarkers } from './review-markers';
import { lookCount } from './look-count';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../backend/tests/fixtures/grade_review');
const readFixture = (name: string) =>
    JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8'));

describe('reviewMarkers — every kind R9 names, not just the evidence ones', () => {
    it('walks evidence, flags and dead scopes alike', () => {
        const markers = reviewMarkers({
            scope_outcomes: [
                {
                    question_id: 'q1', sub_question_id: 'א', graded_by: 'llm',
                    criterion_outcomes: [{
                        criterion_id: 'q1.א.c0',
                        flags: [{ reason: 'bounds_clamped' }],
                        checks: [
                            { check_id: 'k1', quote_status: 'exact' },
                            { check_id: 'k2', quote_status: 'not_found' },
                            { check_id: 'k3', quote_status: 'fuzzy' },
                        ],
                    }],
                },
                { question_id: 'q2', graded_by: 'failed' },
                { question_id: 'q3', graded_by: 'skipped_no_answer' },
            ],
        });

        expect(markers.map((m) => m.reason)).toEqual([
            'bounds_clamped', 'not_found', 'fuzzy', 'failed', 'skipped_no_answer',
        ]);
        expect(markers.map((m) => m.kind)).toEqual([
            'scope', 'check', 'check', 'scope', 'scope',
        ]);
        // Every marker knows which section it lives in, so the nav can follow.
        expect(markers.map((m) => m.scopeId)).toEqual(['q1.א', 'q1.א', 'q1.א', 'q2', 'q3']);
    });

    it('never stops on a scope the student was never owed', () => {
        expect(reviewMarkers({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'excluded_by_selection',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    checks: [{ check_id: 'k1', quote_status: 'not_found' }],
                }],
            }],
        })).toEqual([]);
    });

    it('does not stop twice for one problem', () => {
        const markers = reviewMarkers({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    flags: [{ reason: 'bounds_clamped' }, { reason: 'bounds_clamped' }],
                    checks: [],
                }],
            }],
        });
        expect(markers).toHaveLength(1);
    });

    it('does not double-count a v5 leaf via its legacy quote flag', () => {
        const markers = reviewMarkers({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0',
                    flags: [{ reason: 'quote_not_found' }],
                    checks: [{ check_id: 'k1', quote_status: 'not_found' }],
                }],
            }],
        });
        expect(markers).toHaveLength(1);
        expect(markers[0].kind).toBe('check');
    });

    /**
     * THE agreement that matters: the dashboard shows the server's
     * `look_count` and `F` makes one stop per marker. If these ever diverge,
     * a card promises "3 things to check" and the key finds two.
     */
    it('stops exactly look_count times, on every published fixture', () => {
        for (const name of ['dan_basiuk', 'din_ezra', 'moran_aharon', 'omer_gelber',
            'yonatan_basiuk', 'SYNTHETIC_edge_cases']) {
            const draft = readFixture(`draft_${name}.json`);
            expect(reviewMarkers(draft).length, name).toBe(lookCount(draft));
        }
    });
});

describe('nextMarker', () => {
    const markers = reviewMarkers({
        scope_outcomes: [{
            question_id: 'q1', graded_by: 'llm',
            criterion_outcomes: [{
                criterion_id: 'c0',
                checks: [
                    { check_id: 'a', quote_status: 'not_found' },
                    { check_id: 'b', quote_status: 'fuzzy' },
                ],
            }],
        }],
    });

    it('advances, and WRAPS rather than stopping dead', () => {
        expect(nextMarker(markers, null)?.id).toBe('a');
        expect(nextMarker(markers, markers[0].key)?.id).toBe('b');
        expect(nextMarker(markers, markers[1].key)?.id).toBe('a');
    });

    it('starts at the first marker when the key is unknown', () => {
        expect(nextMarker(markers, 'not-a-marker')?.id).toBe('a');
    });

    /**
     * THE ping-pong bug. One terminal carrying two different flags produces two
     * markers with the SAME id; walking by id finds the first every time, so F
     * bounces between two stops forever and never reaches the third.
     */
    it('walks past two markers that share an id', () => {
        const shared = reviewMarkers({
            scope_outcomes: [{
                question_id: 'q1', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'dup',
                    flags: [{ reason: 'bounds_clamped' }, { reason: 'closed_world_violation' }],
                    checks: [{ check_id: 'later', quote_status: 'not_found' }],
                }],
            }],
        });
        expect(shared).toHaveLength(3);
        expect(shared[0].id).toBe(shared[1].id);          // same id…
        expect(shared[0].key).not.toBe(shared[1].key);    // …different marker

        const first = nextMarker(shared, null)!;
        const second = nextMarker(shared, first.key)!;
        const third = nextMarker(shared, second.key)!;
        expect(third.id).toBe('later');                   // it got there
        expect(nextMarker(shared, third.key)!.key).toBe(first.key);   // and wrapped
    });

    it('is null on a clean test — the key simply does nothing', () => {
        expect(nextMarker([], 'a')).toBeNull();
    });
});

describe('markerCountByScope — the nav dot agrees with F', () => {
    it('counts every marker kind, per scope', () => {
        const markers = reviewMarkers({
            scope_outcomes: [
                {
                    question_id: 'q1', sub_question_id: 'א', graded_by: 'llm',
                    criterion_outcomes: [{
                        criterion_id: 'c0',
                        flags: [{ reason: 'bounds_clamped' }],
                        checks: [{ check_id: 'k1', quote_status: 'fuzzy' }],
                    }],
                },
                { question_id: 'q2', graded_by: 'failed' },
            ],
        });
        expect(markerCountByScope(markers)).toEqual({ 'q1.א': 2, q2: 1 });
    });

    it('sums to look_count on the real fixtures', () => {
        for (const name of ['din_ezra', 'SYNTHETIC_edge_cases']) {
            const draft = readFixture(`draft_${name}.json`);
            const byScope = markerCountByScope(reviewMarkers(draft));
            const summed = Object.values(byScope).reduce((n, v) => n + v, 0);
            expect(summed, name).toBe(lookCount(draft));
        }
    });
});
