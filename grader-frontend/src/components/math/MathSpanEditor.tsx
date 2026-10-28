'use client';

/**
 * One formula, open for editing in a MathLive field (MATH_RENDERING_PLAN §4, OD-M6).
 *
 * The teacher edits the FORMULA, not its LaTeX: she sees the typeset expression and types
 * into it. The field speaks LaTeX to us and only to us.
 *
 * VIEWING IS NOT COMMITMENT (Δ14). MathLive re-serialises what it loads (`\frac{1}{e}` may
 * come back spelled differently), so "did she change it" is decided against the value the
 * FIELD reported when it opened, never against the source string. Open and close without a
 * keystroke and nothing is written — the item stays clean and stays in bulk-accept.
 */
import { useEffect, useRef, useState } from 'react';

import { MATH_EDIT_CANCEL, MATH_EDIT_SAVE, MATH_EDITOR_LOADING } from '@/copy/math';

type Field = HTMLElement & { value: string; focus: () => void };

export function MathSpanEditor({ body, onSave, onCancel, saveUnchanged = false }: {
    body: string;
    /** Called only when the formula changed; the caller splices it into the answer. */
    onSave: (latex: string) => void;
    onCancel: () => void;
    /** A NEW reading may be saved empty (an unlabelled asymptote is still a reading). */
    saveUnchanged?: boolean;
}) {
    const hostRef = useRef<HTMLDivElement>(null);
    const fieldRef = useRef<Field | null>(null);
    const openedAs = useRef<string | null>(null);
    const [ready, setReady] = useState(false);

    const commit = () => {
        const field = fieldRef.current;
        if (!field || openedAs.current === null) return onCancel();
        if (field.value === openedAs.current && !saveUnchanged) return onCancel();   // viewed, not changed
        onSave(field.value);
    };

    useEffect(() => {
        let alive = true;
        let field: Field | null = null;
        import('@/lib/mathlive-bundle').then(({ MathfieldElement }) => {
            if (!alive || !hostRef.current) return;
            field = new MathfieldElement() as unknown as Field;
            field.setAttribute('data-math-field', '');
            field.style.minWidth = '6rem';
            field.style.fontSize = '1.1em';
            field.value = body;
            hostRef.current.appendChild(field);
            fieldRef.current = field;
            openedAs.current = field.value;
            setReady(true);
            field.focus();
        }).catch(() => { if (alive) onCancel(); });
        return () => {
            alive = false;
            field?.remove();
            fieldRef.current = null;
        };
        // `body` is read once, at open: re-seeding the field mid-edit would drop her keystrokes.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    return (
        <span
            data-testid="math-span-editor"
            className="inline-flex flex-wrap items-center gap-1.5 rounded-md border border-primary-300 bg-white px-1.5 py-1 align-middle"
            // The editor sits INSIDE a clickable line: a click here (the field, «שמירה»,
            // «ביטול») must not also open that line as text.
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commit(); }
                if (e.key === 'Escape') { e.preventDefault(); onCancel(); }
            }}
        >
            <span ref={hostRef} dir="ltr" className="inline-block" />
            {!ready && <span className="text-xs text-gray-500">{MATH_EDITOR_LOADING}</span>}
            <button
                type="button"
                data-testid="math-span-save"
                onClick={commit}
                className="rounded bg-primary-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-primary-700"
            >
                {MATH_EDIT_SAVE}
            </button>
            <button
                type="button"
                onClick={onCancel}
                className="rounded px-2 py-0.5 text-xs text-gray-600 hover:bg-surface-100"
            >
                {MATH_EDIT_CANCEL}
            </button>
        </span>
    );
}
