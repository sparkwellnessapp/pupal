import type { Metadata } from 'next'

// The student capture link is never indexed (§8.2) — also X-Robots-Tag in
// next.config.js — and its URL never leaves as a Referer.
export const metadata: Metadata = {
  title: 'צילום מבחן · Vivi',
  robots: { index: false, follow: false },
  referrer: 'no-referrer',
}

export default function StudentCaptureLayout({ children }: { children: React.ReactNode }) {
  return children
}
