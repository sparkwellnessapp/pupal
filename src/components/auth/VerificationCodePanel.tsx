'use client';

import { useEffect, useRef, useState } from 'react';
import { Loader2 } from 'lucide-react';

import { useAuth } from '@/lib/auth';
import {
    RESEND_CTA,
    RESEND_FAILED,
    RESEND_SENT,
    RESEND_WAIT,
    VERIFY_CHECKING,
    VERIFY_CODE_LABEL,
    VERIFY_CTA,
    VERIFY_EXPIRED_HINT,
    VERIFY_START_OVER,
    VERIFY_SUBTITLE,
    VERIFY_TITLE,
    VERIFY_WRONG_ADDRESS,
    VERIFY_WRONG_CODE,
} from '@/copy/auth';

/** Mirrors the server's cooldown. The server is the authority — this only stops
 *  her pressing a button that will be silently ignored. */
const RESEND_COOLDOWN_SECONDS = 60;

/**
 * The six-digit code step.
 *
 * Shown after a signup, and also after a login that returned 403 — an account
 * created before it was verified is exactly the case where a teacher has the
 * right password and still cannot get in.
 */
export function VerificationCodePanel({
    email,
    onVerified,
    onStartOver,
}: {
    email: string;
    onVerified: () => void;
    onStartOver?: () => void;
}) {
    const { verifyEmail, resendCode } = useAuth();

    const [code, setCode] = useState('');
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [notice, setNotice] = useState<string | null>(null);
    const [cooldown, setCooldown] = useState(RESEND_COOLDOWN_SECONDS);
    const inputRef = useRef<HTMLInputElement | null>(null);

    // The code was sent as she arrived, so the cooldown starts running now.
    useEffect(() => {
        if (cooldown <= 0) return;
        const id = setInterval(() => setCooldown((s) => (s > 0 ? s - 1 : 0)), 1000);
        return () => clearInterval(id);
    }, [cooldown]);

    useEffect(() => {
        inputRef.current?.focus();
    }, []);

    const submit = async (value: string) => {
        if (busy) return;
        setBusy(true);
        setError(null);
        setNotice(null);
        try {
            await verifyEmail(email, value);
            onVerified();
        } catch (err) {
            setError(err instanceof Error && err.message ? err.message : VERIFY_WRONG_CODE);
            setCode('');
            inputRef.current?.focus();
        } finally {
            setBusy(false);
        }
    };

    const onChange = (raw: string) => {
        // Digits only, six max. Strips a pasted code's spaces so «123 456» works.
        const digits = raw.replace(/[^0-9]/g, '').slice(0, 6);
        setCode(digits);
        setError(null);
        // Auto-submit on the sixth digit: she has no other decision to make here,
        // and a code panel that then asks her to find a button is one step too
        // many at the end of a signup.
        if (digits.length === 6) void submit(digits);
    };

    const resend = async () => {
        if (cooldown > 0 || busy) return;
        setError(null);
        try {
            await resendCode(email);
            setNotice(RESEND_SENT);
            setCooldown(RESEND_COOLDOWN_SECONDS);
        } catch {
            setError(RESEND_FAILED);
        }
    };

    return (
        <div className="space-y-5" data-testid="verify-panel">
            <div className="space-y-1.5 text-center">
                <h2 className="text-2xl font-semibold text-gray-900">{VERIFY_TITLE}</h2>
                <p className="text-sm text-gray-500">{VERIFY_SUBTITLE(email)}</p>
            </div>

            <div className="space-y-1.5">
                <label htmlFor="verification-code" className="block text-sm font-medium text-gray-600">
                    {VERIFY_CODE_LABEL}
                </label>
                <input
                    id="verification-code"
                    ref={inputRef}
                    // LTR and centred: a six-digit number inside an RTL page
                    // must not reorder, and the caret belongs on the left.
                    dir="ltr"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    value={code}
                    onChange={(e) => onChange(e.target.value)}
                    disabled={busy}
                    aria-invalid={Boolean(error)}
                    data-testid="verify-code-input"
                    className="w-full rounded-grade-ctl border border-surface-300 bg-white px-4 py-3
                               text-center text-2xl tracking-[0.4em] transition-colors
                               focus:border-primary-400 focus:outline-none focus:ring-2
                               focus:ring-primary-400/40 disabled:bg-surface-100"
                />
                <p className="text-xs text-gray-400">{VERIFY_EXPIRED_HINT}</p>
            </div>

            {error && (
                <p role="alert" data-testid="verify-error" className="text-sm text-red-700">
                    {error}
                </p>
            )}
            {notice && <p className="text-sm text-primary-700">{notice}</p>}

            <button
                type="button"
                onClick={() => void submit(code)}
                disabled={busy || code.length !== 6}
                data-testid="verify-submit"
                className="flex w-full items-center justify-center gap-2 rounded-grade-ctl
                           bg-primary-600 px-6 py-3 text-sm font-medium text-white
                           transition-colors hover:bg-primary-700 disabled:opacity-60"
            >
                {busy ? (
                    <>
                        <Loader2 size={16} className="animate-spin motion-reduce:animate-none" />
                        {VERIFY_CHECKING}
                    </>
                ) : (
                    VERIFY_CTA
                )}
            </button>

            <div className="flex items-center justify-between text-sm">
                <button
                    type="button"
                    onClick={() => void resend()}
                    disabled={cooldown > 0 || busy}
                    data-testid="verify-resend"
                    className="text-primary-700 transition-colors hover:text-primary-900
                               disabled:text-gray-400"
                >
                    {cooldown > 0 ? RESEND_WAIT(cooldown) : RESEND_CTA}
                </button>

                {onStartOver && (
                    <button
                        type="button"
                        onClick={onStartOver}
                        className="text-gray-500 transition-colors hover:text-gray-700"
                    >
                        {VERIFY_WRONG_ADDRESS} {VERIFY_START_OVER}
                    </button>
                )}
            </div>
        </div>
    );
}
