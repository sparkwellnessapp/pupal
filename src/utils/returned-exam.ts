import type { components } from '@/lib/api-types'
import { formatPoints } from './points-display'

/**
 * The returned exam (F3, spec §4.3) — the pure half.
 *
 * Two jobs, both of which have to agree with a PDF this code cannot see:
 * WHERE the stamp sits, and WHAT the appendix says. Everything here is a
 * mirror of `backend/app/services/returned_exam.py`, and the constants are
 * copied from it rather than re-derived, because a preview that disagrees with
 * the artefact the student receives is the one failure this surface cannot
 * have — she signs what she previewed.
 *
 * Where the mirror is EXACT it says so. Where it is an estimate (the page
 * break, which PyMuPDF decides by text fit inside a Story) it says that too,
 * loudly, so nobody later reads an approximation as a guarantee.
 */

export type StampPosition = components['schemas']['StampPosition']
export type GradedTestContract = components['schemas']['GradedTestContract']

// ── stamp geometry ────────────────────────────────────────────────────────
// EXACT mirrors of `returned_exam.py`. Do not "clean up" the magic numbers:
// they are a wire contract with a renderer in another language.

/** `_STAMP_FRACTION` — the stamp is 16% of the page WIDTH. */
export const STAMP_FRACTION = 0.16
/** `_INSET` — a corner-placed stamp sits 3% in from both edges. */
export const STAMP_INSET = 0.03
/**
 * The PDF stamp is ROUND and score-bearing since backend phase C/D (OD-2,
 * 2026-09-04): `draw_stamp` sets `h = w`, so a corner insets the disc's own
 * half-width on both axes — exactly what `stampBox` does. The preview and the
 * print now agree to the pixel on every position, corner or point.
 *
 * History, kept because the test table still names it: the PDF used to draw a
 * 2:1 ellipse and inset its half-HEIGHT (`w/4`), so a corner-placed stamp sat
 * `w/4` higher in the PDF than here. That divergence was pinned by name and is
 * now retired — if the corner arithmetic ever drifts again, the parity table in
 * `returned-exam.test.ts` (computed from `draw_stamp`) is what fails.
 */

export interface StampBox {
    /** px from the page's left edge (LTR geometry — the page is an image). */
    left: number
    top: number
    /** Side of the square the `StampSvg` is drawn into. */
    size: number
    /** Normalized centre, i.e. what would be persisted for this box. */
    center: { x: number; y: number }
}

/**
 * Where the stamp goes, in the rendered page's own pixels.
 *
 * A POINT — anything she dragged — is used verbatim, exactly as `draw_stamp`
 * does, so the case that carries her decision is pixel-exact in both renderers.
 *
 * A CORNER is exact too: `dx + w/2`, `dy + w/2` — the same arithmetic
 * `draw_stamp` runs now that its stamp is round (see the note above).
 */
export function stampBox(
    position: StampPosition | null | undefined,
    pageWidth: number,
    pageHeight: number,
): StampBox {
    const w = pageWidth * STAMP_FRACTION
    const dx = pageWidth * STAMP_INSET
    const dy = pageHeight * STAMP_INSET

    let cx: number
    let cy: number

    // A point wins over a corner — and it only counts as a point when `corner`
    // is absent, which is exactly `draw_stamp`'s own test. A payload carrying
    // both is a corner, in both renderers.
    if (position && position.corner == null && position.x != null && position.y != null) {
        cx = pageWidth * position.x
        cy = pageHeight * position.y
    } else {
        const corner = position?.corner ?? 'tl'
        cx = corner === 'tl' || corner === 'bl' ? dx + w / 2 : pageWidth - dx - w / 2
        cy = corner === 'tl' || corner === 'tr' ? dy + w / 2 : pageHeight - dy - w / 2
    }

    return {
        left: cx - w / 2,
        top: cy - w / 2,
        size: w,
        center: { x: pageWidth === 0 ? 0 : cx / pageWidth, y: pageHeight === 0 ? 0 : cy / pageHeight },
    }
}

/**
 * A drag, turned into the position the backend stores.
 *
 * `source: 'manual'` is the load-bearing field: «apply to all» clears AUTO
 * positions and must never clear one she placed herself
 * (`apply_stamp_default_to_draft`). Persisting a drag as `auto` would let a
 * later batch default silently move a stamp she put somewhere on purpose.
 *
 * The centre is clamped so the stamp cannot be dragged off the page; clamping
 * the CENTRE (not the box) keeps the stored value and the drawn box in
 * agreement, which is what makes the preview honest after a drag.
 */
export function stampPositionFromDrag(
    left: number,
    top: number,
    pageWidth: number,
    pageHeight: number,
): StampPosition {
    const w = pageWidth * STAMP_FRACTION
    const clamp = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v))
    const cx = clamp(left + w / 2, w / 2, pageWidth - w / 2)
    const cy = clamp(top + w / 2, w / 2, pageHeight - w / 2)
    return {
        corner: null,
        x: pageWidth === 0 ? 0 : cx / pageWidth,
        y: pageHeight === 0 ? 0 : cy / pageHeight,
        source: 'manual',
    }
}

// ── the appendix ──────────────────────────────────────────────────────────

export interface AppendixCriterion {
    description: string
    awarded: string
    possible: string
}

export interface AppendixScope {
    scopeId: string
    /** `שאלה 1, סעיף א` — never the raw id. */
    title: string
    awarded: string
    possible: string
    feedback: string
    /** `null` when the batch's breakdown toggle is off. */
    criteria: AppendixCriterion[] | null
}

export interface Appendix {
    scopes: AppendixScope[]
    summary: string | null
    total: string
    possible: string
}

/** `scope_id_of` — the id the teacher and the student both see. */
export function scopeIdOf(scope: { question_id: string; sub_question_id?: string | null }): string {
    return scope.sub_question_id ? `${scope.question_id}.${scope.sub_question_id}` : scope.question_id
}

/**
 * `q1.א` → `שאלה 1, סעיף א`.
 *
 * The backend prints the raw id; the mockup and spec §4.3 P4 print this. A
 * student reading «q1.א» is being shown our internal key, so the frontend
 * renders the human form and the divergence is reported.
 */
export function scopeTitleOf(scopeId: string): string {
    const [question, sub] = scopeId.split('.')
    const number = question.replace(/^q/i, '')
    return sub ? `שאלה ${number}, סעיף ${sub}` : `שאלה ${number}`
}

/**
 * The appendix content, from the CONTRACT — never from a draft.
 *
 * Mirrors `scopes_for_render`: excluded-by-selection scopes are OMITTED
 * entirely, because on a «choose k of N» the unchosen questions were never
 * owed and printing them at 0 would tell the student they failed something the
 * exam told them to skip. A scope with no feedback still appears with its
 * points — silence about a question she graded reads as an omission.
 */
export function buildAppendix(
    contract: GradedTestContract,
    includeCriteria: boolean,
): Appendix {
    const texts = new Map<string, string>()
    const feedback = contract.feedback
    for (const [key, value] of Object.entries(feedback?.scopes ?? {})) {
        texts.set(key, (value as { text: string }).text)
    }

    const scopes: AppendixScope[] = []
    for (const scope of contract.scope_outcomes ?? []) {
        if (scope.counted_in_total === false) continue
        const scopeId = scopeIdOf(scope)
        scopes.push({
            scopeId,
            title: scopeTitleOf(scopeId),
            awarded: formatPoints(String(scope.final_points_awarded)),
            possible: formatPoints(String(scope.points_possible)),
            feedback: texts.get(scopeId) ?? '',
            criteria: includeCriteria
                ? (scope.terminal_outcomes ?? []).map((t) => ({
                    description: t.description,
                    awarded: formatPoints(String(t.final_points_awarded)),
                    possible: formatPoints(String(t.points_possible)),
                }))
                : null,
        })
    }

    return {
        scopes,
        summary: feedback?.summary?.text ?? null,
        total: formatPoints(String(contract.total_score)),
        possible: formatPoints(String(contract.total_possible)),
    }
}

// ── pagination ────────────────────────────────────────────────────────────

/**
 * Lines of body text an appendix page holds, at the mockup's 13.5px/1.7 inside
 * a 46/54px margin box.
 *
 * ⚠ AN ESTIMATE, AND THE ONLY ONE IN THIS FILE. The PDF paginates by asking
 * PyMuPDF's Story whether the text fit, which depends on the embedded font's
 * real metrics; no browser-side arithmetic reproduces that. The CONTENT of
 * every page is exact — the same scopes, the same points, the same words, in
 * the same order — and only the position of the break may differ by a line.
 * That is acceptable because nothing she decides here (the breakdown toggle,
 * the stamp) depends on where the break lands, and it must never be described
 * as a guarantee.
 */
/**
 * DERIVED, not chosen: the page is 660 × 1.41 = 930.6px, less the 46px head and
 * 40px foot margins = 844.6px of content, over a 13.5px × 1.7 line = 22.95px,
 * giving 36.8. The first value here was a round 34 picked by eye, and it split
 * pages the render had room for.
 */
export const APPENDIX_LINES_PER_PAGE = 36
/** The header (title, meta, rule, total) costs the first page this much. */
const HEADER_LINES = 5
/** Content width 552px at 13.5px Hebrew ≈ 6.6px per character. */
const CHARS_PER_LINE = 84
/**
 * A criterion line is NARROWER than a feedback line — it shares its row with
 * the points column and sits inside the breakdown rail's inset — but it is also
 * set SMALLER (12px against 13.5px). Measured against the render: the
 * description column is 660 − 2×54 (page margins) − 24 (the rail's border and
 * inset) − 60 (the points column) = 468px, and at 12px that is ≈81 characters.
 *
 * The first value here was 58, chosen to be paranoid while the page still
 * clipped. It produced six near-empty sheets where the PDF makes three or four,
 * which is its own kind of lie — the header would tell her the student receives
 * six pages of feedback. Once `AppendixPage` stopped clipping (see its class
 * note), over-estimating bought nothing, so this went back to a measured value.
 */
const CRITERION_CHARS_PER_LINE = 81

function wrappedLines(text: string): number {
    if (!text) return 0
    return text.split('\n').reduce(
        (sum, line) => sum + Math.max(1, Math.ceil(line.length / CHARS_PER_LINE)), 0)
}

function scopeCost(scope: AppendixScope): number {
    // title row + feedback + every criterion at its REAL wrapped height + the
    // gap after the block. Charging one line per criterion (the first version)
    // under-counted a 236-character description by a factor of four.
    const criteria = (scope.criteria ?? []).reduce(
        (sum, criterion) => sum + Math.max(
            1, Math.ceil(criterion.description.length / CRITERION_CHARS_PER_LINE)),
        0)
    return 1 + wrappedLines(scope.feedback) + criteria + 1
}

/** What `paginateAppendix` charged a page. Exported so a test can prove no
 *  page was over-filled, which is the only thing standing between the estimate
 *  and a silently clipped sheet. */
export function appendixPageCost(page: AppendixPageContent, summary: string | null): number {
    return page.scopes.reduce((sum, scope) => sum + scopeCost(scope), 0)
        + (page.withHeader ? HEADER_LINES : 0)
        + (page.withSummary && summary ? 2 + wrappedLines(summary) : 0)
}

export interface AppendixPageContent {
    scopes: AppendixScope[]
    /** The header block only ever appears on the first appendix page. */
    withHeader: boolean
    /** The summary lands on the last page that has room for it. */
    withSummary: boolean
}

/**
 * Split the appendix into pages.
 *
 * A scope is never split across a break: the backend's Story does split
 * paragraphs, but a preview that cut a sentence at a break the PDF puts
 * elsewhere would show her a page neither renderer produces. Keeping blocks
 * whole makes the preview a truthful sample of the content even where the
 * break is approximate.
 *
 * CONSEQUENCE, stated so it is a decision and not a surprise: a SINGLE scope
 * larger than one page cannot be spilled — there is nowhere to spill it to — so
 * it stays on its own page and that page GROWS past A4. `AppendixPage` is built
 * not to clip precisely so this case loses nothing; see its class note. The
 * alternative, cutting mid-scope, would print a page neither renderer produces.
 */
export function paginateAppendix(appendix: Appendix): AppendixPageContent[] {
    const summaryCost = appendix.summary ? 2 + wrappedLines(appendix.summary) : 0
    const pages: AppendixPageContent[] = []
    let current: AppendixScope[] = []
    let used = HEADER_LINES

    for (const scope of appendix.scopes) {
        const cost = scopeCost(scope)
        if (current.length > 0 && used + cost > APPENDIX_LINES_PER_PAGE) {
            pages.push({ scopes: current, withHeader: pages.length === 0, withSummary: false })
            current = []
            used = 0
        }
        current.push(scope)
        used += cost
    }
    pages.push({ scopes: current, withHeader: pages.length === 0, withSummary: false })

    if (appendix.summary) {
        const last = pages[pages.length - 1]
        if (used + summaryCost > APPENDIX_LINES_PER_PAGE) {
            pages.push({ scopes: [], withHeader: false, withSummary: true })
        } else {
            last.withSummary = true
        }
    }

    return pages
}

// ── the page strip ────────────────────────────────────────────────────────

export interface PageStripEntry {
    kind: 'scan' | 'appendix'
    /** 1-based within its kind, which is how the strip labels it. */
    number: number
    /** Total of its kind, for `משוב 1/2`. */
    of: number
}

export function pageStrip(scanPages: number, appendixPages: number): PageStripEntry[] {
    const entries: PageStripEntry[] = []
    for (let i = 1; i <= scanPages; i += 1) {
        entries.push({ kind: 'scan', number: i, of: scanPages })
    }
    for (let i = 1; i <= appendixPages; i += 1) {
        entries.push({ kind: 'appendix', number: i, of: appendixPages })
    }
    return entries
}

/**
 * P8: the signature is stale when she edited after signing.
 *
 * Degrades by OMISSION on an unknown value (§3.5a): an unrecognised state is
 * not treated as stale, because a banner telling her to re-sign a signature
 * that is in fact current sends her to redo work that was already done.
 */
export function isReturnedExamStale(state: string | null | undefined): boolean {
    return state === 'stale'
}

// ── dates ─────────────────────────────────────────────────────────────────

/**
 * `2026-08-29T20:31:00+00:00` → `29.8.2026, 20:31`.
 *
 * The wire carries an ISO instant; a teacher must never be shown one. This
 * came back from the visual gate with the raw timestamp sitting in the header
 * AND on the student's own feedback page, which is where it would have shipped.
 *
 * Unparseable input returns null so the caller OMITS the line (§3.5a) rather
 * than printing «Invalid Date» — the same degrade-by-omission rule the rest of
 * this module follows.
 */
export function formatSignedAt(iso: string | null | undefined): string | null {
    const date = iso ? new Date(iso) : null
    if (!date || Number.isNaN(date.getTime())) return null
    const time = `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
    return `${formatSignedDate(iso)}, ${time}`
}

/** The date alone, for the appendix meta line: `29.8.2026`. */
export function formatSignedDate(iso: string | null | undefined): string | null {
    const date = iso ? new Date(iso) : null
    if (!date || Number.isNaN(date.getTime())) return null
    return `${date.getDate()}.${date.getMonth() + 1}.${date.getFullYear()}`
}
