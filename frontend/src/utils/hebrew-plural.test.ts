import { describe, expect, it } from 'vitest'
import {
  answersCount, editedExcludedCount, hebrewCount, linesForReviewCount,
  pagesCount, untranscribedFilesCount,
} from './hebrew-plural'

describe('hebrew pluralization (the "1 תשובות" defect can never ship again)', () => {
  it('answers: 0 / 1 / 2 / many', () => {
    expect(answersCount(0)).toBe('אין תשובות')
    expect(answersCount(1)).toBe('תשובה אחת')
    expect(answersCount(2)).toBe('2 תשובות')
    expect(answersCount(35)).toBe('35 תשובות')
  })

  it('pages: 0 / 1 / many', () => {
    expect(pagesCount(0)).toBe('ללא עמודים')
    expect(pagesCount(1)).toBe('עמוד אחד')
    expect(pagesCount(3)).toBe('3 עמודים')
  })

  it('lines for review: 1 / many', () => {
    expect(linesForReviewCount(1)).toBe('שורה אחת לבדיקה')
    expect(linesForReviewCount(2)).toBe('2 שורות לבדיקה')
  })

  it('residue and excluded-count lines: 1 / many', () => {
    expect(untranscribedFilesCount(1)).toBe('קובץ אחד לא תומלל')
    expect(untranscribedFilesCount(4)).toBe('4 קבצים לא תומללו')
    expect(editedExcludedCount(1)).toBe('מבחן אחד נערך ידנית — דורש אישור פרטני')
    expect(editedExcludedCount(3)).toBe('3 מבחנים נערכו ידנית — דורשים אישור פרטני')
  })

  it('generic helper dispatches on exact count', () => {
    const forms = { zero: 'z', one: 'o', many: (n: number) => `m${n}` }
    expect(hebrewCount(0, forms)).toBe('z')
    expect(hebrewCount(1, forms)).toBe('o')
    expect(hebrewCount(7, forms)).toBe('m7')
  })
})
