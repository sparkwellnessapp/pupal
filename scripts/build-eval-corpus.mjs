#!/usr/bin/env node
/**
 * Stage E (UPLOAD_LATENCY_PLAN.md) — build the variant corpora the eval judges.
 *
 * THE POINT, and the reason this is a Playwright script and not a Python one:
 * the corpus must be produced by THE ENCODER THAT WOULD SHIP. A browser's JPEG
 * encoder is Skia; the server's is libjpeg-turbo. They quantise differently, so
 * a corpus built with Pillow would measure an encoder no teacher will ever run,
 * and a passing gate would prove nothing about production. So this drives the
 * real `src/utils/page-repack.ts` inside real Chromium, over the real fixtures.
 *
 * ONE SOURCE OF TRUTH. The transform is not reimplemented here — it is bundled
 * from `src/utils/page-repack.ts` with esbuild and injected into the page. If
 * Stage F ships, the teacher's browser runs that same module. A second copy for
 * the eval is exactly the two-copies-drift this codebase keeps paying for.
 *
 * IT SPENDS NO MONEY AND CALLS NO MODEL. It writes PDFs to disk. The paid run
 * is a separate, explicit command (printed at the end).
 *
 * Usage:
 *   node scripts/build-eval-corpus.mjs                    # q95, q90, q85
 *   node scripts/build-eval-corpus.mjs --quality 90
 *   node scripts/build-eval-corpus.mjs --fixtures bagrut_899371.din_ezra
 *   node scripts/build-eval-corpus.mjs --dpi 150          # eval-gated, not default
 */
import { chromium } from '@playwright/test'
import { build } from 'esbuild'
import { createRequire } from 'node:module'
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const require = createRequire(import.meta.url)
// fileURLToPath, not URL.pathname — the repo path contains a space, and
// pathname hands back a percent-encoded string (the check-copy.mjs lesson).
const ROOT = fileURLToPath(new URL('..', import.meta.url))
const SUITE = resolve(ROOT, '..', 'backend', 'tests', 'transcription_eval_suit')
const SOURCE_PDFS = join(SUITE, 'pdfs')
const OUT_ROOT = join(SUITE, 'pdfs-variants')

// The candidates ruled in the plan. Lower is NOT a candidate: the 2026-08-19
// RUNLOG declined q90 ON THE WIRE, a milder change than this one, so the band
// worth testing starts at the top and works down.
const DEFAULT_QUALITIES = [95, 90, 85]

function arg(name, fallback = null) {
  const i = process.argv.indexOf(`--${name}`)
  return i === -1 ? fallback : process.argv[i + 1]
}

/** Bundle the REAL transform into one IIFE the page can run. */
async function bundleTransform() {
  const result = await build({
    entryPoints: [join(ROOT, 'src', 'utils', 'page-repack.ts')],
    bundle: true,
    format: 'iife',
    globalName: 'PageRepack',
    platform: 'browser',
    write: false,
    target: 'es2020',
  })
  return result.outputFiles[0].text
}

async function main() {
  const only = arg('fixtures')
  const dpi = Number(arg('dpi', '200'))
  const qualities = arg('quality')
    ? [Number(arg('quality'))]
    : DEFAULT_QUALITIES

  let sources
  try {
    sources = readdirSync(SOURCE_PDFS).filter((f) => f.toLowerCase().endsWith('.pdf'))
  } catch {
    console.error(`✗ no fixture directory at ${SOURCE_PDFS}`)
    process.exit(1)
  }
  if (only) {
    const wanted = new Set(only.split(',').map((s) => s.trim().toLowerCase()))
    sources = sources.filter((f) => wanted.has(f.replace(/\.pdf$/i, '').toLowerCase()))
  }
  if (sources.length === 0) {
    console.error('✗ no fixtures matched')
    process.exit(1)
  }

  console.log(`Stage E corpus builder`)
  console.log(`  source   ${SOURCE_PDFS}`)
  console.log(`  fixtures ${sources.length}`)
  console.log(`  dpi      ${dpi}`)
  console.log(`  quality  ${qualities.join(', ')}`)
  console.log()

  const transform = await bundleTransform()
  // The browser build of pdf.js, taken from the installed package so the
  // version is the pinned one rather than whatever a CDN serves today.
  const pdfjsPath = require.resolve('pdfjs-dist/build/pdf.min.mjs')
  const workerPath = require.resolve('pdfjs-dist/build/pdf.worker.min.mjs')

  const browser = await chromium.launch()
  const page = await browser.newPage()
  page.on('console', (m) => {
    if (m.type() === 'error') console.error('  [page]', m.text())
  })
  await page.goto('about:blank')
  await page.addScriptTag({ content: transform })
  await page.addScriptTag({
    content: `${readFileSync(pdfjsPath, 'utf8')}\nwindow.__pdfjs = pdfjsLib;`,
    type: 'module',
  })
  await page.addScriptTag({
    content: `window.__pdfWorkerSrc = ${JSON.stringify(
      'data:text/javascript;base64,' + readFileSync(workerPath).toString('base64'))};`,
  })
  await page.waitForFunction('window.__pdfjs && window.PageRepack')

  const rows = []
  for (const quality of qualities) {
    const outDir = join(OUT_ROOT, `jpeg${quality}${dpi === 200 ? '' : `-dpi${dpi}`}`)
    mkdirSync(outDir, { recursive: true })
    for (const name of sources) {
      const original = readFileSync(join(SOURCE_PDFS, name))
      const result = await page.evaluate(
        async ({ b64, quality, dpi }) => {
          const bin = atob(b64)
          const bytes = new Uint8Array(bin.length)
          for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i)
          window.__pdfjs.GlobalWorkerOptions.workerSrc = window.__pdfWorkerSrc
          const out = await window.PageRepack.repackPdfToJpegPages(
            window.__pdfjs, bytes, { quality: quality / 100, dpi })
          let s = ''
          for (let i = 0; i < out.bytes.length; i += 1) {
            s += String.fromCharCode(out.bytes[i])
          }
          return { b64: btoa(s), pageCount: out.pageCount }
        },
        { b64: original.toString('base64'), quality, dpi },
      )
      const bytes = Buffer.from(result.b64, 'base64')
      writeFileSync(join(outDir, name), bytes)
      const ratio = original.length / bytes.length
      rows.push({ quality, name, pages: result.pageCount,
                  before: original.length, after: bytes.length, ratio })
      console.log(`  q${quality}  ${name.padEnd(38)} `
        + `${(original.length / 1048576).toFixed(2)} MB → `
        + `${(bytes.length / 1048576).toFixed(2)} MB  (${ratio.toFixed(1)}×)`)
    }
    const arm = rows.filter((r) => r.quality === quality)
    const before = arm.reduce((n, r) => n + r.before, 0)
    const after = arm.reduce((n, r) => n + r.after, 0)
    console.log(`  q${quality}  TOTAL ${(before / 1048576).toFixed(1)} MB → `
      + `${(after / 1048576).toFixed(1)} MB  (${(before / after).toFixed(1)}×)\n`)
  }

  await browser.close()

  const manifest = join(OUT_ROOT, 'corpus.json')
  writeFileSync(manifest, JSON.stringify({
    built_at: new Date().toISOString(),
    dpi,
    encoder: 'chromium canvas.toBlob image/jpeg',
    source_dir: SOURCE_PDFS,
    note: 'Built by frontend/scripts/build-eval-corpus.mjs from '
        + 'src/utils/page-repack.ts — the same module Stage F would ship.',
    rows,
  }, null, 2) + '\n', 'utf8')

  console.log(`Wrote ${rows.length} variant PDFs under ${OUT_ROOT}`)
  console.log(`Manifest: ${manifest}`)
  console.log()
  console.log('NOTHING HAS BEEN MEASURED YET — this step calls no model and spends nothing.')
  console.log('The paid run is, from backend/ (see UPLOAD_LATENCY_PLAN.md §3 Stage E):')
  console.log()
  for (const quality of qualities) {
    const d = `pdfs-variants/jpeg${quality}${dpi === 200 ? '' : `-dpi${dpi}`}`
    console.log(`  python -m tests.transcription_eval_suit.runner --config v0 \\`)
    console.log(`      --mode p1_only --repeats 5 --pdf-dir ${d}`)
  }
  console.log()
  console.log('  # champion arm, for the paired comparison:')
  console.log('  python -m tests.transcription_eval_suit.runner --config v0 \\')
  console.log('      --mode p1_only --repeats 5')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
