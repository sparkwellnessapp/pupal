'use client';

import { useEffect, useState } from 'react';

import { getAnswerSource, type AnswerSourceResponse } from '@/lib/api';
import { surfaceError } from '@/lib/errorSurface';
import { hasMathNotation } from '@/lib/subjects';
import { hasMath } from '@/utils/math-spans';
import { MathAnswerEditor } from '@/components/batch-review/MathAnswerEditor';
import { TranscribedTextEditor } from '@/components/batch-review/TranscribedTextEditor';
import {
    V6_EDIT_CANCEL, V6_EDIT_LOADING, V6_FIGURE_LINES_LOCKED, V6_REGRADE_CONFIRM,
    V6_REGRADE_CONFIRM_GO, V6_REGRADING, V6_SAVE_AND_REGRADE, V6_SHARED_ANSWER,
} from '@/copy/grade-review-v6';

/**
 * Correcting the transcription at the grading gate (SRG, owner rulings 2026-11-01).
 *
 * It opens on the RAW answer the scope reads (`GET …/answers/source`) — never the
 * text on screen, which carries each figure's readings expanded under its line;
 * saving that back would write derived lines into the transcription. The server
 * resolves which answer that is (an inheriting part edits its parent's answer, D3)
 * and names every part that shares it, so nothing here re-derives the rule.
 *
 * The editor is the transcription gate's own (MathLive for a math answer, a `dir`
 * island otherwise — the bidi standing rule), so a correction reads the same here
 * as there.
 *
 * KEYS STAY HERE. The review surface listens on `window` (Ctrl+↵ approves, arrows
 * move between tests); a key typed in this editor must never sign the test or leave
 * it, so every keydown stops at this box (the FeedbackCard precedent).
 *
 * D5: when her own decisions would be cleared, the save asks first — inline, so no
 * modal interferes with the surface's keyboard gating. D11: the save stays disabled
 * until the text differs (a failed question is the exception, D10).
 */
export function AnswerEditor({
    gradedTestId, questionId, subQuestionId, subject, failed, busy,
    titleOf, decidedIn, onSubmit, onCancel,
}: {
    gradedTestId: string;
    questionId: string;
    subQuestionId: string | null;
    subject: string | null;
    /** The question failed to grade: the save is a retry even with the text unchanged. */
    failed: boolean;
    /** This correction is being regraded right now. */
    busy: boolean;
    titleOf: (scopeId: string) => string;
    /** How many criteria SHE decided across these scopes (D5 — what a regrade clears). */
    decidedIn: (scopeIds: readonly string[]) => number;
    onSubmit: (answerText: string) => void;
    onCancel: () => void;
}) {
    const [source, setSource] = useState<AnswerSourceResponse | null>(null);
    const [text, setText] = useState('');
    const [confirming, setConfirming] = useState(false);

    useEffect(() => {
        let alive = true;
        getAnswerSource(gradedTestId, questionId, subQuestionId)
            .then((src) => { if (alive) { setSource(src); setText(src.answer_text); } })
            .catch((err) => { if (alive) { surfaceError(err); onCancel(); } });
        return () => { alive = false; };
        // eslint-disable-next-line react-hooks/exhaustive-deps -- opened once per scope
    }, [gradedTestId, questionId, subQuestionId]);

    if (!source) {
        return <p className="text-gr-meta text-grade-pencil" data-answer-editor-loading>{V6_EDIT_LOADING}</p>;
    }

    const changed = text !== source.answer_text;
    const canSave = !busy && (changed || failed);
    const others = source.shared_scope_ids.filter((sid) =>
        sid !== (subQuestionId ? `${questionId}.${subQuestionId}` : questionId));
    const cleared = decidedIn(source.shared_scope_ids);
    const math = hasMathNotation(subject);

    const save = () => {
        if (!canSave) return;
        if (cleared > 0 && !confirming) { setConfirming(true); return; }
        setConfirming(false);
        onSubmit(text);
    };

    return (
        <div
            data-answer-editor
            className="flex flex-col gap-2"
            onKeyDown={(e) => e.stopPropagation()}
        >
            {others.length > 0 ? (
                <p data-answer-shared className="text-gr-meta text-grade-ink-2">
                    {V6_SHARED_ANSWER(source.shared_scope_ids.map(titleOf).join(', '))}
                </p>
            ) : null}
            {source.has_figures ? (
                <p className="text-gr-meta text-grade-pencil">{V6_FIGURE_LINES_LOCKED}</p>
            ) : null}
            {math && hasMath(text) ? (
                <MathAnswerEditor value={text} onChange={setText} readOnly={busy} />
            ) : (
                <TranscribedTextEditor
                    dir={math ? 'rtl' : 'ltr'}
                    value={text}
                    onChange={setText}
                    readOnly={busy}
                />
            )}
            {confirming && !busy ? (
                <div data-regrade-confirm className="rounded-grade-ctl border border-grade-amber-200
                    bg-grade-amber-50 px-3 py-2 text-gr-meta text-grade-amber-ink">
                    <p className="mb-2">{V6_REGRADE_CONFIRM(cleared)}</p>
                    <div className="flex gap-2">
                        <button type="button" onClick={save}
                            className="rounded-grade-ctl bg-primary-600 px-3 py-1 text-white">
                            {V6_REGRADE_CONFIRM_GO}
                        </button>
                        <button type="button" onClick={() => setConfirming(false)}
                            className="rounded-grade-ctl px-3 py-1 text-grade-ink-2">
                            {V6_EDIT_CANCEL}
                        </button>
                    </div>
                </div>
            ) : (
                <div className="flex items-center gap-2">
                    <button
                        type="button"
                        data-save-and-regrade
                        onClick={save}
                        disabled={!canSave}
                        className="rounded-grade-ctl bg-primary-600 px-3 py-1.5 text-gr-meta text-white
                            disabled:cursor-not-allowed disabled:opacity-50"
                    >
                        {busy ? V6_REGRADING : V6_SAVE_AND_REGRADE}
                    </button>
                    <button type="button" onClick={onCancel} disabled={busy}
                        className="rounded-grade-ctl px-3 py-1.5 text-gr-meta text-grade-ink-2
                            disabled:opacity-50">
                        {V6_EDIT_CANCEL}
                    </button>
                </div>
            )}
        </div>
    );
}
