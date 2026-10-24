import { describe, expect, it } from 'vitest'

import { ADD_CONCURRENCY, addStudentsToClass } from './class-membership'

describe('addStudentsToClass — the one bounded add-all', () => {
  it('adds every id, never more than ADD_CONCURRENCY at once, and counts failures', async () => {
    let inFlight = 0
    let peak = 0
    const seen: string[] = []
    const add = async (classId: string, id: string) => {
      inFlight += 1
      peak = Math.max(peak, inFlight)
      await new Promise((r) => setTimeout(r, 1))
      inFlight -= 1
      seen.push(`${classId}:${id}`)
      if (id === 's3' || id === 's7') throw new Error('409')
    }
    const ids = Array.from({ length: 10 }, (_, i) => `s${i}`)
    const { failed } = await addStudentsToClass('c1', ids, add)
    expect(failed).toBe(2)
    expect(seen.sort()).toEqual(ids.map((id) => `c1:${id}`).sort())
    expect(peak).toBeLessThanOrEqual(ADD_CONCURRENCY)
  })

  it('does nothing for an empty list', async () => {
    expect(await addStudentsToClass('c1', [], async () => { throw new Error('never') }))
      .toEqual({ failed: 0 })
  })
})
