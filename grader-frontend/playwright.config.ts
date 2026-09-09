import { defineConfig, devices } from '@playwright/test';

/**
 * PR-4 Phase 6 — the RENDER-HALF guard (census G12).
 *
 * The vitest suites close the data-integrity half (codec, validators, achievable);
 * they run in Node and never render React, so they cannot catch a white-screen. THIS
 * suite drives the real browser through the two journeys where "curl passed, browser
 * died" actually happened — bagrut (depth-2 render / the toFixed crash) and employee
 * (selection achievable). The whole API surface is ROUTE-MOCKED (see e2e/fixtures.ts),
 * so it is deterministic, free, and offline: the live Cloud-Tasks→OIDC→runner hop
 * stays owned by PR-1's manual deploy-verification protocol, not this suite.
 *
 * Browsers install in the CI substrate (see .github/workflows). If a local box cannot
 * fetch Chromium, this suite is CI-only by design — do not fake a local substitute.
 */
export default defineConfig({
    testDir: './e2e',
    timeout: 90_000,
    expect: { timeout: 15_000 },
    fullyParallel: false,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 1 : 0,
    workers: 1,
    reporter: 'line',
    use: {
        baseURL: 'http://localhost:3100',
        navigationTimeout: 60_000,
        actionTimeout: 20_000,
        trace: 'on-first-retry',
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
    webServer: {
        // NEXT_DIST_DIR: the harness's dev server must NEVER share .next with
        // the user's own dev server — two writers corrupt each other's chunk
        // manifests and the OTHER process 404s mid-session (bit the owner's
        // live E2E on 2026-08-22; see next.config.js).
        //
        // ⚠️ TWO CONCURRENT PLAYWRIGHT RUNS share `.next-e2e` and hit the SAME
        // failure from the other direction (twice on 2026-08-31): one run's
        // teardown kills the server the other is still driving, and every
        // remaining test fails with ERR_CONNECTION_REFUSED while a ZOMBIE
        // listener keeps holding port 3100 and answering nothing — so the next
        // `reuseExistingServer` probe fails too, and Playwright's own spawn
        // then cannot bind. A wall of failures with that signature is
        // INFRASTRUCTURE, not findings: check `curl localhost:3100` before
        // believing any of them, and re-run on a quiet tree.
        env: {
            NEXT_DIST_DIR: '.next-e2e',
            // The Google button renders NOTHING without a client ID — a
            // deliberate product choice (a dead sign-in button is worse than
            // no button), which also means the auth journeys cannot see it
            // unless the harness supplies one. Any non-empty value works: the
            // GIS script is stubbed in e2e/auth.spec.ts and never contacts
            // Google.
            NEXT_PUBLIC_GOOGLE_CLIENT_ID: 'e2e-stub.apps.googleusercontent.com',
            // [028] The exam step renders its booking block and its
            // "talk to me on WhatsApp" link ONLY when these are set — the same
            // deliberate choice as the Google button above: a dead link is
            // worse than no link. Stubbed here so the harness does not depend
            // on a developer's .env.local, and never contacted: the booking CTA
            // opens a new tab the spec does not follow.
            NEXT_PUBLIC_BOOKING_URL: 'https://example.test/e2e-booking',
            NEXT_PUBLIC_WHATSAPP_NUMBER: '972500000000',
        },
        command: 'npm run dev -- --port 3100',
        url: 'http://localhost:3100',
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
    },
});
