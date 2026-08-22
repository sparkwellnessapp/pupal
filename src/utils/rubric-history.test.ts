import { describe, it, expect } from 'vitest';
import { pushSnapshot, popSnapshot, HISTORY_CAP, type RubricSnapshot } from './rubric-history';
import { changedPointNodeIds } from './points-cascade';
import type { RubricQuestion } from '@/types/rubric';

const snap = (name: string): RubricSnapshot => ({ questions: [], declaredTotal: undefined, name });

describe('rubric-history — bounded undo stack (E-1)', () => {
    it('push then pop restores the pushed snapshot (LIFO)', () => {
        let s: RubricSnapshot[] = [];
        s = pushSnapshot(s, snap('a'));
        s = pushSnapshot(s, snap('b'));
        const popB = popSnapshot(s);
        expect(popB.snapshot?.name).toBe('b');
        const popA = popSnapshot(popB.stack);
        expect(popA.snapshot?.name).toBe('a');
        expect(popSnapshot(popA.stack).snapshot).toBeNull();
    });

    it('is bounded at HISTORY_CAP, dropping the oldest', () => {
        let s: RubricSnapshot[] = [];
        for (let i = 0; i < HISTORY_CAP + 10; i++) s = pushSnapshot(s, snap(`s${i}`));
        expect(s).toHaveLength(HISTORY_CAP);
        expect(s[0].name).toBe(`s${10}`);                 // first 10 dropped
        expect(s[s.length - 1].name).toBe(`s${HISTORY_CAP + 9}`);
    });

    it('stores questions BY REFERENCE — structural sharing, not a deep copy', () => {
        const questions: RubricQuestion[] = [{ question_id: 'q1', total_points: 1, criteria: [], sub_questions: [] }];
        const s = pushSnapshot([], { questions, declaredTotal: 1, name: 'x' });
        // The very same array object is retained — this is what makes 50 snapshots trivial.
        expect(s[0].questions).toBe(questions);
    });

    it('never mutates the input stack (immutable)', () => {
        const base: RubricSnapshot[] = [snap('a')];
        const next = pushSnapshot(base, snap('b'));
        expect(base).toHaveLength(1);
        expect(next).toHaveLength(2);
        expect(popSnapshot(next).stack).not.toBe(next);
    });
});

describe('changedPointNodeIds — the E-3 cascade hook (keys, not pixels)', () => {
    const tree = (leafPts: number, otherPts: number): RubricQuestion[] => ([
        { question_id: 'q1', total_points: leafPts + otherPts, criteria: [], sub_questions: [
            { sub_question_id: 'א', index: 0, points: leafPts, criteria: [
                { criterion_id: 'c1', index: 0, description: '', points: leafPts }] },
            { sub_question_id: 'ב', index: 1, points: otherPts, criteria: [
                { criterion_id: 'c2', index: 0, description: '', points: otherPts }] },
        ] },
    ]);

    it('reports exactly the edited leaf AND the ancestors that moved', () => {
        const before = tree(2, 3);           // q1=5, א=2(c1=2), ב=3(c2=3)
        const after = tree(4, 3);            // c1 2→4, א 2→4, q1 5→7 ; ב untouched
        const changed = changedPointNodeIds(before, after);
        expect(Array.from(changed).sort()).toEqual(['c1', 'q1', 'א'].sort());
        expect(changed.has('c2')).toBe(false);
        expect(changed.has('ב')).toBe(false);
    });

    it('a newly-added node is not a cascade change', () => {
        const before = tree(2, 3);
        const after = tree(2, 3);
        (after[0].criteria as RubricQuestion['criteria']).push({ criterion_id: 'cNew', index: 0, description: '', points: 0 });
        expect(changedPointNodeIds(before, after).size).toBe(0); // nothing MOVED
    });
});
