import { expect, test } from '@playwright/test';
import { build } from 'esbuild';
import { existsSync, readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';

/**
 * Stage E — the browser transform, exercised in a REAL browser.
 *
 * It has to be Playwright and not vitest: the whole point of this module is
 * that it uses Chromium's own JPEG encoder (Skia), because that is the encoder
 * a teacher would run. jsdom has no canvas and no `toBlob`, so a unit test
 * would either mock the encoder — measuring nothing — or silently exercise a
 * different one.
 *
 * These assertions are about STRUCTURE, not accuracy. Whether the re-encoded
 * pages are good enough for the model is not a question a test can answer; it
 * is what the paid eval (Stage E proper) is for, and ruling R1 says nothing
 * ships until that gate speaks. What is pinned here is everything that would
 * make the eval measure the wrong thing, or make Stage F unshippable:
 *   * the output is a real PDF with the SAME page count and SAME page sizes;
 *   * its pages are JPEG (DCTDecode), because a PDF cannot carry WebP and the
 *     deployed PyMuPDF cannot even read one;
 *   * it is meaningfully smaller — otherwise there is nothing to evaluate;
 *   * a browser that hands back a non-JPEG blob raises instead of quietly
 *     shipping a PNG the server would store believing it had shrunk.
 */

// Playwright compiles specs to CJS, so `import.meta.url` and `createRequire`
// are not available here — resolve from the config's own root instead
// (Playwright runs with cwd = the project root that holds playwright.config.ts).
const ROOT = process.cwd();
const SUITE = resolve(ROOT, '..', 'backend', 'tests', 'transcription_eval_suit');
const FIXTURE = join(SUITE, 'pdfs', 'bagrut_899371.din_ezra.pdf');
const PDFJS = join(ROOT, 'node_modules', 'pdfjs-dist', 'build', 'pdf.min.mjs');
const PDFJS_WORKER = join(ROOT, 'node_modules', 'pdfjs-dist', 'build', 'pdf.worker.min.mjs');

async function bundleTransform(): Promise<string> {
    const out = await build({
        entryPoints: [join(ROOT, 'src', 'utils', 'page-repack.ts')],
        bundle: true, format: 'iife', globalName: 'PageRepack',
        platform: 'browser', write: false, target: 'es2020',
    });
    return out.outputFiles[0].text;
}

async function preparePage(page: import('@playwright/test').Page) {
    // Fail with the path rather than with a confusing browser error.
    for (const p of [FIXTURE, PDFJS, PDFJS_WORKER]) {
        if (!existsSync(p)) throw new Error(`missing: ${p}`);
    }
    const pdfjs = PDFJS;
    const worker = PDFJS_WORKER;
    await page.goto('about:blank');
    await page.addScriptTag({ content: await bundleTransform() });
    await page.addScriptTag({
        content: `${readFileSync(pdfjs, 'utf8')}\nwindow.__pdfjs = pdfjsLib;`,
        type: 'module',
    });
    await page.addScriptTag({
        content: `window.__pdfWorkerSrc = ${JSON.stringify(
            'data:text/javascript;base64,' + readFileSync(worker).toString('base64'))};`,
    });
    await page.waitForFunction('window.__pdfjs && window.PageRepack');
}

/** Run the real transform over the real fixture, inside the real browser. */
async function repack(page: import('@playwright/test').Page, quality: number) {
    const original = readFileSync(FIXTURE);
    const result = await page.evaluate(async ({ b64, quality }) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        (window as any).__pdfjs.GlobalWorkerOptions.workerSrc = (window as any).__pdfWorkerSrc;
        const out = await (window as any).PageRepack.repackPdfToJpegPages(
            (window as any).__pdfjs, bytes, { quality: quality / 100 });
        let s = '';
        for (let i = 0; i < out.bytes.length; i += 1) s += String.fromCharCode(out.bytes[i]);
        return { b64: btoa(s), pageCount: out.pageCount, jpegBytes: out.jpegBytes };
    }, { b64: original.toString('base64'), quality });
    return {
        bytes: Buffer.from(result.b64, 'base64'),
        pageCount: result.pageCount,
        jpegBytes: result.jpegBytes as number[],
        originalBytes: original,
    };
}

test('the repack produces a smaller PDF with the same pages, as JPEG', async ({ page }) => {
    await preparePage(page);
    const out = await repack(page, 90);

    // A real PDF, not a blob with a hopeful name.
    expect(out.bytes.subarray(0, 5).toString('latin1')).toBe('%PDF-');

    // Same document: every page is still there.
    expect(out.pageCount).toBe(7);
    expect(out.jpegBytes).toHaveLength(7);
    expect(Math.min(...out.jpegBytes)).toBeGreaterThan(0);

    // JPEG inside, which is the entire reason this is not WebP: a PDF cannot
    // carry a WebP stream and the deployed PyMuPDF cannot read one, so a
    // WebP-bearing "PDF" would fail on the server, at render time, in prod.
    expect(out.bytes.toString('latin1')).toContain('DCTDecode');

    // There has to be something to evaluate.
    const ratio = out.originalBytes.length / out.bytes.length;
    expect(ratio).toBeGreaterThan(2);
    console.log(`  din_ezra q90: ${(out.originalBytes.length / 1048576).toFixed(2)} MB`
        + ` → ${(out.bytes.length / 1048576).toFixed(2)} MB (${ratio.toFixed(1)}×)`);
});

test('page SIZE is preserved, so the server rasterises the same sheet', async ({ page }) => {
    await preparePage(page);
    const out = await repack(page, 90);

    // The pipeline rasterises the STORED pdf at 200 DPI, and the returned exam
    // stamps page 1 at coordinates computed from the page box. A page that came
    // back a different size would move the stamp and change what the model
    // sees, independently of any pixel difference.
    const sizes = await page.evaluate(async (b64: string) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        (window as any).__pdfjs.GlobalWorkerOptions.workerSrc = (window as any).__pdfWorkerSrc;
        const doc = await (window as any).__pdfjs.getDocument({ data: bytes }).promise;
        const out: Array<[number, number]> = [];
        for (let n = 1; n <= doc.numPages; n += 1) {
            const v = (await doc.getPage(n)).getViewport({ scale: 1 });
            out.push([Math.round(v.width), Math.round(v.height)]);
        }
        return out;
    }, out.bytes.toString('base64'));

    const originalSizes = await page.evaluate(async (b64: string) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        (window as any).__pdfjs.GlobalWorkerOptions.workerSrc = (window as any).__pdfWorkerSrc;
        const doc = await (window as any).__pdfjs.getDocument({ data: bytes }).promise;
        const out: Array<[number, number]> = [];
        for (let n = 1; n <= doc.numPages; n += 1) {
            const v = (await doc.getPage(n)).getViewport({ scale: 1 });
            out.push([Math.round(v.width), Math.round(v.height)]);
        }
        return out;
    }, readFileSync(FIXTURE).toString('base64'));

    expect(sizes).toEqual(originalSizes);
});

test('a higher quality setting yields a larger file — the dial is real', async ({ page }) => {
    await preparePage(page);
    const [q95, q85] = [await repack(page, 95), await repack(page, 85)];
    // If these came out equal the quality argument would not be reaching the
    // encoder, and the eval's three arms would silently be one arm.
    expect(q95.bytes.length).toBeGreaterThan(q85.bytes.length);
});

test('a non-JPEG blob RAISES rather than shipping a PNG in a PDF', async ({ page }) => {
    await preparePage(page);
    // Chromium always honours image/jpeg, so the guard cannot be reached by
    // asking nicely — a browser that lacked JPEG would return PNG silently.
    // Stub `toBlob` to be that browser, and prove we notice.
    const message = await page.evaluate(async (b64: string) => {
        const bin = atob(b64);
        const bytes = new Uint8Array(bin.length);
        for (let i = 0; i < bin.length; i += 1) bytes[i] = bin.charCodeAt(i);
        (window as any).__pdfjs.GlobalWorkerOptions.workerSrc = (window as any).__pdfWorkerSrc;
        const real = HTMLCanvasElement.prototype.toBlob;
        HTMLCanvasElement.prototype.toBlob = function (cb: BlobCallback) {
            cb(new Blob([new Uint8Array([1, 2, 3])], { type: 'image/png' }));
        } as typeof real;
        try {
            await (window as any).PageRepack.repackPdfToJpegPages(
                (window as any).__pdfjs, bytes, { quality: 0.9 });
            return '(no error)';
        } catch (e) {
            return (e as Error).message;
        } finally {
            HTMLCanvasElement.prototype.toBlob = real;
        }
    }, readFileSync(FIXTURE).toString('base64'));

    expect(message).toContain('image/jpeg');
});
