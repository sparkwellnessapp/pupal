import { describe, it, expect } from 'vitest';
import {
    countFindings, countCriteria, resolveRubricName, selectionSummaryLine,
    pluralHe, findingsWaitingLabel, errorsBadgeLabel, classifyExtractionError,
    findingSectionsByQuestion,
} from './session-spine';
import { isOpenFinding, dedupeOpenFindings } from './finding-severity';
import type { Annotation, SelectionGroup } from '@/lib/api';
import type { RubricQuestion } from '@/types/rubric';

function ann(target_id: string | null, severity: 'error' | 'warning' | 'info'): Annotation {
    return { id: `${target_id}-${severity}`, annotation_type: 'invariant_violation', severity, message: '', target_id };
}

describe('countFindings — distinct node, extraction+live deduped (flaw-1 ruling)', () => {
    it('the bagrut case: rubric_mismatch(warning) + INV-R1b(error) on q1.א.2 = ONE finding', () => {
        const anns = [ann('q1.א.2', 'warning'), ann('q1.א.2', 'error')];
        expect(countFindings(anns)).toBe(1);
    });
    it('distinct nodes count separately; info is ignored', () => {
        expect(countFindings([ann('q1.א.2', 'error'), ann('q2', 'warning'), ann('q3', 'info')])).toBe(2);
    });
    it('null-target (rubric-scope) findings count individually', () => {
        expect(countFindings([ann(null, 'error'), ann('q1', 'error')])).toBe(2);
    });
    it('no findings → 0', () => {
        expect(countFindings([ann('q1', 'info')])).toBe(0);
        expect(countFindings([])).toBe(0);
    });
});

describe('finding-severity — the shared predicate + dedup module (F6)', () => {
    it('isOpenFinding: error/warning yes, info no', () => {
        expect(isOpenFinding(ann('q1', 'error'))).toBe(true);
        expect(isOpenFinding(ann('q1', 'warning'))).toBe(true);
        expect(isOpenFinding(ann('q1', 'info'))).toBe(false);
    });
    it('dedupeOpenFindings collapses nodes, counts globals', () => {
        const { nodeTargets, globalCount } = dedupeOpenFindings([
            ann('q1.א.2', 'warning'), ann('q1.א.2', 'error'), ann('q2', 'error'),
            ann(null, 'error'), ann('q3', 'info'),
        ]);
        expect(Array.from(nodeTargets).sort()).toEqual(['q1.א.2', 'q2']);
        expect(globalCount).toBe(1);
    });
    it('countFindings === nodeTargets.size + globalCount (same module, one truth)', () => {
        const anns = [ann('q1.א.2', 'warning'), ann('q1.א.2', 'error'), ann(null, 'error')];
        const { nodeTargets, globalCount } = dedupeOpenFindings(anns);
        expect(countFindings(anns)).toBe(nodeTargets.size + globalCount);
    });
});

describe('findingSectionsByQuestion — E-2 rail dots, all three target_id shapes', () => {
    // q1 nested (א → leaf "2" with criteria c2/c3); q2 direct criteria (c4); q3 empty.
    const questions: RubricQuestion[] = [
        { question_id: 'q1', total_points: 0, criteria: [], sub_questions: [
            { sub_question_id: 'א', index: 0, points: 0, criteria: [], sub_questions: [
                { sub_question_id: '2', index: 0, points: 0, criteria: [
                    { criterion_id: 'c2', index: 0, description: '', points: 0,
                      sub_criteria: [{ sub_criterion_id: 'sc1', index: 0, description: '', points: 0 }] },
                    { criterion_id: 'c3', index: 1, description: '', points: 0 }] },
            ] },
        ] },
        { question_id: 'q2', total_points: 0, sub_questions: [], criteria: [
            { criterion_id: 'c4', index: 0, description: '', points: 0 }] },
        { question_id: 'q3', total_points: 0, sub_questions: [], criteria: [] },
    ];

    it('shape 1 — bare question id', () => {
        expect(Array.from(findingSectionsByQuestion([ann('q2', 'error')], questions))).toEqual(['q2']);
    });
    it('shape 2 — full dotted path resolves to its top question', () => {
        expect(Array.from(findingSectionsByQuestion([ann('q1.א.2', 'error')], questions))).toEqual(['q1']);
    });
    it('shape 3 — bare descendant id (criterion / sub-question / sub-criterion) tree-walks to its question', () => {
        expect(Array.from(findingSectionsByQuestion([ann('c3', 'error')], questions))).toEqual(['q1']);
        expect(Array.from(findingSectionsByQuestion([ann('א', 'warning')], questions))).toEqual(['q1']);
        expect(Array.from(findingSectionsByQuestion([ann('sc1', 'error')], questions))).toEqual(['q1']);
        expect(Array.from(findingSectionsByQuestion([ann('c4', 'error')], questions))).toEqual(['q2']);
    });
    it('dedups: two findings on q1 (different nodes) → one section', () => {
        const s = findingSectionsByQuestion([ann('q1.א.2', 'error'), ann('c3', 'warning')], questions);
        expect(Array.from(s)).toEqual(['q1']);
    });
    it('rubric-scope (null) findings dot no section; info is ignored', () => {
        expect(findingSectionsByQuestion([ann(null, 'error'), ann('q2', 'info')], questions).size).toBe(0);
    });
    it('an unknown target id is skipped, never throws', () => {
        expect(findingSectionsByQuestion([ann('ghost_id', 'error')], questions).size).toBe(0);
    });
});

describe('countCriteria — recursive, any depth', () => {
    it('sums leaf criteria across nested sub-questions', () => {
        const questions: RubricQuestion[] = [
            { question_id: 'q1', total_points: 0, criteria: [], sub_questions: [
                { sub_question_id: 'א', index: 0, points: 0, criteria: [], sub_questions: [
                    { sub_question_id: '1', index: 0, points: 0, criteria: [
                        { criterion_id: 'c1', index: 0, description: '', points: 0 }] },
                    { sub_question_id: '2', index: 1, points: 0, criteria: [
                        { criterion_id: 'c2', index: 0, description: '', points: 0 },
                        { criterion_id: 'c3', index: 1, description: '', points: 0 }] },
                ] },
            ] },
            { question_id: 'q2', total_points: 0, sub_questions: [], criteria: [
                { criterion_id: 'c4', index: 0, description: '', points: 0 }] },
        ];
        expect(countCriteria(questions)).toBe(4); // 1 + 2 nested + 1 direct
    });
});

describe('resolveRubricName — precedence captured > inferred > filename', () => {
    it('prefers captured', () => {
        expect(resolveRubricName('בגרות תשפ"ו', 'inferred', 'file.docx')).toBe('בגרות תשפ"ו');
    });
    it('falls back to inferred then filename', () => {
        expect(resolveRubricName('  ', 'מבחן מסכם', 'file.docx')).toBe('מבחן מסכם');
        expect(resolveRubricName(null, null, 'בגרות 2026.docx')).toBe('בגרות 2026');
    });
    it('never empty', () => {
        expect(resolveRubricName(null, null, null)).toBe('מחוון');
        expect(resolveRubricName('', '', '.docx')).toBe('מחוון');
    });
});

describe('selectionSummaryLine', () => {
    const grp = (k: number, ids: string[]): SelectionGroup =>
        ({ group_id: 'g', label: '', choose_k: k, of_question_ids: ids } as SelectionGroup);
    it('renders "מבחן בחירה: מענה על k מתוך N שאלות"', () => {
        expect(selectionSummaryLine([grp(4, ['q1', 'q2', 'q3', 'q4', 'q5', 'q6'])], 6))
            .toBe('מבחן בחירה: מענה על 4 מתוך 6 שאלות');
    });
    it('null when not a selection exam', () => {
        expect(selectionSummaryLine([], 6)).toBeNull();
        expect(selectionSummaryLine(null, 6)).toBeNull();
    });
});

describe('Hebrew pluralization', () => {
    it('pluralHe uses the singular phrase for 1, "N noun" otherwise', () => {
        expect(pluralHe(1, 'שגיאה אחת', 'שגיאות')).toBe('שגיאה אחת');
        expect(pluralHe(2, 'שגיאה אחת', 'שגיאות')).toBe('2 שגיאות');
        expect(pluralHe(0, 'שגיאה אחת', 'שגיאות')).toBe('0 שגיאות');
    });
    it('findingsWaitingLabel: verb agrees (מחכה/מחכים)', () => {
        expect(findingsWaitingLabel(1)).toBe('ממצא אחד מחכה לאישורך');
        expect(findingsWaitingLabel(3)).toBe('3 ממצאים מחכים לאישורך');
        expect(findingsWaitingLabel(0)).toContain('תקין');
    });
    it('errorsBadgeLabel', () => {
        expect(errorsBadgeLabel(1)).toBe('שגיאה אחת');
        expect(errorsBadgeLabel(4)).toBe('4 שגיאות');
    });
});

describe('classifyExtractionError — blame-correct, never raw-English headline', () => {
    it('transport/timeout/budget → ours, transient', () => {
        const c = classifyExtractionError('httpx.ReadTimeout: deadline exceeded (budget 840s)');
        expect(c.blameOurs).toBe(true);
        expect(c.body).toContain('לא בקובץ שלך');
        expect(c.headline).not.toMatch(/[a-z]/i); // no raw English in the headline
    });
    it('quota → ours', () => {
        expect(classifyExtractionError('insufficient_quota 429').blameOurs).toBe(true);
    });
    it('parse/docx → the file may be the cause (blameOurs false), still gentle', () => {
        const c = classifyExtractionError('Failed to parse DOCX: corrupt');
        expect(c.blameOurs).toBe(false);
        expect(c.headline).toContain('קובץ');
    });
    it('unknown → honest-generic, ours-leaning', () => {
        const c = classifyExtractionError('KeyError: something weird');
        expect(c.blameOurs).toBe(true);
        expect(c.headline).not.toMatch(/[a-z]/i);
    });
});
