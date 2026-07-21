'use client';

import { useEffect, useRef, useState, type ReactNode } from 'react';

/**
 * EditableText (PR-5 S2) — typography-first inline editing.
 *
 * At rest it renders as document text: no input box, no chrome. The edit
 * affordance (underline hint, focus ring) appears on hover/focus only. Clicking
 * (or Enter/Space when focused) opens an autosizing textarea in place. Commit on
 * blur; Escape cancels and restores the previous value.
 *
 * `dir` is passed through so Hebrew prose reads RTL and code/latin reads LTR —
 * default `auto` lets the browser infer per content.
 *
 * State discipline: this NEVER mutates the value it is given. It holds a local
 * draft while editing and only calls `onCommit` (blur) with the final string.
 */

interface EditableTextProps {
    value: string;
    onCommit: (next: string) => void;
    /** Accessible name, e.g. "טקסט שאלה 2 — לחצי לעריכה". Required (a11y default). */
    ariaLabel: string;
    dir?: 'rtl' | 'ltr' | 'auto';
    /** Shown (muted, as an add-affordance) when value is empty. Empty ⇒ nothing at rest. */
    placeholder?: string;
    /** Extra classes on the resting text element. */
    className?: string;
    /** Read-only render (no edit affordance) — used where editing is deferred. */
    readOnly?: boolean;
    /** Optional custom RESTING render of the value (e.g. D-4 prefix de-emphasis).
     *  Editing still edits the raw string — this only styles the at-rest display. */
    renderDisplay?: (value: string) => ReactNode;
}

export function EditableText({
    value,
    onCommit,
    ariaLabel,
    dir = 'auto',
    placeholder,
    className = '',
    readOnly = false,
    renderDisplay,
}: EditableTextProps) {
    const [editing, setEditing] = useState(false);
    const [draft, setDraft] = useState(value);
    const ref = useRef<HTMLTextAreaElement>(null);

    // Autosize + focus on entering edit; keep height in sync with the draft.
    useEffect(() => {
        if (editing && ref.current) {
            const el = ref.current;
            el.style.height = 'auto';
            el.style.height = `${el.scrollHeight}px`;
            el.focus();
            el.setSelectionRange(el.value.length, el.value.length);
        }
    }, [editing]);

    const startEdit = () => {
        if (readOnly) return;
        setDraft(value);
        setEditing(true);
    };

    const commit = () => {
        setEditing(false);
        if (draft !== value) onCommit(draft);
    };

    const cancel = () => {
        setDraft(value);
        setEditing(false);
    };

    if (editing) {
        return (
            <textarea
                ref={ref}
                value={draft}
                dir={dir}
                aria-label={ariaLabel}
                onChange={(e) => {
                    setDraft(e.target.value);
                    e.target.style.height = 'auto';
                    e.target.style.height = `${e.target.scrollHeight}px`;
                }}
                onBlur={commit}
                onKeyDown={(e) => {
                    if (e.key === 'Escape') { e.preventDefault(); cancel(); }
                    // Enter inserts a newline (prose is multi-line); blur commits.
                }}
                className={`w-full resize-none bg-white border border-primary-300 rounded-md px-2 py-1 outline-none focus:ring-2 focus:ring-primary-200 ${className}`}
                rows={1}
            />
        );
    }

    const isEmpty = value.trim() === '';
    if (isEmpty && !placeholder) {
        // Absence at rest — no empty box, no placeholder paragraph (§5).
        return readOnly ? null : (
            <span
                role="button"
                tabIndex={0}
                aria-label={ariaLabel}
                onClick={startEdit}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEdit(); } }}
                className="inline-block w-4 h-4 align-middle rounded hover:bg-surface-100 cursor-text"
            />
        );
    }

    return (
        <span
            role={readOnly ? undefined : 'button'}
            tabIndex={readOnly ? undefined : 0}
            aria-label={readOnly ? undefined : ariaLabel}
            dir={dir}
            onClick={startEdit}
            onKeyDown={readOnly ? undefined : (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); startEdit(); } }}
            className={`whitespace-pre-wrap ${readOnly ? '' : 'cursor-text rounded hover:bg-surface-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-200 decoration-dotted underline-offset-4 hover:underline'} ${isEmpty ? 'text-surface-400 italic' : ''} ${className}`}
        >
            {isEmpty ? placeholder : (renderDisplay ? renderDisplay(value) : value)}
        </span>
    );
}
