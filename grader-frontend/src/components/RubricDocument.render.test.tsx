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
        expect(html).toContain('הכל תקין - ויוי לא מצאה אי-התאמות במחוון');
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

describe('Round 2 — D3 header band / D5 points / D8 prose / D9 anchors', () => {
    const qs = loadGolden('bagrut_899371');

    it('D3: the band is ONE unit ABOVE the document body (not inside the card)', () => {
        const html = render(qs, { selectionGroups: [{ of_question_ids: ['q1', 'q2'], choose_k: 1 }] });
        const header = html.indexOf('<header');
        const body = html.indexOf('bg-white rounded-2xl shadow-sm ring-1 ring-surface-100');
        expect(header).toBeGreaterThan(-1);
        expect(body).toBeGreaterThan(header);          // band precedes the document surface
        expect(html).toContain('שם המחוון — לחצי לעריכה'); // name lives in the band
        expect(html).toContain('data-testid="rubric-achievable-total"');
    });

    it('D4: exactly ONE total renders, and it is the achievable one', () => {
        const html = render(qs);
        expect((html.match(/data-testid="rubric-achievable-total"/g) ?? []).length).toBe(1);
        expect(html).not.toContain('מוצהר');
    });

    it('D5: every point-bearing node exposes an edit affordance', () => {
        const html = render(qs);
        expect(html).toContain('aria-label="ניקוד שאלה 1 — לחצי לעריכה"');      // question
        expect(html).toContain('aria-label="ניקוד סעיף א — לחצי לעריכה"');       // sub-question
        expect(html).toContain('aria-label="ניקוד תת-סעיף 1 — לחצי לעריכה"');    // inner
    });

    it('D8: prose is editable and renders RICH at rest (marker-free, real table)', () => {
        const html = render(qs);
        expect(html).toContain('טקסט שאלה 2 — לחצי לעריכה');   // question prose editable
        expect(html).toMatch(/aria-label="טקסט (סעיף|תת-סעיף)[^"]*— לחצי לעריכה"/); // sub-question prose
        // display-rich: bagrut q2 carries [TABLE …] markers in its text; at rest the
        // teacher sees a table, never the marker (edit-raw restores the source).
        expect(html).not.toContain('[TABLE');
        expect(html).not.toContain('|---');
    });

    it('D9: every question section carries the scroll anchor + header offset', () => {
        const html = render(qs);
        // block:'start' honours scroll-margin-top; the class is what clears the
        // ~80px sticky app header so the TITLE lands visible (pixels are snap's job).
        for (const q of qs) {
            expect(html).toContain(`data-scope-id="${q.question_id}"`);
        }
        expect(html).toMatch(/class="scroll-mt-20[^"]*"[^>]*/);
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
    });

    // D4 — מוצהר leaves the header. The declared total keeps living in page state
    // (INV-R3 + dehydrate depend on it); it simply has no surface in the band, and
    // no orphaned edit affordance.
    it('the header exposes NO declared-total affordance (D4)', () => {
        const html = render(qs);
        expect(html).not.toContain('ניקוד מוצהר — לחצי לעריכה');
        expect(html).not.toContain('מוצהר');
    });

    it('the voice-table micro-copy is the shipped string, not a placeholder (ghost add-row)', () => {
        expect(render(qs)).toContain('+ הוסיפי קריטריון');
    });
});

describe('OutlineRail — nested, points-bearing, collapsible map', () => {
    const qs = loadGolden('bagrut_899371');
    const html = render(qs);
    const rail = html.slice(html.indexOf('<nav'), html.indexOf('</nav>'));

    it('every question row carries its points, named and on the numeric grid', () => {
        expect(rail).toContain('שאלה 1');
        // bagrut declares 25 per question. The DIGITS carry tabular-nums so the
        // numbers stay on one grid; the unit word must NOT be forced onto it.
        expect(rail).toMatch(/<span[^>]*tabular-nums[^>]*>25<\/span> נקודות/);
    });

    it('a parent row exposes a chevron with its own accessible name; a leaf does not', () => {
        // q1..q5 nest; the chevron is a SEPARATE control from the jump target
        expect(rail).toContain('aria-label="הרחיבי שאלה 1"');
        expect(rail).toContain('aria-expanded="false"');
    });

    it('the jump target is addressable per scope (navigation, not toggling)', () => {
        expect(rail).toContain('data-rail-link="q1"');
        expect(rail).toContain('data-rail-link="q6"');
    });

    it('collapsed by default when nothing is active — sub-rows are absent, not hidden', () => {
        // SSR has no IntersectionObserver, so activeId is null ⇒ nothing auto-expands.
        expect(rail).not.toContain('data-rail-link="q1.א"');
        expect(rail).not.toContain('תת-סעיף');
    });

    it('the rail stays a <nav> with its accessible name (E-2 contract intact)', () => {
        expect(html).toContain('aria-label="מפת המחוון"');
    });
});

describe('PR-6 — findings render in the mirror', () => {
    const questions: RubricQuestion[] = [
        { question_id: 'q1', total_points: 3, criteria: [], sub_questions: [
            { sub_question_id: 'א', index: 0, points: 3, criteria: [
                { criterion_id: 'c1', index: 0, description: 'בדיקת נכונות', points: 2 }] },
        ] },
    ];
    const blocker = {
        key: 'q1.א::point_sum', scopeId: 'q1.א', kind: 'point_sum' as const,
        status: 'open' as const, variant: 'blocking_fix' as const, severity: 'error' as const,
        hasLiveBlocker: true,
        liveMessage: 'סכום הנקודות של שאלה 1 · סעיף א (3 נקודות) שונה מסכום הקריטריונים (2 נקודות).',
        documentResidual: 'אזהרה: … מצהירה על 3 …',
        explanation: 'רכיבי הסעיף מסתכמים ל-2.', confidence: 'high' as const,
        fix: { target: 'sub_question' as const, newValue: 2, currentValue: 3, label: 'עדכני את הניקוד המוצהר ל-2' },
        mistakeId: 'pts:q1.א', annotationIds: ['rubric_mismatch:q1.א'],
    };

    it('renders the card at its scope, with the proposal', () => {
        const html = render(questions, { findings: [blocker] });
        expect(html).toContain('עדכני את הניקוד המוצהר ל-2');
        expect(html).toContain('data-finding-key="q1.א::point_sum"');
    });

    it('the rail dots a BLOCKER differently from an ADVISORY (§5 weight)', () => {
        const blockerHtml = render(questions, { findings: [blocker] });
        expect(blockerHtml).toContain('aria-label="ממצא פתוח"');

        const advisory = { ...blocker, severity: 'warning' as const, hasLiveBlocker: false, variant: 'advisory_fix' as const };
        const advisoryHtml = render(questions, { findings: [advisory] });
        expect(advisoryHtml).toContain('aria-label="המלצה פתוחה"');
        expect(advisoryHtml).not.toContain('aria-label="ממצא פתוח"');
    });

    it('a SETTLED finding dots nothing — the rail maps what is left to look at', () => {
        const html = render(questions, { findings: [{ ...blocker, status: 'dismissed' as const }] });
        expect(html).not.toContain('aria-label="ממצא פתוח"');
        expect(html).not.toContain('aria-label="המלצה פתוחה"');
    });

    it('§5: the header counts blockers and advisories separately', () => {
        const advisory = { ...blocker, key: 'q1::sel', scopeId: 'q1', severity: 'warning' as const, hasLiveBlocker: false, variant: 'advisory_fix' as const };
        const html = render(questions, { findings: [blocker, advisory] });
        expect(html).toContain('ממצא אחד לתיקון · המלצה אחת');
    });

    it('§7: a PARTIAL advisory scan says so; a complete one stays quiet', () => {
        expect(render(questions, { advisoryScan: 'partial' })).toContain('חלק מבדיקות ההמלצות לא הושלמו');
        expect(render(questions, { advisoryScan: 'complete' })).not.toContain('לא הושלמו');
        // unknown (a pre-3.5.0 draft) makes NO claim either way
        expect(render(questions, { advisoryScan: 'unknown' })).not.toContain('לא הושלמו');
    });
});
