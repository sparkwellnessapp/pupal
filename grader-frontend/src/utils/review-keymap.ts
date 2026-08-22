/**
 * R3 — the review keymap as a PURE reducer (zero-mock-tested). The page owns
 * exactly one window keydown listener and asks this function what the key
 * means; the F8 Modal suppresses background keys at capture phase, and this
 * reducer additionally returns null whenever a modal is open (belt+braces).
 *
 * RTL: ArrowLeft = הבא (forward), ArrowRight = הקודם. Hebrew IME composition
 * (`isComposing`) never acts. Inside an editable, only Ctrl/Cmd+S (save) and
 * Ctrl/Cmd+Enter (approve) fire.
 */

export type ReviewKeyAction = 'next' | 'prev' | 'approve' | 'save'

export interface KeyInput {
  key: string
  ctrlOrMeta: boolean
  isComposing: boolean
  inEditable: boolean
  modalOpen: boolean
}

export function resolveKeyAction(input: KeyInput): ReviewKeyAction | null {
  if (input.isComposing || input.modalOpen) return null

  const lower = input.key.toLowerCase()
  if (input.inEditable) {
    if (input.ctrlOrMeta && lower === 's') return 'save'
    if (input.ctrlOrMeta && input.key === 'Enter') return 'approve'
    return null
  }

  if (input.ctrlOrMeta && lower === 's') return 'save'
  switch (input.key) {
    case 'ArrowLeft':
      return 'next'
    case 'ArrowRight':
      return 'prev'
    case 'Enter':
      return 'approve'
    default:
      return null
  }
}
