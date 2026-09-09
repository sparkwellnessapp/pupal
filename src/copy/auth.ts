/**
 * Auth copy — sign-in, sign-up and email verification, in one module.
 *
 * Same discipline as `copy/batch.ts` and `copy/onboarding.ts`: the words a
 * teacher reads on the most consequential screen in the product are edited far
 * more often than the code around them, and the executable copy gate can only
 * see strings it can find.
 *
 * Feminine address throughout, matching the rest of the app.
 */

// ── Sign in with Google ──────────────────────────────────────────────────────
export const GOOGLE_DIVIDER = 'או'
export const GOOGLE_UNAVAILABLE = 'ההתחברות עם Google אינה זמינה כרגע. אפשר להמשיך עם מייל וסיסמה.'
/** The 409 from the nOAuth guard — the one Google failure with a real next step. */
export const GOOGLE_NEEDS_VERIFY =
    'כבר קיים חשבון עם הכתובת הזאת שעדיין לא אומת. נאמת אותו במייל ואז אפשר לחבר את Google.'

// ── Email verification ───────────────────────────────────────────────────────
export const VERIFY_TITLE = 'שלחנו לך קוד'
export const VERIFY_SUBTITLE = (email: string) =>
    `הזיני את הקוד בן שש הספרות ששלחנו אל ${email}.`
export const VERIFY_CODE_LABEL = 'קוד אימות'
export const VERIFY_CTA = 'אימות והמשך'
export const VERIFY_CHECKING = 'בודקת…'
export const VERIFY_WRONG_CODE = 'הקוד שגוי או שפג תוקפו.'
export const VERIFY_TOO_MANY = 'יותר מדי ניסיונות. אפשר לבקש קוד חדש.'
export const VERIFY_EXPIRED_HINT = 'הקוד תקף לעשר דקות.'

export const RESEND_CTA = 'שליחת קוד חדש'
export const RESEND_SENT = 'שלחנו קוד חדש.'
export const RESEND_WAIT = (seconds: number) => `אפשר לבקש קוד חדש בעוד ${seconds} שניות`
export const RESEND_FAILED = 'לא הצלחנו לשלוח קוד חדש. אפשר לנסות שוב.'

export const VERIFY_WRONG_ADDRESS = 'טעות בכתובת?'
export const VERIFY_START_OVER = 'להתחיל מחדש'

// ── Login ────────────────────────────────────────────────────────────────────
/** The 403 an unverified account gets: her password was RIGHT, so this must not
 *  read like a failed sign-in. */
export const LOGIN_NEEDS_VERIFY = 'החשבון עדיין לא אומת. נשלים את האימות עכשיו.'
export const LOGIN_GENERIC_ERROR = 'שגיאה בהתחברות'

// ── Signup ───────────────────────────────────────────────────────────────────
export const SIGNUP_SENDING = 'שולחת קוד…'
export const SIGNUP_GENERIC_ERROR = 'שגיאה ביצירת החשבון'
