import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * The exam step, TYPED rather than filled.
 *
 * Every existing assertion about this step uses `locator.fill()`, which sets
 * `input.value` atomically. That is precisely why this shipped broken: the two
 * defects live in the per-keystroke path, and `fill()` never walks it.
 *
 * What the teacher hit (2026-09-10):
 *   * typing the date died at the YEAR — the segment cursor jumped back to the
 *     start and the remaining digits overwrote the date she had just entered;
 *   * typing a PHONE NUMBER threw the caret up into the date field.
 *
 * One cause. `Modal`'s focus effect listed `onClose` in its dependencies, and
 * `OnboardingDialog` passes an inline `onClose={() => undefined}` — a new
 * identity every render — so the effect re-ran on every keystroke and re-took
 * initial focus. On a text input `.focus()` is invisible (the caret does not
 * move), which is why every other step looked fine; on `<input type="date">`
 * it resets the segment cursor to the first segment, and this is the only step
 * with a second field under a date one.
 *
 * These tests drive the keyboard, so they fail on the real defect and cannot be
 * satisfied by a value that was assigned rather than typed.
 */

const SUBJECTS = [
    { id: 7, code: 'computer_science', name_he: 'מדעי המחשב', name_en: 'Computer Science' },
    { id: 8, code: 'english', name_he: 'אנגלית', name_en: 'English' },
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

/** The id of whatever currently holds focus — the thing both bugs corrupt. */
const focusedId = (page: Page) =>
    page.evaluate(() => document.activeElement?.id ?? null);

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

/**
 * The SEGMENT ORDER of `<input type="date">` is the browser locale's, not the
 * page's, so eight typed digits mean different dates under different locales
 * and an un-pinned run asserts something it did not decide. Pinned to en-GB —
 * day-first, which is what the teacher sees and what her screenshot showed.
 */
const TYPED_DATE = '01102026';
const AS_ISO = '2026-10-01';

test.describe('the exam step survives a keyboard', () => {
    test.use({ locale: 'en-GB' });

    test('the year does not reset the date she has already typed', async ({ page }) => {
        await install(page);
        await walkToExam(page);

        const date = page.getByTestId('exam-date');
        await date.click();
        await page.keyboard.type(TYPED_DATE);

        // The whole date, not the fragment left after a segment reset.
        await expect(date).toHaveValue(AS_ISO);
        // …and she is still in the field she was typing in.
        expect(await focusedId(page)).toBe('onboarding-exam-date');
    });

    test('typing a phone number never throws the caret into the date', async ({ page }) => {
        await install(page);
        await walkToExam(page);

        const date = page.getByTestId('exam-date');
        await date.click();
        await page.keyboard.type(TYPED_DATE);
        await expect(date).toHaveValue(AS_ISO);

        const phone = page.getByTestId('exam-phone');
        await phone.click();
        await page.keyboard.type('0521234567');

        // Every digit landed in the phone field…
        await expect(phone).toHaveValue('0521234567');
        // …focus never left it…
        expect(await focusedId(page)).toBe('onboarding-exam-phone');
        // …and the date she had already answered is untouched.
        await expect(date).toHaveValue(AS_ISO);
    });

    test('the consent box does not move focus either', async ({ page }) => {
        await install(page);
        await walkToExam(page);

        await page.getByTestId('exam-phone').click();
        await page.keyboard.type('0521234567');
        await page.getByTestId('exam-consent').check();

        await expect(page.getByTestId('exam-consent')).toBeChecked();
        await expect(page.getByTestId('exam-phone')).toHaveValue('0521234567');
    });

    test('a NEW step still claims focus — the intended half is preserved', async ({ page }) => {
        // Initial focus is now taken once per open plus once per `focusKey`
        // change. Losing that would be the other kind of regression: arriving
        // at a step with focus stranded on the button that is no longer there.
        await install(page);
        await page.goto('/onboarding');
        await expect(page.getByTestId('onboarding-dialog')).toBeVisible();
        await next(page).click();                          // welcome → subjects
        await page.getByTestId('subject-english').click();
        await next(page).click();                          // subjects → schools
        await page.getByTestId('onboarding-skip').click();  // schools → identity

        // IdentityStep marks its name field `data-autofocus`.
        await expect(page.locator('#onboarding-full-name')).toBeFocused();
    });
});
