import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';

/**
 * Design Recovery §1a — the token lint gate (SCOPED to the document-mirror surface).
 *
 * Component classes on the mirror may NOT contain a raw hex color or a bare
 * arbitrary px value — tokens only (see tailwind.config.ts: doc-*, w-rail,
 * max-w-document, the surface/primary palette). Structural arbitrary values
 * (calc(), %, rem, vh, fr, breakpoints) are allowed.
 *
 * Scoped to the mirror on purpose: the rest of the app carries ~79 legacy
 * arbitrary values (decorative orbs, modal sizing) — a repo-wide gate is a
 * separate migration (BACKLOG). Expand SCOPE when that lands.
 *
 * S12/F0 adds the GRADE-REVIEW surface to the scope, from its first line of
 * code rather than after the fact. F0 lands the palette, the radii and the
 * `gr-*` type scale precisely so F1-F3 never need `text-[21px]` or a raw
 * `#C8102E`; a gate that starts clean stays clean, while one retro-fitted to a
 * finished surface only prints debt.
 */

const ROOT = path.resolve('src');
const SCOPE = [
    path.join(ROOT, 'components', 'document'),
    path.join(ROOT, 'components', 'RubricDocument.tsx'),
    // Grade review (S12). Listed ahead of the routes that will fill them — a
    // path that does not exist yet is skipped, never a crash (see filesUnder).
    path.join(ROOT, 'components', 'grade-review'),
    path.join(ROOT, 'app', 'graded-tests'),
];

// Flag a bracket value that is EXACTLY a hex color or a bare px length.
const BRACKET_RE = /-\[([^\]]+)\]/g;
const HEX_RE = /^#[0-9A-Fa-f]{3,8}$/;
const BARE_PX_RE = /^-?[0-9.]+px$/;

function filesUnder(p) {
    // A scope entry may name a surface that has not been built yet (the S12
    // routes). Skipping is correct; crashing would make the gate look broken
    // on a tree where it is simply not needed yet.
    if (!existsSync(p)) return [];
    const st = statSync(p);
    if (st.isFile()) return p.endsWith('.tsx') && !p.endsWith('.test.tsx') ? [p] : [];
    return readdirSync(p).flatMap((c) => filesUnder(path.join(p, c)));
}

const violations = [];
for (const target of SCOPE) {
    for (const file of filesUnder(target)) {
        readFileSync(file, 'utf-8').split('\n').forEach((line, i) => {
            let m;
            BRACKET_RE.lastIndex = 0;
            while ((m = BRACKET_RE.exec(line))) {
                const v = m[1];
                if (HEX_RE.test(v) || BARE_PX_RE.test(v)) {
                    violations.push(`${path.relative(ROOT, file)}:${i + 1}  -[${v}]`);
                }
            }
        });
    }
}

if (violations.length) {
    console.error('✗ token gate: raw hex/px in the mirror surface — use tokens (tailwind.config.ts):');
    violations.forEach((v) => console.error('  ' + v));
    process.exit(1);
}
console.log('✓ token gate: mirror surface is token-clean');
