import { test, expect, type Page, type Route } from '@playwright/test';

/**
 * Sign-in / sign-up journeys — the render half no vitest suite reaches.
 *
 * Google's script is STUBBED, deliberately: `accounts.google.com/gsi/client` is
 * not under test and cannot be driven offline. What IS under test is our
 * handling of what it produces — the nonce round-trip, posting the credential,
 * adopting the session, and the one Google failure that has a real next step
 * (409: an unverified account already holds this address).
 */

const API = '**/api/v0/**';

interface Recorded {
    signups: { email: string }[];
    verifies: { email: string; code: string }[];
    resends: string[];
    googlePosts: { credential: string; nonce: string }[];
    noncesIssued: number;
    nonceRequests: number;
}

const SESSION = (email: string) => ({
    access_token: 'stub.token.value',
    token_type: 'bearer',
    expires_in: 604800,
    user: {
        id: 'u1',
        email,
        full_name: 'מיכל כהן',
        subscription_status: 'active',
        is_subscription_active: true,
        subject_matters: [],
        created_at: '2026-01-01T00:00:00Z',
        // Null so the onboarding gate takes over after sign-in — the honest
        // destination for a brand-new teacher.
        onboarding_completed_at: null,
        gender: null,
        schools: [],
        primary_school_id: null,
    },
});

async function setup(
    page: Page,
    opts: {
        loginStatus?: number;
        googleStatus?: number;
        /** Fail the first N nonce requests, to exercise the retry. */
        nonceFailures?: number;
        /**
         * Hold the nonce response open, standing in for the cold Cloud Run
         * start that produced this defect (11.75s measured, 2026-09-10). It is
         * the only way to observe the slot BEFORE the button can exist.
         */
        nonceDelayMs?: number;
    } = {},
): Promise<Recorded> {
    const rec: Recorded = {
        signups: [], verifies: [], resends: [], googlePosts: [],
        noncesIssued: 0, nonceRequests: 0,
    };

    // The GIS script itself: served as a no-op so `next/script` fires onReady.
    await page.route('https://accounts.google.com/gsi/client', (route) =>
        route.fulfill({ status: 200, contentType: 'application/javascript', body: '/* stub */' }),
    );

    // window.google, installed before any app code runs. renderButton draws a
    // REAL button so the test clicks what a teacher would click.
    await page.addInitScript(() => {
        (window as unknown as { google: unknown }).google = {
            accounts: {
                id: {
                    _cb: null as unknown,
                    initialize(config: { callback: (r: { credential: string }) => void }) {
                        (window as unknown as { __gsiCallback: unknown }).__gsiCallback =
                            config.callback;
                        (window as unknown as { __gsiNonce: unknown }).__gsiNonce =
                            (config as unknown as { nonce: string }).nonce;
                    },
                    renderButton(parent: HTMLElement) {
                        const b = document.createElement('button');
                        b.textContent = 'Continue with Google';
                        b.setAttribute('data-testid', 'gsi-button');
                        b.onclick = () => {
                            const cb = (window as unknown as {
                                __gsiCallback: (r: { credential: string }) => void;
                            }).__gsiCallback;
                            cb({ credential: 'stub-id-token' });
                        };
                        parent.appendChild(b);
                    },
                },
            },
        };
    });

    const json = (route: Route, body: unknown, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    await page.route(API, async (route) => {
        const req = route.request();
        const url = req.url();
        const method = req.method();

        if (method === 'GET' && url.includes('/auth/google/nonce')) {
            rec.nonceRequests += 1;
            if (rec.nonceRequests <= (opts.nonceFailures ?? 0)) {
                // A backend mid-restart, or a network blip.
                return json(route, { detail: 'boom' }, 503);
            }
            if (opts.nonceDelayMs) {
                await new Promise((r) => setTimeout(r, opts.nonceDelayMs));
            }
            rec.noncesIssued += 1;
            return json(route, { nonce: `nonce-${rec.noncesIssued}` });
        }

        if (method === 'POST' && url.endsWith('/auth/google')) {
            rec.googlePosts.push(req.postDataJSON());
            if (opts.googleStatus && opts.googleStatus !== 200) {
                return json(route, { detail: 'כבר קיים חשבון...' }, opts.googleStatus);
            }
            return json(route, SESSION('michal@school.org'));
        }

        if (method === 'POST' && url.endsWith('/auth/signup')) {
            rec.signups.push(req.postDataJSON());
            return json(route, {
                verification_required: true,
                email: req.postDataJSON().email,
                resend_available_in_seconds: 0,
            });
        }

        if (method === 'POST' && url.endsWith('/auth/verify-email')) {
            const body = req.postDataJSON();
            rec.verifies.push(body);
            if (body.code !== '123456') {
                return json(route, { detail: 'הקוד שגוי או שפג תוקפו' }, 400);
            }
            return json(route, SESSION(body.email));
        }

        if (method === 'POST' && url.endsWith('/auth/resend-code')) {
            rec.resends.push(req.postDataJSON().email);
            return json(route, { message: 'אם הכתובת רשומה, שלחנו אליה קוד חדש.' }, 202);
        }

        if (method === 'POST' && url.endsWith('/auth/login')) {
            if (opts.loginStatus === 403) {
                return json(route, { detail: 'החשבון עדיין לא אומת.' }, 403);
            }
            return json(route, SESSION(req.postDataJSON().email));
        }

        return json(route, []);
    });

    return rec;
}

async function fillSignup(page: Page, email: string) {
    await page.locator('input[type="text"]').first().fill('מיכל כהן');
    await page.locator('input[type="email"]').fill(email);
    const passwords = page.locator('input[type="password"]');
    await passwords.nth(0).fill('testpass123');
    await passwords.nth(1).fill('testpass123');
}

// --- signup ------------------------------------------------------------------

test('signup shows the code step and does NOT sign her in', async ({ page }) => {
    const rec = await setup(page);
    await page.goto('/signup');

    await fillSignup(page, 'michal@school.org');
    await page.locator('form button[type="submit"]').click();

    await expect(page.getByTestId('verify-panel')).toBeVisible();
    expect(rec.signups).toHaveLength(1);
    // Still on /signup: a session was never issued, so nothing navigated.
    await expect(page).toHaveURL(/\/signup$/);
});

test('the right code signs her in and lands her in onboarding', async ({ page }) => {
    const rec = await setup(page);
    await page.goto('/signup');
    await fillSignup(page, 'michal@school.org');
    await page.locator('form button[type="submit"]').click();
    await expect(page.getByTestId('verify-panel')).toBeVisible();

    // Typing the sixth digit auto-submits — she has no other decision to make
    // here. Wait on the OUTCOME before reading what was recorded; asserting the
    // request synchronously races the submit that the keystroke started.
    await page.getByTestId('verify-code-input').fill('123456');

    // A brand-new teacher goes to onboarding, not to the app.
    await expect(page).toHaveURL(/\/onboarding$/);
    expect(rec.verifies).toHaveLength(1);
    expect(rec.verifies[0].code).toBe('123456');
});

test('a wrong code keeps her on the panel and says so', async ({ page }) => {
    await setup(page);
    await page.goto('/signup');
    await fillSignup(page, 'michal@school.org');
    await page.locator('form button[type="submit"]').click();
    await expect(page.getByTestId('verify-panel')).toBeVisible();

    await page.getByTestId('verify-code-input').fill('999999');

    await expect(page.getByTestId('verify-error')).toBeVisible();
    await expect(page.getByTestId('verify-panel')).toBeVisible();
    await expect(page).toHaveURL(/\/signup$/);
});

test('the code step survives a reload', async ({ page }) => {
    await setup(page);
    await page.goto('/signup');
    await fillSignup(page, 'michal@school.org');
    await page.locator('form button[type="submit"]').click();
    await expect(page.getByTestId('verify-panel')).toBeVisible();

    await page.reload();

    // Without the sessionStorage handoff she would land back on an empty form
    // holding an account she cannot reach and an address she cannot re-register.
    await expect(page.getByTestId('verify-panel')).toBeVisible();
});

// --- Sign in with Google -----------------------------------------------------

test('the Google button posts the credential WITH the server-issued nonce', async ({ page }) => {
    const rec = await setup(page);
    await page.goto('/login');

    await page.getByTestId('gsi-button').click();

    await expect.poll(() => rec.googlePosts.length).toBe(1);
    expect(rec.googlePosts[0].credential).toBe('stub-id-token');
    // The nonce came from OUR server, not from the client: without it the
    // credential would be replayable for its whole ~1h lifetime.
    expect(rec.googlePosts[0].nonce).toBe('nonce-1');
    expect(rec.noncesIssued).toBeGreaterThan(0);
});

test('a successful Google sign-in adopts the session and leaves the login page', async ({ page }) => {
    await setup(page);
    await page.goto('/login');

    await page.getByTestId('gsi-button').click();

    await expect(page).not.toHaveURL(/\/login$/);
});

test('the 409 nOAuth refusal is explained, not swallowed', async ({ page }) => {
    await setup(page, { googleStatus: 409 });
    await page.goto('/login');

    await page.getByTestId('gsi-button').click();

    // She must learn there is an unverified account to prove first — the one
    // Google failure with an action attached.
    await expect(page.getByText(/לא אומת/)).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
});

test('the button appears on BOTH entry pages', async ({ page }) => {
    await setup(page);
    await page.goto('/login');
    await expect(page.getByTestId('gsi-button')).toBeVisible();

    await page.goto('/signup');
    await expect(page.getByTestId('gsi-button')).toBeVisible();
});

/**
 * The slot while the nonce is in flight.
 *
 * REPORTED AS "the Google button is only on the login page". It was on both,
 * in code and in production — but the button needs a server-issued nonce, and
 * the nonce comes from a Cloud Run service at `minScale=0` whose first request
 * after an idle period measured 11.75s (2026-09-10). The slot rendered as an
 * EMPTY div for those twelve seconds, so a slow dependency was indistinguishable
 * from an absent feature — and /signup is the page a teacher opens cold.
 */
test('a pending nonce shows a skeleton on BOTH pages, not an empty gap', async ({ page }) => {
    await setup(page, { nonceDelayMs: 4000 });

    for (const path of ['/login', '/signup']) {
        await page.goto(path);
        // Before the nonce lands the slot is OCCUPIED and says what it is…
        const skeleton = page.getByTestId('google-signin-skeleton');
        await expect(skeleton).toBeVisible();
        await expect(skeleton).toHaveAttribute('role', 'status');
        // …and it is NOT something she can press: no button, no link.
        await expect(page.getByTestId('gsi-button')).toHaveCount(0);

        // …then the real button replaces it, leaving exactly one control.
        await expect(page.getByTestId('gsi-button')).toBeVisible({ timeout: 15_000 });
        await expect(skeleton).toHaveCount(0);
    }
});

test('a nonce that never arrives retires the skeleton — no endless shimmer', async ({ page }) => {
    await setup(page, { nonceFailures: 99 });
    await page.goto('/signup');

    // The page says why, in its own banner…
    await expect(page.getByText(/אינה זמינה/)).toBeVisible({ timeout: 15_000 });
    // …and the slot does not keep promising a button that is not coming.
    await expect(page.getByTestId('google-signin-skeleton')).toHaveCount(0);
    await expect(page.getByTestId('gsi-button')).toHaveCount(0);
});

// --- login into an unverified account ---------------------------------------

test('a correct password on an unverified account opens the code step', async ({ page }) => {
    const rec = await setup(page, { loginStatus: 403 });
    await page.goto('/login');

    await page.locator('input[type="email"]').fill('michal@school.org');
    await page.locator('input[type="password"]').fill('testpass123');
    await page.locator('form button[type="submit"]').click();

    await expect(page.getByTestId('verify-panel')).toBeVisible();
    // A code was sent — she is not asked for one she never received.
    expect(rec.resends).toContain('michal@school.org');
});

test('a transient nonce failure self-heals — no reload needed', async ({ page }) => {
    // The button renders ONLY once a nonce lands, so before the retry existed a
    // single failed request killed Sign in with Google for that whole page load.
    // `uvicorn --reload` restarting on a file save made that a routine dev event.
    const rec = await setup(page, { nonceFailures: 1 });
    await page.goto('/login');

    await expect(page.getByTestId('gsi-button')).toBeVisible();
    expect(rec.nonceRequests).toBeGreaterThan(1);

    // And the nonce it ended up with is the one it POSTs — the retry must not
    // leave GIS holding a different value than the component sends.
    await page.getByTestId('gsi-button').click();
    await expect.poll(() => rec.googlePosts.length).toBe(1);
    expect(rec.googlePosts[0].nonce).toBe('nonce-1');
});

test('the retry is bounded — it gives up and says so', async ({ page }) => {
    // Not infinite: a backend that is genuinely down must produce an honest
    // message, not a spinner forever.
    await setup(page, { nonceFailures: 99 });
    await page.goto('/login');

    await expect(page.getByText(/אינה זמינה/)).toBeVisible({ timeout: 15_000 });
    await expect(page.getByTestId('gsi-button')).toHaveCount(0);
});
