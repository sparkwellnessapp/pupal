import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

import type { TranscribeResponse } from '@/types/transcription';
import { TranscriptionReviewPanel } from './TranscriptionReviewPanel';

/**
 * P4/U1 (decision 2, replacing the retired `single-flow-review-unchanged`
 * e2e): the single-flow wizard journey that drove that spec — mode toggle →
 * single-file CTA → review step — NO LONGER EXISTS (the upload step always
 * batches). The wrapper itself is QUARANTINED, not deleted (§11), so its two
 * pins move to the component level:
 *
 *  1. PROP SEAM UNCHANGED — `{response, onSubmit, onBack, submitting}`
 *     compiles and renders the shared surface (columns + editor + picker).
 *  2. BATCH AFFORDANCES INERT — no accept button, no save button/indicator,
 *     no approved chip, no batch counters; the single primary is שלח לבדיקה.
 *
 * The submit-payload shape (full snapshot, draft order, edited-over-draft)
 * stays pinned by the controller-free `handleSubmit` above plus the identical
 * assertion style in the batch controller suite — the wire itself is owned by
 * the quarantined flow and will be re-verified by the single-flow-deletion PR
 * if it ever resurrects the path.
 */

const RESPONSE: TranscribeResponse = {
    transcription_id: 'tx-1',
    draft: {
        schema_version: '1.0',
        student_name_suggestion: 'רז כהן',
        page_count: 1,
        answers: [
            {
                question_number: 1, sub_question_id: null,
                answer_text: 'int original = 1;', confidence: 0.9, page_numbers: [1],
            },
            {
                question_number: 2, sub_question_id: 'א',
                answer_text: 'int second = 2;', confidence: 0.95, page_numbers: [1],
            },
        ],
        annotations: [],
        model_version: null,
        transcription_duration_ms: null,
    },
    selection_groups: [],
};

function render(): string {
    return renderToStaticMarkup(
        <TranscriptionReviewPanel
            response={RESPONSE}
            onSubmit={async () => {}}
            onBack={() => {}}
            submitting={false}
        />,
    );
}

describe('TranscriptionReviewPanel — the quarantined single-flow wrapper (U1 decision 2)', () => {
    it('renders the shared surface through the unchanged prop seam', () => {
        const html = render();
        expect(html).toContain('בדיקת תמלול');
        expect(html).toContain('מבחן מקורי');
        expect(html).toContain('תמלול AI');
        expect(html).toContain('data-testid="transcription-editor"');
        expect(html).toContain('int original = 1;');
        expect(html).toContain('data-student-picker');
    });

    it('the single primary is שלח לבדיקה; batch affordances are absent', () => {
        const html = render();
        expect(html).toContain('שלח לבדיקה');
        // Batch-born affordances must NOT render here (Phase-5 rider 2):
        expect(html).not.toContain('אישור תמלול');           // accept CTA/modal
        expect(html).not.toContain('שינויים לא שמורים');      // save indicator
        expect(html).not.toContain('position-primary');       // R5 counters
        expect(html).not.toContain('reason-rail');            // R1 rail
        expect(html).not.toContain('אישור והמשך');
    })

    it('the submit primary is disabled until a student is picked', () => {
        const html = render();
        // SSR: studentId starts null → the primary carries disabled.
        const submitIdx = html.indexOf('שלח לבדיקה');
        const buttonOpen = html.lastIndexOf('<button', submitIdx);
        expect(html.slice(buttonOpen, submitIdx)).toContain('disabled');
    });
});

// ---------------------------------------------------------------------------
// F4 (closeout) — "unreachable by construction" is a claim no test made.
//
// P4/U1 deleted the mode toggle and the single-file CTA, which were the ONLY
// paths that set the gradingStep values rendering this panel. The component
// stays in-tree for the §11 PR. If §11 slips, this guard is what stops the
// quarantine from quietly becoming reachable again.
// ---------------------------------------------------------------------------
describe('F4 — the single-flow panel stays unreachable', () => {
  it('the quarantined ENTRY POINTS have no call sites', () => {
    // The first version of this guard asserted that no `setGradingStep(...)`
    // for a quarantined value appears in the source — and failed, correctly,
    // because those setters DO still exist: they live INSIDE the quarantined
    // handlers. Presence is not reachability. What actually makes the
    // machinery unreachable is that nothing CALLS its entry points, so that
    // is what this asserts.
    const src = readFileSync(join(process.cwd(), 'src', 'app', 'page.tsx'), 'utf-8')
    const entryPoints = ['handleGradeHandwritten', 'handleProceedFromUpload']

    for (const fn of entryPoints) {
      const declarations = src.split(`const ${fn}`).length - 1
      const mentions = src.split(fn).length - 1
      if (declarations === 0) continue          // §11 removal landed — fine
      expect(
        mentions - declarations,
        `${fn} is REFERENCED ${mentions - declarations} time(s) beyond its `
        + 'declaration — the single-flow machinery is reachable again. Either '
        + 'a new path calls it (that is the bug), or §11 landed and this '
        + 'guard should be deleted along with the component.',
      ).toBe(0)
    }
  })
})
