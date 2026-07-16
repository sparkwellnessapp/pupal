// Regenerates src/lib/api-types.ts from the backend's OpenAPI schema (PR-4, R-B).
//
// Two deterministic steps:
//   1. Dump the spec via the backend Python (scripts/dump_openapi.py, sort_keys).
//   2. Run the PINNED openapi-typescript over it.
// Deterministic output is what makes the CI drift check (git diff --exit-code)
// meaningful: same backend schema in → byte-identical api-types.ts out. The type
// lie (Decimal typed `number` but sent as a string) dies at the source — the spec
// types every points Decimal as `string` — instead of being patched field-by-field.
//
// Cross-platform (Windows dev / Linux CI): resolves the venv or system Python and
// invokes the locally-installed openapi-typescript CLI via node (no shell, no npx
// network fetch). Override the interpreter with PYTHON=/path/to/python if needed.
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(HERE, '..');
const BACKEND = path.resolve(FRONTEND, '../backend');
const SPEC = path.join(BACKEND, 'openapi.json');          // git-ignored build artifact
const OUT = path.join(FRONTEND, 'src', 'lib', 'api-types.ts');

function resolvePython() {
    if (process.env.PYTHON) return process.env.PYTHON;
    const candidates = [
        path.join(BACKEND, '.venv', 'Scripts', 'python.exe'), // Windows venv
        path.join(BACKEND, '.venv', 'bin', 'python'),          // POSIX venv
    ];
    for (const c of candidates) if (existsSync(c)) return c;
    return process.platform === 'win32' ? 'python' : 'python3';
}

function run(cmd, args, opts) {
    const r = spawnSync(cmd, args, { stdio: 'inherit', ...opts });
    if (r.error) throw r.error;
    return r.status ?? 1;
}

// Step 1 — dump the OpenAPI schema (no server, no DB; dummy service env if unset).
const python = resolvePython();
console.log(`[gen:api] python = ${python}`);
const dumpStatus = run(python, [path.join(BACKEND, 'scripts', 'dump_openapi.py'), SPEC], {
    cwd: BACKEND,
    env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONPATH: BACKEND,
        DATABASE_URL: process.env.DATABASE_URL ?? 'postgresql+asyncpg://x:x@localhost/x',
        OPENAI_API_KEY: process.env.OPENAI_API_KEY ?? 'sk-dummy',
        GOOGLE_CLOUD_PROJECT: process.env.GOOGLE_CLOUD_PROJECT ?? 'dummy',
    },
});
if (dumpStatus !== 0) {
    console.error('[gen:api] OpenAPI dump failed — is the backend importable? (venv + requirements installed)');
    process.exit(dumpStatus);
}

// Step 2 — generate the TS types with the pinned local openapi-typescript CLI.
const cli = path.join(FRONTEND, 'node_modules', 'openapi-typescript', 'bin', 'cli.js');
if (!existsSync(cli)) {
    console.error('[gen:api] openapi-typescript is not installed — run `npm install` first.');
    process.exit(1);
}
const genStatus = run(process.execPath, [cli, SPEC, '-o', OUT], { cwd: FRONTEND });
if (genStatus !== 0) {
    console.error('[gen:api] openapi-typescript failed');
    process.exit(genStatus);
}
console.log(`[gen:api] wrote ${path.relative(FRONTEND, OUT)}`);
