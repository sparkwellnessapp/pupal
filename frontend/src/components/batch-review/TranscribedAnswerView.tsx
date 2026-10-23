'use client';

/**
 * TranscribedAnswerView — one transcribed answer, rendered as the SEGMENTS it is
 * made of: prose runs, and the trace tables the student drew as real tables.
 *
 * Given `onChange` (and not `readOnly`), it is the EDITOR for that answer
 * (native table editing, 2026-09-24): every prose run is a textarea over its own
 * span of the string, and every cell that owns bytes — header row included — is
 * an input over its own span. Read-only, it is the display it always was.
 *
 * THE ANSWER STRING REMAINS THE ONLY TRUTH (TBL-1). The segments are derived
 * from it (`segmentAnswerSpans`); every edit splices exactly its own span and
 * hands the whole string up through `onChange` — the one write path the raw
 * editor uses too (TBL-2, TBL-5). A cell edit the detector would read as a
 * different grid is refused, never repaired (TBL-4, `answer-segments.ts`), and
 * an end-padded cell owns no bytes, so it is shown as absent, not offered (OD-8).
 *
 * VIEWING IS NOT COMMITMENT (TBL-3 = Δ14): focusing, tabbing, Enter, Esc and
 * blur never call `onChange`, so they can never dirty the item or create an
 * overlay — which would silently pull a clean document out of bulk-accept.
 *
 * THE LAYOUT HOLDS STILL WHILE SHE TYPES (OD-5): from the moment focus enters
 * the answer until it leaves, the segmentation is frozen and carried across each
 * splice (`rebaseSegments`). A keystroke that would re-segment the answer — two
 * pipe lines typed into prose, a header cell that stops looking like a header —
 * therefore cannot remount the field under the caret. It re-derives when she
 * leaves. A frozen layout is valid only for the string it was carried to; any
 * other change to the text (SWAP, rehydration) falls back to a fresh derivation.
 *
 * Direction is pinned `ltr` for the grid, deliberately (owner-ruled 2026-08-23):
 * the raw text is an adjudicated LTR island, and a content-guessed mirror would
 * put the grid and the raw text in disagreement about which end is column 1.
 * Each cell is a pure `dir="ltr"` island — never `unicode-bidi: plaintext`,
 * which the standing bidi rule falsified (`rtl-bidi-table-cell` guards it).
 */

import { useEffect, useMemo, useRef, useState, type FocusEvent, type KeyboardEvent } from 'react';

import { DocTable } from '@/components/document/DocTable';
import {
    ANSWER_CELL_ABSENT,
    ANSWER_CELL_HINT_PIPE,
    ANSWER_CELL_HINT_STRUCTURE,
    ANSWER_CELL_LABEL,
    ANSWER_TEXT_RUN_LABEL,
    ANSWER_VIEW_FLAGS_HIDDEN,
} from '@/copy/batch';
import {
    applyCellEdit,
    applyTextRunEdit,
    rebaseSegments,
    segmentAnswerSpans,
    type Span,
    type SpanCell,
    type SpanSegment,
} from '@/utils/answer-segments';
import { resolveCellKey } from '@/utils/table-cell-keymap';

type TableSeg = Extract<SpanSegment, { kind: 'table' }>;
type RealCell = Extract<SpanCell, { virtual: false }>;

/** A prose run's textarea, grown to its content (no inner scroll to lose her place in). */
function TextRunEditor({ value, dir, onChange }: { value: string; dir: 'ltr' | 'rtl'; onChange: (next: string) => void }) {
    const ref = useRef<HTMLTextAreaElement>(null);
    useEffect(() => {
        const el = ref.current;
        if (!el) return;
        el.style.height = 'auto';
        el.style.height = `${el.scrollHeight}px`;
    }, [value]);
    return (
        <textarea
            ref={ref}
            data-testid="answer-text-run"
            aria-label={ANSWER_TEXT_RUN_LABEL}
            dir={dir}
            value={value}
            rows={value.split('\n').length}
            spellCheck={false}
            onChange={(e) => onChange(e.target.value)}
            className="block w-full resize-none overflow-hidden bg-transparent p-0 font-mono text-sm whitespace-pre-wrap break-words text-gray-800 rounded focus:outline-none focus:ring-2 focus:ring-primary-400 focus:bg-white"
        />
    );
}

export function TranscribedAnswerView({
    text,
    flagCount = 0,
    dir = 'ltr',
    onChange,
    readOnly = false,
    onEditingChange,
}: {
    text: string;
    /** >0 ⇒ the marked lines live only in the raw view; say so rather than hide it. */
    flagCount?: number;
    /** Direction of the prose segments, from the rubric's SUBJECT (Phase 3b); the
     *  grid keeps its own owner-ruled `ltr`. Default = today's behaviour. */
    dir?: 'ltr' | 'rtl';
    /** The answer's ONE write path (the surface's commit). Absent ⇒ display only. */
    onChange?: (next: string) => void;
    readOnly?: boolean;
    /** Focus entered (true) / left (false) this answer — the surface holds the
     *  view mode still while she edits, for the same reason the layout holds. */
    onEditingChange?: (editing: boolean) => void;
}) {
    const editable = !!onChange && !readOnly;
    const derived = useMemo(() => segmentAnswerSpans(text), [text]);
    const [frozen, setFrozen] = useState<{ text: string; segments: SpanSegment[] } | null>(null);
    // A refused-but-not-yet-abandoned cell value (OD-4b): shown, never written.
    const [held, setHeld] = useState<{ id: string; value: string } | null>(null);
    const [hint, setHint] = useState<{ seg: number; message: string } | null>(null);
    const rootRef = useRef<HTMLDivElement>(null);

    const segments = frozen && frozen.text === text ? frozen.segments : derived;

    const commit = (nextText: string, edit: { start: number; oldEnd: number; newEnd: number }) => {
        if (nextText === text || !onChange) return;          // TBL-3: no bytes, no write
        setFrozen({ text: nextText, segments: rebaseSegments(segments, nextText, edit) });
        onChange(nextText);
    };

    const onRootFocus = () => {
        if (!editable) return;
        if (!(frozen && frozen.text === text)) setFrozen({ text, segments: derived });
        onEditingChange?.(true);
    };
    const onRootBlur = (e: FocusEvent<HTMLDivElement>) => {
        if (!editable) return;
        if (rootRef.current?.contains(e.relatedTarget as Node | null)) return;
        setFrozen(null);
        setHeld(null);
        setHint(null);
        onEditingChange?.(false);
    };

    const onCellInput = (segIdx: number, id: string, cell: RealCell, value: string) => {
        const res = applyCellEdit(text, cell, value);
        if (res.ok) {
            if (held) setHeld(null);
            if (hint) setHint(null);
            commit(res.text, { start: cell.start, oldEnd: cell.end, newEnd: cell.start + value.length });
            return;
        }
        if (res.reason === 'structure') {
            // Shown so she sees what she typed, never committed; leaving the cell
            // drops it and the last good value stands.
            setHeld({ id, value });
            setHint({ seg: segIdx, message: ANSWER_CELL_HINT_STRUCTURE });
            return;
        }
        setHint({ seg: segIdx, message: res.reason === 'pipe' ? ANSWER_CELL_HINT_PIPE : ANSWER_CELL_HINT_STRUCTURE });
    };

    const onCellKey = (e: KeyboardEvent<HTMLInputElement>, seg: TableSeg, segIdx: number, row: number, col: number) => {
        if (e.key === '|') {
            e.preventDefault();
            setHint({ seg: segIdx, message: ANSWER_CELL_HINT_PIPE });
            return;
        }
        const action = resolveCellKey(
            { key: e.key, shiftKey: e.shiftKey, ctrlOrMeta: e.ctrlKey || e.metaKey, isComposing: e.nativeEvent.isComposing },
            { row, col },
            seg.rows.map((r) => r.map((c) => !c.virtual)),
        );
        if (!action) return;
        e.preventDefault();
        if (action.kind === 'focus') {
            const next = rootRef.current?.querySelector<HTMLInputElement>(
                `[data-seg="${segIdx}"][data-row="${action.row}"][data-col="${action.col}"]`,
            );
            next?.focus();
            next?.select();
        } else if (action.kind === 'leave') {
            rootRef.current?.focus();
        }
    };

    const renderCell = (seg: TableSeg, segIdx: number) => (_text: string, row: number, col: number) => {
        const cell = seg.rows[row][col];
        if (cell.virtual) {
            return (
                <span
                    data-testid="answer-cell-absent"
                    title={ANSWER_CELL_ABSENT}
                    aria-label={ANSWER_CELL_ABSENT}
                    className="block min-h-[1.25rem] min-w-[1.5rem] rounded-sm bg-[repeating-linear-gradient(135deg,transparent_0_4px,rgba(0,0,0,0.07)_4px_5px)]"
                />
            );
        }
        const id = `${segIdx}:${row}:${col}`;
        const value = held?.id === id ? held.value : cell.text;
        return (
            // The sizer shares the input's grid slot so the column is as wide as
            // its content — and, measured, is where the bidi guard reads glyphs.
            <span className="grid">
                <span data-cell-sizer aria-hidden="true" dir="ltr" className="invisible whitespace-pre px-0.5 [grid-area:1/1]">
                    {value || ' '}
                </span>
                <input
                    type="text"
                    data-testid="answer-cell"
                    data-seg={segIdx}
                    data-row={row}
                    data-col={col}
                    dir="ltr"
                    value={value}
                    aria-label={ANSWER_CELL_LABEL(row + 1, col + 1)}
                    spellCheck={false}
                    autoComplete="off"
                    onChange={(e) => onCellInput(segIdx, id, cell, e.target.value)}
                    onKeyDown={(e) => onCellKey(e, seg, segIdx, row, col)}
                    onBlur={() => {
                        if (held?.id === id) setHeld(null);
                        setHint(null);
                    }}
                    className="w-full min-w-0 rounded-sm bg-transparent px-0.5 [grid-area:1/1] focus:bg-white focus:outline-none focus:ring-2 focus:ring-primary-400"
                />
            </span>
        );
    };

    const ordinals = { text: 0, table: 0 };
    return (
        <div
            data-testid="transcribed-answer-view"
            ref={rootRef}
            tabIndex={editable ? -1 : undefined}
            onFocus={onRootFocus}
            onBlur={onRootBlur}
            className="outline-none"
        >
            {flagCount > 0 && (
                <div className="mb-2 text-xs text-amber-700" dir="rtl">
                    {ANSWER_VIEW_FLAGS_HIDDEN}
                </div>
            )}
            <div
                dir={dir}
                className="w-full p-3 rounded-lg border border-surface-300 bg-surface-50"
            >
                {segments.map((seg, i) => {
                    const key = `${seg.kind}-${ordinals[seg.kind]++}`;
                    if (seg.kind === 'table') {
                        return (
                            <div key={key}>
                                <DocTable
                                    rows={seg.rows.map((r) => r.map((c) => c.text))}
                                    hasHeader={seg.hasHeader}
                                    dir="ltr"
                                    renderCell={editable ? renderCell(seg, i) : undefined}
                                />
                                {editable && hint?.seg === i && (
                                    <div data-testid="answer-cell-hint" role="status" dir="rtl" className="-mt-2 mb-2 text-xs text-amber-700">
                                        {hint.message}
                                    </div>
                                )}
                            </div>
                        );
                    }
                    // Blank lines around a table are layout, not content — the grid
                    // supplies its own; a blank-only run renders nothing.
                    if (!seg.body) return null;
                    const body: Span = seg.body;
                    const value = text.slice(body.start, body.end);
                    if (!editable) {
                        if (!value.trim()) return null;
                        return (
                            // Monospace + pre-wrap so switching modes does not reflow her
                            // text: this is visually the textarea, minus the caret.
                            <pre key={key} className="font-mono text-sm whitespace-pre-wrap break-words text-gray-800">
                                {value}
                            </pre>
                        );
                    }
                    return (
                        <TextRunEditor
                            key={key}
                            dir={dir}
                            value={value}
                            onChange={(next) => commit(
                                applyTextRunEdit(text, body, next),
                                { start: body.start, oldEnd: body.end, newEnd: body.start + next.length },
                            )}
                        />
                    );
                })}
            </div>
        </div>
    );
}
