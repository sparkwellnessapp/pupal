import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { FindingCard } from './FindingCard';
import { composeFindings, type PedagogicalMistakeLike } from '@/utils/findings';
import type { Annotation } from '@/lib/api';
import type { ValidationIssue } from '@/utils/rubric-validation';

/**
 * PR-6 §2 — the card's contract, at the markup level.
 *
 * The property under test is HONESTY, not looks: the present tense may only come
 * from live recomputation, the original document may only be spoken of in the past,
 * a proposal is always a button and never a fait accompli, and nothing ever
 * silently disappears.
 */

const live = (o: Partial<ValidationIssue> = {}): ValidationIssue => ({
    key: 'inv-r1b-q1.א.2', invariant: 'INV-R1b', severity: 'error',
    message: 'סכום הנקודות של שאלה 1 · סעיף א · תת-סעיף 2 (3 נקודות) שונה מסכום הקריטריונים (2 נקודות).',
    target_id: 'q1.א.2', ...o,
} as ValidationIssue);
const residual: Annotation = {
    id: 'rubric_mismatch:q1.א.2', annotation_type: 'rubric_mismatch', severity: 'warning',
    message: 'אזהרה: … מצהירה על 3 נקודות …', target_id: 'q1.א.2',
};
const advisory = (o: Partial<PedagogicalMistakeLike> = {}): PedagogicalMistakeLike => ({
    mistake_id: 'pts:q1.א.2', kind: 'point_sum_mismatch', target_id: 'q1.א.2',
    explanation: 'רכיבי סעיף 2 מסתכמים ל-2 אך נקודות הסעיף הן 3.',
    evidence: { children_sum: '2.0', declared: '3' },
    suggested_fix: {
        operation: 'adjust_points', description: 'עדכני את הניקוד המוצהר ל-2',
        params: { target: 'sub_question', field: 'points', new_value: '2.0', current_value: '3' },
    },
    requires_teacher_input: true, confidence: 1.0, ...o,
});

const noop = () => {};
const render = (f: ReturnType<typeof composeFindings>[number]) => renderToStaticMarkup(
    <FindingCard finding={f} scopeText="שאלה 1 · סעיף א · תת-סעיף 2"
        onApplyFix={noop} onUndoFix={noop} onDismiss={noop} onReopen={noop} onJump={noop} />,
);

const openBlocker = () => composeFindings([residual], [live()], [advisory()])[0];

describe('variant 1 — blocking + fix (the demo moment)', () => {
    const html = render(openBlocker());

    it('offers the proposal as a BUTTON she must press, never as something done', () => {
        expect(html).toContain('<button');
        expect(html).toContain('עדכני את הניקוד המוצהר ל-2');
    });

    it('states the present tense ONLY from live recomputation', () => {
        expect(html).toContain('שונה מסכום הקריטריונים');
    });

    it('speaks of the original document in the PAST, with its own number', () => {
        expect(html).toContain('בקובץ המקורי מצוין 3');
    });

    it('carries the advisory explanation and both alternative paths', () => {
        expect(html).toContain('רכיבי סעיף 2 מסתכמים');
        expect(html).toContain('עדכני את הקריטריונים בעצמך');   // the manual route
        expect(html).toContain('השאירי כך');                    // overrule Vivi
    });

    it('never leaks a raw scope id into anything she can READ', () => {
        // Machine anchors (data-finding-key, data-scope-id) legitimately carry ids —
        // that is how jumping works. The naming law governs visible TEXT.
        const visible = html.replace(/<[^>]*>/g, '');
        expect(visible).not.toContain('q1.א.2');
        expect(visible).not.toContain('pts:');
        expect(visible).not.toContain('rubric_mismatch');
    });
});

describe('variant 2 — advisory + fix, non-blocking', () => {
    it('renders the proposal without the blocking accent', () => {
        // no live entry ⇒ not a blocker; a structural advisory that still has a fix
        const f = composeFindings([], [], [advisory({
            mistake_id: 'mis:q2', kind: 'structural_mislabel', target_id: 'q2',
        })])[0];
        const html = render(f);
        expect(f.variant).toBe('advisory_fix');
        expect(html).toContain('עדכני את הניקוד המוצהר ל-2');
        expect(html).not.toContain('border-amber-300');
    });
});

describe('variant 3 — advisory, info-only (no mechanical fix exists)', () => {
    const f = composeFindings([], [], [advisory({
        mistake_id: 'selnorm:sg0', kind: 'selection_normalization', target_id: null,
        explanation: 'הבחירה היא 1 מתוך 2 שאלות, אך לשאלות ניקוד שונה.',
        suggested_fix: null, evidence: null,
    })])[0];
    const html = render(f);

    it('offers navigation and dismissal — never an invented number', () => {
        expect(f.variant).toBe('advisory_info');
        expect(html).toContain('עברי ל');
        expect(html).toContain('השאירי כך');
        expect(html).not.toContain('עדכני את הניקוד');
    });
});

describe('lifecycle — nothing vanishes, nothing re-asks', () => {
    it('RESOLVED collapses to a ✓ WITH the honest residual', () => {
        const f = composeFindings([residual], [], [advisory()])[0];
        const html = render(f);
        expect(f.status).toBe('resolved');
        expect(html).toContain('תוקן במחוון');
        expect(html).toContain('בקובץ המקורי עדיין מצוין 3');   // the file still says 3
        expect(html).toContain('בטלי');                          // and it is reversible
    });

    it('DISMISSED collapses to HER decision, distinct from resolved', () => {
        const f = composeFindings([residual], [live()], [advisory({ dismissed: true })])[0];
        const html = render(f);
        expect(html).toContain('נשאר כפי שהוא — לבחירתך');
        expect(html).not.toContain('תוקן במחוון');
        expect(html).toContain('החזירי את הממצא');               // reversible too
    });

    it('a settled card no longer nags with buttons to act on', () => {
        const html = render(composeFindings([residual], [], [advisory()])[0]);
        expect(html).not.toContain('עדכני את הניקוד המוצהר');
        expect(html).not.toContain('השאירי כך');
    });
});
