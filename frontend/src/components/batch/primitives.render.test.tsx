/**
 * F8 primitives — SSR render tests (house pattern: renderToStaticMarkup,
 * no DOM). Behavior (Esc/trap/reduced-motion) is Playwright's job; these pin
 * markup structure, token classes, and a11y attributes.
 */
import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { Modal } from '@/components/batch/Modal'
import { SegmentBar } from '@/components/batch/SegmentBar'
import { StatusChip } from '@/components/batch/StatusChip'
import { ZoneCard } from '@/components/batch/ZoneCard'

describe('StatusChip', () => {
  it('renders the hue token classes', () => {
    const html = renderToStaticMarkup(<StatusChip hue="amber">תשובות חסרות</StatusChip>)
    expect(html).toContain('bg-batch-amber-soft')
    expect(html).toContain('text-batch-amber-ink')
    expect(html).toContain('תשובות חסרות')
  })
})

describe('SegmentBar', () => {
  it('renders proportional segments with data-kind + counted legend', () => {
    const html = renderToStaticMarkup(
      <SegmentBar
        segments={[
          { kind: 'approved', count: 1 },
          { kind: 'eyes', count: 2 },
          { kind: 'moving', count: 1 },
        ]}
      />,
    )
    expect(html).toContain('data-kind="approved"')
    expect(html).toContain('data-kind="eyes"')
    expect(html).toContain('width:25%')
    expect(html).toContain('width:50%')
    // Legend labels come from C1
    expect(html).toContain('אושרו')
    expect(html).toContain('דורשים עיון')
    expect(html).toContain('בתמלול')
    // Shimmer is motion-safe only (reduced-motion kills it)
    expect(html).toContain('motion-safe:animate-shimmer')
  })

  it('renders nothing at total 0 (no slivers of nothing)', () => {
    expect(renderToStaticMarkup(<SegmentBar segments={[]} />)).toBe('')
  })

  it('compact mode drops the legend', () => {
    const html = renderToStaticMarkup(
      <SegmentBar segments={[{ kind: 'clean', count: 3 }]} legend={false} compact />,
    )
    expect(html).toContain('data-kind="clean"')
    expect(html).not.toContain('נקיים')
  })
})

describe('ZoneCard', () => {
  it('renders dot, title, sub, and actions', () => {
    const html = renderToStaticMarkup(
      <ZoneCard
        dotClass="bg-batch-seg-eyes"
        title="דורשים עיון — 8"
        sub="ויוי מסמנת בדיוק למה."
        actions={<button>התחילי סבב עיון (8)</button>}
        testId="zone-eyes"
      >
        <div>rows</div>
      </ZoneCard>,
    )
    expect(html).toContain('data-testid="zone-eyes"')
    expect(html).toContain('דורשים עיון — 8')
    expect(html).toContain('ויוי מסמנת בדיוק למה.')
    expect(html).toContain('התחילי סבב עיון (8)')
    expect(html).toContain('bg-batch-seg-eyes')
  })
})

describe('Modal', () => {
  it('renders role=dialog + aria-modal when open, nothing when closed', () => {
    const open = renderToStaticMarkup(
      <Modal open onClose={() => {}} labelledBy="t1" testId="m1">
        <h2 id="t1">כותרת</h2>
      </Modal>,
    )
    expect(open).toContain('role="dialog"')
    expect(open).toContain('aria-modal="true"')
    expect(open).toContain('aria-labelledby="t1"')

    expect(
      renderToStaticMarkup(
        <Modal open={false} onClose={() => {}}>
          x
        </Modal>,
      ),
    ).toBe('')
  })

  // The onboarding flow added `dismissible` and `size`. Both default to the
  // ORIGINAL behaviour so the three pre-existing callers are untouched — these
  // pin that, because a default that drifts silently rewrites three dialogs
  // nobody thought they were editing.
  it('defaults to the md panel width', () => {
    const html = renderToStaticMarkup(
      <Modal open onClose={() => {}}>
        x
      </Modal>,
    )
    expect(html).toContain('max-w-md')
    expect(html).not.toContain('max-w-2xl')
  })

  it('widens only when asked', () => {
    const html = renderToStaticMarkup(
      <Modal open onClose={() => {}} size="lg">
        x
      </Modal>,
    )
    expect(html).toContain('max-w-2xl')
    expect(html).not.toContain('max-w-md')
  })
})
