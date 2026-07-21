/**
 * PR-5 S2 D-4 — display-only de-emphasis of a verbatim routing prefix.
 *
 * Extraction sometimes prepends a criterion description with a token that just
 * repeats its scope heading ("סעיף א: כתבו פעולה…"). The mirror mutes that leading
 * token so the eye goes to the actual criterion — but STATE STAYS VERBATIM
 * (round-trip fidelity is untouchable). This runs in RENDER ONLY.
 *
 * Pure and tested. Returns the split so the caller can style the prefix muted and
 * the rest normally; when there is no such prefix, `prefix` is ''.
 */

/** Escape a string for use as a literal inside a RegExp. */
function escapeRegExp(s: string): string {
    return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function splitRoutingPrefix(
    description: string,
    headingLabel: string,
): { prefix: string; rest: string } {
    if (!description || !headingLabel) return { prefix: '', rest: description };
    // The heading at the very start, followed by an optional separator and space.
    const re = new RegExp(`^(\\s*${escapeRegExp(headingLabel)}\\s*[:.\\-–)]\\s*)`);
    const m = re.exec(description);
    if (m && m[1].length < description.length) {
        return { prefix: m[1], rest: description.slice(m[1].length) };
    }
    return { prefix: '', rest: description };
}
