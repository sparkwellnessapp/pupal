/**
 * PR-5 Sprint 1 — pure helpers for the session spine (arrival card, wait screen,
 * completion, failure copy). All pure and unit-tested; no React, no I/O.
 */

import type { Annotation } from '@/lib/api';
import type { SelectionGroup } from '@/lib/api';
import type { RubricQuestion, RubricSubQuestion, RubricCriterion } from '@/types/rubric';
import { dedupeOpenFindings } from './finding-severity';

// ---------------------------------------------------------------------------
// Findings count (flaw-1 ruling): a finding is a DISTINCT NODE. An extraction
// rubric_mismatch and a live sum-invariant on the same target_id are ONE event.
// Count distinct target_ids among error+warning annotations. At arrival (pre-edit)
// the two sources can only overlap as the same event, so this is exact.
//
// The severity predicate + node/global dedup live in finding-severity.ts — the
// ONE shared module this and findingSectionsByQuestion (E-2's rail dots) consume.
//
// NOTE for Sprint 3: this is the COUNT helper only. Do not read "one node ⇒ one
// finding forever" into the card model — post-edit a node can host two genuinely
// distinct events; the S3 card model counts by card, not by node.
// ---------------------------------------------------------------------------

export function countFindings(annotations: Annotation[]): number {
    const { nodeTargets, globalCount } = dedupeOpenFindings(annotations);
    return nodeTargets.size + globalCount;
}

// ---------------------------------------------------------------------------
// findingSectionsByQuestion (PR-5 S2, E-2 rail dots) — which TOP-LEVEL questions
// hold an open finding, so the outline rail can dot exactly those sections.
//
// A scalar countFindings cannot attribute a finding to a section, and `target_id`
// arrives in THREE shapes (census-verified) — this is their one tested home:
//   1. bare question id          "q1"            → that question
//   2. full dotted path          "q1.א.2"        → first segment is the question id
//   3. bare descendant id        "c_ab12" / "א"  → tree-walk to the owning question
// Generated ids (q_/sq_/c_…) have no positional meaning, so shape (3) can never be
// parsed from the string — it MUST be resolved against the tree. Rubric-scope
// (null-target) findings are intentionally excluded: they belong to the header,
// not a section dot.
// ---------------------------------------------------------------------------

/** Index every node id (question / sub-question / criterion / sub-criterion, at
 *  any depth) to its owning TOP-LEVEL question id. */
function buildNodeToQuestionIndex(questions: RubricQuestion[]): Map<string, string> {
    const index = new Map<string, string>();
    const indexCriterion = (c: RubricCriterion, qid: string) => {
        index.set(c.criterion_id, qid);
        for (const sc of c.sub_criteria ?? []) index.set(sc.sub_criterion_id, qid);
    };
    const indexSub = (sq: RubricSubQuestion, qid: string) => {
        index.set(sq.sub_question_id, qid);
        for (const c of sq.criteria) indexCriterion(c, qid);
        for (const child of sq.sub_questions ?? []) indexSub(child, qid);
    };
    for (const q of questions) {
        index.set(q.question_id, q.question_id);
        for (const c of q.criteria) indexCriterion(c, q.question_id);
        for (const sq of q.sub_questions) indexSub(sq, q.question_id);
    }
    return index;
}

function resolveQuestionId(target: string, index: Map<string, string>): string | null {
    // Shapes (1) and (3): the whole target is a known node id.
    const direct = index.get(target);
    if (direct !== undefined) return direct;
    // Shape (2): a dotted path — the first segment is the question id.
    if (target.includes('.')) {
        const head = index.get(target.slice(0, target.indexOf('.')));
        if (head !== undefined) return head;
    }
    return null;
}

export function findingSectionsByQuestion(
    annotations: Annotation[],
    questions: RubricQuestion[],
): Set<string> {
    const { nodeTargets } = dedupeOpenFindings(annotations);
    if (nodeTargets.size === 0) return new Set();
    const index = buildNodeToQuestionIndex(questions);
    const sections = new Set<string>();
    // .forEach (not for-of) — the project tsc target disallows Set iteration syntax.
    nodeTargets.forEach((target) => {
        const qid = resolveQuestionId(target, index);
        if (qid) sections.add(qid);
    });
    return sections;
}

// ---------------------------------------------------------------------------
// Recursive criteria count — census shows existing counts are depth-1; the
// arrival card must count leaf criteria at ANY depth (matches the backend).
// ---------------------------------------------------------------------------

export function countCriteria(questions: RubricQuestion[]): number {
    const walk = (subs: RubricSubQuestion[] | undefined): number =>
        (subs ?? []).reduce((n, sq) => n + sq.criteria.length + walk(sq.sub_questions), 0);
    return questions.reduce((n, q) => n + q.criteria.length + walk(q.sub_questions), 0);
}

// ---------------------------------------------------------------------------
// Name precedence at save (S1-2.4): captured (state) > inferred (result.rubric_name)
// > filename-derived. Never empty.
// ---------------------------------------------------------------------------

export function resolveRubricName(
    captured: string | null | undefined,
    inferred: string | null | undefined,
    filename: string | null | undefined,
): string {
    const c = captured?.trim();
    if (c) return c;
    const i = inferred?.trim();
    if (i) return i;
    const f = filename?.replace(/\.docx$/i, '').trim();
    return f || 'מחוון';
}

// ---------------------------------------------------------------------------
// Selection structure, first-class (Dream doc §3 arrival): "מבחן בחירה: מענה על
// 4 מתוך 6 שאלות". Returns null when it isn't a selection exam.
// ---------------------------------------------------------------------------

export function selectionSummaryLine(
    groups: SelectionGroup[] | null | undefined,
    totalQuestions: number,
): string | null {
    if (!groups || groups.length === 0) return null;
    // MVP rubrics carry a single choose-k group; sum k across groups if more exist.
    const chooseK = groups.reduce((sum, g) => sum + (g.choose_k ?? 0), 0);
    if (chooseK <= 0) return null;
    return `מבחן בחירה: מענה על ${chooseK} מתוך ${totalQuestions} שאלות`;
}

// ---------------------------------------------------------------------------
// Hebrew pluralization (voice law: שגיאה אחת / 2 שגיאות · ממצא אחד / N ממצאים).
// `one` is the FULL singular phrase; `many` is the plural noun.
// ---------------------------------------------------------------------------

export function pluralHe(n: number, one: string, many: string): string {
    return n === 1 ? one : `${n} ${many}`;
}

/** Arrival card: "ממצא אחד מחכה לאישורך" / "N ממצאים מחכים לאישורך" / (0) none. */
export function findingsWaitingLabel(count: number): string {
    if (count <= 0) return 'לא נמצאו ממצאים — המחוון נראה תקין';
    return count === 1
        ? 'ממצא אחד מחכה לאישורך'
        : `${count} ממצאים מחכים לאישורך`;
}

/** The RubricEditor per-question error badge: "שגיאה אחת" / "N שגיאות". */
export function errorsBadgeLabel(count: number): string {
    return pluralHe(count, 'שגיאה אחת', 'שגיאות');
}

// ---------------------------------------------------------------------------
// Failure copy (S1-4): map a raw backend error_message to blame-correct teacher
// language. Raw English NEVER becomes the headline (it may live in collapsed
// technical details). Blame lands on us unless the file is genuinely the cause.
// ---------------------------------------------------------------------------

export interface ExtractionFailureCopy {
    headline: string;
    body: string;
    /** True when the fault is ours (transient/quota/unknown), false when the file may be. */
    blameOurs: boolean;
}

export function classifyExtractionError(raw: string | null | undefined): ExtractionFailureCopy {
    const s = (raw || '').toLowerCase();

    // Transport / timeout / budget (PR-2 classes) — ours, transient.
    if (/timeout|timed out|deadline|budget|transient|connection|network|502|503|504|unavailable|econn|read timed/.test(s)) {
        return {
            headline: 'תקלה זמנית אצלנו',
            body: 'תקלה זמנית אצלנו — לא בקובץ שלך. הקובץ שמור, אין צורך להעלות שוב.',
            blameOurs: true,
        };
    }
    // Quota / rate — ours, load-related.
    if (/quota|insufficient_quota|rate.?limit|too many requests|429/.test(s)) {
        return {
            headline: 'המערכת עמוסה כרגע',
            body: 'עומס זמני אצלנו — לא בקובץ שלך. נסי שוב בעוד רגע; הקובץ שמור, אין צורך להעלות שוב.',
            blameOurs: true,
        };
    }
    // Parse / document — the file may genuinely be the cause; stay gentle, still actionable.
    if (/failed to parse|parse docx|empty file|corrupt|not a docx|unable to get page count/.test(s)) {
        return {
            headline: 'לא הצלחנו לקרוא את הקובץ',
            body: 'ייתכן שהקובץ אינו DOCX תקין או שהוא פגום. אפשר לנסות שוב, או להעלות קובץ אחר.',
            blameOurs: false,
        };
    }
    // Unknown — honest-generic, ours-leaning (never blame her by default).
    return {
        headline: 'משהו השתבש',
        body: 'משהו השתבש בעיבוד המחוון — לא בקובץ שלך ככל הידוע לנו. הקובץ שמור, אפשר לנסות שוב.',
        blameOurs: true,
    };
}
