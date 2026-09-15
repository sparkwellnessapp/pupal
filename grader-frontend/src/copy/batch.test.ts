/**
 * C1/F3 — the batch-flow glossary. Latin enums never render, `מקבץ` and
 * `אצווה` never render, and every count-bearing builder is plural-aware.
 *
 * The status-label suite that used to head this file is GONE with
 * `batchStatusLabel`: the chip is derived once, in `utils/batch-stage.ts`, and
 * is covered by `batch-stage.test.ts`. Two derivations meant two test suites
 * that could both be green while the screens disagreed.
 */
import { describe, expect, it } from 'vitest'

import { FLAG_REASON_LABELS } from '@/copy/batch'

describe('the stage vocabulary (§5.1)', () => {
  it('names every chip state in Hebrew, with no enum leaking through', async () => {
    const c = await import('@/copy/batch')
    const chips = [
      c.CHIP_UPLOADING, c.CHIP_TRANSCRIBING, c.CHIP_WAITING_APPROVAL,
      c.CHIP_GRADING, c.CHIP_WAITING_SIGNATURE, c.CHIP_DONE, c.CHIP_FAILED,
    ]
    for (const chip of chips) {
      expect(chip).toMatch(/[֐-׿]/)
      expect(chip).not.toMatch(/[A-Za-z_]/)
    }
    // Every chip is distinct — a duplicate label would make two stages
    // indistinguishable on the one surface that exists to tell them apart.
    expect(new Set(chips).size).toBe(chips.length)
  })

  it('tags every step with its owner, so the alternation is visible', async () => {
    const { STEP_LABELS } = await import('@/copy/batch')
    const { BATCH_STEPS } = await import('@/utils/batch-stage')
    for (const step of BATCH_STEPS) {
      expect(STEP_LABELS[step]).toBeDefined()
      expect(['את', 'ויוי']).toContain(STEP_LABELS[step].owner)
    }
  })

  it('re-exports FLAG_REASON_LABELS (one home for batch copy — C1)', () => {
    expect(FLAG_REASON_LABELS.missing_answers).toBe('תשובות חסרות')
  })
})

describe('AM3 — plural-aware count builders', () => {
  it('never renders broken noun agreement at n=1', async () => {
    const c = await import('@/copy/batch')
    expect(c.META_TESTS(1)).toBe('מבחן אחד')
    expect(c.META_TESTS(3)).toBe('3 מבחנים')
    expect(c.ZONE_WAVE_TITLE(1)).toBe('זיהוי תלמידים — שם חדש אחד')
    expect(c.WAVE_PRIMARY(1)).toBe('צרי ושייכי תלמיד אחד')
    expect(c.GHOST_MORE_QUEUED(1)).toBe('+ אחד נוסף בתור')
    expect(c.CLEAN_PRIMARY(1)).toBe('אישור המבחן')      // «כולם» of one is broken
    expect(c.CLEAN_PRIMARY(19)).toBe('אישור 19 המבחנים')
    expect(c.SKIP_NOTICE(1, 'סומנו לבדיקה'))
      .toBe('מבחן אחד דולג — סומנו לבדיקה. הוא ממתין לבדיקה שלך.')
    expect(c.STRIP_TRANSCRIPTIONS_APPROVED(1)).toBe('התמלולים אושרו ✓ · מבחן אחד')
    expect(c.REASON_UNCLEAR_PLACES(1)).toBe('כתב יד לא ברור במקום אחד')
  })

  it('§6 n=0 — the identity zone never announces a count of nothing', async () => {
    // Caught by the n=30 fixture: the zone renders for UNMATCHED items too,
    // which produce no pills, and the header read «0 שמות חדשים» over a
    // button offering to create «0 תלמידים».
    const c = await import('@/copy/batch')
    expect(c.ZONE_WAVE_TITLE_UNMATCHED_ONLY).not.toMatch(/\d/)
    expect(c.ZONE_WAVE_SUB_UNMATCHED_ONLY).not.toMatch(/\d/)
    expect(c.REASON_UNCLEAR_PLACES(4)).toBe('כתב יד לא ברור ב4 מקומות')
  })
})

describe('§5.2 upload strings', () => {
  it('states the one-PDF-per-student rule before a file is chosen', async () => {
    const c = await import('@/copy/batch')
    expect(c.UPLOAD_SUBTITLE).toContain('קובץ אחד לכל תלמיד')
    expect(c.UPLOAD_DROPZONE(50)).toContain('קובץ אחד לכל תלמיד')
    // The cap is RENDERED from the real constraint, never typed into the text.
    expect(c.UPLOAD_DROPZONE(50)).toContain('50')
    expect(c.UPLOAD_DROPZONE(12)).toContain('12')
  })

  it('the scanning help answers the phone-photo question (OD-5)', async () => {
    const { UPLOAD_SCAN_HELP } = await import('@/copy/batch')
    expect(UPLOAD_SCAN_HELP).toHaveLength(3)
    expect(UPLOAD_SCAN_HELP.join(' ')).toContain('רק PDF')
  })

  it('carries the rest of the upload block', async () => {
    const c = await import('@/copy/batch')
    expect(c.UPLOAD_NAME_LABEL).toBe('שם המבחן')
    expect(c.UPLOAD_NAME_HINT).toBe('נוצר אוטומטית מהמחוון, הכיתה והתאריך — אפשר לשנות')
    expect(c.UPLOAD_CLASS_HINT).toBe('בחירת כיתה עוזרת לויוי לזהות תלמידים אוטומטית מתוך הרשימה')
    expect(c.UPLOAD_DUP_CHIP).toBe('כפילות אפשרית — שם וגודל זהים')
    expect(c.UPLOAD_TRUNCATION_NOTICE(50)).toBe('נבחרו יותר מ-50 קבצים — נכללו 50 הראשונים')
    expect(c.UPLOAD_FILE_FAILED('סריקה.pdf')).toBe('ההעלאה של סריקה.pdf נכשלה — נסי שוב')
    expect(c.UPLOAD_CLEAR_ALL).toBe('הסרת הכל')
    expect(c.UPLOAD_BACK).toBe('חזרה')
    expect(c.UPLOAD_RUBRIC_LINE('יסודות')).toBe('המחוון: יסודות')
  })

  it('the CTA counts TESTS, and claims nothing at n=0', async () => {
    const c = await import('@/copy/batch')
    expect(c.UPLOAD_CTA(0)).toBe('שליחה לוויוי')
    expect(c.UPLOAD_CTA(1)).toBe('שליחה לוויוי (מבחן אחד)')
    expect(c.UPLOAD_CTA(38)).toBe('שליחה לוויוי (38 מבחנים)')
    expect(c.UPLOAD_FILES_SUMMARY(1)).toBe('מבחן אחד')
    expect(c.UPLOAD_SKIPPED_SUMMARY(1, 'a.pdf — קובץ ריק')).toBe('קובץ אחד לא נכלל: a.pdf — קובץ ריק')
    expect(c.UPLOAD_SKIPPED_SUMMARY(2, 'a.pdf — קובץ ריק, b.txt — לא קובץ PDF'))
      .toBe('2 קבצים לא נכללו: a.pdf — קובץ ריק, b.txt — לא קובץ PDF')
    const plural = await import('@/utils/hebrew-plural')
    expect(plural.filesCount(1)).toBe('קובץ אחד')
    expect(plural.filesCount(12)).toBe('12 קבצים')
  })

  it('the helper line sets the whole model in one sentence', async () => {
    const { UPLOAD_CTA_HELPER } = await import('@/copy/batch')
    expect(UPLOAD_CTA_HELPER).toContain('ויוי תקרא')
    expect(UPLOAD_CTA_HELPER).toContain('בדיקת ציונים')
  })
})

describe('§5.7 list-page strings', () => {
  it('the section is «המבחנים שלי» and counts tests, not batches', async () => {
    const c = await import('@/copy/batch')
    expect(c.LIST_TITLE).toBe('המבחנים שלי')
    expect(c.BACK_ALL_BATCHES).toBe('המבחנים שלי')
    expect(c.LIST_EMPTY).toBe('אין מבחנים עדיין')
    expect(c.LIST_EMPTY_CTA).toBe('העלי מבחן ראשון')
    expect(c.LIST_ACTION_ALL_APPROVED).toBe('הכל אושר ✓')
    expect(c.LIST_ACTION_NEEDS_EYES(4)).toBe('4 דורשים מבט')
    expect(c.LIST_ACTION_NEEDS_EYES(1)).toBe('מבחן אחד דורש מבט')
    expect(c.LIST_ACTION_TRANSCRIBING(7)).toBe('7 בתמלול')
    expect(c.LIST_ACTION_TRANSCRIBING(1)).toBe('מבחן אחד בתמלול')
  })
})

/**
 * §2.3 — THE VOCABULARY GATE, as an executable claim.
 *
 * `npm run check:copy` walks the surfaces; this walks the GLOSSARY itself,
 * which is where a banned word is likeliest to be reintroduced (every batch
 * string is supposed to come from here). Both, because they fail at different
 * moments: this one fails in `npm test`, the script fails in CI on a component
 * that inlined a literal.
 */
describe('§2.3 — banned vocabulary never reaches a teacher', () => {
  it('no exported string contains the codebase words', async () => {
    const mod = await import('@/copy/batch')
    // `ניקוד` is NOT in this list: on a RUBRIC it legitimately means the point
    // allocation the teacher wrote. It is banned on the GRADING surfaces (where
    // it competed with «ציון» and also reads as vowel-pointing), and the copy
    // script is what enforces that scope.
    const banned = ['אצווה', 'מקבץ', 'דגל', 'דגלים', 'נחת ', 'נחתו ', 'מוחזר', 'החלטות']
    const offenders: string[] = []
    for (const [name, value] of Object.entries(mod)) {
      const texts: string[] = []
      if (typeof value === 'string') texts.push(value)
      else if (Array.isArray(value)) texts.push(...value.filter((v) => typeof v === 'string'))
      else if (typeof value === 'function') {
        try {
          const out = (value as (...a: unknown[]) => unknown)(2, 2, 2)
          if (typeof out === 'string') texts.push(out)
        } catch { /* a builder this probe cannot call is covered by its own case */ }
      } else if (value && typeof value === 'object') {
        texts.push(...Object.values(value).filter((v): v is string => typeof v === 'string'))
      }
      for (const text of texts) {
        for (const word of banned) {
          if (text.includes(word)) offenders.push(`${name}: ${word} — ${text}`)
        }
      }
    }
    expect(offenders).toEqual([])
  })
})

// ---------------------------------------------------------------------------
// F3 (closeout) — AM3 coverage as an ENUMERATING guard.
//
// Plural-awareness was applied builder-by-builder as surfaces were built, so
// nothing stopped the NEXT count-bearing string from silently regressing it.
// This walks every exported single-number builder and asserts n=1 differs
// from n=2 — the property AM3 actually ratified, checked by enumeration
// rather than by remembering to add a case.
// ---------------------------------------------------------------------------
describe('AM3 — every count-bearing builder is plural-aware (enumerated)', () => {
  it('n=1 output differs from n=2 for every single-count builder', async () => {
    const mod = await import('@/copy/batch')
    // Builders whose single argument is NOT a count, or whose text is ruled
    // identical across counts, are listed here WITH their reason.
    const notCounts = new Set([
      'BATCH_FALLBACK_NAME',   // takes an id fragment
      'FAILED_TITLE',          // takes a filename
      'META_CREATED',          // takes a relative-time string
      'WAVE_UNMATCHED_PILL',   // takes a filename
      'UPLOAD_FAILURES_NOTICE', // takes string[] — covered by its own case below
      'UPLOAD_RUBRIC_LINE',    // takes a rubric NAME
      'COMPLETE_MISSING_PREFIX', // takes a rendered key list
      'ZONE_CLEAN_TITLE',      // parenthesised numeral, ruled unchanged
      'ZONE_EYES_TITLE',       // parenthesised numeral, ruled unchanged
      'EYES_PRIMARY',          // `({n})`, ruled defensible at 1
      'CLEAN_SHOW_ALL',        // only rendered when the section is truncated
      'UPLOAD_DROPZONE',       // takes the file CAP, not a count of hers
      'UPLOAD_TRUNCATION_NOTICE', // same cap
      'flagReasonLabel',       // takes a reason STRING, not a count
    ])
    const checked: string[] = []
    for (const [name, fn] of Object.entries(mod)) {
      if (typeof fn !== 'function' || notCounts.has(name)) continue
      if (fn.length !== 1) continue
      let one: unknown, two: unknown
      try { one = (fn as (n: number) => unknown)(1); two = (fn as (n: number) => unknown)(2) } catch { continue }
      if (typeof one !== 'string' || typeof two !== 'string') continue
      if (!/\d|אחד|אחת|דקה/.test(one + two)) continue     // not a count-bearing string
      checked.push(name)
      expect(one, `${name} renders the SAME text at n=1 and n=2 — AM3 regression`).not.toBe(two)
    }
    expect(checked.length).toBeGreaterThan(8)          // the guard is actually walking builders
  })

  it('the multi-name upload notice is plural-aware too', async () => {
    const { UPLOAD_FAILURES_NOTICE } = await import('@/copy/batch')
    expect(UPLOAD_FAILURES_NOTICE(['a.pdf']))
      .not.toBe(UPLOAD_FAILURES_NOTICE(['a.pdf', 'b.pdf']))
    expect(UPLOAD_FAILURES_NOTICE(['a.pdf'])).toContain('קובץ אחד')
  })
})
