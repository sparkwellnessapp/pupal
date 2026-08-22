/**
 * R3 — the keymap reducer (pure). RTL arrows: ArrowLeft = הבא (forward),
 * ArrowRight = הקודם. Hebrew IME composition is ignored; inside an editable
 * only Ctrl/Cmd+S and Ctrl/Cmd+Enter fire; a modal suppresses everything
 * (the F8 Modal owns its own keys).
 */
import { describe, expect, it } from 'vitest'

import { resolveKeyAction } from '@/utils/review-keymap'

const base = { key: '', ctrlOrMeta: false, isComposing: false, inEditable: false, modalOpen: false }

describe('resolveKeyAction (R3)', () => {
  it('bare keys on the page', () => {
    expect(resolveKeyAction({ ...base, key: 'ArrowLeft' })).toBe('next')
    expect(resolveKeyAction({ ...base, key: 'ArrowRight' })).toBe('prev')
    expect(resolveKeyAction({ ...base, key: 'Enter' })).toBe('approve')
    expect(resolveKeyAction({ ...base, key: 's', ctrlOrMeta: true })).toBe('save')
    expect(resolveKeyAction({ ...base, key: 'x' })).toBeNull()
  })

  it('inside an editable, ONLY Ctrl/Cmd+S and Ctrl/Cmd+Enter fire', () => {
    expect(resolveKeyAction({ ...base, inEditable: true, key: 'ArrowLeft' })).toBeNull()
    expect(resolveKeyAction({ ...base, inEditable: true, key: 'Enter' })).toBeNull()
    expect(resolveKeyAction({ ...base, inEditable: true, key: 's', ctrlOrMeta: true })).toBe('save')
    expect(resolveKeyAction({ ...base, inEditable: true, key: 'Enter', ctrlOrMeta: true })).toBe('approve')
  })

  it('Hebrew IME composition is never an action', () => {
    expect(resolveKeyAction({ ...base, key: 'Enter', isComposing: true })).toBeNull()
    expect(resolveKeyAction({ ...base, key: 's', ctrlOrMeta: true, isComposing: true })).toBeNull()
  })

  it('an open modal suppresses the page keymap entirely', () => {
    expect(resolveKeyAction({ ...base, modalOpen: true, key: 'ArrowLeft' })).toBeNull()
    expect(resolveKeyAction({ ...base, modalOpen: true, key: 'Enter' })).toBeNull()
    expect(resolveKeyAction({ ...base, modalOpen: true, key: 's', ctrlOrMeta: true })).toBeNull()
  })

  it('uppercase S (shift held) still saves', () => {
    expect(resolveKeyAction({ ...base, key: 'S', ctrlOrMeta: true })).toBe('save')
  })
})
