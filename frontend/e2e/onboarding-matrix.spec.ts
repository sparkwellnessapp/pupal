import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * The ONBOARDING screenshot matrix — six steps × two viewports, one PNG per
 * cell under e2e/review-artifacts/ONB/. Same protocol as the P4/P5 matrices:
 * this file produces the artifacts; a human opens them and writes the note.
 *
 * It asserts only enough to prove the freeze-frame is the step it claims to be —
 * the behavioural guarantees live in onboarding.spec.ts.
 */

const SUBJECTS = [
    { id: 5, code: 'biology', name_he: 'ביולוגיה', name_en: 'Biology' },
    { id: 7, code: 'computer_science', name_he: 'מדעי המחשב', name_en: 'Computer Science' },
    { id: 8, code: 'english', name_he: 'אנגלית', name_en: 'English' },
    { id: 9, code: 'mathematics', name_he: 'מתמטיקה', name_en: 'Mathematics' },
];

const USER = {
    id: 'u1',
    email: 'teacher@example.com',
    full_name: 'מיכל כהן',
    subscription_status: 'active',
    is_subscription_active: true,
    subject_matters: [],
    created_at: '2026-01-01T00:00:00Z',
    onboarding_completed_at: null,
    gender: null,
    schools: [],
    primary_school_id: null,
};

function futureJwt(): string {
    const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64url');
    return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: 'u1', exp: 4102444800 })}.sig`;
}

async function install(page: Page) {
    await page.addInitScript(
        ([token, user]) => {
            localStorage.setItem('pupal_auth_token', token as string);
            localStorage.setItem('pupal_user', user as string);
        },
        [futureJwt(), JSON.stringify(USER)],
    );

    await page.route('**/api/v0/**', (route: Route) => {
        const url = route.request().url();
        const body = url.includes('/users/subject-matters')
            ? SUBJECTS
            : url.includes('/auth/me')
              ? USER
              : url.includes('/users/me/schools')
                ? []
                : {};
        return route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify(body),
        });
    });
}

const next = (page: Page) => page.getByTestId('onboarding-next');

/** Relative to the RUN: the booking window is computed against the real clock,
 *  so a pinned date would drift out of it and quietly stop exercising this. */
const nearISO = () => {
    const d = new Date();
    d.setDate(d.getDate() + 5);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
/**
 * `animations: 'disabled'` is load-bearing, not tidiness: every chip carries
 * `transition-colors`, so a screenshot taken right after a click freezes the
 * 150ms transition HALFWAY and the selected chip renders a washed-out
 * in-between colour. Measured 2026-09-01 — a settled selected chip is
 * rgb(20,184,166), but the artifact showed rgb(125,199,189) and, earlier still,
 * the unselected grey. An artifact whose whole job is to be LOOKED AT must not
 * lie about the state it claims to show.
 */
const shot = (page: Page, name: string, vp: { w: number; h: number }) =>
    page.screenshot({
        path: `e2e/review-artifacts/ONB/${name}-${vp.w}x${vp.h}.png`,
        animations: 'disabled',
    });

const VIEWPORTS = [
    { w: 1440, h: 900 },
    { w: 390, h: 844 },
];

for (const vp of VIEWPORTS) {
    test(`matrix: onboarding all six steps @ ${vp.w}x${vp.h}`, async ({ page }) => {
        await page.setViewportSize({ width: vp.w, height: vp.h });
        await install(page);
        await page.goto('/onboarding');

        // 1 — welcome
        await expect(page.getByTestId('onboarding-dialog')).toBeVisible();
        await shot(page, '1-welcome', vp);

        // 2 — subjects (one chosen, so the selected state is in the frame)
        await next(page).click();
        await expect(page.getByTestId('subject-english')).toBeVisible();
        await page.getByTestId('subject-english').click();
        await shot(page, '2-subjects', vp);

        // 3 — schools, with the type-ahead open over a real query
        await next(page).click();
        await expect(page.getByTestId('school-input')).toBeVisible();
        await page.getByTestId('school-input').fill('בליך');
        await expect(page.getByTestId('school-results')).toBeVisible();
        await shot(page, '3-schools-typeahead', vp);

        // …and with two picks committed as chips
        await page.getByTestId('school-results').getByRole('button').first().click();
        await page.getByTestId('school-input').fill('הרצוג');
        await page.getByTestId('school-results').getByRole('button').first().click();
        await expect(page.getByTestId('school-chips')).toBeVisible();
        await shot(page, '3-schools-picked', vp);

        // 4 — identity
        await next(page).click();
        await expect(page.locator('#onboarding-full-name')).toBeVisible();
        await page.getByTestId('gender-female').click();
        await shot(page, '4-identity', vp);

        // 5 — exam [028], with a date inside the 14-day window so the booking
        // block is in the frame (it is the only state with real layout).
        await next(page).click();
        await expect(page.getByTestId('exam-date')).toBeVisible();
        await page.getByTestId('exam-date').fill(nearISO());
        await expect(page.getByTestId('exam-booking')).toBeVisible();
        await shot(page, '5-exam', vp);

        // 6 — ready
        await next(page).click();
        await expect(page.getByText('ברוכה הבאה על הסיפון, מיכל')).toBeVisible();
        await shot(page, '6-ready', vp);
    });
}
