/**
 * Hebrew count phrases for the batch-review surface (plan §7 copy table).
 * One helper, specific phrase builders — so "1 תשובות" can never ship again.
 * Nominal, gender-neutral forms throughout.
 */

export interface HebrewCountForms {
  zero: string
  one: string
  /** Called with n ≥ 2. */
  many: (n: number) => string
}

export function hebrewCount(n: number, forms: HebrewCountForms): string {
  if (n === 0) return forms.zero
  if (n === 1) return forms.one
  return forms.many(n)
}

/** «אין תשובות» / «תשובה אחת» / «N תשובות» */
export function answersCount(n: number): string {
  return hebrewCount(n, {
    zero: 'אין תשובות',
    one: 'תשובה אחת',
    many: (x) => `${x} תשובות`,
  })
}

/** «ללא עמודים» / «עמוד אחד» / «N עמודים» */
export function pagesCount(n: number): string {
  return hebrewCount(n, {
    zero: 'ללא עמודים',
    one: 'עמוד אחד',
    many: (x) => `${x} עמודים`,
  })
}

/** «שורה אחת לבדיקה» / «N שורות לבדיקה» (never called with 0 — the header
 *  renders only when flags exist). */
export function linesForReviewCount(n: number): string {
  return hebrewCount(n, {
    zero: '',
    one: 'שורה אחת לבדיקה',
    many: (x) => `${x} שורות לבדיקה`,
  })
}

/** «N תשובות ברמת ביטחון נמוכה» (accept-modal warning). */
export function lowConfidenceCount(n: number): string {
  return hebrewCount(n, {
    zero: '',
    one: 'תשובה אחת ברמת ביטחון נמוכה',
    many: (x) => `${x} תשובות ברמת ביטחון נמוכה`,
  })
}

/** Δ15 residue line: «קובץ אחד לא תומלל» / «N קבצים לא תומללו». */
export function untranscribedFilesCount(n: number): string {
  return hebrewCount(n, {
    zero: '',
    one: 'קובץ אחד לא תומלל',
    many: (x) => `${x} קבצים לא תומללו`,
  })
}

/** Δ1 excluded-from-bulk line: teacher-touched items need individual accept. */
export function editedExcludedCount(n: number): string {
  return hebrewCount(n, {
    zero: '',
    one: 'מבחן אחד נערך ידנית — דורש אישור פרטני',
    many: (x) => `${x} מבחנים נערכו ידנית — דורשים אישור פרטני`,
  })
}
