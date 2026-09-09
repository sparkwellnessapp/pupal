/**
 * Onboarding — the pure half: the step order, what each step commits, and when
 * the teacher may advance.
 *
 * Kept out of the component so the D7 rule (steps 2 and 4 required; step 3, the
 * schools step, is the only skippable one) is a tested function rather than a
 * scattering of `disabled={...}` expressions nobody can read together.
 */

export type Gender = 'female' | 'male' | 'unspecified';

/**
 * A school as the teacher picked it.
 *
 * `id` is a LOCAL key for React and for removal — the display index's id, a
 * free-text marker, or (for a school hydrated from her saved profile) a
 * `schools.id` UUID. It is never sent anywhere.
 *
 * `ministrySymbol` is the one that travels: סמל מוסד when she chose from the
 * list, null when she typed the school herself. It — not the name — is what
 * identifies the institution server-side (023), which matters because 82
 * normalized names in the real export are shared by 213 institutions, two of
 * them in the same city.
 */
export interface PickedSchool {
    id: string;
    name: string;
    city: string;
    label: string;
    ministrySymbol: string | null;
}

export interface OnboardingDraft {
    subjectIds: number[];
    schools: PickedSchool[];
    fullName: string;
    gender: Gender | null;
    /**
     * [028] The exam step. `examDate` is '' for "not answered on this screen"
     * and a 'YYYY-MM-DD' string once she picks one; «עוד לא יודעת» is a
     * SEPARATE flag, because a null date alone cannot tell "she said she does
     * not know" apart from "she has not touched the field" — and the server
     * stores exactly that distinction (ONB-2).
     */
    examDate: string;
    examUnknown: boolean;
    phone: string;
    whatsappOptIn: boolean;
}

/**
 * [028] `exam` sits between `identity` and `ready`, deliberately last-but-one:
 * it is the step that asks for something (a date, a phone number) rather than
 * telling her something, and by then she has already invested four screens.
 * Putting it before `ready` also means the closing screen stays the closing
 * screen — an ask AFTER "ברוכה הבאה על הסיפון" would read as a bait.
 */
export const STEPS = ['welcome', 'subjects', 'schools', 'identity', 'exam', 'ready'] as const;
export type StepId = (typeof STEPS)[number];

export const TOTAL_STEPS = STEPS.length;

/** 1-based, for the progress bar and «שלב N מתוך M». */
export const stepNumber = (step: StepId): number => STEPS.indexOf(step) + 1;

/**
 * The skippable steps (D7 + 028 §8). Exported so the shell renders its skip
 * affordance from the same fact the advance rule uses, instead of a second
 * hardcoded list.
 *
 * `exam` joins `schools` because ONB-1 says so and because the alternative is
 * worse than it looks: a required exam date would be answered with a guess, and
 * a guessed date is indistinguishable from a real one in the outreach queue —
 * it would send a human to call a teacher about an exam that does not exist.
 */
export const isSkippable = (step: StepId): boolean =>
    step === 'schools' || step === 'exam';

/**
 * D7, in one place.
 *
 * `schools` is deliberately absent: the schools step never blocks, whether the
 * teacher picked five schools or none. `identity` requires BOTH a non-blank
 * name and an explicit gender — which is answerable by anyone because the
 * options include «מעדיפ/ה לא לציין», a real stored answer rather than a
 * silence.
 */
export function canAdvance(step: StepId, draft: OnboardingDraft): boolean {
    switch (step) {
        case 'subjects':
            return draft.subjectIds.length > 0;
        case 'identity':
            return draft.fullName.trim().length > 0 && draft.gender !== null;
        case 'welcome':
        case 'schools':
        // [028] `exam` never blocks — it is skippable, and every combination
        // of its fields is a legitimate answer. The ONE thing the server
        // refuses (consent without a number) is guarded below, not here,
        // because it is about the phone field and not about advancing.
        case 'exam':
        case 'ready':
            return true;
    }
}

/**
 * The most schools one teacher may list. MIRRORS the endpoint's own cap
 * (`UpdateSchoolsRequest.schools`, max_length=20) — the server is the authority
 * and rejects more; this is the client stopping her before it does.
 */
export const MAX_SCHOOLS = 20;

/** The next step, or null at the end of the flow. */
export function nextStep(step: StepId): StepId | null {
    const i = STEPS.indexOf(step);
    return i >= 0 && i < STEPS.length - 1 ? STEPS[i + 1] : null;
}

/** The previous step, or null at the start. */
export function prevStep(step: StepId): StepId | null {
    const i = STEPS.indexOf(step);
    return i > 0 ? STEPS[i - 1] : null;
}

/**
 * The three subjects Vivi actually extracts and grades today (owner ruling D6).
 * Codes, not ids: ids are database rows and these are resolved against
 * `GET /users/subject-matters` at render, so a re-seeded database cannot shift
 * a hardcoded number onto the wrong subject.
 */
export const ONBOARDING_SUBJECT_CODES = [
    'english',
    'mathematics',
    'computer_science',
] as const;

/**
 * Keep only the supported subjects, in the order above — the API returns all 16
 * sorted by Hebrew name. A code that is ever missing from the database yields
 * one fewer chip, never a crash and never an undefined id on the wire.
 */
export function pickOnboardingSubjects<T extends { code: string }>(all: T[]): T[] {
    const byCode = new Map(all.map((s) => [s.code, s]));
    return ONBOARDING_SUBJECT_CODES.map((c) => byCode.get(c)).filter(
        (s): s is T => s !== undefined,
    );
}

/** First name for the closing greeting; '' when there is nothing usable. */
export function firstName(fullName: string | null | undefined): string {
    return (fullName ?? '').trim().split(/\s+/)[0] ?? '';
}

/**
 * [028 §8] The booking block appears only when her exam is within this many
 * days. ONE constant, exported, because the block renders REACTIVELY as she
 * changes the date — before any submit — so the server has no say in it and
 * ships no `show_booking` field that could be one step behind what she sees.
 *
 * Fourteen days and not more: asking a stranger to commit to a call eight
 * weeks out, thirty seconds after signup, converts badly and no-shows worse.
 */
export const BOOKING_WINDOW_DAYS = 14;

/**
 * Whether the booking block should render for a picked date.
 *
 * Compares CALENDAR DAYS in the browser's own zone, not elapsed hours: a date
 * input yields a bare 'YYYY-MM-DD' with no time, and `new Date('2026-11-03')`
 * parses as UTC MIDNIGHT while `new Date()` is local — so an hours-based
 * difference silently shifts the boundary by a day for a teacher in Israel
 * (UTC+2/+3). Both sides are reduced to a local Y-M-D triple first.
 */
export function isWithinBookingWindow(isoDate: string, today: Date = new Date()): boolean {
    const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(isoDate.trim());
    if (!m) return false;
    const picked = Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
    const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
    const days = Math.round((picked - now) / 86_400_000);
    return days >= 0 && days <= BOOKING_WINDOW_DAYS;
}

/**
 * `<input type="date" min>` — today, in the browser's own zone.
 *
 * `toISOString()` is NOT usable here: it converts to UTC first, so at 01:00 in
 * Israel it yields YESTERDAY and the control would offer a date the server
 * would still accept but which is not what "today" means to her.
 */
export function todayISO(today: Date = new Date()): string {
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;
}

/**
 * What the exam step sends. Returns null when there is nothing to say — a skip,
 * or a return visit where she touched nothing — so the caller can omit the
 * request entirely rather than POST an empty object that would still re-stamp
 * `next_exam_answered_at` server-side.
 *
 * The absent/null distinction is the wire's, not ours to smooth over:
 * `next_exam_date: null` is «עוד לא יודעת», a real answer.
 */
export interface OnboardingExamPayload {
    next_exam_date?: string | null;
    phone?: string | null;
    whatsapp_opt_in?: boolean;
    guided_session_requested?: boolean;
}

export function examPayload(draft: OnboardingDraft): OnboardingExamPayload | null {
    const payload: OnboardingExamPayload = {};

    if (draft.examUnknown) {
        payload.next_exam_date = null;
    } else if (draft.examDate.trim()) {
        payload.next_exam_date = draft.examDate.trim();
    }

    const phone = draft.phone.trim();
    if (phone) {
        payload.phone = phone;
        payload.whatsapp_opt_in = draft.whatsappOptIn;
    }

    return Object.keys(payload).length > 0 ? payload : null;
}
