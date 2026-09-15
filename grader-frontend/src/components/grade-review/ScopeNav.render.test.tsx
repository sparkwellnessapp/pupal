/**
 * §5.5 — the question rail: the amber dot's legend, and the deduction beside
 * each pair. SSR markup (house pattern: renderToStaticMarkup, no DOM).
 *
 * The rail is where «where did he lose points» gets answered, and both of the
 * claims below were wrong in the first implementation:
 *
 *   * the legend must describe what the dot ACTUALLY marks — six deterministic
 *     verification markers, not confidence — because it appears beside
 *     full-marks questions and a «less sure» legend makes that look like a bug
 *     instead of the invented-credit case the markers exist for;
 *   * an EXCLUDED scope has no points to lose. On a «choose 4 of 6» the two
 *     unchosen questions read 0/25, and a bare subtraction stamped «−25» on
 *     each — a 50-point deduction, in red, on work the exam never asked for.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { ScopeNav } from '@/components/grade-review/ReviewChrome'
import { RV_NAV_LEGEND } from '@/copy/grade-review'
import type { ReviewScope } from '@/utils/grade-review-model'

function scope(over: Partial<ReviewScope> = {}): ReviewScope {
    return {
        scopeId: 'q1',
        title: 'שאלה 1',
        questionText: null,
        answer: { kind: 'own', text: 'x' },
        possible: '10',
        awarded: '10',
        overridden: false,
        gradedBy: 'llm',
        criteria: [],
        feedback: { text: '', state: 'absent' },
        markerCount: 0,
        ...over,
    } as ReviewScope
}

const render = (scopes: ReviewScope[], markers: Record<string, number> = {}) =>
    renderToStaticMarkup(
        <ScopeNav
            scopes={scopes}
            markersByScope={markers}
            activeScopeId={null}
            onJump={() => {}}
        />,
    )

describe('the legend', () => {
    it('renders only when a dot exists — a key to an absent symbol is furniture', () => {
        expect(render([scope()])).not.toContain(RV_NAV_LEGEND)
        expect(render([scope()], { q1: 2 })).toContain(RV_NAV_LEGEND)
    })

    it('describes VERIFICATION, never confidence', () => {
        const html = render([scope()], { q1: 1 })
        expect(html).toContain('לאמת')
        // «ויוי פחות בטוחה» would be a claim about a number this surface does
        // not have — the product never renders a confidence score (OD5).
        expect(html).not.toContain('בטוחה')
    })
})

describe('the deduction', () => {
    it('shows what was lost, in the pricer’s own precision', () => {
        const html = render([scope({ possible: '8', awarded: '7.5' })])
        expect(html).toContain('−0.5')
    })

    it('is ABSENT when nothing was lost', () => {
        expect(render([scope({ possible: '8', awarded: '8' })]))
            .not.toContain('data-nav-deduction')
    })

    it('is ABSENT on an EXCLUDED scope — it was never owed', () => {
        const html = render([scope({
            possible: '25', awarded: '0', gradedBy: 'excluded_by_selection',
        })])
        expect(html).not.toContain('data-nav-deduction')
        expect(html).not.toContain('−25')
        // …and the pair itself still renders, so the rail still adds up.
        expect(html).toContain('0/25')
    })

    it('a skipped-no-answer scope DOES show its loss — that one is real', () => {
        const html = render([scope({
            possible: '25', awarded: '0', gradedBy: 'skipped_no_answer',
        })])
        expect(html).toContain('−25')
    })
})
