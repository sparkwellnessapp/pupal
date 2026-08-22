/**
 * C1/F3 — batch-status labels (spec §3.2). Latin enums never render.
 */
import { describe, expect, it } from 'vitest'

import { BATCH_STATUS_LABELS, batchStatusLabel, FLAG_REASON_LABELS } from '@/copy/batch'

describe('batchStatusLabel (§3.2)', () => {
  it('renders בתמלול while anything is still transcribing', () => {
    expect(batchStatusLabel('in_progress', { transcribing: 3 })).toBe('בתמלול')
    expect(batchStatusLabel('in_progress', { transcribing: 0, activeJobs: 1 })).toBe('בתמלול')
  })

  it('renders ממתין להחלטות when in_progress with nothing in flight', () => {
    expect(batchStatusLabel('in_progress', { transcribing: 0 })).toBe('ממתין להחלטות')
    expect(batchStatusLabel('in_progress')).toBe('ממתין להחלטות')
  })

  it('maps the terminal statuses per §3.2', () => {
    expect(batchStatusLabel('completed')).toBe('הושלם')
    expect(batchStatusLabel('partially_completed')).toBe('הושלם חלקית')
    expect(batchStatusLabel('failed')).toBe('נכשל')
    expect(batchStatusLabel('pending')).toBe('ממתין')
  })

  it('every fixed label is Hebrew (no Latin enum leaks through the map)', () => {
    for (const label of Object.values(BATCH_STATUS_LABELS)) {
      expect(label).toMatch(/[֐-׿]/)
      expect(label).not.toMatch(/[A-Za-z_]/)
    }
  })

  it('re-exports FLAG_REASON_LABELS (one home for batch copy — C1)', () => {
    expect(FLAG_REASON_LABELS.missing_answers).toBe('תשובות חסרות')
  })
})

describe('AM3 — plural-aware count builders (singulars are proposed §3.2 amendments)', () => {
  it('never renders broken noun agreement at n=1', async () => {
    const c = await import('@/copy/batch')
    expect(c.META_TESTS(1)).toBe('מבחן אחד')
    expect(c.META_TESTS(3)).toBe('3 מבחנים')
    expect(c.HEADLINE_NEEDS_EYES(1)).toBe('מבחן אחד צריך את העיניים שלך')
    expect(c.HEADLINE_CLEAN_READY(1)).toBe('מבחן אחד מוכן לאישור מרוכז')
    expect(c.HEADLINE_LAST_TRANSCRIBING(1)).toBe('כמעט שם — מבחן אחרון בתמלול')
    expect(c.HEADLINE_ALL_APPROVED(1)).toBe('סיימת — המבחן אושר')
    expect(c.ZONE_WAVE_TITLE(1)).toBe('זיהוי תלמידים — שם חדש אחד')
    expect(c.WAVE_PRIMARY(1)).toBe('צרי ושייכי תלמיד אחד')
    expect(c.GHOST_MORE_QUEUED(1)).toBe('+ אחד נוסף בתור')
    expect(c.CLEAN_PRIMARY(1)).toBe('אשרי את המבחן (1)')       // "כולם" of one is broken
    expect(c.CLEAN_PRIMARY(19)).toBe('אשרי את כולם (19)')
    expect(c.SKIP_NOTICE(1, 'סומנו לעיון')).toBe('מבחן אחד דולג — סומנו לעיון. הוא ממתין לעיון.')
    expect(c.CLEAN_ROW_META('דנה', 1, 1)).toBe('← דנה · עמוד אחד · תשובה אחת')
    expect(c.CLEAN_ROW_META('דנה', 4, 6)).toBe('← דנה · 4 עמודים · 6 תשובות')
    expect(c.LANE_SUBORDINATE(1)).toContain('מבחן אחד כבר נבדק —')
    expect(c.LANE_COMPLETED(1, 1)).toBe('ויוי בודקת את המבחנים לפי המחוון — מבחן אחד כבר נבדק, אחד בעבודה')
    expect(c.HERO_TITLE(1)).toBe('המבחן אושר')
    expect(c.HERO_DURATION(1)).toBe('מהעלאה ועד אישור אחרון — דקה אחת')
  })
})

describe('P4 upload strings (§3.2 verbatim + AM3-proposed singulars)', () => {
  it('carries the §3.2 upload block', async () => {
    const c = await import('@/copy/batch')
    expect(c.UPLOAD_NAME_LABEL).toBe('שם המקבץ')
    expect(c.UPLOAD_NAME_HINT).toBe('נוצר אוטומטית מהמחוון, הכיתה והתאריך — אפשר לשנות')
    expect(c.UPLOAD_CLASS_HINT).toBe('בחירת כיתה עוזרת לויוי לזהות תלמידים אוטומטית מתוך הרשימה')
    expect(c.UPLOAD_DROPZONE).toBe('גררי לכאן קבצי PDF או לחצי לבחירה (עד 50 קבצים)')
    expect(c.UPLOAD_DUP_CHIP).toBe('כפילות אפשרית — שם וגודל זהים')
    expect(c.UPLOAD_TRUNCATION_NOTICE).toBe('נבחרו יותר מ-50 קבצים — נכללו 50 הראשונים')
    expect(c.UPLOAD_FILE_FAILED('סריקה.pdf')).toBe('ההעלאה של סריקה.pdf נכשלה — נסי שוב')
    expect(c.UPLOAD_CLEAR_ALL).toBe('נקי הכל')                 // U2, feminine (OD5)
  })

  it('count-bearing upload builders are AM3 plural-aware', async () => {
    const c = await import('@/copy/batch')
    expect(c.UPLOAD_CTA(0)).toBe('התחלת תמלול')                // no count to claim yet
    expect(c.UPLOAD_CTA(1)).toBe('התחלת תמלול (מבחן אחד)')     // AM3 proposed
    expect(c.UPLOAD_CTA(38)).toBe('התחלת תמלול (38 מבחנים)')   // §3.2 verbatim
    expect(c.UPLOAD_SKIPPED_SUMMARY(1, 'a.pdf — קובץ ריק')).toBe('קובץ אחד לא נכלל: a.pdf — קובץ ריק')
    expect(c.UPLOAD_SKIPPED_SUMMARY(2, 'a.pdf — קובץ ריק, b.txt — לא קובץ PDF'))
      .toBe('2 קבצים לא נכללו: a.pdf — קובץ ריק, b.txt — לא קובץ PDF')
    const plural = await import('@/utils/hebrew-plural')
    expect(plural.filesCount(1)).toBe('קובץ אחד')
    expect(plural.filesCount(12)).toBe('12 קבצים')
  })
})

describe('P5 list-page strings (§3.2 + AM3-proposed singulars)', () => {
  it('carries the §3.2 list block, plural-aware', async () => {
    const c = await import('@/copy/batch')
    expect(c.LIST_TITLE).toBe('המקבצים שלי')
    expect(c.LIST_EMPTY).toBe('אין מקבצים עדיין')
    expect(c.LIST_EMPTY_CTA).toBe('צרי מקבץ ראשון')
    expect(c.LIST_ACTION_ALL_APPROVED).toBe('הכל אושר ✓')
    expect(c.LIST_ACTION_NEEDS_EYES(4)).toBe('4 דורשים עיון')       // §3.2 verbatim
    expect(c.LIST_ACTION_NEEDS_EYES(1)).toBe('מבחן אחד דורש עיון')  // AM3 proposed
    expect(c.LIST_ACTION_TRANSCRIBING(7)).toBe('7 בתמלול')
    expect(c.LIST_ACTION_TRANSCRIBING(1)).toBe('מבחן אחד בתמלול')   // AM3 proposed
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
    // Builders whose single argument is NOT a count, or whose §3.2 text is
    // ruled identical across counts, are listed here WITH their reason.
    const notCounts = new Set([
      'BATCH_FALLBACK_NAME',   // takes an id fragment
      'FAILED_TITLE',          // takes a filename
      'META_CREATED',          // takes a relative-time string
      'WAVE_UNMATCHED_PILL',   // takes a filename
      'UPLOAD_FAILURES_NOTICE', // takes string[] — covered by its own case below
      'ZONE_CLEAN_TITLE',      // §3.2: parenthesised numeral, ruled unchanged
      'ZONE_EYES_TITLE',       // §3.2: `— {n}` numeral, ruled unchanged
      'ZONE_GHOSTS_TITLE',     // §3.2: `— {n}` numeral, ruled unchanged
      'EYES_PRIMARY',          // §3.2: `({n})`, ruled defensible at 1
      'CLEAN_SHOW_ALL',        // only rendered when n > 5
      'flagReasonLabel',       // takes a reason STRING, not a count
    ])
    const checked: string[] = []
    for (const [name, fn] of Object.entries(mod)) {
      if (typeof fn !== 'function' || notCounts.has(name)) continue
      if (fn.length !== 1) continue
      let one: unknown, two: unknown
      try { one = (fn as (n: number) => unknown)(1); two = (fn as (n: number) => unknown)(2) } catch { continue }
      if (typeof one !== 'string' || typeof two !== 'string') continue
      if (!/\d|אחד|אחת/.test(one + two)) continue     // not a count-bearing string
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
