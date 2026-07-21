/**
 * scopeLabel — turn a technical scope id into the teacher's naming system.
 *
 * The naming law (Dream doc §2): "שאלה 1 · סעיף א · תת-סעיף 2 — Technical ids
 * (q1.א.2) never reach her eyes." This is the single resolver every surface uses
 * so no raw id ever leaks: the summary banner's jump buttons, RubricErrorDisplay's
 * location line, and (Sprints 2–3) the finding cards.
 *
 * It is a POSITIONAL TREE RESOLVER, not token parsing (PR-5 flaw-2 ruling):
 *   - prefer the node's PAPER IDENTITY when the id token is human-meaningful
 *     (`q2` → "שאלה 2", `א` → "סעיף א") — identity survives reordering, position
 *     does not, so a deletion that renumbers positions must not rename a finding;
 *   - fall back to ORDINAL POSITION ("שאלה 3", "סעיף 2") only for GENERATED ids
 *     (`q_*`, `sq_*`, `c_*`, `c<timestamp>`) minted by the editor's add ops —
 *     otherwise a teacher-added node would leak "סעיף sq_mxyz12ab".
 *
 * Accepts every target_id shape that reaches the eyes: null / "rubric" → "המחוון";
 * a question id "q1"; a dotted path "q1.א.2"; or a bare criterion id (searched for
 * in the tree). An unresolvable id degrades to "המחוון" — never to the raw string.
 */

import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';

const RUBRIC_LABEL = 'המחוון';
const SEP = ' · ';

/** An id minted by the editor's add ops — never human-facing. */
export function isGeneratedId(id: string): boolean {
    return /^(q_|sq_|c_)/.test(id) || /^c\d{10,}$/.test(id);
}

/**
 * The LOCAL heading label for a question ("שאלה 2") — identity-preferred, ordinal
 * fallback for generated ids. Exported so the document mirror's SectionHeading
 * speaks the same naming law as the finding jump-labels (one resolver, §0.4).
 */
export function questionLabel(q: RubricQuestion, index: number): string {
    const m = /^q(\d+)$/.exec(q.question_id);
    const paper = m && !isGeneratedId(q.question_id) ? m[1] : String(index + 1);
    return `שאלה ${paper}`;
}

/**
 * The LOCAL heading label for a sub-question ("סעיף א" at depth 1, "תת-סעיף 1"
 * deeper) — identity-preferred, ordinal fallback for generated ids. `depth` is
 * 1 for a question's direct sub-questions and increases with nesting. Exported
 * for the mirror's recursive SectionHeading.
 */
export function subQuestionLabel(sq: RubricSubQuestion, index: number, depth: number): string {
    const kind = depth <= 1 ? 'סעיף' : 'תת-סעיף';
    const paper = isGeneratedId(sq.sub_question_id) ? String(index + 1) : sq.sub_question_id;
    return `${kind} ${paper}`;
}

function criterionSuffix(index: number): string {
    return `קריטריון ${index + 1}`;
}

/** Depth-first search for a criterion id anywhere in the tree; returns its full label path or null. */
function findCriterion(
    criterionId: string,
    subs: RubricSubQuestion[] | undefined,
    prefix: string[],
    depth: number,
): string | null {
    for (let i = 0; i < (subs?.length ?? 0); i++) {
        const sq = subs![i];
        const here = [...prefix, subQuestionLabel(sq, i, depth)];
        const c = sq.criteria.findIndex(cr => cr.criterion_id === criterionId);
        if (c >= 0) return [...here, criterionSuffix(c)].join(SEP);
        const deeper = findCriterion(criterionId, sq.sub_questions, here, depth + 1);
        if (deeper) return deeper;
    }
    return null;
}

export function scopeLabel(
    targetId: string | null | undefined,
    questions: RubricQuestion[],
): string {
    if (!targetId || targetId === 'rubric') return RUBRIC_LABEL;

    const parts = targetId.split('.');
    const qIndex = questions.findIndex(q => q.question_id === parts[0]);

    if (qIndex >= 0) {
        // Dotted path: question . sub_question . sub_question …
        const labels: string[] = [questionLabel(questions[qIndex], qIndex)];
        let level: RubricSubQuestion[] | undefined = questions[qIndex].sub_questions;
        for (let d = 1; d < parts.length; d++) {
            if (!level) break; // resolve as deep as the tree allows; never emit a raw tail
            const idx: number = level.findIndex(sq => sq.sub_question_id === parts[d]);
            if (idx < 0) break;
            const node: RubricSubQuestion = level[idx];
            labels.push(subQuestionLabel(node, idx, d));
            level = node.sub_questions;
        }
        return labels.join(SEP);
    }

    // Not a question path — try a bare criterion id sitting anywhere in the tree.
    for (let qi = 0; qi < questions.length; qi++) {
        const q = questions[qi];
        const ql = questionLabel(q, qi);
        const direct = q.criteria.findIndex(cr => cr.criterion_id === targetId);
        if (direct >= 0) return [ql, criterionSuffix(direct)].join(SEP);
        const nested = findCriterion(targetId, q.sub_questions, [ql], 1);
        if (nested) return nested;
    }

    // Unresolvable — degrade to the rubric scope, NEVER the raw id.
    return RUBRIC_LABEL;
}
