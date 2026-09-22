import type { Page } from '@playwright/test';

import { USER, seedAuth } from './fixtures';
import { syntheticPageSvg } from './gradeReviewFixtures';

/**
 * Route mocks for הכיתות שלי — the roster and the student profile
 * (PR_student_profile.md §8.3). The data is the mockup's own cast, so the
 * parity captures compare like with like.
 *
 * Ids are REAL UUIDs on purpose: the returned page's return context accepts
 * a student only when it looks like one (§6.5 — typed context, never a path).
 */
export const STUDENTS = {
    itayK:  { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa1', full_name: 'איתי כתב',   signed_tests_count: 0 },
    itayKr: { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa2', full_name: 'איתי קראפט', signed_tests_count: 1 },
    dean:   { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa3', full_name: 'דין עזרא',   signed_tests_count: 2 },
    dan:    { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa4', full_name: 'דן בסיוק',   signed_tests_count: 3 },
    moran:  { id: 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa5', full_name: 'מורן אהרון', signed_tests_count: 3 },
} as const;

export const MISSING_STUDENT = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaa9';

export const BATCH_HOBBY = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb1';
export const BATCH_ARRAYS = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbb2';
export const TEST_HOBBY = 'cccccccc-cccc-4ccc-8ccc-ccccccccccc1';
export const TEST_ARRAYS = 'cccccccc-cccc-4ccc-8ccc-ccccccccccc2';
export const TEST_RECURSION = 'cccccccc-cccc-4ccc-8ccc-ccccccccccc3';
/** A signed test whose scan has no rendered page — the M-A8 placeholder. */
export const TEST_NO_PAGES = 'cccccccc-cccc-4ccc-8ccc-ccccccccccc4';
export const CLASS_ID = 'dddddddd-dddd-4ddd-8ddd-ddddddddddd1';

const thumb = (transcription: string) =>
    `/api/v0/transcriptions/${transcription}/pages/1/image?v=600x72@110`;

/** Moran's three rows, in the profile's order (upload date, newest first). */
export const MORAN_SIGNED_TESTS = [
    {
        graded_test_id: TEST_HOBBY,
        exam: { batch_id: BATCH_HOBBY, name: 'Hobby & TvShow', rubric_name: 'Hobby & TvShow',
                class_name: 'י"א 3', uploaded_at: '2026-09-14T09:00:00+03:00' },
        approved_at: '2026-09-19T16:58:00+03:00',
        total_score: '85.50', total_possible: '100.00',
        thumbnail: { page1_image_url: thumb('t-hobby'),
                     stamp_position: { x: 0.2, y: 0.15, corner: null, source: 'manual' } },
    },
    {
        graded_test_id: TEST_ARRAYS,
        exam: { batch_id: BATCH_ARRAYS, name: null, rubric_name: 'מחלקות ומערכים',
                class_name: "י' 3", uploaded_at: '2026-06-22T09:00:00+03:00' },
        approved_at: '2026-06-24T21:12:00+03:00',
        total_score: '92.00', total_possible: '100.00',
        thumbnail: { page1_image_url: thumb('t-arrays'),
                     stamp_position: { corner: 'br', source: 'manual' } },
    },
    {
        // Single-flow: no batch, so no name and no class — the rubric names it.
        graded_test_id: TEST_RECURSION,
        exam: { batch_id: null, name: null, rubric_name: 'בוחן רקורסיה',
                class_name: null, uploaded_at: '2026-03-03T09:00:00+02:00' },
        approved_at: '2026-03-05T19:40:00+02:00',
        total_score: '64.00', total_possible: '80.00',
        thumbnail: { page1_image_url: thumb('t-recursion'), stamp_position: null },
    },
];

/**
 * Itay Kraft's ONE signed test: batch-less AND page-less.
 *
 * M-A8 / §3.5a — a scan the server could not render offers no image, so the
 * row draws the neutral placeholder and STAYS clickable. It is a separate
 * student on purpose: Moran's three rows are the parity capture against the
 * «Profile» artboard and must keep its cast.
 */
export const ITAY_KRAFT_SIGNED_TESTS = [
    {
        graded_test_id: TEST_NO_PAGES,
        exam: { batch_id: null, name: null, rubric_name: 'בוחן קצר',
                class_name: null, uploaded_at: '2026-05-04T09:00:00+03:00' },
        approved_at: '2026-05-06T11:20:00+03:00',
        total_score: '48.00', total_possible: '50.00',
        thumbnail: { page1_image_url: null, stamp_position: null },
    },
];

export interface ProfileMockOptions {
    /** Students the interim delete refuses (409 `student_has_data`). */
    deleteRefused?: readonly string[];
}

export async function installProfileMocks(page: Page, opts: ProfileMockOptions = {}): Promise<{
    deleted: string[];
}> {
    await seedAuth(page);
    const deleted: string[] = [];
    const refused = new Set(opts.deleteRefused ?? [STUDENTS.moran.id]);

    const json = (body: unknown, status = 200) => ({
        status, contentType: 'application/json', body: JSON.stringify(body),
    });
    const detailOf = (s: (typeof STUDENTS)[keyof typeof STUDENTS]) => ({
        ...s,
        created_at: '2026-01-10T10:00:00Z',
        classes: s.id === STUDENTS.itayK.id || s.id === STUDENTS.moran.id
            ? [{ id: CLASS_ID, name: 'י"א 3' }]
            : [],
    });
    const CLASS = {
        id: CLASS_ID, name: 'י"א 3', subject_matter_id: 1,
        subject_matter_name: 'מדעי המחשב', school_year: '2026',
        student_count: 2, created_at: '2026-01-10T10:00:00Z',
    };

    await page.route('**/api/v0/**', async (route) => {
        const req = route.request();
        const url = new URL(req.url());
        const path = url.pathname;
        const method = req.method();

        if (path.endsWith('/auth/me')) return route.fulfill(json(USER));

        if (method === 'GET' && path.includes('/pages/') && path.includes('/image')) {
            const seed = [...path].reduce((n, c) => (n + c.charCodeAt(0)) % 997, 7);
            return route.fulfill({ status: 200, contentType: 'image/svg+xml', body: syntheticPageSvg(seed) });
        }

        const signed = path.match(/\/classroom\/students\/([^/]+)\/signed-tests$/);
        if (method === 'GET' && signed) {
            const id = signed[1];
            if (id === STUDENTS.moran.id) {
                return route.fulfill(json({ signed_tests_count: 3, truncated: false, signed_tests: MORAN_SIGNED_TESTS }));
            }
            if (id === STUDENTS.itayKr.id) {
                return route.fulfill(json({
                    signed_tests_count: 1, truncated: false, signed_tests: ITAY_KRAFT_SIGNED_TESTS,
                }));
            }
            const known = Object.values(STUDENTS).find((s) => s.id === id);
            if (!known) return route.fulfill(json({ detail: 'Student not found' }, 404));
            return route.fulfill(json({ signed_tests_count: 0, truncated: false, signed_tests: [] }));
        }

        const one = path.match(/\/classroom\/students\/([^/]+)$/);
        if (one) {
            const id = one[1];
            const known = Object.values(STUDENTS).find((s) => s.id === id);
            if (!known) return route.fulfill(json({ detail: 'Student not found' }, 404));
            if (method === 'DELETE') {
                if (refused.has(id)) return route.fulfill(json({ detail: 'student_has_data' }, 409));
                deleted.push(id);
                return route.fulfill({ status: 204, body: '' });
            }
            if (method === 'PATCH') {
                const body = req.postDataJSON() as { full_name?: string };
                return route.fulfill(json({ ...known, full_name: body.full_name ?? known.full_name,
                                             created_at: '2026-01-10T10:00:00Z' }));
            }
            return route.fulfill(json(detailOf(known)));
        }

        if (method === 'GET' && path.endsWith('/classroom/students')) {
            return route.fulfill(json({ students: Object.values(STUDENTS).map((s) => ({
                ...s, created_at: '2026-01-10T10:00:00Z',
            })) }));
        }
        if (method === 'GET' && path.endsWith(`/classroom/classes/${CLASS_ID}`)) {
            // FA-1: the class's student list — the OD-2 entry point that lives
            // in the «ניהול תלמידים» modal, this product's class detail.
            return route.fulfill(json({
                ...CLASS,
                students: [
                    { id: STUDENTS.moran.id, full_name: STUDENTS.moran.full_name },
                    { id: STUDENTS.itayK.id, full_name: STUDENTS.itayK.full_name },
                ],
            }));
        }
        if (method === 'GET' && path.endsWith('/classroom/classes')) {
            return route.fulfill(json({ classes: [CLASS] }));
        }
        if (method === 'GET' && path.endsWith('/users/subject-matters')) {
            return route.fulfill(json([{ id: 1, code: 'cs', name_he: 'מדעי המחשב', name_en: 'CS' }]));
        }
        return route.fulfill(json({ detail: `unmocked ${method} ${path}` }, 500));
    });

    return { deleted };
}
