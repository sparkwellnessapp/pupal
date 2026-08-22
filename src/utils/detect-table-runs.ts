/**
 * PR-5 Sprint 2 §4 — the mini-table parser. The ONE interpretation site in the
 * mirror: a pure, display-only, side-effect-free function over verbatim question
 * text. It NEVER changes state — `detectTableRuns` is called at render only, and
 * dehydrated output is unaffected.
 *
 * Why it exists: extraction flattens question-embedded DOCX tables to
 * space-joined rows (the "digit soup" — our convention rendering, not a bug). The
 * wire carries no `[TABLE]` markers and adding them is a pipeline variable
 * (rejected). So the mirror re-recognizes table runs heuristically at render time.
 *
 * BIAS TO PRECISION (the load-bearing rule): when unsure, do NOT tableize. The
 * fallback is clean preformatted prose (line-preserved) — honest. A false positive
 * mangles her actual prose — not honest. Every threshold below is tuned to reject
 * ambiguous input rather than gamble.
 *
 * A TABLE RUN is a maximal sequence of ≥2 consecutive non-empty lines that:
 *   - each split (on whitespace) to the SAME number of tokens, ≥2; and
 *   - across the whole run, ≥60% of tokens are numeric-ish (`-?\d+(\.\d+)?`).
 * The "first line may be a header" allowance (§4) is satisfied by an all-textual
 * first row of equal column count (rendered as <thead>). A header of DIFFERENT
 * column count degrades to prose above the table — precision over cleverness.
 *
 * @see PR5_SPRINT2_SPEC_document_mirror.md §4
 */

export type Segment =
    | { kind: 'prose'; text: string }
    | { kind: 'table'; rows: string[][]; hasHeader: boolean };

const NUMERIC_ISH = /^-?\d+(\.\d+)?$/;
const NUMERIC_RATIO_THRESHOLD = 0.6;

function tokensOf(line: string): string[] {
    const t = line.trim();
    return t === '' ? [] : t.split(/\s+/);
}

/** A line that could participate in a table run: non-empty, ≥2 whitespace tokens. */
function isCandidateLine(line: string): boolean {
    return tokensOf(line).length >= 2;
}

function isNumericIsh(token: string): boolean {
    return NUMERIC_ISH.test(token);
}

function numericRatio(rows: string[][]): number {
    let total = 0;
    let numeric = 0;
    for (const row of rows) {
        for (const tok of row) {
            total++;
            if (isNumericIsh(tok)) numeric++;
        }
    }
    return total === 0 ? 0 : numeric / total;
}

/**
 * Segment `text` into an ordered list of prose and table runs. Order is
 * preserved; concatenating the segments' source lines reproduces the input.
 * Pure — safe to call in render.
 */
export function detectTableRuns(text: string): Segment[] {
    if (!text) return [];
    const lines = text.split('\n');
    const segments: Segment[] = [];
    let prose: string[] = [];

    const flushProse = () => {
        if (prose.length > 0) {
            segments.push({ kind: 'prose', text: prose.join('\n') });
            prose = [];
        }
    };

    let i = 0;
    while (i < lines.length) {
        if (isCandidateLine(lines[i])) {
            // Collect the maximal run of consecutive candidate lines with the SAME
            // token count as line i.
            const count = tokensOf(lines[i]).length;
            let j = i;
            while (j < lines.length && isCandidateLine(lines[j]) && tokensOf(lines[j]).length === count) {
                j++;
            }
            const runLines = lines.slice(i, j);
            if (runLines.length >= 2) {
                const rows = runLines.map(tokensOf);
                if (numericRatio(rows) >= NUMERIC_RATIO_THRESHOLD) {
                    // A textual first row of equal column count is a header (§4).
                    const hasHeader = rows.length >= 2 && rows[0].every((t) => !isNumericIsh(t));
                    flushProse();
                    segments.push({ kind: 'table', rows, hasHeader });
                    i = j;
                    continue;
                }
            }
        }
        prose.push(lines[i]);
        i++;
    }

    flushProse();
    return segments;
}
