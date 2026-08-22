/**
 * F1 (closeout) — PROVE which server the run actually hit.
 *
 * The first attempt at a production-build run passed 13 tests against the DEV
 * server: `PLAYWRIGHT_BASE_URL` is not read by the base config, which
 * hardcodes port 3100 AND starts its own `next dev`. A green suite that
 * silently tested the wrong binary is worse than a red one — so this runs
 * before the prod suite and fails loudly if the target is not a production
 * build.
 *
 * ⚠️ SUBSTRATE HAZARD, learned the hard way: `next dev` REBUILDS INTO THE
 * SAME `.next/` DIRECTORY that `next start` is serving. Running any dev-config
 * spec while a production server is up corrupts its artifacts — every chunk
 * and stylesheet then 500s and the app hangs on `טוען...`, a symptom that
 * points nowhere near the cause. If you see that: rebuild and restart on a
 * fresh port; do not debug the app.
 */
import { request } from '@playwright/test';

export default async function globalSetup() {
    const baseURL = process.env.PW_PROD_BASE_URL ?? 'http://localhost:3202';
    const ctx = await request.newContext();

    let html: string;
    try {
        const res = await ctx.get(baseURL, { timeout: 15_000 });
        if (!res.ok()) throw new Error(`${res.status()} from ${baseURL}`);
        html = await res.text();
    } catch (e) {
        throw new Error(
            `[prod-guard] No server answered at ${baseURL}. Start one with:\n`
            + `    npx next build && npx next start -p 3201\n`
            + `Original error: ${(e as Error).message}`,
        );
    } finally {
        await ctx.dispose();
    }

    // `next dev` ships the HMR client and unhashed chunk names; `next start`
    // ships content-hashed filenames and no HMR.
    const devMarkers = ['webpack-hmr', '/_next/static/chunks/webpack.js', '__nextjs_original-stack-frame'];
    const found = devMarkers.filter((m) => html.includes(m));
    if (found.length > 0) {
        throw new Error(
            `[prod-guard] ${baseURL} is a DEV server (markers: ${found.join(', ')}).\n`
            + 'This config exists to test the PRODUCTION build. Refusing to '
            + 'report a green run against the wrong binary.',
        );
    }

    console.log(`[prod-guard] target verified as a PRODUCTION build: ${baseURL}`);
}
