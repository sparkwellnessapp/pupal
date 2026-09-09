'use client';

import { useEffect } from 'react';
import { usePathname, useRouter } from 'next/navigation';

import { useAuth } from '@/lib/auth';

/**
 * Sends an authenticated teacher who has not finished onboarding to
 * `/onboarding`, and renders nothing.
 *
 * Mounted ONCE, in the root layout inside AuthProvider. It deliberately does not
 * own the unauthenticated redirect — SidebarLayout already does that, and two
 * components racing to redirect the same session is how a bounce loop starts.
 *
 * `replace`, not `push`: onboarding must not sit in the back stack, or «חזרה»
 * in the browser walks her back into a flow she completed.
 */
const PUBLIC_PATHS = new Set(['/login', '/signup', '/onboarding']);

export function OnboardingGate() {
    const { user, isLoading, isAuthenticated } = useAuth();
    const pathname = usePathname();
    const router = useRouter();

    const done = Boolean(user?.onboarding_completed_at);

    useEffect(() => {
        // Never redirect on an unresolved session: during the first render the
        // token is still being read from localStorage, and acting on that empty
        // state would throw an authenticated teacher out of her own app.
        if (isLoading || !isAuthenticated || !user) return;
        if (done) return;
        if (pathname && PUBLIC_PATHS.has(pathname)) return;

        router.replace('/onboarding');
    }, [isLoading, isAuthenticated, user, done, pathname, router]);

    return null;
}
