#!/usr/bin/env node
// Fail the build when a route's server function would carry the project with it.
//
// WHY THIS EXISTS (2026-09-23). Vercel packages each server route into a
// function from the files Next's tracer lists in `.next/server/**/*.nft.json`,
// and refuses any function over 250 MB. The dev-fixtures route read a path the
// tracer could not resolve statically, so it traced the WHOLE project —
// `.next/cache` included, which Vercel restores before every build and which
// grows with each one — until the function reached 259 MB and every production
// deploy failed at "Deploying outputs", after a green `next build`. Nothing on
// this machine could see it: `next build` passes, and the Vercel log is behind
// the owner's login.
//
// A healthy route traces well under 1 MB here, so the bar sits far below
// Vercel's limit: a regression fails HERE, on the first build that has it,
// instead of the day the cache happens to grow past 250 MB. Sizes are the
// files as they sit on disk, summed per route (what the function would ship).
import fs from 'node:fs';
import path from 'node:path';

const LIMIT_MB = 50;
const distDir = process.env.NEXT_DIST_DIR || '.next';
const serverDir = path.join(distDir, 'server');

function* nftFiles(dir) {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) yield* nftFiles(full);
        else if (entry.name.endsWith('.nft.json')) yield full;
    }
}

if (!fs.existsSync(serverDir)) {
    console.error(`[check-function-size] no ${serverDir} — run after \`next build\``);
    process.exit(1);
}

const offenders = [];
let largest = { route: null, mb: 0 };
for (const nft of nftFiles(serverDir)) {
    const base = path.dirname(nft);
    const { files } = JSON.parse(fs.readFileSync(nft, 'utf8'));
    let bytes = 0;
    for (const rel of files) {
        try {
            bytes += fs.statSync(path.resolve(base, rel)).size;
        } catch {
            // a traced path that is absent here is absent from the function too
        }
    }
    const mb = bytes / 1e6;
    const route = path.relative(serverDir, nft).replace(/\\/g, '/').replace(/\.nft\.json$/, '');
    if (mb > largest.mb) largest = { route, mb };
    if (mb > LIMIT_MB) offenders.push({ route, mb, files: files.length });
}

if (offenders.length) {
    for (const o of offenders) {
        console.error(
            `[check-function-size] ${o.route} traces ${o.mb.toFixed(1)} MB (${o.files} files) `
            + `— over ${LIMIT_MB} MB. Vercel refuses functions over 250 MB. Usually a filesystem `
            + 'read whose path the tracer cannot resolve statically (see the dev-fixtures route).');
    }
    process.exit(1);
}
console.log(`[check-function-size] ok — largest route ${largest.route} at ${largest.mb.toFixed(1)} MB`);
