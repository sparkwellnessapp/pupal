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
    /**
     * WRAP long lines instead of scrolling them. The block then grows DOWNWARD to
     * the text it holds — four lines take more height than two — rather than
     * hiding the tail behind a horizontal scrollbar. Used for answer keys, where a
     * whole program can arrive as a single 1000-character line (the parser
     * collapses a 1x1 container cell's newlines).
     */
    wrap?: boolean;
    /** Render the bare <pre> with no card of its own — for use INSIDE a surface
     *  that already provides the background (the solution box). */
    bare?: boolean;
}

export function CodeBlock({ code, lines, caption, className = '', wrap = false, bare = false }: CodeBlockProps) {
    const text = code ?? (lines ?? []).join('\n');
    if (!text.trim()) return null;

    const flow = wrap ? 'whitespace-pre-wrap break-words' : 'overflow-x-auto whitespace-pre';
    const card = bare ? '' : 'bg-surface-50 border border-surface-200 rounded-md px-3 py-2';
    const pre = `font-mono text-doc-meta leading-relaxed text-surface-800 ${flow} ${card}`;

    // `dir="ltr"` is NOT negotiable even when the code carries Hebrew comments:
    // code reads left-to-right, and letting RTL reorder it mangles operators.
    if (bare) return <pre dir="ltr" className={`${pre} ${className}`}>{text}</pre>;

    return (
        <div className={`my-2 ${className}`}>
            {caption ? <div className="text-xs text-surface-500 mb-1" dir="ltr">{caption}</div> : null}
            <pre dir="ltr" className={pre}>{text}</pre>
        </div>
    );
}
