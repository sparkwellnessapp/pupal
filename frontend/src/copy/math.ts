/**
 * Copy for mathematics on the review surfaces (MATH_RENDERING_PLAN §4).
 *
 * A span that cannot be drawn is shown as transcribed, and says so — never hidden,
 * never "fixed". The teacher compares it with the scan like any other line.
 */
export const MATH_UNRENDERED_TITLE = 'לא ניתן להציג את הביטוי — מוצג כפי שתומלל. כדאי להשוות מול הסריקה.';

/** The rendered math answer's editing affordances (transcription gate). */
export const MATH_EDIT_SPAN_LABEL = 'עריכת הביטוי';
export const MATH_EDIT_SAVE = 'שמירה';
export const MATH_EDIT_CANCEL = 'ביטול';
export const MATH_EDIT_RAW = 'עריכת טקסט';
export const MATH_EDIT_RENDERED = 'חזרה לתצוגה';
export const MATH_EDIT_HINT = 'לחיצה על ביטוי פותחת אותו לעריכה';
export const MATH_EDITOR_LOADING = 'טוען עורך…';

/** A drawing's card at the transcription gate (§5): her student's ink, Vivi's reading pinned on it. */
export const FIG_TITLE = (n: number, page: number) => `איור ${n} · עמוד ${page} — מה שויוי קראה מהשרטוט`;
export const FIG_NO_CROP = 'לא ניתן להציג את השרטוט — כדאי לבדוק אותו בסריקה.';
export const FIG_NO_FEATURES = 'ויוי לא קראה סימונים בשרטוט הזה.';
export const FIG_UNREAD = 'ויוי לא קראה את השרטוט הזה — כדאי לבדוק אותו בסריקה.';
export const FIG_EDIT = 'עריכה';
export const FIG_DELETE = 'מחיקה';
export const FIG_ADD = '+ הוספת סימון שויוי פספסה';
export const FIG_UNCERTAIN = 'לא ודאי';
export const FIG_INK_OTHER = 'בצבע אחר';
export const FIG_SOURCE_TEACHER = 'שלך';
export const FIG_KIND_HE: Readonly<Record<string, string>> = {
    vertical_asymptote: 'אסימפטוטה אנכית',
    horizontal_asymptote: 'אסימפטוטה אופקית',
    minimum: 'נקודת מינימום',
    maximum: 'נקודת מקסימום',
    x_intercept: 'חיתוך עם ציר x',
    y_intercept: 'חיתוך עם ציר y',
    point: 'נקודה',
    shaded_region: 'שטח מסומן',
    vertex: 'קודקוד',
    side_label: 'צלע',
    angle_label: 'זווית',
    segment_label: 'קטע',
    right_angle_mark: 'סימון זווית ישרה',
    axis_label: 'ציר',
    other_label: 'סימון',
};

/** §5 (OD-M5) at the grading gate: points were taken where the answer names a drawing. */
export const FIG_DEDUCTION_HINT = 'בתשובה יש שרטוט וירדו בה נקודות. ויוי עלולה לפספס סימון בשרטוט — כדאי לבדוק מול הסריקה.';
