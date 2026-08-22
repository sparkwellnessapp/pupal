import { defineConfig, devices } from '@playwright/test';

// Specs that assert DEV-ONLY semantics (React StrictMode's double mount) read
// this to state their constraint explicitly instead of silently passing or
// silently skipping. See e2e/batch-review-freeze.spec.ts.
process.env.PW_PROD_BUILD = '1';

/**
 * F1 (closeout) — the PRODUCTION-BUILD run.
 *
 * Every behavioural spec in this project has only ever executed under `next
 * dev`: React StrictMode double-mounts, effects run twice, errors are
 * unminified. That is load-bearing on purpose (the freeze spec asserts a
 * StrictMode mount PAIR, and it caught a real bug in P2) — but it means the
 * corpus has never once run under the semantics that actually ship.
 *
 * This config points at a `next start` server and starts NO webServer of its
 * own, so it cannot silently fall back to the dev instance. The base config
 * hardcodes port 3100; overriding baseURL via an env var does nothing, which
 * is how the first attempt at this run produced a false pass.
 */
export default defineConfig({
    testDir: './e2e',
    // Refuses to run against a dev server (F1's false pass).
    globalSetup: './e2e/prod-guard.setup.ts',
    timeout: 90_000,
    expect: { timeout: 15_000 },
    fullyParallel: false,
    workers: 1,
    reporter: 'line',
    use: {
        baseURL: 'http://localhost:3202',
        navigationTimeout: 60_000,
        actionTimeout: 20_000,
    },
    projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
