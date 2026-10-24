import { expect, test, type Page } from '@playwright/test';

import { USER } from './fixtures';
import { CLASS_ID, STUDENTS, installProfileMocks } from './studentProfileFixtures';

/**
 * The classes tab (classes-tab PR): the subject select offers HER subjects
 * (launch set when she has none), «add all» fills the class and members are
 * never suggested again, and a class card opens to its students, each a link
 * to the profile. Route mocks only — `installProfileMocks` carries the
 * roster; the overrides below are registered after it and so run first.
 */

test.use({ viewport: { width: 1440, height: 1000 } });

const SUBJECTS = [
    { id: 1, code: 'computer_science', name_he: 'מדעי המחשב', name_en: 'Computer Science' },
    { id: 2, code: 'english', name_he: 'אנגלית', name_en: 'English' },
    { id: 3, code: 'mathematics', name_he: 'מתמטיקה', name_en: 'Mathematics' },
    { id: 4, code: 'biology', name_he: 'ביולוגיה', name_en: 'Biology' },
    { id: 5, code: 'history', name_he: 'היסטוריה', name_en: 'History' },
];

async function installClassMocks(page: Page, mySubjects: typeof SUBJECTS = []) {
    await installProfileMocks(page);
    const members = new Set<string>([STUDENTS.profile.id, STUDENTS.zero.id]);
    const added: string[] = [];
    const json = (body: unknown, status = 200) => ({
        status, contentType: 'application/json', body: JSON.stringify(body),
    });
    await page.route('**/api/v0/**', async (route) => {
        const req = route.request();
        const path = new URL(req.url()).pathname;
        const method = req.method();
        if (path.endsWith('/auth/me')) return route.fulfill(json({ ...USER, subject_matters: mySubjects }));
        if (method === 'GET' && path.endsWith('/users/subject-matters')) return route.fulfill(json(SUBJECTS));
        if (method === 'POST' && path.endsWith(`/classroom/classes/${CLASS_ID}/students`)) {
            const { student_id } = req.postDataJSON() as { student_id: string };
            members.add(student_id);
            added.push(student_id);
            return route.fulfill({ status: 204, body: '' });
        }
        if (method === 'GET' && path.endsWith(`/classroom/classes/${CLASS_ID}`)) {
            const all = Object.values(STUDENTS);
            return route.fulfill(json({
                id: CLASS_ID, name: 'י"א 3', subject_matter_id: 5,
                subject_matter_name: 'היסטוריה', school_year: '2026',
                student_count: members.size, created_at: '2026-01-10T10:00:00Z',
                students: all.filter(s => members.has(s.id)).map(s => ({ id: s.id, full_name: s.full_name })),
            }));
        }
        return route.fallback();
    });
    return { added };
}

async function openClassesTab(page: Page) {
    await page.goto('/my-classroom');
    await page.getByRole('button', { name: 'כיתות' }).click();
    await page.locator('[data-class-card]').first().waitFor();
}

const optionLabels = (page: Page) =>
    page.getByRole('dialog').or(page.locator('.fixed.inset-0')).locator('select option').allTextContents();

test('subjects: only hers are offered', async ({ page }) => {
    await installClassMocks(page, [SUBJECTS[3], SUBJECTS[0]]);
    await openClassesTab(page);
    await page.getByRole('button', { name: 'כיתה חדשה' }).click();
    expect(await optionLabels(page)).toEqual(['ללא מקצוע', 'ביולוגיה', 'מדעי המחשב']);
});

test('subjects: with none on her profile, the launch three', async ({ page }) => {
    await installClassMocks(page, []);
    await openClassesTab(page);
    await page.getByRole('button', { name: 'כיתה חדשה' }).click();
    const labels = await optionLabels(page);
    expect([...labels].sort()).toEqual(['ללא מקצוע', 'אנגלית', 'מדעי המחשב', 'מתמטיקה'].sort());
});

test('subjects: editing keeps the class\'s stored subject offered', async ({ page }) => {
    await installClassMocks(page, [SUBJECTS[0]]);
    await page.route('**/api/v0/classroom/classes', (route) => route.request().method() === 'GET'
        ? route.fulfill({
            status: 200, contentType: 'application/json',
            body: JSON.stringify({ classes: [{
                id: CLASS_ID, name: 'י"א 3', subject_matter_id: 5, subject_matter_name: 'היסטוריה',
                school_year: '2026', student_count: 2, created_at: '2026-01-10T10:00:00Z',
            }] }),
        })
        : route.fallback());
    await openClassesTab(page);
    await page.getByTitle('עריכה').first().click();
    expect(await optionLabels(page)).toEqual(['ללא מקצוע', 'מדעי המחשב', 'היסטוריה']);
    await expect(page.locator('.fixed.inset-0 select')).toHaveValue('5');
});

test('manage: members are not suggested, and «add all» adds the rest', async ({ page }) => {
    const { added } = await installClassMocks(page);
    await openClassesTab(page);
    await page.getByTitle('ניהול תלמידים').first().click();

    const addAll = page.locator('[data-add-all-students]');
    await expect(addAll).toHaveText('הוספת כל התלמידים (3)');

    // The picker hides the two members.
    await page.getByPlaceholder('חפש או צור תלמיד...').click();
    const suggestions = page.locator('.absolute.top-full button');
    await expect(suggestions.filter({ hasText: STUDENTS.two.full_name })).toHaveCount(1);
    await expect(suggestions.filter({ hasText: STUDENTS.profile.full_name })).toHaveCount(0);
    await expect(suggestions.filter({ hasText: STUDENTS.zero.full_name })).toHaveCount(0);

    // Picking one removes it from the suggestions too.
    await suggestions.filter({ hasText: STUDENTS.two.full_name }).click();
    await expect(addAll).toHaveText('הוספת כל התלמידים (2)');
    await page.getByPlaceholder('חפש או צור תלמיד...').click();
    await expect(suggestions.filter({ hasText: STUDENTS.two.full_name })).toHaveCount(0);
    await page.keyboard.press('Escape');

    await addAll.click();
    await expect(addAll).toHaveText('הוספת כל התלמידים (0)');
    await expect(addAll).toBeDisabled();
    expect(new Set(added)).toEqual(new Set([STUDENTS.two.id, STUDENTS.one.id, STUDENTS.three.id]));
    await expect(page.locator('[data-class-student-link]')).toHaveCount(5);
});

test('class card: a click opens its students, each a link to the profile', async ({ page }) => {
    await installClassMocks(page);
    await openClassesTab(page);

    const card = page.locator(`[data-class-card="${CLASS_ID}"]`);
    await expect(card.locator('[data-class-students]')).toHaveCount(0);
    // A click on empty row space toggles (the stretched button).
    const box = (await card.boundingBox())!;
    await page.mouse.click(box.x + box.width * 0.5, box.y + 30);
    await expect(card.locator('[data-class-toggle]')).toHaveAttribute('aria-expanded', 'true');

    const links = card.locator('[data-class-member-link]');
    await expect(links).toHaveCount(2);
    await expect(links).toHaveText([STUDENTS.zero.full_name, STUDENTS.profile.full_name]);
    const moran = links.filter({ hasText: STUDENTS.profile.full_name });
    await expect(moran).toHaveAttribute('href', `/my-classroom/students/${STUDENTS.profile.id}`);
    await moran.click();
    await expect(page).toHaveURL(new RegExp(`/my-classroom/students/${STUDENTS.profile.id}`));
});

test('class card: the action buttons do not toggle it', async ({ page }) => {
    await installClassMocks(page);
    await openClassesTab(page);
    const card = page.locator(`[data-class-card="${CLASS_ID}"]`);
    await card.getByTitle('ניהול תלמידים').click();
    await expect(card.locator('[data-class-toggle]')).toHaveAttribute('aria-expanded', 'false');
});
