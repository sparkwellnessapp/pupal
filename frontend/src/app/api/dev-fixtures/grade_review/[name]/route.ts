import { readFile } from 'node:fs/promises';
import path from 'node:path';
import { NextResponse } from 'next/server';

import { PENDING_FIXTURES, PRESENT_FIXTURES } from '@/mocks/grade_review/registry';

/**
 * DEV ONLY. Serves the §1.7 fixtures to the browser straight off disk, so the
 * MSW layer can answer with real generated payloads instead of copies.
 *
 * Why a route at all: the fixtures are the backend's, they are generated, and
 * `src/mocks/` must not fork them (§0.4). Node tests read them in place; the
 * browser cannot, so this is the one door. It is deleted with the MSW layer at
 * integration.
 *
 * TWO GUARDS, both load-bearing:
 *   * 404 in production. This reads the filesystem by request; it has no
 *     business existing on a deployed site, and "the flag is off" is not the
 *     same as "the code is not there".
 *   * The name is ALLOWLISTED against the registry, never sanitized. A
 *     sanitizer is a claim about every encoding an attacker might try; an
 *     allowlist is a claim about five files.
 */

export const dynamic = 'force-dynamic';

const DISABLED = process.env.NODE_ENV === 'production';

export async function GET(
    _request: Request,
    { params }: { params: { name: string } },
) {
    if (DISABLED) return new NextResponse('Not found', { status: 404 });

    const { name } = params;
    if (!PRESENT_FIXTURES.includes(name)) {
        const pending = PENDING_FIXTURES[name];
        return NextResponse.json(
            {
                error: 'fixture_not_published',
                fixture: name,
                // The backend's own reason, verbatim — so a developer reads
                // "PR-G8 — the batch feed shape does not exist yet" and knows
                // this is a gap to surface, not a path to fix.
                reason: pending ?? 'not part of the published §1.7 fixture set',
                published: PRESENT_FIXTURES,
            },
            { status: 501 },
        );
    }

    // THE DIRECTORY IS A LITERAL, IN THIS FILE, ON PURPOSE (2026-09-23). Next's
    // file tracer decides what this route's Vercel function carries by reading
    // this call statically. With the directory imported as a constant it could
    // not tell which folder was read, so it packed the WHOLE project — `.next/
    // cache` included, which Vercel restores and which grows every build — and
    // the function crossed Vercel's 250 MB limit (259 MB) and failed every
    // deploy. A literal lets it trace `../backend/…/grade_review/*` alone, and
    // that folder is not in the deploy checkout, so the function carries nothing.
    // `scripts/check-function-size.mjs` fails the build if this ever regresses.
    const file = path.join(process.cwd(), '../backend/tests/fixtures/grade_review', name);
    try {
        const body = await readFile(file, 'utf-8');
        return new NextResponse(body, {
            status: 200,
            headers: { 'content-type': 'application/json; charset=utf-8' },
        });
    } catch {
        return NextResponse.json(
            {
                error: 'fixture_unreadable',
                fixture: name,
                looked_in: file,
                hint: 'the fixtures live in the backend tree and are never copied — '
                    + 'run this dev server from vivi-codebase/frontend',
            },
            { status: 500 },
        );
    }
}
