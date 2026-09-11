import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

import { GradeReviewSurface } from './GradeReviewSurface';
import { ancestorPaths, type WireDraft } from '@/utils/grade-review-model';
import type { NumericPolicy } from '@/lib/pricing';
import { cycleVerdict, type OverlayTerminals } from '@/utils/verdict-cycle';
import { initialCursor, queueState } from '@/utils/grade-review-cursor';
import {
    RV_ANSWER_INHERITED, RV_ANSWER_NONE, RV_ANSWER_UNAVAILABLE, RV_CHIP_NOT_FOUND, RV_FB_ABSENT, RV_FB_FRESH,
    RV_NO_CHECKS, RV_QUOTE, RV_SCOPE_FAILED,
    RV_QUOTE_ALL,
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

const CODE_ANSWER = `class Hobby
{
    private string name;
}`;

const TRANSCRIPTIONS = path.resolve(
    HERE, '../../../../backend/tests/grading_eval_suite/benchmarks/transcriptions');

/**
 * [EVD-1] Attach the REAL graded answers to a published fixture draft.
 *
 * The drafts and the transcription contracts are two halves of the SAME eval
 * run, so pairing them gives each scope the text its checks actually quote.
 * That matters now that the quote button renders on `canHighlight`: a fixture
 * carrying real checks beside a FABRICATED answer produces no buttons at all —
 * correctly, since those quotes are genuinely not in that text — and the
 * button assertions would be testing the fabrication rather than the surface.
 *
 * The answer is resolved by the same rule the server uses: the scope's own key
 * first, then each ancestor path, then the whole question (`gradable_compiler`'s
 * nearest-ancestor fallback).
 */
function withRealAnswers(draft: WireDraft, student: string): WireDraft {
    const contract = JSON.parse(readFileSync(
        path.join(TRANSCRIPTIONS, `${student}.contract.json`), 'utf-8')) as {
            answers: { question_number: number; sub_question_id?: string | null;
                       answer_text: string }[];
        };
    const byKey = new Map(contract.answers.map(
        (a) => [`${a.question_number}|${a.sub_question_id ?? ''}`, a.answer_text]));

    return {
        ...draft,
        scope_outcomes: (draft.scope_outcomes ?? []).map((scope) => {
            const n = Number((/\d+/.exec(scope.question_id) ?? ['0'])[0]);
            const own = scope.sub_question_id ?? null;
            for (const candidate of ancestorPaths(own)) {
                const text = byKey.get(`${n}|${candidate ?? ''}`);
                if (text === undefined) continue;
                return {
                    ...scope,
                    student_answer: candidate === own
                        ? { text, source: 'own' as const, inherited_from: null }
                        : { text, source: 'inherited' as const, inherited_from: candidate },
                };
            }
            return scope;
        }),
    };
}

/**
 * Attach ONE synthetic answer to every scope — for the render states the real
 * cohort cannot produce (an all-Hebrew prose answer; an English essay). Quote
 * buttons are not meaningful on these, and are not asserted.
 */
const withAnswer = (
    draft: WireDraft,
    text: string,
    source: 'own' | 'inherited' = 'own',
    inheritedFrom?: string,
): WireDraft => ({
    ...draft,
    scope_outcomes: (draft.scope_outcomes ?? []).map((scope) => ({
        ...scope,
        student_answer: { text, source, inherited_from: inheritedFrom ?? null },
    })),
});

function render(over: Partial<React.ComponentProps<typeof GradeReviewSurface>> = {}) {
    const noop = () => undefined;
    return renderToStaticMarkup(
        <GradeReviewSurface
            draft={withRealAnswers(readFixture('draft_dan_basiuk.json'), 'dan_basiuk')}
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

/**
 * [S4] An overlay in which she has touched ONE check in every criterion.
 *
 * Used to open every breakdown through the PRODUCT'S OWN RULE — a criterion she
 * has already decided re-opens when she returns to a part-reviewed test — and
 * not through a test-only hook. That keeps these assertions honest: if the
 * re-entry rule ever breaks, the tests that rely on it fail rather than sailing
 * past on a back door SSR gave them.
 */
function overlayTouchingEveryCriterion(draft: WireDraft): OverlayTerminals {
    let overlay: OverlayTerminals = {};
    for (const scope of draft.scope_outcomes ?? []) {
        for (const criterion of scope.criterion_outcomes ?? []) {
            const leaves = criterion.sub_criterion_outcomes?.length
                ? criterion.sub_criterion_outcomes
                : [criterion];
            for (const leaf of leaves) {
                const terminalId = ('sub_criterion_id' in leaf && leaf.sub_criterion_id)
                    || criterion.criterion_id;
                const first = leaf.checks?.[0];
                if (first) {
                    overlay = cycleVerdict(overlay, terminalId, first.check_id, first.verdict);
                }
            }
        }
    }
    return overlay;
}

/** The same draft `render()` uses by default — so an overlay built from it fits. */
const DAN = readFixture('draft_dan_basiuk.json');

describe('GradeReviewSurface renders a real published draft', () => {
    const html = render();

    it('renders every scope, and folds each criterion behind a disclosure [S4]', () => {
        expect(html).toContain('data-scope-id="q1.א"');
        // Every criterion offers a way in…
        expect((html.match(/data-breakdown-for=/g) ?? []).length).toBeGreaterThan(0);
        // …and at least one starts CLOSED, so the page does not open with every
        // row showing. (Criteria carrying a marker open themselves — D1.)
        expect(html).toContain('data-expanded="false"');
        // Fewer than HALF the checks are on screen. (`× 4` here was nearly
        // vacuous: 38 boxes × 4 = 152, against one visible row.)
        const totalChecks = (DAN.scope_outcomes ?? []).flatMap((sc) =>
            (sc.criterion_outcomes ?? []).flatMap((co) => [
                ...(co.checks ?? []),
                ...(co.sub_criterion_outcomes ?? []).flatMap((l) => l.checks ?? []),
            ])).length;
        expect(totalChecks).toBeGreaterThan(20);
        expect((html.match(/data-check-id=/g) ?? []).length).toBeLessThan(totalChecks / 2);
    });

    it('re-opens the criteria she had already decided, and renders their rows', () => {
        const open = render({ overlay: overlayTouchingEveryCriterion(DAN) });
        expect((open.match(/data-check-id=/g) ?? []).length).toBeGreaterThan(20);
        expect(open).not.toContain('data-expanded="false"');
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
            draft: withAnswer(readFixture('draft_dan_basiuk.json'), 'תשובה בעברית בלבד'),
        });
        expect(proseOnly).toContain('data-answer-mode="prose"');
    });

    // Phase 3a (multisubject): the SUBJECT decides the answer's grammar, never a
    // heuristic over the text. The same C#-looking string is prose in English and
    // Hebrew-direction prose in Mathematics.
    it('renders an English answer as LTR prose even when it looks like code', () => {
        const html_en = render({
            subject: 'english',
            draft: withAnswer(readFixture('draft_dan_basiuk.json'), `class Hobby
{
    private string name;
}`),
        });
        expect(html_en).toContain('data-answer-mode="prose"');
        expect(html_en).toContain('data-answer-dir="ltr"');
        expect(html_en).not.toContain('data-answer-mode="code"');
    });

    it('renders a Mathematics answer as RTL prose', () => {
        const html_math = render({
            subject: 'mathematics',
            draft: withAnswer(readFixture('draft_dan_basiuk.json'), `f(x) = (ln x)^2 - ln x - 2
מינימום (sqrt(e), -2.25)`),
        });
        expect(html_math).toContain('data-answer-mode="prose"');
        expect(html_math).toContain('data-answer-dir="rtl"');
    });

    it('offers both quote buttons, and the scope nav', () => {
        // The criterion-level button lives in the HEADER, so it is reachable
        // without opening anything — that is the point of putting it there.
        expect(html).toContain(RV_QUOTE_ALL);
        expect(html).toContain('data-nav-scope="q1.א"');
        // The per-check one travels with the breakdown it belongs to.
        expect(render({ overlay: overlayTouchingEveryCriterion(DAN) })).toContain(RV_QUOTE);
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

        // A `not_found` check offers NO jump affordance. (An earlier version
        // asserted the absence of a highlight, which SSR can never produce
        // anyway — nothing is focused — so it passed vacuously.)
        //
        // The count is now against what can actually be MARKED, not against
        // `quote_status`. That status is the server's verdict under its own
        // normalisation; the button renders on `canHighlight`, which asks the
        // real matcher against the real answer. Pairing the fixture with a text
        // that contains none of its quotes is exactly the case where the two
        // diverge — and the honest answer there is no buttons at all.
        const buttons = html.match(/ציטוט רלוונטי מהתשובה/g)?.length ?? 0;
        expect(buttons).toBe(0);
    });

    it('offers a button exactly for the checks whose quote is IN the answer', () => {
        // The positive half of the same rule, driven by an answer we control.
        // Three checks, one of each outcome:
        //
        //   fuzzy,     quote PRESENT  -> the one button
        //   not_found, quote PRESENT  -> still none (see below)
        //   exact,     quote MISSING  -> none; nothing to jump to
        //
        // The `not_found` row is the interesting one, and this test used to
        // assert the OPPOSITE by accident: it took `checks[0]` as "the present
        // quote" without noticing that check is the not_found one, so it pinned
        // «an invented-credit check gets a highlight button». That contradicts
        // this module's own stated rule — not_found means NO MARK AT ALL and no
        // quote button — and it was reachable for real, because the client's
        // fuzzy floor (0.6) is looser than the server's certification (0.85).
        // `canHighlight` now asks the SAME eligibility rule the resolver
        // applies, so the button and the highlight can no longer disagree.
        const first = (synthetic.scope_outcomes ?? [])[0];
        const checks = first!.criterion_outcomes![0].checks!;
        const notFound = checks.find((c) => c.quote_status === 'not_found')!;
        const fuzzy = checks.find((c) => c.quote_status === 'fuzzy')!;
        expect(typeof notFound.quote).toBe('string');
        expect(typeof fuzzy.quote).toBe('string');

        const html = render({
            draft: {
                ...synthetic,
                scope_outcomes: [{
                    ...first,
                    // BOTH quotes are genuinely in the text, verbatim.
                    student_answer: {
                        text: ['before', notFound.quote, fuzzy.quote, 'after'].join('\n'),
                        source: 'own',
                        inherited_from: null,
                    },
                    criterion_outcomes: [{
                        ...first.criterion_outcomes![0],
                        checks: [
                            notFound,
                            fuzzy,
                            {
                                ...fuzzy,
                                check_id: 'absent-quote',
                                quote: 'int nothingLikeThis = 0 ;',
                                quote_status: 'exact',
                            },
                        ],
                    }],
                }],
            } as WireDraft,
        });
        expect((html.match(/ציטוט רלוונטי מהתשובה/g) ?? []).length).toBe(1);
    });

    /**
     * [EVD-1] «No answer» and «cannot show the answer» are DIFFERENT claims, and
     * the surface must never substitute one for the other. The first accuses the
     * student of leaving it blank; the second admits our own gap. The bug this
     * replaced made the first claim on a scope graded 12/12 with a verbatim
     * quotation from the answer it said did not exist.
     */
    it('says «אין תשובה» only when the grader itself skipped for want of one', () => {
        const skipped: WireDraft = {
            ...synthetic,
            scope_outcomes: (synthetic.scope_outcomes ?? []).map((scope) => ({
                ...scope, graded_by: 'skipped_no_answer', student_answer: null,
            })),
        };
        const html = render({ draft: skipped });
        expect(html).toContain(RV_ANSWER_NONE);
        expect(html).toContain('data-answer-missing');
        expect(html).not.toContain(RV_ANSWER_UNAVAILABLE);
    });

    it('says «cannot show» — never «no answer» — for a graded scope with no evidence', () => {
        // Every scope GRADED and none carrying evidence: the exact shape of a
        // legacy row whose inputs have since moved, and the shape the old code
        // reported as «the student did not answer».
        const gradedWithoutEvidence: WireDraft = {
            ...synthetic,
            scope_outcomes: (synthetic.scope_outcomes ?? []).map((scope) => ({
                ...scope, graded_by: 'llm', student_answer: null,
            })),
        };
        const html = render({ draft: gradedWithoutEvidence });
        expect(html).toContain(RV_ANSWER_UNAVAILABLE);
        expect(html).not.toContain(RV_ANSWER_NONE);
    });

    it('names the ancestor when the answer was inherited', () => {
        const html = render({
            draft: withAnswer(readFixture('draft_dan_basiuk.json'), CODE_ANSWER, 'inherited', 'א'),
        });
        expect(html).toContain('data-answer-inherited');
        expect(html).toContain(RV_ANSWER_INHERITED('א'));
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
        // A signed test folds like any other (D1 is uniform); opening it is
        // what shows the record. The overlay is the one the route hydrates
        // from the approved draft's own teacher_overrides.
        const html = render({
            approved: true, readOnly: true,
            overlay: overlayTouchingEveryCriterion(DAN),
        });
        expect((html.match(/data-check-id=/g) ?? []).length).toBeGreaterThan(10);
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

describe('the approve button obeys the gate before the server does [OD-R1]', () => {
    it('blocks — and stays CLICKABLE — when an ERROR is unresolved', () => {
        // draft_din_ezra carries `error/llm_failure` on q2.ב. §11: a native
        // `disabled` cannot explain itself, and «press it and find out» is how
        // the teacher met «שגיאת שרת (422)» four times.
        const html = render({ draft: readFixture('draft_din_ezra.json') });
        expect(html).toContain('data-blocked="true"');
        // …and it is the APPROVE button that carries no `disabled` (the prev/next
        // nav legitimately does, so a whole-document search would pass vacuously).
        // `disabled=` the ATTRIBUTE — the class list carries Tailwind's
        // `disabled:opacity-50` variant, which a bare substring test matches.
        const tag = html.slice(html.indexOf('data-blocked="true"'));
        expect(tag.slice(0, tag.indexOf('>'))).not.toContain('disabled=');
    });

    it('does not block a clean draft', () => {
        const html = render({ draft: readFixture('draft_dan_basiuk.json') });
        expect(html).not.toContain('data-blocked="true"');
    });
});

describe('the criterion-level quote button [S3]', () => {
    // Read here rather than shared from the honesty block: a describe's const
    // is not in scope across blocks, and hoisting it to file level would
    // parse the fixture for every suite that never touches it.
    const synthetic = readFixture('draft_SYNTHETIC_edge_cases.json');

    it('offers the union button on a criterion whose checks can be highlighted', () => {
        // `render()` with no override, deliberately: it attaches the REAL graded
        // answers (`withRealAnswers`). Passing the raw fixture pairs real checks
        // with a fabricated answer, `canHighlight` is false everywhere, and no
        // union button can exist — which is correct, and is exactly the case the
        // second test below asserts. The label differs from the per-check one, so
        // the two families are distinguishable on screen and in this assertion.
        const html = render();
        const buttons = (html.match(/data-terminal-quote=/g) ?? []).length;
        expect(buttons).toBeGreaterThan(0);
        expect(html).toContain(RV_QUOTE_ALL);
        // Every one renders unpinned on first paint — nothing is lit until she clicks.
        expect(html).not.toMatch(/data-terminal-quote="[^"]*" data-pinned="true"/);
    });

    it('offers NO union button when none of the criterion\'s quotes can be placed', () => {
        // Same rule as the per-check button, taken over the checks: an
        // invented-credit criterion has nothing to show, so it shows nothing.
        // (`synthetic` pairs the fixture with an answer containing none of its quotes.)
        const html = render({ draft: synthetic });
        expect(html.match(/data-terminal-quote=/g) ?? []).toHaveLength(0);
    });
});
