import { hebrewCount } from '@/utils/hebrew-plural'

/**
 * The grade-review module's copy (PR spec §6) — the single home for every
 * Hebrew string on בדיקת ציונים. Components render Hebrew ONLY through this
 * module and tests import from here, so assertions track one source.
 *
 * Rules this file is held to (`npm run check:copy` blocks on them here):
 *  - feminine imperatives throughout — she is the reader (ודאי, אשרי, נסי)
 *  - the student is addressed neutrally (תלמיד/ה), because a class has both
 *  - every count-bearing builder is PLURAL-AWARE: "1 מבחנים" must never ship
 *  - no raw enum ever reaches a screen
 *  - the four product terms are never paraphrased: תמלול · אישור תמלול ·
 *    בדיקת ציונים · המבחן המוחזר
 */

// ── R1 · top bar ──────────────────────────────────────────────────────────
export const RV_TOTAL_PROPOSAL = (possible: string) => `מתוך ${possible} · הצעת ויוי`
export const RV_TOTAL_MINE = (possible: string) => `מתוך ${possible} · אחרי השינויים שלך`
export const RV_NAV_PREV = 'הקודם'
export const RV_NAV_NEXT = 'הבא'
export const RV_MINI_THUMB_TITLE = 'המבחן המוחזר'

/** «כיתה · מס׳ 12 · מבחן 7 מתוך 30 · נחת לפני 6 דקות» */
export const RV_IDENTITY_META = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(' · ')
export const RV_TEST_POSITION = (index: number, total: number) =>
    `מבחן ${index} מתוך ${total}`
export const RV_LANDED_AGO = (relative: string) => `נחת ${relative}`
export const RV_STUDENT_NUMBER = (n: string) => `מס׳ ${n}`

// ── §2 · revision affordances, kept reachable from the top bar's overflow ──
export const RV_MORE_ACTIONS = 'פעולות נוספות'
export const RV_REGRADE = 'ניקוד מחדש'
export const RV_REGRADE_HINT = 'ויוי תנקד מחדש לפי המחוון העדכני'
export const RV_MANUAL_EDIT = 'עריכה מחדש'
export const RV_MANUAL_EDIT_HINT = 'פתיחת בדיקה שכבר אושרה לעריכה'
export const RV_RETRY = 'ניסיון ניקוד נוסף'
export const RV_RETRY_HINT = 'הניקוד נכשל — שליחה לניקוד חוזר'
export const RV_REVISION_STARTED = 'נשלח לניקוד מחדש'
/** A revision lands as a PENDING row — there is no draft to review yet. */
export const RV_GRADING_IN_PROGRESS = 'ויוי מנקדת את המבחן — הבדיקה תיפתח כאן ברגע שתסתיים'
export const RV_GRADING_FAILED = 'הניקוד נכשל'
export const RV_APPROVED_READONLY =
    'המבחן אושר ונחתם. לעריכה נוספת השתמשי ב"עריכה מחדש" בתפריט הפעולות.'

// ── R11 · a regeneration that would overwrite her words is OFFERED ──
export const RV_FB_OFFERED_TITLE = 'ויוי כתבה נוסח חדש לפי הניקוד הנוכחי'
export const RV_FB_OFFERED_KEEP = 'שמירה על הנוסח שלי'
export const RV_FB_OFFERED_USE = 'שימוש בנוסח של ויוי'

// ── R2 · queue line ───────────────────────────────────────────────────────
export const RV_QUEUE_NEXT = (name: string) => `הבא בתור: ${name}`
export const RV_QUEUE_GRADING = (name: string, eta: string | null) =>
    eta ? `אחריו ${name} (מנוקד עכשיו, ${eta})` : `אחריו ${name} (מנוקד עכשיו)`
export const RV_QUEUE_UNLANDED = (n: number) =>
    hebrewCount(n, {
        zero: '',
        one: 'מבחן אחד טרם נחת — הבא מדלג עליו וחוזר אליו',
        many: (x) => `${x} מבחנים טרם נחתו — הבא מדלג עליהם וחוזר אליהם`,
    })
export const RV_QUEUE_SEP = ' · '

// ── R3 · scope nav ────────────────────────────────────────────────────────
export const RV_NAV_HEADING = 'שאלות'

// ── R4 · scope section ────────────────────────────────────────────────────
export const RV_QUESTION_TOGGLE = 'השאלה'
export const RV_ANSWER_LABEL = 'תשובת התלמיד/ה · מתוך התמלול המאושר'
export const RV_SHOW_SCAN = 'הצגת הסריקה'
/** R4 · the scan viewer — the pages the transcription attributed the answer to. */
export const RV_SCAN_TITLE = (scopeTitle: string) => `הסריקה · ${scopeTitle}`
export const RV_SCAN_PAGE = (n: number) => `עמוד ${n}`
export const RV_SCAN_CLOSE = 'סגירה'
export const RV_SCAN_LOADING = 'טוענת את הסריקה…'
export const RV_SCAN_FAILED = 'לא הצלחנו לטעון את העמוד'
/** No page attribution on the wire — say so; never guess a page (§3.5a). */
export const RV_SCAN_NONE =
    'התמלול לא ציין באילו עמודים נמצאת התשובה — הסריקה המלאה זמינה במבחן המוחזר'
export const RV_ANSWER_NONE = 'אין תשובה בתמלול המאושר · ודאי מול הסריקה'
/**
 * [EVD-1] The answer shown belongs to an ANCESTOR part, and this scope was
 * graded against it. Said out loud, never implied: presenting a parent's words
 * as the leaf's own is a silent repair (FC), and the teacher judging the grade
 * is the one person who can tell whether that inference was fair.
 */
export const RV_ANSWER_INHERITED = (from: string) =>
    `זו התשובה לסעיף ${from}, שמכסה גם את החלק הזה`
/** Same fact, when the wire did not name which ancestor. */
export const RV_ANSWER_INHERITED_ANON =
    'זו התשובה לסעיף המלא, שמכסה גם את החלק הזה'
/**
 * NOT the same as RV_ANSWER_NONE, and the difference is the whole point.
 * «No answer» accuses the student of leaving it blank. This says WE cannot
 * show what was graded — which is what a legacy row whose inputs have since
 * moved actually means. Degrade by omission, never by accusation (§3.5a).
 */
export const RV_ANSWER_UNAVAILABLE =
    'לא ניתן להציג את התשובה שנבדקה · ודאי מול הסריקה'
export const RV_SCOPE_FAILED = 'הניקוד נכשל לשאלה זו'
export const RV_SCOPE_FAILED_CHIP = 'לא נוקד'
export const RV_SCOPE_RETRY = 'ניסיון נוסף'
export const RV_SCOPE_EXCLUDED = 'לא נכללה בציון — נבחרו שאלות אחרות'
export const RV_SCOPE_OPEN = 'פתיחה'
export const RV_SCOPE_NO_MARKERS = 'ללא סימונים'

/** «4 סימוני "לבדוק"» — AM3 plural-aware. */
export const RV_LOOK_COUNT = (n: number) =>
    hebrewCount(n, {
        zero: '',
        one: 'סימון אחד לבדוק',
        many: (x) => `${x} סימונים לבדוק`,
    })

// ── R6/R7 · check row ─────────────────────────────────────────────────────
export const RV_CHIP_NOT_FOUND = 'לא נמצאה עדות בתשובה — ודאי לפני שאת מאשרת'
export const RV_CHIP_FUZZY = 'ציטוט משוער — הטקסט בתשובה שונה מעט'
export const RV_CHIP_DISPUTED = 'סימנת: העדות שגויה'
export const RV_QUOTE = 'ציטוט רלוונטי מהתשובה'
export const RV_QUOTE_TITLE = 'הדגשת הציטוט בתשובה'
/** A counted check (a trace table priced per cell): how many of the N units were right. */
export const RV_COUNTED_OF = (k: number, n: number) => `${k} מתוך ${n}`
export const RV_QUOTE_PINNED = 'הציטוט מודגש בתשובה · Esc לביטול'
export const RV_VERDICT_TITLE = 'שינוי (Space)'

/** «הצעת ויוי: ✓ · 2 → השינוי שלך · חזרה» — the struck-through proposal. */
export const RV_ORIG_PREFIX = 'הצעת ויוי:'
export const RV_ORIG_MINE = 'השינוי שלך'
export const RV_ORIG_REVERT = 'חזרה'

export const RV_NOTE_PLACEHOLDER = 'הערה קצרה — למה שינית (לא מוצגת לתלמיד/ה)'

// ── R11 · feedback ────────────────────────────────────────────────────────
export const RV_FB_TITLE = (scopeTitle: string) => `משוב לתלמיד/ה · ${scopeTitle}`
export const RV_FB_SUMMARY_TITLE = 'סיכום לתלמיד/ה · המבחן כולו'
export const RV_FB_FRESH = 'נכתב על ידי ויוי לפי הניקוד · ניתן לעריכה'
export const RV_FB_STALE = 'נכתב לפני השינוי שלך'
export const RV_FB_REWRITE = 'כתיבה מחדש לפי הניקוד החדש'
/** `feedback = null` is a wire state, not an error — R11. */
export const RV_FB_ABSENT = 'לא נכתב משוב'
export const RV_FB_WRITE = 'כתיבה'
export const RV_FB_REGENERATED = 'המשוב נכתב מחדש לפי הניקוד הנוכחי'
export const RV_FB_EDITED = 'נכתב על ידך'

// ── R12 · bottom bar ──────────────────────────────────────────────────────
export const RV_SAVED = 'נשמר אוטומטית'
export const RV_SAVING = 'שומרת…'
export const RV_SAVE_FAILED = 'השמירה נכשלה — נסי שוב'
/** The server priced the same overlay differently — she must not review one
 *  number and have another freeze (the §5 catastrophe). */
export const RV_PRICING_MISMATCH =
    'הניקוד שמוצג אינו תואם את חישוב השרת — רענני את הדף לפני האישור'
export const RV_APPROVE = 'אישור וחתימה'
export const RV_APPROVING = 'מאשרת…'
export const RV_APPROVED_TOAST = (score: string, next: string | null) =>
    next ? `אושר ונחתם · ${score} · עוברת ל${next}` : `אושר ונחתם · ${score}`
export const RV_KEYS_ALL = 'כל המקשים'
export const RV_KEY_MOVE = 'מעבר'
export const RV_KEY_VERDICT = 'שינוי ניקוד'
export const RV_KEY_REVERT = 'חזרה להצעת ויוי'
export const RV_KEY_MARKER = 'לסימון הבא'
export const RV_KEYS_REST =
    'H הערה · E עדות שגויה · ← → מבחן הבא/קודם · Ctrl ↵ אישור · Esc ביטול הדגשה'

// ── R13 · version banner ──────────────────────────────────────────────────
/**
 * `version` is OMITTED, not invented, when the feed does not carry it: the
 * banner's job is the fact («you are editing a signed test»), and a wrong
 * number beside it would be the kind of detail she checks against her memory.
 */
export const RV_VBANNER_MANUAL = (version: number | null) =>
    version != null && version > 1
        ? `גרסה ${version} · את עורכת בדיקה שכבר אושרה. אישור וחתימה יחתמו את הגרסה החדשה.`
        : 'את עורכת בדיקה שכבר אושרה. אישור וחתימה יחתמו את הגרסה החדשה.'
export const RV_VBANNER_CTA = 'לשינוי'

// ── WaitCard ──────────────────────────────────────────────────────────────
export const RV_WAIT_TITLE = 'אין כרגע מבחן נוסף שנחת'
export const RV_WAIT_GRADING = (n: number) =>
    hebrewCount(n, {
        zero: 'כל המבחנים במקבץ נבדקו.',
        one: 'מבחן אחד מנוקד עכשיו.',
        many: (x) => `${x} מבחנים מנוקדים עכשיו.`,
    })
export const RV_WAIT_ETA_UNKNOWN = 'עוד רגע'
export const RV_WAIT_TO_DASHBOARD = 'חזרה ללוח המקבץ'

// ── errors / shells ───────────────────────────────────────────────────────
export const RV_LOAD_ERROR = 'שגיאה בטעינת הבדיקה'
export const RV_NOT_FOUND = 'הבדיקה לא נמצאה'
export const RV_LOADING = 'טוענת את הבדיקה…'
/** N6: the review module is desktop-only; the dashboard stays glanceable. */
export const RV_MOBILE_INTERSTITIAL =
    'בדיקת ציונים דורשת מסך רחב — התשובה, הקריטריונים והציטוטים צריכים להופיע זה לצד זה. '
    + 'פתחי את המקבץ במחשב כדי לבדוק ולחתום.'
export const RV_MOBILE_BACK = 'חזרה ללוח המקבץ'

/**
 * A draft with no `checks` cannot be reviewed here (a pre-v5 grade). The
 * surface REFUSES rather than rendering empty cards — an empty checklist reads
 * as "nothing to check" on a test nobody has checked (§3.5a: a degradation
 * that keeps computing is more dangerous than one that stops).
 */
export const RV_NO_CHECKS =
    'הבדיקה הזו נוצרה בגרסה ישנה של ויוי ואי אפשר להציג אותה כאן. נקדי אותה מחדש מלוח המקבץ.'

// ═══════════════════════════════════════════════════════════════════════════
// F1 · לוח המקבץ — the grade-review dashboard (spec §4.1, D1–D10)
// ═══════════════════════════════════════════════════════════════════════════

// ── D1 · header ───────────────────────────────────────────────────────────
export const DASH_TITLE = 'בדיקת ציונים'
export const DASH_SUB = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(' · ')
export const DASH_DOWNLOAD = 'הורדת המבחנים המוחזרים'
export const DASH_DOWNLOAD_ALL = (n: number) => `הורדת כל המבחנים המוחזרים (${n})`
export const DASH_CONTINUE = 'המשיכי לבדיקת ציונים'

// ── D2 · steps + ETA ──────────────────────────────────────────────────────
export const DASH_STEP_GRADING = (landed: number, total: number) =>
    `ויוי מנקדת · נחתו ${landed} מתוך ${total}`
export const DASH_STEP_AUDIT = 'ביקורת עקביות מול הכיתה'
export const DASH_STEP_AUDIT_DONE = (n: number) => `ביקורת עקביות · עודכנו ${n}`
export const DASH_STEP_APPROVE = (approved: number, total: number) =>
    `אישור וחתימה · ${approved} מתוך ${total}`

export const DASH_ETA_LANDING = (minutes: number) =>
    minutes === 1
        ? 'כל המבחנים ינחתו בעוד כדקה. אפשר להתחיל לבדוק כבר עכשיו.'
        : `כל המבחנים ינחתו בעוד כ-${minutes} דקות. אפשר להתחיל לבדוק כבר עכשיו.`
export const DASH_ETA_REMAINING = (minutes: number) =>
    minutes === 1 ? 'עוד כדקה' : `עוד כ-${minutes} דקות`
export const DASH_ETA_UNKNOWN = 'עוד רגע'

// ── D3 · attention line ───────────────────────────────────────────────────
export const DASH_ATTENTION_PREFIX = 'דורש את תשומת לבך:'
export const DASH_ATTENTION_MARKERS = (n: number) =>
    n === 1 ? 'סימון אחד לבדוק' : `${n} סימונים לבדוק`
export const DASH_ATTENTION_OPEN = 'פתיחה'
export const DASH_DONE_BANNER = (approved: number, minutes: number | null) => {
    const tests = approved === 1 ? 'המבחן המוחזר נחתם' : `${approved} המבחנים המוחזרים נחתמו`
    return minutes === null
        ? `הכול מוכן. ${tests}.`
        : `הכול מוכן. ${tests}. הבדיקה שלך ארכה ${minutes} דקות.`
}
export const DASH_DONE_WITH_FAILURES = (failed: number) =>
    failed === 1
        ? 'מבחן אחד נכשל בניקוד ולא ייכלל בהורדה.'
        : `${failed} מבחנים נכשלו בניקוד ולא ייכללו בהורדה.`

// ── D6 · pile cards ───────────────────────────────────────────────────────
export const DASH_CARD_PENDING = 'ממתין לניקוד'
export const DASH_CARD_GRADING = 'ויוי מנקדת'
/** The caption under a grading card (mockup `card()`): the thumb says who is
 *  working, the caption says what is happening to this test. */
export const DASH_CARD_GRADING_CAPTION = 'מנוקד עכשיו'
/** D6: a draft that is a revision of a signed test — the signature is gone. */
export const DASH_CARD_STALE_VERSION = (n: number) => `גרסה ${n} · לא נחתם`
export const DASH_CARD_LANDED = 'נחת · מוכן לבדיקה'
export const DASH_CARD_MARKED = (n: number) =>
    n === 1 ? 'סימון אחד לבדוק' : `${n} לבדוק`
export const DASH_CARD_DRAFT = 'בעריכה · נשמר'
export const DASH_CARD_APPROVED = 'אושר ונחתם'
export const DASH_CARD_FAILED = 'הניקוד נכשל'
export const DASH_CARD_RETRY = 'ניסיון נוסף'
/** After she clicked retry: the successor is a new pending row the feed cannot
 *  show yet (`extend_chain` does not copy `batch_id` — reported), so the card
 *  says what happened instead of offering the same click again. */
export const DASH_CARD_RETRIED = 'נשלח לניקוד חוזר'
export const DASH_CARD_NO_NAME = 'ללא שם'
export const DASH_CARD_ALT = (name: string) => `העמוד הראשון של המבחן של ${name}`
export const DASH_PILE_EMPTY = 'אין עדיין מבחנים מנוקדים במקבץ הזה.'

// ── D9 · download modal ───────────────────────────────────────────────────
export const DL_TITLE = (n: number) =>
    n === 1 ? 'הורדת מבחן מוחזר אחד' : `הורדת ${n} מבחנים מוחזרים`
export const DL_BODY_PARTIAL = (excluded: number) =>
    excluded === 1
        ? 'יורדו רק המבחנים שאישרת וחתמת. מבחן אחד עדיין לא אושר ולא ייכלל בקובץ.'
        : `יורדו רק המבחנים שאישרת וחתמת. ${excluded} מבחנים עדיין לא אושרו ולא ייכללו בקובץ.`
export const DL_BODY_ALL =
    'כל המבחנים אושרו ונחתמו. יורד קובץ ZIP אחד — כל מבחן כולל את דפי הסריקה עם חותמת הציון, ואחריהם דפי המשוב.'
export const DL_STALE = (n: number) =>
    n === 1
        ? 'מבחן אחד נערך אחרי החתימה ואינו מעודכן — אשרי אותו מחדש כדי לכלול אותו.'
        : `${n} מבחנים נערכו אחרי החתימה ואינם מעודכנים — אשרי אותם מחדש כדי לכלול אותם.`
/** A failed test can never be approved — she can only send it back to grading,
 *  so it is named apart from the ones that merely await her review. */
export const DL_FAILED = (n: number) =>
    n === 1
        ? 'מבחן אחד נכשל בניקוד ולא ייכלל — אפשר לנסות לנקד אותו שוב.'
        : `${n} מבחנים נכשלו בניקוד ולא ייכללו — אפשר לנסות לנקד אותם שוב.`
export const DL_NAMING = 'שם כל קובץ: <שם המקבץ>_<שם התלמיד/ה>_מוחזר.pdf'
export const DL_CONFIRM = (n: number) => `הורדת ${n} המבחנים`
export const DL_CANCEL = 'ביטול'
export const DL_NOTHING = 'עדיין לא אושר אף מבחן, ולכן אין מה להוריד.'
export const DASH_DOWNLOAD_STARTED = 'ההורדה התחילה'
export const DASH_DOWNLOAD_FAILED = 'לא הצלחנו להוריד את הקובץ — נסי שוב'
export const DASH_RETRY_STARTED = (name: string) => `${name} נשלח לניקוד חוזר`
export const DASH_RETRY_FAILED = 'לא הצלחנו לשלוח לניקוד חוזר — נסי שוב'

// ── P1–P8 · המבחן המוחזר ──────────────────────────────────────────────────
export const PV_TITLE = (student: string) => `המבחן המוחזר · ${student}`
/** «6 עמודי מבחן + 2 עמודי משוב · נחתם 29.8.2026, 20:31 · גרסה 1» */
export const PV_SUB = (scanPages: number, appendixPages: number,
                       signedAt: string | null, version: number | null) =>
    [
        // `scanPages === 0` means we never fetched the scan (a link without a
        // batch), NOT that the exam has no pages. Saying «ללא עמודי מבחן» would
        // be an invented claim about a document we did not ask for, so the
        // clause is omitted instead (§3.5a).
        scanPages > 0
            ? `${examPagesCount(scanPages)} + ${feedbackPagesCount(appendixPages)}`
            : feedbackPagesCount(appendixPages),
        signedAt ? `נחתם ${signedAt}` : null,
        version != null ? `גרסה ${version}` : null,
    ].filter(Boolean).join(' · ')

const examPagesCount = (n: number) => hebrewCount(n, {
    zero: 'ללא עמודי מבחן',
    one: 'עמוד מבחן אחד',
    many: (x) => `${x} עמודי מבחן`,
})
const feedbackPagesCount = (n: number) => hebrewCount(n, {
    zero: 'ללא עמודי משוב',
    one: 'עמוד משוב אחד',
    many: (x) => `${x} עמודי משוב`,
})

export const PV_TOGGLE = 'פירוט קריטריונים בדף המשוב'
/**
 * The (i) explainer, VERBATIM from PR spec §6. It is quoted there character for
 * character because it is the only place the product explains that this switch
 * changes every returned exam in the batch and not just the one on screen — a
 * per-batch setting reached from a per-test screen is exactly the control that
 * surprises people. Do not paraphrase it.
 */
export const PV_TOGGLE_INFO =
    'חל על כל המבחנים במקבץ. כשהמתג דלוק, דף המשוב של כל תלמיד/ה יכלול, מתחת לכל שאלה, את רשימת הקריטריונים מהמחוון ואת הניקוד שניתן לכל אחד מהם. כשהמתג כבוי, יופיעו רק הניקוד לשאלה והמשוב המילולי. הציון הסופי אינו משתנה.'
export const PV_TOGGLE_INFO_LABEL = 'הסבר על פירוט הקריטריונים'
export const PV_TOGGLE_ON = 'פירוט הקריטריונים יופיע בדפי המשוב של כל המקבץ'
export const PV_TOGGLE_OFF = 'דפי המשוב יכללו ניקוד לשאלה ומשוב מילולי בלבד'
export const PV_TOGGLE_FAILED = 'לא הצלחנו לשמור את ההגדרה — נסי שוב'

export const PV_EDIT = 'עריכת הבדיקה'
export const PV_DOWNLOAD = 'הורדת PDF'
/** 202: the file is being rendered. The button stays live and SAYS SO — a
 *  disabled button with no explanation reads as a broken product (P1). */
export const PV_DOWNLOAD_PREPARING = 'ויוי עדיין מכינה את הקובץ · עוד כ-10 שניות'
export const PV_DOWNLOAD_FAILED = 'לא הצלחנו להוריד את הקובץ — נסי שוב'

export const PV_STRIP_SCAN = (n: number) => `עמוד ${n}`
export const PV_STRIP_APPENDIX = (n: number) => `משוב ${n}`

export const PV_HINT_STAMP =
    'גררי את החותמת כדי להזיז אותה. ויוי בחרה את הפינה הריקה ביותר בעמוד הראשון.'
/**
 * Nothing stored yet: the PDF's corner is chosen by the backend's picker at
 * render time and is NOT on the wire, so the preview cannot show it — it shows
 * a default corner and says so honestly rather than claiming Vivi chose it.
 */
export const PV_HINT_STAMP_AUTO =
    'ויוי תבחר את הפינה הריקה ביותר בעמוד הראשון. גררי את החותמת כדי לקבוע מיקום בעצמך.'
export const PV_HINT_SCAN = (n: number) => `עמוד ${n} — ללא שינוי מהסריקה המקורית`
export const PV_HINT_APPENDIX =
    'דף המשוב מודפס בסוף המבחן המוחזר. מנוסח בלשון ניטרלית (עבר / שם פועל) כדי להתאים לכל תלמיד ותלמידה.'
export const PV_APPLY_ALL = 'להחיל מיקום זה על כל המבחנים במקבץ'
/**
 * NO COUNT, deliberately. The PATCH answers with `stamp_applied_count`, which
 * counts DRAFTS whose auto-position was cleared — not exams affected, since
 * setting the batch default also moves every test that never had a position at
 * all. Printing that number beside «הוחל על» would state a figure the server
 * never claimed. The setting is batch-wide, and that is what this says.
 */
export const PV_APPLY_ALL_DONE = 'המיקום הוחל על כל המבחנים במקבץ'
export const PV_APPLY_ALL_FAILED = 'לא הצלחנו להחיל את המיקום — נסי שוב'
export const PV_STAMP_SAVED = 'מיקום החותמת נשמר'
export const PV_STAMP_SAVE_FAILED = 'לא הצלחנו לשמור את מיקום החותמת — נסי שוב'
export const PV_STAMP_LABEL = 'חותמת האישור — אפשר לגרור'

/** P8 — she edited after signing, so the artefact below is the OLD version. */
export const PV_STALE = (version: number) =>
    `ערכת את הבדיקה אחרי החתימה. המבחן המוחזר שלמטה הוא גרסה ${version} ואינו מעודכן — אשרי מחדש כדי לחתום את גרסה ${version + 1}.`
export const PV_REAPPROVE = 'אישור וחתימה מחדש'

export const PV_NOT_APPROVED_TITLE = 'המבחן הזה עדיין לא אושר ונחתם'
export const PV_NOT_APPROVED_BODY =
    'המבחן המוחזר נוצר מהבדיקה החתומה. אשרי את הבדיקה כדי לראות אותו.'
export const PV_NOT_APPROVED_CTA = 'למעבר לבדיקה'
export const PV_LOADING = 'טוענת את המבחן המוחזר…'
export const PV_LOAD_FAILED = 'לא הצלחנו לטעון את המבחן המוחזר'

// ── appx.* · the feedback pages ───────────────────────────────────────────
export const APPX_TITLE = (examName: string) => `משוב · ${examName}`
export const APPX_META = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(' · ')
export const APPX_TEACHER = (name: string) => `המורה: ${name}`
export const APPX_SUMMARY = 'סיכום'
export const APPX_FOOTER = 'נבדק בעזרת ויוי · הציון והמשוב אושרו על ידי המורה'
export const APPX_FOOTER_PAGE = (n: number, of: number) => `משוב ${n}/${of}`
/** LTR-isolated at the call site; the slash reorders next to Hebrew. */
export const APPX_POINTS = (awarded: string, possible: string) => `${awarded} / ${possible}`
