'use client';

/**
 * The grade-review entry holder — the batch payload, the frozen cursor, and the
 * rubric questions, all fetched ONCE per route entry.
 *
 * Lifetime is the whole point: this lives in the segment LAYOUT, so it survives
 * every prev/next while the page component beneath it remounts. See the layout
 * for the App Router finding that forces it.
 *
 * ── THE REVIEW ROUTE DOES NOT POLL ───────────────────────────────────────
 * The dashboard polls; this route fetches on entry and after an approve, and
 * that is all (inherited from the transcription flow). A poll here would
 * reorder the queue line under her while she reads, and re-render a surface she
 * is typing into, to tell her something she is about to be told anyway by the
 * approve she is working toward.
 *
 * ── WHAT IS FETCHED, AND WHY IT IS THREE CALLS ───────────────────────────
 *   GET /batches/{id}   the graded-test list (cursor) AND the approved answers
 *                       — `transcriptions[].approved_answers`, matched on
 *                       `graded_test_id`
 *   GET /rubrics/{id}   the question text
 * The graded-test GET itself carries neither. Reported as OD-F9: a
 * `?include=answers,questions` would collapse this to one round trip, and the
 * join is isolated here so that change stays a one-line swap.
 */

import {
    createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
    type ReactNode,
} from 'react';

import { getBatch, getRubric } from '@/lib/api';
import type { BatchDetailResponse } from '@/types/batch';
import {
    initialCursor, mergeCursor, type CursorItem, type GradeCursor,
} from '@/utils/grade-review-cursor';
import type { AnswerItem, QuestionText } from '@/utils/grade-review-model';
import { RV_LOAD_ERROR } from '@/copy/grade-review';

/**
 * Where a test's SCAN is, for «הצגת הסריקה» (R4): the transcription that
 * produced it and, per answer, the pages the transcription attributed it to.
 * The approved answers (`GradeAnswerInputItem`) carry no page numbers; the
 * transcription DRAFT's answers do, and both ride the same batch payload.
 */
export interface ScanSource {
    transcriptionId: string;
    pageCount: number;
    answers: { question_number: number; sub_question_id: string | null; page_numbers: number[] }[];
}

interface GradeReviewState {
    batch: BatchDetailResponse | null;
    cursor: GradeCursor | null;
    /** graded_test_id → the student's approved answers. */
    answersByTest: Record<string, AnswerItem[]>;
    /** graded_test_id → its scan's whereabouts (R4). */
    scanByTest: Record<string, ScanSource>;
    /**
     * The same two joins keyed by TRANSCRIPTION id. A revision successor
     * (manual_edit / regrade / retry) has its own graded_test_id, which the feed
     * does not carry (`extend_chain` does not copy `batch_id` — reported), so
     * the graded-test key finds nothing and every scope would read «אין תשובה
     * בתמלול המאושר». The successor shares its predecessor's transcription, and
     * the graded-test payload names it — that join survives the chain.
     */
    answersByTranscription: Record<string, AnswerItem[]>;
    scanByTranscription: Record<string, ScanSource>;
    questions: QuestionText[];
    /** The rubric's subject key (migration 027) — null until the rubric loads or for a pre-seam row. */
    rubricSubject: string | null;
    error: string | null;
    loading: boolean;
    refetch: () => Promise<void>;
    getCursor: () => GradeCursor | null;
    /**
     * Record locally that a test is now approved.
     *
     * Cheaper and more truthful than a refetch: the cursor is append-only and
     * prefix-stable, so a STATUS update in place is exactly what `mergeCursor`
     * already does. Without it the just-signed test still reads `draft`, so
     * `next` can hand her back a test she has already signed and the WaitCard's
     * "nothing landed left" can never become true.
     */
    markApproved: (gradedTestId: string) => void;
}

const Ctx = createContext<GradeReviewState | null>(null);

export function useGradeReview(): GradeReviewState {
    const ctx = useContext(Ctx);
    if (!ctx) throw new Error('useGradeReview must be used inside GradeReviewProvider');
    return ctx;
}

/** The batch feed's graded-test rows, as cursor items. */
function toCursorItems(batch: BatchDetailResponse): CursorItem[] {
    const rows = (batch as unknown as {
        graded_tests?: {
            graded_test_id: string; status: string;
            student_name?: string | null; landed_at?: string | null;
        }[];
    }).graded_tests ?? [];
    return rows.map((r) => ({
        graded_test_id: r.graded_test_id,
        status: r.status as CursorItem['status'],
        student_name: r.student_name ?? null,
        landed_at: r.landed_at ?? null,
    }));
}

/** `transcriptions[]` → answers, keyed by TRANSCRIPTION id. */
function toAnswersByTranscription(batch: BatchDetailResponse): Record<string, AnswerItem[]> {
    const out: Record<string, AnswerItem[]> = {};
    for (const item of batch.transcriptions ?? []) {
        if (item.approved_answers) out[item.transcription_id] = item.approved_answers;
    }
    return out;
}

/** `transcriptions[]` → answers, keyed by the graded test they produced. */
function toAnswers(batch: BatchDetailResponse): Record<string, AnswerItem[]> {
    const items = (batch as unknown as {
        transcriptions?: {
            graded_test_id?: string | null;
            approved_answers?: AnswerItem[] | null;
        }[];
    }).transcriptions ?? [];
    const out: Record<string, AnswerItem[]> = {};
    for (const item of items) {
        if (item.graded_test_id && item.approved_answers) {
            out[item.graded_test_id] = item.approved_answers;
        }
    }
    return out;
}

function scanOf(item: BatchDetailResponse['transcriptions'][number]): ScanSource {
    return {
        transcriptionId: item.transcription_id,
        pageCount: item.draft?.page_count ?? 0,
        answers: (item.draft?.answers ?? []).map((a) => ({
            question_number: a.question_number,
            sub_question_id: a.sub_question_id ?? null,
            page_numbers: a.page_numbers ?? [],
        })),
    };
}

function toScansByTranscription(batch: BatchDetailResponse): Record<string, ScanSource> {
    const out: Record<string, ScanSource> = {};
    for (const item of batch.transcriptions ?? []) out[item.transcription_id] = scanOf(item);
    return out;
}

/** `transcriptions[]` → scan sources, keyed by the graded test they produced. */
function toScans(batch: BatchDetailResponse): Record<string, ScanSource> {
    const out: Record<string, ScanSource> = {};
    for (const item of batch.transcriptions ?? []) {
        if (!item.graded_test_id) continue;
        out[item.graded_test_id] = {
            transcriptionId: item.transcription_id,
            pageCount: item.draft?.page_count ?? 0,
            answers: (item.draft?.answers ?? []).map((a) => ({
                question_number: a.question_number,
                sub_question_id: a.sub_question_id ?? null,
                page_numbers: a.page_numbers ?? [],
            })),
        };
    }
    return out;
}

export function GradeReviewProvider({ batchId, children }: {
    batchId: string;
    children: ReactNode;
}) {
    const [batch, setBatch] = useState<BatchDetailResponse | null>(null);
    const [questions, setQuestions] = useState<QuestionText[]>([]);
    const [rubricSubject, setRubricSubject] = useState<string | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    const cursorRef = useRef<GradeCursor | null>(null);
    const [, forceRender] = useState(0);
    const aliveRef = useRef(true);

    useEffect(() => {
        aliveRef.current = true;
        return () => { aliveRef.current = false; };
    }, []);

    const load = useCallback(async () => {
        try {
            const payload = await getBatch(batchId);
            if (!aliveRef.current) return;
            setBatch(payload);
            // Append-only: an existing id NEVER moves, whatever its status now
            // says (OD2). Only a fresh entry re-freezes the order.
            const items = toCursorItems(payload);
            cursorRef.current = cursorRef.current
                ? mergeCursor(cursorRef.current, items)
                : initialCursor(items);
            forceRender((n) => n + 1);
            setError(null);

            if (payload.rubric_id) {
                try {
                    const rubric = await getRubric(payload.rubric_id);
                    if (!aliveRef.current) return;
                    setQuestions(extractQuestions(rubric));
                    setRubricSubject((rubric as { subject?: string | null }).subject ?? null);
                } catch {
                    // The questions are CONTEXT, not the grade. Losing them
                    // must not take down a surface she can still review from —
                    // the collapsed question text simply does not appear.
                    setQuestions([]);
                }
            }
        } catch {
            if (aliveRef.current) setError(RV_LOAD_ERROR);
        } finally {
            if (aliveRef.current) setLoading(false);
        }
    }, [batchId]);

    useEffect(() => { void load(); }, [load]);

    const markApproved = useCallback((gradedTestId: string) => {
        const current = cursorRef.current;
        const item = current?.byId[gradedTestId];
        if (!current || !item || item.status === 'approved') return;
        cursorRef.current = mergeCursor(current, [{ ...item, status: 'approved' }]);
        forceRender((n) => n + 1);
    }, []);

    const value = useMemo<GradeReviewState>(() => ({
        batch,
        cursor: cursorRef.current,
        answersByTest: batch ? toAnswers(batch) : {},
        scanByTest: batch ? toScans(batch) : {},
        answersByTranscription: batch ? toAnswersByTranscription(batch) : {},
        scanByTranscription: batch ? toScansByTranscription(batch) : {},
        questions,
        rubricSubject,
        error,
        loading,
        refetch: load,
        getCursor: () => cursorRef.current,
        markApproved,
    }), [batch, questions, rubricSubject, error, loading, load, markApproved]);

    return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

/** Flatten a rubric contract's questions to (id, sub_id, text). */
export function extractQuestions(rubric: unknown): QuestionText[] {
    const source = rubric as {
        contract_json?: { questions?: unknown[] };
        questions?: unknown[];
    };
    const questions = (source?.contract_json?.questions ?? source?.questions ?? []) as {
        question_id?: string;
        question_text?: string;
        // `SubQuestion` names the field `text` (ontology_types.py) while the
        // parent uses `question_text`. Reading `question_text` here made every
        // sub-question fall back to its PARENT's prose — the grade rendered
        // beside the wrong question. `question_text` stays as a tolerated
        // alias in case a future shape unifies them.
        sub_questions?: {
            sub_question_id?: string; text?: string; question_text?: string;
        }[] | null;
    }[];
    const out: QuestionText[] = [];
    for (const question of questions) {
        if (!question?.question_id) continue;
        if (question.question_text) {
            out.push({
                question_id: question.question_id,
                sub_question_id: null,
                text: question.question_text,
            });
        }
        for (const sub of question.sub_questions ?? []) {
            const subText = sub?.text ?? sub?.question_text;
            if (sub?.sub_question_id && subText) {
                out.push({
                    question_id: question.question_id,
                    sub_question_id: sub.sub_question_id,
                    text: subText,
                });
            }
        }
    }
    return out;
}
