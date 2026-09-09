'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Loader2 } from 'lucide-react';

import { OnboardingDialog } from '@/components/onboarding/OnboardingDialog';
import { useAuth } from '@/lib/auth';

/**
 * The onboarding route.
 *
 * The dialog sits over a dimmed Vivi backdrop rather than over the live app: the
 * teacher cannot reach anything behind it yet, and a half-loaded dashboard
 * glowing through a wall she cannot cross is a promise the screen does not keep.
 * (The gradient is the signup page's, so the two first screens of the product
 * look like one place.)
 *
 * Two redirects it owns, both `replace`:
 *   * no session        → /login (this route is outside SidebarLayout, which is
 *                         what guards every other authenticated page)
 *   * already onboarded → /  (so the URL cannot be used to replay the flow)
 */
export default function OnboardingPage() {
    const { user, isLoading, isAuthenticated } = useAuth();
    const router = useRouter();

    const done = Boolean(user?.onboarding_completed_at);

    useEffect(() => {
        if (isLoading) return;
        if (!isAuthenticated) {
            router.replace('/login');
            return;
        }
        if (done) router.replace('/');
    }, [isLoading, isAuthenticated, done, router]);

    const ready = !isLoading && isAuthenticated && !done;

    return (
        <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-[#FFFaf2] p-4">
            <div className="pointer-events-none absolute inset-0 overflow-hidden">
                <div className="absolute right-[-10%] top-[-20%] h-[600px] w-[600px] rounded-full bg-gradient-to-br from-primary-200/40 via-primary-300/20 to-transparent blur-3xl" />
                <div className="absolute bottom-[-30%] left-[-15%] h-[700px] w-[700px] rounded-full bg-gradient-to-tr from-[#aa77f7]/20 via-[#aa77f7]/10 to-transparent blur-3xl" />
            </div>

            {ready ? (
                <OnboardingDialog />
            ) : (
                <Loader2
                    className="animate-spin text-primary-500 motion-reduce:animate-none"
                    size={28}
                    aria-label="טוען"
                />
            )}
        </div>
    );
}
