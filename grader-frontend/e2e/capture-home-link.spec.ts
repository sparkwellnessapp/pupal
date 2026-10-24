import { expect, test, type Route } from '@playwright/test';
import { seedAuth } from './fixtures';
import { AUTH_ME, fulfillJson, seedBatch } from './seedBatch';

/**
 * [036] The home page's «יצירת לינק לתלמידים» card: card → rubric → the batch
 * is created at once (named like the upload step names it, B5) → the batch
 * page opens on its student-link form, which is in view and focused.
 *
 * NEXT_PUBLIC_CAPTURE_ENABLED is inlined at BUILD time and the shared harness
 * server is built without it (it would put the capture section on every batch
 * page the other specs drive). Run against a server started with the flag:
 *   NEXT_PUBLIC_CAPTURE_ENABLED=true NEXT_DIST_DIR=.next-e2e npm run dev -- --port 3100
 *   E2E_CAPTURE=1 npx playwright test e2e/capture-home-link.spec.ts
 */
test.skip(process.env.E2E_CAPTURE !== '1', 'needs a server built with NEXT_PUBLIC_CAPTURE_ENABLED=true');

const BATCH_ID = 'b0000000-0000-0000-0000-00000000c036';
const RUBRIC = {
    id: 'r1', name: 'מחוון בדיקה', total_points: 100, total_questions: 2,
    is_compiled: true, needs_recompilation: false,
    created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
    stats: null, draft: null,
};

test('the home card goes straight from a rubric to the student-link form', async ({ page }) => {
    await seedAuth(page);
    const created: Array<Record<string, unknown>> = [];
    await page.route('**/api/v0/**', async (route: Route) => {
        const url = route.request().url().split('?')[0];
        const method = route.request().method();
        if (url.endsWith('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.endsWith('/api/v0/rubrics') && method === 'GET') return fulfillJson(route, { rubrics: [RUBRIC] });
        if (url.endsWith('/api/v0/batches') && method === 'POST') {
            created.push(route.request().postDataJSON() as Record<string, unknown>);
            return fulfillJson(route, { batch_id: BATCH_ID, test_count: 0, expected_test_count: null });
        }
        if (url.endsWith(`/batches/${BATCH_ID}/capture-link`)) return fulfillJson(route, { detail: 'Not Found' }, 404);
        if (url.endsWith(`/batches/${BATCH_ID}/capture-submissions`)) {
            return fulfillJson(route, { rows: [], counter: { submitted_students: 0, roster_size: null } });
        }
        if (url.includes('/api/v0/classroom/classes')) return fulfillJson(route, { classes: [{ id: 'c1', name: 'יא׳3' }] });
        if (url.endsWith(`/api/v0/batches/${BATCH_ID}`)) {
            return fulfillJson(route, seedBatch({ id: BATCH_ID, items: [], rollup: { total: 0 } }));
        }
        return fulfillJson(route, {});
    });

    await page.goto('/');
    const card = page.getByTestId('home-student-link');
    await expect(card).toContainText('יצירת לינק לתלמידים');
    await expect(card).toContainText('כאן תלמידים יוכלו לצלם את התשובות שלהם ולעלות לVivi בעת הגשת המבחן');
    await card.click();

    await expect(page.getByText('בחרי את המחוון של המבחן שהתלמידים יצלמו')).toBeVisible();
    await page.getByText('מחוון בדיקה').first().click();

    // Straight to the batch — no upload step — and the URL is clean after it.
    await expect(page).toHaveURL(new RegExp(`/batches/${BATCH_ID}$`));
    const form = page.getByTestId('capture-link-form');
    await expect(form).toBeVisible();
    await expect(form).toBeInViewport();
    // A new batch has no class: her first step is choosing one (the create
    // button is disabled until then), so that is where the focus lands.
    await expect(form.getByRole('combobox')).toBeFocused();
    await form.getByRole('combobox').selectOption('c1');
    await expect(form.getByRole('button', { name: 'יצירת קישור' })).toBeEnabled();

    expect(created).toHaveLength(1);
    expect(created[0].rubric_id).toBe('r1');
    expect(created[0].expected_test_count ?? null).toBeNull();      // nothing will be uploaded
    expect(String(created[0].name)).toMatch(/^בדיקה · \d{1,2}\.\d{1,2}\.\d{4}$/);
});
