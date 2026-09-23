import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';

import { expect, test } from '@playwright/test';

import {
    BATCH_ARRAYS, BATCH_HOBBY, MISSING_STUDENT, PROFILE_SIGNED_TESTS, STUDENTS,
    TEST_HOBBY, TEST_NO_PAGES, TEST_RECURSION, installProfileMocks,
} from './studentProfileFixtures';

/**
 * The student profile and the roster — PR_student_profile.md §8.3, in a real
 * browser against route mocks. The pure half (§8.2) lives in
 * `utils/student-profile.test.ts`; the backend's (§8.1) in
 * `tests/api/test_student_profile.py`.
 *
 * Local time is PINNED to Asia/Jerusalem so «בדיקה אושרה ב19.9.2026, 16:58»
 * is the same sentence on every machine (FA-11: the formatter is local time).
 */

const ART = 'e2e/review-artifacts/student-profile';
const PROFILE = (id: string) => `/my-classroom/students/${id}`;

test.use({ viewport: { width: 1440, height: 1000 }, timezoneId: 'Asia/Jerusalem' });

// ── the roster (§6.1) ──────────────────────────────────────────────────────

test('roster: every card is a link, the badge counts, 0 is hidden, 1 is singular', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto('/my-classroom');
    await page.locator('[data-student-card]').first().waitFor();

    const card = (id: string) => page.locator(`[data-student-card="${id}"]`);
    await expect(card(STUDENTS.zero.id).locator('[data-signed-badge]')).toHaveCount(0);
    await expect(card(STUDENTS.one.id).locator('[data-signed-badge]')).toHaveText('מבחן בדוק אחד');
    await expect(card(STUDENTS.two.id).locator('[data-signed-badge]')).toHaveText('2 מבחנים בדוקים');
    await expect(card(STUDENTS.profile.id).locator('[data-signed-badge]')).toHaveText('3 מבחנים בדוקים');

    // OD-1 / UI-5: the name is the link; no button sits inside it.
    const link = card(STUDENTS.profile.id).locator('[data-student-link]');
    await expect(link).toHaveAttribute('href', PROFILE(STUDENTS.profile.id));
    await expect(link.locator('button')).toHaveCount(0);

    await page.screenshot({ path: `${ART}/roster-1440.png` });

    // The stretched link covers the card: a click on empty card space opens
    // the profile; the pencil above the layer opens the dialog and stays put.
    await card(STUDENTS.profile.id).getByLabel('עריכת שם').click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page).toHaveURL(/\/my-classroom$/);
    await page.getByRole('dialog').getByRole('button', { name: 'ביטול' }).click();
    // No «הערות» anywhere (UI-4).
    await page.getByRole('button', { name: 'תלמיד חדש' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('dialog').getByText('הערות')).toHaveCount(0);
    await page.getByRole('dialog').getByRole('button', { name: 'ביטול' }).click();

    const box = (await card(STUDENTS.three.id).boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.5, box.y + box.height * 0.5);
    await expect(page).toHaveURL(new RegExp(PROFILE(STUDENTS.three.id)));
});

test('roster: Tab reaches the name link and Enter opens the profile', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto('/my-classroom');
    await page.locator('[data-student-card]').first().waitFor();

    let reached = false;
    for (let i = 0; i < 60 && !reached; i += 1) {
        await page.keyboard.press('Tab');
        reached = await page.evaluate(() => document.activeElement?.hasAttribute('data-student-link') ?? false);
    }
    expect(reached).toBe(true);
    const href = await page.evaluate(() => (document.activeElement as HTMLAnchorElement).getAttribute('href'));
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(new RegExp(href!));
});

test('roster: the interim delete refuses in her words, not the server\'s code', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto('/my-classroom');
    await page.locator(`[data-student-card="${STUDENTS.profile.id}"]`).getByLabel('מחיקת תלמיד/ה').click();
    await page.getByRole('dialog').getByRole('button', { name: 'מחיקה' }).click();
    await expect(page.getByRole('dialog')).toContainText('אי אפשר עדיין למחוק תלמיד/ה עם מבחנים משויכים.');
    await expect(page.getByRole('dialog')).not.toContainText('student_has_data');
});

// ── the profile (§6.2) ─────────────────────────────────────────────────────

test('profile: header, rows in upload order, the row facts, the thumbnails, the links', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto(PROFILE(STUDENTS.profile.id));
    await page.locator('[data-signed-test]').first().waitFor();

    // Header: breadcrumb → name → class chip → count.
    await expect(page.getByRole('navigation', { name: 'ניווט' })).toContainText('הכיתות שלי');
    await expect(page.getByRole('heading', { level: 1 })).toHaveText('מאיה דוגמה');
    await expect(page.locator('[data-class-chip]')).toHaveText(['י"א 3']);
    await expect(page.locator('[data-signed-count]')).toHaveText('3 מבחנים בדוקים');

    // Rows: newest upload first (OD-6 / M-A3), spelled as המבחנים שלי spells them.
    const rows = page.locator('[data-signed-test]');
    await expect(rows).toHaveCount(3);
    await expect(rows.locator('[data-exam-title]')).toHaveText([
        'Hobby & TvShow',      // the stored batch name
        'מבחן bbbbbbbb',       // no stored name → the list's own fallback
        'בוחן רקורסיה',        // single-flow → the rubric
    ]);
    await expect(rows.nth(0).locator('[data-approved-at]')).toHaveText('בדיקה אושרה ב19.9.2026, 16:58');
    await expect(rows.nth(2).locator('[data-approved-at]')).toHaveText('בדיקה אושרה ב5.3.2026, 19:40');

    // OD-7: the grade is the row's own two numbers — and it equals the stamp's.
    await expect(rows.nth(0).locator('[data-signed-grade]')).toHaveText(/85\.5\s*מתוך 100/);
    await expect(rows.nth(2).locator('[data-signed-grade]')).toHaveText(/64\s*מתוך 80/);
    for (const [i, expected] of [[0, '85.5'], [1, '92'], [2, '64']] as const) {
        const stamp = rows.nth(i).locator('[data-stamp-drag][data-measured="true"]');
        await expect(stamp).toBeVisible();
        await expect(stamp.locator('svg text')).toHaveText(expected);
        // Read-only (UI-2): the same renderer, none of the drag affordance.
        await expect(stamp).toHaveAttribute('data-readonly', 'true');
        await expect(stamp).not.toHaveAttribute('role', 'button');
    }
    // The page images arrive through the seam (FA-4) — as object URLs, lazily.
    await expect(rows.nth(0).locator('[data-thumb] img')).toHaveAttribute('src', /^blob:/);
    await expect(rows.nth(0).locator('[data-thumb] img')).toBeVisible();

    // FA-3: the stamp sits where the returned page puts it — a normalized
    // (x=0.2, y=0.15) centre on a 96px-wide, 1:1.41 box, at 16% width.
    const thumbBox = (await rows.nth(0).locator('[data-thumb] [data-page-view], [data-thumb] > div').first().boundingBox())!;
    const stampBox = (await rows.nth(0).locator('[data-stamp-drag]').boundingBox())!;
    const cx = (stampBox.x + stampBox.width / 2 - thumbBox.x) / thumbBox.width;
    const cy = (stampBox.y + stampBox.height / 2 - thumbBox.y) / thumbBox.height;
    expect(Math.abs(cx - 0.2)).toBeLessThan(0.02);
    expect(Math.abs(cy - 0.15)).toBeLessThan(0.02);
    expect(Math.abs(stampBox.width / thumbBox.width - 0.16)).toBeLessThan(0.01);

    // §6.2 / FA-9: the returned page with the student context, + batch iff any.
    await expect(rows.nth(0)).toHaveAttribute(
        'href', `/graded-tests/${TEST_HOBBY}/returned?student=${STUDENTS.profile.id}&batch=${BATCH_HOBBY}`);
    await expect(rows.nth(2)).toHaveAttribute(
        'href', `/graded-tests/${TEST_RECURSION}/returned?student=${STUDENTS.profile.id}`);
    expect(PROFILE_SIGNED_TESTS[1].exam.batch_id).toBe(BATCH_ARRAYS);

    await page.screenshot({ path: `${ART}/profile-1440.png` });
    await page.setViewportSize({ width: 1180, height: 900 });
    await page.waitForTimeout(150);
    await page.screenshot({ path: `${ART}/profile-1180.png` });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(150);
    await page.screenshot({ path: `${ART}/profile-390.png`, fullPage: true });
    // Below ~640 px the grade wraps under the text and never floats to the far edge.
    const grade = (await rows.nth(0).locator('[data-signed-grade]').boundingBox())!;
    const title = (await rows.nth(0).locator('[data-exam-title]').boundingBox())!;
    expect(grade.y).toBeGreaterThan(title.y + title.height - 1);
});

test('profile: a scan with no rendered page draws the placeholder and still links (M-A8)', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto(PROFILE(STUDENTS.one.id));
    const row = page.locator('[data-signed-test]');
    await row.first().waitFor();

    // No image — and NOT a broken-image glyph: the empty paper box, with the
    // stamp still on it, because the grade is a fact we do have.
    await expect(row.locator('[data-thumb] img')).toHaveCount(0);
    await expect(row.locator('[data-thumb] [data-stamp-drag][data-measured="true"]')).toBeVisible();
    await expect(row.locator('[data-signed-grade]')).toHaveText(/48\s*מתוך 50/);

    // Still a link, and batch-less, so it carries the student and nothing else.
    await expect(row).toHaveAttribute(
        'href', `/graded-tests/${TEST_NO_PAGES}/returned?student=${STUDENTS.one.id}`);
    await page.screenshot({ path: `${ART}/profile-placeholder-1440.png` });
    await row.click();
    await expect(page).toHaveURL(new RegExp(`/graded-tests/${TEST_NO_PAGES}/returned`));
});

test('roster: the class\'s student list links to the profile too (FA-1 / OD-2)', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto('/my-classroom');
    await page.getByRole('button', { name: 'כיתות' }).click();
    await page.getByTitle('ניהול תלמידים').first().click();

    const link = page.locator('[data-class-student-link]').first();
    await expect(link).toBeVisible();
    await expect(link).toHaveAttribute('href', PROFILE(STUDENTS.profile.id));
    await link.click();
    await expect(page).toHaveURL(new RegExp(PROFILE(STUDENTS.profile.id)));
});

test('profile: the empty state, in the name of the student', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto(PROFILE(STUDENTS.zero.id));
    await page.locator('[data-profile-empty]').waitFor();
    await expect(page.locator('[data-profile-empty]')).toContainText('עדיין אין מבחנים בדוקים לנועה דוגמה');
    await expect(page.locator('[data-profile-empty]')).toContainText('מבחנים שתאשרי יופיעו כאן.');
    await expect(page.locator('[data-signed-count]')).toHaveCount(0);
    await page.screenshot({ path: `${ART}/profile-empty-1440.png` });
});

test('profile: a missing or foreign student goes back to the roster with a word', async ({ page }) => {
    await installProfileMocks(page);
    await page.goto(PROFILE(MISSING_STUDENT));
    await expect(page).toHaveURL(/\/my-classroom$/);
    await expect(page.getByText('התלמיד/ה לא נמצא/ה')).toBeVisible();
});

test('profile: the interim delete — refused in place with signed tests, refused by the server without', async ({ page }) => {
    // Moran has signed tests: the trash says so in place, no dialog.
    await installProfileMocks(page, { deleteRefused: [STUDENTS.profile.id, STUDENTS.zero.id] });
    await page.goto(PROFILE(STUDENTS.profile.id));
    await page.locator('[data-signed-test]').first().waitFor();
    await page.locator('[data-delete-student]').click();
    await expect(page.locator('[data-delete-blocked]')).toHaveText('אי אפשר עדיין למחוק תלמיד/ה עם מבחנים משויכים.');
    await expect(page.getByRole('dialog')).toHaveCount(0);

    // Itay K. has none signed — but a draft (the server knows): dialog → 409 → the same sentence.
    await page.goto(PROFILE(STUDENTS.zero.id));
    await page.locator('[data-profile-empty]').waitFor();
    await page.locator('[data-delete-student]').click();
    await page.getByRole('dialog').getByRole('button', { name: 'מחיקה' }).click();
    await expect(page.locator('[data-delete-blocked]')).toBeVisible();
    await expect(page).toHaveURL(new RegExp(PROFILE(STUDENTS.zero.id)));
});

test('profile: a student with nothing attributable deletes and lands on the roster', async ({ page }) => {
    const { deleted } = await installProfileMocks(page, { deleteRefused: [] });
    await page.goto(PROFILE(STUDENTS.zero.id));
    await page.locator('[data-profile-empty]').waitFor();
    await page.locator('[data-delete-student]').click();
    await page.getByRole('dialog').getByRole('button', { name: 'מחיקה' }).click();
    await expect(page).toHaveURL(/\/my-classroom$/);
    expect(deleted).toEqual([STUDENTS.zero.id]);
});

// ── mockup parity captures (§6.0, UI-6) ────────────────────────────────────

const MOCKUP_DIR = path.resolve(__dirname, '../../vivi-student-profile-mockup');
/** The artboards are Noam's design export at the repo root — NOT a tracked
 *  file, so a fresh clone (and CI) does not have them. The captures are
 *  evidence for a human comparison, not a regression gate: absent, they skip
 *  and say why, rather than failing a checkout that is otherwise green. */
const MOCKUP_PRESENT = existsSync(MOCKUP_DIR);

function mockupHtml(name: string): string {
    // The artboards are design-canvas exports with `{{accent}}`/`{{stamp}}`
    // placeholders resolved by a support script we do not ship; substitute the
    // defaults the canvas would.
    return readFileSync(path.join(MOCKUP_DIR, `${name}.dc.html`), 'utf-8')
        .replace(/\{\{accent\}\}/g, '#2AB3A2')
        .replace(/\{\{stamp\}\}/g, '#B5121B')
        .replace(/<script src="\.\/support\.js"><\/script>/, '');
}

for (const [name, width, height] of [['Main', 1440, 1000], ['Roster', 1440, 900], ['Empty', 1000, 560]] as const) {
    test(`the ${name} artboard, for side-by-side comparison`, async ({ page }) => {
        test.skip(!MOCKUP_PRESENT, `no mockup export at ${MOCKUP_DIR}`);
        await page.setViewportSize({ width, height });
        await page.setContent(mockupHtml(name));
        await page.waitForTimeout(300);
        // Written OUTSIDE the tracked artifacts: the artboards show the mockup's
        // cast, who are real students, and this repository is public.
        await page.screenshot({ path: `test-results/mockup-${name.toLowerCase()}.png` });
    });
}
