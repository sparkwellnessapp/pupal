'use client';

import { CalendarCheck, MessageCircle } from 'lucide-react';

import { isWithinBookingWindow, todayISO } from '@/lib/onboarding';
import {
    EXAM_BOOKING_BODY,
    EXAM_BOOKING_CTA,
    EXAM_BOOKING_TITLE,
    EXAM_DATE_LABEL,
    EXAM_PHONE_HELPER,
    EXAM_PHONE_LABEL,
    EXAM_PHONE_PLACEHOLDER,
    EXAM_SUCCESS_DATE,
    EXAM_SUCCESS_UNKNOWN,
    EXAM_UNKNOWN,
    EXAM_WHATSAPP_CONSENT,
    EXAM_WHATSAPP_DIRECT,
    EXAM_WHATSAPP_PREFILL,
} from '@/copy/onboarding';

/**
 * Step 5 [028] — when is your next exam, and how may we reach you.
 *
 * THE ONE THING THIS SCREEN MUST NOT DO is make a teacher invent a date.
 * «עוד לא יודעת» is therefore a real button of equal weight, not a muted link:
 * a guessed date is indistinguishable from a real one downstream, and it would
 * send a human to phone her about an exam that does not exist. Answering
 * "I don't know" is what schedules the 14-day re-ask.
 *
 * CONSENT. The checkbox governs MESSAGING, not storage (owner ruling OD-2):
 * she may hand over a number to be called and still decline WhatsApp, and the
 * helper text says exactly what the number is for. It is unchecked by default
 * and there is no way for this component to send `whatsapp_opt_in` true without
 * a number — the server refuses that combination too.
 */
export function ExamStep({
    date,
    unknown,
    phone,
    whatsappOptIn,
    onDateChange,
    onUnknownToggle,
    onPhoneChange,
    onConsentChange,
    onBookingClick,
    whatsappNumber,
    bookingUrl,
}: {
    date: string;
    unknown: boolean;
    phone: string;
    whatsappOptIn: boolean;
    onDateChange: (value: string) => void;
    onUnknownToggle: () => void;
    onPhoneChange: (value: string) => void;
    onConsentChange: (value: boolean) => void;
    onBookingClick: () => void;
    whatsappNumber?: string;
    bookingUrl?: string;
}) {
    const showBooking = !unknown && isWithinBookingWindow(date) && Boolean(bookingUrl);

    // Rendered from the same two facts the payload is built from, so the line
    // she reads and the row we write can never disagree.
    const acknowledgement = unknown
        ? EXAM_SUCCESS_UNKNOWN
        : date.trim()
          ? EXAM_SUCCESS_DATE
          : null;

    const directChatHref = whatsappNumber
        ? `https://wa.me/${whatsappNumber}?text=${encodeURIComponent(EXAM_WHATSAPP_PREFILL)}`
        : null;

    return (
        <div className="space-y-5">
            <div className="space-y-2">
                <label
                    htmlFor="onboarding-exam-date"
                    className="block text-sm font-medium text-gray-600"
                >
                    {EXAM_DATE_LABEL}
                </label>
                <div className="flex flex-col gap-2.5 sm:flex-row sm:items-center">
                    {/*
                      * `dir="ltr"` on the CONTROL, inside an RTL container. A
                      * date input is internally left-to-right in every browser
                      * — its own segments (dd/mm/yyyy, the picker glyph) are
                      * laid out by the platform and cannot be flipped. Forcing
                      * the container RTL only strands the calendar icon on the
                      * wrong side of a field whose contents still read LTR. The
                      * label above it is the RTL half, which is the half that
                      * carries the meaning.
                      */}
                    <input
                        id="onboarding-exam-date"
                        type="date"
                        dir="ltr"
                        value={date}
                        min={todayISO()}
                        onChange={(e) => onDateChange(e.target.value)}
                        data-testid="exam-date"
                        // The ring COLOUR is declared in both branches on
                        // purpose. `focus:ring-2` in the shared half with the
                        // colour only in the active one leaves the muted state
                        // falling back to Tailwind's default ring — so a date
                        // field that is meant to read as stood-down still drew
                        // a bright ring, and next to a lit «עוד לא יודעת»
                        // button both controls looked selected. Caught by the
                        // §8 snapshot gate, in state (4), not by a test.
                        className={`w-full rounded-grade-ctl border bg-white px-4 py-3 text-base
                                    transition-colors focus:outline-none focus:ring-2 sm:flex-1
                                    ${
                                        unknown
                                            ? 'border-surface-200 text-gray-400 focus:border-surface-300 focus:ring-surface-300/50'
                                            : 'border-surface-300 text-gray-900 focus:border-primary-400 focus:ring-primary-400/40'
                                    }`}
                    />
                    <button
                        type="button"
                        onClick={onUnknownToggle}
                        aria-pressed={unknown}
                        data-testid="exam-unknown"
                        className={`shrink-0 rounded-grade-ctl border px-5 py-3 text-sm transition-colors
                                    ${
                                        unknown
                                            ? 'border-primary-500 bg-primary-50 font-medium text-primary-800'
                                            : 'border-surface-300 bg-white text-gray-700 hover:border-primary-300'
                                    }`}
                    >
                        {EXAM_UNKNOWN}
                    </button>
                </div>
                {acknowledgement && (
                    <p
                        data-testid="exam-acknowledgement"
                        className="text-sm text-primary-700"
                        aria-live="polite"
                    >
                        {acknowledgement}
                    </p>
                )}
            </div>

            <div className="space-y-2">
                <label
                    htmlFor="onboarding-exam-phone"
                    className="block text-sm font-medium text-gray-600"
                >
                    {EXAM_PHONE_LABEL}
                </label>
                <input
                    id="onboarding-exam-phone"
                    type="tel"
                    dir="ltr"
                    inputMode="tel"
                    value={phone}
                    onChange={(e) => onPhoneChange(e.target.value)}
                    placeholder={EXAM_PHONE_PLACEHOLDER}
                    data-testid="exam-phone"
                    className="w-full rounded-grade-ctl border border-surface-300 bg-white px-4 py-3
                               text-base text-gray-900 transition-colors focus:border-primary-400
                               focus:outline-none focus:ring-2 focus:ring-primary-400/40"
                />
                <p className="text-sm text-gray-500">{EXAM_PHONE_HELPER}</p>
                <label className="flex items-start gap-2.5 pt-0.5 text-sm text-gray-700">
                    <input
                        type="checkbox"
                        checked={whatsappOptIn}
                        onChange={(e) => onConsentChange(e.target.checked)}
                        data-testid="exam-consent"
                        className="mt-0.5 h-4 w-4 shrink-0 rounded border-surface-300
                                   text-primary-600 focus:ring-primary-400/40"
                    />
                    {/* Plain text, no link — see the copy module. */}
                    <span>{EXAM_WHATSAPP_CONSENT}</span>
                </label>
            </div>

            {directChatHref && (
                <a
                    href={directChatHref}
                    target="_blank"
                    rel="noopener noreferrer"
                    data-testid="exam-whatsapp-direct"
                    className="inline-flex items-center gap-2 text-sm font-medium text-primary-700
                               underline-offset-4 transition-colors hover:text-primary-800 hover:underline"
                >
                    <MessageCircle size={16} />
                    {EXAM_WHATSAPP_DIRECT}
                </a>
            )}

            {showBooking && (
                <div
                    data-testid="exam-booking"
                    className="rounded-grade-sm border border-primary-200 bg-primary-50/60 p-4"
                >
                    <div className="flex items-start gap-2.5">
                        <CalendarCheck size={18} className="mt-0.5 shrink-0 text-primary-700" />
                        <div className="space-y-1">
                            <p className="text-sm font-semibold text-primary-900">
                                {EXAM_BOOKING_TITLE}
                            </p>
                            <p className="text-sm text-primary-800">{EXAM_BOOKING_BODY}</p>
                        </div>
                    </div>
                    <a
                        href={bookingUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={onBookingClick}
                        data-testid="exam-booking-cta"
                        className="mt-3 inline-flex rounded-grade-ctl bg-primary-600 px-5 py-2.5
                                   text-sm font-medium text-white transition-colors hover:bg-primary-700"
                    >
                        {EXAM_BOOKING_CTA}
                    </a>
                </div>
            )}
        </div>
    );
}
