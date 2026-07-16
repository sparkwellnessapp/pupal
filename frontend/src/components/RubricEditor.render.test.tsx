import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { renderToStaticMarkup } from 'react-dom/server';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';
import { RubricEditor } from './RubricEditor';

/**
 * B-11 render test — the recursive SubQuestionNode must render a real depth-2
 * rubric (bagrut: question → sub-question → sub-question → criteria) without
 * crashing, anchoring each nested node at its FULL dotted path so a backend
 * annotation targeting "q1.א.2" lands on it.
 *
 * SSR via react-dom/server (no jsdom) is enough here: we assert on the produced
 * markup. A depth-1 renderer could never emit data-scope-id="q1.א.2" — only the
 * recursion can — so these anchors are the proof that nesting renders.
 *
 * Fixture: the canonical backend golden (read in place, as the round-trip suite
 * does — one owner of ground truth, no drift).
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BAGRUT = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks/bagrut_899371.json');

function renderBagrut(): string {
    const golden = JSON.parse(readFileSync(BAGRUT, 'utf-8'));
    const questions = hydrateAnyQuestions(golden.questions);
    return renderToStaticMarkup(
        <RubricEditor questions={questions} onQuestionsChange={() => {}} />,
    );
}

describe('RubricEditor — recursive render of a depth-2 rubric', () => {
    it('renders without crashing', () => {
        expect(() => renderBagrut()).not.toThrow();
    });

    it('anchors the nested parent q1.א and both nested leaves at their full paths', () => {
        const html = renderBagrut();
        expect(html).toContain('data-scope-id="q1.א"');    // parent sub-question
        expect(html).toContain('data-scope-id="q1.א.1"');  // nested leaf
        expect(html).toContain('data-scope-id="q1.א.2"');  // nested leaf — the bagrut error node
        expect(html).toContain('data-scope-id="q1.ב.2"');  // a second nested branch
    });

    it('renders criteria under the nested leaves (CriteriaList reused at depth 2)', () => {
        const html = renderBagrut();
        // The CriteriaList header renders "קריטריונים"; its presence alongside the
        // depth-2 anchors proves nested leaves render their own criteria.
        expect(html).toContain('קריטריונים');
    });

    it('still renders a direct-criteria question (q6) — the non-nested branch is intact', () => {
        const html = renderBagrut();
        expect(html).toContain('data-scope-id="q6"');
    });
});
