import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { GradeReviewSurface } from './GradeReviewSurface';
import type { WireDraft } from '@/utils/grade-review-model';
import type { NumericPolicy } from '@/lib/pricing';
import { cycleVerdict } from '@/utils/verdict-cycle';
import { initialCursor, queueState } from '@/utils/grade-review-cursor';
import {
    RV_ANSWER_NONE, RV_CHIP_FUZZY, RV_CHIP_NOT_FOUND, RV_FB_ABSENT, RV_FB_FRESH,
    RV_NO_CHECKS, RV_QUOTE, RV_SCOPE_FAILED,
} from '@/copy/grade-review';

/**
 * The RENDER half. The vitest suites above close the data-integrity half; they
 * never render React, so they cannot catch a white screen or a state that
 * paints the wrong grammar. This SSR-renders the real surface against the real
 * published fixtures — no mocks, no jsdom.
 */

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FIXTURES = path.resolve(HERE, '../../../../backend/tests/fixtures/grade_review');
const readFixture = (name: string): WireDraft =>
    JSON.parse(readFileSync(path.join(FIXTURES, name), 'utf-8'));

const POLICY: NumericPolicy = {
    precision: '0.25', rounding_mode: 'half_up', sum_tolerance: '0.01',
};

const CURSOR = initialCursor([
    { graded_test_id: 'a', status: 'draft', student_name: 'דן בסיוק' },
    { graded_test_id: 'b', status: 'grading', student_name: 'עומר גלבר' },
]);

const ANSWERS = [
    { question_number: 1, sub_question_id: null, answer_text: 'class Hobby\n{\n    private string name;\n}' },
    { question_number: 2, sub_question_id: null, answer_text: 'שורה בעברית בלבד' },
];

function render(over: Partial<React.ComponentProps<typeof GradeReviewSurface>> = {}) {
    const noop = () => undefined;
    return renderToStaticMarkup(
        <GradeReviewSurface
            draft={readFixture('draft_dan_basiuk.json')}
            answers={ANSWERS}
            questions={[{ question_id: 'q1', sub_question_id: null, text: 'הגדירו את המחלקה Hobby ואת התכונות שלה, ואז כתבו בנאי.' }]}
            policy={POLICY}
            overlay={{}}
            onOverlayChange={noop}
            feedbackOverrides={{}}
            onFeedbackChange={noop}
            onFeedbackRegenerate={noop}
            studentName="דן בסיוק"
            identityMeta="י״א 3 · מבחן 1 מתוך 2"
            queue={queueState(CURSOR, 'a')}
            eta="עוד כ-2 דקות"
            batchHref="/batches/x"
            canPrev={false}
            canNext
            onPrev={noop}
            onNext={noop}
            onOpenPreview={noop}
            onShowScan={noop}
            saveState="saved"
            onApprove={noop}
            onSaveNow={noop}
            onNotice={noop}
            {...over}
        />,
    );
}

describe('GradeReviewSurface renders a real published draft', () => {
    const html = render();

    it('renders every scope, with a checklist under each', () => {
        expect(html).toContain('data-scope-id="q1.א"');
        expect(html.match(/data-check-id=/g)?.length).toBeGreaterThan(20);
    });

    it('shows Vivi\'s total in PENCIL while nothing is overridden', () => {
        expect(html).toContain('data-overridden="false"');
        expect(html).toContain('הצעת ויוי');
        expect(html).not.toContain('אחרי השינויים שלך');
    });

    it('turns the total RED the moment she decides something different', () => {
        const draft = readFixture('draft_dan_basiuk.json');
        const scope = draft.scope_outcomes![0];
        const criterion = scope.criterion_outcomes![0];
        const leaf = criterion.sub_criterion_outcomes?.length
            ? criterion.sub_criterion_outcomes[0] : criterion;
        const terminalId = leaf.sub_criterion_id || criterion.criterion_id;
        const check = leaf.checks![0];
        const overlay = cycleVerdict({}, terminalId, check.check_id, check.verdict);

        const overridden = render({ overlay });
        expect(overridden).toContain('אחרי השינויים שלך');
        expect(overridden).toContain('data-overridden="true"');

        // The proposal survives beside her decision — provenance is never lost,
        // and it carries the GLYPH VIVI CHOSE plus what that was worth, struck
        // through. Showing only the glyph (the first version of this) loses the
        // one number she is actually deciding against.
        expect(overridden).toContain('הצעת ויוי:');
        const struck = /<s[^>]*>([^<]*)<\/s>/.exec(overridden)?.[1] ?? '';
        expect(struck).toContain('✓');           // Vivi said met…
        expect(struck).not.toContain('✗');       // …not what the teacher now says
        expect(struck).toMatch(/·\s*\d/);        // and it was worth something
    });

    it('renders a code answer as an LTR island with line numbers', () => {
        expect(html).toContain('data-answer-mode="code"');
        expect(html).toContain('dir="ltr"');
    });

    it('renders an all-Hebrew answer as prose, never as a code island', () => {
        const proseOnly = render({
            answers: [{ question_number: 1, sub_question_id: null, answer_text: 'תשובה בעברית בלבד' }],
        });
        expect(proseOnly).toContain('data-answer-mode="prose"');
    });

    it('offers the quote button, and the scope nav', () => {
        expect(html).toContain(RV_QUOTE);
        expect(html).toContain('data-nav-scope="q1.א"');
    });

    /**
     * PR-G4 landed and the fixtures were backfilled, so the published drafts
     * now carry real per-scope feedback with a `basis_hash`. These three pin
     * the whole R11 lifecycle against that real data.
     */
    it('renders the real per-scope feedback Vivi wrote', () => {
        expect(html).toContain(RV_FB_FRESH);
        expect(html).toContain('data-feedback-state="fresh"');
        expect(html).not.toContain(RV_FB_ABSENT);
    });

    it('goes STALE on the scope whose verdict she just moved — and only there', () => {
        const draft = readFixture('draft_dan_basiuk.json');
        const scope = draft.scope_outcomes![0];
        const criterion = scope.criterion_outcomes![0];
        const leaf = criterion.sub_criterion_outcomes?.length
            ? criterion.sub_criterion_outcomes[0] : criterion;
        const terminalId = leaf.sub_criterion_id || criterion.criterion_id;
        const check = leaf.checks![0];

        const moved = render({
            overlay: cycleVerdict({}, terminalId, check.check_id, check.verdict),
        });
        expect(moved).toContain('data-feedback-state="stale"');
        expect(moved).toContain('נכתב לפני השינוי שלך');
        // Every OTHER scope's feedback is untouched — staleness is derived per
        // scope from its own verdict vector, not smeared across the test.
        const stale = moved.match(/data-feedback-state="stale"/g)?.length ?? 0;
        const fresh = moved.match(/data-feedback-state="fresh"/g)?.length ?? 0;
        expect(stale).toBe(1);
        expect(fresh).toBeGreaterThan(1);
    });

    it('still says «לא נכתב משוב» when the wire really carries none', () => {
        // `feedback = null` remains a first-class state: the call can fail
        // while the grade lands (review-first, never guess).
        const draft = { ...readFixture('draft_dan_basiuk.json'), feedback: null };
        expect(render({ draft })).toContain(RV_FB_ABSENT);
    });

    it('reports the save state and the approve action', () => {
        expect(html).toContain('data-save-state="saved"');
        expect(html).toContain('אישור וחתימה');
    });
});

describe('the states that carry the honesty', () => {
    const synthetic = readFixture('draft_SYNTHETIC_edge_cases.json');

    it('chips the invented-credit case and gives it no quote button', () => {
        const html = render({ draft: synthetic });
        expect(html).toContain(RV_CHIP_NOT_FOUND);
        expect(html).toContain(RV_CHIP_FUZZY);

        // The real assertion: a `not_found` check offers NO jump affordance.
        // (An earlier version asserted the absence of a highlight, which SSR
        // can never produce anyway — nothing is focused — so it passed
        // vacuously. Count the buttons against the checks that may have one.)
        const buttons = html.match(/ציטוט רלוונטי מהתשובה/g)?.length ?? 0;
        const eligible = JSON.stringify(synthetic).match(
            /"quote_status": ?"(exact|fuzzy)"/g)?.length ?? 0;
        expect(eligible).toBeGreaterThan(0);
        expect(buttons).toBe(eligible);
    });

    it('says «אין תשובה» for a scope with no answer, and marks it', () => {
        const html = render({ draft: synthetic, answers: [] });
        expect(html).toContain(RV_ANSWER_NONE);
        expect(html).toContain('data-answer-missing');
    });

    it('outlines a failed scope in red and offers a retry', () => {
        const html = render({
            draft: readFixture('draft_din_ezra.json'),
            onRetryScope: () => undefined,
        });
        expect(html).toContain('data-graded-by="failed"');
        expect(html).toContain(RV_SCOPE_FAILED);
    });

    it('REFUSES a pre-v5 draft instead of painting empty checklists', () => {
        const v3: WireDraft = {
            scope_outcomes: [{
                question_id: 'q1', sub_question_id: null,
                points_possible: '10', points_awarded: '10', graded_by: 'llm',
                criterion_outcomes: [{
                    criterion_id: 'c0', description: 'x',
                    points_possible: '10', points_awarded: '10', checks: null,
                }],
            }],
        };
        const html = render({ draft: v3 });
        expect(html).toContain('data-no-checks');
        expect(html).toContain(RV_NO_CHECKS);
        expect(html).not.toContain('data-check-id');
    });

    it('shows the WaitCard when nothing landed is left to review', () => {
        const exhausted = initialCursor([
            { graded_test_id: 'a', status: 'draft', student_name: 'דן' },
            { graded_test_id: 'b', status: 'grading', student_name: 'עומר' },
        ]);
        const html = render({ queue: queueState(exhausted, 'a') });
        expect(html).toContain('data-wait-card');
    });

    /** The ETA string arrives already phrased; the card must not re-prefix it. */
    it('WaitCard shows the ETA once — never «עוד עוד»', () => {
        const exhausted = initialCursor([
            { graded_test_id: 'a', status: 'draft', student_name: 'דן' },
            { graded_test_id: 'b', status: 'grading', student_name: 'עומר' },
        ]);
        const html = render({ queue: queueState(exhausted, 'a'), eta: 'עוד כ-2 דקות' });
        expect(html).toContain('עוד כ-2 דקות');
        expect(html).not.toContain('עוד עוד');
    });

    it('raises the version banner on a manual-edit revision', () => {
        expect(render({ versionBanner: { version: 2 } })).toContain('data-version-banner');
        expect(render({ versionBanner: null })).not.toContain('data-version-banner');
    });

    /**
     * The banner is driven by `regraded_from_id` — a fact the wire always
     * carries — while the chain position is not (the feed sends 1 for every
     * row today). The fact is stated; the number is omitted, never invented.
     */
    it('states the revision fact without a number when the feed has none', () => {
        const html = render({ versionBanner: { version: null } });
        expect(html).toContain('data-version-banner');
        expect(html).toContain('את עורכת בדיקה שכבר אושרה');
        // A NUMBERED version is what must not appear; «הגרסה החדשה» in the
        // banner's own sentence is not a number.
        expect(html).not.toMatch(/גרסה \d/);
        expect(render({ versionBanner: { version: 2 } })).toContain('גרסה 2');
    });

    it('reports a failed save in the teacher\'s words, in red', () => {
        const html = render({ saveState: 'failed' });
        expect(html).toContain('data-save-state="failed"');
        expect(html).toContain('השמירה נכשלה — נסי שוב');
    });
});

/**
 * §2 — "keep its revision affordances (regrade / manual_edit / retry)
 * reachable from the review top bar's overflow, unchanged". Replacing a
 * surface must not quietly delete the ways out of it.
 */
describe('the revision overflow', () => {
    const revision = {
        status: 'approved',
        contractStale: false,
        onRegrade: () => undefined,
        onManualEdit: () => undefined,
        onRetry: () => undefined,
    };

    it('offers manual-edit on an approved test', () => {
        expect(render({ revision })).toContain('data-revision-menu');
    });

    it('offers retry on a failed test', () => {
        expect(render({ revision: { ...revision, status: 'failed' } }))
            .toContain('data-revision-menu');
    });

    /**
     * A draft is the thing being reviewed: none of the three revisions applies,
     * so there is NO button at all. An overflow that opens onto an empty list
     * is a promise the surface cannot keep.
     */
    it('shows no overflow at all on a draft', () => {
        expect(render({ revision: { ...revision, status: 'draft' } }))
            .not.toContain('data-revision-menu');
    });

    it('is absent entirely when the page passes no revision affordances', () => {
        expect(render()).not.toContain('data-revision-menu');
    });
});

describe('R11 — a regeneration that would overwrite her words', () => {
    it('is OFFERED beside them, with both choices visible', () => {
        const html = render({ feedbackOffers: { summary: 'נוסח חדש של ויוי' } });
        expect(html).toContain('data-feedback-offer');
        expect(html).toContain('נוסח חדש של ויוי');
        expect(html).toContain('שמירה על הנוסח שלי');
        expect(html).toContain('שימוש בנוסח של ויוי');
    });

    it('shows nothing when there is no offer', () => {
        expect(render()).not.toContain('data-feedback-offer');
    });
});

describe('R12 — the stamp presses before she moves on', () => {
    it('animates only when the approval has just happened', () => {
        expect(render({ approved: true, stampPressed: true }))
            .toContain('motion-safe:animate-stamp-press');
        // A test she navigated BACK to shows the stamp at rest: the beat marks
        // the act of signing, not the state of being signed.
        expect(render({ approved: true, stampPressed: false }))
            .not.toContain('motion-safe:animate-stamp-press');
    });
});

/**
 * An approved test is immutable (LCY-2). This is not cosmetic: a live verdict
 * button on a signed test queues a save the server 409s, and because a failed
 * save blocks navigation, one stray keystroke strands her on that test with no
 * way forward.
 */
describe('readOnly — a signed test cannot be edited', () => {
    it('disables nothing about READING, and everything about writing', () => {
        const html = render({ approved: true, readOnly: true });
        // She can still read the whole grade…
        expect(html).toContain('data-check-id');
        // …and the approve button is gone.
        expect(html).not.toContain('אישור וחתימה (Ctrl');
    });

    it('still renders the checklist so she can see what was signed', () => {
        const html = render({ approved: true, readOnly: true });
        expect(html.match(/data-check-id=/g)?.length).toBeGreaterThan(10);
    });
});

describe('R3 — the nav dot counts what F walks', () => {
    it('shows a dot on a scope whose only marker is a FLAG', () => {
        // The model's own per-scope tally counted quote markers and dead scopes
        // but not bounds_clamped, so a question F stopped at showed no dot.
        const draft = readFixture('draft_dan_basiuk.json');
        const html = render({ draft });
        // dan_basiuk carries exactly one marker, and it is a clamp.
        expect(html).toContain('סימון אחד לבדוק');
    });
});

/**
 * A BACKEND GAP, recorded as a test rather than a comment.
 *
 * `app/agents/feedback/runner.py` stamps a `basis_hash` on every SCOPE text and
 * never on the summary, so `block.summary` keeps its default `""`. Spec §1.3
 * makes `basis_hash` part of `FeedbackText`, and the summary is a
 * `FeedbackText` — so this is a gap, not a design.
 *
 * The client behaves correctly either way: no basis ⇒ never stale, because an
 * amber "rewrite me" on text that has no idea what it described is a warning
 * she cannot act on. But the CONSEQUENCE is visible: she moves a verdict, the
 * scope's feedback correctly goes amber, and the whole-test summary — which
 * certainly depends on that verdict — keeps claiming to be current.
 *
 * When the backend stamps it, THIS TEST FAILS. That is the point: the failure
 * is the notification, and the fix is to delete this block.
 */
describe('the summary cannot go stale — because the wire carries no basis', () => {
    it('has no basis_hash on any published fixture', () => {
        for (const name of ['dan_basiuk', 'din_ezra', 'moran_aharon',
            'omer_gelber', 'yonatan_basiuk']) {
            const draft = readFixture(`draft_${name}.json`);
            expect(draft.feedback?.summary?.text, name).toBeTruthy();
            expect(draft.feedback?.summary?.basis_hash || '', name).toBe('');
        }
    });

    it('so it stays fresh even when a verdict moves', () => {
        const draft = readFixture('draft_dan_basiuk.json');
        const criterion = draft.scope_outcomes![0].criterion_outcomes![0];
        const leaf = criterion.sub_criterion_outcomes?.length
            ? criterion.sub_criterion_outcomes[0] : criterion;
        const html = render({
            overlay: cycleVerdict(
                {},
                leaf.sub_criterion_id || criterion.criterion_id,
                leaf.checks![0].check_id,
                leaf.checks![0].verdict,
            ),
        });
        // Exactly one stale card — the scope. The summary is not among them.
        expect(html.match(/data-feedback-state="stale"/g)?.length).toBe(1);
    });
});
