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
        command: 'npm run dev -- --port 3100',
        url: 'http://localhost:3100',
        reuseExistingServer: !process.env.CI,
        timeout: 180_000,
    },
});
