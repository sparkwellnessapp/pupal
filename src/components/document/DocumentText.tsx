import { Fragment, type ReactNode } from 'react';
import { ImageOff } from 'lucide-react';
import { parseMarkdownText, inferGridDir, type TableSegment } from '@/utils/markdown-parser';
import { detectTableRuns } from '@/utils/detect-table-runs';
import { stripColorMarkers, groupTextBlocks, bidiRuns, looksLikeCode } from '@/utils/document-text';
import { CodeBlock } from './CodeBlock';

/**
 * DocumentText — the mirror's verbatim-text renderer (Design Recovery Phase 2).
 *
 * Pipeline (each stage pure + tested in document-text.ts / markdown-parser.ts):
 *   1. strip [[color]] markers (color discipline: no teacher red bleeding in)
 *   2. parseMarkdownText → consume [TABLE N: RxC] + pipe rows as real tables
 *   3. within text segments: group code runs → ONE LTR CodeBlock; [IMAGE] → a
 *      placeholder; prose → detectTableRuns fallback (unmarked numeric grids) +
 *      bidi-isolated paragraphs (Latin runs in <bdi> so RTL doesn't mangle code).
 * ZERO raw markers survive; code reads as code; "Check(arr, 6)" reads correctly.
 */

const NUMERIC_ISH = /^-?\d+(\.\d+)?$/;

// ── bidi-isolated inline text: wrap Latin/code runs so RTL can't reorder them ──
function BidiText({ text }: { text: string }) {
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

// ── prose: paragraphs (blank-line separated), single newlines → <br> ──
function Prose({ text }: { text: string }) {
    const paragraphs = text.split(/\n{2,}/).filter((p) => p.trim());
    return (
        <>
            {paragraphs.map((para, pi) => (
                <p key={pi} dir="auto" className="text-doc-body text-surface-800" style={{ unicodeBidi: 'plaintext' }}>
                    {para.split('\n').map((line, li, arr) => (
                        <Fragment key={li}>
                            <BidiText text={line} />
                            {li < arr.length - 1 && <br />}
                        </Fragment>
                    ))}
                </p>
            ))}
        </>
    );
}

// ── unmarked numeric grid (detectTableRuns fallback) ──
function MiniTable({ rows, hasHeader }: { rows: string[][]; hasHeader: boolean }) {
    const body = hasHeader ? rows.slice(1) : rows;
    const cellDir = (v: string) => (NUMERIC_ISH.test(v.trim()) ? 'ltr' : undefined);
    return (
        <div className="my-3 overflow-x-auto">
            <table className="border-collapse text-doc-table">
                {hasHeader && (
                    <thead><tr>{rows[0].map((c, i) => (
                        <th key={i} className="border border-surface-200 px-3 py-1.5 text-surface-500 font-medium" dir={cellDir(c)}>{c}</th>
                    ))}</tr></thead>
                )}
                <tbody>{body.map((row, r) => (
                    <tr key={r}>{row.map((c, ci) => (
                        <td key={ci} className="border border-surface-200 px-3 py-1.5 tabular-nums text-surface-800" dir={cellDir(c)}>{c}</td>
                    ))}</tr>
                ))}</tbody>
            </table>
        </div>
    );
}

// ── marked table (parseMarkdownText) → document-styled, hairline, muted header ──
function DocTable({ segment }: { segment: TableSegment }) {
    const { rows, nestedTables } = segment;
    if (rows.length === 0) return null;
    // A single-row table is a data array (e.g. [TABLE N: 1xC] — an arr/trace row):
    // its one row is DATA, not a header. A header needs at least one data row
    // beneath it to be one. Render 1-row tables as a body row, no <thead>.
    const hasHeader = rows.length >= 2;
    const header = hasHeader ? rows[0] : null;
    const dataRows = hasHeader ? rows.slice(1) : rows;
    // CONSERVE THE SOURCE. Cells arrive in LOGICAL order, so direction decides
    // which end is column 1 — and the document already told us (`bidiVisual` →
    // the marker's dir token). Only fall back to guessing from content for legacy
    // markers that carry no token: guessing mirrored 16 tables across the
    // fixtures, in BOTH directions (an RTL row of digits, and an LTR table that
    // merely contained Hebrew).
    const dir = segment.dir ?? inferGridDir(rows);
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

function ImagePlaceholder({ name }: { name: string }) {
    return (
        <div className="my-3 inline-flex items-center gap-2 text-doc-meta text-surface-400 border border-dashed border-surface-300 rounded-md px-3 py-1.5" dir="rtl">
            <ImageOff size={14} className="flex-shrink-0" />
            <span>תמונה בלתי-קריאה{name && name !== 'תמונה' ? <> · <bdi dir="ltr">{name}</bdi></> : null}</span>
        </div>
    );
}

// ── a text segment: code runs, images, prose (with unmarked-table fallback) ──
function TextSegment({ text }: { text: string }) {
    const blocks = groupTextBlocks(text);
    return (
        <>
            {blocks.map((block, bi) => {
                if (block.kind === 'code') return <CodeBlock key={bi} code={block.text} />;
                if (block.kind === 'image') return <ImagePlaceholder key={bi} name={block.name} />;
                // prose: fall back to detectTableRuns for UNMARKED numeric grids.
                const segs = detectTableRuns(block.text);
                return (
                    <Fragment key={bi}>
                        {segs.map((s, si) =>
                            s.kind === 'table'
                                ? <MiniTable key={si} rows={s.rows} hasHeader={s.hasHeader} />
                                : <Prose key={si} text={s.text} />,
                        )}
                    </Fragment>
                );
            })}
        </>
    );
}

/**
 * SolutionBody — the ONE renderer for every `example_solution`, so the answer key
 * looks the same wherever it appears (it used to split: table-bearing solutions
 * rendered as bare document text, code ones as a card, so some had a grey surface
 * and some didn't).
 *
 * One grey box, tied to the "פתרון לדוגמה" disclosure above it by proximity and a
 * start-edge rule. Inside, each segment is routed by what it IS:
 *
 *   - TABLE  → the document table, keeping its OWN content-inferred direction (a
 *              Hebrew trace table stays RTL, matching the column order in her
 *              Word file). The surrounding RTL must not leak into it, and a wide
 *              grid may scroll inside its own box — a table cannot reflow.
 *   - CODE   → one LTR block that WRAPS. Block-level detection (`looksLikeCode`)
 *              keeps Hebrew `//` comments inside the code instead of splitting
 *              the program into alternating islands.
 *   - PROSE  → RTL-aware paragraphs (`Prose`: dir=auto + unicode-bidi:plaintext +
 *              per-run <bdi>), so a Hebrew or mixed Hebrew/English answer reads
 *              right-to-left with its Latin identifiers intact.
 *
 * Nothing here scrolls horizontally except a table: text grows downward instead.
 */
export function SolutionBody({ text, className = '' }: { text: string; className?: string }) {
    if (!text || !text.trim()) return null;
    const segments = parseMarkdownText(stripColorMarkers(text));
    return (
        <div
            dir="rtl"
            className={`rounded-lg bg-surface-50 border border-surface-200 border-r-2 border-r-surface-300 px-4 py-3 space-y-2 ${className}`}
        >
            {segments.map((seg, i) =>
                seg.type === 'table'
                    ? <DocTable key={i} segment={seg} />
                    : looksLikeCode(seg.content)
                        ? <CodeBlock key={i} code={seg.content} wrap bare />
                        : <Prose key={i} text={seg.content} />,
            )}
        </div>
    );
}

export function DocumentText({ text, className = '' }: { text: string; className?: string }) {
    if (!text || !text.trim()) return null;
    const segments = parseMarkdownText(stripColorMarkers(text));
    return (
        <div className={`space-y-2 ${className}`} dir="rtl">
            {segments.map((seg, i) => {
                if (seg.type !== 'table') return <TextSegment key={i} text={seg.content} />;
                // A 1×1 table is a single-cell container (code/prose the renderer wrapped),
                // not a grid — render its cell as a text segment, never a bordered table.
                if (seg.rows.length === 1 && (seg.rows[0]?.length ?? 0) <= 1) {
                    return <TextSegment key={i} text={seg.rows[0]?.[0] ?? ''} />;
                }
                return <DocTable key={i} segment={seg} />;
            })}
        </div>
    );
}
