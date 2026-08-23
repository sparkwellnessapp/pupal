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
  // Launch hygiene (2026-08-24): bake the deployed commit into the bundle so
  // "is production current?" is a five-second answer, not forensics. The
  // frontend drifted 5 weeks with a 422-broken batch flow and nothing said so
  // — and the webpack runtime chunk hash is build-invariant, so hash-diffing
  // the bundle lies. Vercel injects VERCEL_GIT_COMMIT_SHA at build time (the
  // frontend-deployment subtree SHA — compare against
  // `git rev-parse origin/frontend-deployment`).
  env: {
    NEXT_PUBLIC_BUILD_SHA:
      process.env.VERCEL_GIT_COMMIT_SHA || process.env.BUILD_SHA || 'local-dev',
  },
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
