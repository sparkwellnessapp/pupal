import { hebrewCount } from '@/utils/hebrew-plural'

/**
 * הכיתות שלי — the student profile and the roster's new strings
 * (PR_student_profile.md §7). Teacher in the feminine imperative; the student
 * gender-neutral (תלמיד/ה), because a class has both.
 *
 * Everything the profile SAYS is a discrete fact from one approved test or a
 * count (UI-1) — there is no string here for an average, a trend or a verdict,
 * and adding one is an open decision, not a convenience.
 */

// ── the count (OD-12 / M-A5) ───────────────────────────────────────────────
/** «מבחן בדוק אחד» · «N מבחנים בדוקים» · null at 0 — the badge is HIDDEN, not
 *  «0»: a zero on most cards of a new teacher is noise, and the profile's own
 *  empty state carries that message. */
export const CL_SIGNED_COUNT = (n: number): string | null =>
    n === 0 ? null : hebrewCount(n, {
        zero: '',
        one: 'מבחן בדוק אחד',
        many: (x) => `${x} מבחנים בדוקים`,
    })

// ── the profile (§6.2) ─────────────────────────────────────────────────────
export const CL_BREADCRUMB_ROOT = 'הכיתות שלי'
export const CL_BREADCRUMB_SEP = '›'
export const CL_EDIT_NAME = 'עריכת שם'
export const CL_DELETE_STUDENT = 'מחיקת תלמיד/ה'
export const CL_SIGNED_SECTION = 'מבחנים בדוקים'
/** OD-14: the moment she approved the grading — «בדיקה אושרה ב19.9.2026, 16:58». */
export const CL_APPROVED_AT = (when: string) => `בדיקה אושרה ב${when}`
/** OD-7: «85.5 מתוך 100» — the approved row's own two numbers, never a computation. */
export const CL_GRADE_OF = (possible: string) => `מתוך ${possible}`
export const CL_THUMB_ALT = (exam: string) => `עמוד 1 · ${exam}`
export const CL_EMPTY_TITLE = (name: string) => `עדיין אין מבחנים בדוקים ל${name}`
export const CL_EMPTY_BODY = 'מבחנים שתאשרי יופיעו כאן.'
export const CL_LOAD_FAILED = 'לא הצלחנו לטעון את הפרופיל — נסי לרענן'
export const CL_NOT_FOUND = 'התלמיד/ה לא נמצא/ה'
/** §5.3: the list is cut at the cap; the count above it is still the truth. */
export const CL_TRUNCATED = (shown: number, total: number) =>
    `מוצגים ${shown} מתוך ${total} המבחנים הבדוקים`

// ── the purge dialog (Part B §15; the Delete artboard) ─────────────────────
export const CL_PURGE_TITLE = (name: string) => `למחוק את ${name}?`
/** «יימחקו לצמיתות גם **3 המבחנים הבדוקים** — …»: the count is the bold span. */
export const CL_PURGE_SIGNED_LEAD = 'יימחקו לצמיתות גם '
export const CL_PURGE_SIGNED_COUNT = (n: number) =>
    n === 1 ? 'המבחן הבדוק' : `${n} המבחנים הבדוקים`
export const CL_PURGE_SIGNED_TAIL = ' — הסריקות, הבדיקות והקבצים להורדה. אי אפשר לבטל את הפעולה.'
export const CL_PURGE_DATA_ONLY = 'יימחקו לצמיתות גם הסריקות והבדיקות שטרם אושרו. אי אפשר לבטל את הפעולה.'
export const CL_PURGE_NOTHING = 'הפעולה אינה הפיכה.'
export const CL_PURGE_TYPE_NAME = 'כדי לאשר, הקלידי את השם המלא'
export const CL_PURGE_CONFIRM = 'מחיקה לצמיתות'
export const CL_PURGE_CONFIRM_PLAIN = 'מחיקה'
export const CL_PURGE_CANCEL = 'ביטול'
export const CL_PURGE_CLOSE = 'סגירה'
/** §14: 409 grading_in_progress — nothing was touched. */
export const CL_PURGE_BLOCKED = (name: string) => `ויוי עדיין בודקת מבחן של ${name}. נסי שוב בעוד רגע.`
/** 409 purge_refused — the plan could not promise a correct purge; nothing was touched. */
export const CL_PURGE_REFUSED = (name: string) => `אי אפשר למחוק את ${name} כרגע. פני אלינו ונבדוק.`
export const CL_PURGE_LOAD_FAILED = 'לא הצלחנו לבדוק מה יימחק — נסי שוב'
export const CL_PURGE_DONE = 'המחיקה הושלמה'

// ── the returned page's way back (§6.5, OD-9) ──────────────────────────────
export const CL_BACK_TO_STUDENT = (name: string) => `חזרה אל ${name}`
export const CL_BACK_TO_BATCH = 'חזרה ללוח המקבץ'
