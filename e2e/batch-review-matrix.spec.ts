import { expect, test, type Page } from '@playwright/test';
import { seedAuth } from './fixtures';
import {
    AUTH_ME,
    fulfillJson,
    SEED_BATCH_ID,
    seedBatch,
    seedItem,
} from './seedBatch';

/**
 * §4.2 — the REVIEW screenshot matrix (P3): five states × two viewports, one
 * PNG per cell under e2e/review-artifacts/P3/. Protocol note: every 390px
 * cell renders the D11 mobile interstitial BY DESIGN (the module is
 * desktop-only below `desk`); the cells are still shot so the matrix is
 * grid-complete and the honest mobile rendering is itself inspected. The
 * per-cell mockup structural-diff notes happen OUTSIDE this spec (the phase
 * report), after personally opening each PNG.
 */

const PNG_1PX =
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGNgYGBgAAAABQABh6FO1AAAAABJRU5ErkJggg==';

const matched = { matchedStudentId: 's1', matchedStudentName: 'רז כהן' };

/** Flagged item with the full diagnostic dressing: rail chips, a leading
 *  student marker contradicting its assigned key (mismatch banner + swap
 *  proposal), and an empty-unexplained answer (R2 amber marker). */
function flaggedItems() {
    return [
        {
            id: 't1',
            opts: {
                reasons: ['missing_answers', 'segmentation_mismatch'],
                ...matched,
                draft: {
                    answers: [
                        { question_number: 1, sub_question_id: null, answer_text: 'שאלה 2\nint x = 1;', confidence: 0.9, page_numbers: [1] },
                        { question_number: 2, sub_question_id: null, answer_text: '', confidence: 0, page_numbers: [] },
                    ],
                },
            },
        },
        { id: 't2', opts: { ...matched } },
    ];
}

function cleanItems() {
    return [
        { id: 'f1', opts: { reasons: ['low_confidence'], ...matched } },
        { id: 'c1', opts: { ...matched } },
    ];
}

function approvedItems() {
    return [
        {
            id: 'a1',
            opts: {
                status: 'approved' as const,
                ...matched,
                approvedAnswers: [
                    { question_number: 1, sub_question_id: null, answer_text: 'התשובה המאושרת — טקסט החוזה (B6)' },
                ],
            },
        },
        { id: 'c1', opts: { ...matched } },
    ];
}

async function install(page: Page, items: Array<{ id: string; opts?: Record<string, unknown> }>) {
    const payload = seedBatch({
        items: items.map(({ id, opts }) => seedItem(id, opts ?? {})),
    });
    await page.route('**/api/v0/**', async (route) => {
        const url = route.request().url();
        const method = route.request().method();
        if (url.includes('/api/v0/auth/me')) return fulfillJson(route, AUTH_ME);
        if (url.includes('/api/v0/classroom/students')) {
            return fulfillJson(route, {
                students: [{ id: 's1', full_name: 'רז כהן', notes: null, created_at: '2026-01-01T00:00:00Z' }],
            });
        }
        if (method === 'POST' && /\/accept\//.test(url)) {
            return fulfillJson(route, { accepted: 1 });
        }
        if (url.includes(`/api/v0/batches/${SEED_BATCH_ID}`)) return fulfillJson(route, payload);
        if (/\/api\/v0\/transcriptions\/[^/]+\/pages\/\d+/.test(url)) {
            return fulfillJson(route, {
                page_number: Number(url.split('/pages/')[1]),
                thumbnail_base64: PNG_1PX,
            });
        }
        return fulfillJson(route, {});
    });
}

interface Cell {
    name: string;
    items: () => Array<{ id: string; opts?: Record<string, unknown> }>;
    route: string;
    /** Desktop-only setup + anchor assertions before the shot. */
    driveDesktop: (page: Page) => Promise<void>;
}

const CELLS: Cell[] = [
    {
        name: 'flagged',
        items: flaggedItems,
        route: `/batches/${SEED_BATCH_ID}/review/t1`,
        driveDesktop: async (page) => {
            await expect(page.getByTestId('reason-rail')).toBeVisible();
            await expect(page.getByTestId('segmentation-mismatch-banner')).toBeVisible();
            await expect(page.getByTestId('empty-answer-marker')).toBeVisible();
        },
    },
    {
        name: 'clean',
        items: cleanItems,
        route: `/batches/${SEED_BATCH_ID}/review/c1`,
        driveDesktop: async (page) => {
            await expect(page.getByTestId('review-main')).toBeVisible();
            await expect(page.getByTestId('position-primary')).toHaveCount(0);
            await expect(page.getByTestId('position-secondary')).toBeVisible();
        },
    },
    {
        name: 'approved',
        items: approvedItems,
        route: `/batches/${SEED_BATCH_ID}/review/a1`,
        driveDesktop: async (page) => {
            await expect(page.getByText('אושר', { exact: true })).toBeVisible();
            // R7: the read-only editor shows the FROZEN contract text.
            await expect(page.getByTestId('transcription-editor'))
                .toHaveValue('התשובה המאושרת — טקסט החוזה (B6)');
        },
    },
    {
        name: 'interstitial',
        items: cleanItems,
        route: `/batches/${SEED_BATCH_ID}/review/f1`,
        driveDesktop: async (page) => {
            await page.getByRole('button', { name: 'אישור תמלול' }).first().click();
            await page.getByTestId('confirm-accept-primary').click();
            await expect(page.getByTestId('review-interstitial')).toBeVisible();
        },
    },
    {
        name: 'mobile-interstitial',
        items: flaggedItems,
        route: `/batches/${SEED_BATCH_ID}/review/t1`,
        // Desktop cell for this state shows the normal module (the state IS
        // the 390 rendering); nothing extra to drive.
        driveDesktop: async (page) => {
            await expect(page.getByTestId('review-main')).toBeVisible();
        },
    },
];

const VIEWPORTS = [
    { w: 1440, h: 900 },
    { w: 390, h: 844 },
];

for (const cell of CELLS) {
    for (const vp of VIEWPORTS) {
        test(`matrix: review ${cell.name} @ ${vp.w}x${vp.h}`, async ({ page }) => {
            await page.setViewportSize({ width: vp.w, height: vp.h });
            await seedAuth(page);
            await install(page, cell.items());

            await page.goto(cell.route);
            if (vp.w > 940) {
                await cell.driveDesktop(page);
            } else {
                // D11: every review route below `desk` yields the honest
                // interstitial + back link.
                await expect(page.getByTestId('mobile-review-interstitial')).toBeVisible();
                await expect(page.getByRole('link', { name: 'חזרה לסיכום המקבץ' })).toBeVisible();
            }
            await page.screenshot({
                path: `e2e/review-artifacts/P3/review-${cell.name}-${vp.w}x${vp.h}.png`,
                fullPage: true,
            });
        });
    }
}
