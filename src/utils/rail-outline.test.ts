import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { buildRailOutline, type RailNode } from './rail-outline';
import { hydrateAnyQuestions } from './rubric-transform';
import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';

/**
 * The rail is a NAVIGATION surface, so its one non-negotiable property is that
 * every `id` is a real anchor: identical to the `data-scope-id` the document
 * renders, which is what `scrollToScope` queries. These tests pin that
 * correspondence against the real golden fixtures — a rail row that cannot be
 * jumped to is worse than no row.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const load = (name: string): RubricQuestion[] =>
    hydrateAnyQuestions(JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8')).questions);

const flatten = (nodes: RailNode[]): RailNode[] =>
    nodes.flatMap((n) => [n, ...flatten(n.children)]);

/** The ids the DOCUMENT emits as data-scope-id, derived independently of the rail. */
function documentScopeIds(questions: RubricQuestion[]): string[] {
    const out: string[] = [];
    const walk = (subs: RubricSubQuestion[] | undefined, prefix: string) => {
        (subs ?? []).forEach((sq) => {
            const id = `${prefix}.${sq.sub_question_id}`;
            out.push(id);
            walk(sq.sub_questions, id);
        });
    };
    questions.forEach((q) => { out.push(q.question_id); walk(q.sub_questions, q.question_id); });
    return out;
}

describe('buildRailOutline — anchors match the document exactly', () => {
    it.each(['bagrut_899371', 'csharp_plane_combine', 'employee_course_select1', 'foundations_cs', 'hobby_tvshow'])(
        '%s: every rail id is a real scope anchor, and none is missing',
        (fixture) => {
            const qs = load(fixture);
            const railIds = flatten(buildRailOutline(qs)).map((n) => n.id);
            expect(railIds).toEqual(documentScopeIds(qs));
        },
    );
});

describe('buildRailOutline — shape', () => {
    const bagrut = buildRailOutline(load('bagrut_899371'));

    it('recurses to FULL depth (bagrut nests 3 levels)', () => {
        expect(Math.max(...flatten(bagrut).map((n) => n.depth))).toBe(2);
        const q1a = bagrut[0].children[0];
        expect(q1a.id).toBe('q1.א');
        expect(q1a.children.map((c) => c.id)).toEqual(['q1.א.1', 'q1.א.2']);
    });

    it('carries each node its OWN points', () => {
        expect(bagrut[0].points).toBe(25);                       // שאלה 1
        expect(bagrut[0].children[0].points).toBe(15);           // סעיף א
        expect(bagrut[0].children[0].children[0].points).toBe(12); // תת-סעיף 1
    });

    it('labels speak the document naming law (שאלה / סעיף / תת-סעיף)', () => {
        expect(bagrut[0].label).toBe('שאלה 1');
        expect(bagrut[0].children[0].label).toBe('סעיף א');
        expect(bagrut[0].children[0].children[0].label).toBe('תת-סעיף 1');
    });

    it('a direct-criteria question is a childless leaf (no phantom expander)', () => {
        const flat = buildRailOutline(load('foundations_cs'));
        expect(flat.every((n) => n.depth === 0)).toBe(true);
        expect(flat.some((n) => n.children.length > 0)).toBe(true); // foundations DOES nest
    });

    it('a teacher TITLE overrides the positional label (same rule as the heading)', () => {
        const qs: RubricQuestion[] = [{
            question_id: 'q1', total_points: 10, criteria: [], sub_questions: [
                { sub_question_id: 'א', index: 0, points: 10, title: 'חלק תיאורטי', criteria: [] },
            ],
        }];
        expect(buildRailOutline(qs)[0].children[0].label).toBe('חלק תיאורטי');
    });

    it('is pure — building twice yields equal trees and never mutates input', () => {
        const qs = load('bagrut_899371');
        const snapshot = JSON.stringify(qs);
        expect(JSON.stringify(buildRailOutline(qs))).toBe(JSON.stringify(buildRailOutline(qs)));
        expect(JSON.stringify(qs)).toBe(snapshot);
    });
});
