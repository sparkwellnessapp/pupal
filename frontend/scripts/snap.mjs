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
// 'cards-open' (PR-6b) composes each fixture's OWN GT pedagogical canon into
// finding cards — hobby shows the steps-wire root proposal + explained_by shadows.
const STATES = ['at-rest', 'findings', 'solutions-expanded', 'cards-open'];
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
        // ── Round 2: the INTERACTIVE + composed states (closes audit F4). Driven
        // by clicking, then capturing the VIEWPORT (an open editor in a full-page
        // shot of an 8000px document is unreadable). bagrut is the driver: depth-2,
        // marker-bearing prose, selection, and a long body for the rail landing.
        const drive = async (name, fn, { element = null } = {}) => {
            await page.goto(`${BASE}/design-lab?fixture=bagrut_899371&state=at-rest`, { waitUntil: 'networkidle' });
            await page.waitForTimeout(450);
            await fn();
            const file = path.join(OUT, `bagrut_899371_${name}_${vp.w}.png`);
            if (element) await page.locator(element).first().screenshot({ path: file });
            else await page.screenshot({ path: file, fullPage: false });
            console.log('  shot', file);
            n++;
        };

        // D3 — the header band, as its own named shot.
        await drive('header', async () => {}, { element: 'header' });

        // D5 — editing a PARENT's points (the unlanded Sprint-2 item).
        await drive('editing-point', async () => {
            const chip = page.getByRole('button', { name: /^ניקוד סעיף/ }).first();
            await chip.scrollIntoViewIfNeeded();
            await chip.click();
            await page.waitForTimeout(200);
        });

        // D8 — editing PROSE: rich at rest, RAW in the box (markers visible).
        await drive('editing-prose', async () => {
            const prose = page.getByRole('button', { name: /^טקסט שאלה/ }).first();
            await prose.scrollIntoViewIfNeeded();
            await prose.click();
            await page.waitForTimeout(250);
        });

        // D9 — where a rail click actually LANDS (the title, below the header offset).
        await drive('rail-landing', async () => {
            // ^-anchored: PR-6's collapse toggles are named «הרחיבי/כווצי שאלה 4»
            // and collide with an unanchored regex (strict-mode double match).
            await page.getByRole('navigation', { name: 'מפת המחוון' })
                .getByRole('button', { name: /^שאלה 4/ }).click();
            await page.waitForTimeout(1200);
        });

        // ── PR-6b: the finding LIFECYCLE on hobby (the fixture whose GT carries the
        // steps-wire root fix + explained_by shadows). cards-open is covered by the
        // STATES matrix; these two capture what one click / one dismissal leaves.
        for (const st of ['cards-resolved', 'cards-dismissed']) {
            await page.goto(`${BASE}/design-lab?fixture=hobby_tvshow&state=${st}`, { waitUntil: 'networkidle' });
            await page.waitForTimeout(450);
            const file = path.join(OUT, `hobby_tvshow_${st}_${vp.w}.png`);
            await page.screenshot({ path: file, fullPage: true });
            console.log('  shot', file);
            n++;
        }

        await ctx.close();
    }
} finally {
    await browser.close();
}
console.log(`\n${n} shots -> ${OUT}`);
