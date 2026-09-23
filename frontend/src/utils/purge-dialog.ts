/**
 * The Delete dialog's two rules (Part B §15, §16.2) — pure, so they are pinned
 * without a browser.
 *
 *  - The CASE comes from the server's preview, never from the client's own
 *    count: drafts and scans can exist with zero signed tests, and only the
 *    server's plan knows.
 *  - M-B3: whenever anything attributable exists, deletion needs her FULL NAME
 *    typed — the trimmed input equal to `full_name`. An irreversible deletion of
 *    a minor's work deserves more than a click. A grade in flight disables it
 *    outright (PRV-5): the server would refuse anyway.
 */

export type PurgeCase = 'signed_tests' | 'data_only' | 'nothing';

export function needsTypedName(purgeCase: PurgeCase): boolean {
    return purgeCase !== 'nothing';
}

export function canConfirmPurge(
    purgeCase: PurgeCase,
    typed: string,
    fullName: string,
    blockers: number,
): boolean {
    if (blockers > 0) return false;
    if (!needsTypedName(purgeCase)) return true;
    return typed.trim() === fullName.trim() && fullName.trim() !== '';
}
