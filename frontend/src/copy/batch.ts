import { answersCount, pagesCount } from '@/utils/hebrew-plural'
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

/** Fixed batch-status labels (§3.2). `in_progress` is context-dependent —
 * always render it via batchStatusLabel(). */
export const BATCH_STATUS_LABELS: Record<string, string> = {
  completed: 'הושלם',
  partially_completed: 'הושלם חלקית',
  failed: 'נכשל',
  pending: 'ממתין',
}

/**
 * §3.2: `in_progress` → 'בתמלול' while anything is still transcribing
 * (rollup.transcribing > 0 or active jobs exist), else 'ממתין להחלטות'.
 * Latin enums never render (F3 grep gate); unknown values fall through raw
 * only for forward-compat with statuses this build has never heard of.
 */
export function batchStatusLabel(
  status: string,
  opts?: { transcribing?: number; activeJobs?: number },
): string {
  if (status === 'in_progress') {
    const inFlight = (opts?.transcribing ?? 0) + (opts?.activeJobs ?? 0)
    return inFlight > 0 ? 'בתמלול' : 'ממתין להחלטות'
  }
  return BATCH_STATUS_LABELS[status] ?? status
}

/** Dashboard load/poll strings touched by F1 (OD4: מקבץ, never אצווה). */
export const BATCH_LOAD_ERROR = 'שגיאה בטעינת המקבץ'
export const BATCH_NOT_FOUND = 'המקבץ לא נמצא'
export const DISMISS_NOTICE_LABEL = 'סגירת ההודעה'
export const RETRY_ERROR = 'שגיאה בניסיון החוזר'

/** Honesty-bar legend labels (D2) — vocabulary drawn from the §3.2 zone
 * titles/status table; keyed by BarSegmentKind. */
export const SEGMENT_LABELS: Record<string, string> = {
  approved: 'אושרו',
  clean: 'נקיים',
  eyes: 'דורשים עיון',
  moving: 'בתמלול',
  failed: 'נכשל',
}

/**
 * Dashboard headline (D3) — §3.2 with AM3 (RATIFIED 2026-08-18): every
 * count-bearing builder is PLURAL-AWARE. Both the n>1 templates and the
 * n===1 singulars are now §3.2 law (inlined there as `(n=1: …)`; the diff
 * table lives in batch_redesign_LOG.md, P3 wave 0).
 */
export const HEADLINE_IDENTITY = (n: number) =>
  n === 1
    ? 'ויוי זיהתה תלמיד חדש בכתב היד — בדקי את האיות וצרי אותו.'
    : `ויוי זיהתה ${n} תלמידים חדשים בכתב היד — בדקי את האיות וצרי את כולם.`
export const HEADLINE_IDENTITY_TRANSCRIBING_TAIL = ' השאר בדרך.'
export const HEADLINE_NEEDS_EYES = (f: number) =>
  f === 1 ? 'מבחן אחד צריך את העיניים שלך' : `${f} מבחנים צריכים את העיניים שלך`
export const HEADLINE_CLEAN_READY = (c: number) =>
  c === 1 ? 'מבחן אחד מוכן לאישור מרוכז' : `${c} מוכנים לאישור מרוכז`
export const HEADLINE_CLAUSE_SEP = ' · '
export const HEADLINE_LAST_TRANSCRIBING = (t: number) =>
  t === 1 ? 'כמעט שם — מבחן אחרון בתמלול' : `כמעט שם — ${t} מבחנים אחרונים בתמלול`
export const HEADLINE_ALL_APPROVED = (n: number) =>
  n === 1 ? 'סיימת — המבחן אושר' : `סיימת — כל ${n} המבחנים אושרו`

/** ── §3.2 zone strings (P2 wave 2) — verbatim law ─────────────────────── */

// Header (D1)
export const BACK_ALL_BATCHES = 'כל המקבצים'
export const BATCH_FALLBACK_NAME = (id8: string) => `מקבץ ${id8}`
export const META_RUBRIC_PREFIX = 'מחוון:'
export const META_TESTS = (n: number) => (n === 1 ? 'מבחן אחד' : `${n} מבחנים`)  // AM3
export const META_CREATED = (rel: string) => `נוצר ${rel}`

// Transcribing ghosts (D7)
export const ZONE_GHOSTS_TITLE = (n: number) => `בתמלול עכשיו — ${n}`
export const ZONE_GHOSTS_SUB =
  'כל מבחן נוחת כאן ברגע שהוא מוכן. אפשר להתחיל לעבוד בלי לחכות לכולם.'
export const GHOST_QUEUED = 'בתור'
export const GHOST_RUNNING = 'קוראת עמוד אחר עמוד…'
export const GHOST_MORE_QUEUED = (n: number) =>
  n === 1 ? '+ אחד נוסף בתור' : `+ ${n} נוספים בתור`  // AM3
export const NO_FILENAME = 'קובץ ללא שם'

// Identity wave (D4)
export const ZONE_WAVE_TITLE = (n: number) =>
  n === 1 ? 'זיהוי תלמידים — שם חדש אחד' : `זיהוי תלמידים — ${n} שמות חדשים`  // AM3
export const ZONE_WAVE_SUB =
  'אלה השמות כפי שנקראו מראש הדף. תקני איות בלחיצה על שם, ואז צרי את כולם.'
export const WAVE_PRIMARY = (n: number) =>
  n === 1 ? 'צרי ושייכי תלמיד אחד' : `צרי ושייכי ${n} תלמידים`  // AM3
export const WAVE_FOOTNOTE =
  'היצירה רק מוסיפה תלמידים לרשימה שלך. אף תמלול לא מאושר בלי החלטה שלך — מבחנים של תלמידים שנוצרו יעברו ל"נקיים" וימתינו לאישור.'
export const WAVE_UNMATCHED_PILL = (filename: string) =>
  `שם לא זוהה בקובץ "${filename}" — פתחי לעיון`
export const WAVE_PILL_CONFLICT = 'כבר קיים תלמיד בשם זה'

// Clean panel (D5)
export const ZONE_CLEAN_TITLE = (n: number) => `נקיים — מוכנים לאישור מרוכז (${n})`
export const ZONE_CLEAN_SUB =
  'תמלול תקין, תלמיד מזוהה, בלי דגלים. האישור חותם אותם כפי שהם ושולח לבדיקת ציונים.'
export const CLEAN_PRIMARY = (n: number) =>
  n === 1 ? 'אשרי את המבחן (1)' : `אשרי את כולם (${n})`  // AM3: "כולם" of one is broken
export const CLEAN_SECONDARY = 'בדיקה ידנית'
export const CLEAN_OPEN_FULL = 'פתחי לבדיקה מלאה ←'
export const CLEAN_SHOW_ALL = (n: number) => `הצגת כל ${n} השורות`
// AM3 (ratified): pages/answers ride the existing hebrew-plural builders
// (עמוד אחד / תשובה אחת) — now §3.2 law for the clean-row meta.
export const CLEAN_ROW_META = (student: string, pages: number, answers: number) =>
  `← ${student} · ${pagesCount(pages)} · ${answersCount(answers)}`
export const SKIP_NOTICE = (k: number, reasons: string) =>
  k === 1
    ? `מבחן אחד דולג — ${reasons}. הוא ממתין לעיון.`
    : `${k} מבחנים דולגו — ${reasons}. הם ממתינים לעיון.`  // AM3
export const SKIP_REASON_FRAGMENTS: Record<string, string> = {
  flagged: 'סומנו לעיון',
  has_review_edits: 'נערכו ידנית',
  already_approved: 'כבר אושרו',
}

// Needs-eyes queue (D6)
export const ZONE_EYES_TITLE = (n: number) => `דורשים עיון — ${n}`
export const ZONE_EYES_SUB =
  'ויוי מסמנת בדיוק למה. סבב העיון עובר ביניהם ברצף, עם מקלדת, וממשיך אוטומטית אחרי כל אישור.'
export const EYES_PRIMARY = (n: number) => `התחילי סבב עיון (${n})`
export const EYES_ROW_CTA = 'פתחי לעיון'
export const EYES_UNMATCHED_NOTE = 'שם תלמיד לא זוהה'
export const CHIP_MISSING_WITH_COUNT = (n: number) => `תשובות חסרות · ${n}`
export const CHIP_UNCLEAR_WITH_COUNT = (n: number) => `תוכן לא קריא [?] · ${n}`
export const CHIP_EDITED = 'נערך ידנית'

// Failed zone (D8; guidance strings kept from the pre-redesign card)
export const FAILED_TITLE = (filename: string) => `התמלול של ${filename} נכשל`
export const FAILED_RETRY = 'נסי שוב'
export const FAILED_GUIDE_NET = 'זוהתה בעיית רשת בשרת בזמן העיבוד. הקובץ שמור — אפשר לנסות שוב.'
export const FAILED_GUIDE_RETRYABLE = 'הקובץ שמור אצלנו — אפשר לנסות שוב בלחיצה. אם הבעיה חוזרת, פנו לתמיכה.'
// P5 conformance: §3.2 says "keep the existing net_verdict guidance strings",
// but KEEP never overrode the OD4 lock — this one still said `באצווה חדשה`
// inside the copy module itself. Guidance content unchanged; the banned word
// replaced.
export const FAILED_GUIDE_LEGACY = 'יש להעלות את הקובץ מחדש במקבץ חדש. אם הבעיה חוזרת — פנו לתמיכה.'

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
export const POSITION_PRIMARY = (i: number, f: number) => `${i} מתוך ${f} לעיון`
export const POSITION_SECONDARY = (k: number, t: number) => `מבחן ${k} מתוך ${t} במקבץ`
export const RAIL_LABEL = 'סומן בגלל:'
export const EMPTY_ANSWER_PLACEHOLDER =
  'אם התשובה קיימת בסריקה — אפשר להקליד אותה כאן, או להעביר אליה תוכן משאלה אחרת'
export const APPROVE_AND_CONTINUE = 'אישור והמשך'
export const SOFT_REFETCH_NOTE = 'הרענון נכשל — הנתונים יתעדכנו בהמשך'
export const INTERSTITIAL_TITLE = 'כל המבחנים שסומנו נבדקו'
export const INTERSTITIAL_BODY = (n: number) =>
  n === 1 ? 'נשאר מבחן נקי אחד — לאשר אותו?' : `נשארו ${n} נקיים — לאשר את כולם?`  // AM3
export const INTERSTITIAL_BACK = 'חזרה לסיכום המקבץ'
export const MOBILE_REVIEW_INTERSTITIAL =
  'הבדיקה הידנית בנויה למסך גדול — פתחי את המקבץ מהמחשב. אפשר לעקוב אחרי ההתקדמות כאן.'

// Completion hero (D10 + AM3 singulars)
export const HERO_TITLE = (n: number) =>
  n === 1 ? 'המבחן אושר' : `כל ${n} המבחנים אושרו`
export const HERO_DURATION = (minutes: number) =>
  minutes === 1
    ? 'מהעלאה ועד אישור אחרון — דקה אחת'
    : `מהעלאה ועד אישור אחרון — ${minutes} דקות`
export const HERO_STAT_APPROVED = 'אושרו'
export const HERO_STAT_STUDENTS = 'תלמידים חדשים נוצרו'

// Upload surface (P4, §3.2 + U2). Count-bearing builders are AM3
// plural-aware; the n=1 and n=0 forms were SIGNED OFF at the P4 review
// (2026-08-19) and are inlined in §3.2 — this module and the spec agree.
export const UPLOAD_NAME_LABEL = 'שם המקבץ'
export const UPLOAD_NAME_HINT = 'נוצר אוטומטית מהמחוון, הכיתה והתאריך — אפשר לשנות'
export const UPLOAD_CLASS_HINT = 'בחירת כיתה עוזרת לויוי לזהות תלמידים אוטומטית מתוך הרשימה'
export const UPLOAD_DROPZONE = 'גררי לכאן קבצי PDF או לחצי לבחירה (עד 50 קבצים)'
// AM3, signed off (incl. the n=0 case caught by matrix inspection: a disabled
// CTA must not claim "(0 מבחנים)" — it counts nothing yet).
export const UPLOAD_CTA = (n: number) =>
  n === 0 ? 'התחלת תמלול'
    : n === 1 ? 'התחלת תמלול (מבחן אחד)'
      : `התחלת תמלול (${n} מבחנים)`
export const UPLOAD_DUP_CHIP = 'כפילות אפשרית — שם וגודל זהים'
export const UPLOAD_TRUNCATION_NOTICE = 'נבחרו יותר מ-50 קבצים — נכללו 50 הראשונים'
export const UPLOAD_SKIPPED_SUMMARY = (k: number, details: string) =>
  k === 1 ? `קובץ אחד לא נכלל: ${details}` : `${k} קבצים לא נכללו: ${details}`  // AM3 proposed
export const UPLOAD_FILE_FAILED = (filename: string) => `ההעלאה של ${filename} נכשלה — נסי שוב`
export const UPLOAD_RETRY = 'נסי שוב'
export const UPLOAD_CLEAR_ALL = 'נקי הכל'          // U2 (feminine per OD5)
export const UPLOAD_CTA_DISABLED_REASON = 'בחרי לפחות קובץ PDF אחד כדי להתחיל'
/** Decision 4 (P4 plan): explicit continue once ≥1 landed while failures
 *  remain visible. Feminine imperative per OD5 — proposed alongside AM3. */
export const UPLOAD_CONTINUE = 'המשיכי למקבץ'
export const UPLOAD_UPLOADING = 'מעלה…'
export const UPLOAD_CREATE_ERROR = 'שגיאה ביצירת המקבץ'  // OD4: מקבץ, never אצווה

// Batches list page (P5/L1, §3.2). Count-bearing lines are AM3 plural-aware;
// the n=1 forms are PROPOSED in the P5 plan (owner sign-off at the P5 review),
// per AM3's new-surface clause.
export const LIST_TITLE = 'המקבצים שלי'
export const LIST_SUBTITLE = 'כל המקבצים שלך — לפי סדר היצירה'
export const LIST_ACTION_NEEDS_EYES = (f: number) =>
  f === 1 ? 'מבחן אחד דורש עיון' : `${f} דורשים עיון`   // AM3 proposed
export const LIST_ACTION_TRANSCRIBING = (t: number) =>
  t === 1 ? 'מבחן אחד בתמלול' : `${t} בתמלול`           // AM3 proposed
export const LIST_ACTION_ALL_APPROVED = 'הכל אושר ✓'
/** INTERIM (P5 open decision, Option B): the list payload cannot split
 *  clean|needs-eyes, so the pending line counts every test still owing the
 *  teacher a decision. Not new vocabulary — §3.2 already uses
 *  `ממתין להחלטות` as the in_progress status label for this exact state.
 *  Becomes §3.2's `{F} דורשים עיון` verbatim if Option A is approved. */
export const LIST_ACTION_PENDING = (n: number) =>
  n === 1 ? 'מבחן אחד ממתין להחלטה' : `${n} ממתינים להחלטה`
export const LIST_ACTION_FAILED = (n: number) =>
  n === 1 ? 'תמלול אחד נכשל' : `${n} תמלולים נכשלו`
export const LIST_EMPTY = 'אין מקבצים עדיין'
export const LIST_EMPTY_CTA = 'צרי מקבץ ראשון'
export const LIST_NEW_BATCH = 'מקבץ חדש'   // was `אצווה חדשה` (OD4)

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
