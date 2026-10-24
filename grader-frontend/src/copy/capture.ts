/**
 * In-house scanning — every string (PR_in_house_scanning.md §8). Brand voice:
 * calm, specific, brief; no exclamation marks.
 *
 *   STUDENT surfaces speak in the PLURAL imperative (gender-neutral: צלמו).
 *   TEACHER surfaces speak to her in the feminine singular (צלמי).
 *
 * The shared capture flow takes its strings as a value (`FlowCopy`), so the
 * same component speaks to each audience in its own voice.
 */

export interface FlowCopy {
  camera: string
  gallery: string
  nextPage: string
  maxPages: string
  uploading: (n: number) => string
  uploadIncomplete: string
  uploadFailed: string
  retry: string
  reset: string
  fullFrame: string
  rotate: string
  retake: string
  remove: string
  moveUp: string
  moveDown: string
  pageN: (n: number) => string
  quality: Record<'blurry' | 'too_far' | 'glare' | 'edges_not_found', string>
  badgeUploading: string
  badgeReady: string
  badgeWarning: string
  noPagesYet: string
  unsupportedFile: string
  tooLarge: string
  actionFailed: string
  failedUploads: (n: number) => string
}

export const STUDENT_FLOW: FlowCopy = {
  camera: 'צילום עמוד',
  gallery: 'בחירה מהגלריה',
  nextPage: 'צילום העמוד הבא',
  maxPages: 'הגעתם למקסימום של 20 עמודים',
  uploading: (n) => (n === 1 ? 'מעלה עוד עמוד אחד…' : `מעלה עוד ${n} עמודים…`),
  uploadIncomplete: 'העלאה לא הושלמה — צלמו שוב',
  uploadFailed: 'ההעלאה נכשלה',
  retry: 'ניסיון נוסף',
  reset: 'איפוס',
  fullFrame: 'כל התמונה',
  rotate: 'סיבוב',
  retake: 'צילום מחדש',
  remove: 'מחיקה',
  moveUp: 'הזזה למעלה',
  moveDown: 'הזזה למטה',
  pageN: (n) => `עמוד ${n}`,
  quality: {
    blurry: 'התמונה יצאה מטושטשת. כדאי לצלם שוב.',
    too_far: 'כדאי להתקרב לדף.',
    glare: 'יש השתקפות על הדף. כדאי לשנות זווית.',
    edges_not_found: 'לא זוהו קצוות הדף. אפשר לגרור את הפינות.',
  },
  badgeUploading: 'בהעלאה',
  badgeReady: 'מוכן',
  badgeWarning: 'כדאי לבדוק',
  noPagesYet: 'עוד לא צילמתם עמודים',
  unsupportedFile: 'אפשר להעלות רק תמונות (JPG, PNG, HEIC)',
  tooLarge: 'התמונה גדולה מדי (עד 50MB). צלמו שוב.',
  actionFailed: 'השינוי לא נשמר. נסו שוב.',
  failedUploads: (n) => (n === 1 ? 'עמוד אחד לא עלה — נסו שוב או מחקו אותו' : `${n} עמודים לא עלו — נסו שוב או מחקו אותם`),
}

export const TEACHER_FLOW: FlowCopy = {
  ...STUDENT_FLOW,
  maxPages: 'הגעת למקסימום של 20 עמודים',
  uploadIncomplete: 'העלאה לא הושלמה — צלמי שוב',
  noPagesYet: 'עוד לא צילמת עמודים של התלמיד הזה',
  gallery: 'העלאת תמונות',
  tooLarge: 'התמונה גדולה מדי (עד 50MB). צלמי שוב.',
  actionFailed: 'השינוי לא נשמר. נסי שוב.',
  failedUploads: (n) => (n === 1 ? 'עמוד אחד לא עלה — נסי שוב או מחקי אותו' : `${n} עמודים לא עלו — נסי שוב או מחקי אותם`),
}

// ---------------------------------------------------------------------------
// the student page (/s/[token]) — plural
// ---------------------------------------------------------------------------

export const S = {
  invalid: 'הקישור לא תקין. בקשו מהמורה קישור חדש.',
  notYetOpen: (date: string) => `הקישור ייפתח ביום המבחן, ${date}.`,
  closed: 'הקישור נסגר. אם לא הספקתם, פנו למורה.',
  resumed: (n: number, time: string) =>
    `כבר שלחתם ${n === 1 ? 'עמוד אחד' : `${n} עמודים`} בשעה ${time}. אפשר להוסיף, להחליף או למחוק עמודים ולשמור שוב.`,
  askName: 'איך קוראים לך? (שם פרטי ושם משפחה)',
  namePlaceholder: 'שם מלא',
  continue: 'המשך',
  isThisYou: (name: string) => `${name}?`,
  yesMe: 'כן, זה אני',
  notMe: 'לא, זה לא אני',
  notOnRoster: 'השם לא מופיע ברשימת הכיתה. נוסיף אותך כתלמיד חדש, והמורה תאשר.',
  addAsNew: 'הוספה כתלמיד/ה חדש/ה',
  fixName: 'תיקון השם',
  instructionsTitle: 'לפני שמצלמים',
  instructions: [
    'מניחים את הדף על משטח שטוח וכהה',
    'כל הדף בתוך התמונה',
    'בלי צל של היד או הטלפון',
  ],
  done: 'סיימתי',
  reviewTitle: 'בדיקה לפני שליחה',
  save: 'שמירה ושליחה למורה',
  saving: 'שולחים…',
  sent: (n: number) =>
    `נשלח. ${n === 1 ? 'עמוד אחד הגיע' : `${n} עמודים הגיעו`} למורה. אפשר לחזור לקישור הזה היום כדי להוסיף או להחליף עמודים.`,
  backToEdit: 'הוספה או החלפה של עמודים',
  genericError: 'משהו השתבש. נסו שוב בעוד רגע.',
  tryAgain: 'ניסיון נוסף',
  loading: 'טוען…',
}

// ---------------------------------------------------------------------------
// the teacher capture page (/capture/[batchId]) — feminine
// ---------------------------------------------------------------------------

export const T = {
  savedCount: (k: number) => (k === 1 ? 'נשמר תלמיד אחד' : `נשמרו ${k} תלמידים`),
  unsavedResume: (k: number) => (k === 1 ? 'תלמיד אחד עדיין לא נשמר' : `${k} תלמידים עדיין לא נשמרו`),
  detecting: 'מזהה את השם בעמוד הראשון…',
  foundMatch: (name: string) => `נמצאה התאמה: ${name}`,
  whoIsThis: 'של מי המבחן?',
  nextStudent: 'התלמיד הבא',
  save: 'שמירה',
  saving: 'שומרת…',
  missingPages: 'צלמי לפחות עמוד אחד',
  missingStudent: 'בחרי את התלמיד',
  waitingUploads: 'מחכים שהעמודים יסיימו לעלות',
  nothingToSave: 'אין עדיין מבחן מוכן לשמירה — צלמי עמודים ובחרי תלמיד',
  loadFailed: 'לא הצלחנו לטעון את הצילום. רענני את הדף ונסי שוב.',
  savedToast: (k: number) => (k === 1 ? 'מבחן אחד נשלח לעיבוד.' : `${k} מבחנים נשלחו לעיבוד.`),
  notSaved: 'לא נשמרו:',
  duplicateTitle: (name: string, n: number, time: string | null) =>
    `כבר יש מבחן של ${name} בקבוצה הזאת (${n === 1 ? 'עמוד אחד' : `${n} עמודים`}${time ? `, ${time}` : ''}).`,
  replaceExisting: 'החלפת המבחן הקיים',
  cancel: 'ביטול',
  sessionExpired: 'פג תוקף החיבור מהטלפון — סרקי שוב את הקוד מהמחשב',
  student: (n: number) => `תלמיד ${n}`,
  loading: 'טוען…',
}

// ---------------------------------------------------------------------------
// the batch detail panels — feminine
// ---------------------------------------------------------------------------

export const P = {
  // The home page's third card: straight to a rubric, then to the link form.
  homeLinkTitle: 'יצירת לינק לתלמידים',
  homeLinkSubtitle: 'כאן תלמידים יוכלו לצלם את התשובות שלהם ולעלות לVivi בעת הגשת המבחן',
  homeLinkPickRubric: 'בחרי את המחוון של המבחן שהתלמידים יצלמו',
  homeLinkCreating: 'יוצרת את הקבוצה…',
  captureButton: 'צילום מבחנים',
  handoffTitle: 'צילום מבחנים',
  handoffScan: 'סרקי עם הטלפון כדי לצלם',
  handoffDesktop: 'או העלי תמונות מהמחשב',
  handoffExpires: 'הקוד תקף ל-10 דקות',
  handoffFailed: 'לא הצלחנו ליצור קוד לטלפון.',
  retryFailed: 'הניסיון הנוסף לא יצא לדרך — נסי שוב בעוד רגע',
  linkTitle: 'קישור לצילום על ידי התלמידים',
  linkExplain: 'קישור אחד לכל כיתה. לכיתה נוספת, פתחי קבוצת בדיקה נפרדת עם קישור משלה.',
  examDate: 'תאריך המבחן',
  className: 'כיתה',
  pickClass: 'בחירת כיתה',
  newClass: 'כיתה חדשה',
  newClassName: 'שם הכיתה',
  createLink: 'יצירת קישור',
  linkState: { not_yet_open: 'ייפתח ביום המבחן', open: 'פתוח', closed: 'סגור' } as Record<string, string>,
  showQr: 'הצגת QR על המסך',
  copyLink: 'העתקת קישור',
  copied: 'הקישור הועתק',
  shareWhatsapp: 'שיתוף בוואטסאפ',
  closeLink: 'סגירת הקישור',
  reopenLink: 'פתיחה מחדש',
  qrInstruction: 'צלמו את המבחן שלכם: סרקו את הקוד, כתבו את השם, צלמו כל עמוד ולחצו על שמירה.',
  closeQr: 'סגירה',
  submissionsTitle: 'הגשות מצילום',
  counter: (submitted: number, roster: number | null) =>
    roster == null ? `${submitted} הגישו` : `${submitted} מתוך ${roster} הגישו`,
  badge: {
    processing: 'בעיבוד',
    ready: 'מוכן',
    failed: 'נכשל',
    pending: 'ממתין לאישור',
    conflict: 'התנגשות',
  },
  updatedAt: (time: string) => `עודכן ב-${time}`,
  retry: 'ניסיון נוסף',
  approveNew: 'אישור כתלמיד/ה חדש/ה',
  linkExisting: 'שיוך לתלמיד קיים',
  studentExists: 'כבר קיים תלמיד בשם הזה — שייכי אותו מהרשימה',
  resolve: 'פתרון',
  keepThis: 'שמירת ההגשה הזאת',
  discardThis: 'ביטול ההגשה הזאת',
  lateResubmission: 'נשלחה גרסה חדשה',
  conflictTitle: 'שתי הגשות לאותו תלמיד',
  pages: (n: number) => (n === 1 ? 'עמוד אחד' : `${n} עמודים`),
  empty: 'עוד לא הגיעו הגשות',
}

/** HH:MM in Israel time, for «עודכן ב-…» and «בשעה …». */
export function hhmm(iso: string | null | undefined): string {
  if (!iso) return ''
  return new Intl.DateTimeFormat('he-IL', {
    hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Jerusalem', hour12: false,
  }).format(new Date(iso))
}

export function longDate(isoDate: string): string {
  return new Intl.DateTimeFormat('he-IL', {
    day: 'numeric', month: 'long', timeZone: 'Asia/Jerusalem',
  }).format(new Date(`${isoDate}T12:00:00Z`))
}
