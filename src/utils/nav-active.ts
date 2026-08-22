/**
 * P5/L2 — sidebar active-state, pure.
 *
 * Section entries (`/batches`) must stay lit across their descendants
 * (`/batches/{id}`, `/batches/{id}/review/{tx}`); the old strict equality went
 * dark the moment the teacher opened a batch. `/` is special-cased to exact —
 * under a prefix rule Home would light on every page. The boundary is a PATH
 * SEPARATOR, never a character prefix, so `/batches-archive` never lights
 * `/batches`.
 */
export function isNavActive(href: string, pathname: string): boolean {
  if (href === '/') return pathname === '/'
  if (pathname === href) return true
  return pathname.startsWith(`${href}/`)
}
