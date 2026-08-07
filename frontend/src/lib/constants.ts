/**
 * Named product constants (one definition point each — plan Δ8/Δ15).
 */

/**
 * Δ15: the un-transcribed residue line appears when rows < test_count AND more
 * than this has passed since the LATER of (batch created_at, newest
 * transcription row created_at) — progress-based, so a healthy large batch
 * mid-fan-out never shows a false failure claim; a batch with no new row for
 * this long is genuinely stuck.
 */
export const UNTRANSCRIBED_RESIDUE_HORIZON_MS = 10 * 60 * 1000;
