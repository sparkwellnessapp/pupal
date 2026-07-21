import type { ContextTableData } from '@/types/rubric';
import { detectTableRuns } from '@/utils/detect-table-runs';

/**
 * Document-aesthetic renderers for the mirror (PR-5 S2): hairline borders, no card
 * chrome. These are the mirror's own display components — RubricEditor's inline
 * TraceTablesDisplay/QuestionContextTablesDisplay stay put (they belong to the
 * rollback editor and must not shift visually). All pure/stateless (server-safe).
 *
 * The mini-table renderer consumes `detectTableRuns` (the ONE interpretation site).
 */

const NUMERIC_ISH = /^-?\d+(\.\d+)?$/;
const cellDir = (v: string) => (NUMERIC_ISH.test(v.trim()) ? 'ltr' : undefined);

/** A detected table run → a bordered mini-table. Numeric cells render LTR. */
function MiniTable({ rows, hasHeader }: { rows: string[][]; hasHeader: boolean }) {
    const body = hasHeader ? rows.slice(1) : rows;
    return (
        <div className="my-2 overflow-x-auto">
            <table className="border-collapse text-sm">
                {hasHeader && (
                    <thead>
                        <tr>
                            {rows[0].map((cell, i) => (
                                <th key={i} className="border border-surface-200 px-2 py-1 text-surface-600 font-medium" dir={cellDir(cell)}>
                                    {cell}
                                </th>
                            ))}
                        </tr>
                    </thead>
                )}
                <tbody>
                    {body.map((row, r) => (
                        <tr key={r}>
                            {row.map((cell, c) => (
                                <td key={c} className="border border-surface-200 px-2 py-1 tabular-nums text-surface-800" dir={cellDir(cell)}>
                                    {cell}
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

/**
 * Verbatim question/sub-question prose, table runs re-recognized. Prose segments
 * keep newlines; table runs become mini-tables. The fallback for ambiguous input
 * is honest preformatted text (precision bias — see detect-table-runs.ts).
 */
export function RichBody({ text, dir = 'auto', className = '' }: { text: string; dir?: 'rtl' | 'ltr' | 'auto'; className?: string }) {
    if (!text || !text.trim()) return null;
    const segments = detectTableRuns(text);
    return (
        <div className={`space-y-1 leading-relaxed text-surface-800 ${className}`} dir={dir}>
            {segments.map((seg, i) =>
                seg.kind === 'table'
                    ? <MiniTable key={i} rows={seg.rows} hasHeader={seg.hasHeader} />
                    : <p key={i} className="whitespace-pre-wrap">{seg.text}</p>,
            )}
        </div>
    );
}

/** DOCX trace tables (headers + row objects). */
export function TraceTablesDisplay({
    tables,
}: {
    tables?: Array<{ headers: string[]; rows: Record<string, string>[]; row_count: number }>;
}) {
    if (!tables || tables.length === 0) return null;
    return (
        <div className="my-2 space-y-3">
            {tables.map((t, ti) => (
                <div key={ti} className="overflow-x-auto">
                    <table className="border-collapse text-sm">
                        <thead>
                            <tr>
                                {t.headers.map((h, i) => (
                                    <th key={i} className="border border-surface-200 px-2 py-1 text-surface-600 font-medium" dir="ltr">{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {t.rows.map((row, ri) => (
                                <tr key={ri}>
                                    {t.headers.map((h, ci) => (
                                        <td key={ci} className="border border-surface-200 px-2 py-1 tabular-nums text-surface-800" dir="ltr">{row[h] ?? ''}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            ))}
        </div>
    );
}

/** Context tables (class interfaces, I/O grids) — raw 2D grid, merged cells resolved upstream. */
export function ContextTablesDisplay({ tables }: { tables?: ContextTableData[] }) {
    if (!tables || tables.length === 0) return null;
    return (
        <div className="my-2 space-y-3">
            {tables.map((t, ti) => (
                <div key={ti}>
                    {t.title ? <div className="text-sm text-surface-600 mb-1">{t.title}</div> : null}
                    <div className="overflow-x-auto">
                        <table className="border-collapse text-sm">
                            <tbody>
                                {t.grid.map((row, ri) => (
                                    <tr key={ri}>
                                        {row.map((cell, ci) => (
                                            <td key={ci} className="border border-surface-200 px-2 py-1 text-surface-800" dir={cellDir(cell)}>{cell}</td>
                                        ))}
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ))}
        </div>
    );
}
