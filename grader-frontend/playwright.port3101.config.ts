// An alternate-port e2e harness. The base config hardcodes port 3100 with
// `reuseExistingServer`, so ANY other Next app already on 3100 silently becomes the
// system under test — that happened during the multi-subject beta (2026-09-08): the
// owner's ViviWebsite dev server held the port and the whole suite reported 168
// failures against the wrong application. A wall of failures with that signature is
// INFRASTRUCTURE, as playwright.config.ts itself warns; check `curl localhost:3100`
// before believing any of them, then run this config instead:
//
//     npx playwright test -c playwright.port3101.config.ts
//
// Same settings, own port, own dist dir, and `reuseExistingServer: false` so it always
// drives a server it started itself.
import { defineConfig } from '@playwright/test';
import base from './playwright.config';

export default defineConfig({
    ...base,
    use: { ...base.use, baseURL: 'http://localhost:3101' },
    webServer: {
        env: { NEXT_DIST_DIR: '.next-e2e-3101', NEXT_PUBLIC_GOOGLE_CLIENT_ID: 'e2e-stub.apps.googleusercontent.com' },
        command: 'npm run dev -- --port 3101',
        url: 'http://localhost:3101',
        reuseExistingServer: false,
        timeout: 180_000,
    },
});
