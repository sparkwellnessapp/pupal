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

// ---------------------------------------------------------------------------
// Grading-flow clarity pass (§4) — the named counting helper.
//
// `countNoun` is the spec's name for the (one, many) case: a count that is
// only ever rendered for n ≥ 1, so there is no zero form to invent. It is
// DEFINED IN TERMS OF `hebrewCount` rather than beside it — a second counting
// engine in the same module would be exactly the parallel system §0.4 bans,
// and the zero branch is unreachable by construction (`n < 1` clamps to the
// singular, which is the only honest reading of "one noun").
//
// Gender lives in the FORMS, never in the helper: feminine nouns (תשובה,
// סריקה, שאלה) take אחת, masculine (מבחן, סעיף, מקום, עמוד) take אחד. Nothing
// here pluralizes by string concatenation.
// ---------------------------------------------------------------------------

export interface CountNounForms {
  one: string
  /** Called with n ≥ 2. */
  many: (n: number) => string
}

export function countNoun(n: number, forms: CountNounForms): string {
  // A non-finite count renders the SINGULAR, never «NaN מבחנים». These
  // numbers come off the wire, and one bad field should cost a wrong noun
  // agreement, not a screen that reads as broken software.
  const safe = Number.isFinite(n) ? Math.max(1, Math.round(n)) : 1
  return hebrewCount(safe, { zero: forms.one, ...forms })
}

/** «מבחן אחד» / «N מבחנים» — the flow's unit of work, as she counts it. */
export function testsCount(n: number): string {
  return countNoun(n, { one: 'מבחן אחד', many: (x) => `${x} מבחנים` })
}


/** «מקום אחד» / «N מקומות» — where the handwriting was unclear. */
export function placesCount(n: number): string {
  return countNoun(n, { one: 'מקום אחד', many: (x) => `${x} מקומות` })
}
