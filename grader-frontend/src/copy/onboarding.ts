/**
 * Onboarding copy — every user-visible string in the flow, in one module.
 *
 * The `copy/batch.ts` pattern: the executable gate (`npm run check:copy`) can
 * see strings here, and a copy change is one file rather than a hunt through
 * five step components.
 *
 * Address form is FEMININE throughout, matching the rest of the product and the
 * OD5 gate. The gender question in step 4 is collected for future address forms
 * and is NOT read by any copy today (owner ruling D4) — so nothing here branches
 * on it, and nothing here should start to without that ruling being revisited.
 */

// ── Shell ────────────────────────────────────────────────────────────────────
export const NEXT = 'הבא'
export const BACK = 'חזרה'
export const PROGRESS_LABEL = 'התקדמות בתהליך ההיכרות'
export const STEP_OF = (i: number, n: number) => `שלב ${i} מתוך ${n}`
export const SAVING = 'שומרת…'
export const GENERIC_ERROR = 'משהו השתבש. אפשר לנסות שוב.'

// ── Step 1 · welcome ─────────────────────────────────────────────────────────
export const WELCOME_TITLE =
    'ברוכה הבאה ל‑Vivi, הפלטפורמה המובילה בישראל לבדיקת מבחנים בכתב יד'
export const WELCOME_BODY = [
    'Vivi היא העוזרת האישית שלך לבדיקה. את מעלה את המחוון ואת מבחני הכיתה — Vivi מתמללת את כתב היד, בודקת מול המחוון, ומגישה הצעת ציון עם נימוק וציטוט מדויק מתוך תשובת התלמיד.',
    'ההחלטה תמיד שלך: Vivi מציעה, את מחליטה. שום ציון לא נסגר בלי שעברת עליו.',
    'מה שנשאר לך הוא מה שחשוב באמת — ללמד.',
]
export const WELCOME_CTA = 'בואי נתחיל'

// ── Step 2 · subjects ────────────────────────────────────────────────────────
export const SUBJECTS_TITLE = 'אילו מקצועות את מלמדת?'
export const SUBJECTS_SUBTITLE = 'נתאים לך את המחוונים וההמלצות למקצועות שלך.'
export const SUBJECTS_HINT = 'בחרי לפחות מקצוע אחד כדי להמשיך'
export const SUBJECTS_LOADING = 'טוען מקצועות…'
export const SUBJECTS_LOAD_ERROR = 'לא הצלחנו לטעון את רשימת המקצועות.'
export const RETRY = 'לנסות שוב'

// ── Step 3 · schools ─────────────────────────────────────────────────────────
export const SCHOOLS_TITLE = 'באילו בתי ספר את מלמדת?'
export const SCHOOLS_SUBTITLE = 'נתאים את החוויה לבית הספר שלך. אפשר לבחור יותר מאחד.'
export const SCHOOLS_PLACEHOLDER = 'התחילי להקליד שם של בית ספר או עיר…'
export const SCHOOLS_LOADING = 'טוען רשימת בתי ספר…'
export const SCHOOLS_LOAD_ERROR = 'לא הצלחנו לטעון את רשימת בתי הספר. אפשר להקליד את השם ידנית.'
export const SCHOOLS_EMPTY = 'לא מצאנו בית ספר כזה ברשימה.'
export const SCHOOLS_ADD_FREE_TEXT = (q: string) => `הוסיפי את «${q}» כפי שכתבת`
export const SCHOOLS_SKIP = 'דלגי לעת עתה'
export const SCHOOLS_REMOVE = (label: string) => `הסירי את ${label}`
export const SCHOOLS_CHOSEN = 'בתי הספר שנבחרו'
/** The cap itself lives in lib/onboarding (it mirrors the endpoint's), so this
 *  sentence cannot drift away from the number actually enforced. */
export const SCHOOLS_MAX_REACHED = (max: number) => `אפשר לבחור עד ${max} בתי ספר.`

// ── Step 4 · identity ────────────────────────────────────────────────────────
export const IDENTITY_TITLE = 'איך לפנות אלייך?'
export const IDENTITY_SUBTITLE = 'כמעט סיימנו — נשארו רק הפרטים שלך.'
export const IDENTITY_NAME_LABEL = 'שם מלא'
export const IDENTITY_NAME_PLACEHOLDER = 'מיכל כהן'
export const IDENTITY_NAME_REQUIRED = 'צריך שם מלא כדי להמשיך'
export const IDENTITY_GENDER_LABEL = 'מגדר'
export const GENDER_OPTIONS = [
    { value: 'female', label: 'אישה' },
    { value: 'male', label: 'גבר' },
    { value: 'unspecified', label: 'מעדיפ/ה לא לציין' },
] as const

// ── Step 5 · next exam [028] ────────────────────────────────────────────────
export const EXAM_TITLE = 'מתי המבחן הבא שלך?'
export const EXAM_SUBTITLE =
    'כדי שנהיה מוכנים איתך ביום שאחרי — נזכיר לך יום לפני, ונהיה זמינים אם משהו נתקע.'
export const EXAM_DATE_LABEL = 'תאריך המבחן'
/** A real button of equal visual weight, not a muted link: "I don't know yet"
 *  is an ANSWER (ONB-2), and styling it as a lesser option would push teachers
 *  into inventing a date. */
export const EXAM_UNKNOWN = 'עוד לא יודעת'
export const EXAM_PHONE_LABEL = 'טלפון (לא חובה)'
export const EXAM_PHONE_PLACEHOLDER = '050-0000000'
export const EXAM_PHONE_HELPER =
    'כדי שנוכל לעדכן בוואטסאפ לפני המבחן. לא נשלח שום דבר אחר.'
/** NO LINK on this label. The privacy page does not exist yet, and a link to a
 *  404 beside a consent checkbox is worse than no link — it promises terms a
 *  teacher cannot read. The link is added the day that page ships. */
export const EXAM_WHATSAPP_CONSENT = 'אני מאשרת קבלת הודעות מ‑Vivi בוואטסאפ'
export const EXAM_WHATSAPP_DIRECT = 'דברי איתי ישירות בוואטסאפ'
export const EXAM_WHATSAPP_PREFILL = 'היי נועם, יש לי שאלה על Vivi'
export const EXAM_BOOKING_TITLE = 'רוצה שנבדוק את המנה הראשונה ביחד?'
export const EXAM_BOOKING_BODY =
    'שיחה של 30 דקות עם נועם, המייסד. את מעלה, אנחנו עוברים על זה יחד.'
export const EXAM_BOOKING_CTA = 'לקביעת שיחה'
export const EXAM_SKIP = 'אפשר לדלג'
/** Success lines. Two, because "I don't know" earns a DIFFERENT promise — and
 *  it is a promise we keep: the 14-day digest is what asks her again. */
export const EXAM_SUCCESS_DATE = 'מעולה. נהיה בקשר לקראת המבחן.'
export const EXAM_SUCCESS_UNKNOWN = 'אין בעיה. נשאל שוב בעוד שבועיים.'
/** The persistent app-shell entry point (§8), independent of this step. */
export const BOOK_A_CALL = 'קביעת שיחה עם נועם (מייסד Vivi)'

// ── Step 6 · welcome aboard ──────────────────────────────────────────────────
export const READY_TITLE = (firstName: string) =>
    firstName ? `ברוכה הבאה על הסיפון, ${firstName}` : 'ברוכה הבאה על הסיפון'
export const READY_SUBTITLE = 'ארבעה דברים ששווה לדעת לפני שמתחילים.'
export const READY_TIPS = [
    {
        title: 'התחילי מהמחוון',
        body: 'העלי את קובץ ה‑Word של המחוון. Vivi קוראת אותו בדיוק כפי שכתבת — כולל טעויות — ומסמנת כל אי‑התאמה לפני שממשיכים.',
    },
    {
        title: 'העלי מקבץ מבחנים',
        body: 'אפשר להעלות כיתה שלמה בבת אחת. התמלול מתחיל מיד, ואת חופשית לעשות בינתיים דברים אחרים.',
    },
    {
        title: 'עברי על התמלול לפני הבדיקה',
        body: 'התמלול מוצג לצד הסריקה המקורית. מה שתאשרי — זה מה שייבדק.',
    },
    {
        title: 'הציון האחרון תמיד שלך',
        body: 'לכל ניקוד יש נימוק וציטוט מהתשובה. אפשר לשנות כל ניקוד, וההסבר מתעדכן בהתאם.',
    },
]
export const READY_CTA = 'קדימה, לעבודה'
