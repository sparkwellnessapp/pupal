'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, ArrowRight, Loader2 } from 'lucide-react';

import { Modal } from '@/components/batch/Modal';
import { ProgressBar } from '@/components/onboarding/ProgressBar';
import { WelcomeStep } from '@/components/onboarding/steps/WelcomeStep';
import { SubjectsStep } from '@/components/onboarding/steps/SubjectsStep';
import { SchoolsStep } from '@/components/onboarding/steps/SchoolsStep';
import { IdentityStep } from '@/components/onboarding/steps/IdentityStep';
import { ExamStep } from '@/components/onboarding/steps/ExamStep';
import { ReadyStep } from '@/components/onboarding/steps/ReadyStep';
import {
    canAdvance,
    examPayload,
    firstName,
    isSkippable,
    nextStep,
    prevStep,
    stepNumber,
    TOTAL_STEPS,
    type Gender,
    type OnboardingDraft,
    type PickedSchool,
    type StepId,
} from '@/lib/onboarding';
import {
    completeOnboarding,
    setMySchools,
    updateMyProfile,
    updateMySubjectMatters,
    updateOnboardingExam,
} from '@/lib/api';
import {
    BOOKING_URL,
    requestGuidedSession,
    WHATSAPP_NUMBER,
} from '@/lib/guidedSession';
import { toMessage } from '@/lib/errorSurface';
import { useAuth } from '@/lib/auth';
import {
    BACK,
    EXAM_SKIP,
    EXAM_SUBTITLE,
    EXAM_TITLE,
    GENERIC_ERROR,
    IDENTITY_SUBTITLE,
    IDENTITY_TITLE,
    NEXT,
    READY_CTA,
    READY_TITLE,
    SAVING,
    SCHOOLS_SKIP,
    SCHOOLS_SUBTITLE,
    SCHOOLS_TITLE,
    STEP_OF,
    SUBJECTS_SUBTITLE,
    SUBJECTS_TITLE,
    WELCOME_CTA,
    WELCOME_TITLE,
} from '@/copy/onboarding';

/**
 * The onboarding flow: one centered popup, five steps, a turquoise progress bar.
 *
 * COMMIT MODEL — each step commits when the teacher advances past it, not one
 * write at the end. A teacher who closes the tab at step 4 keeps her subjects
 * and her schools; buffering everything until the finish would lose all of it
 * and gain nothing. Every write is a full replacement or is idempotent
 * server-side, so «חזרה» → «הבא» re-sending is safe.
 *
 * On failure the step does NOT advance and the reason is shown inline. Nothing
 * here retries by itself: a mutation that repeats on its own is how a duplicate
 * lands, so the retry is the teacher's next click.
 */
export function OnboardingDialog() {
    const router = useRouter();
    const { user, applyUser } = useAuth();

    const [step, setStep] = useState<StepId>('welcome');
    /** Guards a same-batch double click; see `advance`. */
    const inFlight = useRef(false);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    // Only shown after she has TRIED to advance — a hint that appears before
    // she has done anything reads as a scolding.
    const [showHint, setShowHint] = useState(false);

    const [draft, setDraft] = useState<OnboardingDraft>(() => ({
        subjectIds: (user?.subject_matters ?? []).map((s) => s.id),
        schools: (user?.schools ?? []).map((s) => ({
            id: s.id,
            name: s.name,
            city: s.city ?? '',
            label: s.city ? `${s.name}, ${s.city}` : s.name,
            // Round-trip the IDENTITY, not just the spelling: dropping it here
            // would demote every school she picked from the list to a free-text
            // one the moment she re-saves an unchanged list.
            ministrySymbol: s.ministry_symbol ?? null,
        })),
        fullName: user?.full_name ?? '',
        gender: (user?.gender as Gender | undefined) ?? null,
        // [028] Deliberately NOT seeded from the profile. The exam step's
        // fields are not on the profile shape, and an empty date is what makes
        // "she skipped" expressible: pre-filling a stored date would make a
        // re-entry through this flow re-send — and therefore re-stamp
        // `next_exam_answered_at` — for an answer she never touched.
        examDate: '',
        examUnknown: false,
        phone: '',
        whatsappOptIn: false,
    }));

    /**
     * Merge into the draft, and BAIL when nothing actually changed.
     *
     * Without the guard every call returns a fresh object, so React re-renders
     * even when the values are identical — and several handlers here re-assert
     * a field they are not changing (`onDateChange` also sends
     * `examUnknown: false`). A re-render mid-edit is not free on a controlled
     * `<input type="date">`: React writes `node.value` back whenever its
     * rendered value differs from the DOM's, and a half-typed date reads as
     * `''` in the DOM, so an incidental render can put the OLD date back under
     * her caret. Rendering only on real change removes that whole class.
     */
    const patch = useCallback(
        (fields: Partial<OnboardingDraft>) =>
            setDraft((d) => {
                const changed = (Object.keys(fields) as (keyof OnboardingDraft)[])
                    .some((k) => !Object.is(d[k], fields[k]));
                return changed ? { ...d, ...fields } : d;
            }),
        [],
    );

    // PREFETCH the school index one step early. It is ~640KB (2,194 schools) and
    // is deliberately kept out of every other route's bundle by the dynamic
    // import — but that means step 3 would otherwise start the download at the
    // moment she arrives and wants to type. Warming it while she picks subjects
    // costs nothing (the module cache makes step 3's own import instant) and
    // fails silently: SchoolCombobox owns the real load, its error state, and
    // its free-text fallback.
    useEffect(() => {
        if (step !== 'subjects') return;
        void import('@/data/israeli-schools').catch(() => {});
    }, [step]);

    /** What advancing PAST this step commits. Null ⇒ nothing to write. */
    const commitFor = useCallback(
        (current: StepId): (() => Promise<void>) | null => {
            switch (current) {
                case 'subjects':
                    return async () => {
                        await updateMySubjectMatters(draft.subjectIds);
                    };
                case 'schools':
                    return async () => {
                        // Order is meaningful: the FIRST school becomes the
                        // attribution key server-side. Do not sort this.
                        await setMySchools(
                            draft.schools.map((s) => ({
                                name: s.name,
                                city: s.city || null,
                                ministry_symbol: s.ministrySymbol,
                            })),
                        );
                    };
                case 'identity':
                    return async () => {
                        await updateMyProfile({
                            full_name: draft.fullName.trim(),
                            ...(draft.gender ? { gender: draft.gender } : {}),
                        });
                    };
                case 'exam':
                    return async () => {
                        // Null ⇒ she touched nothing (or skipped). Sending an
                        // empty body would still stamp `answered_at` server-
                        // side and claim she answered, which is the one thing
                        // this step must never fake.
                        const payload = examPayload(draft);
                        if (payload) await updateOnboardingExam(payload);
                    };
                case 'ready':
                    return async () => {
                        const profile = await completeOnboarding();
                        // Adopt the returned profile rather than re-fetching:
                        // refreshUser swallows its errors, and a silent failure
                        // there would bounce her straight back into the flow she
                        // just finished.
                        //
                        // Mapped field by field rather than cast: the wire type
                        // and the session's User are two hand-kept shapes, and a
                        // blanket cast would hide the day they stop agreeing.
                        applyUser({
                            id: profile.id,
                            email: profile.email,
                            full_name: profile.full_name,
                            subscription_status: profile.subscription_status,
                            started_trial_at: profile.started_trial_at ?? undefined,
                            started_pro_at: profile.started_pro_at ?? undefined,
                            trial_ends_at: profile.trial_ends_at,
                            is_subscription_active: profile.is_subscription_active,
                            subject_matters: profile.subject_matters ?? [],
                            created_at: profile.created_at,
                            gender: profile.gender ?? null,
                            onboarding_completed_at: profile.onboarding_completed_at ?? null,
                            schools: (profile.schools ?? []).map((s) => ({
                                id: s.id,
                                name: s.name,
                                city: s.city ?? null,
                            })),
                            primary_school_id: profile.primary_school_id ?? null,
                        });
                    };
                case 'welcome':
                    return null;
            }
        },
        [draft, applyUser],
    );

    const advance = useCallback(
        async (opts: { skip?: boolean } = {}) => {
            // A REF, not just the `busy` state: two clicks landing in the same
            // React batch both read busy === false, and the second would re-send
            // the step's write. Every write here is a replacement or idempotent
            // server-side, so a duplicate is survivable — but "survivable" is
            // not a reason to send it.
            if (inFlight.current) return;
            inFlight.current = true;
            try {
                if (!opts.skip && !canAdvance(step, draft)) {
                    setShowHint(true);
                    return;
                }

                const commit = commitFor(step);
                const target = nextStep(step);

                setError(null);
                if (commit) {
                    setBusy(true);
                    try {
                        await commit();
                    } catch (err) {
                        // toMessage already routes ApiAuthError to the honest
                        // "session expired" line (it can tell expired from
                        // unauthorized by reading the JWT locally), so there is
                        // no auth branch to duplicate here.
                        setError(toMessage(err) || GENERIC_ERROR);
                        return;                   // the step does NOT advance
                    } finally {
                        setBusy(false);
                    }
                }

                setShowHint(false);
                if (target) setStep(target);
                else router.replace('/');
            } finally {
                inFlight.current = false;
            }
        },
        [step, draft, commitFor, router],
    );

    const goBack = useCallback(() => {
        const target = prevStep(step);
        if (target) {
            setError(null);
            setShowHint(false);
            setStep(target);
        }
    }, [step]);

    const view = useMemo(() => {
        switch (step) {
            case 'welcome':
                return { title: WELCOME_TITLE, subtitle: null, cta: WELCOME_CTA };
            case 'subjects':
                return { title: SUBJECTS_TITLE, subtitle: SUBJECTS_SUBTITLE, cta: NEXT };
            case 'schools':
                return { title: SCHOOLS_TITLE, subtitle: SCHOOLS_SUBTITLE, cta: NEXT };
            case 'identity':
                return { title: IDENTITY_TITLE, subtitle: IDENTITY_SUBTITLE, cta: NEXT };
            case 'exam':
                return { title: EXAM_TITLE, subtitle: EXAM_SUBTITLE, cta: NEXT };
            case 'ready':
                return {
                    title: READY_TITLE(firstName(draft.fullName || user?.full_name)),
                    subtitle: null,
                    cta: READY_CTA,
                };
        }
    }, [step, draft.fullName, user?.full_name]);

    const index = stepNumber(step);

    return (
        <Modal
            open
            // Never dismissible: there is nothing behind this she may reach yet.
            // The prop exists so `onClose` is unreachable rather than a lie.
            onClose={() => undefined}
            dismissible={false}
            size="lg"
            // Move focus into each new step — the ONLY intended half of what
            // the focus effect used to do by accident on every keystroke.
            focusKey={step}
            // A WARM scrim, not the default dark one: this dialog is not
            // interrupting a surface, it IS the surface, and black/50 over the
            // cream ground reads as muddy grey instead of as a dimmed Vivi.
            backdropClassName="bg-[#FFFaf2]/70 backdrop-blur-sm"
            labelledBy="onboarding-title"
            testId="onboarding-dialog"
        >
            <div className="space-y-5">
                <div className="space-y-4">
                    <img
                        src="/vivi-logo-no-background-no-slogan.png"
                        alt="Vivi"
                        className="mx-auto h-12 w-auto"
                    />
                    <ProgressBar step={index} total={TOTAL_STEPS} />
                    <p className="sr-only" aria-live="polite">
                        {STEP_OF(index, TOTAL_STEPS)}
                    </p>
                </div>

                <div className="space-y-1.5">
                    <h2 id="onboarding-title" className="text-2xl font-semibold text-gray-900">
                        {view.title}
                    </h2>
                    {view.subtitle && <p className="text-sm text-gray-500">{view.subtitle}</p>}
                </div>

                {/* A reserved well: without it the panel resizes between a prose
                    step and a chip step, and the footer moves under her cursor. */}
                <div className="min-h-[18rem]">
                    {step === 'welcome' && <WelcomeStep />}
                    {step === 'subjects' && (
                        <SubjectsStep
                            selected={draft.subjectIds}
                            onChange={(subjectIds) => patch({ subjectIds })}
                            showHint={showHint}
                        />
                    )}
                    {step === 'schools' && (
                        <SchoolsStep
                            picked={draft.schools}
                            onChange={(schools: PickedSchool[]) => patch({ schools })}
                        />
                    )}
                    {step === 'identity' && (
                        <IdentityStep
                            fullName={draft.fullName}
                            gender={draft.gender}
                            onNameChange={(fullName) => patch({ fullName })}
                            onGenderChange={(gender) => patch({ gender })}
                            showHint={showHint}
                        />
                    )}
                    {step === 'exam' && (
                        <ExamStep
                            date={draft.examDate}
                            unknown={draft.examUnknown}
                            phone={draft.phone}
                            whatsappOptIn={draft.whatsappOptIn}
                            // Picking a date CLEARS «עוד לא יודעת», and vice
                            // versa: they are two answers to one question, and
                            // letting both stand would leave the payload
                            // builder to guess which she meant.
                            onDateChange={(examDate) =>
                                patch({ examDate, examUnknown: false })
                            }
                            onUnknownToggle={() =>
                                patch({
                                    examUnknown: !draft.examUnknown,
                                    examDate: draft.examUnknown ? draft.examDate : '',
                                })
                            }
                            onPhoneChange={(phone) =>
                                // Clearing the number withdraws the consent it
                                // was given for. Leaving the tick standing on
                                // an empty field would be a stored "yes" that
                                // no number was ever attached to.
                                patch({
                                    phone,
                                    whatsappOptIn: phone.trim() ? draft.whatsappOptIn : false,
                                })
                            }
                            onConsentChange={(whatsappOptIn) => patch({ whatsappOptIn })}
                            onBookingClick={requestGuidedSession}
                            whatsappNumber={WHATSAPP_NUMBER}
                            bookingUrl={BOOKING_URL}
                        />
                    )}
                    {step === 'ready' && <ReadyStep />}
                </div>

                {error && (
                    <div
                        role="alert"
                        data-testid="onboarding-error"
                        className="rounded-grade-sm border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
                    >
                        {error}
                    </div>
                )}

                <div className="flex items-center justify-between gap-3 border-t border-surface-200 pt-4">
                    <div>
                        {prevStep(step) && (
                            <button
                                type="button"
                                onClick={goBack}
                                disabled={busy}
                                data-testid="onboarding-back"
                                className="flex items-center gap-1.5 rounded-grade-ctl px-4 py-2.5 text-sm
                                           text-gray-600 transition-colors hover:bg-surface-100
                                           disabled:opacity-50"
                            >
                                <ArrowRight size={16} />
                                {BACK}
                            </button>
                        )}
                    </div>

                    <div className="flex items-center gap-2">
                        {isSkippable(step) && (
                            <button
                                type="button"
                                onClick={() => void advance({ skip: true })}
                                disabled={busy}
                                data-testid="onboarding-skip"
                                className="rounded-grade-ctl px-4 py-2.5 text-sm text-gray-500
                                           transition-colors hover:bg-surface-100 disabled:opacity-50"
                            >
                                {step === 'exam' ? EXAM_SKIP : SCHOOLS_SKIP}
                            </button>
                        )}
                        <button
                            type="button"
                            onClick={() => void advance()}
                            disabled={busy}
                            data-testid="onboarding-next"
                            className="flex items-center gap-2 rounded-grade-ctl bg-primary-600 px-6 py-2.5
                                       text-sm font-medium text-white transition-colors
                                       hover:bg-primary-700 disabled:opacity-60"
                        >
                            {busy ? (
                                <>
                                    <Loader2
                                        size={16}
                                        className="animate-spin motion-reduce:animate-none"
                                    />
                                    {SAVING}
                                </>
                            ) : (
                                <>
                                    {view.cta}
                                    <ArrowLeft size={16} />
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </Modal>
    );
}
