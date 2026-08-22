/** @type {import('next').NextConfig} */
const nextConfig = {
  // Shared-.next hazard, third occurrence (2026-08-22, this time against the
  // OWNER'S live session): the user's `next dev` (:3000), the Playwright
  // harness's own `next dev` (:3100) and the F1 prod-verify `next start`
  // all read/wrote ONE .next/. Two writers corrupt the third's chunk
  // manifest: the running server then 404s lazily-compiled routes
  // (layout.js/page.js under /_next/static/chunks) and the page hangs on
  // loading forever — a symptom pointing nowhere near the cause. Each
  // consumer now gets its own dist dir via NEXT_DIST_DIR:
  //   user dev            → .next        (default, untouched by tooling)
  //   Playwright e2e dev  → .next-e2e    (set by playwright.config.ts)
  //   prod-verify build   → .next-prod   (set by the F1 flow)
  distDir: process.env.NEXT_DIST_DIR || '.next',
  // Allow images from any domain for PDF thumbnails
  images: {
    remotePatterns: [
      {
        protocol: 'http',
        hostname: 'localhost',
      },
    ],
  },
}

module.exports = nextConfig
