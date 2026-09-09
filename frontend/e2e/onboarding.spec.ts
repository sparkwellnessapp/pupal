import { test, expect, type Page, type Route } from '@playwright/test';

/**
 * The onboarding journey — the render half no vitest suite can reach.
 *
 * Route-mocked like every spec here: deterministic, offline, free. What it
 * guards is the wiring the unit tests cannot see — that an un-onboarded teacher
 * is REDIRECTED in, that each step actually commits (asserted on the requests
 * the browser really made), that the order she picked survives to the wire (the
 * PR-G6 attribution key), and that finishing lets her out.
 */

function futureJwt(): string {
    const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64url');
    return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: 'u1', exp: 4102444800 })}.sig`;
}

const BASE_USER = {
    id: 'u1',
    email: 'teacher@example.com',
    full_name: 'מורה בדיקה',
    subscription_status: 'active',
    is_subscription_active: true,
    subject_matters: [],
    created_at: '2026-01-01T00:00:00Z',
    gender: null,
    schools: [],
    primary_school_id: null,
};

const SUBJECTS = [
    { id: 5, code: 'biology', name_he: 'ביולוגיה', name_en: 'Biology' },
    { id: 7, code: 'computer_science', name_he: 'מדעי המחשב', name_en: 'Computer Science' },
    { id: 8, code: 'english', name_he: 'אנגלית', name_en: 'English' },
    { id: 9, code: 'mathematics', name_he: 'מתמטיקה', name_en: 'Mathematics' },
];

interface Recorded {
    subjects: number[][];
    schools: { name: string; city: string | null; ministry_symbol: string | null }[][];
    profiles: { full_name?: string; gender?: string }[];
    /** [028] Every body the exam step (or the shell's booking link) sent. The
     *  RAW body, not a normalized one: which KEYS arrived is the contract. */
    exams: Record<string, unknown>[];
    completes: number;
}

async function setup(
    page: Page,
    opts: { onboarded?: boolean } = {},
): Promise<Recorded> {
    const user = {
        ...BASE_USER,
        onboarding_completed_at: opts.onboarded ? '2026-01-02T00:00:00Z' : null,
    };

    await page.addInitScript(
        ([token, seeded]) => {
            localStorage.setItem('pupal_auth_token', token as string);
            localStorage.setItem('pupal_user', seeded as string);
        },
        [futureJwt(), JSON.stringify(user)],
    );

    const rec: Recorded = {
        subjects: [], schools: [], profiles: [], exams: [], completes: 0,
    };
    let completed = opts.onboarded ?? false;

    const json = (route: Route, body: unknown, status = 200) =>
        route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) });

    await page.route('**/api/v0/**', async (route) => {
        const req = route.request();
        const url = req.url();
        const method = req.method();
        const me = () => ({
            ...user,
            onboarding_completed_at: completed ? '2026-01-02T00:00:00Z' : null,
        });

        if (url.includes('/auth/me')) return json(route, me());

        if (method === 'GET' && url.includes('/users/subject-matters')) {
            return json(route, SUBJECTS);
        }

        if (method === 'PUT' && url.includes('/users/me/subject-matters')) {
            rec.subjects.push(req.postDataJSON().subject_matter_ids);
            return json(route, SUBJECTS.filter((s) => req.postDataJSON().subject_matter_ids.includes(s.id)));
        }

        if (method === 'PUT' && url.includes('/users/me/schools')) {
            const body = req.postDataJSON().schools;
            rec.schools.push(body);
            return json(
                route,
                body.map((s: { name: string; city: string | null; ministry_symbol: string | null }, i: number) => ({
                    id: `sch-${i}`,
                    name: s.name,
                    city: s.city,
                    ministry_symbol: s.ministry_symbol,
                })),
            );
        }

        if (method === 'PATCH' && url.includes('/users/me/profile')) {
            rec.profiles.push(req.postDataJSON());
            return json(route, { ...me(), ...req.postDataJSON() });
        }

        if (method === 'PATCH' && url.includes('/users/me/onboarding-exam')) {
            const body = req.postDataJSON();
            rec.exams.push(body);
            return json(route, {
                next_exam_date: body.next_exam_date ?? null,
                next_exam_answered_at:
                    'next_exam_date' in body ? '2026-01-02T00:00:00Z' : null,
                phone: body.phone ?? null,
                whatsapp_opt_in: body.whatsapp_opt_in ?? false,
                guided_session_requested_at: body.guided_session_requested
                    ? '2026-01-02T00:00:00Z'
                    : null,
            });
        }

        if (method === 'POST' && url.includes('/users/me/onboarding/complete')) {
            rec.completes += 1;
            completed = true;
            return json(route, { ...me(), onboarding_completed_at: '2026-01-02T00:00:00Z' });
        }

        // Anything the home screen asks for once she is let out.
        return json(route, []);
    });

    return rec;
}

const next = (page: Page) => page.getByTestId('onboarding-next');

/** [028] Dates relative to the RUN, not fixtures: the booking block's 14-day
 *  window is computed against the real clock, so a pinned date would silently
 *  fall out of the window and turn a real assertion into a tautology. */
const iso = (daysAhead: number) => {
    const d = new Date();
    d.setDate(d.getDate() + daysAhead);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};
const nearDate = () => iso(5);        // inside the window
const farFutureDate = () => iso(60);  // well outside it

/** Walk to the exam step through the cheapest legal path. */
async function runToExamStep(page: Page) {
    await page.goto('/onboarding');
    await next(page).click();                       // welcome → subjects
    await page.getByTestId('subject-english').click();
    await next(page).click();                       // subjects → schools
    await page.getByTestId('onboarding-skip').click();  // schools → identity
    await page.getByTestId('gender-female').click();
    await next(page).click();                       // identity → exam
    await expect(page.getByTestId('exam-date')).toBeVisible();
}

test('an un-onboarded teacher is redirected into the flow from the app', async ({ page }) => {
    await setup(page);

    await page.goto('/');

    await expect(page).toHaveURL(/\/onboarding$/);
    await expect(page.getByTestId('onboarding-dialog')).toBeVisible();
});

test('a teacher who finished onboarding is never shown it again', async ({ page }) => {
    await setup(page, { onboarded: true });

    await page.goto('/onboarding');

    // The route itself bounces her out — the URL cannot replay the flow.
    await expect(page).not.toHaveURL(/\/onboarding$/);
});

test('the full journey commits each step and lets her out at the end', async ({ page }) => {
    const rec = await setup(page);

    await page.goto('/onboarding');
    await expect(page.getByTestId('onboarding-dialog')).toBeVisible();

    // 1 — welcome. Prose only; nothing is written.
    await expect(page.getByTestId('onboarding-back')).toHaveCount(0);
    await next(page).click();

    // 2 — subjects. Only the three supported ones are offered (D6).
    await expect(page.getByTestId('subject-english')).toBeVisible();
    await expect(page.getByTestId('subject-mathematics')).toBeVisible();
    await expect(page.getByTestId('subject-computer_science')).toBeVisible();
    await expect(page.getByTestId('subject-biology')).toHaveCount(0);

    // Required: advancing with nothing chosen explains itself and does not move.
    await next(page).click();
    await expect(page.getByTestId('subjects-hint')).toBeVisible();
    expect(rec.subjects).toHaveLength(0);

    await page.getByTestId('subject-english').click();
    await next(page).click();
    expect(rec.subjects).toEqual([[8]]);

    // 3 — schools. Pick two; ORDER is the attribution key and must survive to
    // the wire. Asserted against the labels the UI actually showed rather than
    // against hardcoded names: the index is the real Ministry export (2,194
    // schools) and a test that pins its contents breaks on the next refresh of
    // a file this suite does not own.
    await page.getByTestId('school-input').fill('בליך');
    await page.getByTestId('school-results').getByRole('button').first().click();
    await page.getByTestId('school-input').fill('הרצוג');
    await page.getByTestId('school-results').getByRole('button').first().click();

    const chips = page.getByTestId('school-chips').getByRole('listitem');
    await expect(chips).toHaveCount(2);
    const chipLabels = await chips.allInnerTexts();

    await next(page).click();
    expect(rec.schools).toHaveLength(1);
    const sent = rec.schools[0];
    expect(sent).toHaveLength(2);
    // Same order, and each committed name is the one behind that chip.
    sent.forEach((school, i) => {
        expect(chipLabels[i]).toContain(school.name);
    });
    // Both picks came from the index, so both carry a city — a free-text entry
    // would not, and that difference is what the server's create-or-pick sees.
    expect(sent.every((s) => Boolean(s.city))).toBe(true);
    // …and both carry their Ministry symbol, which is the IDENTITY the server
    // resolves on (023). A pick that reached the wire without one would be
    // silently downgraded to a free-text school.
    sent.forEach((s) => expect(s.ministry_symbol).toMatch(/^[0-9]{4,12}$/));

    // 4 — identity. The name is prefilled from signup; gender is required.
    await expect(page.locator('#onboarding-full-name')).toHaveValue('מורה בדיקה');
    await next(page).click();
    expect(rec.profiles).toHaveLength(0);          // blocked: no gender yet

    await page.getByTestId('gender-female').click();
    await next(page).click();
    expect(rec.profiles).toEqual([{ full_name: 'מורה בדיקה', gender: 'female' }]);

    // 5 — exam [028]. Never blocks, and «עוד לא יודעת» is a real answer.
    await expect(page.getByTestId('exam-date')).toBeVisible();
    await expect(page.getByTestId('onboarding-skip')).toBeVisible();
    await page.getByTestId('exam-date').fill(farFutureDate());
    await page.getByTestId('exam-phone').fill('052-123 4567');
    await next(page).click();

    expect(rec.exams).toHaveLength(1);
    // The phone travels VERBATIM, and consent is sent explicitly false — an
    // omitted flag would leave a stored `true` standing.
    expect(rec.exams[0]).toEqual({
        next_exam_date: farFutureDate(),
        phone: '052-123 4567',
        whatsapp_opt_in: false,
    });

    // 6 — ready. Finishing stamps completion and hands her the app.
    await next(page).click();
    expect(rec.completes).toBe(1);
    await expect(page).not.toHaveURL(/\/onboarding$/);
});

test('«עוד לא יודעת» is a real answer, and it sends an explicit null', async ({ page }) => {
    const rec = await setup(page);
    await runToExamStep(page);

    await page.getByTestId('exam-unknown').click();
    // The booking block is for a date INSIDE the window; "I don't know" is not
    // a date and must not conjure one.
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);
    await next(page).click();

    expect(rec.exams).toEqual([{ next_exam_date: null }]);
});

test('a near date reveals the booking block; a far one does not', async ({ page }) => {
    await setup(page);
    await runToExamStep(page);

    await page.getByTestId('exam-date').fill(farFutureDate());
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);

    await page.getByTestId('exam-date').fill(nearDate());
    await expect(page.getByTestId('exam-booking')).toBeVisible();

    // Switching to "I don't know" retracts it, because there is no date left.
    await page.getByTestId('exam-unknown').click();
    await expect(page.getByTestId('exam-booking')).toHaveCount(0);
});

test('skipping the exam step sends NOTHING — a skip is not an answer', async ({ page }) => {
    const rec = await setup(page);
    await runToExamStep(page);

    await page.getByTestId('onboarding-skip').click();

    // An empty PATCH would still stamp `next_exam_answered_at` server-side and
    // claim she answered — and would then never come due for the re-ask.
    expect(rec.exams).toEqual([]);
    await expect(page.getByTestId('onboarding-next')).toBeVisible();
});

test('clearing the phone withdraws the consent it was given for', async ({ page }) => {
    const rec = await setup(page);
    await runToExamStep(page);

    await page.getByTestId('exam-phone').fill('0521234567');
    await page.getByTestId('exam-consent').check();
    await expect(page.getByTestId('exam-consent')).toBeChecked();

    await page.getByTestId('exam-phone').fill('');
    // The server refuses consent without a number (422); the client must never
    // put it on the wire in the first place.
    await expect(page.getByTestId('exam-consent')).not.toBeChecked();

    await next(page).click();
    expect(rec.exams).toEqual([]);
});

test('the schools step can be skipped, and skipping still records the answer', async ({ page }) => {
    const rec = await setup(page);

    await page.goto('/onboarding');
    await next(page).click();                                   // welcome → subjects
    await page.getByTestId('subject-mathematics').click();
    await next(page).click();                                   // subjects → schools

    await expect(page.getByTestId('onboarding-skip')).toBeVisible();
    await page.getByTestId('onboarding-skip').click();

    // An empty list is an ANSWER ("none yet"), not an absence — it is committed.
    expect(rec.schools).toEqual([[]]);
    await expect(page.locator('#onboarding-full-name')).toBeVisible();
});

test('going back preserves what she already entered', async ({ page }) => {
    await setup(page);

    await page.goto('/onboarding');
    await next(page).click();
    await page.getByTestId('subject-english').click();
    await next(page).click();                                   // → schools

    await page.getByTestId('onboarding-back').click();          // ← subjects

    await expect(page.getByTestId('subject-english')).toHaveAttribute('aria-pressed', 'true');
});

test('a failed commit keeps her on the step and says why', async ({ page }) => {
    await setup(page);
    // Override just the subjects write with a domain failure.
    await page.route('**/api/v0/users/me/subject-matters', (route) =>
        route.fulfill({
            status: 400,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'מקצוע לא תקין' }),
        }),
    );

    await page.goto('/onboarding');
    await next(page).click();
    await page.getByTestId('subject-english').click();
    await next(page).click();

    await expect(page.getByTestId('onboarding-error')).toContainText('מקצוע לא תקין');
    // Still on the subjects step — a failed write never advances the flow.
    await expect(page.getByTestId('subject-english')).toBeVisible();
});

test('the flow is a wall: Escape does not dismiss it', async ({ page }) => {
    await setup(page);

    await page.goto('/onboarding');
    await expect(page.getByTestId('onboarding-dialog')).toBeVisible();

    await page.keyboard.press('Escape');

    await expect(page.getByTestId('onboarding-dialog')).toBeVisible();
    await expect(page).toHaveURL(/\/onboarding$/);
});

test('a school typed by hand carries NO symbol — an honest absence, not a guess', async ({ page }) => {
    const rec = await setup(page);

    await page.goto('/onboarding');
    await next(page).click();
    await page.getByTestId('subject-english').click();
    await next(page).click();                                   // → schools

    // A name the Ministry list does not contain.
    await page.getByTestId('school-input').fill('בית ספר שאינו ברשימה כלל');
    await page.getByTestId('school-free-text').click();
    await expect(page.getByTestId('school-chips').getByRole('listitem')).toHaveCount(1);

    await next(page).click();

    expect(rec.schools).toHaveLength(1);
    expect(rec.schools[0]).toHaveLength(1);
    // Null, not invented: nothing identifies this school but the name she typed,
    // and the server falls back to the name rule for exactly these.
    expect(rec.schools[0][0].ministry_symbol).toBeNull();
    expect(rec.schools[0][0].name).toBe('בית ספר שאינו ברשימה כלל');
});
