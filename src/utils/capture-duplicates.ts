/**
 * The duplicate submissions of a batch (SCN-13), as the panel's rows carry
 * them. The SERVER derives the groups (`duplicate_group`); this only reads
 * them back for the dialog and decides what each set may offer. Pure.
 */
import type { CaptureSubmissionRow } from '@/types/capture'

/** The rows of one duplicate, oldest set first. Empty when `key` names none. */
export function duplicateRows(rows: readonly CaptureSubmissionRow[], key: string | null): CaptureSubmissionRow[] {
  if (!key) return []
  return rows
    .filter((r) => r.duplicate_group === key)
    .sort((a, b) => (a.saved_at ?? '').localeCompare(b.saved_at ?? ''))
}

/** The group a transcription's set belongs to — the triage card's way in. */
export function groupOfTranscription(rows: readonly CaptureSubmissionRow[],
                                     transcriptionId: string | null): string | null {
  if (!transcriptionId) return null
  return rows.find((r) => r.transcription_id === transcriptionId)?.duplicate_group ?? null
}

/** SCN-14: with an approved set in the group, that set is the only one she
 *  can keep (approved work is never discarded); otherwise any one. */
export function canKeep(group: readonly CaptureSubmissionRow[], row: CaptureSubmissionRow): boolean {
  const approved = group.filter((r) => r.transcription_status === 'approved')
  return approved.length === 0 || approved.some((r) => r.submission_id === row.submission_id)
}

/** What the dialog calls the student: the confirmed name, else what was typed. */
export function claimName(row: CaptureSubmissionRow): string {
  return row.student?.display_name ?? row.pending_student_name ?? ''
}
