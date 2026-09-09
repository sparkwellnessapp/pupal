import { describe, expect, it } from 'vitest';

import {
    BOOKING_WINDOW_DAYS,
    canAdvance,
    examPayload,
    firstName,
    isWithinBookingWindow,
    isSkippable,
    nextStep,
    ONBOARDING_SUBJECT_CODES,
    pickOnboardingSubjects,
    prevStep,
    STEPS,
    stepNumber,
    todayISO,
    TOTAL_STEPS,
    type OnboardingDraft,
} from './onboarding';

const EXAM_EMPTY = {
    examDate: '',
    examUnknown: false,
    phone: '',
    whatsappOptIn: false,
} as const;

const empty: OnboardingDraft = {
    subjectIds: [],
    schools: [],
    fullName: '',
    gender: null,
    ...EXAM_EMPTY,
};

const full: OnboardingDraft = {
    subjectIds: [1],
    schools: [
        { id: '1', name: 'בליך', city: 'רמת גן', label: 'בליך, רמת גן', ministrySymbol: '540151' },
    ],
    fullName: 'מיכל כהן',
    gender: 'female',
    ...EXAM_EMPTY,
};

describe('canAdvance — the D7 matrix', () => {
    it('never blocks the welcome step', () => {
        expect(canAdvance('welcome', empty)).toBe(true);
    });

    it('blocks subjects until at least one is chosen', () => {
        expect(canAdvance('subjects', empty)).toBe(false);
        expect(canAdvance('subjects', { ...empty, subjectIds: [3] })).toBe(true);
    });

    it('NEVER blocks schools — the one skippable step', () => {
        expect(canAdvance('schools', empty)).toBe(true);
        expect(canAdvance('schools', full)).toBe(true);
    });

    it('blocks identity without a name', () => {
        expect(canAdvance('identity', { ...full, fullName: '' })).toBe(false);
        expect(canAdvance('identity', { ...full, fullName: '   ' })).toBe(false);
    });

    it('blocks identity without a gender', () => {
        expect(canAdvance('identity', { ...full, gender: null })).toBe(false);
    });

    it('accepts "unspecified" as a real answer, not a silence', () => {
        expect(canAdvance('identity', { ...full, gender: 'unspecified' })).toBe(true);
    });

    it('never blocks the final step', () => {
        expect(canAdvance('ready', empty)).toBe(true);
    });
});

describe('step navigation', () => {
    it('has six steps in the documented order', () => {
        // [028] `exam` between `identity` and `ready` — the closing screen stays
        // the closing screen.
        expect(STEPS).toEqual([
            'welcome', 'subjects', 'schools', 'identity', 'exam', 'ready',
        ]);
        expect(TOTAL_STEPS).toBe(6);
    });

    it('numbers steps 1..N for the progress bar', () => {
        expect(stepNumber('welcome')).toBe(1);
        expect(stepNumber('ready')).toBe(TOTAL_STEPS);
    });

    it('walks forward and back, and stops at both ends', () => {
        expect(nextStep('welcome')).toBe('subjects');
        expect(nextStep('ready')).toBeNull();
        expect(prevStep('subjects')).toBe('welcome');
        expect(prevStep('welcome')).toBeNull();
    });

    it('marks exactly the two optional steps skippable', () => {
        // ONB-1: the exam step never blocks. A required date would be answered
        // with a guess, and a guessed date is indistinguishable from a real one
        // in the outreach queue.
        expect(STEPS.filter(isSkippable)).toEqual(['schools', 'exam']);
    });

    it('never blocks the exam step', () => {
        expect(canAdvance('exam', empty)).toBe(true);
    });
});

describe('pickOnboardingSubjects', () => {
    const api = [
        { id: 10, code: 'biology', name_he: 'ביולוגיה' },
        { id: 11, code: 'computer_science', name_he: 'מדעי המחשב' },
        { id: 12, code: 'english', name_he: 'אנגלית' },
        { id: 13, code: 'mathematics', name_he: 'מתמטיקה' },
    ];

    it('keeps only the three supported subjects, in the declared order', () => {
        expect(pickOnboardingSubjects(api).map((s) => s.code)).toEqual([
            ...ONBOARDING_SUBJECT_CODES,
        ]);
    });

    it('resolves real database ids rather than hardcoded numbers', () => {
        expect(pickOnboardingSubjects(api).map((s) => s.id)).toEqual([12, 13, 11]);
    });

    it('degrades to one fewer chip when a code is missing — never undefined', () => {
        const partial = api.filter((s) => s.code !== 'english');
        const picked = pickOnboardingSubjects(partial);
        expect(picked.map((s) => s.code)).toEqual(['mathematics', 'computer_science']);
        expect(picked.every((s) => s !== undefined)).toBe(true);
    });

    it('survives an empty API response', () => {
        expect(pickOnboardingSubjects([])).toEqual([]);
    });
});

describe('firstName', () => {
    it('takes the first word', () => {
        expect(firstName('מיכל כהן')).toBe('מיכל');
    });

    it('is empty rather than "undefined" for missing input', () => {
        expect(firstName('')).toBe('');
        expect(firstName(null)).toBe('');
        expect(firstName(undefined)).toBe('');
        expect(firstName('   ')).toBe('');
    });
});

// ─────────────────────────────────────────────────────────────────────────────
// [028] The exam step
// ─────────────────────────────────────────────────────────────────────────────

describe('isWithinBookingWindow', () => {
    // A fixed "today" so the suite does not drift with the calendar.
    const today = new Date(2026, 8, 9); // 2026-09-09, local

    it('includes today and the whole window', () => {
        expect(isWithinBookingWindow('2026-09-09', today)).toBe(true);
        expect(isWithinBookingWindow('2026-09-23', today)).toBe(true); // +14
    });

    it('excludes the day after the window and anything past', () => {
        expect(isWithinBookingWindow('2026-09-24', today)).toBe(false); // +15
        expect(isWithinBookingWindow('2026-11-03', today)).toBe(false);
    });

    it('excludes the past — a date behind her is not a call to book', () => {
        expect(isWithinBookingWindow('2026-09-08', today)).toBe(false);
    });

    it('is calendar-day based, not hours', () => {
        // `new Date('2026-09-23')` is UTC midnight while `today` is local; an
        // hours-based difference would shift this boundary by a day for a
        // teacher in Israel (UTC+2/+3).
        const lateEvening = new Date(2026, 8, 9, 23, 30);
        expect(isWithinBookingWindow('2026-09-23', lateEvening)).toBe(true);
        expect(isWithinBookingWindow('2026-09-24', lateEvening)).toBe(false);
    });

    it('refuses junk rather than guessing', () => {
        expect(isWithinBookingWindow('', today)).toBe(false);
        expect(isWithinBookingWindow('בקרוב', today)).toBe(false);
        expect(isWithinBookingWindow('2026-9-9', today)).toBe(false);
    });

    it('uses one exported constant for the window', () => {
        expect(BOOKING_WINDOW_DAYS).toBe(14);
    });
});

describe('todayISO', () => {
    it('is LOCAL, not UTC — the control must offer her own today', () => {
        // 01:00 in Israel is still the previous UTC day; toISOString() would
        // return yesterday and `min` would exclude today.
        expect(todayISO(new Date(2026, 8, 9, 1, 0))).toBe('2026-09-09');
        expect(todayISO(new Date(2026, 0, 5))).toBe('2026-01-05');
    });
});

describe('examPayload — omission is meaningful', () => {
    const draft = (over: Partial<OnboardingDraft>): OnboardingDraft => ({
        ...empty,
        ...over,
    });

    it('sends nothing when she touched nothing (a skip)', () => {
        // An empty body would still stamp `next_exam_answered_at` server-side
        // and claim she answered.
        expect(examPayload(draft({}))).toBeNull();
    });

    it('sends an explicit null for «עוד לא יודעת» (ONB-2)', () => {
        expect(examPayload(draft({ examUnknown: true }))).toEqual({
            next_exam_date: null,
        });
    });

    it('sends the date she picked', () => {
        expect(examPayload(draft({ examDate: '2026-11-03' }))).toEqual({
            next_exam_date: '2026-11-03',
        });
    });

    it('sends the phone EXACTLY as typed, with its consent state', () => {
        expect(
            examPayload(draft({ phone: ' 052-123 4567 ', whatsappOptIn: true })),
        ).toEqual({ phone: '052-123 4567', whatsapp_opt_in: true });
    });

    it('sends whatsapp_opt_in false when she declined — never omits it', () => {
        // Omitting it would leave a previously-stored `true` standing.
        expect(examPayload(draft({ phone: '0521234567' }))).toEqual({
            phone: '0521234567',
            whatsapp_opt_in: false,
        });
    });

    it('never sends consent without a number (the server 422s on it)', () => {
        const payload = examPayload(draft({ phone: '  ', whatsappOptIn: true }));
        expect(payload).toBeNull();
    });

    it('never sends guided_session_requested — that is the shell link field', () => {
        expect(examPayload(draft({ examDate: '2026-11-03' }))).not.toHaveProperty(
            'guided_session_requested',
        );
    });
});
