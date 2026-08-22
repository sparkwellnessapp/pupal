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

    it('carries the advisory explanation and the manual route', () => {
        expect(html).toContain('רכיבי סעיף 2 מסתכמים');
        expect(html).toContain('עדכני את הקריטריונים בעצמך');
    });

    it('does NOT offer to leave a blocker as-is — the compiler would reject it anyway', () => {
        // §2 lists dismiss on advisories only. Offering «השאירי כך» on a live
        // invariant violation would promise something the system cannot honour.
        expect(html).not.toContain('השאירי כך');
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

describe('the steps wire — a structural proposal renders as ONE button', () => {
    const rootFix = {
        operation: 'reassign_subquestion',
        description: "העבירי את רכיב PrintLowRatingChannel לסעיף ג'",
        steps: [
            { op: 'move_criterion', scope: 'q2.ב', criterion_index: 6, to_scope: 'q2.ג' },
            { op: 'move_text', scope: 'q2.ב', to_scope: 'q2.ג', text: 'ג. כתבו' },
        ],
    };

    it('shows the imperative description; the machine steps never leak into copy', () => {
        const f = composeFindings([], [], [advisory({
            mistake_id: 'adj:q2:structural_mislabel', kind: 'structural_mislabel', target_id: 'q2',
            suggested_fix: rootFix,
        })])[0];
        const html = render(f);
        // (the trailing geresh renders HTML-escaped — assert up to it)
        expect(html).toContain('העבירי את רכיב PrintLowRatingChannel לסעיף ג');
        const visible = html.replace(/<[^>]*>/g, '');
        expect(visible).not.toContain('move_criterion');
        expect(visible).not.toContain('q2.ב');
        // no single displaced number exists for a structural plan — no false residual
        expect(html).not.toContain('בקובץ המקורי מצוין');
    });

    it('D3 — a fixless SHADOW with a live blocker points at its root and cannot be dismissed', () => {
        const f = composeFindings([], [live({ target_id: 'q2.ב' })], [advisory({
            mistake_id: 'pts:q2.ב', target_id: 'q2.ב', suggested_fix: null,
            explained_by: 'adj:q2:structural_mislabel',
        }), advisory({
            mistake_id: 'adj:q2:structural_mislabel', kind: 'structural_mislabel', target_id: 'q2',
            suggested_fix: rootFix,
        })]).find((x) => x.scopeId === 'q2.ב')!;
        const html = render(f);
        expect(f.fix).toBeNull();
        expect(html).toContain('עברי לממצא המקורי');
        expect(html).toContain('התיקון המוצע שם פותר גם את זה');
        // it is a LIVE violation: amber accent, and no «השאירי כך» escape hatch
        expect(html).toContain('border-amber-300');
        expect(html).not.toContain('השאירי כך');
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
