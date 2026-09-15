import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, minutesAgo, seedBatch, seedItem, seedRollup } from './seedBatch';

/**
 * P5/L1–L2 — the batches list: the section's front door, previously untested
 * and unreachable from the sidebar.
 *
 * Covers: OD4 (no `אצווה` anywhere), the mini honesty bar drawn from rollup,
 * one action line per row with correct precedence, rubric/class names finally
 * rendered (B4's server work was dead on this surface), the empty state, and
 * L2's nav entry staying lit across the section's descendants.
 */

const listItem = (over: Record<string, unknown> = {}) => ({
    id: 'b0000000-0000-0000-0000-00000000000a',
    name: 'מתכונת קיץ · יא׳3 · 18.8.2026',
    rubric_id: 'r1',
    class_id: 'c1',
    rubric_name: 'מתכונת 1 — שאלון 899371',
    class_name: 'יא׳3',
    status: 'in_progress',
    created_at: minutesAgo(90),
    rollup: seedRollup({ transcribed: 5, needs_eyes: 5, approved: 2, total: 7 }),
    ...over,
});

async function install(page: Page, batches: unknown[]) {
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/api/v0/classroom/students')) return fulfillJson(route, { students: [] });
        // The list endpoint is the BARE collection; a detail fetch has an id.
        if (/\/api\/v0\/batches(\?[^/]*)?$/.test(url)) return fulfillJson(route, batches);
        // L2 navigates one level deep — the dashboard needs a real payload or
        // it errors out before its shell (and its sidebar) ever render.
        if (/\/api\/v0\/batches\/[^/]+$/.test(url)) {
            return fulfillJson(route, seedBatch({
                id: url.split('/batches/')[1],
                items: [seedItem('t1')],
                rollup: { transcribed: 1, total: 1 },
            }));
        }
        return fulfillJson(route, {});
    });
}

test('list-populated (L1) — names, mini honesty bar, action line, zero אצווה', async ({ page }) => {
    await seedAuth(page);
    await install(page, [
        listItem(),
        listItem({
            id: 'b0000000-0000-0000-0000-00000000000b',
            name: null,                               // → BATCH_FALLBACK_NAME
            status: 'completed',
            rollup: seedRollup({ approved: 4, total: 4 }),
        }),
        listItem({
            id: 'b0000000-0000-0000-0000-00000000000c',
            name: 'עדיין בתמלול',
            rollup: seedRollup({ transcribing: 3, transcribed: 1, total: 4 }),
        }),
    ]);

    await page.goto('/batches');
    await expect(page.getByRole('heading', { name: 'המבחנים שלי' })).toBeVisible();
    await expect(page.getByTestId('batch-row')).toHaveCount(3);

    // OD4: the word אצווה must not appear anywhere on the page.
    expect(await page.locator('body').innerText()).not.toContain('אצווה');
    // [§2.3 / OD-1] `מקבץ` is the code word and never reaches a screen.
    expect(await page.locator('body').innerText()).not.toContain('מקבץ');

    // B4's names finally drawn (this surface dropped them for the whole project).
    await expect(page.getByText('מחוון: מתכונת 1 — שאלון 899371').first()).toBeVisible();
    await expect(page.getByText('יא׳3').first()).toBeVisible();

    // Fallback name for a null-named batch — C1's builder, not a local literal.
    await expect(page.getByText(/^מבחן b0000000$/)).toBeVisible();

    // The mini honesty bar renders per row (legend-less), replacing the old
    // single green approved/total fill.
    await expect(page.getByTestId('segment-bar')).toHaveCount(3);

    // Action lines, one per row, precedence respected.
    const actions = page.getByTestId('list-action-line');
    // Ruling 1: needs-eyes is the sharp signal, §3.2 verbatim.
    await expect(actions.nth(0)).toHaveText('5 דורשים מבט');
    await expect(actions.nth(1)).toHaveText('הכל אושר ✓');          // complete
    await expect(actions.nth(2)).toHaveText('3 בתמלול');            // still arriving

    // The row links into the batch.
    await page.getByTestId('batch-row').first().click();
    await expect(page).toHaveURL(/\/batches\/b0000000-0000-0000-0000-00000000000a$/);
});

test('list-empty (L1) — honest empty state with its CTA', async ({ page }) => {
    await seedAuth(page);
    await install(page, []);

    await page.goto('/batches');
    await expect(page.getByTestId('list-empty')).toBeVisible();
    await expect(page.getByText('אין מבחנים עדיין')).toBeVisible();
    await expect(page.getByRole('link', { name: 'העלי מבחן ראשון' })).toBeVisible();
    await expect(page.getByTestId('batch-row')).toHaveCount(0);
});

test('sidebar-entry (L2) — the section is reachable, and stays lit on its descendants', async ({ page }) => {
    await seedAuth(page);
    await install(page, [listItem()]);

    // The entry exists at all (before P5 the list was reachable only from a
    // batch you had already opened).
    await page.goto('/');
    const nav = page.getByRole('navigation');
    const entry = nav.getByRole('link', { name: 'המבחנים שלי' });
    await expect(entry).toBeVisible();
    await entry.click();
    await expect(page).toHaveURL(/\/batches$/);

    // Lit on the section root…
    await expect(nav.getByRole('link', { name: 'המבחנים שלי' })).toHaveClass(/bg-primary-100/);

    // …and STILL lit one level deep (strict equality would go dark here).
    // SCOPED TO THE NAV: since the §5.7 fold the batch page's breadcrumb
    // back-link carries the section name too, which is the point — they are
    // one section, and an unscoped role query now matches both.
    await page.goto('/batches/b0000000-0000-0000-0000-00000000000a');
    await expect(nav.getByRole('link', { name: 'המבחנים שלי' })).toHaveClass(/bg-primary-100/);
});

test('§5.7 fold — one section, two zoom levels, and no second sidebar entry', async ({ page }) => {
    await seedAuth(page);
    await install(page, [listItem()]);

    await page.goto('/batches');
    const nav = page.getByRole('navigation');
    // `מבחנים בדוקים` is no longer a sidebar entry — two entries for one
    // set of objects is how a teacher ends up asking which holds her work.
    await expect(nav.getByRole('link', { name: 'מבחנים בדוקים' })).toHaveCount(0);

    // It is a TAB inside the section, and the route it points at still works.
    const tabs = page.getByTestId('exams-tabs');
    await expect(tabs.getByRole('link', { name: 'לפי מבחן' })).toHaveAttribute('aria-current', 'page');
    // The graded-tests list is an ARRAY; the shared `install` answers `{}` for
    // everything it does not know, and `[].filter` on an object white-screens.
    await page.route('**/api/v0/grading/graded_tests*', (route) =>
        fulfillJson(route, []));
    await tabs.getByRole('link', { name: 'כל המבחנים הבדוקים' }).click();
    await expect(page).toHaveURL(/\/my-graded-tests$/);
    await expect(page.getByTestId('exams-tabs')
        .getByRole('link', { name: 'כל המבחנים הבדוקים' }))
        .toHaveAttribute('aria-current', 'page');
});
