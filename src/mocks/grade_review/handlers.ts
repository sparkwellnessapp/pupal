import { http, HttpResponse } from 'msw';

import {
    BATCH_FEED_STATES,
    FIXTURE_STUDENTS,
    PENDING_FIXTURES,
    fixtureUrl,
    type BatchFeedState,
    type FixtureStudent,
} from './registry';
import { priceScopeChecks, type PricingCheck, type ScopeTerminal } from '@/lib/pricing';
import { add, dec, toString as decToString } from '@/lib/decimal';
import { syntheticPageResponse } from './syntheticPage';

/**
 * MSW handlers for the grade-review module, keyed by a `?fixture=` query.
 * DEV ONLY — deleted at integration; the fixtures stay as unit-test inputs.
 *
 * ── WHAT THIS LAYER IS FOR, AND WHAT IT IS NOT ────────────────────────────
 * It is for driving UI STATES before the endpoints land: a real draft with
 * real checks, so F2 can be built and looked at.
 *
 * It is NOT a parity signal. `PATCH /draft` re-prices here with the very TS
 * mirror the client uses, so of course they agree — that comparison is
 * circular and proves nothing. Parity is `pricer-parity` against the published
 * vectors, and nothing here may ever be cited as evidence for it.
 *
 * ── PENDING ENDPOINTS REFUSE ──────────────────────────────────────────────
 * An endpoint whose fixture is not published answers 501 with the backend's
 * own reason. It does not get a plausible payload: a made-up shape would let a
 * surface be built against something nobody agreed to, and the disagreement
 * would surface at integration instead of now.
 *
 * The batch feed WAS in that category and no longer is — PR-G8 shipped the
 * endpoint (9c627a6) and the four state fixtures (114baf7). It is served from
 * those fixtures now, generated from the live wire types and re-validated
 * against them by tests/api/test_batch_feed_fixtures.py, so it cannot drift
 * from the endpoint it stands in for.
 */

const API = '*/api/v0';
/** The pilot rubric's policy (hobby_tvshow). Real responses now carry their
 *  own `numeric_policy` (OD-F8, shipped) — this is the mock's stand-in for
 *  the one rubric these fixtures came from, and it is served on the response
 *  too so F2 reads it off the wire exactly as it will in production. */
const PILOT_POLICY = {
    precision: '0.25',
    rounding_mode: 'half_up',
    sum_tolerance: '0.01',
} as const;

interface WireTerminal {
    criterion_id?: string;
    sub_criterion_id?: string;
    points_possible: string;
    points_awarded: string;
    checks?: PricingCheck[] | null;
    sub_criterion_outcomes?: WireTerminal[] | null;
}

interface WireScope {
    question_id: string;
    sub_question_id: string | null;
    points_possible: string;
    points_awarded: string;
    graded_by: string;
    criterion_outcomes: WireTerminal[];
}

interface WireDraft {
    scope_outcomes: WireScope[];
    [key: string]: unknown;
}

/** A leaf is a sub-criterion when there are sub-criteria, else the criterion. */
function terminalsOf(scope: WireScope): ScopeTerminal[] {
    const out: ScopeTerminal[] = [];
    for (const criterion of scope.criterion_outcomes ?? []) {
        const leaves = criterion.sub_criterion_outcomes?.length
            ? criterion.sub_criterion_outcomes
            : [criterion];
        for (const leaf of leaves) {
            out.push({
                terminal_id: (leaf.sub_criterion_id ?? leaf.criterion_id) as string,
                points_possible: leaf.points_possible,
                checks: leaf.checks ?? [],
            });
        }
    }
    return out;
}

/** Σ over scopes of Σ over terminals — NOT selection-aware (see below). */
function totalAwarded(draft: WireDraft): string {
    // Summed with the decimal helpers, not `Number()`. A mock is read as an
    // example, and a float sum here would be copied into F2 by whoever reads
    // it next — which is how the arithmetic this module exists to protect
    // gets undone one convenience at a time.
    let total = dec('0');
    for (const scope of draft.scope_outcomes ?? []) {
        // Selection ("choose k of N") exclusion is DERIVED server-side from
        // post-override scores and is deliberately not reimplemented here
        // (CLAUDE.md §5). The pilot rubric has no selection groups, so this
        // sum is honest for the fixtures and for nothing else.
        if (scope.graded_by === 'excluded_by_selection') continue;
        const priced = priceScopeChecks(terminalsOf(scope), PILOT_POLICY);
        for (const value of Object.values(priced)) total = add(total, dec(value));
    }
    return decToString(total);
}

const isStudent = (value: string | null): value is FixtureStudent =>
    (FIXTURE_STUDENTS as readonly string[]).includes(value ?? '');

async function loadDraft(student: FixtureStudent): Promise<WireDraft> {
    const response = await fetch(fixtureUrl(`draft_${student}.json`));
    if (!response.ok) throw new Error(`fixture draft_${student}.json unavailable`);
    return response.json() as Promise<WireDraft>;
}

function notPublished(fixture: string) {
    return HttpResponse.json(
        {
            error: 'fixture_not_published',
            fixture,
            reason: PENDING_FIXTURES[fixture] ?? 'not part of the published §1.7 set',
            note: 'the mock refuses rather than inventing a shape — surface the gap',
        },
        { status: 501 },
    );
}

/** Stable per-transcription seed, so a screenshot diff does not churn. */
function seedFrom(id: string): number {
    let h = 0;
    for (let i = 0; i < id.length; i++) h = (Math.imul(h, 31) + id.charCodeAt(i)) | 0;
    return Math.abs(h);
}

/** `?state=landing|running|done|complete`; defaults to the first. */
function stateFrom(url: string): BatchFeedState {
    const asked = new URL(url).searchParams.get('state');
    return (BATCH_FEED_STATES as readonly string[]).includes(asked ?? '')
        ? (asked as BatchFeedState)
        : BATCH_FEED_STATES[0];
}

/** `?fixture=dan_basiuk`; defaults to the first pilot student. */
function studentFrom(url: string): FixtureStudent {
    const asked = new URL(url).searchParams.get('fixture');
    return isStudent(asked) ? asked : FIXTURE_STUDENTS[0];
}

export const gradeReviewHandlers = [
    // ── published: the real drafts ───────────────────────────────────────
    http.get(`${API}/grading/graded_test/:id`, async ({ params, request }) => {
        const student = studentFrom(request.url);
        const draft = await loadDraft(student);
        return HttpResponse.json({
            id: params.id,
            status: 'draft',
            student_name: student,
            filename: `${student}.pdf`,
            total_score: totalAwarded(draft),
            total_possible: '100',
            percentage: null,
            total_cost_usd: null,
            transcription_id: `mock-transcription-${student}`,
            numeric_policy: PILOT_POLICY,
            draft,
            rubric_contract_stale: false,
            regraded_from_id: null,
        });
    }),

    http.patch(`${API}/grading/graded_test/:id/draft`, async ({ request }) => {
        const draft = await loadDraft(studentFrom(request.url));
        return HttpResponse.json({
            // Circular by construction — see the module doc. Never parity.
            effective_totals: { total_awarded: totalAwarded(draft) },
            pricing_mismatch: false,
        });
    }),

    // ── published: the four dashboard states (PR-G8) ─────────────────────
    // `?state=landing|running|done|complete`; defaults to the first.
    http.get(`${API}/batches/:id`, async ({ request }) => {
        const state = stateFrom(request.url);
        const response = await fetch(fixtureUrl(`batch_feed_${state}.json`));
        if (!response.ok) {
            return notPublished(`batch_feed_${state}.json`);
        }
        return HttpResponse.json(await response.json());
    }),

    // ── page images: a VISIBLY SYNTHETIC page (⟨C3⟩) ─────────────────────
    // Not a refusal. `registry.ts`'s refuse-rather-than-invent rule governs wire
    // SHAPES; an image is content, and this shape is fully specified. Refusing
    // would make the Pile unscreenshottable and so defeat the visual gate — and
    // the fixtures cannot carry real bytes anyway, they would be named students'
    // exam scans. What comes back is seeded pseudo-handwriting stamped
    // «דוגמה סינתטית», so a screenshot review cannot pass believing it saw a
    // real scan.
    http.get(`${API}/transcriptions/:id/pages/:page/image`, ({ params }) =>
        syntheticPageResponse(seedFrom(String(params.id)))),

    // ── still pending: refuse, with the backend's reason ─────────────────
    http.get(`${API}/batches/:id/returned-exams/manifest`, () =>
        notPublished('returned-exams manifest')),
];
