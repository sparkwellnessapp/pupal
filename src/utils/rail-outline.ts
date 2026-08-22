import type { RubricQuestion, RubricSubQuestion } from '@/types/rubric';
import { questionLabel, subQuestionLabel } from './scope-label';

/**
 * The outline rail's model — the document's scope tree, flattened to what a map
 * needs: an anchor, a name, a number, and children.
 *
 * PURE and separate from the component on purpose. The rail is a NAVIGATION
 * surface, so the one thing it must never get wrong is the anchor: `id` is the
 * full dotted scope path (`q1`, `q1.א`, `q1.א.2`) and is exactly the value the
 * document renders as `data-scope-id`, which is what `scrollToScope` queries.
 * Building it here means that correspondence is unit-testable without a DOM.
 *
 * Labels come from the SAME resolvers the document headings use (`questionLabel` /
 * `subQuestionLabel`, with a teacher `title` winning), so the rail and the page
 * speak one naming system — the map says "סעיף א" because the heading does.
 */
export interface RailNode {
    /** Full dotted scope path — matches `data-scope-id` in the document. */
    id: string;
    label: string;
    points: number;
    /** 0 = question, 1 = sub-question, 2+ = nested. Drives indentation. */
    depth: number;
    children: RailNode[];
}

function subNode(sq: RubricSubQuestion, index: number, depth: number, parentId: string): RailNode {
    const id = `${parentId}.${sq.sub_question_id}`;
    return {
        id,
        label: sq.title?.trim() || subQuestionLabel(sq, index, depth),
        points: sq.points,
        depth,
        children: (sq.sub_questions ?? []).map((child, i) => subNode(child, i, depth + 1, id)),
    };
}

/** Build the rail tree for a rubric. Recurses to ANY depth (the ontology does). */
export function buildRailOutline(questions: RubricQuestion[]): RailNode[] {
    return questions.map((q, i) => ({
        id: q.question_id,
        label: questionLabel(q, i),
        points: q.total_points,
        depth: 0,
        children: (q.sub_questions ?? []).map((sq, si) => subNode(sq, si, 1, q.question_id)),
    }));
}
