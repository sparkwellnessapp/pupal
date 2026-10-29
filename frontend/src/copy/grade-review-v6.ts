/**
 * בדיקת ציונים, grader-v6 — the strings the v6 review ADDS (owner rulings
 * 2026-10-17 §7). Everything the v6 surface shares with v5 — the top bar, the
 * bottom bar, the save states, the approval blockers, the answer pane — is
 * imported from `copy/grade-review.ts` and never restated here (§0.4).
 *
 * Rules this file is held to (the same as its sibling's):
 *  - feminine imperatives — she is the reader (בחרי, קבעי)
 *  - the student is addressed neutrally (תלמיד/ה)
 *  - no machine vocabulary: no ids, no «מודל», no «אפשרות» for a plan option —
 *    a teacher chooses what fits the answer, she does not pick "options"
 *  - calm: a deduction is stated, never alarmed about
 */

import type { Chip } from '@/lib/pricing-v6'

// ── the criterion row ─────────────────────────────────────────────────────
/** The chip beside a criterion's grade (`PricedTerminal.chip`). */
export const V6_CHIP: Readonly<Record<Chip, string>> = {
    full: 'מלא',
    partial: 'חלקי',
    zero: 'ללא נקודות',
}

/** Her edit is saved and the server is composing the line that describes it. */
export const V6_LINE_UPDATING = 'ההסבר מתעדכן…'

/** She set this criterion's grade by hand (`overlay.terminal_points`). */
export const V6_MANUAL_GRADE = 'הציון נקבע ידנית'
export const V6_MANUAL_CLEAR = 'חזרה לציון לפי הבדיקות'

/** The evidence a check was credited on (inside an opened row). */
export const V6_QUOTE_PREFIX = 'מהתשובה:'
/**
 * [owner 2026-10-21] The button on EVERY criterion: lights all of the criterion's
 * verified quotes in the answer and scrolls the answer to the first. Disabled,
 * with the reason as its title, when there is nothing to light.
 */
export const V6_QUOTE_BUTTON = 'ציטוט מהתשובה'
export const V6_QUOTE_TITLE = 'הדגשת הציטוטים של הקריטריון בתשובה'
export const V6_QUOTE_NONE = 'אין לקריטריון הזה ציטוט מהתשובה להדגשה'

/** «2 בדיקות מחכות לבחירה שלך» — on a closed row, so she knows to open it. */
export const V6_WAITING = (n: number) =>
    n === 1 ? 'בדיקה אחת מחכה לבחירה שלך' : `${n} בדיקות מחכות לבחירה שלך`

// ── one check, opened ─────────────────────────────────────────────────────
export const V6_VIVI_TAG = 'הצעת ויוי'
export const V6_HER_TAG = 'הבחירה שלך'
export const V6_BACK_TO_VIVI = 'חזרה להצעת ויוי'
/** [OD-4] No answer came back for this check — an empty amber ring. */
export const V6_UNDECIDED = 'ויוי לא קבעה את הבדיקה הזו — בחרי מה מתאים לתשובה'
/**
 * Vivi proposed credit, but the words she cited are not in the answer, so the
 * credit was not given (AM-G2). Her own choice is never held back this way.
 */
export const V6_GATED =
    'ויוי הציעה זיכוי אך לא מצאה לו ציטוט בתשובה, ולכן הוא לא ניתן — בחרי בעצמך אם מגיע'
export const V6_FAULT_TAG = 'הורדה'
export const V6_NOTE_PREFIX = 'הערה:'

// her note on a criterion — written FOR the student: it is printed under the
// question's feedback on the signed exam, and the copy says so
export const V6_COMMENT_ADD = 'הוספת הערה לתלמיד/ה'
export const V6_COMMENT_EDIT = 'עריכה'
export const V6_COMMENT_PLACEHOLDER = 'הערה לתלמיד/ה — תופיע במשוב על השאלה'
export const V6_COMMENT_SAVE = 'שמירה'
export const V6_COMMENT_CANCEL = 'ביטול'
export const V6_COMMENT_REMOVE = 'מחיקה'
export const V6_COMMENT_MINE = 'הערה לתלמיד/ה:'

// ── the student's feedback ────────────────────────────────────────────────
/** Vivi is rewriting it because a decision of hers made it out of date. */
export const V6_FB_UPDATING = 'ויוי מעדכנת את המשוב לפי השינויים שלך…'
/** Vivi tried and could not — an admission, never an accusation of the student. */
export const V6_FB_FAILED = 'ויוי לא הצליחה לכתוב משוב לשאלה הזו'
export const V6_FB_NOT_WRITTEN = 'לא נכתב משוב לשאלה הזו'
export const V6_FB_SUMMARY_FAILED = 'ויוי לא הצליחה לכתוב סיכום'
export const V6_FB_SUMMARY_NOT_WRITTEN = 'לא נכתב סיכום'
/** She emptied it: nothing goes out, by her choice. */
export const V6_FB_BLANK = 'לא יישלח משוב על השאלה הזו'
export const V6_FB_SUMMARY_BLANK = 'לא יישלח סיכום'
export const V6_FB_WRITE = 'כתבי משוב'
export const V6_FB_RETRY = 'נסי שוב'
export const V6_FB_ASK_VIVI = 'בקשי נוסח מויוי'
/** Beside the approve button — information, never a block. */
export const V6_FB_MISSING = (n: number) =>
    n === 1 ? 'שאלה אחת בלי משוב' : `${n} שאלות בלי משוב`
/** She pressed approve while feedback was out of date: Vivi updated it first, for her to read. */
export const V6_FB_UPDATED_BEFORE_SIGN =
    'ויוי עדכנה את המשוב לפי השינויים שלך — עברי עליו ואשרי שוב'
export const V6_FB_REWRITE_FAILED = 'עדכון המשוב לא הצליח. אפשר לנסות שוב מהכרטיס.'

// ── how a deduction was charged (the pricer's charge statuses) ────────────
export const V6_CHARGE_APPLIED = (amount: string) => `הורדה של ${amount}`
/** BehaviorCap (AM-G13): the deductions on one requirement never cost more than it earned. */
export const V6_CHARGE_CAPPED = (charged: string, amount: string) =>
    `הורדה מוגבלת: ${charged} במקום ${amount} — ההורדות על אותה דרישה אינן עולות על מה שנצבר עליה`
/** ChargedOnce (AM-G13): another member of the same group carried the charge. */
export const V6_CHARGE_SUPERSEDED = 'לא נוכה כאן — אותה טעות נוכתה פעם אחת בלבד, בקריטריון אחר'
export const V6_CHARGE_FLOORED = (charged: string, amount: string) =>
    `הורדה חלקית: ${charged} במקום ${amount} — הציון לא יורד מתחת ל-0`
export const V6_CHARGE_INACTIVE = 'לא נוכה — הדרישה שהטעות נוגעת אליה לא התקיימה'
/**
 * [AM-G15] The group's one charge landed HERE because she set the OTHER
 * criterion's grade by hand — named by her own words, never by an id.
 */
export const V6_CHARGE_MOVED = (otherCriterion: string) =>
    `הטעות החוזרת נוכתה כאן, כי קבעת ידנית את הציון של «${otherCriterion}»`

// ── approval ──────────────────────────────────────────────────────────────
/** An `llm_failure` she has not yet resolved — named by the question's title. */
export const V6_BLOCK_FAILED = (scopeTitle: string) =>
    `הבדיקה האוטומטית נכשלה ב${scopeTitle} — קבעי בעצמך את כל הבדיקות שבה כדי לאשר`
