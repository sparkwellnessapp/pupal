/**
 * Rubric Validation Utilities
 *
 * Live validation for rubric invariants INV-R1, INV-R1b, INV-R2, INV-R3.
 * Used by RubricEditor (via page.tsx's combinedAnnotations) for inline
 * feedback and save-blocking.
 *
 * Invariant taxonomy (matches CLAUDE.md §the 7 invariants):
 *
 *   INV-R1   — Question.total_points equals its children's sum.
 *              Shape-dependent (StructureExclusivity):
 *                - direct-criteria question: Σ q.criteria.points  == q.total_points
 *                - sub-question question:    Σ sq.points          == q.total_points
 *              The two shapes need different messages because they describe
 *              different mismatches; surfacing the criteria-sum diagnosis on
 *              a sub-question-bearing question is the wrong diagnosis.
 *
 *   INV-R1b  — Σ sq.criteria.points == sq.points, per sub-question.
 *              Independent of INV-R1. A teacher can break either, both, or
 *              neither; the validator surfaces each independently so the
 *              teacher can resolve them in any order.
 *
 *   INV-R2   — Σ sub_criterion.points == criterion.points, per criterion
 *              that has sub_criteria. Vacuously satisfied when none.
 *
 *   INV-R3   — ACHIEVABLE-aware (PR-4): computeAchievablePoints(questions,
 *              selection_groups) == rubric.total_points (the document-declared
 *              achievable total anchored at extraction time). Rubric-scope. This
 *              is the client analog of the backend INV-4; with no selection
 *              groups it reduces EXACTLY to the legacy Σ q.total_points check.
 *              (Was, pre-PR-4: the offered-sum check, ABSTAINED-on-selection.)
 *
 *   INV-R-XOR — StructureExclusivity: a node (question or sub-question) has
 *              EITHER direct criteria OR sub_questions, never both. The client
 *              analog of the backend Pydantic StructureExclusivity validator;
 *              the TS types stay permissive, the validator enforces.
 *
 * B-11: INV-R1b and INV-R2 RECURSE over nested sub-questions, mirroring the
 * backend compiler's `_walk_sub_question` (contract_compiler.py) exactly —
 * parent node: Σ children.points == node.points; leaf: Σ criteria.points ==
 * node.points; target_id is the full dotted path (e.g. "q1.א.2"). The depth-1
 * version was blind to a parent sub-question and to every nested leaf — it could
 * not see the exact node the backend rejects.
 *
 * @see CLAUDE.md §the 7 invariants
 * @see contract_compiler.py::_walk_sub_question — the recursion this mirrors
 * @see rubric-display.ts — getDisplayLabel for human-facing label rendering
 */

import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';
import type { SelectionGroup } from '@/lib/api';
import { getDisplayLabel, formatPoints } from './rubric-display';
import { computeAchievablePoints } from './rubric-achievable';

// =============================================================================
// Types
// =============================================================================

export type ValidationSeverity = 'error' | 'warning' | 'info';

export interface ValidationIssue {
    /** Unique key for React rendering */
    key: string;
    /** Which invariant is violated */
    invariant: 'INV-R1' | 'INV-R1b' | 'INV-R2' | 'INV-R3' | 'INV-R-XOR';
    /** Severity determines save-blocking behavior */
    severity: ValidationSeverity;
    /** Hebrew message for display */
    message: string;
    /**
     * ID of the affected entity (question_id, sub_question_id, criterion_id,
     * or 'rubric' for rubric-scope). Raw IDs throughout — RubricEditor's
     * scope filters accept these directly. See RubricEditor.tsx for the
     * matching filter clauses.
     */
    target_id: string;
}

// Tolerance for floating-point comparisons (matches backend NumericPolicy.sum_tolerance)
const SUM_TOLERANCE = 0.01;

// =============================================================================
// Helpers
// =============================================================================

/** Safe floating-point comparison within tolerance. */
function isClose(a: number, b: number, tolerance: number = SUM_TOLERANCE): boolean {
    return Math.abs(a - b) <= tolerance;
}

/**
 * Σ q.criteria.points — only meaningful for direct-criteria questions.
 * For sub-question-bearing questions, q.criteria is structurally empty
 * (StructureExclusivity), so the sum is 0 and this function is not used.
 */
function sumDirectCriteriaPoints(question: RubricQuestion): number {
    return question.criteria.reduce((sum, c) => sum + c.points, 0);
}

/**
 * Σ sq.points — only meaningful for sub-question-bearing questions.
 * For direct-criteria questions, sub_questions is structurally empty
 * (StructureExclusivity), so the sum is 0 and this function is not used.
 */
function sumSubQuestionPoints(question: RubricQuestion): number {
    return (question.sub_questions || []).reduce((sum, sq) => sum + sq.points, 0);
}

/** Σ sub_criterion.points for one criterion. */
function sumSubCriteriaPoints(criterion: RubricCriterion): number {
    return (criterion.sub_criteria || []).reduce((sum, sc) => sum + sc.points, 0);
}

// =============================================================================
// Per-question validation
// =============================================================================

/**
 * Validate one question against INV-R1, INV-R1b, and INV-R2 (the latter
 * cascading into each criterion under the question and its sub-questions).
 *
 * INV-R1 splits by question shape (StructureExclusivity):
 *   - sub-question-bearing question: Σ sq.points vs q.total_points
 *   - direct-criteria question:      Σ q.criteria.points vs q.total_points
 *
 * The two shapes produce different Hebrew messages because they describe
 * different mismatches. A sub-question-bearing question whose Σ sq.points
 * diverges from q.total_points should NOT be diagnosed as a criteria sum
 * problem — that diagnosis is wrong and misleads the teacher about which
 * fields to edit.
 *
 * @param qIndex     position of `question` in `questions` (0-based)
 * @param questions  full array — needed by getDisplayLabel for sub-question
 *                   title resolution
 */
export function validateQuestion(
    question: RubricQuestion,
    qIndex: number,
    questions: RubricQuestion[]
): ValidationIssue[] {
    const issues: ValidationIssue[] = [];

    // ── INV-R-XOR: a question has direct criteria XOR sub-questions ──────────
    pushXorIssue(
        issues,
        question.criteria,
        question.sub_questions,
        getDisplayLabel({ kind: 'question', qIndex }, questions),
        question.question_id,
    );

    const hasSubQuestions = !!(question.sub_questions && question.sub_questions.length > 0);

    if (hasSubQuestions) {
        // ── INV-R1 (sub-question shape): Σ sq.points (declared) vs q.total_points ─
        // Matches backend INV-1: sums the DECLARED child points, one level down.
        const sqSum = sumSubQuestionPoints(question);
        if (!isClose(sqSum, question.total_points)) {
            const qLabel = getDisplayLabel({ kind: 'question', qIndex }, questions);
            const total = formatPoints(question.total_points);
            const actual = formatPoints(sqSum);
            issues.push({
                key: `inv-r1-${question.question_id}`,
                invariant: 'INV-R1',
                severity: 'error',
                message:
                    `סכום הנקודות של ${qLabel} (${total} נקודות) ` +
                    `שונה מסכום הנקודות של תתי-השאלות שלה (${actual} נקודות). ` +
                    `מומלץ לתקן את סכום הנקודות של תתי-השאלות כך שיהיו שווים ל-${total} נקודות.`,
                target_id: question.question_id,
            });
        }

        // ── INV-R1b + INV-R2, RECURSIVELY, mirroring _walk_sub_question ──────
        question.sub_questions!.forEach((sq, sqIndex) => {
            walkSubQuestion(
                sq,
                [sqIndex],
                `${question.question_id}.${sq.sub_question_id}`,
                qIndex,
                questions,
                issues,
            );
        });
    } else {
        // ── INV-R1 (direct-criteria shape): Σ q.criteria.points vs q.total_points ─
        const criteriaSum = sumDirectCriteriaPoints(question);
        if (!isClose(criteriaSum, question.total_points)) {
            const qLabel = getDisplayLabel({ kind: 'question', qIndex }, questions);
            const total = formatPoints(question.total_points);
            const actual = formatPoints(criteriaSum);
            issues.push({
                key: `inv-r1-${question.question_id}`,
                invariant: 'INV-R1',
                severity: 'error',
                message:
                    `סכום הנקודות של ${qLabel} (${total} נקודות) ` +
                    `שונה מסכום הנקודות של הקריטריונים שלה (${actual} נקודות). ` +
                    `מומלץ לתקן את סכום הנקודות של הקריטריונים כך שיהיו שווים ל-${total} נקודות.`,
                target_id: question.question_id,
            });
        }

        // ── INV-R2 (per criterion): direct criteria ─────────────────────────
        question.criteria.forEach((criterion, cIndex) => {
            issues.push(
                ...validateCriterion(criterion, qIndex, undefined, cIndex, questions)
            );
        });
    }

    return issues;
}

/**
 * Recurse one sub-question, mirroring `contract_compiler.py::_walk_sub_question`:
 *   - parent (has sub_questions): Σ children.points == sq.points, then recurse;
 *   - leaf (has criteria): Σ criteria.points == sq.points, then INV-R2 per criterion.
 * `path` is the full dotted id-path (e.g. "q1.א.2") used as `target_id` so the
 * editor anchors the error to the exact node — the same anchor the backend uses.
 * `sqPath` is the positional path used only for the human label.
 *
 * Unlike the depth-1 predecessor, a parent is NOT treated as a vacuously-satisfied
 * empty-criteria leaf — that blindness is precisely what hid the bagrut error at
 * q1.א.2. A leaf whose criteria sum ≠ its points fires even when criteria is empty,
 * matching the backend (a leaf with points but no criteria is malformed).
 */
function walkSubQuestion(
    sq: RubricSubQuestion,
    sqPath: number[],
    path: string,
    qIndex: number,
    questions: RubricQuestion[],
    issues: ValidationIssue[],
): void {
    const sqLabel = getDisplayLabel({ kind: 'sub_question', qIndex, sqPath }, questions);

    // ── INV-R-XOR at this sub-question ──────────────────────────────────────
    pushXorIssue(issues, sq.criteria, sq.sub_questions, sqLabel, path);

    const hasChildren = !!(sq.sub_questions && sq.sub_questions.length > 0);

    if (hasChildren) {
        // Parent: Σ children.points == sq.points.
        const childSum = sq.sub_questions!.reduce((sum, c) => sum + c.points, 0);
        if (!isClose(childSum, sq.points)) {
            const declared = formatPoints(sq.points);
            const actual = formatPoints(childSum);
            issues.push({
                key: `inv-r1b-${path}`,
                invariant: 'INV-R1b',
                severity: 'error',
                message:
                    `סכום הנקודות של ${sqLabel} (${declared} נקודות) ` +
                    `שונה מסכום הנקודות של תתי-הסעיפים שלו (${actual} נקודות). ` +
                    `מומלץ לתקן את סכום הנקודות של תתי-הסעיפים כך שיהיו שווים ל-${declared} נקודות.`,
                target_id: path,
            });
        }
        sq.sub_questions!.forEach((child, i) => {
            walkSubQuestion(
                child,
                [...sqPath, i],
                `${path}.${child.sub_question_id}`,
                qIndex,
                questions,
                issues,
            );
        });
    } else {
        // Leaf: Σ criteria.points == sq.points.
        const critSum = sq.criteria.reduce((sum, c) => sum + c.points, 0);
        if (!isClose(critSum, sq.points)) {
            const declared = formatPoints(sq.points);
            const actual = formatPoints(critSum);
            issues.push({
                key: `inv-r1b-${path}`,
                invariant: 'INV-R1b',
                severity: 'error',
                message:
                    `סכום הנקודות של ${sqLabel} (${declared} נקודות) ` +
                    `שונה מסכום הנקודות של הקריטריונים שלו (${actual} נקודות). ` +
                    `מומלץ לתקן את סכום הנקודות של הקריטריונים כך שיהיו שווים ל-${declared} נקודות.`,
                target_id: path,
            });
        }
        sq.criteria.forEach((criterion, cIndex) => {
            issues.push(...validateCriterion(criterion, qIndex, sqPath, cIndex, questions));
        });
    }
}

/**
 * INV-R-XOR: push an error if a node has BOTH direct criteria and sub-questions.
 * Mirrors backend StructureExclusivity (enforced by validator; the type stays
 * permissive). `targetId` is the node's anchor (question_id or full path).
 */
function pushXorIssue(
    issues: ValidationIssue[],
    criteria: RubricCriterion[] | undefined,
    subQuestions: RubricSubQuestion[] | undefined,
    label: string,
    targetId: string,
): void {
    if ((criteria?.length ?? 0) > 0 && (subQuestions?.length ?? 0) > 0) {
        issues.push({
            key: `inv-r-xor-${targetId}`,
            invariant: 'INV-R-XOR',
            severity: 'error',
            message:
                `ל-${label} יש גם קריטריונים ישירים וגם תתי-סעיפים. ` +
                `כל רכיב חייב להיות מחולק לתתי-סעיפים או לקריטריונים — לא לשניהם.`,
            target_id: targetId,
        });
    }
}

/**
 * Validate INV-R2 for a single criterion: Σ sub_criterion.points == criterion.points.
 * Vacuously satisfied when criterion has no sub_criteria. `sqPath` (positional) is
 * used only for the human label; the anchor is the criterion_id.
 */
export function validateCriterion(
    criterion: RubricCriterion,
    qIndex: number,
    sqPath: number[] | undefined,
    cIndex: number,
    questions: RubricQuestion[]
): ValidationIssue[] {
    if (!criterion.sub_criteria || criterion.sub_criteria.length === 0) {
        return [];
    }

    const subSum = sumSubCriteriaPoints(criterion);
    if (isClose(subSum, criterion.points)) return [];

    const cLabel = getDisplayLabel(
        { kind: 'criterion', qIndex, sqPath, cIndex },
        questions
    );
    const declared = formatPoints(criterion.points);
    const actual = formatPoints(subSum);

    return [
        {
            key: `inv-r2-${criterion.criterion_id}`,
            invariant: 'INV-R2',
            severity: 'error',
            message:
                `סכום הנקודות של ${cLabel} (${declared} נקודות) ` +
                `שונה מסכום הנקודות של תתי-הקריטריונים שלו (${actual} נקודות). ` +
                `מומלץ לתקן את סכום הנקודות של תתי-הקריטריונים כך שיהיו שווים ל-${declared} נקודות.`,
            target_id: criterion.criterion_id,
        },
    ];
}

// =============================================================================
// Aggregate validation
// =============================================================================

/**
 * Validate all questions, returning issues grouped by question_id.
 * Threads positional index into each call so messages can render "שאלה N".
 */
export function validateAllQuestions(
    questions: RubricQuestion[]
): Map<string, ValidationIssue[]> {
    const issuesByQuestion = new Map<string, ValidationIssue[]>();
    questions.forEach((question, qIndex) => {
        const issues = validateQuestion(question, qIndex, questions);
        if (issues.length > 0) {
            issuesByQuestion.set(question.question_id, issues);
        }
    });
    return issuesByQuestion;
}

/** Are there any error-severity issues anywhere in the rubric? */
export function hasErrors(questions: RubricQuestion[]): boolean {
    for (let qIndex = 0; qIndex < questions.length; qIndex++) {
        const issues = validateQuestion(questions[qIndex], qIndex, questions);
        if (issues.some((issue) => issue.severity === 'error')) {
            return true;
        }
    }
    return false;
}

/** Total error count across all questions (excluding INV-R3 — rubric-scope). */
export function countErrors(questions: RubricQuestion[]): number {
    let count = 0;
    questions.forEach((question, qIndex) => {
        const issues = validateQuestion(question, qIndex, questions);
        count += issues.filter((issue) => issue.severity === 'error').length;
    });
    return count;
}

/**
 * Error count for one question (used in the question header badge).
 * Caller must pass the question's positional index and the full questions
 * array so messages render correctly even if this is the only validator
 * call for that question.
 */
export function getQuestionErrorCount(
    question: RubricQuestion,
    qIndex: number,
    questions: RubricQuestion[]
): number {
    const issues = validateQuestion(question, qIndex, questions);
    return issues.filter((issue) => issue.severity === 'error').length;
}

// =============================================================================
// Rubric-scope validation
// =============================================================================

/**
 * Validate INV-R3 (achievable-aware — the client analog of backend INV-4, PR-4):
 * computeAchievablePoints(questions, selectionGroups) == rubric.total_points.
 *
 * Was, pre-PR-4: `Σ q.total_points == declared`, and page.tsx ABSTAINED from
 * running it on selection exams (offered Σ ≠ achievable would fire a false
 * error). Now it validates BOTH regimes because the achievable mirror IS the
 * single client-side source — the same discipline B-5 asks for (never show/check
 * an aggregate that can disagree with what save freezes). With no selection
 * groups, computeAchievablePoints reduces exactly to the offered sum, so this is
 * a strict superset of the old check — no behavior change for flat rubrics.
 *
 * `target_id` is the literal string 'rubric' (not null) — RubricEditor's
 * global banner filter accepts both 'rubric' (live INV-R3) and null
 * (legacy backend rubric-scope annotations).
 *
 * Returns the issue or null if the invariant holds.
 *
 * @see rubric-achievable.ts::computeAchievablePoints — the mirror of backend INV-4
 */
export function validateRubricTotalPoints(
    questions: RubricQuestion[],
    rubricTotalPoints: number,
    selectionGroups: SelectionGroup[] = []
): ValidationIssue | null {
    const achievable = computeAchievablePoints(questions, selectionGroups);
    if (isClose(achievable, rubricTotalPoints)) return null;

    const declared = formatPoints(rubricTotalPoints);
    const actual = formatPoints(achievable);

    return {
        key: 'inv-r3-rubric-total',
        invariant: 'INV-R3',
        severity: 'error',
        message:
            `סכום הנקודות של המחוון (${declared} נקודות) ` +
            `שונה מהניקוד הניתן להשגה בשאלות (${actual} נקודות). ` +
            `מומלץ לתקן את הנקודות כך שיהיו שווים ל-${declared} נקודות.`,
        target_id: 'rubric',
    };
}

/**
 * True if there is a rubric-level total mismatch (INV-R3).
 *
 * Convenience wrapper around validateRubricTotalPoints. Currently unused —
 * page.tsx routes INV-R3 through combinedAnnotations and derives the save-
 * blocking signal from `combinedAnnotations.some(a => a.severity === 'error')`.
 * Kept exported in case a non-annotation consumer needs the boolean form;
 * safe to delete in a cleanup pass if no callers materialize.
 */
export function hasRubricTotalError(
    questions: RubricQuestion[],
    rubricTotalPoints: number,
    selectionGroups: SelectionGroup[] = []
): boolean {
    return validateRubricTotalPoints(questions, rubricTotalPoints, selectionGroups) !== null;
}