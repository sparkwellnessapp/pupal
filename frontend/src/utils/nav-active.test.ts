import { describe, expect, it } from 'vitest'

import { isNavActive } from './nav-active'

/**
 * P5/L2 — the sidebar's active-state rule. Strict equality (`pathname ===
 * href`) was fine while every nav target was a leaf, but `/batches` owns a
 * SECTION: the entry must stay lit on `/batches/{id}` and on the review
 * route, or it goes dark exactly when the teacher is deepest inside it.
 * `/` is special-cased — a prefix match would light Home on every page.
 */

describe('isNavActive', () => {
  it('exact match lights the entry', () => {
    expect(isNavActive('/batches', '/batches')).toBe(true)
    expect(isNavActive('/my-rubrics', '/my-rubrics')).toBe(true)
  })

  it('a section entry stays lit on its descendants', () => {
    expect(isNavActive('/batches', '/batches/b-123')).toBe(true)
    expect(isNavActive('/batches', '/batches/b-123/review/t-9')).toBe(true)
  })

  it('Home is EXACT — a prefix rule would light it everywhere', () => {
    expect(isNavActive('/', '/')).toBe(true)
    expect(isNavActive('/', '/batches')).toBe(false)
    expect(isNavActive('/', '/my-rubrics/x')).toBe(false)
  })

  it('sibling routes that merely share a prefix STRING do not light it', () => {
    // '/batches-archive' starts with '/batches' as a string but is a different
    // section — the boundary must be a path separator, not a character.
    expect(isNavActive('/batches', '/batches-archive')).toBe(false)
    expect(isNavActive('/my-rubrics', '/my-rubrics-old/3')).toBe(false)
  })

  it('unrelated routes are dark', () => {
    expect(isNavActive('/batches', '/my-classroom')).toBe(false)
  })

  it('a trailing slash on the pathname does not unlight the entry', () => {
    expect(isNavActive('/batches', '/batches/')).toBe(true)
  })
})
