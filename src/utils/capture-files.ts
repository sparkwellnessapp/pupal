/**
 * Photo files for capture — pure.
 *
 * D15: a desktop multi-select is ordered by `lastModified`, then by file name
 * (numeric-aware), because photos copied off a phone keep their capture time.
 * She can reorder afterwards.
 *
 * The accepted types are the four the server signs for. A HEIC from a phone
 * often arrives with an EMPTY `type`, so the extension decides then; anything
 * else is refused before an upload URL is requested.
 */
import type { CaptureContentType } from '@/types/capture'

export const ACCEPT_ATTR = 'image/jpeg,image/png,image/heic,image/heif'
/** The server's silent cap (R2, `capture_max_file_bytes`): checked here first,
 *  so an oversized photo is named at once instead of failing at the PUT. */
export const MAX_FILE_BYTES = 52_428_800

const BY_EXTENSION: Record<string, CaptureContentType> = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', heic: 'image/heic', heif: 'image/heif',
}
const ACCEPTED = new Set<string>(Object.values(BY_EXTENSION))

export function contentTypeOf(file: { name: string; type: string }): CaptureContentType | null {
  if (ACCEPTED.has(file.type)) return file.type as CaptureContentType
  const ext = file.name.split('.').pop()?.toLowerCase() ?? ''
  return BY_EXTENSION[ext] ?? null
}

export function orderFiles<T extends { name: string; lastModified: number }>(files: readonly T[]): T[] {
  return [...files].sort((a, b) =>
    a.lastModified - b.lastModified || a.name.localeCompare(b.name, undefined, { numeric: true }))
}
