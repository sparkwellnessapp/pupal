import { Fragment, type ReactNode } from 'react';
import { ImageOff } from 'lucide-react';
import { parseMarkdownText, inferGridDir, type TableSegment } from '@/utils/markdown-parser';
import { detectTableRuns } from '@/utils/detect-table-runs';
import { stripColorMarkers, groupTextBlocks, bidiRuns } from '@/utils/document-text';
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
    const header = rows[0];
    const dataRows = rows.slice(1);
    const dir = inferGridDir(rows);
    const align = dir === 'rtl' ? 'text-right' : 'text-left';
    return (
        <div className="my-3 overflow-x-auto" dir={dir}>
            <table className="border-collapse text-doc-table w-full">
                <thead><tr>{header.map((c, i) => (
                    <th key={i} className={`border border-surface-200 px-3 py-1.5 text-surface-500 font-medium ${align}`}><BidiText text={c} /></th>
                ))}</tr></thead>
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

export function DocumentText({ text, className = '' }: { text: string; className?: string }) {
    if (!text || !text.trim()) return null;
    const segments = parseMarkdownText(stripColorMarkers(text));
    return (
        <div className={`space-y-2 ${className}`} dir="rtl">
            {segments.map((seg, i) =>
                seg.type === 'table'
                    ? <DocTable key={i} segment={seg} />
                    : <TextSegment key={i} text={seg.content} />,
            )}
        </div>
    );
}
