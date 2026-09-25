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
 *    בדיקת ציונים · המבחן החתום
 */

// ── R1 · top bar ──────────────────────────────────────────────────────────
export const RV_TOTAL_PROPOSAL = (possible: string) => `מתוך ${possible} · הצעת ויוי`
export const RV_TOTAL_MINE = (possible: string) => `מתוך ${possible} · אחרי השינויים שלך`
export const RV_NAV_PREV = 'הקודם'
export const RV_NAV_NEXT = 'הבא'
/** The way OUT of the module, beside «הבא» — the only other exit was the
 *  browser's back button. Names the dashboard by what she calls it. */
export const RV_NAV_TO_BATCH = 'חזרה לכל המבחנים'
export const RV_MINI_THUMB_TITLE = 'המבחן החתום'

/** «כיתה · מס׳ 12 · מבחן 7 מתוך 30 · מוכן לפני 6 דקות» */
export const RV_IDENTITY_META = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(' · ')
export const RV_TEST_POSITION = (index: number, total: number) =>
    `מבחן ${index} מתוך ${total}`
export const RV_LANDED_AGO = (relative: string) => `מוכן ${relative}`
export const RV_STUDENT_NUMBER = (n: string) => `מס׳ ${n}`

// ── §2 · revision affordances, kept reachable from the top bar's overflow ──
export const RV_MORE_ACTIONS = 'פעולות נוספות'
export const RV_REGRADE = 'בדיקה מחדש'
export const RV_REGRADE_HINT = 'ויוי תבדוק מחדש לפי המחוון העדכני'
export const RV_MANUAL_EDIT = 'עריכה מחדש'
export const RV_MANUAL_EDIT_HINT = 'פתיחת בדיקה שכבר אושרה לעריכה'
export const RV_RETRY = 'ניסיון בדיקה נוסף'
export const RV_RETRY_HINT = 'הבדיקה נכשלה — שליחה לבדיקה חוזרת'
export const RV_REVISION_STARTED = 'נשלח לבדיקה מחדש'
/** A revision lands as a PENDING row — there is no draft to review yet. */
export const RV_GRADING_IN_PROGRESS = 'ויוי בודקת את המבחן — הבדיקה תיפתח כאן ברגע שתסתיים'
export const RV_GRADING_FAILED = 'הבדיקה נכשלה'
export const RV_APPROVED_READONLY =
    'המבחן אושר ונחתם. לעריכה נוספת השתמשי ב"עריכה מחדש" בתפריט הפעולות.'

// ── R11 · a regeneration that would overwrite her words is OFFERED ──
export const RV_FB_OFFERED_TITLE = 'ויוי כתבה נוסח חדש לפי הציון הנוכחי'
export const RV_FB_OFFERED_KEEP = 'שמירה על הנוסח שלי'
export const RV_FB_OFFERED_USE = 'שימוש בנוסח של ויוי'

// ── R2 · queue line ───────────────────────────────────────────────────────
export const RV_QUEUE_NEXT = (name: string) => `הבא בתור: ${name}`
export const RV_QUEUE_GRADING = (name: string, eta: string | null) =>
    eta ? `אחריו ${name} (נבדק עכשיו, ${eta})` : `אחריו ${name} (נבדק עכשיו)`
export const RV_QUEUE_UNLANDED = (n: number) =>
    hebrewCount(n, {
        zero: '',
        one: 'מבחן אחד עדיין לא מוכן — הבא מדלג עליו וחוזר אליו',
        many: (x) => `${x} מבחנים עדיין לא מוכנים — הבא מדלג עליהם וחוזר אליהם`,
    })
export const RV_QUEUE_SEP = ' · '

// ── R3 · scope nav ────────────────────────────────────────────────────────
export const RV_NAV_HEADING = 'שאלות'
/**
 * §5.5 — THE LEGEND, and it has to be TRUE.
 *
 * The dot is `markerCountByScope(reviewMarkers(draft))`, and the markers are
 * SIX deterministic kinds (`utils/review-markers.ts`): a cited quote that does
 * not validate against the answer, a bounds-clamped or closed-world terminal, a
 * scope the grader skipped or failed. NOT a confidence score — the product
 * never renders one.
 *
 * That is exactly why a dot appears beside a full-marks question and looked
 * like a bug: the case the markers exist for is a `met` check whose quotation
 * is not in the student's answer. That is invented credit, it is INVISIBLE in
 * the score, and if nothing sent her there nothing would.
 *
 * So the legend says what Vivi could not verify by itself, and never «ויוי פחות
 * בטוחה», which would be a claim about a number this surface does not have.
 */
export const RV_NAV_LEGEND = 'ויוי לא הצליחה לאמת את זה בעצמה — כדאי להציץ'
/** §5.5 — «where did he lose points» is her first read, and the dots do not
 *  answer it. Rendered only when the deduction is non-zero. */
export const RV_DEDUCTION = (d: string) => `−${d}`

// ── R4 · scope section ────────────────────────────────────────────────────
export const RV_QUESTION_TOGGLE = 'השאלה'
export const RV_ANSWER_LABEL = 'תשובת התלמיד/ה · מתוך התמלול שאישרת'
export const RV_SHOW_SCAN = 'הצגת הסריקה המקורית'
/** R4 · the scan viewer — the pages the transcription attributed the answer to. */
export const RV_SCAN_TITLE = (scopeTitle: string) => `הסריקה · ${scopeTitle}`
export const RV_SCAN_PAGE = (n: number) => `עמוד ${n}`
export const RV_SCAN_CLOSE = 'סגירה'
export const RV_SCAN_LOADING = 'טוענת את הסריקה…'
export const RV_SCAN_FAILED = 'לא הצלחנו לטעון את העמוד'
/** No page attribution on the wire — say so; never guess a page (§3.5a). */
export const RV_SCAN_NONE =
    'התמלול לא ציין באילו עמודים נמצאת התשובה — הסריקה המלאה זמינה במבחן החתום'
export const RV_ANSWER_NONE = 'אין תשובה בתמלול שאישרת · ודאי מול הסריקה'
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
export const RV_SCOPE_FAILED = 'הבדיקה נכשלה בשאלה זו'
export const RV_SCOPE_FAILED_CHIP = 'לא נבדק'
export const RV_SCOPE_RETRY = 'ניסיון נוסף'

// [OD-R1] The approval blockers. A failed scope is re-graded automatically, so
// she reaches these only when the retry ALSO failed — and then the way out is
// her own judgement, which is what these sentences have to say out loud.
export const RV_BLOCK_LLM_FAILURE = (scopeId: string) =>
    `הבדיקה האוטומטית נכשלה בסעיף ${scopeId} — קבעי בעצמך את כל הבדיקות בסעיף כדי לאשר`
export const RV_BLOCK_GENERIC = 'יש בעיה שדורשת תיקון לפני אישור'
export const RV_APPROVE_BLOCKED = (blockers: readonly string[]) =>
    blockers.length === 1
        ? `לא ניתן לאשר עדיין · ${blockers[0]}`
        : `לא ניתן לאשר עדיין · ${blockers.join(' · ')}`
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
export const RV_CHIP_DISPUTED = 'סימנת: העדות שגויה'

export const RV_QUOTE = 'ציטוט רלוונטי מהתשובה'
export const RV_QUOTE_TITLE = 'הדגשת הציטוט בתשובה'
// [S3] The criterion-level button — lights every span its checks would light,
// at once. Owner wording (2026-09-11); it must NOT contain the per-check
// label «ציטוט רלוונטי מהתשובה» as a substring, or the two families become
// indistinguishable to a role query — the «ה» in «הרלוונטי» is what keeps
// them apart.
export const RV_QUOTE_ALL = 'לציטוט הרלוונטי מהתשובה'
export const RV_QUOTE_ALL_TITLE = 'הדגשת הציטוטים הרלוונטיים של הקריטריון בתשובה'

// [S4] The criterion breakdown, behind a disclosure.
/** The accessible name of the expander — it must say WHAT opens, not «פתיחה». */
export const RV_BREAKDOWN_SHOW = (criterion: string) => `פתיחת הפירוט של ${criterion}`
export const RV_BREAKDOWN_HIDE = (criterion: string) => `סגירת הפירוט של ${criterion}`
/** «N בדיקות» — the weight of the box, visible before she opens it. */
export const RV_BREAKDOWN_COUNT = (n: number) =>
    n === 1 ? 'בדיקה אחת' : `${n} בדיקות`
/** A counted check (a trace table priced per cell): how many of the N units were right. */
export const RV_COUNTED_OF = (k: number, n: number) => `${k} מתוך ${n}`
export const RV_QUOTE_PINNED = 'הציטוט מודגש בתשובה · Esc לביטול'
// [S3] The criterion button lights SEVERAL spans; the singular above would
// describe one of them and leave her looking for the rest.
export const RV_QUOTES_PINNED = 'כל הציטוטים של הקריטריון מודגשים · Esc לביטול'
export const RV_VERDICT_TITLE = 'שינוי (Space)'

/** «הצעת ויוי: ✓ · 2 → השינוי שלך · חזרה» — the struck-through proposal. */
export const RV_ORIG_PREFIX = 'הצעת ויוי:'

// ── [OD-R2] typed points (owner ruling 2026-09-13) ─────────────────────────
export const RV_POINTS_EDIT_TITLE = 'לחצי כדי להקליד את מספר הנקודות (Enter)'
export const RV_POINTS_TYPED_TITLE = 'הנקודות הוקלדו ידנית — לחצי כדי לשנות'
/** The refusal, live while she types (OD-4 a). X is what she typed, Y the ceiling. */
export const RV_POINTS_OVER_MAX_CRITERION = (x: string, y: string) =>
    `לא ניתן להעניק ${x} נקודות לקריטריון עם מקסימום ${y} נקודות`
export const RV_POINTS_OVER_MAX_CHECK = (x: string, y: string) =>
    `לא ניתן להעניק ${x} נקודות לבדיקה עם מקסימום ${y} נקודות`
/** A deduction row (ruling 2026-09-13): binary, toggle-only, its own grammar. */
export const RV_TARIFF_MARK = 'הורדה'
export const RV_TARIFF_NONE = 'ללא הורדה'
export const RV_TARIFF_UP_TO = (y: string) => `עד ${y}`
export const RV_TARIFF_ONCE = 'נספרה פעם אחת'
export const RV_VERDICT_TITLE_TARIFF = 'הורדה כן / לא (Space)'
/** An UNVERIFIED credit verdict (2026-09-15): Vivi's ✓ whose quote she could not
 *  find in the answer — priced at 0 until the teacher confirms it. */
export const RV_VERDICT_TITLE_UNVERIFIED = 'ויוי סימנה ✓ אך לא אימתה את הציטוט — לחיצה מאשרת (Space)'
export const RV_ORIG_CONFIRMED = 'אישרת למרות שהציטוט לא אומת'
export const RV_POINTS_OFF_GRID = (x: string, step: string) =>
    `לא ניתן להעניק ${x} נקודות — הנקודות ניתנות בקפיצות של ${step}`
export const RV_POINTS_NEGATIVE = (x: string) =>
    `לא ניתן להעניק ${x} נקודות — המינימום הוא 0`
export const RV_POINTS_NOT_A_NUMBER = 'יש להקליד מספר, למשל 2.5'
/** The criterion row's provenance line when she typed its total. */
export const RV_CRIT_TYPED = 'הנקודות שהקלדת'
export const RV_ORIG_MINE = 'השינוי שלך'
export const RV_ORIG_REVERT = 'חזרה'

export const RV_NOTE_PLACEHOLDER = 'הערה קצרה — למה שינית (לא מוצגת לתלמיד/ה)'

// ── R11 · feedback ────────────────────────────────────────────────────────
export const RV_FB_TITLE = (scopeTitle: string) => `משוב לתלמיד/ה · ${scopeTitle}`
export const RV_FB_SUMMARY_TITLE = 'סיכום לתלמיד/ה · המבחן כולו'
export const RV_FB_FRESH = 'נכתב על ידי ויוי לפי הציון · ניתן לעריכה'
export const RV_FB_STALE = 'נכתב לפני השינוי שלך'
export const RV_FB_REWRITE = 'כתיבה מחדש לפי הציון החדש'
/** `feedback = null` is a wire state, not an error — R11. */
export const RV_FB_ABSENT = 'לא נכתב משוב'
export const RV_FB_WRITE = 'כתיבה'
export const RV_FB_REGENERATED = 'המשוב נכתב מחדש לפי הציון הנוכחי'
export const RV_FB_EDITED = 'נכתב על ידך'

// ── R12 · bottom bar ──────────────────────────────────────────────────────
export const RV_SAVED = 'נשמר אוטומטית'
export const RV_SAVING = 'שומרת…'
export const RV_SAVE_FAILED = 'השמירה נכשלה — נסי שוב'
/** The server priced the same overlay differently — she must not review one
 *  number and have another freeze (the §5 catastrophe). */
export const RV_PRICING_MISMATCH =
    'הציון שמוצג אינו תואם את חישוב השרת — רענני את הדף לפני האישור'
export const RV_APPROVE = 'אישור וחתימה'
/** §5.5 — what pressing it DOES, beside the button that does it. She is
 *  legally accountable for the number; she is entitled to know it is about to
 *  be written onto the paper the student gets back. */
export const RV_APPROVE_HELPER = 'הציון ייכתב על המבחן'
export const RV_APPROVING = 'מאשרת…'
export const RV_APPROVED_TOAST = (score: string, next: string | null) =>
    next ? `אושר ונחתם · ${score} · עוברת ל${next}` : `אושר ונחתם · ${score}`
/**
 * §5.5 — the keyboard bar shows TWO hints by default; everything else folds
 * under «כל המקשים». A first-timer does not read a row of six shortcuts, and a
 * row of six is how she learns to read none of them.
 *
 * ⚠ THE VISIBLE APPROVE HINT IS `Ctrl ↵`, NOT a bare Enter. The spec's §5.5
 * line reads «Enter אישור וחתימה»; on THIS surface a bare Enter opens the
 * points field on the focused row (OD-R2, owner-ruled 2026-09-13) and never
 * approves — deliberately, because Space cycles verdicts here and a hand
 * resting one key over would otherwise sign a grade. A hint that names the
 * wrong key is worse than no hint: she presses it, a field opens, and the
 * product looks broken. The KEY is the ruling; the HINT tells the truth about
 * it (CLAUDE.md §0.3 — surfaced, not silently reconciled).
 */
export const RV_KEYS_ALL = 'כל המקשים'
export const RV_KEY_MOVE = 'מעבר'
export const RV_KEY_APPROVE = 'אישור וחתימה'
export const RV_KEY_VERDICT = 'שינוי ציון'
export const RV_KEY_REVERT = 'חזרה להצעת ויוי'
export const RV_KEY_MARKER = 'לסימון הבא של ויוי'
export const RV_KEYS_REST =
    'Space שינוי ציון · ⌫ חזרה להצעת ויוי · F לסימון הבא של ויוי · '
    + 'H הערה · E עדות שגויה · ← → מבחן הבא/קודם · Esc ביטול הדגשה'

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
export const RV_WAIT_TITLE = 'אין כרגע מבחן נוסף מוכן'
export const RV_WAIT_GRADING = (n: number) =>
    hebrewCount(n, {
        zero: 'כל המבחנים נבדקו.',
        one: 'מבחן אחד נבדק עכשיו.',
        many: (x) => `${x} מבחנים נבדקים עכשיו.`,
    })
export const RV_WAIT_ETA_UNKNOWN = 'עוד רגע'
export const RV_WAIT_TO_DASHBOARD = 'חזרה למבחן'

// ── errors / shells ───────────────────────────────────────────────────────
export const RV_LOAD_ERROR = 'שגיאה בטעינת הבדיקה'
export const RV_NOT_FOUND = 'הבדיקה לא נמצאה'
export const RV_LOADING = 'טוענת את הבדיקה…'
/** N6: the review module is desktop-only; the dashboard stays glanceable. */
export const RV_MOBILE_INTERSTITIAL =
    'בדיקת ציונים דורשת מסך רחב — התשובה, הקריטריונים והציטוטים צריכים להופיע זה לצד זה. '
    + 'פתחי את המבחן במחשב כדי לבדוק ולחתום.'
export const RV_MOBILE_BACK = 'חזרה למבחן'

/**
 * A draft with no `checks` cannot be reviewed here (a pre-v5 grade). The
 * surface REFUSES rather than rendering empty cards — an empty checklist reads
 * as "nothing to check" on a test nobody has checked (§3.5a: a degradation
 * that keeps computing is more dangerous than one that stops).
 */
export const RV_NO_CHECKS =
    'הבדיקה הזו נוצרה בגרסה ישנה של ויוי ואי אפשר להציג אותה כאן. בדקי אותה מחדש מהמסך של המבחן.'

// ═══════════════════════════════════════════════════════════════════════════
// F1 · the grade-review dashboard (spec §4.1, D1–D10)
// ═══════════════════════════════════════════════════════════════════════════

// ── D1 · header ───────────────────────────────────────────────────────────
export const DASH_TITLE = 'בדיקת ציונים'
export const DASH_SUB = (parts: (string | null | undefined)[]) =>
    parts.filter(Boolean).join(' · ')
/**
 * §5.4 — the download button is HIDDEN until at least one test is signed, so
 * these never render a «(0)». Owner-ruled label (2026-09-24). ONE constant for
 * both sites that offer the ZIP — `DownloadAllButton` is the only reader.
 */
export const DASH_DOWNLOAD = 'הורדת כל הבדיקות שאושרו'
/** DL-1 — announced (aria-live) while the ZIP is being built and fetched. */
export const DASH_DOWNLOAD_PREPARING = 'מכינים את הקובץ להורדה…'
export const DASH_CONTINUE = 'המשיכי לבדיקת ציונים'

// ── §5.4 · the grading stage, in her words ────────────────────────────────
export const DASH_HEADING_GRADING = 'התמלולים אושרו · ויוי בודקת עכשיו'
/** «12 מתוך 30 מבחנים בדוקים ומחכים לאישור שלך» */
export const DASH_GRADING_COUNTER = (done: number, total: number) =>
    `${done} מתוך ${total} מבחנים בדוקים ומחכים לאישור שלך`
export const DASH_GRADING_REST_ETA = (minutes: number) =>
    minutes === 1 ? ' · השאר בעוד כדקה' : ` · השאר בעוד כ-${minutes} דקות`
/** done === 0: no «start now» sentence, because there is nothing to start. */
export const DASH_GRADING_FIRST_ETA = (minutes: number | null) =>
    minutes === null
        ? 'המבחן הראשון יהיה מוכן בקרוב'
        : minutes === 1
            ? 'הראשון יהיה מוכן בעוד כדקה'
            : `הראשון יהיה מוכן בעוד כ-${minutes} דקות`
export const DASH_GRADING_START_NOW = 'אפשר להתחיל לאשר כבר עכשיו'

// ── D2 · steps + ETA ──────────────────────────────────────────────────────
export const DASH_STEP_GRADING = (landed: number, total: number) =>
    `ויוי בודקת · ${landed} מתוך ${total} מוכנים`
export const DASH_STEP_AUDIT = 'ביקורת עקביות מול הכיתה'
export const DASH_STEP_AUDIT_DONE = (n: number) => `ביקורת עקביות · עודכנו ${n}`
export const DASH_STEP_APPROVE = (approved: number, total: number) =>
    `אישור וחתימה · ${approved} מתוך ${total}`

export const DASH_ETA_LANDING = (minutes: number) =>
    minutes === 1
        ? 'כל המבחנים יהיו מוכנים בעוד כדקה.'
        : `כל המבחנים יהיו מוכנים בעוד כ-${minutes} דקות.`
export const DASH_ETA_REMAINING = (minutes: number) =>
    minutes === 1 ? 'עוד כדקה' : `עוד כ-${minutes} דקות`
export const DASH_ETA_UNKNOWN = 'עוד רגע'

// ── D3 · attention line ───────────────────────────────────────────────────
export const DASH_ATTENTION_PREFIX = 'דורש את תשומת לבך:'
export const DASH_ATTENTION_MARKERS = (n: number) =>
    n === 1 ? 'סימון אחד לבדוק' : `${n} סימונים לבדוק`
export const DASH_ATTENTION_OPEN = 'פתיחה'
/**
 * §5.6 — the completion banner. It said «המבחן המוחזר נחתם», which names a
 * document she has not seen yet and a verb she just performed; what she needs
 * to know at this moment is that there is nothing left to do and the files are
 * ready to hand out. The duration moved onto the celebration card beside it
 * (`DONE_DURATION`), where it belongs.
 */
export const DASH_DONE_BANNER = 'הכל מוכן. המבחנים החתומים מוכנים להורדה.'
/**
 * ── §5.6 · THE END STATE — the flow's ONE celebration ─────────────────────
 *
 * There used to be two green-check cards with the same shape: one after the
 * last transcription approval and one here. A teacher cannot tell two endings
 * apart, so the first taught her the flow was over four steps early. The other
 * one is deleted; this is the only one that exists.
 */
export const DONE_TITLE = (n: number) =>
    n === 1 ? 'סיימת! מבחן אחד בדוק וחתום' : `סיימת! ${n} מבחנים בדוקים וחתומים`
export const DONE_DURATION = (minutes: number) =>
    minutes === 1
        ? 'מהעלאה ועד החתימה האחרונה — דקה אחת'
        : `מהעלאה ועד החתימה האחרונה — ${minutes} דקות`
/** The emotional payoff: a real page of a real signed exam, large. */
export const DONE_HERO_ALT = (name: string) =>
    `העמוד הראשון של המבחן החתום של ${name}`
export const DONE_HERO_OPEN = 'פתיחת המבחן החתום'
/** Per-card, on every signed test — an EXPLICIT button, not a hidden click
 *  target on the thumbnail (§5.6). */
export const DONE_PREVIEW = 'תצוגה מקדימה'
/**
 * Marketing notebook #008 — the peak-relief moment, and the only place the
 * product asks her for anything. The link is the plain signup URL: no referral
 * attribution exists anywhere in this codebase (R10), and a tracked link that
 * tracks nothing would be a feature wearing copy's clothes.
 */
export const DONE_REFERRAL = 'אם זה חסך לך ערב — שלחי למורה בחדר המורים'
export const DONE_REFERRAL_COPY = 'העתקת קישור'
export const DONE_REFERRAL_COPIED = 'הקישור הועתק'
export const DONE_REFERRAL_FAILED = 'לא הצלחנו להעתיק — אפשר להעתיק מהכתובת'

export const DASH_DONE_WITH_FAILURES = (failed: number) =>
    failed === 1
        ? 'מבחן אחד נכשל בבדיקה ולא ייכלל בהורדה.'
        : `${failed} מבחנים נכשלו בבדיקה ולא ייכללו בהורדה.`

// ── D6 · pile cards ───────────────────────────────────────────────────────
export const DASH_CARD_PENDING = 'ממתין לבדיקה'
export const DASH_CARD_GRADING = 'ויוי בודקת'
/** The caption under a grading card (mockup `card()`): the thumb says who is
 *  working, the caption says what is happening to this test. */
export const DASH_CARD_GRADING_CAPTION = 'נבדק עכשיו'
/** D6: a draft that is a revision of a signed test — the signature is gone. */
export const DASH_CARD_STALE_VERSION = (n: number) => `גרסה ${n} · לא נחתם`
export const DASH_CARD_LANDED = 'מוכן · מחכה לאישור שלך'
export const DASH_CARD_MARKED = (n: number) =>
    n === 1 ? 'סימון אחד לבדוק' : `${n} לבדוק`
export const DASH_CARD_DRAFT = 'בעריכה · נשמר'
export const DASH_CARD_APPROVED = 'אושר ונחתם'
export const DASH_CARD_FAILED = 'הבדיקה נכשלה — נסי שוב'
export const DASH_CARD_RETRY = 'נסי שוב'
/** After she clicked retry: the successor is a new pending row the feed cannot
 *  show yet (`extend_chain` does not copy `batch_id` — reported), so the card
 *  says what happened instead of offering the same click again. */
export const DASH_CARD_RETRIED = 'נשלח לבדיקה חוזרת'
/** §5.4 — whose number this is. The card's wire row carries `total_awarded`
 *  and NO possible total, so it says «הצעת ויוי» and not «מתוך X · הצעת
 *  ויוי»: a denominator this feed does not carry would have to be guessed,
 *  and a guessed denominator is a wrong percentage on a grade. */
export const DASH_CARD_SCORE_TITLE = 'הצעת ויוי'
export const DASH_CARD_NO_NAME = 'ללא שם'
export const DASH_CARD_ALT = (name: string) => `העמוד הראשון של המבחן של ${name}`
export const DASH_PILE_EMPTY = 'אין עדיין מבחנים בדוקים.'

// ── D9 · download modal ───────────────────────────────────────────────────
export const DL_TITLE = (n: number) =>
    n === 1 ? 'הורדת מבחן חתום אחד' : `הורדת ${n} מבחנים חתומים`
export const DL_BODY_PARTIAL = (excluded: number) =>
    excluded === 1
        ? 'יורדו רק המבחנים שאישרת וחתמת. מבחן אחד עדיין לא אושר ולא ייכלל בקובץ.'
        : `יורדו רק המבחנים שאישרת וחתמת. ${excluded} מבחנים עדיין לא אושרו ולא ייכללו בקובץ.`
export const DL_BODY_ALL =
    'כל המבחנים אושרו ונחתמו. יורד קובץ ZIP אחד — כל מבחן כולל את דפי הסריקה עם חותמת הציון, ואחריהם דפי המשוב.'
/**
 * Approved, but no document can be produced from it.
 *
 * REPLACES `DL_STALE`, which said «נערך אחרי החתימה ... אשרי אותו מחדש» — an
 * accusation AND a wrong instruction. A test that had merely never been
 * rendered landed in that bucket, so a teacher who had just approved five
 * tests and touched nothing was told she had edited all five. The download
 * now RENDERS what is missing, so the only exam it cannot ship is one whose
 * frozen contract will not parse — which is ours to fix, not hers.
 */
export const DL_UNAVAILABLE = (n: number) =>
    n === 1
        ? 'מבחן אחד לא ניתן להפקה כרגע ולא ייכלל — אנחנו בודקים את זה.'
        : `${n} מבחנים לא ניתנים להפקה כרגע ולא ייכללו — אנחנו בודקים את זה.`
/** A failed test can never be approved — she can only send it back to grading,
 *  so it is named apart from the ones that merely await her review. */
export const DL_FAILED = (n: number) =>
    n === 1
        ? 'מבחן אחד נכשל בבדיקה ולא ייכלל — אפשר לנסות לבדוק אותו שוב.'
        : `${n} מבחנים נכשלו בבדיקה ולא ייכללו — אפשר לנסות לבדוק אותם שוב.`
export const DL_NAMING = 'שם כל קובץ: <שם המבחן>_<שם התלמיד/ה>_חתום.pdf'
export const DL_CONFIRM = (n: number) => `הורדת ${n} המבחנים`
export const DL_CANCEL = 'ביטול'
/** No exam can be included. Deliberately does NOT claim she approved nothing:
 *  the state that produced this bug was five approved tests and zero
 *  includable ones, and the old sentence blamed her for it. */
export const DL_NOTHING = 'אין כרגע מבחנים להורדה.'
export const DASH_DOWNLOAD_STARTED = 'ההורדה התחילה'
export const DASH_DOWNLOAD_FAILED = 'לא הצלחנו להוריד את הקובץ — נסי שוב'
export const DASH_RETRY_STARTED = (name: string) => `${name} נשלח לבדיקה חוזרת`
export const DASH_RETRY_FAILED = 'לא הצלחנו לשלוח לבדיקה חוזרת — נסי שוב'

// ── P1–P8 · המבחן החתום ──────────────────────────────────────────────────
export const PV_TITLE = (student: string) => `${PV_TITLE_PREFIX} · ${student}`
/** The title's first half, when the student's name is rendered as a LINK to
 *  the profile (student-profile PR OD-2) and cannot be one string. */
export const PV_TITLE_PREFIX = 'המבחן החתום'
/** «6 עמודי מבחן + 2 עמודי משוב · בדיקה אושרה ב29.8.2026, 20:31 · גרסה 1»
 *  OD-14: the moment she approved the grading reads «בדיקה אושרה ב…» wherever
 *  its timestamp is shown — here and on the profile row. It was «נחתם …». */
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
        signedAt ? `בדיקה אושרה ב${signedAt}` : null,
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
    'חל על כל המבחנים שהעלית יחד. כשהמתג דלוק, דף המשוב של כל תלמיד/ה יכלול, מתחת לכל שאלה, את רשימת הקריטריונים מהמחוון ואת הציון שניתן לכל אחד מהם. כשהמתג כבוי, יופיעו רק הציון לשאלה והמשוב המילולי. הציון הסופי אינו משתנה.'
export const PV_TOGGLE_INFO_LABEL = 'הסבר על פירוט הקריטריונים'
export const PV_TOGGLE_ON = 'פירוט הקריטריונים יופיע בדפי המשוב של כל המבחנים'
export const PV_TOGGLE_OFF = 'דפי המשוב יכללו ציון לשאלה ומשוב מילולי בלבד'
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
    'דף המשוב מודפס בסוף המבחן החתום. מנוסח בלשון ניטרלית (עבר / שם פועל) כדי להתאים לכל תלמיד ותלמידה.'
export const PV_APPLY_ALL = 'להחיל מיקום זה על כל המבחנים שהעלית יחד'
/**
 * NO COUNT, deliberately. The PATCH answers with `stamp_applied_count`, which
 * counts DRAFTS whose auto-position was cleared — not exams affected, since
 * setting the batch default also moves every test that never had a position at
 * all. Printing that number beside «הוחל על» would state a figure the server
 * never claimed. The setting is batch-wide, and that is what this says.
 */
export const PV_APPLY_ALL_DONE = 'המיקום הוחל על כל המבחנים שהעלית יחד'
export const PV_APPLY_ALL_FAILED = 'לא הצלחנו להחיל את המיקום — נסי שוב'
export const PV_STAMP_SAVED = 'מיקום החותמת נשמר'
export const PV_STAMP_SAVE_FAILED = 'לא הצלחנו לשמור את מיקום החותמת — נסי שוב'
export const PV_STAMP_LABEL = 'חותמת האישור — אפשר לגרור'

/** P8 — she edited after signing, so the artefact below is the OLD version. */
export const PV_STALE = (version: number) =>
    `ערכת את הבדיקה אחרי החתימה. המבחן החתום שלמטה הוא גרסה ${version} ואינו מעודכן — אשרי מחדש כדי לחתום את גרסה ${version + 1}.`
export const PV_REAPPROVE = 'אישור וחתימה מחדש'

export const PV_NOT_APPROVED_TITLE = 'המבחן הזה עדיין לא אושר ונחתם'
export const PV_NOT_APPROVED_BODY =
    'המבחן החתום נוצר מהבדיקה החתומה. אשרי את הבדיקה כדי לראות אותו.'
export const PV_NOT_APPROVED_CTA = 'למעבר לבדיקה'
export const PV_LOADING = 'טוענת את המבחן החתום…'
export const PV_LOAD_FAILED = 'לא הצלחנו לטעון את המבחן החתום'

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
