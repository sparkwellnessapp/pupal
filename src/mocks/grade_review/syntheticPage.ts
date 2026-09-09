/**
 * A visibly SYNTHETIC page image for the mock and e2e routes.
 *
 * WHY THIS EXISTS RATHER THAN A REFUSAL — an owner amendment (2026-09-02) to
 * `registry.ts`'s "a pending fixture refuses, it does not get a plausible
 * payload invented for it". That rule governs **wire shapes**: never let a
 * surface be built against a payload nobody agreed to. An image is **content,
 * not shape**, and the shape here is fully specified — WebP bytes at
 * `/api/v0/transcriptions/{id}/pages/1/image`. Two things follow:
 *
 *   * refusing would mean F1's Pile can never be screenshotted with images,
 *     which defeats the visual review gate;
 *   * the fixtures cannot carry real bytes regardless — they would be named
 *     students' exam scans.
 *
 * WHY IT MUST LOOK FAKE. A screenshot review must not be able to pass believing
 * it saw real output. So this draws seeded pseudo-handwriting — grey strokes on
 * an empty page, the same device the mockup uses (`sqSvg`) — and stamps
 * "דוגמה סינתטית" across it. It is unmistakable for a scan at any zoom.
 *
 * Deterministic in the seed, so a screenshot diff is stable across runs.
 */

/** Mulberry32 — small, seeded, and identical in every browser and in Node. */
function rng(seed: number): () => number {
    let a = seed + 0x6d2b79f5;
    return () => {
        a |= 0;
        a = (a + 0x6d2b79f5) | 0;
        let t = Math.imul(a ^ (a >>> 15), 1 | a);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}

export const SYNTHETIC_LABEL = 'דוגמה סינתטית';

/**
 * @param seed  any stable per-card number (e.g. a hash of the transcription id)
 * @returns an SVG document string, 600x849 — the same 1:1.415 the real
 *          `600x72@110` thumbnail has, so layout work against it is honest even
 *          though the pixels are not.
 */
export function syntheticPageSvg(seed = 0): string {
    const r = rng(seed);
    const lines: string[] = [];
    let y = 90;
    for (let i = 0; i < 26; i++) {
        const len = 150 + r() * 320;
        const x0 = 60 + (r() < 0.4 ? 0 : 40) + (r() < 0.25 ? 40 : 0);
        let d = `M${x0.toFixed(1)} ${y.toFixed(1)}`;
        for (let k = 0; k < len / 18; k++) {
            d += ` q9 ${((r() - 0.5) * 9).toFixed(1)} 18 0`;
        }
        lines.push(`<path d="${d}"/>`);
        y += 26;
        if (i === 3 || i === 14) y += 18;
    }
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 849" width="600" height="849"',
        ` role="img" aria-label="${SYNTHETIC_LABEL}">`,
        '<rect width="600" height="849" fill="#ffffff"/>',
        '<g fill="none" stroke="#B9BABF" stroke-width="2.2" stroke-linecap="round">',
        lines.join(''),
        '</g>',
        // The label is what stops a screenshot review passing on a fake.
        '<text x="300" y="440" text-anchor="middle" transform="rotate(-24 300 440)"',
        ' font-family="system-ui, sans-serif" font-size="52" font-weight="700"',
        ` fill="#C8102E" fill-opacity="0.16">${SYNTHETIC_LABEL}</text>`,
        '</svg>',
    ].join('');
}

/** As a `Response` body. SVG, not WebP: the route's CONTRACT is "an image the
 *  browser can render", and encoding WebP in a mock would need a canvas the
 *  test environment may not have. The mock is honest about being a mock. */
export function syntheticPageResponse(seed = 0): Response {
    return new Response(syntheticPageSvg(seed), {
        status: 200,
        headers: {
            'Content-Type': 'image/svg+xml',
            // Mirrors the real route's unpinned answer, never its year-long
            // `immutable` — a mock must not train the browser to hold a fake.
            'Cache-Control': 'private, max-age=60',
            'X-Vivi-Synthetic': 'page-image',
        },
    });
}
