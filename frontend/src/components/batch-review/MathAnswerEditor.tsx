'use client';

/**
 * A math answer at the transcription gate: typeset, and edited where she points
 * (MATH_RENDERING_PLAN §4, "Editing"; OD-M6).
 *
 *   click a FORMULA   → that formula opens in a MathLive field. She edits the expression,
 *                       never its LaTeX.
 *   click a LINE      → that line opens as text (Hebrew words, a mis-split line). Its
 *                       formulas show as source there; it is the escape hatch, not the
 *                       main path.
 *   a TABLE           → typeset grid; its formulas open in MathLive like any other, and
 *                       «עריכת טקסט» under it opens the table's rows as text.
 *
 * THE ANSWER STRING STAYS THE ONLY TRUTH (TBL-1's rule, kept here): every edit splices
 * exactly its own byte range and hands the whole string up through `onChange` — the same
 * one write path the text editor and the table view use. VIEWING IS NOT COMMITMENT (Δ14):
 * opening and closing anything without a change never calls `onChange`.
 *
 * ONE VIEW PER ANSWER, decided by content (owner ruling 2026-09-27): the surface shows this
 * editor for an answer under a math-notation subject that carries spans. There is no
 * global toggle; the line editor is a per-line affordance.
 *
 * ⚠ SPIKE STATUS (plan §4): the mechanics here are the plan's spike. A teacher tries it
 * before the LaTeX variant is switched on in production.
 */
import { useMemo, useRef, useEffect, useState, type ReactNode } from 'react';

import { DocTable } from '@/components/document/DocTable';
import { MathSpanEditor } from '@/components/math/MathSpanEditor';
import { MathText } from '@/components/math/MathText';
import { MATH_EDIT_CANCEL, MATH_EDIT_HINT, MATH_EDIT_RAW, MATH_EDIT_SAVE, MATH_EDIT_SPAN_LABEL } from '@/copy/math';
import { segmentAnswerSpans } from '@/utils/answer-segments';
import { splitMath } from '@/utils/math-spans';
import type { ReviewLineFlag } from '@/utils/review-flags';

type Range = { start: number; end: number };

/** Every line of a text run, with its absolute offsets. */
function linesOf(text: string, from: number, to: number): Range[] {
    const out: Range[] = [];
    let at = from;
    while (at <= to) {
        const nl = text.indexOf('\n', at);
        const end = nl === -1 || nl > to ? to : nl;
        out.push({ start: at, end });
        if (end >= to) break;
        at = end + 1;
    }
    return out;
}

/** The absolute body range of span `index` inside `unit`, a slice of the answer. */
function spanBody(text: string, unit: Range, index: number): Range | null {
    const spans = splitMath(text.slice(unit.start, unit.end)).segments.filter((s) => s.kind === 'math');
    const seg = spans[index];
    return seg ? { start: unit.start + seg.bodyStart, end: unit.start + seg.bodyEnd } : null;
}

function lineNumberAt(text: string, offset: number): number {
    let n = 1;
    for (let i = 0; i < offset; i += 1) if (text[i] === '\n') n += 1;
    return n;
}

function TextBlockEditor({ value, onCommit, onCancel }: {
    value: string; onCommit: (next: string) => void; onCancel: () => void;
}) {
    const [draft, setDraft] = useState(value);
    const ref = useRef<HTMLTextAreaElement>(null);
    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        el.focus();
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
    }, [draft]);
    return (
        <span className="block" data-testid="math-line-editor">
            <textarea
                ref={ref}
                dir="rtl"
                value={draft}
                spellCheck={false}
                rows={Math.max(1, draft.split('\n').length)}
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                    if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); onCommit(draft); }
                }}
                className="block w-full resize-none overflow-hidden rounded border border-primary-300 bg-white p-1.5 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-primary-400"
            />
            <span className="mt-1 flex gap-1.5">
                <button
                    type="button"
                    data-testid="math-line-save"
                    onClick={() => onCommit(draft)}
                    className="rounded bg-primary-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-primary-700"
                >
                    {MATH_EDIT_SAVE}
                </button>
                <button type="button" onClick={onCancel} className="rounded px-2 py-0.5 text-xs text-gray-600 hover:bg-surface-100">
                    {MATH_EDIT_CANCEL}
                </button>
            </span>
        </span>
    );
}

export function MathAnswerEditor({ value, onChange, readOnly = false, lineFlags = [] }: {
    value: string;
    onChange: (next: string) => void;
    readOnly?: boolean;
    lineFlags?: ReviewLineFlag[];
}) {
    const editable = !readOnly;
    const segments = useMemo(() => segmentAnswerSpans(value), [value]);
    const [openSpan, setOpenSpan] = useState<Range | null>(null);
    const [openBlock, setOpenBlock] = useState<Range | null>(null);
    const flagged = useMemo(() => new Map(lineFlags.map((f) => [f.line, f.reason])), [lineFlags]);

    // Any change to the string from outside (SWAP, rehydration) closes what was open:
    // its offsets belong to the old string.
    useEffect(() => { setOpenSpan(null); setOpenBlock(null); }, [value]);

    const splice = (range: Range, next: string) => {
        const text = value.slice(0, range.start) + next + value.slice(range.end);
        setOpenSpan(null);
        setOpenBlock(null);
        if (text !== value) onChange(text);                       // Δ14: no bytes, no write
    };

    const openFormula = (unit: Range) => (index: number) => {
        const body = spanBody(value, unit, index);
        if (body) { setOpenBlock(null); setOpenSpan(body); }
    };

    /** The open span editor, if it belongs to `unit`; MathText draws it in place. */
    const editorFor = (unit: Range): { index: number; node: ReactNode } | undefined => {
        if (!openSpan || openSpan.start < unit.start || openSpan.end > unit.end) return undefined;
        const spans = splitMath(value.slice(unit.start, unit.end)).segments.filter((s) => s.kind === 'math');
        const index = spans.findIndex((s) => unit.start + s.bodyStart === openSpan.start);
        if (index === -1) return undefined;
        return {
            index,
            node: (
                <MathSpanEditor
                    body={value.slice(openSpan.start, openSpan.end)}
                    onSave={(latex) => splice(openSpan, latex)}
                    onCancel={() => setOpenSpan(null)}
                />
            ),
        };
    };

    const renderLine = (line: Range) => {
        if (openBlock && openBlock.start === line.start && openBlock.end === line.end) {
            return (
                <TextBlockEditor
                    key={`l${line.start}`}
                    value={value.slice(line.start, line.end)}
                    onCommit={(next) => splice(line, next)}
                    onCancel={() => setOpenBlock(null)}
                />
            );
        }
        const reason = flagged.get(lineNumberAt(value, line.start));
        const text = value.slice(line.start, line.end);
        return (
            <div
                key={`l${line.start}`}
                data-math-line=""
                title={reason}
                onClick={editable ? () => { setOpenSpan(null); setOpenBlock(line); } : undefined}
                className={[
                    'min-h-[1.6em] rounded px-1 py-0.5',
                    reason ? 'bg-red-100/70 border-s-4 border-red-400' : '',
                    editable ? 'cursor-text hover:bg-surface-100' : '',
                ].join(' ')}
            >
                {text ? (
                    <MathText
                        text={text}
                        onSpanClick={editable ? openFormula(line) : undefined}
                        spanLabel={MATH_EDIT_SPAN_LABEL}
                        replaceSpan={editorFor(line)}
                    />
                ) : ' '}
            </div>
        );
    };

    return (
        <div data-testid="math-answer-editor" className="w-full rounded-lg border border-surface-300 bg-surface-50 p-3">
            {editable && <div dir="rtl" className="mb-1.5 text-xs text-gray-500">{MATH_EDIT_HINT}</div>}
            <div dir="rtl" className="text-[15px] leading-relaxed text-gray-800">
                {segments.map((seg) => {
                    if (seg.kind === 'text') {
                        if (!seg.body) return null;
                        return linesOf(value, seg.body.start, seg.body.end).map(renderLine);
                    }
                    const tableRange = { start: seg.start, end: seg.end };
                    if (openBlock && openBlock.start === seg.start && openBlock.end === seg.end) {
                        return (
                            <TextBlockEditor
                                key={`t${seg.start}`}
                                value={value.slice(seg.start, seg.end)}
                                onCommit={(next) => splice(tableRange, next)}
                                onCancel={() => setOpenBlock(null)}
                            />
                        );
                    }
                    return (
                        <div key={`t${seg.start}`} data-math-table="">
                            <DocTable
                                rows={seg.rows.map((r) => r.map((c) => c.text))}
                                hasHeader={seg.hasHeader}
                                dir="ltr"
                                renderCell={(_t, row, col) => {
                                    const cell = seg.rows[row][col];
                                    if (cell.virtual || !cell.text) return null;
                                    const unit = { start: cell.start, end: cell.end };
                                    return (
                                        <span dir="rtl">
                                            <MathText
                                                text={cell.text}
                                                onSpanClick={editable ? openFormula(unit) : undefined}
                                                spanLabel={MATH_EDIT_SPAN_LABEL}
                                                replaceSpan={editorFor(unit)}
                                            />
                                        </span>
                                    );
                                }}
                            />
                            {editable && (
                                <button
                                    type="button"
                                    onClick={() => { setOpenSpan(null); setOpenBlock(tableRange); }}
                                    className="-mt-2 mb-2 text-xs text-primary-700 underline underline-offset-2"
                                >
                                    {MATH_EDIT_RAW}
                                </button>
                            )}
                        </div>
                    );
                })}
            </div>
        </div>
    );
}
