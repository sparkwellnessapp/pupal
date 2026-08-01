import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { hydrateAnyQuestions } from '@/utils/rubric-transform';
import { validateAllQuestions } from '@/utils/rubric-validation';
import { composeFindings, acknowledgedIdsFor, type PedagogicalMistakeLike } from './findings';
import {
    resolveScopePath, applyFindingFix,
    recordFixApplied, clearFixApplied, recordDismissed, clearDismissed,
} from './findings-ops';
import type { RubricQuestion } from '@/types/rubric';
import type { Annotation } from '@/lib/api';

/**
 * PR-6 §3/§4 — the demo journey and the dismiss journey, proved at the ops layer
 * on the REAL bagrut fixture: apply → the validator itself closes the card → undo
 * reopens it and erases the record; dismiss → persists and stops the re-ask.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const BENCH = path.resolve(HERE, '../../../backend/tests/rubric_eval_suite/benchmarks');
const bagrut = (): RubricQuestion[] =>
    hydrateAnyQuestions(JSON.parse(readFileSync(path.join(BENCH, 'bagrut_899371.json'), 'utf-8')).questions);

const clock = () => '2026-07-30T12:00:00Z';

/** The real Step 2c advisory for bagrut's q1.א.2 (post-3.5.0 emission). */
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
const residual: Annotation[] = [{
    id: 'rubric_mismatch:q1.א.2', annotation_type: 'rubric_mismatch', severity: 'warning',
    message: 'אזהרה: … מצהירה על 3 נקודות …', target_id: 'q1.א.2',
}];

const composeFor = (qs: RubricQuestion[], mistakes: PedagogicalMistakeLike[]) =>
    composeFindings(residual, Array.from(validateAllQuestions(qs).values()).flat(), mistakes, qs);

/** Apply the q1.א.2 finding's fix and return the new tree (must succeed). */
const applied = (qs: RubricQuestion[], mistakes: PedagogicalMistakeLike[]): RubricQuestion[] => {
    const f = composeFor(qs, mistakes).find((x) => x.scopeId === 'q1.א.2')!;
    const out = applyFindingFix(qs, f);
    expect(out).not.toBeNull();
    expect(out!.declaredTotal).toBeUndefined();
    return out!.questions;
};

describe('resolveScopePath — scope ids → the indices the pure ops address', () => {
    it('resolves a question, a sub-question and a nested sub-question', () => {
        const qs = bagrut();
        expect(resolveScopePath(qs, 'q1')).toEqual({ qIndex: 0, sqPath: [] });
        expect(resolveScopePath(qs, 'q1.א')).toEqual({ qIndex: 0, sqPath: [0] });
        expect(resolveScopePath(qs, 'q1.א.2')).toEqual({ qIndex: 0, sqPath: [0, 1] });
    });
    it('returns null for an unresolvable id — degrade to no-fix, never a wrong write', () => {
        const qs = bagrut();
        expect(resolveScopePath(qs, 'q9')).toBeNull();
        expect(resolveScopePath(qs, 'q1.ZZ')).toBeNull();
        expect(resolveScopePath(qs, null)).toBeNull();
    });
});

describe('§3 — THE DEMO JOURNEY on the real bagrut fixture', () => {
    it('the card starts as an open blocker carrying Vivi\'s proposal', () => {
        const f = composeFor(bagrut(), [advisory()]).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f.status).toBe('open');
        expect(f.variant).toBe('blocking_fix');
        expect(f.fix?.label).toBe('עדכני את הניקוד המוצהר ל-2');
    });

    it('APPLY sets the declared value to her own children-sum, through the pure ops', () => {
        const next = applied(bagrut(), [advisory()]);
        expect(next[0].sub_questions[0].sub_questions![1].points).toBe(2);   // 1.5 + 0.5
    });

    it('the VALIDATOR closes the card — resolution is never static bookkeeping', () => {
        const next = applied(bagrut(), [advisory()]);
        // Note: provenance is NOT what resolves it — recompose with the SAME advisory.
        const f1 = composeFor(next, [advisory()]).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f1.status).toBe('resolved');
        expect(f1.hasLiveBlocker).toBe(false);
    });

    it('the honest residual survives resolution ("בקובץ המקורי עדיין מצוין 3")', () => {
        const next = applied(bagrut(), [advisory()]);
        const f = composeFor(next, [advisory()]).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f.documentResidual).toContain('3');
        expect(f.fix?.displayCurrentValue).toBe(3);   // the resolved card's residual number
    });

    it('a resolved finding acks — it saves silently, never re-asked', () => {
        const next = applied(bagrut(), [advisory()]);
        const mistakes = recordFixApplied([advisory()], 'pts:q1.א.2', clock);
        expect(acknowledgedIdsFor(composeFor(next, mistakes))).toContain('rubric_mismatch:q1.א.2');
    });

    it('APPLY never mutates its input (the undo stack shares structure)', () => {
        const qs = bagrut();
        const snapshot = JSON.stringify(qs);
        applied(qs, [advisory()]);
        expect(JSON.stringify(qs)).toBe(snapshot);
    });

    it('a fix whose plan no longer resolves is WITHHELD, never mis-applied', () => {
        const qs = bagrut();
        // she deleted the whole sub-question the fix addresses
        const edited = qs.map((q, i) => (i !== 0 ? q : {
            ...q,
            sub_questions: q.sub_questions.map((sq, j) => (j !== 0 ? sq : {
                ...sq, sub_questions: sq.sub_questions!.filter((_, k) => k !== 1),
            })),
        }));
        const f = composeFor(edited, [advisory()]).find((x) => x.scopeId === 'q1.א.2');
        expect(f?.fix ?? null).toBeNull();               // composition preflight withdrew it
    });

    it('UNDO reopens the card AND erases the record — an undone fix is not applied', () => {
        const qs = bagrut();
        const after = applied(qs, [advisory()]);
        let mistakes = recordFixApplied([advisory()], 'pts:q1.א.2', clock);
        expect(mistakes[0].fix_applied).toBe(true);

        // «בטלי»: the E-1 stack restores `qs`, and the provenance is cleared with it.
        mistakes = clearFixApplied(mistakes, 'pts:q1.א.2');
        const reopened = composeFor(qs, mistakes).find((x) => x.scopeId === 'q1.א.2')!;

        expect(after[0].sub_questions[0].sub_questions![1].points).toBe(2);   // it HAD applied
        expect(reopened.status).toBe('open');            // the card is open again
        expect(mistakes[0].fix_applied).toBeNull();      // and the trail does not lie
        expect(mistakes[0].fix_applied_at).toBeNull();
        expect(acknowledgedIdsFor([reopened])).toEqual([]);   // so it is NOT acked
    });

    it('a MANUAL edit resolves it too — the same signal, no fix payload involved', () => {
        const qs = bagrut();
        // she edits the criteria herself so the sum matches the declared 3
        const edited = qs.map((q, i) => (i !== 0 ? q : {
            ...q,
            sub_questions: q.sub_questions.map((sq, j) => (j !== 0 ? sq : {
                ...sq,
                sub_questions: sq.sub_questions!.map((inner, k) => (k !== 1 ? inner : {
                    ...inner,
                    criteria: inner.criteria.map((c, ci) => (ci === 0 ? { ...c, points: 2.5 } : c)),
                })),
            })),
        }));
        const f = composeFor(edited, [advisory()]).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f.status).toBe('resolved');
    });
});

describe('§4 — THE DISMISS JOURNEY: she overrules Vivi and that is respected', () => {
    it('dismissal outranks a still-live blocker and stops the re-ask', () => {
        const qs = bagrut();                                   // the mismatch is REAL and stays
        const mistakes = recordDismissed([advisory()], 'pts:q1.א.2', clock);
        const f = composeFor(qs, mistakes).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f.status).toBe('dismissed');
        expect(f.hasLiveBlocker).toBe(true);                   // honest: it is still there
        expect(acknowledgedIdsFor([f])).toEqual(['rubric_mismatch:q1.א.2']);
    });

    it('the decision is stamped, and survives a JSON round trip (save → reopen)', () => {
        const mistakes = recordDismissed([advisory()], 'pts:q1.א.2', clock);
        expect(mistakes[0].dismissed_at).toBe('2026-07-30T12:00:00Z');
        const revived = JSON.parse(JSON.stringify(mistakes)) as PedagogicalMistakeLike[];
        const f = composeFor(bagrut(), revived).find((x) => x.scopeId === 'q1.א.2')!;
        expect(f.status).toBe('dismissed');
    });

    it('she can reopen her own dismissal — absence of a record is the honest state', () => {
        let mistakes = recordDismissed([advisory()], 'pts:q1.א.2', clock);
        mistakes = clearDismissed(mistakes, 'pts:q1.א.2');
        expect(mistakes[0].dismissed).toBeNull();
        expect(composeFor(bagrut(), mistakes)[0].status).toBe('open');
    });

    it('recording NEVER mutates its input', () => {
        const mistakes = [advisory()];
        const snapshot = JSON.stringify(mistakes);
        recordDismissed(mistakes, 'pts:q1.א.2', clock);
        recordFixApplied(mistakes, 'pts:q1.א.2', clock);
        expect(JSON.stringify(mistakes)).toBe(snapshot);
    });

    it('touches only the addressed mistake', () => {
        const other = advisory({ mistake_id: 'pts:q2', target_id: 'q2' });
        const out = recordDismissed([advisory(), other], 'pts:q1.א.2', clock);
        expect(out[1]).toEqual(other);
    });
});
