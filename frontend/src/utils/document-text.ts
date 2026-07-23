/**
 * PR-5 Design Recovery — pure text-shaping for the document mirror (Phases 2.1–2.3).
 *
 * The production pipeline (`parser_render.py`) emits markers into question text:
 *   [TABLE N: RxC] + markdown pipe rows   → parsed by markdown-parser.ts (reused)
 *   [IMAGE: filename]                      → an unreadable-image placeholder
 *   [[color:RRGGBB]]text[[/color]]         → teacher ink; markers stripped (color
 *                                            discipline: red is reserved for blocking)
 * plus embedded code and Latin runs inside Hebrew prose. This module owns the PURE
 * decisions (marker stripping, code-run grouping, image detection); the React
 * renderer (DocumentText.tsx) composes them with the existing parseMarkdownText.
 *
 * Everything here is pure and unit-tested. NEVER mutates input.
 */

const COLOR_OPEN_RE = /\[\[color:[0-9A-Fa-f]{6}\]\]/g;
const COLOR_CLOSE_RE = /\[\[\/color\]\]/g;
const IMAGE_LINE_RE = /^\s*\[IMAGE:\s*(.*?)\]\s*$/;

/** Strip `[[color:RRGGBB]]…[[/color]]` markers, keeping the inner text verbatim. */
export function stripColorMarkers(text: string): string {
    return text.replace(COLOR_OPEN_RE, '').replace(COLOR_CLOSE_RE, '');
}

/** If a line is exactly an `[IMAGE: name]` marker, return the name; else null. */
export function imageMarkerName(line: string): string | null {
    const m = IMAGE_LINE_RE.exec(line);
    return m ? (m[1].trim() || 'תמונה') : null;
}

const HEBREW_RE = /[֐-׿]/;
const CODE_KEYWORD_RE = /^(public|private|protected|internal|static|void|int|bool|boolean|string|double|float|char|long|var|for|foreach|while|do|if|else|switch|case|return|class|struct|interface|new|using|namespace|import|def|function|const|let)\b/;

/**
 * Is this line code (not Hebrew prose)? Strong signals: a brace-only line, a
 * trailing `;`, a leading language keyword, or a symbol-dense line with NO Hebrew.
 * Blank lines are NOT code (handled as run continuation by the grouper).
 */
export function isCodeLine(line: string): boolean {
    const t = line.trim();
    if (!t) return false;
    if (HEBREW_RE.test(t)) return false;             // Hebrew ⇒ prose, always
    if (/^[{}()[\]]+$/.test(t)) return true;         // structural brace/paren line
    if (/;\s*$/.test(t)) return true;                // statement terminator
    if (CODE_KEYWORD_RE.test(t)) return true;        // language keyword
    const symbols = (t.match(/[(){}\[\];=<>+\-*/%&|]/g) ?? []).length;
    return symbols >= 3;                             // symbol-dense Latin line
}

export type TextBlock =
    | { kind: 'code'; text: string }
    | { kind: 'image'; name: string }
    | { kind: 'prose'; text: string };

/**
 * Group a text segment's lines into ordered blocks: consecutive code lines fuse
 * into ONE code block (killing the airy line-per-paragraph rendering), `[IMAGE]`
 * lines become image blocks, everything else is prose. A code run of fewer than
 * two non-blank lines is demoted to prose (a lone Latin line isn't a code block) —
 * precision-biased, like the table parser.
 */
export function groupTextBlocks(text: string): TextBlock[] {
    const lines = text.split('\n');
    const raw: TextBlock[] = [];
    let mode: 'code' | 'prose' | null = null;
    let buf: string[] = [];

    const flush = () => {
        if (buf.length === 0) return;
        // trim trailing blank lines off a block
        while (buf.length && !buf[buf.length - 1].trim()) buf.pop();
        if (buf.length) raw.push({ kind: mode === 'code' ? 'code' : 'prose', text: buf.join('\n') });
        buf = [];
    };

    for (const line of lines) {
        const img = imageMarkerName(line);
        if (img !== null) { flush(); mode = null; raw.push({ kind: 'image', name: img }); continue; }

        const blank = !line.trim();
        if (blank) { buf.push(line); continue; }   // blank extends the current run

        const want: 'code' | 'prose' = isCodeLine(line) ? 'code' : 'prose';
        if (mode !== null && mode !== want) flush();
        mode = want;
        buf.push(line);
    }
    flush();

    // Demote weak code blocks (< 2 non-blank lines) back to prose.
    return raw.map((b) => {
        if (b.kind !== 'code') return b;
        const nonBlank = b.text.split('\n').filter((l) => l.trim()).length;
        return nonBlank >= 2 ? b : { kind: 'prose', text: b.text };
    });
}

/**
 * Split a string into alternating Hebrew and Latin/code runs, so a renderer can
 * wrap the Latin runs in a bidi-isolating element (`<bdi dir="ltr">`) — killing
 * the "Check (arr, 6)B" mangling class where RTL reorders code internals.
 * Returns runs in order; `latin: true` marks the ones to isolate.
 */
export function bidiRuns(text: string): Array<{ text: string; latin: boolean }> {
    // A Latin run starts at a Latin letter and extends through following code-ish
    // chars (digits, brackets, operators, dots) so identifiers/calls stay intact.
    const re = /[A-Za-z][A-Za-z0-9_.,:;!?'"()[\]{}<>+\-*/%=&|]*/g;
    const runs: Array<{ text: string; latin: boolean }> = [];
    let last = 0;
    let m: RegExpExecArray | null;
    while ((m = re.exec(text))) {
        if (m.index > last) runs.push({ text: text.slice(last, m.index), latin: false });
        runs.push({ text: m[0], latin: true });
        last = m.index + m[0].length;
    }
    if (last < text.length) runs.push({ text: text.slice(last), latin: false });
    return runs;
}
