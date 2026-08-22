/**
 * PR-6b — THE EDIT-STEPS INTERPRETER. One applier for the general fix wire.
 *
 * A backend `SuggestedFix` is an ordered list of primitive edit steps
 * (set_points / move_criterion / move_text) over the dotted scope-path
 * vocabulary every surface already speaks. This module is the ONLY place that
 * interprets them. Properties the trust story depends on:
 *
 *   - ATOMIC. The apply IS the dry-run: ops are pure, so a failure at step N
 *     simply discards the partial result and returns null — the tree the page
 *     holds was never touched. `canApplySteps` uses the same code path, which
 *     is how a card knows to withhold a button it cannot honour ("offer
 *     nothing rather than a wrong write" — the resolveScopePath rule).
 *
 *   - OPS IMPORTED, NEVER FORKED. Every mutation routes through the pure
 *     rubric-editor-ops primitives, so the E-1 undo stack's structural-sharing
 *     assumption holds for applied fixes exactly as for hand edits.
 *
 *   - THE CARVE IS MACHINE-PERFORMED. For move_text the model only QUOTES the
 *     text that moves; this applier verifies it is an exact substring and does
 *     the subtraction itself. A quote that does not match verbatim fails the
 *     whole plan — the model structurally cannot rewrite prose it wasn't
 *     moving.
 *
 *   - AUTO-VIVIFY. A move destination naming a sub-question that does not
 *     exist is created (empty, 0 points) under its — existing — parent. This is
 *     how "create the missing סעיף ג" is expressed without a create op.
 *
 * A fix touches EITHER the question tree OR the rubric-level declared total,
 * never both: the declared total lives outside `questions` and is applied by
 * the caller through its own handler, and mixing the two would push two undo
 * snapshots for one click. The applier enforces this (rubric ⇒ single step).
 */

import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';
import {
    changeQuestionPoints, changeSubQuestionPointsAtPath, updateCriterionAtPath,
    mapCriteriaAtPath, updateSubQuestionAtPath, setQuestionText, setSubQuestionTextAtPath,
} from '@/utils/rubric-editor-ops';
import { recalculateParentsFromCriteria, safeParseFloat } from '@/utils/rubric-transform';

// ─────────────────────────────────────────────────────────────────────────────
// Wire shape
// ─────────────────────────────────────────────────────────────────────────────

export const FIX_STEP_OPS = ['set_points', 'move_criterion', 'move_text'] as const;
export type FixStepOp = (typeof FIX_STEP_OPS)[number];

/** One primitive edit, exactly as the backend EditStep serializes. */
export interface FixStep {
    op: FixStepOp;
    scope: string;
    criterion_index?: number | null;
    to_scope?: string | null;
    text?: string | null;
    value?: string | null;
    current_value?: string | null;
}

export interface AppliedSteps {
    questions: RubricQuestion[];
    /** Present iff the (single-step) fix targets the rubric-level declared total. */
    declaredTotal?: number;
}

// ─────────────────────────────────────────────────────────────────────────────
// Scope resolution (moved here from findings-ops so the module graph stays a DAG;
// findings-ops re-exports it unchanged)
// ─────────────────────────────────────────────────────────────────────────────

export interface ScopePath { qIndex: number; sqPath: number[] }

/**
 * Resolve a dotted scope id (`q1`, `q1.א`, `q1.א.2`) to the (qIndex, sqPath) the
 * pure ops address. Returns null when the id names no node in the CURRENT tree —
 * which happens legitimately after a structural edit, and must degrade to "no
 * fix offered" rather than to a wrong write.
 */
export function resolveScopePath(questions: RubricQuestion[], scopeId: string | null): ScopePath | null {
    if (!scopeId) return null;
    const parts = scopeId.split('.');
    const qIndex = questions.findIndex((q) => q.question_id === parts[0]);
    if (qIndex < 0) return null;

    const sqPath: number[] = [];
    let level: RubricSubQuestion[] = questions[qIndex].sub_questions ?? [];
    for (let d = 1; d < parts.length; d++) {
        const idx = level.findIndex((sq) => sq.sub_question_id === parts[d]);
        if (idx < 0) return null;              // the path does not resolve — offer nothing
        sqPath.push(idx);
        level = level[idx].sub_questions ?? [];
    }
    return { qIndex, sqPath };
}

function nodeAt(questions: RubricQuestion[], path: ScopePath): RubricQuestion | RubricSubQuestion {
    let node: RubricQuestion | RubricSubQuestion = questions[path.qIndex];
    for (const i of path.sqPath) node = (node.sub_questions ?? [])[i];
    return node;
}

/**
 * Resolve `scope`, creating the LAST path segment as a fresh empty sub-question
 * when it is missing (its parent must exist — a fix may create one node, not a
 * chain nobody proposed). Returns the (possibly extended) tree + path.
 */
function resolveOrVivify(
    questions: RubricQuestion[], scope: string,
): { questions: RubricQuestion[]; path: ScopePath } | null {
    const found = resolveScopePath(questions, scope);
    if (found) return { questions, path: found };

    const parts = scope.split('.');
    if (parts.length < 2) return null;         // a question is never vivified
    const parentScope = parts.slice(0, -1).join('.');
    const parent = resolveScopePath(questions, parentScope);
    if (!parent) return null;

    const newId = parts[parts.length - 1];
    const make = (index: number): RubricSubQuestion => ({
        // The id IS the label from the fix (`ג`) — that is what makes the created
        // node addressable by the very next step, and by every validator anchor.
        sub_question_id: newId, index, text: '', points: 0, criteria: [],
    });
    const next = parent.sqPath.length === 0
        ? questions.map((q, i) => (i !== parent.qIndex ? q
            : { ...q, sub_questions: [...(q.sub_questions ?? []), make((q.sub_questions ?? []).length)] }))
        : updateSubQuestionAtPath(questions, parent.qIndex, parent.sqPath, (sq) => ({
            ...sq, sub_questions: [...(sq.sub_questions ?? []), make((sq.sub_questions ?? []).length)],
        }));
    const path = resolveScopePath(next, scope);
    return path ? { questions: next, path } : null;
}

// ─────────────────────────────────────────────────────────────────────────────
// The three primitives
// ─────────────────────────────────────────────────────────────────────────────

function num(v: string | null | undefined): number | null {
    if (v === null || v === undefined) return null;
    const n = safeParseFloat(v);
    return Number.isFinite(n) ? n : null;
}

function applySetPoints(questions: RubricQuestion[], step: FixStep): RubricQuestion[] | null {
    const value = num(step.value);
    if (value === null || value < 0) return null;
    const path = resolveScopePath(questions, step.scope);
    if (!path) return null;

    if (step.criterion_index !== null && step.criterion_index !== undefined) {
        const node = nodeAt(questions, path);
        if (!node.criteria || step.criterion_index >= node.criteria.length) return null;
        // A criterion-point edit behaves exactly like her own edit at that row:
        // it cascades through the ONE cascade (living sums, E-3).
        const edited = updateCriterionAtPath(questions, path.qIndex, path.sqPath, step.criterion_index, { points: value });
        return recalculateParentsFromCriteria(edited);
    }
    return path.sqPath.length === 0
        ? changeQuestionPoints(questions, path.qIndex, value)
        : changeSubQuestionPointsAtPath(questions, path.qIndex, path.sqPath, value);
}

function applyMoveCriterion(questions: RubricQuestion[], step: FixStep): RubricQuestion[] | null {
    if (!step.to_scope || step.criterion_index === null || step.criterion_index === undefined) return null;

    // Vivify the destination FIRST: appending a sibling never shifts existing
    // indices, so the source path resolved afterwards stays valid.
    const target = resolveOrVivify(questions, step.to_scope);
    if (!target) return null;
    const source = resolveScopePath(target.questions, step.scope);
    if (!source) return null;

    const srcNode = nodeAt(target.questions, source);
    const moved: RubricCriterion | undefined = srcNode.criteria?.[step.criterion_index];
    if (!moved) return null;

    // Q1-strict: a move is remove+append of the SAME criterion — nothing is
    // redistributed; the validators see the resulting sums.
    const ci = step.criterion_index;
    let next = mapCriteriaAtPath(target.questions, source.qIndex, source.sqPath,
        (cs) => cs.filter((_, i) => i !== ci).map((c, i) => ({ ...c, index: i })));
    const dest = resolveScopePath(next, step.to_scope);
    if (!dest) return null;
    next = mapCriteriaAtPath(next, dest.qIndex, dest.sqPath,
        (cs) => [...cs, { ...moved, index: cs.length }]);
    return next;
}

function applyMoveText(questions: RubricQuestion[], step: FixStep): RubricQuestion[] | null {
    if (!step.to_scope || !step.text) return null;
    const source = resolveScopePath(questions, step.scope);
    if (!source) return null;

    const srcNode = nodeAt(questions, source);
    const srcText = (source.sqPath.length === 0
        ? (srcNode as RubricQuestion).question_text
        : (srcNode as RubricSubQuestion).text) ?? '';
    if (!srcText.includes(step.text)) return null;   // the quote must be verbatim — else the plan is void

    // The machine does the subtraction; the model only quoted what moves.
    const remainder = srcText.replace(step.text, '').replace(/\n{3,}/g, '\n\n').trim();

    const target = resolveOrVivify(questions, step.to_scope);
    if (!target) return null;
    const dest = resolveScopePath(target.questions, step.to_scope);
    if (!dest) return null;

    let next = target.questions;
    next = source.sqPath.length === 0
        ? setQuestionText(next, source.qIndex, remainder)
        : setSubQuestionTextAtPath(next, source.qIndex, source.sqPath, remainder);

    const destNode = nodeAt(next, dest);
    const destText = (dest.sqPath.length === 0
        ? (destNode as RubricQuestion).question_text
        : (destNode as RubricSubQuestion).text) ?? '';
    const joined = destText ? `${destText}\n${step.text}` : step.text;
    return dest.sqPath.length === 0
        ? setQuestionText(next, dest.qIndex, joined)
        : setSubQuestionTextAtPath(next, dest.qIndex, dest.sqPath, joined);
}

// ─────────────────────────────────────────────────────────────────────────────
// The interpreter
// ─────────────────────────────────────────────────────────────────────────────

export function applyEditSteps(questions: RubricQuestion[], steps: FixStep[]): AppliedSteps | null {
    if (!steps.length) return null;
    let qs = questions;
    for (const step of steps) {
        if (step.op === 'set_points' && step.scope === 'rubric') {
            // The declared total lives outside `questions`; a rubric fix is
            // single-step by contract so one click stays one undo snapshot.
            if (steps.length !== 1) return null;
            const v = num(step.value);
            if (v === null || v < 0) return null;
            return { questions: qs, declaredTotal: v };
        }
        const next =
            step.op === 'set_points' ? applySetPoints(qs, step)
                : step.op === 'move_criterion' ? applyMoveCriterion(qs, step)
                    : step.op === 'move_text' ? applyMoveText(qs, step)
                        : null;
        if (!next) return null;
        qs = next;
    }

    // DETERMINISTIC BOOKKEEPING for plan-created nodes: a vivified sub-question
    // the plan gave criteria but no explicit points ends with points = Σ of what
    // arrived — HER numbers travelling with their criteria, not an invention
    // (the E-3 living-sums rule applied at birth). Observed live: the model
    // emits the moves and forgets the set_points; the arithmetic must not
    // depend on the model remembering bookkeeping.
    const explicitlySet = new Set(steps.filter((s) => s.op === 'set_points').map((s) => s.scope));
    const vivified = Array.from(new Set(
        steps.filter((s) => (s.op === 'move_criterion' || s.op === 'move_text') && s.to_scope)
            .map((s) => s.to_scope as string)
            .filter((scope) => !resolveScopePath(questions, scope)),   // absent from the ORIGINAL tree
    ));
    for (const scope of vivified) {
        if (explicitlySet.has(scope)) continue;
        const path = resolveScopePath(qs, scope);
        if (!path || path.sqPath.length === 0) continue;
        const node = nodeAt(qs, path);
        const sum = (node.criteria ?? []).reduce((a, c) => a + c.points, 0);
        if (sum > 0) qs = changeSubQuestionPointsAtPath(qs, path.qIndex, path.sqPath, sum);
    }
    return { questions: qs };
}

/** The preflight a card runs before offering the button. Same code path as apply. */
export function canApplySteps(questions: RubricQuestion[], steps: FixStep[]): boolean {
    return applyEditSteps(questions, steps) !== null;
}
