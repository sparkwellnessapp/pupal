/**
 * The dev-only MSW entry point.
 *
 * Off unless BOTH are true: this is not a production build, and
 * `NEXT_PUBLIC_GRADE_REVIEW_FIXTURES=1` is set. Two conditions rather than
 * one because a mock layer that can reach production is a mock layer that
 * will: the flag is the intent, the build check is the guarantee.
 *
 * Everything here is dynamically imported, so `msw` never enters a production
 * bundle even by accident.
 *
 * Usage (frontend/.env.local):
 *     NEXT_PUBLIC_GRADE_REVIEW_FIXTURES=1
 * then, once, to write the worker file:
 *     npx msw init public/ --save
 */

export const GRADE_REVIEW_FIXTURES_ENABLED =
    process.env.NODE_ENV !== 'production'
    && process.env.NEXT_PUBLIC_GRADE_REVIEW_FIXTURES === '1';

let started: Promise<void> | null = null;

export function startGradeReviewMocks(): Promise<void> {
    if (!GRADE_REVIEW_FIXTURES_ENABLED || typeof window === 'undefined') {
        return Promise.resolve();
    }
    if (started) return started;

    started = (async () => {
        const [{ setupWorker }, { gradeReviewHandlers }] = await Promise.all([
            import('msw/browser'),
            import('./handlers'),
        ]);
        await setupWorker(...gradeReviewHandlers).start({
            // An unhandled request is the app talking to the real backend.
            // That is normal here (only the grade-review endpoints are mocked)
            // and must not spam the console into uselessness.
            onUnhandledRequest: 'bypass',
            quiet: false,
        });
        // eslint-disable-next-line no-console
        console.info(
            '[grade-review] MSW on. Fixtures come from backend/tests/fixtures/'
            + 'grade_review via /api/dev-fixtures — never copied. Add ?fixture='
            + '<student> to pick a draft.',
        );
    })();

    return started;
}
