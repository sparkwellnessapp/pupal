import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { renderToStaticMarkup } from 'react-dom/server';
import { RubricDocument } from './RubricDocument';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';
import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';
import type { Annotation } from '@/lib/api';

/**
 * PR-5 S2 §7 — the SSR render suite over all five golden benchmarks (sibling of
 * RubricEditor.render.test.tsx). vitest is node-env, so this proves STRUCTURE:
 * no empty text boxes at rest, identity headings, disclosures only where content
 * exists, no mutation on render. Interactive behavior is Playwright's job.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCHMARKS = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const FIXTURES = ['bagrut_899371', 'csharp_plane_combine', 'employee_course_select1', 'foundations_cs', 'hobby_tvshow'] as const;

function loadGolden(name: string): RubricQuestion[] {
    const raw = JSON.parse(readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8'));
    return hydrateAnyQuestions(raw.questions);
}

function walkSubs<T>(subs: RubricSubQuestion[] | undefined, f: (sq: RubricSubQuestion) => T[]): T[] {
    return (subs ?? []).flatMap((sq) => [...f(sq), ...walkSubs(sq.sub_questions, f)]);
}
function allSolutions(qs: RubricQuestion[]): (string | null | undefined)[] {
    return [...qs.map((q) => q.example_solution), ...qs.flatMap((q) => walkSubs(q.sub_questions, (sq) => [sq.example_solution]))];
}
function hasAnySolution(qs: RubricQuestion[]): boolean {
    return allSolutions(qs).some((s) => !!s && s.trim() !== '');
}

const render = (qs: RubricQuestion[], extra: Record<string, unknown> = {}) =>
    renderToStaticMarkup(<RubricDocument questions={qs} onQuestionsChange={() => {}} rubricName="מחוון בדיקה" {...extra} />);

describe.each(FIXTURES)('RubricDocument SSR — %s', (name) => {
    const qs = loadGolden(name);

    it('renders without error and shows question-1 identity heading', () => {
        const html = render(qs);
        expect(html).toContain('שאלה 1');
    });

    it('has NO edit boxes at rest (typography, not furniture)', () => {
        const html = render(qs);
        expect(html).not.toContain('<textarea');
        expect(html).not.toContain('<input');
    });

    it('renders a solution disclosure IFF a solution exists', () => {
        const html = render(qs);
        expect(html.includes('פתרון לדוגמה')).toBe(hasAnySolution(qs));
    });

    it('does not mutate the questions prop on render (displays, never fixes state)', () => {
        const before = JSON.stringify(qs);
        render(qs);
        expect(JSON.stringify(qs)).toBe(before);
    });
});

describe('RubricDocument SSR — bagrut nesting', () => {
    it('nested identity headings render ("סעיף" under "שאלה 1")', () => {
        const html = render(loadGolden('bagrut_899371'));
        expect(html).toContain('שאלה 1');
        expect(html).toContain('סעיף');
    });

    it('emits full dotted data-scope-id anchors for nested nodes', () => {
        const html = render(loadGolden('bagrut_899371'));
        // q1's first sub-question anchor is q1.<id> — a dotted path, not a bare id.
        expect(html).toMatch(/data-scope-id="q1\.[^"]+"/);
    });
});

describe('RubricDocument SSR — findings relocation (§6) + designed silence (E-5)', () => {
    const questions: RubricQuestion[] = [
        { question_id: 'q1', total_points: 3, criteria: [], sub_questions: [
            { sub_question_id: 'א', index: 0, points: 3, criteria: [
                { criterion_id: 'c1', index: 0, description: 'בדיקת נכונות', points: 2 },
                { criterion_id: 'c2', index: 1, description: 'יעילות', points: 1 }] },
        ] },
    ];

    it('zero findings → the warm reassurance line', () => {
        const html = render(questions, { annotations: [] });
        expect(html).toContain('ויוי לא מצאה אי-התאמות במחוון');
    });

    it('a criterion-anchored finding renders inline at its row', () => {
        const anns: Annotation[] = [{ id: 'a1', annotation_type: 'rubric_mismatch', severity: 'warning', message: 'סכום רכיבים אינו תואם', target_id: 'c1' }];
        const html = render(questions, { annotations: anns });
        expect(html).toContain('סכום רכיבים אינו תואם');
        expect(html).not.toContain('ויוי לא מצאה'); // findings present → no silence line
    });

    it('a finding puts an amber dot (aria "ממצא פתוח") on its section in the rail', () => {
        const anns: Annotation[] = [{ id: 'a1', annotation_type: 'rubric_mismatch', severity: 'warning', message: 'x', target_id: 'c1' }];
        const html = render(questions, { annotations: anns });
        expect(html).toContain('aria-label="ממצא פתוח"');
    });

    it('an ERROR shows the top summary with a naming-law jump label, not the raw id', () => {
        const anns: Annotation[] = [{ id: 'e1', annotation_type: 'invariant_violation', severity: 'error', message: 'סכום שגוי', target_id: 'q1.א' }];
        const html = render(questions, { annotations: anns });
        expect(html).toContain('יש לתקן לפני שמירה');
        expect(html).toContain('שאלה 1 · סעיף א'); // scopeLabel, not "q1.א"
        expect(html).not.toContain('>q1.א<');
    });
});

describe('RubricDocument SSR — a11y smoke + voice (E-5)', () => {
    const qs = loadGolden('employee_course_select1'); // direct-criteria questions → real tables

    it('the outline rail is a <nav> with an accessible name', () => {
        const html = render(qs);
        expect(html).toContain('<nav');
        expect(html).toContain('aria-label="מפת המחוון"');
    });

    it('criteria render with REAL <table> semantics (thead + the "קריטריון · נק\'" header), not card divs', () => {
        const html = render(qs);
        expect(html).toContain('<table');
        expect(html).toContain('<thead');
        expect(html).toContain('קריטריון');
    });

    it('every editable carries an aria-label (points, name)', () => {
        const html = render(qs);
        expect(html).toMatch(/aria-label="ניקוד קריטריון \d+ — לחצי לעריכה"/);
        expect(html).toContain('שם המחוון — לחצי לעריכה');
        expect(html).toContain('ניקוד מוצהר — לחצי לעריכה');
    });

    it('the voice-table micro-copy is the shipped string, not a placeholder (ghost add-row)', () => {
        expect(render(qs)).toContain('+ הוסיפי קריטריון');
    });
});
