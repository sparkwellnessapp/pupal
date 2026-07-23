import type { ReactNode } from 'react';

/**
 * The shared LTR code island (PR-5 S2). Replaces the three copy-pasted `<pre>`
 * variants that were scattered through RubricEditor.
 *
 * Two invariants make code render correctly inside an RTL Hebrew document:
 *   - `dir="ltr"` — code reads left-to-right even when the surrounding paragraph
 *     is RTL; without it, symbols and operators mangle.
 *   - long lines scroll INSIDE the block (`overflow-x-auto`), never widening the
 *     page — the census's horizontal-scrollbar-on-her-words flaw dies here.
 *
 * Pure and stateless — safe to render on the server.
 */

interface CodeBlockProps {
    /** The code as a single string (newlines preserved) … */
    code?: string;
    /** … or as pre-split lines (either one; `code` wins if both are given). */
    lines?: string[];
    /** Optional caption rendered above the block (e.g. a language hint). */
    caption?: ReactNode;
    className?: string;
}

export function CodeBlock({ code, lines, caption, className = '' }: CodeBlockProps) {
    const text = code ?? (lines ?? []).join('\n');
    if (!text.trim()) return null;
    return (
        <div className={`my-2 ${className}`}>
            {caption ? <div className="text-xs text-surface-500 mb-1" dir="ltr">{caption}</div> : null}
            <pre
                dir="ltr"
                className="font-mono text-doc-meta leading-relaxed bg-surface-50 border border-surface-200 rounded-md px-3 py-2 overflow-x-auto whitespace-pre text-surface-800"
            >
                {text}
            </pre>
        </div>
    );
}
