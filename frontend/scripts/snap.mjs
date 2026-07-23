import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';
import path from 'node:path';

/**
 * DESIGN RECOVERY SUITE — Phase 0 "npm run snap".
 *
 * Captures deterministic full-page PNGs of every /design-lab state × fixture at
 * two viewports into design/shots/iter-<N>/. Naming is fixed
 * (bagrut_899371_at-rest_1440.png) so audits can cite by filename and diffs are
 * stable. Requires the dev server up on SNAP_BASE_URL (default :3100).
 *
 *   node scripts/snap.mjs <iter>      e.g.  node scripts/snap.mjs 0
 */

const ITER = process.argv[2] ?? '0';
const BASE = process.env.SNAP_BASE_URL ?? 'http://localhost:3100';
const OUT = path.join('design', 'shots', `iter-${ITER}`);
mkdirSync(OUT, { recursive: true });

const FIXTURES = ['markers_demo', 'bagrut_899371', 'csharp_plane_combine', 'employee_course_select1', 'foundations_cs', 'hobby_tvshow'];
const STATES = ['at-rest', 'findings', 'solutions-expanded'];
const VIEWPORTS = [{ w: 1440, h: 900 }, { w: 1280, h: 800 }];

async function waitForServer(page) {
    for (let i = 0; i < 90; i++) {
        try {
            const r = await page.goto(`${BASE}/design-lab?fixture=bagrut_899371&state=at-rest`, { waitUntil: 'domcontentloaded', timeout: 4000 });
            if (r && r.ok()) return;
        } catch { /* not up yet */ }
        await page.waitForTimeout(1000);
    }
    throw new Error(`dev server never came up at ${BASE} — start it with: npm run dev -- --port 3100`);
}

const browser = await chromium.launch();
let n = 0;
try {
    const warm = await browser.newPage();
    await waitForServer(warm);
    await warm.close();

    for (const vp of VIEWPORTS) {
        const ctx = await browser.newContext({ viewport: { width: vp.w, height: vp.h }, deviceScaleFactor: 1 });
        const page = await ctx.newPage();
        for (const fx of FIXTURES) {
            for (const st of STATES) {
                await page.goto(`${BASE}/design-lab?fixture=${fx}&state=${st}`, { waitUntil: 'networkidle' });
                await page.waitForTimeout(450); // rail measurement + solutions-expand effect settle
                const file = path.join(OUT, `${fx}_${st}_${vp.w}.png`);
                await page.screenshot({ path: file, fullPage: true });
                console.log('  shot', file);
                n++;
            }
        }
        await ctx.close();
    }
} finally {
    await browser.close();
}
console.log(`\n${n} shots -> ${OUT}`);
