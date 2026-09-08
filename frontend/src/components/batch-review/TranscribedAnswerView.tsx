'use client';

/**
 * TranscribedAnswerView — the READ-ONLY rendering of one transcribed answer,
 * with the trace tables the student drew rendered as real tables.
 *
 * It is the display half of the surface's view/edit split. The rubric mirror
 * (`DocumentText`) is a reader and this surface is an editor, so the grid can
 * never replace the textarea — it sits beside it as a mode. THE RAW TEXT
 * REMAINS THE SOURCE OF TRUTH: this component takes a string and returns
 * markup, touches no state, and the accept/save payload is built from
 * `editedAnswers` exactly as before.
 *
 * Direction is pinned `ltr`, deliberately (owner-ruled 2026-08-23). Unlike the
 * docx path there is no `dir` token to conserve, and the textarea beside it is
 * an adjudicated LTR island — a content-guessed mirror would put the grid and
 * the raw text in disagreement about which end is column 1, giving the teacher
 * two truths on one screen. Cells keep their own bidi via `BidiText`, so a
 * Hebrew header cell still reads right-to-left inside its cell.
 */

import { segmentAnswerText } from '@/utils/detect-pipe-tables';
import { DocTable } from '@/components/document/DocTable';
import { ANSWER_VIEW_FLAGS_HIDDEN } from '@/copy/batch';

/** Blank lines around a table are layout, not content — the grid supplies its own. */
function trimEdgeBlankLines(text: string): string {
    return text.replace(/^\n+/, '').replace(/\n+$/, '');
}

export function TranscribedAnswerView({
    text,
    flagCount = 0,
    dir = 'ltr',
}: {
    text: string;
    /** >0 ⇒ the marked lines live only in the raw view; say so rather than hide it. */
    flagCount?: number;
    /** Direction of the prose segments, from the rubric's SUBJECT (Phase 3b); the
     *  grid keeps its own owner-ruled `ltr`. Default = today's behaviour. */
    dir?: 'ltr' | 'rtl';
}) {
    const segments = segmentAnswerText(text);

    return (
        <div data-testid="transcribed-answer-view">
            {flagCount > 0 && (
                <div className="mb-2 text-xs text-amber-700" dir="rtl">
                    {ANSWER_VIEW_FLAGS_HIDDEN}
                </div>
            )}
            <div
                dir={dir}
                className="w-full p-3 rounded-lg border border-surface-300 bg-surface-50"
            >
                {segments.map((seg, i) => {
                    if (seg.kind === 'table') {
                        return (
                            <DocTable
                                key={i}
                                rows={seg.rows}
                                hasHeader={seg.hasHeader}
                                dir="ltr"
                            />
                        );
                    }
                    const body = trimEdgeBlankLines(seg.text);
                    if (!body.trim()) return null;
                    return (
                        // Monospace + pre-wrap so switching modes does not reflow her
                        // text: this is visually the textarea, minus the caret.
                        <pre
                            key={i}
                            className="font-mono text-sm whitespace-pre-wrap break-words text-gray-800"
                        >
                            {body}
                        </pre>
                    );
                })}
            </div>
        </div>
    );
}
