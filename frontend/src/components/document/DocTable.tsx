import { Fragment } from 'react';
import { inferGridDir, type NestedTableBlock } from '@/utils/markdown-parser';

/**
 * The document-styled table — hairline borders, muted header — extracted from
 * DocumentText (PR-5 S2) so the transcription-review surface can render the
 * trace tables in a student's answer with the SAME renderer instead of forking
 * a second one (§0.4; the extension path B-16.4 already named).
 *
 * The markup is unchanged from its in-DocumentText original; only the props
 * widened, from a `TableSegment` to the three things a table actually needs.
 * Both defaults reproduce the previous behaviour exactly:
 *   `dir`       → falls back to inferGridDir(rows)
 *   `hasHeader` → falls back to rows.length >= 2
 */

// ── bidi-isolated inline text: wrap Latin/code runs so RTL can't reorder them ──
import { bidiRuns } from '@/utils/document-text';

export function BidiText({ text }: { text: string }) {
    return (
        <>
            {bidiRuns(text).map((run, i) =>
                run.latin
                    ? <bdi key={i} dir="ltr">{run.text}</bdi>
                    : <Fragment key={i}>{run.text}</Fragment>,
            )}
        </>
    );
}

export interface DocTableProps {
    rows: string[][];
    /**
     * The table's OWN direction. CONSERVE THE SOURCE: cells arrive in LOGICAL
     * order, so direction decides which end is column 1. The docx path passes
     * the marker's `dir` token; the transcription path pins `ltr` (its text is
     * already displayed as an LTR island, and a mirrored grid would disagree
     * with the raw text the teacher edits). Omitted ⇒ guessed from content,
     * which is the legacy path the token exists to retire.
     */
    dir?: 'rtl' | 'ltr';
    /**
     * Is row 0 a header? Omitted ⇒ "any table with 2+ rows has one" — a
     * single-row table is a data array (an arr/trace row), never a header.
     * The transcription detector decides this from content and passes it.
     */
    hasHeader?: boolean;
    nestedTables?: NestedTableBlock[];
}

export function DocTable({ rows, dir: dirProp, hasHeader: hasHeaderProp, nestedTables = [] }: DocTableProps) {
    if (rows.length === 0) return null;
    const hasHeader = hasHeaderProp ?? rows.length >= 2;
    const header = hasHeader ? rows[0] : null;
    const dataRows = hasHeader ? rows.slice(1) : rows;
    const dir = dirProp ?? inferGridDir(rows);
    const align = dir === 'rtl' ? 'text-right' : 'text-left';
    return (
        <div className="my-3 overflow-x-auto" dir={dir}>
            <table className="border-collapse text-doc-table w-full">
                {header && <thead><tr>{header.map((c, i) => (
                    <th key={i} className={`border border-surface-200 px-3 py-1.5 text-surface-500 font-medium ${align}`}><BidiText text={c} /></th>
                ))}</tr></thead>}
                <tbody>
                    {dataRows.map((row, ri) => (
                        <tr key={ri}>{row.map((c, ci) => (
                            <td key={ci} className={`border border-surface-200 px-3 py-1.5 text-surface-800 align-top ${align}`}><BidiText text={c} /></td>
                        ))}</tr>
                    ))}
                </tbody>
            </table>
            {nestedTables.length > 0 && (
                <div className="mt-1 space-y-1">
                    {nestedTables.map((nb, i) => (
                        <div key={i} className="text-doc-meta text-surface-500 pr-3">
                            {nb.rows.map((r, ri) => <div key={ri} dir={dir}><BidiText text={r.join(' · ')} /></div>)}
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
