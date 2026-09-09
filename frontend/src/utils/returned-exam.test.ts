import { readFileSync } from 'node:fs'
import { join } from 'node:path'

import { describe, expect, it } from 'vitest'

import {
    APPENDIX_LINES_PER_PAGE, STAMP_FRACTION, STAMP_INSET, appendixPageCost,
    buildAppendix, formatSignedAt, formatSignedDate, isReturnedExamStale,
    pageStrip, paginateAppendix, scopeIdOf, scopeTitleOf, stampBox,
    stampPositionFromDrag, type GradedTestContract,
} from './returned-exam'

/**
 * F3's pure layer, pinned against the backend it has to agree with.
 *
 * The stamp table is not self-referential: the numbers were produced by running
 * `draw_stamp`'s own arithmetic in Python on a 595×842 A4 page, and are pasted
 * here. If the mirror drifts, this fails against the renderer rather than
 * against itself — which is the whole reason the pricing mirror is pinned the
 * same way.
 */

const A4_W = 595
const A4_H = 842

/**
 * From `returned_exam.py::draw_stamp`, run on A4 (595×842) AFTER OD-2 made the
 * stamp round: cx = 0.03·W + 0.08·W, cy = 0.03·H + 0.08·W (the disc's own
 * half-width on both axes). An EXACT mirror, asserted as one on both axes.
 *
 * The old table carried cy = 49.06 for the 2:1 ellipse the PDF used to draw,
 * and the preview deliberately diverged from it; both are retired together.
 */
const BACKEND_CORNERS = {
    tl: { cx: 65.45, cy: 72.86 },
    tr: { cx: 529.55, cy: 72.86 },
    bl: { cx: 65.45, cy: 769.14 },
    br: { cx: 529.55, cy: 769.14 },
} as const

describe('stamp geometry mirrors the PDF renderer', () => {
    it('carries the backend constants verbatim', () => {
        expect(STAMP_FRACTION).toBe(0.16)
        expect(STAMP_INSET).toBe(0.03)
    })

    it.each(Object.entries(BACKEND_CORNERS))(
        'places the %s corner exactly where draw_stamp does', (corner, expected) => {
            const box = stampBox(
                { corner: corner as 'tl', x: null, y: null, source: 'auto' }, A4_W, A4_H)
            expect(box.center.x * A4_W).toBeCloseTo(expected.cx, 6)
            expect(box.center.y * A4_H).toBeCloseTo(expected.cy, 6)
            // …and the drawn square is inset 3% from its edge, as the disc is.
            if (corner === 'tl') expect(box.top).toBeCloseTo(A4_H * 0.03, 6)
        })

    it('defaults to tl for a null position, exactly as draw_stamp does', () => {
        const box = stampBox(null, A4_W, A4_H)
        expect(box.center.x * A4_W).toBeCloseTo(BACKEND_CORNERS.tl.cx, 6)
        expect(box.center.y * A4_H).toBeCloseTo(BACKEND_CORNERS.tl.cy, 6)
    })

    it('sizes the stamp at 16% of the page WIDTH, not its height', () => {
        expect(stampBox(null, A4_W, A4_H).size).toBeCloseTo(95.2, 6)
    })

    /**
     * `draw_stamp` reads a point ONLY when `corner` is absent. A payload
     * carrying both is a corner in the PDF, so it must be a corner here too —
     * otherwise the preview and the print disagree on the same stored value.
     */
    it('honours a point only when no corner is set', () => {
        const point = stampBox(
            { corner: null, x: 0.5, y: 0.25, source: 'manual' }, A4_W, A4_H)
        expect(point.center).toEqual({ x: 0.5, y: 0.25 })

        const both = stampBox(
            { corner: 'br', x: 0.5, y: 0.25, source: 'manual' }, A4_W, A4_H)
        expect(both.center.x * A4_W).toBeCloseTo(BACKEND_CORNERS.br.cx, 6)
    })
})

describe('a drag becomes a position the backend will honour', () => {
    it('stores the normalized CENTRE, not the box corner', () => {
        const next = stampPositionFromDrag(100, 200, A4_W, A4_H)
        const size = A4_W * STAMP_FRACTION
        expect(next.x).toBeCloseTo((100 + size / 2) / A4_W, 10)
        expect(next.y).toBeCloseTo((200 + size / 2) / A4_H, 10)
        expect(next.corner).toBeNull()
    })

    /** `apply_stamp_default_to_draft` clears AUTO positions and keeps manual
     *  ones. A drag written as `auto` would be silently overwritten later. */
    it('marks the position as manual so «apply to all» cannot erase it', () => {
        expect(stampPositionFromDrag(10, 10, A4_W, A4_H).source).toBe('manual')
    })

    it('cannot be dragged off the page in any direction', () => {
        const size = A4_W * STAMP_FRACTION
        const off = stampPositionFromDrag(-500, -500, A4_W, A4_H)
        expect(off.x! * A4_W).toBeCloseTo(size / 2, 6)
        expect(off.y! * A4_H).toBeCloseTo(size / 2, 6)

        const far = stampPositionFromDrag(9999, 9999, A4_W, A4_H)
        expect(far.x! * A4_W).toBeCloseTo(A4_W - size / 2, 6)
        expect(far.y! * A4_H).toBeCloseTo(A4_H - size / 2, 6)
    })

    /** A round trip is the property that matters: what she sees after a drag
     *  must be where the value she stored puts it. */
    it('round-trips through stampBox unchanged', () => {
        const stored = stampPositionFromDrag(123, 456, A4_W, A4_H)
        const box = stampBox(stored, A4_W, A4_H)
        expect(box.center.x).toBeCloseTo(stored.x!, 10)
        expect(box.center.y).toBeCloseTo(stored.y!, 10)
    })
})

describe('scope identity', () => {
    it('builds the id the backend builds', () => {
        expect(scopeIdOf({ question_id: 'q1', sub_question_id: 'א' })).toBe('q1.א')
        expect(scopeIdOf({ question_id: 'q3', sub_question_id: null })).toBe('q3')
    })

    /** The student never sees our internal key (spec §4.3 P4 + the mockup). */
    it('titles a scope in Hebrew, never as a raw id', () => {
        expect(scopeTitleOf('q1.א')).toBe('שאלה 1, סעיף א')
        expect(scopeTitleOf('q2')).toBe('שאלה 2')
    })
})

// ── appendix-preview-matches-fixture (spec §7) ────────────────────────────
// Read IN PLACE from the published fixture: copying it here would fork ground
// truth, which is the failure the fixture seam exists to prevent.
const FIXTURE = join(
    process.cwd(), '..', 'backend', 'tests', 'fixtures', 'grade_review',
    'approved_dan_basiuk.json')
const approved = JSON.parse(readFileSync(FIXTURE, 'utf-8'))
const contract = approved.contract as GradedTestContract

describe('appendix-preview-matches-fixture', () => {
    it('renders every counted scope from the real contract', () => {
        const appendix = buildAppendix(contract, false)
        expect(appendix.scopes.map((s) => s.scopeId)).toEqual(
            ['q1.א', 'q1.ב', 'q1.ג', 'q2.א', 'q2.ב', 'q2.ג'])
        // Trailing zeros TRIMMED for display: the stamp on the same screen
        // reads «79.5», and the product must not disagree with itself.
        expect(appendix.total).toBe('79.5')
        expect(appendix.possible).toBe('100')
    })

    it('carries each scope its own points and its own feedback', () => {
        const [first] = buildAppendix(contract, false).scopes
        expect(first.title).toBe('שאלה 1, סעיף א')
        expect(first.awarded).toBe('7.5')
        expect(first.possible).toBe('8')
        expect(first.feedback.length).toBeGreaterThan(40)
    })

    it('omits the breakdown when the batch toggle is off, and shows it when on', () => {
        expect(buildAppendix(contract, false).scopes[0].criteria).toBeNull()

        const [withCriteria] = buildAppendix(contract, true).scopes
        expect(withCriteria.criteria).not.toBeNull()
        expect(withCriteria.criteria!.length).toBeGreaterThan(0)
        for (const criterion of withCriteria.criteria!) {
            expect(criterion.description).not.toBe('')
            expect(criterion.possible).not.toBe('')
        }
    })

    it('carries the summary', () => {
        expect(buildAppendix(contract, false).summary).toContain('דפוסים')
    })

    /**
     * `scopes_for_render` omits excluded-by-selection scopes ENTIRELY. Printing
     * one at 0 would tell the student they failed a question the exam told them
     * to skip — the §7 selection-scoring lesson, on the student's own copy.
     */
    it('omits a scope the selection excluded rather than printing it at zero', () => {
        const withExcluded = {
            ...contract,
            scope_outcomes: [
                ...contract.scope_outcomes,
                {
                    question_id: 'q9', sub_question_id: null, scope_kind: 'question',
                    points_possible: '20', final_points_awarded: '0',
                    counted_in_total: false, terminal_outcomes: [],
                },
            ],
        } as unknown as GradedTestContract

        const ids = buildAppendix(withExcluded, false).scopes.map((s) => s.scopeId)
        expect(ids).not.toContain('q9')
    })

    it('still lists a scope that has no feedback, with its points', () => {
        const noFeedback = {
            ...contract,
            feedback: { scopes: {}, summary: null },
        } as unknown as GradedTestContract
        const appendix = buildAppendix(noFeedback, false)
        expect(appendix.scopes).toHaveLength(6)
        expect(appendix.scopes[0].feedback).toBe('')
        expect(appendix.scopes[0].awarded).toBe('7.5')
    })
})

describe('pagination', () => {
    it('places the header on the first page only and the summary once', () => {
        const pages = paginateAppendix(buildAppendix(contract, true))
        expect(pages[0].withHeader).toBe(true)
        expect(pages.slice(1).every((p) => !p.withHeader)).toBe(true)
        expect(pages.filter((p) => p.withSummary)).toHaveLength(1)
    })

    it('never drops or duplicates a scope', () => {
        const appendix = buildAppendix(contract, true)
        const paged = paginateAppendix(appendix).flatMap((p) => p.scopes.map((s) => s.scopeId))
        expect(paged).toEqual(appendix.scopes.map((s) => s.scopeId))
    })

    /**
     * THE ONE THAT MATTERS. The appendix page is `overflow-hidden`, so content
     * the estimate under-counts is CLIPPED, not spilled — she would preview and
     * sign a page whose bottom half she never saw. The first cost model charged
     * one line per criterion and under-counted a 236-character description
     * fourfold. This asserts the budget holds on the real fixture, with the
     * breakdown ON, which is the heaviest the page ever gets.
     */
    it('never over-fills a page — the estimate must not silently clip', () => {
        for (const includeCriteria of [false, true]) {
            const appendix = buildAppendix(contract, includeCriteria)
            for (const page of paginateAppendix(appendix)) {
                expect(appendixPageCost(page, appendix.summary))
                    .toBeLessThanOrEqual(APPENDIX_LINES_PER_PAGE)
            }
        }
    })

    it('charges a long criterion description more than one line', () => {
        const long = 'א'.repeat(240)
        const heavy = (sub: string) => ({
            question_id: 'q1', sub_question_id: sub, scope_kind: 'sub_question',
            points_possible: '8', final_points_awarded: '8', counted_in_total: true,
            terminal_outcomes: Array.from({ length: 12 }, () => ({
                description: long, final_points_awarded: '1', points_possible: '1',
            })),
        })
        const withLong = {
            ...contract,
            scope_outcomes: [heavy('א'), heavy('ב')],
            feedback: { scopes: {}, summary: null },
        } as unknown as GradedTestContract

        // Two scopes of 12 × ~5 lines cannot share a page. Under the old cost
        // model (one line per criterion) they did, and the second was clipped.
        expect(paginateAppendix(buildAppendix(withLong, true)).length)
            .toBeGreaterThan(1)
    })

    /**
     * The documented consequence of never splitting a scope: one scope bigger
     * than a page has nowhere to spill, so it keeps its own page and the SHEET
     * grows. Pinned because the safety of that decision lives in
     * `AppendixPage`'s missing `overflow-hidden` — if anyone restores the clip,
     * this test is the note explaining what it would start eating.
     */
    it('gives an over-large single scope its own page rather than cutting it', () => {
        const huge = {
            ...contract,
            scope_outcomes: [{
                question_id: 'q1', sub_question_id: 'א', scope_kind: 'sub_question',
                points_possible: '8', final_points_awarded: '8', counted_in_total: true,
                terminal_outcomes: Array.from({ length: 40 }, () => ({
                    description: 'א'.repeat(240),
                    final_points_awarded: '1', points_possible: '1',
                })),
            }],
            feedback: { scopes: {}, summary: null },
        } as unknown as GradedTestContract

        const pages = paginateAppendix(buildAppendix(huge, true))
        expect(pages).toHaveLength(1)
        expect(pages[0].scopes).toHaveLength(1)
        // …and it is knowingly over budget, which is what the growing sheet is for.
        expect(appendixPageCost(pages[0], null))
            .toBeGreaterThan(APPENDIX_LINES_PER_PAGE)
    })

    it('keeps a scope whole rather than splitting it across a break', () => {
        for (const page of paginateAppendix(buildAppendix(contract, true))) {
            for (const scope of page.scopes) {
                expect(scope.feedback).toBe(
                    buildAppendix(contract, true).scopes
                        .find((s) => s.scopeId === scope.scopeId)!.feedback)
            }
        }
    })
})

describe('the page strip', () => {
    it('numbers each kind from one, so the labels read עמוד 1 / משוב 1', () => {
        const strip = pageStrip(6, 2)
        expect(strip).toHaveLength(8)
        expect(strip[0]).toEqual({ kind: 'scan', number: 1, of: 6 })
        expect(strip[6]).toEqual({ kind: 'appendix', number: 1, of: 2 })
    })
})

describe('P8 staleness', () => {
    it('is stale only when the wire says so', () => {
        expect(isReturnedExamStale('stale')).toBe(true)
        expect(isReturnedExamStale('current')).toBe(false)
    })

    /** Degrade by omission (§3.5a): an unknown value must not send her to
     *  re-sign a signature that is in fact current. */
    it('treats an unknown or absent state as not stale', () => {
        expect(isReturnedExamStale(undefined)).toBe(false)
        expect(isReturnedExamStale(null)).toBe(false)
        expect(isReturnedExamStale('something_new')).toBe(false)
    })
})

describe('signed-at is never shown as an ISO instant', () => {
    /** The visual gate caught the raw timestamp in BOTH the header and the
     *  student's own feedback page. This is the guard against its return. */
    it('formats the instant the way the mockup does', () => {
        const iso = new Date(2026, 7, 29, 20, 31).toISOString()
        expect(formatSignedAt(iso)).toBe('29.8.2026, 20:31')
        expect(formatSignedDate(iso)).toBe('29.8.2026')
    })

    it('returns null on junk so the caller omits the line', () => {
        expect(formatSignedAt('not a date')).toBeNull()
        expect(formatSignedAt(null)).toBeNull()
        expect(formatSignedDate(undefined)).toBeNull()
    })
})
