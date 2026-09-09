import { describe, it, expect, vi } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';

/**
 * SSR render guards for the onboarding shell (the suite's node/SSR convention —
 * no jsdom). Effects do not run here, which is exactly right for pinning what
 * the FIRST paint shows: the logo, the progress bar, and a footer that never
 * moves.
 */

vi.mock('next/navigation', () => ({
    useRouter: () => ({ replace: () => {}, push: () => {} }),
    usePathname: () => '/onboarding',
}));

const user = {
    id: 'u1',
    email: 'a@b.co',
    full_name: 'מיכל כהן',
    subscription_status: 'trial',
    is_subscription_active: true,
    subject_matters: [],
    created_at: '2026-01-01T00:00:00Z',
    onboarding_completed_at: null,
    schools: [],
};

vi.mock('@/lib/auth', () => ({
    useAuth: () => ({
        user,
        token: 't',
        isLoading: false,
        isAuthenticated: true,
        applyUser: () => {},
        refreshUser: async () => {},
        login: async () => {},
        signup: async () => {},
        logout: () => {},
    }),
    getAuthHeaders: () => ({}),
}));

import { OnboardingDialog } from './OnboardingDialog';
import { ProgressBar } from './ProgressBar';
import { WELCOME_CTA, WELCOME_TITLE, BACK, SCHOOLS_SKIP } from '@/copy/onboarding';

const html = () => renderToStaticMarkup(<OnboardingDialog />);

describe('OnboardingDialog — the shell', () => {
    it('shows the Vivi logo', () => {
        expect(html()).toContain('/vivi-logo-no-background-no-slogan.png');
    });

    it('shows the progress bar on the first step', () => {
        expect(html()).toContain('onboarding-progress');
    });

    it('opens on the welcome step with its own CTA', () => {
        const out = html();
        expect(out).toContain(WELCOME_TITLE);
        expect(out).toContain(WELCOME_CTA);
    });

    it('offers no way back from the first step', () => {
        expect(html()).not.toContain(BACK);
    });

    it('offers no skip on a non-skippable step', () => {
        expect(html()).not.toContain(SCHOOLS_SKIP);
    });

    it('reserves the body height so the footer cannot move between steps', () => {
        expect(html()).toContain('min-h-[18rem]');
    });

    it('renders a labelled modal dialog', () => {
        const out = html();
        expect(out).toContain('role="dialog"');
        expect(out).toContain('aria-modal="true"');
        expect(out).toContain('onboarding-title');
    });

    it('shows no error banner before anything has failed', () => {
        expect(html()).not.toContain('onboarding-error');
    });
});

describe('ProgressBar', () => {
    const bar = (step: number, total = 5) =>
        renderToStaticMarkup(<ProgressBar step={step} total={total} />);

    it('fills proportionally to the step', () => {
        expect(bar(1)).toContain('width:20%');
        expect(bar(3)).toContain('width:60%');
        expect(bar(5)).toContain('width:100%');
    });

    it('is turquoise — the existing primary ramp, not a new color', () => {
        expect(bar(1)).toContain('from-primary-400');
        expect(bar(1)).toContain('to-primary-600');
    });

    it('grows from the right, because the document is RTL', () => {
        expect(bar(1)).toContain('bg-gradient-to-l');
    });

    it('exposes progress to assistive tech', () => {
        const out = bar(2);
        expect(out).toContain('role="progressbar"');
        expect(out).toContain('aria-valuenow="2"');
        expect(out).toContain('aria-valuemax="5"');
    });

    it('clamps rather than overflowing on out-of-range input', () => {
        expect(bar(9)).toContain('width:100%');
        expect(bar(-1)).toContain('width:0%');
    });

    it('collapses its motion under prefers-reduced-motion', () => {
        expect(bar(1)).toContain('motion-reduce:transition-none');
    });
});
