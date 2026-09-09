'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Script from 'next/script';

import { useAuth } from '@/lib/auth';
import { GOOGLE_NEEDS_VERIFY, GOOGLE_UNAVAILABLE } from '@/copy/auth';

/**
 * "Sign in with Google" — the Google Identity Services button.
 *
 * WHY THE ID-TOKEN FLOW (owner ruling A2): Google hands the browser a signed
 * JWT, we post it to our own backend, verify it there, and mint OUR session.
 * No redirect URIs, no client secret, no refresh tokens — the only question
 * Google is asked is "who is this".
 *
 * FedCM has been mandatory since August 2025, so `accounts.google.com/gsi/client`
 * IS the current library; there is no legacy `gapi.auth2` path to fall into.
 *
 * THE NONCE IS NOT OPTIONAL HERE. A Google credential is a bearer token for
 * ~1 hour. We fetch a server-issued nonce first, Google embeds it in the token
 * it signs, and the server spends it exactly once — which is what stops a
 * stolen credential being replayed. If the nonce cannot be fetched the button
 * does not render, because rendering it without one would silently downgrade
 * the security of every sign-in.
 */

interface GsiCredentialResponse {
    credential: string;
}

declare global {
    interface Window {
        google?: {
            accounts: {
                id: {
                    initialize: (config: Record<string, unknown>) => void;
                    renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
                };
            };
        };
    }
}

const CLIENT_ID = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || '';
const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

/** Waits BETWEEN attempts, so the count of attempts is this + 1. */
const NONCE_RETRY_BACKOFF_MS = [400, 1200];

/**
 * Fetch a nonce, retrying a transient failure. Resolves to the nonce, or to
 * null once the attempts are spent.
 *
 * WHY THIS EXISTS. The nonce is fetched exactly once per page load, and without
 * it the button does not render at all — so a single failed request used to
 * kill Sign in with Google until the teacher manually reloaded. That is not a
 * rare edge: `uvicorn --reload` restarts on every backend file save, so any
 * page load landing in that window lost the button, and in production a network
 * blip does the same.
 *
 * WHY THE RETRY LIVES *HERE* AND NOWHERE LATER. A nonce is single-use and is
 * handed to GIS by `initialize()`. Retrying after that point would leave Google
 * signing a token carrying nonce #1 while we post nonce #2, and the server would
 * refuse an entirely legitimate sign-in — the same defect StrictMode's double
 * mount produced. Before `initialize` is the only safe place, which is exactly
 * where this sits.
 *
 * A response without a `nonce` field counts as a FAILURE rather than being
 * stored: an undefined nonce renders no button and would post `undefined`.
 */
async function fetchNonceWithRetry(): Promise<string | null> {
    for (let attempt = 0; ; attempt += 1) {
        try {
            const res = await fetch(`${API_BASE}/api/v0/auth/google/nonce`);
            if (!res.ok) throw new Error(`nonce request failed: ${res.status}`);
            const data = await res.json();
            if (typeof data?.nonce === 'string' && data.nonce) return data.nonce;
            throw new Error('nonce missing from response');
        } catch {
            const backoff = NONCE_RETRY_BACKOFF_MS[attempt];
            if (backoff === undefined) return null;      // attempts spent
            await new Promise((resolve) => setTimeout(resolve, backoff));
        }
    }
}

export function GoogleSignInButton({ onError }: { onError?: (message: string) => void }) {
    const router = useRouter();
    const { adoptSession } = useAuth();

    const holder = useRef<HTMLDivElement | null>(null);
    const [scriptReady, setScriptReady] = useState(false);
    const [nonce, setNonce] = useState<string | null>(null);
    const rendered = useRef(false);
    const nonceRequested = useRef(false);

    // EXACTLY ONE nonce per mount, guarded by a ref rather than by the effect's
    // dependency list. React StrictMode double-invokes mount effects in dev, and
    // a second fetch does not merely waste a nonce: the first one has already
    // been handed to GIS by initialize(), so the token Google signs would embed
    // nonce #1 while this component posts nonce #2 — and the server would refuse
    // a sign-in that was entirely legitimate. Caught by the auth e2e.
    useEffect(() => {
        if (nonceRequested.current) return;
        nonceRequested.current = true;

        // NO `alive` flag here, deliberately. The usual cleanup idiom is wrong
        // in combination with the ref guard: StrictMode runs the effect, tears
        // it down (flipping `alive` to false), then runs it again — where the
        // guard returns early. The one in-flight sequence would then resolve
        // into a dead flag, the nonce would never land, and the button would
        // never render at all. The guard already guarantees a single sequence,
        // and a setState after unmount is a no-op in React 18.
        void fetchNonceWithRetry().then((value) => {
            if (value) setNonce(value);
            else onError?.(GOOGLE_UNAVAILABLE);
        });
        // onError is a render-scope callback; re-running on it would refetch a
        // nonce on every parent render and burn them.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const handleCredential = useCallback(
        async (response: GsiCredentialResponse) => {
            try {
                const res = await fetch(`${API_BASE}/api/v0/auth/google`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ credential: response.credential, nonce }),
                });

                if (!res.ok) {
                    // 409 is the ONE Google failure with a real next step: an
                    // unverified account already holds this address, so she must
                    // prove the mailbox before the identities may be joined.
                    onError?.(res.status === 409 ? GOOGLE_NEEDS_VERIFY : GOOGLE_UNAVAILABLE);
                    return;
                }

                const data = await res.json();
                adoptSession(data.access_token, data.user);
                router.push('/');
            } catch {
                onError?.(GOOGLE_UNAVAILABLE);
            }
        },
        [nonce, adoptSession, router, onError],
    );

    useEffect(() => {
        if (!scriptReady || !nonce || !holder.current || rendered.current) return;
        if (!CLIENT_ID || !window.google) return;

        window.google.accounts.id.initialize({
            client_id: CLIENT_ID,
            callback: handleCredential,
            nonce,
        });
        window.google.accounts.id.renderButton(holder.current, {
            theme: 'outline',
            size: 'large',
            shape: 'pill',
            text: 'continue_with',
            locale: 'he',
            width: 320,
        });
        // Rendered ONCE per mount: GIS appends an iframe, and re-running would
        // stack a second button under the first.
        rendered.current = true;
    }, [scriptReady, nonce, handleCredential]);

    // No client ID configured ⇒ render nothing at all. A dead button is worse
    // than no button: it invites a teacher to click something that cannot work.
    if (!CLIENT_ID) return null;

    return (
        <>
            <Script
                src="https://accounts.google.com/gsi/client"
                strategy="afterInteractive"
                onReady={() => setScriptReady(true)}
                onError={() => onError?.(GOOGLE_UNAVAILABLE)}
            />
            <div ref={holder} data-testid="google-signin" className="flex justify-center" />
        </>
    );
}
