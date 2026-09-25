import { placesCount, testsCount } from '@/utils/hebrew-plural'
import { FLAG_REASON_LABELS as FLAG_REASON_LABELS_MAP } from '@/types/batch'

/**
 * Transcription of spec §3.2 — do not edit without a spec change.
 * (vivi-batch-redesign-spec-v2.md, C1: the single home of batch-surface copy.)
 *
 * Components on the five batch surfaces render Hebrew ONLY via this module;
 * tests import from here so assertions track the single source. P0 scaffolds
 * it with the batch-status labels (F3) + the strings the P0 items touch; the
 * remaining §3.2 strings move in with their phases (P2–P5).
 */

/* ── §5.1 · THE STAGE MODEL ────────────────────────────────────────────────
 *
 * `BATCH_STATUS_LABELS` / `batchStatusLabel` are GONE, not deprecated.
 *
 * That pair rendered the chip from `status` + the transcription half of the
 * rollup, so a batch Vivi was actively grading showed «ממתין להחלטות» — it told
 * the teacher she was the one holding it up while the machine worked. Two
 * derivations of the same fact cannot stay in agreement (§9's precedent, which
 * was settled by DELETION, not repair), so the chip now has exactly one source:
 * `utils/batch-stage.ts::deriveBatchStage`. These are the strings it renders.
 *
 * The chip answers ONE question — «is there something for me to do» — and the
 * turn line under it carries the nuance. Neither word «אצווה» nor «מקבץ»
 * appears: OD-1 ruled that a batch is an exam event, counted in מבחנים.
 */

export const CHIP_UPLOADING = 'בהעלאה'
export const CHIP_TRANSCRIBING = 'ויוי קוראת את כתב היד'
export const CHIP_WAITING_APPROVAL = 'ממתין לאישור שלך'
export const CHIP_GRADING = 'ויוי בודקת'
export const CHIP_WAITING_SIGNATURE = 'ממתין לחתימה שלך'
export const CHIP_DONE = 'הושלם'
/** Some documents died, everything that survived is signed. «שגיאה» would
 *  libel a batch that mostly worked; «הושלם» would hide the hole. */
export const CHIP_PARTIAL = 'הושלם חלקית'
export const CHIP_FAILED = 'שגיאה'

/** The six steps of §5.1A, with the owner tag that makes the alternation
 *  visible. `owner` is rendered as a small label under the step name, so she
 *  can see at a glance whose turn each stage is. */
export const STEP_LABELS: Record<string, { label: string; owner: string }> = {
  upload: { label: 'העלאה', owner: 'את' },
  transcribe: { label: 'תמלול', owner: 'ויוי' },
  approve_transcriptions: { label: 'אישור תמלולים', owner: 'את' },
  grade: { label: 'בדיקת ציונים', owner: 'ויוי' },
  sign: { label: 'מעבר ואישור', owner: 'את' },
  download: { label: 'הורדה', owner: 'את' },
}

/** ── §5.1B · the turn line, one row per line of the spec's table ──────── */

export const TURN_UPLOADING = 'עכשיו: המבחנים בהעלאה'
/** No transcription ETA exists on the wire (only a GRADING one), so the
 *  «תורך בעוד כ-N דקות» clause the spec allows is OMITTED rather than filled
 *  from the wrong stage's estimate. See batch-stage.ts. */
export const TURN_TRANSCRIBING_ONLY = 'עכשיו: ויוי קוראת את כתב היד'
export const TURN_TRANSCRIBING_MIXED = (still: number, ready: number) =>
  `ויוי עדיין קוראת ${testsCount(still)} · אפשר להתחיל לאשר את ${ready} שכבר מוכנים`
export const TURN_TRANSCRIBED_ALL = (n: number) => `תורך: ${testsCount(n)} לאישור`
export const TURN_TRANSCRIBED_NEEDS_LOOK = (n: number, m: number) =>
  `${TURN_TRANSCRIBED_ALL(n)}, ${
    m === 1 ? 'מבחן אחד דורש מבט' : `${m} מבחנים דורשים מבט`}`
export const TURN_GRADING_NONE_READY = (etaMinutes: number | null) =>
  etaMinutes === null
    ? 'עכשיו: ויוי בודקת'
    : etaMinutes === 1
      ? 'עכשיו: ויוי בודקת · הראשון יהיה מוכן בעוד כדקה'
      : `עכשיו: ויוי בודקת · הראשון יהיה מוכן בעוד כ-${etaMinutes} דקות`
export const TURN_GRADING_SOME_READY = (done: number, total: number) =>
  `ויוי בודקת · ${done} מתוך ${total} מוכנים לאישור וחתימה שלך`
export const TURN_GRADED_UNSIGNED = (n: number) =>
  n === 1
    ? 'תורך: מבחן אחד בדוק מחכה לאישור וחתימה'
    : `תורך: ${n} מבחנים בדוקים מחכים לאישור וחתימה`
/**
 * Terminal WITH LOSSES. Both numbers, in one sentence, because either alone is
 * a different batch: «you finished 27» hides three students with no grade, and
 * «three failed» hides an evening's work she did complete.
 */
export const TURN_PARTIAL = (signed: number, dead: number) =>
  `סיימת · ${testsCount(signed)} חתומים · ${
    dead === 1 ? 'מבחן אחד לא נקרא' : `${dead} מבחנים לא נקראו`}`
/**
 * Nothing survived. It names the retry because that is the only thing left to
 * do, and a red chip with no sentence is where a teacher gets stuck hardest.
 */
export const TURN_ALL_FAILED = (dead: number) =>
  dead === 1
    ? 'לא הצלחנו לקרוא את המבחן — אפשר לנסות שוב'
    : `לא הצלחנו לקרוא את המבחנים — אפשר לנסות שוב`
export const TURN_ALL_SIGNED = (n: number) =>
  n === 1 ? 'סיימת · מבחן אחד חתום' : `סיימת · ${n} מבחנים חתומים`

/** ── §5.1E · a finished stage collapses to one line, never a card ──────── */
export const STRIP_TRANSCRIPTIONS_APPROVED = (n: number) =>
  `התמלולים אושרו ✓ · ${testsCount(n)}`
export const STRIP_EXPAND = 'הצגה'
export const STRIP_COLLAPSE = 'הסתרה'

/** Dashboard load/poll strings (OD-1: never `מקבץ` on screen). */
export const BATCH_LOAD_ERROR = 'שגיאה בטעינת המבחן'
export const BATCH_NOT_FOUND = 'המבחן לא נמצא'
export const DISMISS_NOTICE_LABEL = 'סגירת ההודעה'
export const RETRY_ERROR = 'שגיאה בניסיון החוזר'

/** Honesty-bar legend labels (D2) — vocabulary drawn from the §3.2 zone
 * titles/status table; keyed by BarSegmentKind. */
export const SEGMENT_LABELS: Record<string, string> = {
  approved: 'אושרו',
  clean: 'מוכנים לאישור',
  eyes: 'דורשים מבט',
  // [Stage A] The upload stage, one step before 'בתמלול'. Its own word because
  // a file still climbing the wire is not being read by anything yet.
  uploading: 'בהעלאה',
  moving: 'בתמלול',
  failed: 'נכשל',
  // [Stage A/R9] Declared, never arrived — dead, but not a failure.
  not_received: 'לא הגיעו',
}

/**
 * THE DASHBOARD HEADLINE IS GONE (§5.1B).
 *
 * `selectHeadline` and the HEADLINE_* family said the same kind of thing as the
 * turn line — "here is what is happening and what you can do" — two sentences
 * deep, stacked, each derived separately. Whichever one she read first, the
 * other was redundant at best and contradicting at worst. The turn line is now
 * «the only thing she must read» (§5.1B) and there is exactly one of it.
 *
 * The identity clause the old headline carried is not lost: the identity wave
 * zone states it in its own title and sub-line, next to the pills it is about.
 */

/** ── §3.2 zone strings (P2 wave 2) — verbatim law ─────────────────────── */

// Header (D1). OD-1: the list is «המבחנים שלי», and `מקבץ` never appears.
export const BACK_ALL_BATCHES = 'המבחנים שלי'
export const BATCH_FALLBACK_NAME = (id8: string) => `מבחן ${id8}`
export const META_RUBRIC_PREFIX = 'מחוון:'
export const META_TESTS = (n: number) => (n === 1 ? 'מבחן אחד' : `${n} מבחנים`)  // AM3
export const META_CREATED = (rel: string) => `נוצר ${rel}`

// Transcribing (D7 · §5.3A). The heading names what Vivi is DOING, in the same
// words as the chip and the turn line — one vocabulary for one stage.
export const ZONE_GHOSTS_TITLE = () => 'ויוי קוראת את כתב היד'
export const ZONE_GHOSTS_SUB =
  'כל מבחן מופיע כאן ברגע שהוא מוכן — אפשר להתחיל לאשר בלי לחכות לכולם.'
/** §5.3A: shown ONLY when `total ≥ 2 && remaining === 1`. On a batch of one
 *  «כמעט שם — מבחן אחרון» is the whole batch described as a remainder, and on
 *  two-or-more-remaining it is simply untrue. */
export const GHOST_ALMOST_THERE = 'כמעט שם — מבחן אחרון בתמלול'
export const GHOST_QUEUED = 'בתור'
export const GHOST_RUNNING = 'קוראת עמוד אחר עמוד…'
export const GHOST_MORE_QUEUED = (n: number) =>
  n === 1 ? '+ אחד נוסף בתור' : `+ ${n} נוספים בתור`  // AM3
/** The ghost that overran. Says what happened and what it costs her — the
 *  source PDF is on the server, so the retry is one click and no re-upload.
 *  Deliberately NOT «נכשל»: nothing broke, it just took too long. */
export const GHOST_STUCK = 'לוקח יותר מדי זמן'
export const GHOST_STUCK_HINT = 'אפשר לנסות שוב — הקובץ כבר אצלנו, אין צורך להעלות מחדש'
export const GHOST_RETRY = 'נסי שוב'
export const NO_FILENAME = 'קובץ ללא שם'

/** [Stage B] The upload lane on the dashboard — the surface that replaces
 *  sitting on the upload page watching a bar. AM3 plural-aware; PROPOSED for
 *  §3.2. Feminine imperatives per OD5. */
export const ZONE_UPLOAD_TITLE = (n: number) =>
  n === 1 ? 'בהעלאה עכשיו — קובץ אחד' : `בהעלאה עכשיו — ${n}`
export const ZONE_UPLOAD_SUB =
  'התמלול מתחיל בכל קובץ ברגע שהוא מגיע — אפשר להתחיל לעיין במה שכבר כאן'
export const ZONE_UPLOAD_DONE_TITLE = 'ההעלאה הסתיימה'
/** The lane stays until she dismisses it when files were left behind, so the
 *  batch never quietly ends up short without her being told which ones. */
export const ZONE_UPLOAD_LEFT_BEHIND = (n: number) =>
  n === 1 ? 'קובץ אחד לא הועלה' : `${n} קבצים לא הועלו`
export const UPLOAD_LANE_DONE = 'הועלה'
export const UPLOAD_LANE_WAITING = 'ממתין'
export const UPLOAD_LANE_REMOVE = 'הסירי'
export const UPLOAD_LANE_DISMISS = 'סגירת רשימת ההעלאה'

// Identity wave (D4)
export const ZONE_WAVE_TITLE = (n: number) =>
  n === 1 ? 'זיהוי תלמידים — שם חדש אחד' : `זיהוי תלמידים — ${n} שמות חדשים`  // AM3
export const ZONE_WAVE_SUB =
  'אלה השמות כפי שנקראו מראש הדף. תקני איות בלחיצה על שם, ואז צרי את כולם.'
/** [§6, n=0] The zone with UNMATCHED items and no new names. It must not
 *  announce «0 שמות חדשים» over a button offering to create «0 תלמידים» —
 *  there is nothing to create, only documents to identify by opening them. */
export const ZONE_WAVE_TITLE_UNMATCHED_ONLY = 'זיהוי תלמידים'
export const ZONE_WAVE_SUB_UNMATCHED_ONLY =
  'ויוי לא הצליחה לקרוא שם תלמיד בראש הדף. פתחי כל מבחן ובחרי את התלמיד/ה.'
export const WAVE_PRIMARY = (n: number) =>
  n === 1 ? 'צרי ושייכי תלמיד אחד' : `צרי ושייכי ${n} תלמידים`  // AM3
export const WAVE_FOOTNOTE =
  'היצירה רק מוסיפה תלמידים לרשימה שלך. אף תמלול לא מאושר בלי החלטה שלך — מבחנים של תלמידים שנוצרו יעברו למוכנים לאישור וימתינו לך.'
export const WAVE_UNMATCHED_PILL = (filename: string) =>
  `שם לא זוהה בקובץ "${filename}" — פתחי לבדיקה`
export const WAVE_PILL_CONFLICT = 'כבר קיים תלמיד בשם זה'

/** ── §5.3C · THE TRIAGED GRID · section 2, the confidently-read ────────── */
export const ZONE_CLEAN_TITLE = (n: number) => `נקראו בביטחון מלא (${n})`
export const ZONE_CLEAN_SUB =
  'ויוי קראה את כל כתב היד בלי ספקות וזיהתה את התלמיד. אפשר לאשר את כולם בלחיצה אחת, או להציץ קודם.'
export const CLEAN_PRIMARY = (n: number) =>
  n === 1 ? 'אישור המבחן' : `אישור ${n} המבחנים`
/** The «peek before you commit» affordance — it opens the review surface for
 *  the FIRST clean transcription, so her first bulk approval is not blind. */
export const CLEAN_SECONDARY = 'הצגת תמלול אחד לדוגמה'
export const CLEAN_SHOW_ALL = (n: number) => `הצגת כל ${n} המבחנים`
export const CLEAN_CARD_BADGE = 'מוכן לאישור'
/** ZC-1 v2 (2026-08-23): identity-pending cards live in the clean section but
 *  are excluded from the bulk count until their student exists. */
export const CLEAN_PENDING_STUDENTS = (n: number) =>
  n === 1
    ? 'מבחן אחד ממתין ליצירת תלמיד — צרי אותו בזיהוי התלמידים למעלה'
    : `${n} ממתינים ליצירת תלמיד — צרי אותם בזיהוי התלמידים למעלה`

export const SKIP_NOTICE = (k: number, reasons: string) =>
  k === 1
    ? `מבחן אחד דולג — ${reasons}. הוא ממתין לבדיקה שלך.`
    : `${k} מבחנים דולגו — ${reasons}. הם ממתינים לבדיקה שלך.`
export const SKIP_REASON_FRAGMENTS: Record<string, string> = {
  flagged: 'סומנו לבדיקה',
  has_review_edits: 'נערכו ידנית',
  already_approved: 'כבר אושרו',
}

/** ── §5.3C · THE TRIAGED GRID · section 1, needs-a-look (rendered FIRST) ── */
export const ZONE_EYES_TITLE = (n: number) => `דורשים מבט שלך (${n})`
export const ZONE_EYES_SUB =
  'ויוי סימנה מקומות שלא הייתה בטוחה בהם. בדרך כלל פחות מדקה לכל מבחן.'
export const EYES_PRIMARY = (n: number) => `בדיקה (${n})`
export const EYES_ROW_CTA = 'בדיקה'
export const EYES_UNIDENTIFIED = 'לא זוהה'

/**
 * §5.3C · THE REASON LINE, in teacher words.
 *
 * Keyed on the triage reasons the backend ACTUALLY emits
 * (`batch_triage.compute_flag_verdict` — cross-pinned in
 * `tests/fixtures/flag_reason_vocabulary.json`). Nothing here invents a reason
 * the server cannot produce, and `flagReasonLabel`'s runtime fallback still
 * covers a reason this build has never heard of.
 *
 * The page-level VLM confidence reason (`low_confidence`) carries no page
 * number on the wire, so its line does not claim one: naming «עמוד 3» from a
 * payload that never said 3 is the invented-value failure FC exists to stop.
 */
export const REASON_UNCLEAR_PLACES = (k: number) =>
  `כתב יד לא ברור ב${placesCount(k)}`
export const REASON_LOW_CONFIDENCE = 'חלק מהעמודים לא נקראו בביטחון'
/** A DIFFERENT fact from the `[?]` count: the model read words and was unsure
 *  of them. It leaves no markers to count, so it gets a sentence rather than a
 *  number — quoting «ב0 מקומות» would be a figure about the wrong signal. */
export const REASON_LOW_LOGPROB = 'ויוי לא בטוחה בקריאה של חלק מהמילים'
export const REASON_STUDENT_UNIDENTIFIED = 'התלמיד לא זוהה'
export const REASON_STUDENT_UNMATCHED = 'השם לא נמצא ברשימת הכיתה'
export const REASON_EDITED = 'ערכת את התמלול — אישור פרטני'
/** The catch-all for `grounding_retry` and `segmentation_mismatch`: both mean
 *  «Vivi is unsure about part of the transcription» and neither has a sentence
 *  a teacher can act on more precisely without opening the document. */
export const REASON_GENERIC = 'ויוי לא בטוחה בחלק מהתמלול'

// Failed zone (D8; guidance strings kept from the pre-redesign card)
export const FAILED_TITLE = (filename: string) => `התמלול של ${filename} נכשל`
export const FAILED_RETRY = 'נסי שוב'
export const FAILED_GUIDE_NET = 'זוהתה בעיית רשת בשרת בזמן העיבוד. הקובץ שמור — אפשר לנסות שוב.'
export const FAILED_GUIDE_RETRYABLE = 'הקובץ שמור אצלנו — אפשר לנסות שוב בלחיצה. אם הבעיה חוזרת, פנו לתמיכה.'
// P5 conformance: §3.2 says "keep the existing net_verdict guidance strings",
// but KEEP never overrode the OD4 lock — this one still said `באצווה חדשה`
// inside the copy module itself. Guidance content unchanged; the banned word
// replaced.
export const FAILED_GUIDE_LEGACY = 'יש להעלות את הקובץ מחדש. אם הבעיה חוזרת — פנו לתמיכה.'

// Grading lane (D9, AM2 + AM3 singulars)
const laneChecked = (n: number) =>
  n === 1 ? 'מבחן אחד כבר נבדק' : `${n} מבחנים כבר נבדקו`
export const LANE_SUBORDINATE = (n: number) =>
  `בדיקת ציונים · ${laneChecked(n)} — הבדיקה נפתחת אחרי אישור התמלולים`
export const LANE_COMPLETED = (d: number, g: number) =>
  `ויוי בודקת את המבחנים לפי המחוון — ${laneChecked(d)}, ${g === 1 ? 'אחד בעבודה' : `${g} בעבודה`}`
export const LANE_CTA = 'לבדיקת הציונים'

// Review-surface strings the dashboard shares (D5 peek; P3 consumes more)
export const EMPTY_ANSWER_MARKER = 'תשובה ריקה — לא נמצא תוכן בסריקה'

// Review module (P3, §3.2)
export const POSITION_PRIMARY = (i: number, f: number) => `${i} מתוך ${f} לבדיקה`
export const POSITION_SECONDARY = (k: number, t: number) => `מבחן ${k} מתוך ${t}`
export const RAIL_LABEL = 'סומן בגלל:'
export const EMPTY_ANSWER_PLACEHOLDER =
  'אם התשובה קיימת בסריקה — אפשר להקליד אותה כאן, או להעביר אליה תוכן משאלה אחרת'
export const APPROVE_AND_CONTINUE = 'אישור והמשך'
// Answer view/edit split (table rendering, 2026-08-23). The raw text is always
// the source of truth; the grid is a display derivation over it.
export const ANSWER_VIEW_SHOW_RAW = 'הצגת הטקסט המקורי'
export const ANSWER_VIEW_SHOW_TABLE = 'הצגה כטבלה'
export const ANSWER_VIEW_FLAGS_HIDDEN = 'שורות מסומנות מוצגות רק בטקסט המקורי'
// Native table editing (2026-09-24): a cell edit never changes the grid (TBL-4).
export const ANSWER_CELL_HINT_PIPE = 'התו | מפריד בין תאים, ולכן אי אפשר להקליד אותו בתוך תא'
export const ANSWER_CELL_HINT_STRUCTURE =
  'שינוי זה ישנה את מבנה הטבלה ולא יישמר — אפשר לערוך אותו בטקסט המקורי'
export const ANSWER_CELL_ABSENT = 'אין תא כזה בטקסט המתומלל'
export const ANSWER_CELL_LABEL = (row: number, col: number) => `תא בשורה ${row}, עמודה ${col}`
export const ANSWER_TEXT_RUN_LABEL = 'טקסט התשובה'
export const SOFT_REFETCH_NOTE = 'הרענון נכשל — הנתונים יתעדכנו בהמשך'
export const INTERSTITIAL_TITLE = 'כל המבחנים שסומנו נבדקו'
export const INTERSTITIAL_BODY = (n: number) =>
  n === 1
    ? 'נשאר מבחן אחד שנקרא בביטחון מלא — לאשר אותו?'
    : `נשארו ${n} שנקראו בביטחון מלא — לאשר את כולם?`
/** A deep link to an item this exam does not contain. Found by the §2.3 gate
 *  once it learned to see Hebrew prefixes — it had been inlined here in a
 *  component, saying «לא נמצא במקבץ הזה», past every earlier sweep. */
export const REVIEW_ITEM_NOT_FOUND = 'המבחן המבוקש לא נמצא במבחן הזה'
export const INTERSTITIAL_BACK = 'חזרה לסיכום המבחן'
export const MOBILE_REVIEW_INTERSTITIAL =
  'הבדיקה הידנית בנויה למסך גדול — פתחי את המבחן מהמחשב. אפשר לעקוב אחרי ההתקדמות כאן.'

/**
 * THE MID-FLOW CELEBRATION IS GONE (§5.1F · §5.3E).
 *
 * `CompletionHero` fired a full green-check card the moment the last
 * TRANSCRIPTION was approved — the same card, the same ✓, the same shape she
 * would later see after signing the last grade. One visual for two different
 * milestones taught her that the first one was the end of something, on a
 * screen where four of six steps were still ahead.
 *
 * A finished stage is now a one-line strip (STRIP_TRANSCRIPTIONS_APPROVED), and
 * there is exactly ONE celebration in the flow — after the last signature. It
 * lives with the surface that renders it (`copy/grade-review.ts`, the `DONE_*`
 * family), and the «מהעלאה ועד…» statistic moved there with it, re-anchored to
 * the signature rather than to the transcription approval.
 */

// ── §5.2 · the upload page ────────────────────────────────────────────────
// She arrives here knowing nothing about how this works. Four things have to
// land before the first file is chosen: what she is uploading, what it will be
// graded against, the one-PDF-per-student rule, and what happens next.

export const UPLOAD_SUBTITLE = 'העלי סריקות PDF של מבחני התלמידים — קובץ אחד לכל תלמיד'
/** She must see what the papers will be graded against, on the page where she
 *  commits them — not two screens back. */
export const UPLOAD_RUBRIC_LINE = (rubricName: string) => `המחוון: ${rubricName}`
export const UPLOAD_RUBRIC_CHANGE = 'שינוי'
export const UPLOAD_NAME_LABEL = 'שם המבחן'
export const UPLOAD_NAME_HINT = 'נוצר אוטומטית מהמחוון, הכיתה והתאריך — אפשר לשנות'
export const UPLOAD_CLASS_HINT = 'בחירת כיתה עוזרת לויוי לזהות תלמידים אוטומטית מתוך הרשימה'
/** `max` is the REAL constraint (`MAX_FILES`, mirrored by the server's
 *  `MAX_DECLARED_TEST_COUNT`), never a number typed into a sentence. */
export const UPLOAD_DROPZONE = (max: number) =>
  `גררי לכאן סריקות PDF של המבחנים או לחצי לבחירה · קובץ אחד לכל תלמיד · עד ${max} קבצים`
export const UPLOAD_SCAN_HELP_LINK = 'איך סורקים נכון?'
/** Three lines, and the third is the one she needs: OD-5 — image formats are
 *  not accepted today, and a dropzone that silently refuses her phone photo
 *  teaches her the product is broken. */
export const UPLOAD_SCAN_HELP: readonly string[] = [
  'המבחן של כל תלמיד הוא קובץ PDF נפרד.',
  'כל העמודים של אותו תלמיד — באותו קובץ.',
  'כרגע רק PDF. צילום מהטלפון עדיין לא נתמך.',
]
export const UPLOAD_SCAN_HELP_CLOSE = 'סגירה'
export const UPLOAD_FILES_SUMMARY = (n: number) => testsCount(n)
/** n=0 counts nothing yet, so the disabled CTA claims nothing. */
export const UPLOAD_CTA = (n: number) =>
  n === 0 ? 'שליחה לוויוי' : `שליחה לוויוי (${testsCount(n)})`
/** One sentence, under the button, that sets the whole model before she starts. */
export const UPLOAD_CTA_HELPER =
  'ויוי תקרא את כתב היד ותקליד אותו. אחר כך תאשרי ותשלחי לבדיקת ציונים.'
export const UPLOAD_BACK = 'חזרה'
export const UPLOAD_DUP_CHIP = 'כפילות אפשרית — שם וגודל זהים'
export const UPLOAD_TRUNCATION_NOTICE = (max: number) =>
  `נבחרו יותר מ-${max} קבצים — נכללו ${max} הראשונים`
export const UPLOAD_SKIPPED_SUMMARY = (k: number, details: string) =>
  k === 1 ? `קובץ אחד לא נכלל: ${details}` : `${k} קבצים לא נכללו: ${details}`
export const UPLOAD_FILE_FAILED = (filename: string) => `ההעלאה של ${filename} נכשלה — נסי שוב`
export const UPLOAD_RETRY = 'נסי שוב'
export const UPLOAD_CLEAR_ALL = 'הסרת הכל'
export const UPLOAD_CTA_DISABLED_REASON = 'בחרי לפחות קובץ PDF אחד כדי להתחיל'
/* [Stage B / R3] `UPLOAD_CONTINUE` is DELETED, not orphaned. Decision 4's
 * explicit continue existed only to end a wait that no longer happens: she is
 * on the batch page before the first file finishes. */
export const UPLOAD_UPLOADING = 'מעלה…'
export const UPLOAD_CREATE_ERROR = 'שגיאה ביצירת המבחן'
/** [Stage B / R10] One uploading batch at a time. Two simultaneous uploads
 *  would share one lane with no way to tell whose progress is whose, so she is
 *  pointed at the one already running instead. */
export const UPLOAD_BUSY_NOTICE = 'העלאה אחרת עדיין רצה — אפשר להתחיל מבחן חדש כשהיא תסתיים'
export const UPLOAD_BUSY_LINK = 'למבחן שבהעלאה'
/** [Stage B] Signing out navigates hard and takes in-flight transfers with it.
 *  Every OTHER navigation is now safe, which is precisely why this one must
 *  ask — nothing else in the app teaches her that leaving costs anything. */
export const LOGOUT_WHILE_UPLOADING =
  'יש קבצים שעדיין בהעלאה. יציאה מהחשבון תעצור אותם. להתנתק בכל זאת?'

// ── §5.7 · the list. OD-1 (ruled): batches ARE «המבחנים שלי» — an exam event
// named by rubric · class · date. The word `מקבץ` stays in the code, the route
// and the DB, and never reaches a screen.
export const LIST_TITLE = 'המבחנים שלי'
export const LIST_SUBTITLE = 'כל המבחנים שהעלית — לפי סדר היצירה'
/** §5.7 — the two zoom levels of one section, as tabs rather than two sidebar
 *  entries (see ExamsTabs). */
/** The tab strip's own name — distinct from the page heading, because the
 *  sidebar is a <nav> too and two identically-named ones are ambiguous. */
export const TABS_LABEL = 'מעבר בין תצוגות'
export const TAB_BY_EXAM = 'לפי מבחן'
export const TAB_GRADED_TESTS = 'כל המבחנים הבדוקים'
export const LIST_ACTION_NEEDS_EYES = (f: number) =>
  f === 1 ? 'מבחן אחד דורש מבט' : `${f} דורשים מבט`
export const LIST_ACTION_TRANSCRIBING = (t: number) =>
  t === 1 ? 'מבחן אחד בתמלול' : `${t} בתמלול`           // AM3 proposed
export const LIST_ACTION_ALL_APPROVED = 'הכל אושר ✓'
/** Everything past the transcription gate but short of a signature. It covers
 *  two different waits (a bulk accept, a grade review), so it names neither —
 *  the row's status chip says which stage the batch is in. */
export const LIST_ACTION_PENDING = (n: number) =>
  n === 1 ? 'מבחן אחד ממתין לך' : `${n} מבחנים ממתינים לך`
export const LIST_ACTION_FAILED = (n: number) =>
  n === 1 ? 'תמלול אחד נכשל' : `${n} תמלולים נכשלו`
/** [Stage A] Declared files still on the wire. AM3 plural-aware; PROPOSED
 *  for §3.2. The list is the one batch surface with no upload lane, so this
 *  line is where a still-arriving batch says so. */
export const LIST_ACTION_UPLOADING = (n: number) =>
  n === 1 ? 'קובץ אחד בהעלאה' : `${n} קבצים בהעלאה`
/** [Stage A / R9] Declared, never arrived, and the batch has gone quiet past
 *  the backstop. Deliberately NOT phrased as a failure: nothing was transcribed
 *  and nothing broke — the file never reached us and is still on her machine,
 *  so the sentence that helps her is the one that says to send it again. */
export const LIST_ACTION_NOT_RECEIVED = (n: number) =>
  n === 1 ? 'קובץ אחד לא הגיע — אפשר להעלות אותו שוב'
    : `${n} קבצים לא הגיעו — אפשר להעלות אותם שוב`
export const LIST_EMPTY = 'אין מבחנים עדיין'
export const LIST_EMPTY_CTA = 'העלי מבחן ראשון'
export const LIST_NEW_BATCH = 'מבחן חדש'

/** Live-E2E fix (2026-08-22, failure 1): while uploads are still in flight
 *  the transcription is ALREADY running server-side (jobs enqueue per
 *  append), but the teacher saw no signal of it — she sat on the upload page
 *  for minutes believing nothing was happening. AM3 plural-aware; PROPOSED
 *  for §3.2. */
export const UPLOAD_LIVE_STARTED = 'התמלול כבר החל ברקע'
export const UPLOAD_LIVE_READY = (n: number) =>
  n === 1 ? 'תמלול אחד כבר מוכן לעיון' : `${n} תמלולים כבר מוכנים לעיון`

/** D1 (closeout): files selected but never uploaded have no record in the
 *  batch — the dashboard says so explicitly rather than showing a tidy batch
 *  that is quietly short. AM3 plural-aware; PROPOSED for §3.2. */
export const UPLOAD_FAILURES_NOTICE = (names: string[]) =>
  names.length === 1
    ? `קובץ אחד לא הועלה — ${names[0]}. אפשר להעלות אותו שוב.`
    : `${names.length} קבצים לא הועלו — ${names.join(', ')}. אפשר להעלות אותם שוב.`

/**
 * ── §5.3B · the first-batch explainer ─────────────────────────────────────
 *
 * Three lines, shown on her FIRST batch only (`is_first_batch`) and
 * never again. It answers the question the whole transcription stage begs and
 * no screen was answering: why is a machine typing out my students' work, and
 * what is my part in it.
 *
 * The third line is the load-bearing one — it says the marks exist so the grade
 * lands on what the student actually wrote, which is the promise the review
 * gate is keeping.
 */
export const EXPLAINER_LINES: readonly string[] = [
  'ויוי קוראת את כתב היד של כל תלמיד ומקלידה אותו.',
  'איפה שכתב היד לא ברור — היא מסמנת במקום לנחש.',
  'את מכריעה בסימונים, כדי שהציון יינתן על מה שהתלמיד באמת כתב.',
]
export const EXPLAINER_DISMISS = 'הבנתי'

/**
 * ── §5.3D · the completeness sentence ─────────────────────────────────────
 *
 * Replaces «6 עמודים · 6 תשובות», which counted containers rather than saying
 * whether anything is missing. Selection-aware: on a «choose 4 of 6» exam the
 * three questions the student did not answer are not gaps, and naming them
 * would send her looking for work nobody owed.
 *
 * UNDER A GROUP, COUNTS ONLY — never which questions are "missing". The student
 * chose; there is nothing to find.
 */
export const COMPLETE_ALL = (n: number) => `נמצאו תשובות לכל ${n} השאלות`
export const COMPLETE_MISSING = (found: number, total: number, keys: string) =>
  `נמצאו ${found} מתוך ${total} סעיפים — ${keys} לא נמצאו`
export const COMPLETE_MISSING_PREFIX = (keys: string) => `${keys} לא נמצאו`
export const COMPLETE_GROUP_OK = (k: number, of: number) =>
  `נמצאו תשובות ל-${k} מתוך ${of} שאלות, כנדרש — אין תשובות חסרות`
export const COMPLETE_GROUP_SHORT = (found: number, required: number) =>
  `נמצאו תשובות ל-${found} שאלות מתוך ${required} הנדרשות`
/** OD-6: SURFACE the count, decide nothing. Which of the extra answers counts
 *  is a grading-constitution question, not a UI one. */
export const COMPLETE_GROUP_EXCESS = (found: number, required: number) =>
  `נמצאו תשובות ל-${found} שאלות — נדרשות ${required}`
export const COMPLETE_PARTIAL_QUESTION = (q: string, letters: string) =>
  `בשאלה ${q} חסר ${letters}`
/**
 * The selection structure could not be read — a question in two groups, or a
 * group asking for more answers than it has members. It says so instead of
 * reporting a shortfall it cannot substantiate: on a «choose k of N» exam a
 * wrong requirement reads as the student having skipped work he was never set.
 */
export const COMPLETE_NOT_COMPUTABLE =
  'לא ניתן לבדוק כאן תשובות חסרות — מבנה הבחירה במחוון לא ברור'
export const COMPLETE_CLAUSE_SEP = ' · '
export const COMPLETE_APPEND_SEP = '; '
export const COMPLETE_GROUP_LABEL = (label: string, clause: string) =>
  `"${label}": ${clause}`

/** One home for the flag-reason labels (C1): re-exported; the definition
 * stays in types/batch.ts until the P5 sweep migrates it in. */
export { FLAG_REASON_LABELS } from '@/types/batch'

/**
 * F3 AT RUNTIME (closeout/B1): the cross-pinned vocabulary test protects the
 * REPO, not the deploy window — backend and frontend ship to different
 * targets, so a new reason string can reach Cloud Run minutes before Vercel
 * catches up, and CI's green says nothing about those minutes. Every render
 * site goes through here, so an unknown reason degrades to a generic HEBREW
 * label instead of leaking a raw Latin enum onto an RTL screen.
 */
export function flagReasonLabel(reason: string): string {
  const label = FLAG_REASON_LABELS_MAP[reason]
  if (label) return label
  if (typeof console !== 'undefined') {
    console.warn(`[vivi] unknown flag reason "${reason}" — add it to FLAG_REASON_LABELS and the cross-pinned vocabulary`)
  }
  return FLAG_REASON_UNKNOWN
}

export const FLAG_REASON_UNKNOWN = 'סומן לבדיקה'
