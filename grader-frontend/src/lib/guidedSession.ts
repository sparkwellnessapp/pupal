/**
 * [028 §8] The guided-session ask, in one place.
 *
 * It has TWO entry points — the onboarding exam step's booking block, and the
 * persistent «קבעי שיחה עם נועם» link in the app shell — and they must record
 * the same fact against the same field. Two copies of "fire the PATCH and open
 * the tab" is exactly how one of them quietly stops recording.
 */
import { updateOnboardingExam } from '@/lib/api';

/**
 * Read at module scope, not per call: `process.env.NEXT_PUBLIC_*` is INLINED at
 * build time, so a dynamic lookup (`process.env[name]`) would compile to an
 * undefined read in the browser. Undefined is a supported state — the callers
 * render nothing rather than a dead link.
 */
export const BOOKING_URL = process.env.NEXT_PUBLIC_BOOKING_URL || undefined;
export const WHATSAPP_NUMBER = process.env.NEXT_PUBLIC_WHATSAPP_NUMBER || undefined;

/**
 * Record that she asked for a guided session. Fire-and-forget, and it sends
 * ONLY `guided_session_requested`.
 *
 * The omission is the point: including `next_exam_date` here — even as null —
 * would erase a date she gave and re-stamp `next_exam_answered_at`, pushing her
 * 14-day re-ask out by however long she took to click. The server reads which
 * fields arrived, so sending one field touches one column.
 *
 * Swallows its error on purpose. She is on her way to a booking page in another
 * tab; an error toast about a telemetry-shaped write would interrupt the exact
 * action it is recording. The server stamps first-occurrence only, so a retry
 * on her next visit costs nothing.
 */
export function requestGuidedSession(): void {
    void updateOnboardingExam({ guided_session_requested: true }).catch(() => {});
}
