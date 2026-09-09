import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * [028 §8] The exam step's VERIFICATION GATE — the six states the spec names,
 * at 390×844, plus 1440×900 for the one state with real layout (the booking
 * block). One PNG per cell under `e2e/snapshots/onboarding-exam/`.
 *
 * The spec names that directory explicitly, which is why it is not the
 * `e2e/review-artifacts/` the other matrices use: a human is being told where
 * to look, and moving the target would be the least helpful possible tidiness.
 *
 * 390px is the brief, not a convenience: the teacher this step is written for
 * arrives from WhatsApp on a phone. Every defect this gate exists to catch —
 * a date control that lays out LTR inside an RTL panel, the consent line
 * wrapping badly, a primary action out of thumb reach — is invisible at 1440.
 *
 * This file PRODUCES artifacts and asserts only enough to prove each frame is
 * the state it claims to be. The behavioural guarantees live in
 * onboarding.spec.ts.
 */

const SUBJECTS = [
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

/** Relative to the RUN. The booking window is computed against the real clock,
 *  so a pinned date would fall out of it and freeze a frame that no longer
 *  shows what its filename claims. */
const iso = (daysAhead: number) => {
    const d = new Date();
    d.setDate(d.getDate() + daysAhead);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

const next = (page: Page) => page.getByTestId('onboarding-next');

/**
 * `animations: 'disabled'` is load-bearing (the 2026-09-01 measurement): the
 * chips and buttons carry `transition-colors`, so a shot taken right after a
 * click freezes the 150ms transition HALFWAY and shows a washed-out
 * in-between colour. An artifact whose whole job is to be LOOKED AT must not
 * lie about the state it claims to show.
 */
const shot = (page: Page, name: string, w: number, h: number) =>
    page.screenshot({
        path: `e2e/snapshots/onboarding-exam/${name}-${w}x${h}.png`,
        animations: 'disabled',
    });

async function walkToExam(page: Page) {
    await page.goto('/onboarding');
    await expect(page.getByTestId('onboarding-dialog')).toBeVisible();
    await next(page).click();                              // welcome → subjects
    await page.getByTestId('subject-english').click();
    await next(page).click();                              // subjects → schools
    await page.getByTestId('onboarding-skip').click();     // schools → identity
    await expect(page.locator('#onboarding-full-name')).toBeVisible();
    await page.getByTestId('gender-female').click();
    await next(page).click();                              // identity → exam
    await expect(page.getByTestId('exam-date')).toBeVisible();
}

test('snapshots: the exam step, six states @ 390x844', async ({ page }) => {
    const [w, h] = [390, 844];
    await page.setViewportSize({ width: w, height: h });
    await install(page);
    await walkToExam(page);

    // (1) empty — nothing answered, no booking block, no acknowledgement.
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);
    await expect(page.getByTestId('exam-acknowledgement')).toHaveCount(0);
    await shot(page, '1-empty', w, h);

    // (2) a date well outside the window: acknowledged, no booking block.
    await page.getByTestId('exam-date').fill(iso(60));
    await expect(page.getByTestId('exam-acknowledgement')).toBeVisible();
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);
    await shot(page, '2-date-far', w, h);

    // (3) inside the 14-day window: the booking block is the point of the frame.
    await page.getByTestId('exam-date').fill(iso(5));
    await expect(page.getByTestId('exam-booking')).toBeVisible();
    await shot(page, '3-date-near-booking', w, h);

    // (4) «עוד לא יודעת» — a real answer, and it retracts the booking block.
    await page.getByTestId('exam-unknown').click();
    await expect(page.getByTestId('exam-unknown')).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);
    await shot(page, '4-unknown', w, h);

    // (5) phone filled and consent ticked — the longest string on the page.
    await page.getByTestId('exam-phone').fill('052-123 4567');
    await page.getByTestId('exam-consent').check();
    await expect(page.getByTestId('exam-consent')).toBeChecked();
    await shot(page, '5-phone-consent', w, h);

    // (6) success — the screen she lands on after the step commits.
    await next(page).click();
    await expect(page.getByText('ברוכה הבאה על הסיפון, מיכל')).toBeVisible();
    await shot(page, '6-success', w, h);
});

test('snapshots: the booking block @ 1440x900', async ({ page }) => {
    const [w, h] = [1440, 900];
    await page.setViewportSize({ width: w, height: h });
    await install(page);
    await walkToExam(page);

    await page.getByTestId('exam-date').fill(iso(5));
    await expect(page.getByTestId('exam-booking')).toBeVisible();
    await shot(page, '3-date-near-booking', w, h);
});
