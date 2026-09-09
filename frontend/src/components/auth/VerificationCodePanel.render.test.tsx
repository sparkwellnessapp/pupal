import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

/**
 * SSR guards for the code step (the suite's node/SSR convention — no jsdom).
 * Effects do not run here, which is right for pinning the FIRST paint: what she
 * sees the instant the panel replaces the signup form.
 */

vi.mock('next/navigation', () => ({
    useRouter: () => ({ push: () => {}, replace: () => {} }),
    usePathname: () => '/signup',
}));

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        verifyEmail: async () => {},
        resendCode: async () => {},
        adoptSession: () => {},
        user: null,
        isLoading: false,
        isAuthenticated: false,
    }),
    getAuthHeaders: () => ({}),
}));

import { VerificationCodePanel } from './VerificationCodePanel';
import {
    RESEND_WAIT,
    VERIFY_CTA,
    VERIFY_EXPIRED_HINT,
    VERIFY_TITLE,
} from '@/copy/auth';

const html = (email = 'michal@school.org') =>
    renderToStaticMarkup(
        <VerificationCodePanel email={email} onVerified={() => {}} />,
    );

describe('VerificationCodePanel', () => {
    it('names the address the code went to', () => {
        expect(html()).toContain('michal@school.org');
    });

    it('states the title and the CTA', () => {
        const out = html();
        expect(out).toContain(VERIFY_TITLE);
        expect(out).toContain(VERIFY_CTA);
    });

    it('says how long the code lasts, so an expiry is not a surprise', () => {
        expect(html()).toContain(VERIFY_EXPIRED_HINT);
    });

    it('renders the code input LTR — six digits must not reorder in an RTL page', () => {
        expect(html()).toContain('dir="ltr"');
    });

    // Case-insensitive: React's SSR preserves the camelCase prop name, and the
    // GUARANTEE is the attribute reaching the browser, not how the serializer
    // spells it.
    it('asks the browser for the one-time code autofill', () => {
        expect(html().toLowerCase()).toContain('autocomplete="one-time-code"');
    });

    it('uses a numeric keypad on mobile', () => {
        expect(html().toLowerCase()).toContain('inputmode="numeric"');
    });

    it('disables submit until six digits are present', () => {
        // First paint: the field is empty, so the button must not be pressable.
        expect(html()).toContain('disabled=""');
    });

    it('starts the resend control in its cooldown', () => {
        // The code was just sent; offering "send again" immediately would
        // promise something the server silently refuses for 60s.
        expect(html()).toContain(RESEND_WAIT(60));
    });

    it('shows no error before anything failed', () => {
        expect(html()).not.toContain('verify-error');
    });

    it('omits the start-over affordance when the caller gives no handler', () => {
        expect(html()).not.toContain('להתחיל מחדש');
    });

    it('offers start-over when the caller does', () => {
        const out = renderToStaticMarkup(
            <VerificationCodePanel
                email="a@b.co"
                onVerified={() => {}}
                onStartOver={() => {}}
            />,
        );
        expect(out).toContain('להתחיל מחדש');
    });
});
