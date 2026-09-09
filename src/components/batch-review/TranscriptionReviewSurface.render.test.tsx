import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import type { TranscriptionDraft } from '@/types/transcription';
import { TranscriptionReviewSurface } from './TranscriptionReviewSurface';

/**
 * Selection-aware review surface (owner-ruled 2026-08-12): on a "choose k of
 * N" exam whose selection is satisfied, unchosen questions' empty containers
 * collapse into one disclosure row instead of rendering as gaps; an
 * under-answered group suppresses nothing. SSR pins the default (collapsed)
 * markup; the expand interaction is a client toggle.
 */

function draftWith(answers: Array<[number, string | null, string]>): TranscriptionDraft {
    return {
        schema_version: '1.0',
        student_name_suggestion: null,
        page_count: 1,
        answers: answers.map(([question_number, sub_question_id, answer_text]) => ({
            question_number, sub_question_id, answer_text,
            confidence: answer_text ? 0.95 : 0,
            page_numbers: answer_text ? [1] : [],
        })),
        annotations: [],
        model_version: null,
        transcription_duration_ms: null,
    };
}

function render(draft: TranscriptionDraft, groups?: { choose_k: number; question_numbers: number[] }[]) {
    return renderToStaticMarkup(
        <TranscriptionReviewSurface
            draft={draft}
            selectionGroups={groups}
            editedAnswers={{}}
            onAnswerChange={() => {}}
            studentId={null}
            onStudentPick={() => {}}
            readOnly={false}
            getPage={() => Promise.resolve('')}
            isDissolved={() => false}
            markDissolved={() => {}}
        />,
    );
}

describe('TranscriptionReviewSurface — R2 empty-answer marker', () => {
    // Three-way (P3 plan, decision 5): empty ∧ unexplained → marked;
    // empty ∧ selection-explained → collapsed (no marker anywhere);
    // filled → never marked. LIVE against current text by design.
    const answers: Array<[number, string | null, string]> = [
        [1, null, 'תשובה אמיתית לשאלה אחת'],
        [2, 'א', ''],
        [2, 'ב', ''],
    ];

    it('marks an empty, unexplained answer: amber card + marker chip + guidance placeholder', () => {
        const html = render(draftWith(answers));
        expect(html).toContain('empty-answer-marker');
        expect(html).toContain('תשובה ריקה — לא נמצא תוכן בסריקה');
        expect(html).toContain('border-amber-300');
        // §3.2 placeholder replaces the generic one on marked cards only.
        expect(html).toContain('אם התשובה קיימת בסריקה');
    });

    it('does not mark a selection-explained empty (the card is collapsed instead)', () => {
        const html = render(draftWith(answers), [{ choose_k: 1, question_numbers: [1, 2] }]);
        expect(html).not.toContain('empty-answer-marker');
        expect(html).not.toContain('border-amber-300');
    });

    it('never marks filled answers', () => {
        const html = render(draftWith([[1, null, 'מלא'], [2, null, 'גם מלא']]));
        expect(html).not.toContain('empty-answer-marker');
        expect(html).not.toContain('border-amber-300');
    });
});

describe('TranscriptionReviewSurface — R1/R10 hooks', () => {
    it('cards carry data-answer-key and the picker region carries data-student-picker (R1 anchors)', () => {
        const html = render(draftWith([[1, null, 'טקסט'], [2, 'א', 'עוד']]));
        expect(html).toContain('data-answer-key="q1"');
        expect(html).toContain('data-answer-key="q2.א"');
        expect(html).toContain('data-student-picker');
    });

    it('renders the zoom controls and the transform target at default scale (R10)', () => {
        const html = render(draftWith([[1, null, 'טקסט']]));
        expect(html).toContain('data-testid="zoom-in"');
        expect(html).toContain('data-testid="zoom-out"');
        expect(html).toContain('data-testid="scan-zoom-content"');
    });
});

describe('TranscriptionReviewSurface — selection expectation', () => {
    const answers: Array<[number, string | null, string]> = [
        [1, null, 'תשובה אמיתית לשאלה אחת'],
        [2, 'א', ''],
        [2, 'ב', ''],
    ];

    it('collapses unchosen questions into the disclosure row when selection is satisfied', () => {
        const html = render(draftWith(answers), [{ choose_k: 1, question_numbers: [1, 2] }]);
        expect(html).toContain('selection-unanswered-toggle');
        expect(html).toContain('שאלות שלא נענו (שאלות בחירה)');
        // q2's cards are collapsed: its labels appear ONLY in the toggle line.
        expect(html).not.toContain('שאלה 2 סעיף א');
        // Collapsed by default → no suppressed card, hence no per-card badge.
        expect(html).not.toContain('selection-unanswered-badge');
        // The answered question's card renders normally.
        expect(html).toContain('תשובה אמיתית לשאלה אחת');
    });

    it('suppresses nothing when the group is under-answered', () => {
        const html = render(draftWith(answers), [{ choose_k: 2, question_numbers: [1, 2] }]);
        expect(html).not.toContain('selection-unanswered-toggle');
        expect(html).toContain('שאלה 2 סעיף א');
        expect(html).toContain('שאלה 2 סעיף ב');
    });

    it('renders identically to old behavior without selection groups', () => {
        const html = render(draftWith(answers));
        expect(html).not.toContain('selection-unanswered-toggle');
        expect(html).toContain('שאלה 2 סעיף א');
    });
});

/**
 * Table rendering (2026-08-23). The default is content-derived and the raw text
 * is never displaced: a grid renders instead of the textarea only when there is
 * a grid AND nothing is flagged. Line flags outrank the prettier surface — they
 * are the review signal, and they exist only in the raw view.
 */
describe('TranscriptionReviewSurface — the answer view/edit split', () => {
    const TABLE_ANSWER = [
        'if:',
        'returned | x | i | arr[i]',
        '6 | 0 | 1 | F',
        '6 | 1 | 5 | F',
    ].join('\n');

    it('renders a table-bearing answer as a grid, with a toggle back to the text', () => {
        const html = render(draftWith([[1, null, TABLE_ANSWER]]));
        expect(html).toContain('data-testid="transcribed-answer-view"');
        expect(html).toContain('<table');
        expect(html).toContain('data-testid="answer-view-toggle"');
        expect(html).toContain('הצגת הטקסט המקורי');
        expect(html).not.toContain('data-testid="transcription-editor"');
        expect(html).not.toContain('6 | 0 | 1 | F');
    });

    it('keeps the editor when the answer carries a line flag, grid or not', () => {
        const flagged = `${TABLE_ANSWER}\n5 | [?] | 2 | T`;
        const html = render(draftWith([[1, null, flagged]]));
        expect(html).toContain('data-testid="transcription-editor"');
        expect(html).not.toContain('data-testid="transcribed-answer-view"');
        // The grid is still one click away — the toggle is offered, not forced.
        expect(html).toContain('data-testid="answer-view-toggle"');
        expect(html).toContain('הצגה כטבלה');
    });

    it('leaves a table-free answer exactly as before: editor, no toggle', () => {
        const html = render(draftWith([[1, null, 'public int foo()\nreturn 1']]));
        expect(html).toContain('data-testid="transcription-editor"');
        expect(html).not.toContain('data-testid="answer-view-toggle"');
        expect(html).not.toContain('data-testid="transcribed-answer-view"');
    });
});
