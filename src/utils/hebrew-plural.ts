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

/** «אין קבצים» / «קובץ אחד» / «N קבצים» (P4 upload aggregate, AM3). */
export function filesCount(n: number): string {
  return hebrewCount(n, {
    zero: 'אין קבצים',
    one: 'קובץ אחד',
    many: (x) => `${x} קבצים`,
  })
}

/** «שאלה אחת» / «N שאלות» (P5/S1 rubric card). */
export function questionsCount(n: number): string {
  return hebrewCount(n, {
    zero: 'ללא שאלות',
    one: 'שאלה אחת',
    many: (x) => `${x} שאלות`,
  })
}

/** «נקודה אחת» / «N נקודות» (P5/S1 rubric card). */
export function pointsCount(n: number): string {
  return hebrewCount(n, {
    zero: 'ללא נקודות',
    one: 'נקודה אחת',
    many: (x) => `${x} נקודות`,
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
