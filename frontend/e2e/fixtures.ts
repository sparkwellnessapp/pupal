import { readFileSync } from 'node:fs';
import path from 'node:path';
import type { Page } from '@playwright/test';

// The golden rubrics are read IN PLACE from the backend eval suite — the canonical
// owner of these fixtures (CLAUDE.md §0.4, same as the vitest suites). __dirname
// (not import.meta) so this transpiles under Playwright's CommonJS loader.
const BENCHMARKS = path.resolve(__dirname, '../../backend/tests/rubric_eval_suite/benchmarks');

export function loadGoldenRaw(name: string): string {
    return readFileSync(path.join(BENCHMARKS, `${name}.json`), 'utf-8');
}

const USER = {
    id: 'u1',
    email: 'teacher@example.com',
    full_name: 'מורה בדיקה',
    subscription_status: 'active',
    is_subscription_active: true,
    subject_matters: [],
    created_at: '2026-01-01T00:00:00Z',
};

/** A well-formed JWT with a far-future exp so session.ts never renews/logs out. */
function futureJwt(): string {
    const b64 = (o: object) => Buffer.from(JSON.stringify(o)).toString('base64url');
    return `${b64({ alg: 'HS256', typ: 'JWT' })}.${b64({ sub: 'u1', exp: 4102444800 })}.sig`;
}

/** Seed the auth localStorage BEFORE any app code runs, so the wizard renders
 *  authenticated without a real login. */
export async function seedAuth(page: Page): Promise<void> {
    await page.addInitScript(
        ([token, user]) => {
            localStorage.setItem('pupal_auth_token', token as string);
            localStorage.setItem('pupal_user', user as string);
        },
        [futureJwt(), JSON.stringify(USER)],
    );
}

export interface MockOptions {
    /** Which golden the mocked extraction job returns. */
    fixture: string;
    /** Save behaviour: 'ok' → 201 success; 'reject-then-ok' → first 400 (structured
     *  compile error), then 201. */
    save?: 'ok' | 'reject-then-ok';
    /** The full-path node id the mocked 400 anchors to (must exist in the fixture). */
    rejectLocation?: string;
}

/** Route-mock the entire backend surface the rubric wizard touches. A single
 *  catch-all dispatched by URL+method — no route-ordering surprises. */
export async function installMocks(page: Page, opts: MockOptions): Promise<void> {
    const resultJson = loadGoldenRaw(opts.fixture);
    let statusPolls = 0;
    let savePosts = 0;

    const json = (body: unknown, status = 200) => ({
        status,
        contentType: 'application/json',
        body: typeof body === 'string' ? body : JSON.stringify(body),
    });

    await page.route('**/api/v0/**', async (route) => {
        const req = route.request();
        const url = req.url();
        const method = req.method();

        // Auth: verifyToken hits /auth/me — must return the user, else it logs out.
        if (url.includes('/api/v0/auth/me')) {
            return route.fulfill(json(USER));
        }

        // Resume-on-mount: no active job.
        if (method === 'GET' && url.includes('/extraction-jobs') && url.includes('active=')) {
            return route.fulfill(json([]));
        }

        // Submit a DOCX for extraction.
        if (method === 'POST' && /\/extraction-jobs\/?(\?|$)/.test(url)) {
            return route.fulfill(json({ job_id: 'job-e2e', status: 'queued', reused: false }));
        }

        // Poll a job's status — one 'extracting' tick, then 'completed'.
        if (method === 'GET' && /\/extraction-jobs\/job-e2e$/.test(url)) {
            statusPolls += 1;
            const done = statusPolls >= 2;
            return route.fulfill(json({
                job_id: 'job-e2e',
                status: done ? 'completed' : 'extracting',
                progress_stage: done ? 'complete' : 'llm_call',
                progress_detail: null,
                stale: false,
                error_message: null,
                has_result: done,
                source_filename: `${opts.fixture}.docx`,
                created_at: '2026-01-01T00:00:00Z',
                started_at: '2026-01-01T00:00:01Z',
                finished_at: done ? '2026-01-01T00:00:05Z' : null,
                elapsed_seconds: done ? 5 : 2,
            }));
        }

        // Fetch the completed job's ExtractRubricResponse (the golden).
        if (method === 'GET' && /\/extraction-jobs\/job-e2e\/result$/.test(url)) {
            return route.fulfill(json({
                job_id: 'job-e2e',
                result: JSON.parse(resultJson),
                warnings: [],
                errors: [],
                requires_review: null,
                provenance: {},
            }));
        }

        // Save (compile) the reviewed draft.
        if (method === 'POST' && url.includes('/save_ontology_draft')) {
            savePosts += 1;
            if (opts.save === 'reject-then-ok' && savePosts === 1) {
                return route.fulfill(json({
                    detail: {
                        error_type: 'compilation_failed',
                        message_he: 'המחוון לא עבר בדיקה',
                        errors: [{
                            location: opts.rejectLocation ?? null,
                            invariant: 'INV-2',
                            expected: '3',
                            actual: '2',
                            message: 'criteria sum (2) != declared (3)',
                            message_he: `סעיף ${opts.rejectLocation}: סכום רכיבי הניקוד (2) שונה מהניקוד המוצהר (3)`,
                        }],
                    },
                }, 400));
            }
            return route.fulfill(json({
                rubric_id: 'rub-e2e',
                name: opts.fixture,
                is_ontology_format: true,
                is_compiled: true,
                needs_recompilation: false,
                created_at: '2026-01-01T00:00:00Z',
                stats: { total_points: 50, total_questions: 3, total_criteria: 18, total_sub_criteria: 0 },
            }, 201));
        }

        // Anything else the flow happens to touch — keep it lenient, never hit a
        // real (nonexistent) backend.
        return route.fulfill(json({}));
    });
}
