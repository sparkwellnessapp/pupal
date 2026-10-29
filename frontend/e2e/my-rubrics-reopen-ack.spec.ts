import { test, expect, type Route } from '@playwright/test';
import { seedAuth, USER } from './fixtures';

/**
 * A FIXED mismatch must not come back on the next edit (prod incident 2026-10-29).
 *
 * The extraction annotated q3 «Σ criteria = 30, declared 40» (a WARNING). She fixed
 * the points in the upload flow and saved; the annotation stays in `draft_json`
 * BY DESIGN (findings survive reopen). Two days later she edited the rubric from
 * «המחוונים שלי» and the save popped the warnings modal with the same — long fixed —
 * mismatch: that page composed the findings (q3 → resolved) but sent the compile
 * an EMPTY acknowledgment, and the compiler acks every stored WARNING by id.
 *
 * The mocked PUT enforces that same gate, so this fails exactly the way prod did.
 */

const RUBRIC_ID = 'r-reopen';
const STALE = {
    id: 'rubric_mismatch:q3',
    annotation_type: 'rubric_mismatch',
    severity: 'warning',
    target_id: 'q3',
    message: 'אזהרה: סכום הנקודות בQ3 הוא 30 נקודות, אך כותרת השאלה מצהירה על 40 נקודות.',
    message_he: null, invariant: null, expected: null, actual: null,
};

// q3 as she left it: declared 40, criteria now summing to 40.
const DRAFT = {
    schema_version: '1.0',
    rubric_id: RUBRIC_ID,
    rubric_name: 'מחוון בדיקה',
    subject: 'computer_science',
    total_points: '40',
    questions: [{
        question_id: 'q3', question_type: 'coding_task', question_text: 'שאלה 3',
        total_points: '40', sub_questions: [], example_solution: null,
        criteria: [
            { criterion_id: 'q3.c0', index: 0, description: 'רכיב א', points: '18', sub_criteria: null },
            { criterion_id: 'q3.c1', index: 1, description: 'רכיב ב', points: '22', sub_criteria: null },
        ],
    }],
    selection_groups: [],
    annotations: [STALE],
    pedagogical_mistakes: [{
        mistake_id: 'pts:q3', kind: 'point_sum_mismatch', target_id: 'q3', severity: 'warning',
        confidence: 1.0, explanation: 'רכיבי המחוון מסתכמים ב־30 נקודות, בעוד שבכותרת מצוינות 40.',
        evidence: { children_sum: '30.0', declared_total: '40.0' }, dismissed: null,
    }],
};

test('re-editing a rubric whose extraction mismatch she already fixed saves without the warnings modal', async ({ page }) => {
    await seedAuth(page);
    const puts: { acknowledged_warning_ids?: string[] }[] = [];

    await page.route('**/api/v0/**', async (route: Route) => {
        const req = route.request();
        const url = req.url();
        const json = (body: unknown) => route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) });

        if (url.includes('/api/v0/auth/me')) return json(USER);
        if (req.method() === 'GET' && /\/api\/v0\/rubrics\/?(\?|$)/.test(url)) {
            return json([{ id: RUBRIC_ID, name: 'מחוון בדיקה', created_at: '2026-10-27T20:11:55Z', format: 'ontology', is_compiled: true, total_points: 40, total_questions: 1 }]);
        }
        if (req.method() === 'GET' && url.includes(`/rubrics/${RUBRIC_ID}?include_draft=true`)) {
            return json({ id: RUBRIC_ID, name: 'מחוון בדיקה', created_at: '2026-10-27T20:11:55Z', format: 'ontology', is_compiled: true, total_points: 40, total_questions: 1, draft_json: DRAFT });
        }
        if (req.method() === 'PUT' && url.includes(`/rubrics/${RUBRIC_ID}/draft`)) {
            const body = req.postDataJSON();
            puts.push(body);
            // The compiler's Step-5 gate: every stored WARNING must be acked by id.
            const acked = new Set<string>(body.acknowledged_warning_ids ?? []);
            const unacked = (body.draft.annotations ?? []).filter((a: { severity: string; id: string }) => a.severity === 'warning' && !acked.has(a.id));
            if (unacked.length) {
                return json({ status: 'warnings_require_acknowledgment', message_he: 'יש אזהרות שדורשות אישור', warnings: unacked });
            }
            return json({ rubric_id: RUBRIC_ID, updated_at: '2026-10-29T13:11:23Z', needs_recompilation: false, previous_contract_version: null, has_existing_grades: false, stats: { total_points: 40, total_questions: 1, total_criteria: 2, total_rules: 0 } });
        }
        return json({});
    });

    await page.goto('/my-rubrics');
    const card = page.getByText('מחוון בדיקה').first();
    await card.hover();
    await page.locator('button:has(svg[class*="vertical"])').first().click({ force: true });
    await page.getByRole('button', { name: 'עריכה' }).click();
    await expect(page.getByRole('heading', { name: 'עריכת מחוון' })).toBeVisible();

    await page.getByRole('button', { name: 'שמור שינויים' }).click();

    await expect.poll(() => puts.length).toBe(1);
    expect(puts[0].acknowledged_warning_ids).toContain('rubric_mismatch:q3');
    await expect(page.getByText('יש אזהרות שדורשות אישור')).toHaveCount(0);
});
